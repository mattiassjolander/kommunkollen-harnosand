"""Ett nyckeltal hela vägen: insamling från Kolada → observationer → tidsserie i API:t."""

import json

from conftest import INSPELNINGAR

MATT = "kolada:N03007"


def antal_perioder_i_inspelningen() -> int:
    manifest = json.loads((INSPELNINGAR / "manifest.json").read_text(encoding="utf-8"))
    fil = manifest["api.kolada.se/v3/data/kpi/N03007/municipality/2280"]
    data = json.loads((INSPELNINGAR / fil).read_text(encoding="utf-8"))
    return len(data["values"])


def kallresultat(korning: dict, id: str) -> dict:
    [k] = [k for k in korning["kallor"] if k["datakalla_id"] == id]
    return k


def test_insamling_ger_tidsserie_med_kalla_och_tidpunkter(redaktor):
    api = redaktor
    svar = api.post("/api/insamlingar")
    assert svar.status_code == 200
    korning = svar.json()
    assert korning["status"] == "lyckad"
    kolada = kallresultat(korning, "kolada")
    assert kolada["status"] == "lyckad"
    assert kolada["antal_nya"] >= antal_perioder_i_inspelningen()

    serie = api.get(f"/api/matt/{MATT}/serie").json()
    assert serie["matt"]["titel"] == "Årets resultat kommun, kr/inv"
    assert serie["matt"]["enhet"] == "kr/inv"
    assert serie["matt"]["datakalla"] == {"id": "kolada", "titel": "Kolada", "url": "https://www.kolada.se"}
    assert serie["omrade"] == "2280"

    punkter = {p["period"]: p for p in serie["punkter"]}
    assert len(punkter) == antal_perioder_i_inspelningen()
    p2025 = punkter["2025"]
    assert p2025["varde"] == 972.194841
    assert p2025["kallans_publicering"] == "2026-08-28"  # källans publicering
    assert p2025["hamtad"]  # när plattformen hämtade värdet
    assert p2025["version"] == 1
    assert [p["period"] for p in serie["punkter"]] == sorted(punkter)  # i periodordning


def test_andra_insamlingen_utan_andringar_ger_inga_nya_uppgifter(redaktor):
    api = redaktor
    api.post("/api/insamlingar")
    forsta = api.get(f"/api/matt/{MATT}/serie").json()

    korning = api.post("/api/insamlingar").json()
    for kalla in korning["kallor"]:
        assert kalla["status"] == "inga_nya"
        assert kalla["antal_nya"] == 0
        assert kalla["antal_andrade"] == 0

    andra = api.get(f"/api/matt/{MATT}/serie").json()
    for fore, efter in zip(forsta["punkter"], andra["punkter"], strict=True):
        # Bara tidpunkten för senaste hämtning flyttas fram. Ingen ny version, ingen ändring.
        assert efter["senast_hamtad"] > fore["senast_hamtad"]
        assert {k: v for k, v in efter.items() if k != "senast_hamtad"} ==             {k: v for k, v in fore.items() if k != "senast_hamtad"}


def test_okant_matt_ger_404(redaktor):
    api = redaktor
    assert api.get("/api/matt/kolada:FINNS_EJ/serie").status_code == 404
