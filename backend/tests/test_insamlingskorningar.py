"""Insamlingskörningar och uppdateringsstatus: global status, status per datakälla och körningslogg."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.sources.kolada import Kolada
from conftest import skapa_app


class TrasigKalla:
    """En datakälla som alltid misslyckas, t.ex. för att webbplatsen är nere."""

    id = "trasig"
    titel = "Trasig källa"
    url = "https://trasig.example"

    def hamta(self, client, sedan):
        raise httpx.ConnectError("Värden svarar inte")


@pytest.fixture
def api(database_url, google) -> TestClient:
    """Öppen läsning, som i produktion."""
    return TestClient(skapa_app(database_url, google, anonym_lasning=True))


def kor(api: TestClient) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar")
    assert svar.status_code == 200
    api.post("/api/auth/logga-ut")
    return svar.json()


def kalla(api: TestClient, id: str) -> dict:
    [k] = [k for k in api.get("/api/datakallor").json() if k["id"] == id]
    return k


def test_innan_nagon_insamling_ar_informationen_inte_uppdaterad(api):
    status = api.get("/api/status").json()
    assert status["senaste_korning"] is None
    assert status["senaste_lyckade_korning"] is None
    assert status["fullstandigt_uppdaterad"] is False

    kolada = kalla(api, "kolada")
    assert kolada["titel"] == "Kolada"
    assert kolada["senaste_kontroll"] is None
    assert kolada["status"] is None
    assert api.get("/api/insamlingar").json() == []


def test_forsta_korningen_registreras_med_resultat_per_kalla(api):
    kor(api)  # status och logg är öppna för läsare utan inloggning

    status = api.get("/api/status").json()
    assert status["senaste_korning"]["status"] == "lyckad"
    assert status["senaste_korning"]["utlosare"] == "manuell"
    assert status["senaste_korning"]["avslutad"]
    assert status["senaste_lyckade_korning"]["id"] == status["senaste_korning"]["id"]
    # Kolada, SCB, SKR, protokollen från fem organ, sammanträdesplanerna, Valmyndigheten och två rankningar
    assert status["kallor_kontrollerade"] == 12
    assert status["kallor_utan_fel"] == 12
    assert status["fullstandigt_uppdaterad"] is True

    kolada = kalla(api, "kolada")
    assert kolada["status"] == "lyckad"
    assert kolada["senaste_kontroll"]
    assert kolada["senaste_lyckade_hamtning"] == kolada["senaste_kontroll"]
    assert kolada["senaste_publicering"] == "2026-08-28"
    assert kolada["fel"] is None

    [korning] = api.get("/api/insamlingar").json()
    assert {r["datakalla_id"] for r in korning["kallor"]} == {
        "kolada", "scb", "skr-skatteunderlagsprognos", *(f"harnosand-protokoll-{o}" for o in ("kf", "ks", "sam", "soc", "skol")),
        "harnosand-sammantradesplaner", "valmyndigheten", "foretagsklimat", "miljobasta-kommun"}
    [rad] = [r for r in korning["kallor"] if r["datakalla_id"] == "kolada"]
    assert rad["status"] == "lyckad"
    assert rad["antal_nya"] > 0
    assert rad["senaste_publicering"] == "2026-08-28"


def test_andra_korningen_utan_andringar_ar_inga_nya_uppgifter(api):
    kor(api)
    kor(api)

    andra, forsta = api.get("/api/insamlingar").json()  # senaste först
    for fore, rad in zip(forsta["kallor"], andra["kallor"]):
        assert fore["status"] == "lyckad"
        assert rad["status"] == "inga_nya"
        assert rad["antal_nya"] == 0
        assert rad["antal_andrade"] == 0
        if rad["datakalla_id"].startswith("harnosand-protokoll"):
            # Protokollen på organets sida hämtas igen (högst två i inspelningen), arkivets inte.
            assert 0 < rad["antal_oforandrade"] <= 2 < fore["antal_nya"]
        else:
            assert rad["antal_oforandrade"] == fore["antal_nya"]

    # En körning utan nya uppgifter är fortfarande en lyckad kontroll.
    assert andra["status"] == "lyckad"
    assert kalla(api, "kolada")["status"] == "inga_nya"
    assert api.get("/api/status").json()["fullstandigt_uppdaterad"] is True


def test_global_status_nar_en_kalla_har_fel(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[Kolada(["N03007"]), TrasigKalla()], anonym_lasning=True))
    korning = kor(api)
    assert korning["status"] == "delvis_fel"

    status = api.get("/api/status").json()
    assert status["senaste_korning"]["status"] == "delvis_fel"
    assert status["senaste_lyckade_korning"] is None
    assert status["kallor_kontrollerade"] == 2
    assert status["kallor_utan_fel"] == 1
    assert status["fullstandigt_uppdaterad"] is False

    trasig = kalla(api, "trasig")
    assert trasig["status"] == "misslyckad"
    assert "Värden svarar inte" in trasig["fel"]
    assert trasig["senaste_kontroll"]
    assert trasig["senaste_lyckade_hamtning"] is None
    assert kalla(api, "kolada")["status"] == "lyckad"


def test_omkorning_av_en_enskild_kalla_gor_inte_de_andra_inaktuella(api):
    kor(api)
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/insamlingar", params={"kalla": "kolada"}).status_code == 200

    status = api.get("/api/status").json()
    assert status["kallor_kontrollerade"] == 12
    assert status["kallor_utan_fel"] == 12
    assert status["fullstandigt_uppdaterad"] is True


def test_en_ny_kontroll_med_fel_gor_informationen_delvis_inaktuell(database_url, google):
    kallor = [Kolada(["N03007"]), TrasigKalla()]
    api = TestClient(skapa_app(database_url, google, kallor=kallor, anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    api.post("/api/insamlingar", params={"kalla": "kolada"})

    # Den trasiga källan är aldrig kontrollerad.
    status = api.get("/api/status").json()
    assert (status["kallor_kontrollerade"], status["fullstandigt_uppdaterad"]) == (1, False)

    # Källans senaste kontroll avgör, även om en tidigare körning gick bra.
    api.post("/api/insamlingar", params={"kalla": "trasig"})
    api.post("/api/insamlingar", params={"kalla": "kolada"})
    status = api.get("/api/status").json()
    assert (status["kallor_kontrollerade"], status["kallor_utan_fel"]) == (2, 1)
    assert status["fullstandigt_uppdaterad"] is False


def test_en_kalla_dar_bara_en_del_misslyckas_far_delvis_fel(database_url, google):
    # N99999 saknas i inspelningen, så det nyckeltalet går inte att hämta.
    api = TestClient(skapa_app(database_url, google, kallor=[Kolada(["N03007", "N99999"])], anonym_lasning=True))
    kor(api)

    kolada = kalla(api, "kolada")
    assert kolada["status"] == "delvis_fel"
    assert "N99999" in kolada["fel"]
    assert kolada["senaste_lyckade_hamtning"] is None
    assert api.get("/api/status").json()["fullstandigt_uppdaterad"] is False
    # Det som gick att hämta finns ändå.
    assert len(api.get("/api/matt/kolada:N03007/serie").json()["punkter"]) > 0
