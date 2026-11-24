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


def _pdf(sokvag) -> None:
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(100, 100)
    with open(sokvag, "wb") as f:
        w.write(f)


def test_dokument_utan_publik_adress_lagras_och_visas(api, database_url, monkeypatch, capsys, tmp_path):
    """En delårsrapport som begärts ur diariet lagras i plattformen och visas först när uppföljningen är publicerad."""
    mapp = tmp_path / "budgetforslag"
    shutil.copytree(FIXTURER, mapp)
    (mapp / "2027" / uppfoljning.DOKUMENTMAPP).mkdir()
    _pdf(mapp / "2027" / uppfoljning.DOKUMENTMAPP / "delarsrapport-2027.pdf")
    d = data()
    d["delarsrapport"] = {"titel": "Delårsrapport augusti 2027", "fil": "delarsrapport-2027.pdf",
                          "kalla": "Begärd ur kommunens diarium"}
    (mapp / "2027" / uppfoljning.FILNAMN).write_text(json.dumps(d), encoding="utf-8")
    las_in(database_url, monkeypatch, capsys, mapp)
    publicera_alla(api)

    logga_in(api, "redaktor")
    [u] = api.get("/api/uppfoljning?status=utkast").json()
    url = f"/api/uppfoljning/{u['id']}/dokument/delarsrapport"
    assert u["dokument"]["delarsrapport"] == {"titel": "Delårsrapport augusti 2027", "url": url,
                                              "kalla": "Begärd ur kommunens diarium"}
    svar = api.get(url)
    assert svar.status_code == 200 and svar.headers["content-type"] == "application/pdf"
    assert svar.content.startswith(b"%PDF")
    # Läsaren ser inte dokumentet förrän uppföljningen är publicerad.
    logga_in(api, None)
    assert api.get(url).status_code == 404
    logga_in(api, "utgivare")
    api.post(f"/api/uppfoljning/{u['id']}/granskning")
    api.post(f"/api/uppfoljning/{u['id']}/publicering")
    logga_in(api, None)
    assert api.get(url).status_code == 200

    # Samma fil igen ändrar inget. En ändrad PDF ger en ny version.
    assert "1 oförändrade" in las_in(database_url, monkeypatch, capsys, mapp)
    w_ = mapp / "2027" / uppfoljning.DOKUMENTMAPP / "delarsrapport-2027.pdf"
    w_.write_bytes(w_.read_bytes() + b"%%EOF")
    assert "1 nya utkast" in las_in(database_url, monkeypatch, capsys, mapp)


@pytest.mark.parametrize("dok, fel", [
    ({"titel": "D", "fil": "saknas.pdf", "kalla": "Diariet"}, "finns inte"),
    ({"titel": "D", "fil": "d.pdf"}, "ange var filen kommer ifrån"),
    ({"titel": "D", "fil": "../d.pdf", "kalla": "Diariet"}, "namnet på en PDF"),
    ({"titel": "D", "fil": "d.pdf", "url": "https://example.org/d.pdf", "kalla": "Diariet"}, "inte båda"),
])
def test_fel_i_lagrat_dokument(tmp_path, dok, fel):
    d = data()
    d["delarsrapport"] = dok
    with pytest.raises(Ogiltig, match=fel):
        uppfoljning.uppgifter(d, tmp_path)


# Revideringarna kopplade till beslut och orsakerna till avvikelserna (#134)

ANTAGEN_2027 = {"ramar": {"Kommunstyrelsen": {"mnkr": 191.3, "sida": 4}, "Kommunfullmäktige": {"mnkr": 13.4, "sida": 4},
                          "Samhällsnämnden": {"mnkr": 243.5, "sida": 4}, "Skolnämnden": {"mnkr": 664.4, "sida": 4},
                          "Socialnämnden": {"mnkr": 893.1, "sida": 4}},
                "resultat": None}


def test_revideringarna_fordelas_och_resten_visas_som_ej_kopplad():
    b = uppfoljning.berakning(uppfoljning.uppgifter(data()), ANTAGEN_2027)
    n = {x["organ"]: x for x in b["namnder"]}
    assert b["revideringar_utredda"] is True
    # Socialnämnden 893,1 → 905,2: hela ändringen är beslutad i KF 2026-06-15 § 108.
    [soc] = n["Socialnämnden"]["revideringar"]
    assert soc["mnkr"] == 12.1 and soc["belopp_sida"] is None
    assert (soc["beslut"]["organ"], soc["beslut"]["datum"], soc["beslut"]["paragraf"]) == ("KF", "2026-06-15", 108)
    assert n["Socialnämnden"]["ej_kopplat"] is None
    # Kommunstyrelsen: beloppet står inte i beslutet utan på sidan i årsredovisningen.
    assert n["Kommunstyrelsen"]["revideringar"][0]["belopp_sida"] == 82
    # Samhällsnämnden 243,5 → 245,1 har inget beslut: resten är ej kopplad.
    assert n["Samhällsnämnden"]["revideringar"] == [] and n["Samhällsnämnden"]["ej_kopplat"] == 1.6
    # Utan antagen ram (eller utan reviderad budget) går ingen rest att räkna.
    assert n["Kommunövergripande verksamhet"]["ej_kopplat"] is None


