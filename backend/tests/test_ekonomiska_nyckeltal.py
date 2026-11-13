"""Ekonomiska nyckeltal från Kolada och SCB, som ekonomivyn visar dem."""

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app import ekonomi
from app.sources.scb import Scb, ScbMatt
from conftest import INSPELNINGAR, skapa_app

SCB_BALANS = "api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0107/OE0107A/BalansKnN"


def inspelning(nyckel: str) -> dict:
    manifest = json.loads((INSPELNINGAR / "manifest.json").read_text(encoding="utf-8"))
    return json.loads((INSPELNINGAR / manifest[nyckel]).read_text(encoding="utf-8-sig"))


@pytest.fixture
def api(database_url, google) -> TestClient:
    api = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/insamlingar").json()["status"] == "lyckad"
    return api


def nyckeltal(api: TestClient) -> dict[str, dict]:
    svar = api.get("/api/ekonomi").json()
    return {n["id"]: n for g in svar["grupper"] for n in g["nyckeltal"]}


def punkter(n: dict) -> dict[str, float | None]:
    return {p["period"]: p["varde"] for p in n["serie"]["punkter"]}


def test_alla_nyckeltal_i_katalogen_visas_grupperade_med_forklaring_och_enhet(api):
    svar = api.get("/api/ekonomi").json()
    assert [g["id"] for g in svar["grupper"]] == [g.id for g in ekonomi.GRUPPER]
    alla = nyckeltal(api)
    assert list(alla) == [m for g in ekonomi.GRUPPER for m in g.matt]
    for id, n in alla.items():
        assert n["serie"] is not None, f"{id} saknar data"
        matt = n["serie"]["matt"]
        assert matt["titel"] and matt["beskrivning"] and matt["enhet"], id
        assert matt["datakalla"]["id"] in ("kolada", "scb")
        assert n["serie"]["punkter"], id


def test_kolada_nyckeltal_i_procent_saknar_prisniva(api):
    soliditet = nyckeltal(api)["kolada:N03002"]
    assert soliditet["serie"]["matt"]["enhet"] == "%"
    assert soliditet["prisniva"] is None
    assert soliditet["serie"]["matt"]["datakalla"]["titel"] == "Kolada"

    skatt = nyckeltal(api)["kolada:N03010"]
    assert skatt["serie"]["matt"]["enhet"] == "kr/inv"
    assert skatt["prisniva"] == "löpande priser"


def test_framtida_publiceringsdatum_fran_kolada_raknas_inte_som_publicering(api):
    # Kolada anger nästa planerade publicering (2027) för nettoinvesteringar.
    kpi = inspelning("api.kolada.se/v3/kpi/N03132")["values"][0]
    assert kpi["publication_date"] > "2026-12-31"
    assert nyckeltal(api)["kolada:N03132"]["serie"]["matt"]["kallans_publicering"] is None


def test_scb_ger_hela_tidsserien_i_tkr_med_publiceringsdatum(api):
    likvida = nyckeltal(api)["scb:BalansKnN:065"]
    matt = likvida["serie"]["matt"]
    assert matt["titel"] == "Likvida medel"
    assert matt["enhet"] == "tkr"
    assert matt["datakalla"]["titel"] == "SCB"
    assert matt["kallans_publicering"] == "2026-08-28"
    assert likvida["prisniva"] == "löpande priser"

    data = inspelning(SCB_BALANS)["data"]
    forvantat = {r["key"][2]: float(r["values"][0]) for r in data if r["key"][1] == "065"}
    assert punkter(likvida) == forvantat
    assert min(punkter(likvida)) == "1998"  # så långt bakåt som källan har


def test_rorelsekapital_beraknas_som_omsattningstillgangar_minus_kortfristiga_skulder(api):
    alla = nyckeltal(api)
    oms, kort, rorelse = (punkter(alla[i]) for i in ("scb:BalansKnN:069", "scb:BalansKnN:098", "scb:rorelsekapital"))
    assert rorelse["2025"] == pytest.approx(oms["2025"] - kort["2025"])
    assert "Beräknat" in alla["scb:rorelsekapital"]["serie"]["matt"]["beskrivning"]


def test_saknade_varden_fran_scb_blir_null_aldrig_noll(database_url, google, tmp_path):
    # En inspelning där SCB markerat två år som saknade ("..") och ett som noll ("-").
    shutil.copytree(INSPELNINGAR, tmp_path / "rec")
    fil = tmp_path / "rec" / json.loads((INSPELNINGAR / "manifest.json").read_text(encoding="utf-8"))[SCB_BALANS]
    data = json.loads(fil.read_text(encoding="utf-8-sig"))
    for rad in data["data"]:
        if rad["key"][1] == "065" and rad["key"][2] in ("2023", "2024"):
            rad["values"] = [".."]
        if rad["key"][1] == "065" and rad["key"][2] == "2022":
            rad["values"] = ["-"]
    fil.write_text(json.dumps(data), encoding="utf-8")

    kalla = Scb([ScbMatt("BalansKnN", "065", "Likvida medel", "Kassa och bank.")])
    api = TestClient(skapa_app(database_url, google, kallor=[kalla], inspelningar=tmp_path / "rec", anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    api.post("/api/insamlingar")
    serie = {p["period"]: p["varde"] for p in api.get("/api/matt/scb:BalansKnN:065/serie").json()["punkter"]}
    assert serie["2023"] is None
    assert serie["2024"] is None
    assert serie["2022"] == 0


def test_nyckeltal_som_laggs_till_i_katalogen_far_hela_historiken(database_url, google):
    """Ett nyckeltal som läggs till efter en tidigare lyckad kontroll ska inte bara få de senast ändrade åren."""
    from app.recorded import InspeladTransport
    from app.sources.kolada import Kolada

    anrop: list[str] = []

    class Spion(InspeladTransport):
        def handle_request(self, request):
            anrop.append(str(request.url))
            return super().handle_request(request)

    forsta = TestClient(skapa_app(database_url, google, kallor=[Kolada(["N03007"])], anonym_lasning=True))
    forsta.post("/api/auth/test/redaktor")
    assert forsta.post("/api/insamlingar").json()["status"] == "lyckad"

    from app.main import create_app

    app = skapa_app(database_url, google, kallor=[Kolada(["N03007", "N03010"])], anonym_lasning=True)
    andra = TestClient(create_app(database_url=database_url, kallor=[Kolada(["N03007", "N03010"])],
                                  transport=Spion(INSPELNINGAR), inloggning=app.state.inloggning))
    andra.post("/api/auth/test/redaktor")
    andra.post("/api/insamlingar")
    assert anrop and not any("from_date" in u for u in anrop)
    kolada = inspelning("api.kolada.se/v3/data/kpi/N03010/municipality/2280")
    assert len(andra.get("/api/matt/kolada:N03010/serie").json()["punkter"]) == len(kolada["values"])
