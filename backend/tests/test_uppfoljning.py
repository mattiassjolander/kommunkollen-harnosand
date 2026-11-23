"""Budget jämfört med utfall per budgetår (#83, kravspec 3.2).

Reviderad budget, delårsprognos och utfall läses in ur `uppfoljning.json` i budgetårets mapp, med sida för varje
siffra, och går utkast → granskad → publicerad. Den antagna budgetens ramar och resultat hämtas ur det antagna
budgetförslaget. Avvikelserna räknas i mnkr och procent, och dokumentets avvikelse kontrolleras mot den räknade.
"""

from __future__ import annotations

import json
import shutil

import pytest
from test_budgetforslag import FIXTURER, api, las_in, logga_in, publicera_alla  # noqa: F401 – fixturen api

from app import uppfoljning
from app.planforutsattningar import Ogiltig

FIL = FIXTURER / "2027" / uppfoljning.FILNAMN


def data() -> dict:
    return json.loads(FIL.read_text(encoding="utf-8"))


def test_filen_lases_med_sidor():
    [u] = uppfoljning.las_mapp(FIXTURER)
    assert u.budgetar == 2027
    assert u.uppgifter["arsredovisning"]["titel"] == "Årsredovisning 2027"
    soc = next(n for n in u.uppgifter["namnder"] if n["organ"] == "Socialnämnden")
    assert soc["budget"] == {"mnkr": 905.2, "sida": 81}
    assert soc["prognosavvikelse"] == {"mnkr": -12.5, "sida": 25}


@pytest.mark.parametrize("andring, fel", [
    (lambda d: d["namnder"][0]["budget"].pop("sida"), "sida ska vara sidnumret"),
    (lambda d: d["namnder"][0].update(budget={"mnkr": "195", "sida": 81}), "mnkr ska vara ett tal"),
    (lambda d: d.pop("delarsrapport"), "står i delårsrapporten"),
    (lambda d: d["namnder"].append({"organ": "Skolnämnden"}), "Samma nämnd"),
    (lambda d: d["arsredovisning"].update(url="www.example.org"), "https-adress"),
    (lambda d: d.update(okand=1), "Okända fält: okand"),
    (lambda d: d["namnder"][0].update(ram={"mnkr": 1, "sida": 1}), "okända fält: ram"),
])
def test_fel_i_filen_ger_begripligt_felmeddelande(andring, fel):
    d = data()
    andring(d)
    with pytest.raises(Ogiltig, match=fel):
        uppfoljning.uppgifter(d)


def test_ar_utan_arsredovisning_har_bara_prognosen():
    u = uppfoljning.uppgifter({
        "delarsrapport": {"titel": "Delårsrapport augusti 2026", "url": "https://example.org/d.pdf"},
        "resultat": {"prognos": {"mnkr": -12.0, "sida": 20}, "prognos_budget": {"mnkr": 5.0, "sida": 20}},
        "namnder": [{"organ": "Skolnämnden", "prognosavvikelse": {"mnkr": -3.0, "sida": 21}}],
    })
    b = uppfoljning.berakning(u, {"ramar": {"Skolnämnden": {"mnkr": 600.0, "sida": 4}}, "resultat": None})
    [skol] = b["namnder"]
    assert skol["reviderad"] is None and skol["utfall"] is None and skol["kontroll"] is None
    # Prognosavvikelsen i procent räknas av den antagna ramen när den reviderade saknas.
    assert skol["prognosavvikelse"] == {"mnkr": -3.0, "sida": 21, "procent": -0.5}
    assert b["resultat"]["prognosavvikelse"] == {"mnkr": -17.0, "procent": -340.0}


def test_berakningen_mot_antagen_och_reviderad_budget():
    u = uppfoljning.uppgifter(data())
    antagen = {"ramar": {"Socialnämnden": {"mnkr": 893.1, "sida": 4}, "Kommungemensam verksamhet": {"mnkr": 138.9, "sida": 4}},
               "resultat": {"mnkr": 50.3, "procent": 2.3, "sida": 3}}
    b = uppfoljning.berakning(u, antagen)
    soc = next(n for n in b["namnder"] if n["organ"] == "Socialnämnden")
    # Budget minus nettokostnad, som i årsredovisningen.
    assert soc["avvikelse_reviderad"] == {"mnkr": -10.2, "procent": -1.1}
    assert soc["avvikelse_antagen"] == {"mnkr": -22.3, "procent": -2.5}
    assert soc["andring"] == {"mnkr": 12.1, "procent": 1.4}
    assert soc["kontroll"] == {"angiven": -10.2, "sida": 81, "raknad": -10.2, "differens": 0.0, "stammer": True}
    # En nämnd i uppföljningen som inte finns i årsplanen, och en ram i årsplanen utan uppföljning.
    ovr = next(n for n in b["namnder"] if n["organ"] == "Kommunövergripande verksamhet")
    assert ovr["antagen"] is None and ovr["avvikelse_antagen"] is None
    assert b["utan_uppfoljning"] == [{"organ": "Kommungemensam verksamhet", "antagen": {"mnkr": 138.9, "sida": 4}}]
    # Resultatet: resultat minus budget.
    assert b["resultat"]["avvikelse_reviderad"] == {"mnkr": -12.2, "procent": -24.3}
    assert b["resultat"]["avvikelse_antagen"] == {"mnkr": -12.2, "procent": -24.3}
    assert b["resultat"]["kontroll"]["stammer"] is True
    assert b["resultat"]["prognosavvikelse"] == {"mnkr": -19.3, "procent": -38.4}


