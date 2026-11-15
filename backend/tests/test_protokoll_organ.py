"""Protokoll från alla beslutande organ, med arkivet från 2022 (#29).

Insamlingen körs mot inspelade svar från harnosand.se, med två protokoll per sida och årsmapp
(PROTOKOLL_URVAL=2, se conftest). De förväntade värdena är kontrollerade för hand mot protokollen.
"""

from __future__ import annotations

import httpx
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient

from app.main import standardkallor
from app.recorded import InspeladTransport

ORGAN = ("KF", "KS", "SAM", "SOC", "SKOL")


def protokollkallor():
    return [k for k in standardkallor() if k.id.startswith("harnosand-protokoll")]


class Raknande(httpx.BaseTransport):
    """Inspelade svar. Räknar anropen, och kan låta vissa adresser saknas (404)."""

    def __init__(self, saknas: tuple[str, ...] = ()) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.saknas = saknas
        self.anrop: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.anrop.append(str(request.url))
        if any(s in request.url.path for s in self.saknas):
            return httpx.Response(404, request=request)
        return self.inspelad.handle_request(request)


def app(database_url, google, transport=None) -> TestClient:
    return TestClient(skapa_app(database_url, google, kallor=protokollkallor(), transport=transport))


def kor(api: TestClient) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar")
    assert svar.status_code == 200, svar.text
    return svar.json()


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = app(database_url, google)
    kor(a)
    return a


def sammantrade(api: TestClient, organ: str, datum: str) -> dict:
    [s] = [s for s in api.get("/api/sammantraden", params={"organ": organ}).json() if s["datum"] == datum]
    return api.get(f"/api/sammantraden/{s['id']}").json()


def person(s: dict, namn: str) -> dict:
    [p] = [p for p in s["narvaro"] if p["namn"] == namn]
    return p


def test_varje_organ_ar_en_egen_kalla_med_protokoll_fran_sidan_och_arkivet(database_url, google):
    a = app(database_url, google)
    korning = kor(a)
    assert {r["datakalla_id"]: r["status"] for r in korning["kallor"]} == {
        f"harnosand-protokoll-{o.lower()}": "lyckad" for o in ORGAN
    }
    titlar = {k["id"]: k["titel"] for k in a.get("/api/datakallor").json()}
    assert titlar["harnosand-protokoll-sam"] == "Härnösands kommun – protokoll, samhällsnämnden"

    assert [o["id"] for o in a.get("/api/organ").json()] == list(ORGAN)
    lista = a.get("/api/sammantraden").json()
    for organ in ORGAN:
        ar = {s["datum"][:4] for s in lista if s["organ"]["id"] == organ}
        # Innevarande år från organets sida, 2022–2025 ur arkivet. Äldre år hämtas inte.
        assert ar == {"2022", "2023", "2024", "2025", "2026"}, organ
    assert all(s["tolkning"] == "tolkad" for s in lista)


def test_narvaro_med_en_rad_per_person_och_tjanstgorande_ersattare(api):
    s = sammantrade(api, "SAM", "2023-01-26")
    assert s["organ"] == {"id": "SAM", "namn": "Samhällsnämnden"}
    assert (person(s, "Helena Elfvendal")["parti"], person(s, "Helena Elfvendal")["roll"]) == ("MP", "Ordförande")
    kurt = person(s, "Kurt Rydqvist")
    assert (kurt["kategori"], kurt["roll"]) == ("beslutande", "Ersättare")
    assert kurt["tjanstgor_for"] == {"namn": "Elisabeth Strömqvist", "parti": "S"}

    s = sammantrade(api, "SOC", "2023-02-23")
    assert person(s, "Simon Andersson")["tjanstgor_for"] == {"namn": "Agneta Jonsson", "parti": "S"}
    assert person(s, "Ingrid Mähler")["kategori"] == "ej_tjanstgorande"
    assert not [p for p in s["narvaro"] if p["kategori"] == "ovrig"]  # tjänstepersoner tas inte med

    s = sammantrade(api, "KS", "2025-01-21")
    assert person(s, "Göran Kejerhag Östlund")["tjanstgor_for"] == {"namn": "Eva-Clara Viklund", "parti": "M"}
    # "()" i protokollet: parti anges inte, och partiet härleds ur ett annat protokoll.
    baran = person(s, "Baran Hosseini")
    assert baran["parti_harlett"]["grund"] in ("samma_protokoll", "annat_protokoll")
    assert not [p for p in s["narvaro"] if p["namn"] == "ordförande"]  # radbruten roll är ingen person

    s = sammantrade(api, "SKOL", "2022-02-24")
    olsson = person(s, "Anna-Lena Olsson")
    assert isinstance(olsson.pop("ledamot_id"), int)  # länk till ledamotsregistret
    assert olsson == {
        "namn": "Anna-Lena Olsson", "parti": "S", "roll": "Ersättare", "kategori": "ej_tjanstgorande",
        "tjanstgor_for": None, "paragrafer": None, "jav": [],
    }


