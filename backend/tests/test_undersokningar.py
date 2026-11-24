"""Undersökningar (#67): medborgarundersökningen, Insikt och anmälda brott från Kolada.

Söm 1: insamlingen hämtar nyckeltalen från inspelade svar från Kolada (2026-11-24), för Härnösand och riket,
i några få samlade anrop. Sidan "Undersökningar" läses från API:t.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import undersokningar
from app.main import standardkallor
from app.recorded import InspeladTransport
from app.sources.kolada import RIKET, Kolada
from conftest import INSPELNINGAR, skapa_app


@pytest.fixture
def api(database_url, google) -> TestClient:
    # Bara Kolada-källan med undersökningarna, så att testerna går fort. Standardkällorna testas nedan.
    kolada = Kolada(nyckeltal=[], samlade=undersokningar.KOLADA, anrop_per_sekund=None)
    api = TestClient(skapa_app(database_url, google, kallor=[kolada], anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/insamlingar").json()["status"] == "lyckad"
    api.post("/api/auth/logga-ut")
    return api


def avsnitt(api: TestClient) -> dict[str, dict]:
    return {a["id"]: a for a in api.get("/api/undersokningar").json()["avsnitt"]}


def alla_nyckeltal(a: dict) -> dict[str, dict]:
    return {n["id"]: n for g in a["grupper"] for n in g["nyckeltal"]}


def punkter(serie: dict) -> dict[str, float | None]:
    return {p["period"]: p["varde"] for p in serie["punkter"]}


def test_katalogen_har_alla_nyckeltal_ur_issuet():
    assert len(undersokningar.MEDBORGARUNDERSOKNINGEN) == 114
    assert undersokningar.MEDBORGARUNDERSOKNINGEN[0] == "N00528"
    assert set(undersokningar.INSIKT) == {"U07453", "U07451", "U07446", "U07447", "U07448", "U07449", "U07450"}
    assert len(undersokningar.BROTT) == 9
    urval = [m for g in undersokningar.AVSNITT[0].grupper for m in g.matt]
    # Issuet säger 27, men listar 26 nyckeltal. Listan gäller.
    assert len(urval) == 26 and len(set(urval)) == 26


def test_kolada_hamtar_alla_samlat_for_harnosand_och_riket():
    standard = next(k for k in standardkallor() if k.id == "kolada")
    assert standard.samlade == undersokningar.KOLADA
    kolada = Kolada(nyckeltal=[], samlade=undersokningar.KOLADA, anrop_per_sekund=None)
    with httpx.Client(transport=InspeladTransport(INSPELNINGAR)) as client:
        h = kolada.hamta(client, None)
    assert h.fel == []
    assert {m.id for m in h.matt} == {f"kolada:{i}" for i in undersokningar.KOLADA}
    omraden = {(u.matt_id, u.omrade) for u in h.uppgifter}
    assert ("kolada:N00529", "2280") in omraden and ("kolada:N00529", RIKET) in omraden
    assert ("kolada:N07540", "2280") in omraden and ("kolada:N07540", RIKET) in omraden


def test_medborgarundersokningen_med_svarsfrekvensen_overst(api):
    mu = avsnitt(api)["medborgarundersokningen"]
    assert mu["titel"] == "Medborgarundersökningen"
    assert mu["kalla"] == "SCB/Kolada"
    assert mu["grupper"][0]["titel"] == "Svar"
    assert [n["id"] for n in mu["grupper"][0]["nyckeltal"]] == ["kolada:N00529", "kolada:N00528"]
    assert sum(len(g["nyckeltal"]) for g in mu["grupper"]) == 26

    alla = alla_nyckeltal(mu)
    svarsfrekvens = alla["kolada:N00529"]
    assert svarsfrekvens["serie"]["matt"]["enhet"] == "%"
    assert svarsfrekvens["serie"]["matt"]["beskrivning"]
    assert punkter(svarsfrekvens["serie"]) == {
        "2021": 37.37, "2022": 36.16, "2023": 37.94, "2024": 35.15, "2025": 39.0,
    }
    assert punkter(alla["kolada:N00530"]["serie"])["2025"] == 90.1
    assert alla["kolada:N00528"]["serie"]["matt"]["enhet"] == "antal"


def test_riket_hamtas_och_visas_bredvid_harnosand(api):
    svarsfrekvens = alla_nyckeltal(avsnitt(api)["medborgarundersokningen"])["kolada:N00529"]
    assert svarsfrekvens["serie"]["omrade"] == "2280"
    assert svarsfrekvens["riket"]["omrade"] == RIKET
    assert punkter(svarsfrekvens["riket"])["2021"] == 37.6

    brott = alla_nyckeltal(avsnitt(api)["anmalda-brott"])["kolada:N07540"]
    assert brott["riket"]["omrade"] == RIKET and punkter(brott["riket"])


def test_insikt_visar_gammal_och_ny_definition_som_separata_serier(api):
    insikt = avsnitt(api)["insikt"]
    assert insikt["kalla"] == "SKR/Kolada"
    total = insikt["grupper"][0]
    assert [n["id"] for n in total["nyckeltal"]] == ["kolada:U07451", "kolada:U07453"]
    assert total["metodbyte"]["ar"] == 2024
    assert [s["id"] for s in total["metodbyte"]["serier"]] == ["kolada:U07451", "kolada:U07453"]

    ny = alla_nyckeltal(insikt)["kolada:U07453"]
    assert ny["serie"]["matt"]["enhet"] == "index"
    assert alla_nyckeltal(insikt)["kolada:U07451"]["serie"]["matt"]["enhet"] == "index"
    assert alla_nyckeltal(insikt)["kolada:U07446"]["serie"]["matt"]["enhet"] == "index"
    varden = punkter(ny["serie"])
    assert round(varden["2024"], 2) == 82.94 and round(varden["2025"], 2) == 86.11
    # Kolada anger riket för den nya definitionen med enbart saknade värden. Det är inget genomsnitt.
    assert ny["riket"] is None
    # Den gamla definitionen slås inte ihop med den nya: den har sina egna år.
    gammal = punkter(alla_nyckeltal(insikt)["kolada:U07451"]["serie"])
    assert "2025" not in gammal and "2012" in gammal
    assert {n["id"] for n in insikt["grupper"][1]["nyckeltal"]} == {f"kolada:U0744{i}" for i in (6, 7, 8, 9)} | {
        "kolada:U07450"
    }


def test_anmalda_brott_med_texten_om_vad_de_mater(api):
    brott = avsnitt(api)["anmalda-brott"]
    assert brott["kalla"] == "Brå/Kolada"
    assert "inte hur många brott som faktiskt begås" in brott["om_matningen"]
    assert list(alla_nyckeltal(brott)) == [f"kolada:{i}" for i in undersokningar.BROTT]
    totalt = alla_nyckeltal(brott)["kolada:N07540"]["serie"]
    assert totalt["matt"]["enhet"] == "antal/100 000 inv"
    assert round(punkter(totalt)["2025"], 2) == 12029.55


def test_saknade_varden_ar_null_aldrig_noll(api):
    brandskydd = alla_nyckeltal(avsnitt(api)["insikt"])["kolada:U07446"]["serie"]
    assert punkter(brandskydd)["2025"] is None


def test_alla_fragor_i_medborgarundersokningen_nas_i_analysverktyget(api):
    svar = api.get("/api/undersokningar").json()
    alla = svar["medborgarundersokningen"]
    assert len(alla) == 114
    assert all(a["titel"].startswith("Medborgarundersökningen -") for a in alla)
    utanfor_urvalet = "kolada:N00544"  # Viktigt i boendemiljön – tyst och lugnt
    n = api.get(f"/api/undersokningar/nyckeltal/{utanfor_urvalet}").json()
    assert n["serie"]["punkter"] and n["riket"]["punkter"]
    assert api.get("/api/undersokningar/nyckeltal/kolada:N03002").status_code == 404