def test_avvikelse_som_inte_gar_ihop_visas():
    d = data()
    d["namnder"][0]["avvikelse"]["mnkr"] = 5.8
    b = uppfoljning.berakning(uppfoljning.uppgifter(d), None)
    assert b["namnder"][0]["kontroll"] == {"angiven": 5.8, "sida": 81, "raknad": 4.8, "differens": 1.0, "stammer": False}


def test_uppfoljningen_granskas_och_publiceras(api, database_url, monkeypatch, capsys, tmp_path):
    ut = las_in(database_url, monkeypatch, capsys)
    assert "1 uppföljningar: 1 nya utkast, 0 uppdaterade, 0 oförändrade." in ut
    publicera_alla(api)

    # Läsaren ser inget förrän uppföljningen är publicerad.
    assert api.get("/api/budget-och-utfall").json() == []
    assert api.get("/api/budget-och-utfall/2027").status_code == 404

    logga_in(api, "redaktor")
    [u] = api.get("/api/uppfoljning?status=utkast").json()
    assert u["redaktorer"] == ["test-redaktor@kommunkollen.test"]
    # Redaktören läste in och kan inte godkänna; bara en utgivare.
    assert api.post(f"/api/uppfoljning/{u['id']}/granskning").status_code == 403
    logga_in(api, "utgivare")
    assert api.post(f"/api/uppfoljning/{u['id']}/publicering").status_code == 409
    assert api.post(f"/api/uppfoljning/{u['id']}/granskning").json()["status"] == "granskad"
    assert api.post(f"/api/uppfoljning/{u['id']}/publicering").json()["status"] == "publicerad"

    logga_in(api, None)
    assert api.get("/api/budget-och-utfall").json() == [{"budgetar": 2027, "publicerad": True}]
    j = api.get("/api/budget-och-utfall/2027").json()
    assert "redaktorer" not in j and j["aterkallad"] is False
    # Den antagna budgeten kommer ur årsplanen, med länk till förslaget och behandlingen i fullmäktige.
    assert j["antagen"]["titel"] == "Årsplan 2027"
    assert j["antagen"]["original"].startswith("/api/budgetforslag/")
    assert (j["antagen"]["behandling"]["organ"], j["antagen"]["behandling"]["paragraf"]) == ("KF", 108)
    soc = next(n for n in j["berakning"]["namnder"] if n["organ"] == "Socialnämnden")
    assert soc["antagen"] == {"mnkr": 893.1, "sida": 4}
    assert soc["avvikelse_antagen"] == {"mnkr": -22.3, "procent": -2.5}
    # Årsplanens resultat lagras i procent av skatter och bidrag. Beloppet räknas ur planförutsättningarna.
    assert j["berakning"]["resultat"]["antagen"] == {"mnkr": 51.0, "procent": 2.3, "sida": 3, "beraknat": True}
    assert j["dokument"]["delarsrapport"]["url"] == "https://example.org/delarsrapport-2027.pdf"

    # Samma fil igen ändrar inget. En ändrad fil ger en ny version av den publicerade.
    assert "1 uppföljningar: 0 nya utkast, 0 uppdaterade, 1 oförändrade." in las_in(database_url, monkeypatch, capsys)
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    d = data()
    d["resultat"]["utfall"]["mnkr"] = 38.4
    (mapp / "2027" / uppfoljning.FILNAMN).write_text(json.dumps(d), encoding="utf-8")
    assert "1 uppföljningar: 1 nya utkast" in las_in(database_url, monkeypatch, capsys, mapp)
    logga_in(api, "redaktor")
    [ny] = api.get("/api/uppfoljning?status=utkast").json()
    assert ny["andring"] is None or ny["andring"]["tidigare"] == u["id"]

    # En utgivare återkallar den publicerade, och läsaren ser en notis.
    logga_in(api, "utgivare")
    assert api.post(f"/api/uppfoljning/{u['id']}/aterkallelse", json={"motivering": "Fel utfall"}).json()["status"] == "aterkallad"
    logga_in(api, None)
    assert api.get("/api/budget-och-utfall/2027").json() == {"budgetar": 2027, "aterkallad": True}


def test_ogiltig_fil_avbryter_inlasningen(database_url, monkeypatch, capsys, tmp_path):
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    (mapp / "2027" / uppfoljning.FILNAMN).write_text('{"namnder": []}', encoding="utf-8")
    with pytest.raises(SystemExit, match="2027/uppfoljning.json: Ange årsredovisningen"):
        las_in(database_url, monkeypatch, capsys, mapp)
