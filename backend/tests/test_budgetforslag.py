"""Partiernas budgetförslag (#48) mot gemensamma planförutsättningar (#58).

Söm 1: planförutsättningarna och förslagen läses in från en mapp med `planforutsattningar.xlsx` och
`budget.json`, rättas av en redaktör, publiceras av en utgivare och jämförs mot planförutsättningarna
och den antagna budgeten. Fixturerna är sidor ur de verkliga förslagen för 2027: majoritetens årsplan
(antagen, i formatet med planår), Liberalernas förslag med belopp per nämnd och resultat i mnkr,
Moderaternas förslag, som bara anger förändringar, och Sverigedemokraternas.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

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


def publicera_alla(api: TestClient, planforutsattningar: bool = True) -> None:
    logga_in(api, "utgivare")
    vagar = ["budgetforslag", "planforutsattningar"] if planforutsattningar else ["budgetforslag"]
    for vag in vagar:
        for f in api.get(f"/api/{vag}?status=utkast").json():
            assert api.post(f"/api/{vag}/{f['id']}/granskning").status_code == 200
            assert api.post(f"/api/{vag}/{f['id']}/publicering").status_code == 200
    logga_in(api, None)


def test_verkliga_forslag_lases_in_som_utkast(api, database_url, monkeypatch, capsys):
    ut = las_in(database_url, monkeypatch, capsys)
    assert "1 planförutsättningar: 1 nya utkast, 0 uppdaterade, 0 oförändrade." in ut
    assert "4 budgetförslag: 4 nya utkast, 0 uppdaterade, 0 oförändrade." in ut
    f = utkast(api)
    assert set(f) == {"majoritet", "L", "M", "SD"}

    # Bara budgetåret: planåren i årsplanen läses inte.
    maj = f["majoritet"]
    assert (maj["budgetar"], maj["partier"], maj["antagen"], maj["status"], maj["redaktorer"]) == (
        2027, ["KD", "MP", "S"], True, "utkast", [REDAKTOR])
    assert maj["uppgifter"]["skattesats"] == {"ore": 0, "sida": 3}
    assert maj["uppgifter"]["resultat"] == {"procent": 2.3, "sida": 3}
    assert {"organ": "Socialnämnden", "mnkr": 893.1, "sida": 4} in maj["uppgifter"]["ramar"]
    assert len(maj["uppgifter"]["ramar"]) == 6

    # Ett förslag som bara anger förändringar lagras med ramarna i mnkr, skatten i öre.
    m = f["M"]["uppgifter"]
    assert m["skattesats"] == {"ore": -10, "sida": 1}
    assert {"organ": "Skolnämnden", "mnkr": 678.0, "sida": 1} in m["ramar"]
    # Ett resultat i mnkr lagras i procent av planförutsättningarnas skatter och bidrag.
    assert f["L"]["uppgifter"]["resultat"] == {"procent": 3.608, "sida": 1}
    # Redaktionen ser beräkningen mot planförutsättningarna redan som utkast.
    assert f["L"]["berakning"]["differens"] == 20.0

    # Läsaren ser inget opublicerat, varken förslag, planförutsättningar eller original.
    logga_in(api, None)
    assert api.get("/api/budget").json() == []
    assert api.get("/api/budget/2027").json()["forslag"] == []
    assert api.get("/api/budget/2027").json()["planforutsattningar"] is None
    assert api.get(f"/api/budgetforslag/{maj['id']}/original").status_code == 404
    assert api.get("/api/budgetforslag").status_code == 401
    assert api.get("/api/planforutsattningar").status_code == 401

    # Samma mapp igen ändrar inget.
    ut = las_in(database_url, monkeypatch, capsys)
    assert "1 planförutsättningar: 0 nya utkast, 0 uppdaterade, 1 oförändrade." in ut
    assert "0 nya utkast, 0 uppdaterade, 4 oförändrade" in ut


def test_inlasning_fran_tar_strom(database_url, monkeypatch, capsys):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(FIXTURER, arcname="budgetforslag")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(buf.getvalue())))
    budgetforslag.main(["-", "--redaktor", REDAKTOR])
    ut = capsys.readouterr().out
    assert "1 planförutsättningar: 1 nya utkast" in ut and "4 nya utkast" in ut


def test_planforutsattningar_granskas_och_publiceras(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys, redaktor="test-utgivare@kommunkollen.test")
    logga_in(api, "redaktor")
    [p] = api.get("/api/planforutsattningar?status=utkast").json()
    forslag = utkast(api)
    assert (p["budgetar"], p["status"], p["skattesats"]["procent"]) == (2027, "utkast", 23.34)
    # Alla tabeller, med källa och länk till sidan i förslaget.
    assert set(p["tabeller"]) == {"resultatbudget", "namnder", "investeringar", "balansbudget", "kassaflode"}
    [ks] = [x for x in p["tabeller"]["namnder"] if x["post"] == "Kommunstyrelsen"]
    assert ks | {"kallor": None} == {"post": "Kommunstyrelsen", "mnkr": 187.0, "kalla": "L s. 8", "kallor": None}
    assert ks["kallor"] == [{"text": "L s. 8", "forslag": forslag["L"]["id"], "sida": 8}]
    # Kontrollsummorna.
    assert {"tabell": "namnder", "post": "Totalt", "summa": 2144.0, "angivet": 2145.0, "differens": 1.0} in p["kontroller"]

    # Den som läste in kan inte godkänna, trots rollen utgivare.
    logga_in(api, "utgivare")
    egen = api.post(f"/api/planforutsattningar/{p['id']}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner planförutsättningar som hen själv läst in")
    logga_in(api, "lasare+utgivare")
    assert api.post(f"/api/planforutsattningar/{p['id']}/publicering").status_code == 409
    assert api.post(f"/api/planforutsattningar/{p['id']}/granskning").json()["status"] == "granskad"
    assert api.post(f"/api/planforutsattningar/{p['id']}/publicering").json()["status"] == "publicerad"
    # Redaktören utan utgivarroll godkänner inte.
    logga_in(api, "redaktor")
    assert api.post(f"/api/planforutsattningar/{p['id']}/granskning").status_code == 403


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
    assert {"organ": "Skolnämnden", "mnkr": 704.0, "sida": 1} in ny["uppgifter"]["ramar"]
    assert {"organ": "Skolnämnden", "mnkr": 704.0, "plan": 663.0, "forandring": 41.0} in ny["berakning"]["ramar"]
    # Det som lästes in finns kvar att jämföra med.
    assert {"organ": "Skolnämnden", "mnkr": 703.0, "sida": 1} in ny["inlast"]["ramar"]
    egen = api.post(f"/api/budgetforslag/{lid}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner ett förslag som hen själv läst in eller ändrat")

    # Redaktören kan ange en förändring i stället för mnkr; den lagras som mnkr.
    ny = api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {
        "skattesats": {"ore": 5, "sida": 1}, "resultat": {"procent": 3.0, "sida": 1},
        "ramar": [{"organ": "Skolnämnden", "forandring": 10, "sida": 1}]}}).json()
    assert ny["uppgifter"] == {"skattesats": {"ore": 5, "sida": 1}, "resultat": {"procent": 3.0, "sida": 1},
                               "ramar": [{"organ": "Skolnämnden", "mnkr": 673.0, "sida": 1}]}

    # Ogiltiga uppgifter avvisas.
    fel = api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"ramar": [{"organ": "Skolnämnden", "sida": 1}]}})
    assert (fel.status_code, fel.json()["detail"]) == (422, "ram 1: ange mnkr eller forandring")
    fel = api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"ramar": [{"organ": "Valnämnden", "forandring": 1, "sida": 1}]}})
    assert (fel.status_code, fel.json()["detail"]) == (422, "ram 1: Valnämnden finns inte i planförutsättningarna för 2027, ange mnkr")
    assert api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"skattesats": {"procent": 0.2334, "sida": 1}}}).status_code == 422
    assert api.patch(f"/api/budgetforslag/{lid}", json={"uppgifter": {"skattesats": {"ore": 2.5, "sida": 1}}}).status_code == 422

    # Läsare och utgivare utan redaktörsroll ändrar inte.
    logga_in(api, "utgivare")
    assert api.patch(f"/api/budgetforslag/{lid}", json={"titel": "x"}).status_code == 403
    # Publicering kräver granskning, av en utgivare som inte läst in eller ändrat förslaget.
    logga_in(api, "lasare+utgivare")
    assert api.post(f"/api/budgetforslag/{lid}/publicering").status_code == 409


def test_lasaren_ser_forandringarna_forst_nar_planforutsattningarna_ar_publicerade(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api, planforutsattningar=False)

    # Förslagen är publicerade men inte planförutsättningarna: bara förslagens egna siffror.
    j = api.get("/api/budget/2027").json()
    assert j["planforutsattningar"] is None
    [l] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert l["berakning"]["planforutsattningar"] is False
    assert (l["berakning"]["beraknat"], l["berakning"]["differens"], l["berakning"]["ramar"][0]["forandring"]) == (None, None, None)

    publicera_alla(api)
    assert api.get("/api/budget").json() == [{"budgetar": 2027, "forslag": 4, "antagen": True}]
    j = api.get("/api/budget/2027").json()
    # Nämnderna i planförutsättningarnas ordning.
    assert j["organ"][:2] == ["Kommunstyrelsen", "Kommungemensam verksamhet"]
    # Den antagna budgeten först, sedan förslagen i alfabetisk ordning.
    assert [f["nyckel"] for f in j["forslag"]] == ["majoritet", "L", "M", "SD"]
    maj, l, m, sd = j["forslag"]
    assert j["antagen"] == maj["id"] and maj["differens"] is None

    # Planförutsättningarna visas en gång för budgetåret, med investerings-, balans- och kassaflödesbudget.
    p = j["planforutsattningar"]
    assert [x["mnkr"] for x in p["tabeller"]["investeringar"] if x["post"] == "Totalt"] == [147.0]
    assert {x["post"] for x in p["tabeller"]["kassaflode"]} >= {"Totalt kassaflöde", "Likvida medel vid årets slut"}
    assert [x["kallor"] for x in p["tabeller"]["balansbudget"]][0] == [{"text": "L s. 9", "forslag": l["id"], "sida": 9}]

    # L budgeterar 80 mnkr men ramarna sparar bara 10 mnkr: cirka 20 mnkr saknar finansiering.
    b = l["berakning"]
    assert {"organ": "Kommunstyrelsen", "mnkr": 150.0, "plan": 187.0, "forandring": -37.0} in b["ramar"]
    assert (b["forandring"], b["plan_resultat"], b["beraknat"], b["resultat"]["mnkr"], b["differens"]) == (-10.0, 50.0, 60.0, 80.0, 20.0)
    # SD utelämnar kostnaderna utanför nämnderna: cirka 22 mnkr.
    assert sd["berakning"]["beraknat"] == 21.2
    assert sd["berakning"]["differens"] == pytest.approx(22, abs=1.5)
    # M sänker skatten med 10 öre och går ihop.
    assert m["berakning"]["skattesats"] == {"procent": 23.24, "ore": -10, "plan": 23.34}
    assert m["berakning"]["skattejustering"] == -6.4
    assert abs(m["berakning"]["differens"]) < 1

    # Skillnaden mot den antagna budgeten per nämnd i kronor och procent.
    d = l["differens"]
    assert {"organ": "Kommunstyrelsen", "mnkr": -41.3, "procent": -21.6} in d["ramar"]
    assert {"organ": "Skolnämnden", "mnkr": 38.6, "procent": 5.8} in d["ramar"]
    assert d["skattesats"] == 0
    assert m["differens"]["skattesats"] == -10

    # Originalet för ett publicerat förslag är öppet.
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
    data["forslag"]["L.pdf"]["resultat"] = {"procent": 4.0, "sida": 1}
    besk.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert "1 uppdaterade" not in las_in(database_url, monkeypatch, capsys, mapp)

    # Det publicerade förslaget gäller tills det nya utkastet publicerats.
    logga_in(api, None)
    [l] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "L"]
    assert l["uppgifter"]["resultat"]["procent"] == 3.608
    publicera_alla(api)
    [l] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "L"]
    assert l["uppgifter"]["resultat"]["procent"] == 4.0
    logga_in(api, "redaktor")
    assert len(api.get("/api/budgetforslag?status=ersatt").json()) == 1


def test_befintliga_forslag_fors_over_till_budgetaret(api, database_url, monkeypatch, capsys, tmp_path):
    """Förslag som lästes in före #58, med planår, resultat i mnkr och skattesats i procent."""
    from app import db

    db.migrate(database_url)
    gammal = {"skattesats": {"procent": 23.24, "sida": 1},
              "resultat": [{"ar": 2027, "mnkr": 55.3, "sida": 2}, {"ar": 2028, "mnkr": 60, "sida": 2}],
              "ramar": [{"organ": "Kommunstyrelsen", "ar": 2027, "forandring": -37, "sida": 1},
                        {"organ": "Kommunstyrelsen", "ar": 2028, "mnkr": 190, "sida": 1},
                        {"organ": "Skolnämnden", "ar": 2027, "mnkr": 678, "forandring": 15, "sida": 1}],
              "utgangslage": "Planförutsättningar 2027"}
    nu = datetime(2026, 11, 1, tzinfo=timezone.utc)
    with psycopg.connect(database_url) as conn:
        for nyckel, status in (("M", "publicerad"), ("C", "utkast")):
            conn.execute(
                "INSERT INTO budgetforslag (budgetar, nyckel, partier, titel, typ, filnamn, sha256, original, inlast, "
                "uppgifter, status, redaktorer, publicerad, publicerad_av) VALUES (2027, %s, %s, 'x', 'budget', %s, 'x', "
                "'\\x00', %s, %s, %s, %s, %s, %s)",
                (nyckel, [nyckel], f"{nyckel}.pdf", Jsonb({"uppgifter": gammal}), Jsonb(gammal), status,
                 ["tidigare@kommunkollen.test"], nu if status == "publicerad" else None,
                 "u@kommunkollen.test" if status == "publicerad" else None),
            )
    mapp = tmp_path / "budgetforslag"
    mapp.mkdir()
    shutil.copy(FIXTURER / "planforutsattningar.xlsx", mapp)
    ut = las_in(database_url, monkeypatch, capsys, mapp)
    assert "Förda till budgetåret: 1 utkast, 1 nya utkast för publicerade förslag, 0 ersatta." in ut

    logga_in(api, "redaktor")
    alla = api.get("/api/budgetforslag").json()
    # Det publicerade förslaget ändras inte utan får ett nytt utkast.
    [publ] = [f for f in alla if f["nyckel"] == "M" and f["status"] == "publicerad"]
    assert publ["uppgifter"] == gammal and publ["berakning"] is None
    ny = {"skattesats": {"ore": -10, "sida": 1}, "resultat": {"procent": 2.502, "sida": 2},
          "ramar": [{"organ": "Kommunstyrelsen", "mnkr": 150.0, "sida": 1}, {"organ": "Skolnämnden", "mnkr": 678.0, "sida": 1}]}
    for nyckel in ("M", "C"):
        [f] = [f for f in alla if f["nyckel"] == nyckel and f["status"] == "utkast"]
        # Planåren borta, resultatet i procent, skattesatsen som förändring i öre.
        assert f["uppgifter"] == ny and f["inlast"] == ny
        assert f["redaktorer"][-1] == REDAKTOR
    # Andra körningen ändrar inget.
    assert "Förda till budgetåret" not in las_in(database_url, monkeypatch, capsys, mapp)