def test_aldre_narvarotabeller_med_radbrutna_rader(api):
    s = sammantrade(api, "KF", "2024-02-26")
    beslutande = [p for p in s["narvaro"] if p["kategori"] == "beslutande"]
    assert len(beslutande) == 44
    assert person(s, "Ester Sundin Hemström")["parti"] == "M"  # namnet bryts över två rader
    assert person(s, "Ro Blomkvist")["paragrafer"] == list(range(1, 14))
    hans = person(s, "Hans Rosengren")
    assert hans["tjanstgor_for"] == {"namn": "Ro Blomkvist", "parti": "S"}
    assert hans["paragrafer"] == list(range(14, 19))


def test_paragrafprotokoll_galler_tills_hela_protokollet_finns(database_url, google):
    # Först finns bara samhällsnämndens direktjusterade § 145 från 2026-10-29.
    a = app(database_url, google, transport=Raknande(saknas=("samhällsnämnden 2026-10-29.pdf",)))
    [sam] = [r for r in kor(a)["kallor"] if r["datakalla_id"] == "harnosand-protokoll-sam"]
    assert sam["status"] == "delvis_fel"
    fore = sammantrade(a, "SAM", "2026-10-29")
    assert fore["protokoll"]["typ"] == "paragrafprotokoll"
    assert [b["paragraf"] for b in fore["behandlingar"]] == [145]
    pp_dokument = fore["protokoll"]["kopia"]

    # Hela protokollet publiceras: det ersätter paragrafprotokollet i samma sammanträde.
    b = app(database_url, google)
    kor(b)
    efter = sammantrade(b, "SAM", "2026-10-29")
    assert efter["id"] == fore["id"]
    assert efter["protokoll"]["typ"] == "protokoll"
    assert efter["protokoll"]["filnamn"] == "Protokoll samhällsnämnden 2026-10-29.pdf"
    assert len(efter["behandlingar"]) == 24
    assert b.get(pp_dokument).status_code == 200  # paragrafprotokollet finns kvar som dokument

    # En ny hämtning av paragrafprotokollet ändrar inte sammanträdet.
    kor(b)
    assert sammantrade(b, "SAM", "2026-10-29")["protokoll"]["typ"] == "protokoll"


def test_arkivets_protokoll_hamtas_bara_en_gang(database_url, google):
    forsta = Raknande()
    kor(app(database_url, google, transport=forsta))
    andra = Raknande()
    [ks] = [r for r in kor(app(database_url, google, transport=andra))["kallor"]
            if r["datakalla_id"] == "harnosand-protokoll-ks"]
    assert ks["status"] == "inga_nya"

    pdf_forsta = {u for u in forsta.anrop if u.endswith(".pdf")}
    pdf_andra = {u for u in andra.anrop if u.endswith(".pdf")}
    assert len(pdf_forsta) == 50  # 2 per sida och årsmapp, 5 organ
    # Andra gången hämtas bara protokollen på organens sidor, där innehållet kan bytas ut.
    assert len(pdf_andra) == 10
    assert pdf_andra < pdf_forsta


def test_filter_per_ar_och_sokning_pa_rubrik_och_diarienummer(api):
    lista = api.get("/api/sammantraden", params={"organ": "SAM", "ar": 2023}).json()
    assert [s["datum"] for s in lista] == ["2023-02-23", "2023-01-26"]

    # Samma ärende behandlat i kommunstyrelsen och fullmäktige.
    svar = api.get("/api/behandlingar", params={"q": "2024-000533"}).json()
    assert [(t["sammantrade"]["organ"]["id"], t["sammantrade"]["datum"], t["paragraf"]) for t in svar["traffar"]] == [
        ("KF", "2025-03-24", 23), ("KS", "2025-03-04", 38),
    ]
    assert svar["antal"] == 2
    assert svar["traffar"][0]["rubrik"].startswith("Hemställan om godkännande av budgetavvikelse")

    svar = api.get("/api/behandlingar", params={"q": "BUDGETUPPFÖLJNING", "organ": "SOC"}).json()
    assert svar["antal"] >= 2
    assert all(t["sammantrade"]["organ"]["id"] == "SOC" for t in svar["traffar"])
    assert all("budgetuppföljning" in t["rubrik"].lower() for t in svar["traffar"])

    svar = api.get("/api/behandlingar", params={"q": "budget", "ar": 2026}).json()
    assert svar["antal"] > 0 and all(t["sammantrade"]["datum"].startswith("2026") for t in svar["traffar"])

    # Jokertecken i söktexten är vanliga tecken.
    assert api.get("/api/behandlingar", params={"q": "%%"}).json()["antal"] == 0
    assert api.get("/api/behandlingar", params={"q": "x"}).status_code == 422
