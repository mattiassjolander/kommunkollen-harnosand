"""Brodiagrammet för årets resultat (#81): delarna ur SCB och kontrollen mot årets resultat."""

import pytest
from fastapi.testclient import TestClient

from app import resultatbro
from conftest import skapa_app


def varden(ar: str = "2024", **andrat) -> dict[str, dict[str, float | None]]:
    v = {
        "scb:ResultKnN:040": 1000.0, "scb:ResultKnN:050": 500.0, "scb:ResultKnN:030": -1450.0,
        "scb:ResultKnN:060": 10.0, "scb:ResultKnN:072": -40.0, "scb:ResultKnN:085": 0.0,
        "scb:ResultKnN:120": 20.0,
    }
    v.update({f"scb:ResultKnN:{k[1:]}": x for k, x in andrat.items()})
    return {m: {ar: x} for m, x in v.items()}


def test_delarna_summerar_till_arets_resultat():
    b = resultatbro.bro(varden())
    ar = b["ar"]["2024"]
    assert [s["id"] for s in ar["steg"]] == ["skatteintakter", "statsbidrag", "nettokostnader", "finansnetto"]
    finans = next(s for s in ar["steg"] if s["id"] == "finansnetto")
    assert finans["varde"] == -30.0
    assert "Summerat av Kommunkollen" in finans["markering"]
    assert ar["kontroll"] == {"summa_av_delar": 20.0, "avvikelse": 0.0, "restpost": False}
    assert b["standardar"] == "2024"


def test_extraordinara_poster_visas_bara_nar_de_inte_ar_noll():
    ar = resultatbro.bro(varden(p085=5.0, p120=25.0))["ar"]["2024"]
    assert ar["steg"][-1]["id"] == "extraordinart"
    assert ar["kontroll"]["avvikelse"] == 0.0


def test_en_avvikelse_mot_scbs_resultat_visas_och_doljs_inte():
    ar = resultatbro.bro(varden(p120=120.0))["ar"]["2024"]
    assert ar["kontroll"]["avvikelse"] == 100.0
    assert ar["resultat"] == 120.0


def test_saknas_finansnettot_blir_skillnaden_en_markerad_restpost():
    b = resultatbro.bro(varden(p060=None))
    ar = b["ar"]["2024"]
    rest = ar["steg"][-1]
    assert rest["id"] == "ovrigt" and rest["titel"] == "Övrigt inklusive finansnetto"
    assert rest["markering"] == "Beräknat av Kommunkollen"
    assert rest["varde"] == -30.0
    assert ar["kontroll"]["restpost"] is True
    assert ar["kontroll"]["avvikelse"] == 0.0


def test_utan_arets_resultat_finns_ingen_bro():
    assert resultatbro.bro(varden(p120=None))["ar"] == {}


def test_bron_mot_riktiga_data_summerar_till_scbs_arets_resultat(database_url, google):
    api = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/insamlingar").json()["status"] == "lyckad"
    b = api.get("/api/ekonomi/resultatbro").json()
    assert b["standardar"] == "2025"
    assert set(b["matt"]) == set(resultatbro.matt())
    for ar, data in b["ar"].items():
        # Kontrollen mot SCB:s årets resultat, år för år.
        assert data["kontroll"]["avvikelse"] == 0, ar
        assert sum(s["varde"] for s in data["steg"]) == pytest.approx(data["resultat"], abs=1), ar
    assert b["ar"]["2024"]["resultat"] == -91043
    assert {s["id"]: s["varde"] for s in b["ar"]["2024"]["steg"]}["finansnetto"] == 7287 - 80582
