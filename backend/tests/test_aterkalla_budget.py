"""Återkalla publicerade planförutsättningar och budgetförslag (#76, del 1).

En utgivare återkallar en publicerad uppgift direkt, med motivering, utan att någon annan godkänner det.
Läsaren ser en notis i stället för uppgiften, och inga uppgifter ur den återkallade versionen. Den visas
igen först när en rättad version har publicerats i det vanliga flödet. Återkallandet bevaras vid en ny
inläsning av filerna.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import openpyxl
import psycopg
from psycopg.types.json import Jsonb
from test_budgetforslag import FIXTURER, api, las_in, logga_in, publicera_alla  # noqa: F401 – fixturen api

MOTIVERING = "Kommunstyrelsens ram är fel avläst. Påpekat av en läsare 2026-11-20."


def planen(api) -> dict:
    logga_in(api, "redaktor")
    [p] = api.get("/api/planforutsattningar?status=publicerad").json()
    return p


def forslaget(api, nyckel: str, status: str = "publicerad") -> dict:
    logga_in(api, "redaktor")
    [f] = [f for f in api.get(f"/api/budgetforslag?status={status}").json() if f["nyckel"] == nyckel]
    return f


def test_utgivaren_aterkallar_planforutsattningarna(api, database_url, monkeypatch, capsys, tmp_path):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    p = planen(api)

    # Bara en utgivare, och bara med motivering.
    assert api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 403
    logga_in(api, "utgivare")
    utan = api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": " "})
    assert utan.status_code == 422
    ater = api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": MOTIVERING}).json()
    assert (ater["status"], ater["aterkallelse"], ater["aterkallad_av"]) == ("aterkallad", MOTIVERING, "test-utgivare@kommunkollen.test")
    assert ater["aterkallad"]
    # Det som redan är återkallat kan inte återkallas igen.
    assert api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 409

    # Läsaren ser året utan planförutsättningar: inga förändringar och inget beräknat resultat, och en notis.
    logga_in(api, None)
    j = api.get("/api/budget/2027").json()
    assert j["planforutsattningar"] is None
    assert j["aterkallat"] == {"planforutsattningar": True, "forslag": []}
    assert "187" not in json.dumps(j["skr"])
    [l] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert (l["berakning"]["planforutsattningar"], l["berakning"]["beraknat"], l["berakning"]["ramar"][0]["forandring"]) == (False, None, None)
    # Inga belopp ur planförutsättningarna i källorna eller förslagen.
    assert all(r.get("plan") is None for r in l["berakning"]["ramar"])

    # Redaktionen ser det återkallade med motiveringen.
    logga_in(api, "redaktor")
    [a] = api.get("/api/planforutsattningar?status=aterkallad").json()
    assert (a["id"], a["aterkallelse"]) == (p["id"], MOTIVERING)

    # En ny inläsning av samma fil ändrar inget: uppgifterna är återkallade och kommer inte tillbaka.
    assert "1 oförändrade" in las_in(database_url, monkeypatch, capsys)
    logga_in(api, "redaktor")
    assert api.get("/api/planforutsattningar?status=utkast").json() == []

    # En rättad fil ger ett nytt utkast, som publiceras i det vanliga flödet.
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    bok = openpyxl.load_workbook(mapp / "planforutsattningar.xlsx")
    flik = bok["2027"]
    [rad] = [r for r in flik.iter_rows() if r[0].value == "Nämnder" and r[1].value == "Kommunstyrelsen"]
    rad[2].value = 188
    bok.save(mapp / "planforutsattningar.xlsx")
    assert "1 nya utkast" in las_in(database_url, monkeypatch, capsys, mapp)
    publicera_alla(api)
    j = api.get("/api/budget/2027").json()
    assert j["aterkallat"]["planforutsattningar"] is False
    assert [x["mnkr"] for x in j["planforutsattningar"]["tabeller"]["namnder"] if x["post"] == "Kommunstyrelsen"] == [188.0]
    # Det återkallade bevaras.
    logga_in(api, "redaktor")
    [a] = api.get("/api/planforutsattningar?status=aterkallad").json()
    assert a["id"] == p["id"]


def test_den_forra_versionen_kommer_inte_tillbaka(api, database_url, monkeypatch, capsys, tmp_path):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    bok = openpyxl.load_workbook(mapp / "planforutsattningar.xlsx")
    [rad] = [r for r in bok["2027"].iter_rows() if r[0].value == "Nämnder" and r[1].value == "Kommunstyrelsen"]
    rad[2].value = 188
    bok.save(mapp / "planforutsattningar.xlsx")
    las_in(database_url, monkeypatch, capsys, mapp)
    publicera_alla(api)
    p = planen(api)
    logga_in(api, "utgivare")
    assert api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 200

    logga_in(api, None)
    j = api.get("/api/budget/2027").json()
    assert (j["planforutsattningar"], j["aterkallat"]["planforutsattningar"]) == (None, True)
    logga_in(api, "redaktor")
    assert len(api.get("/api/planforutsattningar?status=ersatt").json()) == 1


def test_utgivaren_aterkallar_ett_budgetforslag(api, database_url, monkeypatch, capsys, tmp_path):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    l = forslaget(api, "L")

    assert api.post(f"/api/budgetforslag/{l['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 403
    logga_in(api, "utgivare")
    assert api.post(f"/api/budgetforslag/{l['id']}/aterkallelse", json={}).status_code == 422
    ater = api.post(f"/api/budgetforslag/{l['id']}/aterkallelse", json={"motivering": MOTIVERING}).json()
    assert (ater["status"], ater["aterkallelse"]) == ("aterkallad", MOTIVERING)

    # Förslaget försvinner ur jämförelsen, och en notis står där det stod.
    logga_in(api, None)
    assert api.get("/api/budget").json() == [{"budgetar": 2027, "forslag": 3, "antagen": True}]
    j = api.get("/api/budget/2027").json()
    assert [f["nyckel"] for f in j["forslag"]] == ["majoritet", "M", "SD"]
    assert j["aterkallat"] == {"planforutsattningar": False,
                               "forslag": [{"nyckel": "L", "partier": ["L"], "titel": l["titel"], "typ": "budget"}]}
    # Planförutsättningarnas källor länkar inte längre till det återkallade förslaget.
    assert f"/{l['id']}/" not in json.dumps(j)
    assert api.get(l["original"]).status_code == 404

    # En ny inläsning av samma fil ändrar inget. En rättad beskrivning ger ett nytt utkast.
    assert "budgetförslag: 0 nya utkast, 0 uppdaterade, 4 oförändrade" in las_in(database_url, monkeypatch, capsys)
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    besk = mapp / "2027" / "budget.json"
    data = json.loads(besk.read_text(encoding="utf-8"))
    data["forslag"]["L.pdf"]["resultat"] = {"procent": 4.0, "sida": 1}
    besk.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert "1 nya utkast" in las_in(database_url, monkeypatch, capsys, mapp)
    publicera_alla(api)
    j = api.get("/api/budget/2027").json()
    assert j["aterkallat"]["forslag"] == []
    [ny] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert ny["uppgifter"]["resultat"]["procent"] == 4.0
    # Det återkallade bevaras.
    assert forslaget(api, "L", "aterkallad")["id"] == l["id"]


def test_alla_forslag_aterkallade(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    logga_in(api, "utgivare")
    for f in api.get("/api/budgetforslag?status=publicerad").json():
        assert api.post(f"/api/budgetforslag/{f['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 200
    # Året finns kvar, så att läsaren ser notiserna.
    logga_in(api, None)
    assert api.get("/api/budget").json() == [{"budgetar": 2027, "forslag": 0, "antagen": False}]
    j = api.get("/api/budget/2027").json()
    assert (j["forslag"], j["antagen"]) == ([], None)
    assert [f["nyckel"] for f in j["aterkallat"]["forslag"]] == ["majoritet", "L", "M", "SD"]


def test_overforingen_behaller_det_aterkallade(api, database_url, monkeypatch, capsys, tmp_path):
    """Ett återkallat förslag i formatet före #58 förs över där det står och förblir återkallat."""
    from app import db

    db.migrate(database_url)
    gammal = {"skattesats": {"procent": 23.24, "sida": 1}, "resultat": [{"ar": 2027, "mnkr": 55.3, "sida": 2}],
              "ramar": [{"organ": "Kommunstyrelsen", "ar": 2027, "mnkr": 150, "sida": 1}]}
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO budgetforslag (budgetar, nyckel, partier, titel, typ, filnamn, sha256, original, inlast, uppgifter, "
            "status, redaktorer, publicerad, publicerad_av, aterkallad, aterkallad_av, aterkallelse) VALUES (2027, 'C', "
            "'{C}', 'x', 'budget', 'C.pdf', 'x', '\\x00', %s, %s, 'aterkallad', '{tidigare@kommunkollen.test}', now(), "
            "'u@kommunkollen.test', now(), 'u@kommunkollen.test', %s)",
            (Jsonb({"uppgifter": gammal}), Jsonb(gammal), MOTIVERING),
        )
    mapp = tmp_path / "budgetforslag"
    mapp.mkdir()
    shutil.copy(FIXTURER / "planforutsattningar.xlsx", mapp)
    assert "0 utkast, 0 nya utkast för publicerade förslag, 1 ersatta" in las_in(database_url, monkeypatch, capsys, mapp)
    c = forslaget(api, "C", "aterkallad")
    assert (c["aterkallelse"], c["uppgifter"]["resultat"]) == (MOTIVERING, {"procent": c["uppgifter"]["resultat"]["procent"], "sida": 2})


def test_bara_publicerat_kan_aterkallas(api, database_url, monkeypatch, capsys):
    las_in(database_url, monkeypatch, capsys)
    logga_in(api, "utgivare")
    [f, *_] = api.get("/api/budgetforslag?status=utkast").json()
    [p] = api.get("/api/planforutsattningar?status=utkast").json()
    assert api.post(f"/api/budgetforslag/{f['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 409
    assert api.post(f"/api/planforutsattningar/{p['id']}/aterkallelse", json={"motivering": MOTIVERING}).status_code == 409
    assert api.post("/api/budgetforslag/999999/aterkallelse", json={"motivering": MOTIVERING}).status_code == 404
