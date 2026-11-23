"""Robust insamling: fel, omförsök, timeout, anropsgräns, återupptagning och omkörning av en källa."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, ekonomi
from app.insamling import kor_insamling
from app.main import standardkallor
from app.recorded import InspeladTransport
from app.robust import Robusthet
from app.sources.kolada import Kolada
from conftest import INSPELNINGAR, skapa_app

SCB = "api.scb.se"


def scb_tabeller() -> int:
    return len({m.tabell for m in next(k for k in standardkallor() if k.id == "scb").matt})


class Strulande(httpx.BaseTransport):
    """Inspelade svar, men de `antal` första anropen till `vard` misslyckas på angivet sätt."""

    def __init__(self, vard: str, antal: int, fel: str = "503") -> None:
        self.inre = InspeladTransport(INSPELNINGAR)
        self.vard, self.kvar, self.fel = vard, antal, fel
        self.anrop: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.anrop.append(request.url.host)
        if request.url.host == self.vard and self.kvar:
            self.kvar -= 1
            if self.fel == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            return httpx.Response(int(self.fel), request=request)
        return self.inre.handle_request(request)


class FalskTid:
    def __init__(self) -> None:
        self.nu = 0.0
        self.pauser: list[float] = []

    def sov(self, s: float) -> None:
        self.pauser.append(s)
        self.nu += s

    def robusthet(self) -> Robusthet:
        return Robusthet(sov=self.sov, klocka=lambda: self.nu)


def insamling(api: TestClient, **params) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar", params=params)
    assert svar.status_code == 200, svar.text
    return svar.json()


def per_kalla(res: dict) -> dict[str, dict]:
    return {k["datakalla_id"]: k for k in res["kallor"]}


def test_en_kalla_med_fel_stoppar_inte_de_andra(database_url, google):
    transport = Strulande(SCB, antal=10**6, fel="500")
    api = TestClient(skapa_app(database_url, google, transport=transport, anonym_lasning=True))
    res = per_kalla(insamling(api))
    assert res["kolada"]["status"] == "lyckad"
    assert res["scb"]["status"] == "misslyckad"
    assert "500" in res["scb"]["fel"]
    # Kolada:s uppgifter finns, SCB:s inte.
    ekonomi = api.get("/api/ekonomi").json()
    serier = {
        v["id"]: v["serie"] for g in ekonomi["grupper"] for n in g["nyckeltal"] for v in (n, n["per_invanare"]) if v
    }
    assert serier["kolada:N03007"]["punkter"]
    assert serier["scb:ResultKnN:120"] is None
    # Varje anrop försöktes tre gånger innan det gav upp.
    assert transport.anrop.count(SCB) == 3 * scb_tabeller()


@pytest.mark.parametrize("fel", ["503", "429", "timeout"])
def test_tillfalligt_fel_forsoks_igen_och_ger_lyckad(database_url, google, fel):
    tid = FalskTid()
    api = TestClient(skapa_app(database_url, google, transport=Strulande(SCB, antal=2, fel=fel),
                               robusthet=tid.robusthet(), anonym_lasning=True))
    res = insamling(api)
    assert res["status"] == "lyckad"
    assert per_kalla(res)["scb"]["status"] == "lyckad"
    assert per_kalla(res)["scb"]["fel"] is None
    # Fördröjningen växer mellan försöken.
    assert tid.pauser[:2] == [2.0, 4.0]


def test_anropsfrekvensen_per_kalla_ar_konfigurerbar(database_url, google, monkeypatch):
    monkeypatch.setenv("SCB_ANROP_PER_SEKUND", "4")
    monkeypatch.setenv("KOLADA_ANROP_PER_SEKUND", "0")
    kallor = {k.id: k for k in standardkallor()}
    assert kallor["scb"].anrop_per_sekund == 4
    assert kallor["kolada"].anrop_per_sekund is None

    tid = FalskTid()
    api = TestClient(skapa_app(database_url, google, kallor=[kallor["scb"]], robusthet=tid.robusthet(),
                               anonym_lasning=True))
    insamling(api)
    # Ett anrop per SCB-tabell, med en kvarts sekund mellan anropen.
    assert tid.pauser == pytest.approx([0.25] * (scb_tabeller() - 1))


class Avbrott(BaseException):
    """Som när processen stoppas mitt i en körning."""


class AvbrytandeKalla:
    id, titel, url, anrop_per_sekund = "scb", "SCB", "https://www.scb.se", None

    def hamta(self, client, sedan):
        raise Avbrott()


class RaknadKolada(Kolada):
    def __init__(self) -> None:
        super().__init__(ekonomi.KOLADA)
        self.antal = 0

    def hamta(self, client, sedan):
        self.antal += 1
        return super().hamta(client, sedan)


def test_avbruten_korning_ateruptas_utan_dubbletter(database_url):
    db.migrate(database_url)
    scb = next(k for k in standardkallor() if k.id == "scb")
    kolada = RaknadKolada()
    snabb = Robusthet(sov=lambda s: None)
    with db.connect(database_url) as conn, httpx.Client(transport=InspeladTransport(INSPELNINGAR)) as client:
        with pytest.raises(Avbrott):
            kor_insamling(conn, [kolada, AvbrytandeKalla()], client, robusthet=snabb)
        conn.rollback()
        [forsta] = conn.execute("SELECT id, status FROM insamlingskorning").fetchall()
        assert forsta["status"] == "pagar"

        res = kor_insamling(conn, [kolada, scb], client, robusthet=snabb)
        assert res.korning_id == forsta["id"]  # samma körning återupptas
        assert kolada.antal == 1  # Kolada var redan klar och hämtas inte igen
        assert res.status == "lyckad"
        assert {k.datakalla_id for k in res.kallor} == {"kolada", "scb"}

        # En körning till: inget nytt, inget dubblerat.
        andra = kor_insamling(conn, [kolada, scb], client, robusthet=snabb)
        assert andra.korning_id != forsta["id"]
        assert all(k.status == "inga_nya" for k in andra.kallor)
        dubbletter = conn.execute(
            "SELECT count(*) AS n FROM observation GROUP BY matt_id, omrade, period HAVING count(*) > 1"
        ).fetchall()
        assert dubbletter == []
        assert conn.execute("SELECT count(*) AS n FROM insamlingskorning WHERE status = 'pagar'").fetchone()["n"] == 0


def test_redaktor_kan_kora_om_en_enskild_kalla(database_url, google):
    api = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    insamling(api)
    res = insamling(api, kalla="scb")
    assert [k["datakalla_id"] for k in res["kallor"]] == ["scb"]
    assert res["status"] == "lyckad"
    logg = api.get("/api/insamlingar").json()
    assert [k["datakalla_id"] for k in logg[0]["kallor"]] == ["scb"]

    assert api.post("/api/insamlingar", params={"kalla": "finns-inte"}).status_code == 404
    api.post("/api/auth/logga-ut")
    assert api.post("/api/insamlingar", params={"kalla": "scb"}).status_code in (401, 403)
