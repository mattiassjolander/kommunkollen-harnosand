"""Ändra publicerade planförutsättningar och budgetförslag i efterhand (#76, del 2).

En redaktör eller utgivare skapar en ny version från en publicerad eller återkallad version, med en motivering.
Den rättas i gränssnittet och publiceras av en utgivare som inte ändrat den. Läsaren ser den märkt "Ändrad
efter publicering" och kan öppna den förra versionen.

Söm 2: ett budgetförslag återkallas, rättas, granskas och publiceras igen, och läsaren ser markeringen och
den förra versionen.
"""

from __future__ import annotations

import json
import shutil

import openpyxl
from test_budgetforslag import FIXTURER, api, las_in, logga_in, publicera_alla  # noqa: F401 – fixturen api

from app import planforutsattningar as pf

ANDRING = "Resultatet är fel avläst, det står 4,0 % på sidan 1. Påpekat av L 2026-11-21."


def publicerat(api, vag: str, nyckel: str | None = None) -> dict:
    logga_in(api, "redaktor")
    rader = api.get(f"/api/{vag}?status=publicerad").json()
    [r] = [r for r in rader if nyckel is None or r["nyckel"] == nyckel]
    return r


def granska_och_publicera(api, vag: str, id_: int, roll: str = "utgivare") -> dict:
    logga_in(api, roll)
    assert api.post(f"/api/{vag}/{id_}/granskning").status_code == 200
    svar = api.post(f"/api/{vag}/{id_}/publicering")
    assert svar.status_code == 200, svar.text
    logga_in(api, None)
    return svar.json()


