"""Partiernas budgetförslag (#48).

Söm 1: förslagen läses in från en mapp med `budget.json` till budgetmodellen, rättas av en redaktör,
publiceras av en utgivare och jämförs mot den antagna budgeten. Fixturerna är sidor ur de verkliga
förslagen för 2027: majoritetens årsplan (antagen), Liberalernas förslag med belopp per nämnd och
Moderaternas förslag, som bara anger förändringar.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient

from app import budgetforslag

FIXTURER = Path(__file__).parent / "fixtures" / "budgetforslag"
REDAKTOR = "test-redaktor@kommunkollen.test"


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    return TestClient(skapa_app(database_url, google, anonym_lasning=True))


def logga_in(api: TestClient, roll: str | None) -> None:
    api.post("/api/auth/logga-ut")
    if roll:
        assert api.post(f"/api/auth/test/{roll}").status_code == 200


def las_in(database_url: str, monkeypatch, capsys, mapp: Path = FIXTURER, redaktor: str = REDAKTOR) -> str:
    monkeypatch.setenv("DATABASE_URL", database_url)
    budgetforslag.main([str(mapp), "--redaktor", redaktor])
    return capsys.readouterr().out


def utkast(api: TestClient) -> dict[str, dict]:
    logga_in(api, "redaktor")
    return {f["nyckel"]: f for f in api.get("/api/budgetforslag?status=utkast").json()}


def publicera_alla(api: TestClient) -> None:
    logga_in(api, "utgivare")
    for f in api.get("/api/budgetforslag?status=utkast").json():
        assert api.post(f"/api/budgetforslag/{f['id']}/granskning").status_code == 200
        assert api.post(f"/api/budgetforslag/{f['id']}/publicering").status_code == 200
    logga_in(api, None)


def test_verkliga_forslag_lases_in_som_utkast(api, database_url, monkeypatch, capsys):
    assert "3 budgetförslag: 3 nya utkast, 0 uppdaterade, 0 oförändrade." in las_in(database_url, monkeypatch, capsys)
    f = utkast(api)
    assert set(f) == {"majoritet", "L", "M"}

    maj = f["majoritet"]
    assert (maj["budgetar"], maj["partier"], maj["antagen"], maj["status"], maj["redaktorer"]) == (
        2027, ["KD", "MP", "S"], True, "utkast", [REDAKTOR])
    assert maj["uppgifter"]["skattesats"] == {"procent": 23.34, "sida": 3}
    assert {"ar": 2027, "mnkr": 50.3, "procent": 2.3, "sida": 3} in maj["uppgifter"]["resultat"]
    assert {"organ": "Socialnämnden", "ar": 2027, "mnkr": 893.1, "sida": 4} in maj["uppgifter"]["ramar"]

    # Ett förslag som bara anger förändringar lagras så, med sitt utgångsläge.
    m = f["M"]["uppgifter"]
    assert (m["skattesats"], m["utgangslage"]) == ({"forandring": -0.1, "sida": 1}, "Planförutsättningar 2027")
    assert {"organ": "Skolnämnden", "ar": 2027, "forandring": 15.0, "sida": 1} in m["ramar"]

    # Läsaren ser inget opublicerat, varken förslag eller original.
    logga_in(api, None)
    assert api.get("/api/budget").json() == []
    assert api.get("/api/budget/2027").json()["forslag"] == []
    assert api.get(f"/api/budgetforslag/{maj['id']}/original").status_code == 404
    assert api.get("/api/budgetforslag").status_code == 401

    # Samma mapp igen ändrar inget.
    assert "0 nya utkast, 0 uppdaterade, 3 oförändrade" in las_in(database_url, monkeypatch, capsys)


def test_inlasning_fran_tar_strom(database_url, monkeypatch, capsys):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(FIXTURER, arcname="budgetforslag")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(buf.getvalue())))
    budgetforslag.main(["-", "--redaktor", REDAKTOR])
    assert "3 nya utkast" in capsys.readouterr().out


def test_redaktor_rattar_och_ingen_godkanner_sitt_eget(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys, redaktor="test-utgivare@kommunkollen.test")
    lid = utkast(api)["L"]["id"]

    # Den som läste in räknas som redaktör och kan inte godkänna förslaget, trots rollen utgivare.
    logga_in(api, "utgivare")
    egen = api.post(f"/api/budgetforslag/{lid}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner ett förslag som hen själv läst in eller ändrat")

    # En redaktör rättar: förslaget blir utkast igen och redaktören kan inte själv godkänna det.
    logga_in(api, "redaktor+utgivare")
    f = api.get(f"/api/budgetforslag/{lid}").json()
    ramar = [r | {"mnkr": 704} if r["organ"] == "Skolnämnden" else r for r in f["uppgifter"]["ramar"]]
    ny = api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {**f["uppgifter"], "ramar": ramar},
                                                     "anmarkning": "Skolnämnden 704 enligt tabellen."})
    assert ny.status_code == 200, ny.text
    ny = ny.json()
    assert (ny["status"], ny["redaktorer"]) == ("utkast", ["test-utgivare@kommunkollen.test", "test-redaktor+utgivare@kommunkollen.test"])
    assert {"organ": "Skolnämnden", "ar": 2027, "mnkr": 704.0, "forandring": 40.0, "sida": 1} in ny["uppgifter"]["ramar"]
    # Det som lästes in finns kvar att jämföra med.
    assert {"organ": "Skolnämnden", "ar": 2027, "mnkr": 703.0, "forandring": 40.0, "sida": 1} in ny["inlast"]["ramar"]
    egen = api.post(f"/api/budgetforslag/{lid}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner ett förslag som hen själv läst in eller ändrat")

    # Ogiltiga uppgifter avvisas.
    fel = api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"ramar": [{"organ": "Skolnämnden", "ar": 2027, "sida": 1}]}})
    assert (fel.status_code, fel.json()["detail"]) == (422, "ram 1: ange mnkr eller forandring")
    assert api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"skattesats": {"procent": 0.2334, "sida": 1}}}).status_code == 422

    # Läsare och utgivare utan redaktörsroll ändrar inte.
    logga_in(api, "utgivare")
    assert api.patch(f"/api/budgetforslag/{lid}", json={"titel": "x"}).status_code == 403
    # Publicering kräver granskning, av en utgivare som inte läst in eller ändrat förslaget.
    logga_in(api, "lasare+utgivare")
    assert api.post(f"/api/budgetforslag/{lid}/publicering").status_code == 409


def test_lasaren_jamfor_forslagen_med_den_antagna_budgeten(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)

    assert api.get("/api/budget").json() == [{"budgetar": 2027, "forslag": 3, "antagen": True}]
    j = api.get("/api/budget/2027").json()
    assert j["ar"] == [2027, 2028, 2029]
    assert j["organ"][:2] == ["Kommunstyrelsen", "Kommungemensam verksamhet"]
    # Den antagna budgeten först, sedan förslagen i alfabetisk ordning.
    assert [f["nyckel"] for f in j["forslag"]] == ["majoritet", "L", "M"]
    maj, l, m = j["forslag"]
    assert j["antagen"] == maj["id"] and maj["differens"] is None

    # Differensen per nämnd i kronor och procent, för år och nämnd där båda anger ett belopp.
    d = l["differens"]
    assert {"organ": "Kommunstyrelsen", "ar": 2027, "mnkr": -41.3, "procent": -21.6} in d["ramar"]
    assert {"organ": "Skolnämnden", "ar": 2027, "mnkr": 38.6, "procent": 5.8} in d["ramar"]
    assert d["resultat"] == [{"ar": 2027, "mnkr": 29.7, "procent": 59.0}]
    assert d["skattesats"] is None  # Liberalerna anger ingen skattesats

    # Ett förslag med bara förändringar får ingen beräknad differens.
    assert m["differens"] == {"skattesats": None, "resultat": [], "ramar": []}

    # Originalet för ett publicerat förslag är öppet, med sidan i länken.
    svar = api.get(maj["original"])
    assert (svar.status_code, svar.headers["content-type"]) == (200, "application/pdf")
    assert 'filename="2027-majoritet.pdf"' in svar.headers["content-disposition"]


def test_ny_inlasning_av_publicerat_forslag_ger_nytt_utkast(api, database_url, monkeypatch, capsys, tmp_path):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)

    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    besk = mapp / "2027" / "budget.json"
    data = json.loads(besk.read_text(encoding="utf-8"))
    data["forslag"]["L.pdf"]["resultat"] = [{"ar": 2027, "mnkr": 81, "sida": 1}]
    besk.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert "0 nya utkast, 0 uppdaterade, 2 oförändrade" not in las_in(database_url, monkeypatch, capsys, mapp)

    # Det publicerade förslaget gäller tills det nya utkastet publicerats.
    logga_in(api, None)
    [l] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "L"]
    assert l["uppgifter"]["resultat"][0]["mnkr"] == 80
    publicera_alla(api)
    [l] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "L"]
    assert l["uppgifter"]["resultat"][0]["mnkr"] == 81
    logga_in(api, "redaktor")
    assert len(api.get("/api/budgetforslag?status=ersatt").json()) == 1


@pytest.mark.parametrize(
    ("fil", "post", "fel"),
    [
        ("S och V.pdf", None, "filnamnet ska vara partiförkortningarna"),
        ("majoritet.pdf", None, "partier ska vara en lista"),
        ("S.pdf", {"resultat": [{"ar": 2040, "mnkr": 1, "sida": 1}]}, "året ska ligga mellan 2026 och 2031"),
        ("S.pdf", {"ramar": [{"organ": "Skolnämnden", "ar": 2027, "mnkr": 1, "sida": 0}]}, "sidan ska vara ett heltal"),
        ("S.pdf", {"skattesats": {"procent": 23.34, "sida": 1}, "okant": 1}, "Okända fält: okant"),
        ("S.pdf", {"skattesats": {"procent": 23.34}}, "sidan ska vara ett heltal"),
        ("S.docx", {"skattesats": {"procent": 23.34, "sida": 1}}, "Word-dokument har inga fasta sidor"),
    ],
)
def test_ogiltig_mapp_avbryter_inlasningen(tmp_path, fil, post, fel):
    ar = tmp_path / "2027"
    ar.mkdir()
    (ar / fil).write_bytes(b"%PDF-1.4")
    if post is not None:
        (ar / "budget.json").write_text(json.dumps({"forslag": {fil: post}}), encoding="utf-8")
    with pytest.raises(budgetforslag.Ogiltig, match=fel):
        budgetforslag.las_mapp(tmp_path)


def test_forslag_utan_beskrivning_blir_tomt_utkast(tmp_path):
    (tmp_path / "2027").mkdir()
    (tmp_path / "2027" / "L+M-tillagg.docx").write_bytes(b"PK")
    [f] = budgetforslag.las_mapp(tmp_path)
    assert (f.nyckel, f.partier, f.typ, f.anmarkning) == ("L+M-tillagg", ["L", "M"], "tillagg", "Uppgifter saknas i budget.json.")


def test_word_dokument_har_uppgifter_utan_sida(tmp_path):
    # Ett Word-dokument har inga fasta sidor. Siffrorna står utan sida och visas utan sidlänk.
    (tmp_path / "2022").mkdir()
    (tmp_path / "2022" / "C.docx").write_bytes(b"PK")
    post = {"skattesats": {"procent": 23.34}, "ramar": [{"organ": "Skolnämnden", "ar": 2022, "mnkr": 600.5}]}
    (tmp_path / "2022" / "budget.json").write_text(json.dumps({"forslag": {"C.docx": post}}), encoding="utf-8")
    [f] = budgetforslag.las_mapp(tmp_path)
    assert f.uppgifter["skattesats"] == {"procent": 23.34}
    assert f.uppgifter["ramar"] == [{"organ": "Skolnämnden", "ar": 2022, "mnkr": 600.5}]