def test_ar_utan_planforutsattningar(api, database_url, monkeypatch, capsys, tmp_path):
    # 2022 saknar planförutsättningar: förslagens faktiska ramar, utan förändring och beräknat resultat.
    (tmp_path / "2022").mkdir()
    (tmp_path / "2022" / "C.docx").write_bytes(b"PK")
    post = {"skattesats": {"procent": 23.34}, "resultat": [{"ar": 2022, "mnkr": 43.3, "procent": 2.3}],
            "ramar": [{"organ": "Skolnämnden", "ar": 2022, "mnkr": 620.371}]}
    (tmp_path / "2022" / "budget.json").write_text(json.dumps({"forslag": {"C.docx": post}}), encoding="utf-8")
    las_in(database_url, monkeypatch, capsys, tmp_path)
    publicera_alla(api)
    j = api.get("/api/budget/2022").json()
    assert j["planforutsattningar"] is None
    [c] = j["forslag"]
    assert c["uppgifter"] == {"skattesats": {"procent": 23.34}, "resultat": {"procent": 2.3},
                              "ramar": [{"organ": "Skolnämnden", "mnkr": 620.371}]}
    b = c["berakning"]
    assert (b["planforutsattningar"], b["ramar"][0]["forandring"], b["beraknat"], b["skattesats"]["procent"]) == (
        False, None, None, 23.34)


