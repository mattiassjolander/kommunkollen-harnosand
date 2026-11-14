"""Ekonomiska flöden (Sankey) från SCB:s räkenskapssammandrag."""

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from conftest import INSPELNINGAR, skapa_app

DRIFT = "api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0107/OE0107B/Driftredovisning"
RESULT = "api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0107/OE0107A/ResultKnN"
AR = "2024"


def manifest() -> dict:
    return json.loads((INSPELNINGAR / "manifest.json").read_text(encoding="utf-8"))


def inspelning(nyckel: str, katalog=INSPELNINGAR) -> dict:
    return json.loads((katalog / manifest()[nyckel]).read_text(encoding="utf-8-sig"))


def scb_varde(data: dict, post: str, ar: str, innehall: str | None = None) -> float:
    kolumner = [k["code"] for k in data["columns"] if k["type"] == "c"]
    [rad] = [r for r in data["data"] if r["key"][1] == post and r["key"][2] == ar]
    return float(rad["values"][kolumner.index(innehall) if innehall else 0])


def oppen_app(database_url, google, inspelningar=INSPELNINGAR) -> TestClient:
    api = TestClient(skapa_app(database_url, google, inspelningar=inspelningar, anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/insamlingar").json()["status"] == "lyckad"
    api.post("/api/auth/logga-ut")
    return api


@pytest.fixture
def api(database_url, google) -> TestClient:
    return oppen_app(database_url, google)


def noder(modell: dict) -> dict[str, dict]:
    return {n["id"]: n for n in modell["noder"]}


def test_floden_visar_intakter_till_verksamhetsomraden_och_anger_indelning_och_flodestyp(api):
    m = api.get(f"/api/floden?ar={AR}").json()
    assert m["fullstandig"] is True
    assert m["flodestyp"] == "brutto"
    assert "verksamhetsindelning" in m["indelning"] and "inte kommunens nämnder" in m["indelning"]

    n = noder(m)
    for intakt in ("kommunalskatt", "generella_statsbidrag", "utjamning", "riktade_statsbidrag", "avgifter",
                   "finansiella_intakter"):
        assert n[intakt]["sida"] == "in", intakt
    for omrade in ("omrade_490", "omrade_590", "omrade_290"):
        assert n[omrade]["sida"] == "ut", omrade
    assert n["omrade_490"]["titel"] == "Pedagogisk verksamhet"

    # Varje intäkt går till kommunen, och kommunen går till varje utflöde.
    for f in m["floden"]:
        assert "kommunen" in (f["fran"], f["till"])


def test_inflod_och_utflod_summerar_till_resultatrakningen(api):
    m = api.get(f"/api/floden?ar={AR}").json()
    in_ = sum(f["belopp"] for f in m["floden"] if f["till"] == "kommunen")
    ut = sum(f["belopp"] for f in m["floden"] if f["fran"] == "kommunen")
    assert in_ == pytest.approx(ut)
    assert m["totalt"] == pytest.approx(in_)
    assert m["differens"] == pytest.approx(0)
    assert sum(f["andel"] for f in m["floden"] if f["till"] == "kommunen") == pytest.approx(1)

    res = inspelning(RESULT)
    intakter = sum(scb_varde(res, p, AR) for p in ("010", "040", "050", "060"))
    resultat = scb_varde(res, "120", AR)
    # Ett underskott finansieras med eget kapital och hamnar på intäktssidan.
    assert in_ == pytest.approx(intakter + max(0, -resultat))
    assert noder(m)["resultat"]["titel"] == ("Årets underskott" if resultat < 0 else "Årets överskott")
    assert noder(m)["kommunalskatt"]["belopp"] == scb_varde(res, "040", AR)


def test_interna_poster_dubbelraknas_inte(api):
    m = api.get(f"/api/floden?ar={AR}").json()
    drift = inspelning(DRIFT)
    brutto = scb_varde(drift, "490", AR, "000000Z3")
    internt = scb_varde(drift, "490", AR, "000000Z7") + scb_varde(drift, "490", AR, "000000YY")
    assert noder(m)["omrade_490"]["belopp"] == pytest.approx(brutto - internt)
    assert noder(m)["omrade_490"]["belopp"] < brutto

    # Gemensamma verksamheter ingår i områdena genom fördelningen och visas inte för sig.
    assert not any("gemensam" in n["titel"].lower() for n in m["noder"])
    # Summan av områdena överstiger inte resultaträkningens kostnader.
    omraden = sum(n["belopp"] for n in m["noder"] if n["id"].startswith("omrade_"))
    assert omraden <= -scb_varde(inspelning(RESULT), "022", AR) + 1


def test_klick_pa_flode_ger_belopp_andel_kronor_per_invanare_och_kalla(api):
    m = api.get(f"/api/floden?ar={AR}").json()
    [skatt] = [f for f in m["floden"] if f["fran"] == "kommunalskatt"]
    assert skatt["belopp"] > 0
    assert 0 < skatt["andel"] < 1
    assert m["invanare"] > 20000
    assert skatt["kr_per_invanare"] == pytest.approx(skatt["belopp"] * 1000 / m["invanare"])
    [kalla] = skatt["kallor"]
    assert "ResultKnN" in kalla["titel"]
    assert kalla["url"].startswith("https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__OE__OE0107__OE0107A/ResultKnN")


def test_utan_ar_visas_senaste_fullstandiga_aret(api):
    m = api.get("/api/floden").json()
    fullstandiga = [a["ar"] for a in m["tillgangliga_ar"] if a["fullstandig"]]
    assert m["ar"] == fullstandiga[-1]
    assert "2011" in fullstandiga  # driftredovisningen finns från 2011
    # Före 2011 finns inte intäkterna per kontopost: ofullständigt, inte utfyllt.
    assert {"ar": "2005", "fullstandig": False} in m["tillgangliga_ar"]


def test_ofullstandigt_ar_markeras_och_fylls_inte_ut(database_url, google, tmp_path):
    # SCB saknar (..) Pedagogisk verksamhets bruttokostnad för 2023.
    shutil.copytree(INSPELNINGAR, tmp_path / "rec")
    fil = tmp_path / "rec" / manifest()[DRIFT]
    data = json.loads(fil.read_text(encoding="utf-8-sig"))
    kolumner = [k["code"] for k in data["columns"] if k["type"] == "c"]
    for rad in data["data"]:
        if rad["key"][1] == "490" and rad["key"][2] == "2023":
            rad["values"][kolumner.index("000000Z3")] = ".."
    fil.write_text(json.dumps(data), encoding="utf-8")

    api = oppen_app(database_url, google, inspelningar=tmp_path / "rec")
    m = api.get("/api/floden?ar=2023").json()
    assert m["fullstandig"] is False
    assert m["noder"] == [] and m["floden"] == []
    assert any("Pedagogisk verksamhet" in s for s in m["saknas"])
    assert {"ar": "2023", "fullstandig": False} in m["tillgangliga_ar"]
    assert api.get("/api/floden?ar=2024").json()["fullstandig"] is True


def test_ett_ar_dar_summorna_inte_gar_ihop_visas_inte(database_url, google, tmp_path):
    # Årets resultat för 2022 ändras så att resultaträkningen inte längre går ihop.
    shutil.copytree(INSPELNINGAR, tmp_path / "rec")
    fil = tmp_path / "rec" / manifest()[RESULT]
    data = json.loads(fil.read_text(encoding="utf-8-sig"))
    for rad in data["data"]:
        if rad["key"][1] == "120" and rad["key"][2] == "2022":
            rad["values"] = [str(int(rad["values"][0]) + 5000)]
    fil.write_text(json.dumps(data), encoding="utf-8")

    m = oppen_app(database_url, google, inspelningar=tmp_path / "rec").get("/api/floden?ar=2022").json()
    assert m["fullstandig"] is False
    assert m["floden"] == []
    assert "går inte ihop" in m["saknas"][0]


# Fördjupning: ett verksamhetsområdes kostnadsslag (#12)

KOSTNADSSLAG = {"personal", "lokaler", "kop_av_tjanster", "material", "kapitalkostnader", "ovrigt"}


def test_klick_pa_verksamhetsomrade_ger_dess_kostnadsslag(api):
    m = api.get(f"/api/floden?ar={AR}&verksamhet=490").json()
    assert m["fullstandig"] is True
    assert m["verksamhet"] == {"kod": "490", "id": "omrade_490", "titel": "Pedagogisk verksamhet"}
    n = noder(m)
    assert {i for i, x in n.items() if x["sida"] == "ut"} == KOSTNADSSLAG

    drift = inspelning(DRIFT)
    v = lambda innehall: scb_varde(drift, "490", AR, innehall)  # noqa: E731
    brutto = v("000000Z3")
    assert n["omrade_490"]["sida"] == "mitt"
    assert n["omrade_490"]["belopp"] == pytest.approx(brutto)
    assert sum(x["belopp"] for x in n.values() if x["sida"] == "ut") == pytest.approx(brutto)
    assert n["personal"]["belopp"] == pytest.approx(v("000000YR") + v("000000YS"))
    assert n["kapitalkostnader"]["belopp"] == pytest.approx(v("000000YY"))

    # Finansieringen hänger ihop med kommunnivån: samma belopp som flödet till området där.
    kommun = noder(api.get(f"/api/floden?ar={AR}").json())
    assert n["fran_kommunen"]["belopp"] == pytest.approx(kommun["omrade_490"]["belopp"])
    assert n["interna_poster"]["belopp"] == pytest.approx(v("000000Z7") + v("000000YY"))
    for f in m["floden"]:
        assert "omrade_490" in (f["fran"], f["till"])
        assert "Driftredovisning" in f["kallor"][0]["titel"]


def test_alla_verksamhetsomraden_kan_fordjupas_och_okant_ger_404(api):
    for kod in ("190", "290", "390", "490", "590", "690", "890"):
        assert api.get(f"/api/floden?ar={AR}&verksamhet={kod}").json()["fullstandig"] is True, kod
    assert api.get("/api/floden?verksamhet=999").status_code == 404


# Årsjämförelse (#12)


def test_tva_ar_jamfors_per_flode_i_kronor_och_procent(api):
    m = api.get(f"/api/floden?ar={AR}&jamfor=2023").json()
    assert m["ar"] == AR and m["jamforelse_ar"] == "2023"
    res = inspelning(RESULT)
    [skatt] = [f for f in m["floden"] if f["fran"] == "kommunalskatt"]
    nu, da = scb_varde(res, "040", AR), scb_varde(res, "040", "2023")
    assert skatt["jamforelse"]["belopp"] == pytest.approx(da)
    assert skatt["jamforelse"]["forandring"] == pytest.approx(nu - da)
    assert skatt["jamforelse"]["procent"] == pytest.approx((nu - da) / da)
    assert all("jamforelse" in f for f in m["floden"])

    # Årets resultat jämförs även om det bytt mellan över- och underskott.
    # 2024/2023: underskott båda åren. 2024/2022 och 2025/2024: bytt riktning.
    for ar, tidigare in ((AR, "2023"), (AR, "2022"), ("2025", AR)):
        m = api.get(f"/api/floden?ar={ar}&jamfor={tidigare}").json()
        [res_flode] = [f for f in m["floden"] if "resultat" in (f["fran"], f["till"])]
        r_nu, r_da = scb_varde(res, "120", ar), scb_varde(res, "120", tidigare)
        tecken = 1 if r_nu >= 0 else -1
        assert res_flode["jamforelse"]["forandring"] == pytest.approx(tecken * (r_nu - r_da)), ar


def test_jamforelse_inom_ett_verksamhetsomrade(api):
    m = api.get(f"/api/floden?ar={AR}&jamfor=2015&verksamhet=590").json()
    drift = inspelning(DRIFT)
    personal = lambda ar: scb_varde(drift, "590", ar, "000000YR") + scb_varde(drift, "590", ar, "000000YS")  # noqa: E731
    [f] = [f for f in m["floden"] if f["till"] == "personal"]
    assert f["jamforelse"]["forandring"] == pytest.approx(personal(AR) - personal("2015"))
    assert f["jamforelse"]["procent"] == pytest.approx((personal(AR) - personal("2015")) / personal("2015"))


def test_jamforelse_med_ofullstandigt_ar_fylls_inte_ut(api):
    m = api.get(f"/api/floden?ar={AR}&jamfor=2005").json()
    assert m["fullstandig"] is True
    assert m["jamforelse_ar"] == "2005" and m["jamforelse_fullstandig"] is False
    assert not any("jamforelse" in f for f in m["floden"])