def test_utan_revideringar_ar_de_inte_utredda():
    d = data()
    d.pop("revideringar")
    b = uppfoljning.berakning(uppfoljning.uppgifter(d), ANTAGEN_2027)
    assert b["revideringar_utredda"] is False
    assert all(n["ej_kopplat"] is None and n["revideringar"] == [] for n in b["namnder"])
    # En tom lista: inga beslut hittade, och hela skillnaden är ej kopplad.
    d["revideringar"] = []
    b = uppfoljning.berakning(uppfoljning.uppgifter(d), ANTAGEN_2027)
    assert next(n for n in b["namnder"] if n["organ"] == "Socialnämnden")["ej_kopplat"] == 12.1


def test_orsakerna_visas_vid_namnden_som_citat():
    b = uppfoljning.berakning(uppfoljning.uppgifter(data()), ANTAGEN_2027)
    n = {x["organ"]: x for x in b["namnder"]}
    assert n["Socialnämnden"]["orsaker"] == [
        {"dokument": "arsredovisning", "sida": 81,
         "text": "Socialnämndens underskott beror främst på högre kostnader för placeringar än budgeterat."},
        {"dokument": "delarsrapport", "sida": 25, "text": "Socialnämnden prognostiserar ett underskott inom äldreomsorgen."},
    ]
    # Ett citat om flera nämnder visas vid var och en; ett utan nämnd gäller nämnderna i stort.
    assert n["Skolnämnden"]["orsaker"] == n["Samhällsnämnden"]["orsaker"]
    assert n["Kommunstyrelsen"]["orsaker"] == []
    assert b["orsaker"] == [{"dokument": "arsredovisning", "sida": 81, "text":
                             "Mer detaljerad information kring nämndernas utfall återfinns i respektive nämndsrapport."}]


@pytest.mark.parametrize("andring, fel", [
    (lambda d: d.update(revideringar={}), "revideringar ska vara en lista"),
    (lambda d: d["revideringar"][0]["beslut"].update(datum="15 juni 2026"), "beslut: datum ska anges"),
    (lambda d: d["revideringar"][0].update(andringar=[]), "andringar ska vara en lista"),
    (lambda d: d["revideringar"][0]["andringar"].append({"organ": "Gatunämnden", "mnkr": 1}), "Gatunämnden finns inte"),
    (lambda d: d["revideringar"][0]["andringar"][0].update(mnkr="12"), "mnkr ska vara ett tal"),
    (lambda d: d["revideringar"][0]["andringar"].append({"organ": "Skolnämnden", "mnkr": 1}), "samma nämnd"),
    (lambda d: (d.pop("arsredovisning"), d.pop("resultat"), d.update(namnder=[{"organ": "Kommunstyrelsen"}]),
                d.update(orsaker=[]), d["revideringar"].pop(0)), "belopp_sida är sidan i årsredovisningen"),
    (lambda d: d["orsaker"][0].update(dokument="protokoll"), "dokument ska vara"),
    (lambda d: d["orsaker"][0].update(text=" "), "text saknas"),
    (lambda d: d["orsaker"][0].pop("sida"), "sida ska vara sidnumret"),
    (lambda d: d["orsaker"][0].update(organ="Socialnämnden"), "organ ska vara en lista"),
])
def test_fel_i_revideringar_och_orsaker(andring, fel):
    d = data()
    andring(d)
    with pytest.raises(Ogiltig, match=fel):
        uppfoljning.uppgifter(d)


def test_revideringens_beslut_lankar_till_behandlingen(database_url, google, monkeypatch, capsys):
    """Beslutet KF 2026-06-15 § 108 finns i protokollen och länkar dit; § 120 2027-09-27 visas som hänvisning."""
    from conftest import skapa_app
    from fastapi.testclient import TestClient
    from test_protokoll import kf, kor

    api = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(api)
    las_in(database_url, monkeypatch, capsys)
    publicera_alla(api)
    logga_in(api, "utgivare")
    [u] = api.get("/api/uppfoljning?status=utkast").json()
    soc = next(n for n in u["berakning"]["namnder"] if n["organ"] == "Socialnämnden")
    b = soc["revideringar"][0]["beslut"]
    assert (b["hittad"], b["rubrik"]) == (True, "Mål, budget och skattesats 2027")
    assert api.get(f"/api/sammantraden/{b['sammantrade_id']}").json()["datum"] == "2026-06-15"
    ks = next(n for n in u["berakning"]["namnder"] if n["organ"] == "Kommunstyrelsen")
    assert ks["revideringar"][0]["beslut"] == {"organ": "KF", "datum": "2027-09-27", "paragraf": 120, "hittad": False,
                                              "sammantrade_id": None, "rubrik": None}