@pytest.mark.parametrize(
    ("fil", "post", "fel"),
    [
        ("S och V.pdf", None, "filnamnet ska vara partiförkortningarna"),
        ("majoritet.pdf", None, "partier ska vara en lista"),
        ("S.pdf", {"resultat": [{"ar": 2040, "mnkr": 1, "sida": 1}]}, "året ska ligga mellan 2026 och 2031"),
        ("S.pdf", {"ramar": [{"organ": "Skolnämnden", "mnkr": 1, "sida": 0}]}, "sidan ska vara ett heltal"),
        ("S.pdf", {"skattesats": {"ore": 0, "sida": 1}, "okant": 1}, "Okända fält: okant"),
        ("S.pdf", {"skattesats": {"ore": -10}}, "sidan ska vara ett heltal"),
        ("S.docx", {"skattesats": {"ore": 0, "sida": 1}}, "Word-dokument har inga fasta sidor"),
        ("S.pdf", {"resultat": {"mnkr": 50, "sida": 1}}, "ange procent, mnkr räknas bara om när planförutsättningarna"),
        ("S.pdf", {"ramar": [{"organ": "Skolnämnden", "mnkr": 1, "sida": 1}, {"organ": "Skolnämnden", "mnkr": 2, "sida": 1}]},
         "Samma nämnd står flera gånger"),
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


def test_fel_i_planforutsattningarna_avbryter_hela_inlasningen(database_url, monkeypatch, capsys, tmp_path):
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    (mapp / "planforutsattningar.xlsx").write_bytes(b"trasig")
    monkeypatch.setenv("DATABASE_URL", database_url)
    with pytest.raises(SystemExit, match="Inläsningen avbröts: planforutsattningar.xlsx kan inte läsas"):
        budgetforslag.main([str(mapp), "--redaktor", REDAKTOR])
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM budgetforslag").fetchone()[0] == 0


def test_forslag_utan_beskrivning_blir_tomt_utkast(tmp_path):
    (tmp_path / "2027").mkdir()
    (tmp_path / "2027" / "L+M-tillagg.docx").write_bytes(b"PK")
    [f] = budgetforslag.las_mapp(tmp_path)
    assert (f.nyckel, f.partier, f.typ, f.anmarkning) == ("L+M-tillagg", ["L", "M"], "tillagg", "Uppgifter saknas i budget.json.")
    assert f.uppgifter == {"skattesats": {"ore": 0}, "resultat": None, "ramar": []}