def test_sam_2_aterkallat_forslag_rattas_och_publiceras_igen(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    l = publicerat(api, "budgetforslag", "L")
    logga_in(api, "utgivare")
    assert api.post(f"/api/budgetforslag/{l['id']}/aterkallelse", json={"motivering": "Fel resultat."}).status_code == 200

    # En ny version kräver motivering, och det finns bara ett utkast åt gången.
    logga_in(api, "redaktor+utgivare")
    assert api.post(f"/api/budgetforslag/{l['id']}/versioner", json={"motivering": ""}).status_code == 422
    svar = api.post(f"/api/budgetforslag/{l['id']}/versioner", json={"motivering": ANDRING})
    assert svar.status_code == 201
    ny = svar.json()
    assert api.post(f"/api/budgetforslag/{l['id']}/versioner", json={"motivering": ANDRING}).status_code == 409
    # Utkastet har samma uppgifter och original som den återkallade versionen.
    assert (ny["status"], ny["uppgifter"], ny["filnamn"]) == ("utkast", l["uppgifter"], l["filnamn"])
    assert ny["andring"] == {"motivering": ANDRING, "tidigare": l["id"], "publicerad": None}
    assert ny["redaktorer"] == ["test-redaktor+utgivare@kommunkollen.test"]

    # Det rättas i gränssnittet. Den som skapade och ändrade versionen godkänner den inte, trots rollen utgivare.
    u = {**ny["uppgifter"], "resultat": {"procent": 4.0, "sida": 1}}
    assert api.patch(f"/api/budgetforslag/{ny['id']}", json={"uppgifter": u}).status_code == 200
    egen = api.post(f"/api/budgetforslag/{ny['id']}/granskning")
    assert egen.status_code == 403
    # Ett återkallat förslag syns inte medan det nya väntar.
    logga_in(api, None)
    assert "L" not in [f["nyckel"] for f in api.get("/api/budget/2027").json()["forslag"]]

    granska_och_publicera(api, "budgetforslag", ny["id"])
    j = api.get("/api/budget/2027").json()
    assert j["aterkallat"]["forslag"] == []
    [l2] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert l2["uppgifter"]["resultat"]["procent"] == 4.0
    assert l2["andring"]["motivering"] == ANDRING and l2["andring"]["tidigare"] == l["id"]
    assert l2["andring"]["publicerad"] == l2["publicerad"]

    # Läsaren öppnar den förra versionen, med originalet. Den återkallade versionen behåller sin status.
    tidigare = api.get(f"/api/budget/tidigare/forslag/{l['id']}").json()
    assert (tidigare["status"], tidigare["uppgifter"]["resultat"]["procent"]) == ("aterkallad", 3.608)
    assert "aterkallelse" not in tidigare and "redaktorer" not in tidigare
    assert api.get(tidigare["original"]).status_code == 200
    # Den gällande versionen och ett utkast är inga förra versioner.
    assert api.get(f"/api/budget/tidigare/forslag/{l2['id']}").status_code == 404
    # En ny version utgår från den senaste versionen, inte från den återkallade.
    logga_in(api, "redaktor")
    sen = api.post(f"/api/budgetforslag/{l['id']}/versioner", json={"motivering": ANDRING})
    assert (sen.status_code, sen.json()["detail"]) == (409, "Det finns en senare version av förslaget. Skapa den nya versionen från den")


def test_publicerat_forslag_syns_tills_den_nya_versionen_publiceras(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    m = publicerat(api, "budgetforslag", "M")
    ny = api.post(f"/api/budgetforslag/{m['id']}/versioner", json={"motivering": ANDRING}).json()
    assert api.patch(f"/api/budgetforslag/{ny['id']}", json={"anmarkning": "Rättad."}).status_code == 200
    # Utkastet är ingen förra version, och den publicerade gäller.
    logga_in(api, None)
    assert api.get(f"/api/budget/tidigare/forslag/{ny['id']}").status_code == 404
    [m1] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "M"]
    assert (m1["id"], m1["andring"]) == (m["id"], None)

    granska_och_publicera(api, "budgetforslag", ny["id"])
    [m2] = [f for f in api.get("/api/budget/2027").json()["forslag"] if f["nyckel"] == "M"]
    assert (m2["id"], m2["anmarkning"], m2["andring"]["tidigare"]) == (ny["id"], "Rättad.", m["id"])
    assert api.get(f"/api/budget/tidigare/forslag/{m['id']}").json()["status"] == "ersatt"
    # Ett utkast eller granskat förslag får ingen ny version; det rättas direkt.
    logga_in(api, "redaktor")
    sd = api.get("/api/budgetforslag?status=publicerad").json()
    utkast = api.post(f"/api/budgetforslag/{[f for f in sd if f['nyckel'] == 'SD'][0]['id']}/versioner",
                      json={"motivering": ANDRING}).json()
    assert api.post(f"/api/budgetforslag/{utkast['id']}/versioner", json={"motivering": ANDRING}).status_code == 409
    # En läsare skapar inga versioner.
    logga_in(api, "lasare")
    assert api.post(f"/api/budgetforslag/{m2['id']}/versioner", json={"motivering": ANDRING}).status_code == 403


def test_planforutsattningar_andras_i_granssnittet(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    p = publicerat(api, "planforutsattningar")
    logga_in(api, "utgivare")
    ny = api.post(f"/api/planforutsattningar/{p['id']}/versioner", json={"motivering": ANDRING}).json()
    assert (ny["status"], ny["andring"]["tidigare"]) == ("utkast", p["id"])

    # Rättas av en redaktör med samma regler som filen.
    logga_in(api, "redaktor")
    u = {"skattesats": {"procent": ny["skattesats"]["procent"], "kalla": ny["skattesats"]["kalla"]},
         "tabeller": {t: [{"post": x["post"], "mnkr": x["mnkr"], "kalla": x["kalla"]} for x in poster]
                      for t, poster in ny["tabeller"].items()}}
    [ks] = [x for x in u["tabeller"]["namnder"] if x["post"] == "Kommunstyrelsen"]
    ks["mnkr"] = 188
    fel = json.loads(json.dumps(u))
    fel["tabeller"]["resultatbudget"] = [x for x in fel["tabeller"]["resultatbudget"] if x["post"] != "Årets resultat"]
    svar = api.patch(f"/api/planforutsattningar/{ny['id']}", json={"uppgifter": fel})
    assert (svar.status_code, svar.json()["detail"]) == (422, "raden 'Årets resultat' i Resultatbudget saknas")
    fel = json.loads(json.dumps(u)) | {"skattesats": {"procent": 0.2334, "kalla": ""}}
    assert api.patch(f"/api/planforutsattningar/{ny['id']}", json={"uppgifter": fel}).status_code == 422
    fel = json.loads(json.dumps(u))
    fel["tabeller"]["namnder"][0]["mnkr"] = "mycket"
    assert api.patch(f"/api/planforutsattningar/{ny['id']}", json={"uppgifter": fel}).status_code == 422
    andrad = api.patch(f"/api/planforutsattningar/{ny['id']}", json={"uppgifter": u}).json()
    assert {"tabell": "namnder", "post": "Totalt", "summa": 2145.0, "angivet": 2145.0, "differens": 0.0} in andrad["kontroller"]
    # Ett publicerat ändras inte direkt.
    assert api.patch(f"/api/planforutsattningar/{p['id']}", json={"uppgifter": u}).status_code == 409

    # Den publicerade gäller tills den nya publiceras, av en utgivare som inte ändrat den.
    logga_in(api, None)
    assert api.get("/api/budget/2027").json()["planforutsattningar"]["id"] == p["id"]
    granska_och_publicera(api, "planforutsattningar", ny["id"], roll="lasare+utgivare")
    plan = api.get("/api/budget/2027").json()["planforutsattningar"]
    assert [x["mnkr"] for x in plan["tabeller"]["namnder"] if x["post"] == "Kommunstyrelsen"] == [188.0]
    assert (plan["andring"]["motivering"], plan["andring"]["tidigare"]) == (ANDRING, p["id"])
    tidigare = api.get(f"/api/budget/tidigare/planforutsattningar/{p['id']}").json()
    assert (tidigare["status"], [x["mnkr"] for x in tidigare["tabeller"]["namnder"] if x["post"] == "Kommunstyrelsen"]) == ("ersatt", [187.0])
    assert api.get(f"/api/budget/tidigare/planforutsattningar/{plan['id']}").status_code == 404


def test_ny_inlasning_ger_en_ny_version(api, database_url, monkeypatch, capsys, tmp_path):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    p, l = publicerat(api, "planforutsattningar"), publicerat(api, "budgetforslag", "L")
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    bok = openpyxl.load_workbook(mapp / "planforutsattningar.xlsx")
    [rad] = [r for r in bok["2027"].iter_rows() if r[0].value == "Nämnder" and r[1].value == "Kommunstyrelsen"]
    rad[2].value = 188
    bok.save(mapp / "planforutsattningar.xlsx")
    besk = mapp / "2027" / "budget.json"
    data = json.loads(besk.read_text(encoding="utf-8"))
    data["forslag"]["L.pdf"]["resultat"] = {"procent": 4.0, "sida": 1}
    besk.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    las_in(database_url, monkeypatch, capsys, mapp)
    publicera_alla(api)

    j = api.get("/api/budget/2027").json()
    assert j["planforutsattningar"]["andring"]["motivering"] == pf.INLASNING
    assert j["planforutsattningar"]["andring"]["tidigare"] == p["id"]
    [l2] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert (l2["andring"]["motivering"], l2["andring"]["tidigare"]) == (pf.INLASNING, l["id"])
    # Moderaterna anger bara förändringen, så deras ram räknas om mot den rättade planen och får en ny version.
    # Förslag med egna belopp är oförändrade.
    assert {f["nyckel"]: f["andring"] is not None for f in j["forslag"]} == {"majoritet": False, "L": True, "M": True, "SD": False}
