"""Rankningar (#66): Svenskt Näringslivs lokala företagsklimat och Aktuell Hållbarhets miljöbästa kommun.

Söm 1: insamlingen hämtar från inspelningar (2026-11-24). Företagsklimatets tre Excelfiler är förminskade till
riket, Härnösand och grannkommunerna (och totalrankingen för alla kommuner, så att antalet rankade kommuner
stämmer). Miljöbarometerns sidor är sparade kopior utan skript och bilder. Sidan "Rankningar" läses från API:t.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import standardkallor
from app.recorded import InspeladTransport
from app.sources.foretagsklimat import Foretagsklimat, hitta_lankar
from app.sources.miljobarometern import Miljobarometern
from conftest import INSPELNINGAR, skapa_app

RANKNINGSFIL = "www.foretagsklimat.se/ladda-ner/j0o69c_rankingresultatxlsx_1231708.html/Rankingresultat.xlsx"
ENKATFIL = "www.foretagsklimat.se/ladda-ner/xun406_enkatresultatxlsx_1231709.html/Enkätresultat.xlsx"
RESULTATSIDA = "kommunrankning.miljobarometern.se/resultat/härnösand/"
OMDOME = "Vilket sammanfattande omdöme vill du ge företagsklimatet i kommunen?"


class Andrad(httpx.BaseTransport):
    """Inspelningarna, men med vissa svar utbytta (en ny version av en fil, ett nytt format, ett fel)."""

    def __init__(self, andringar: dict[str, object]) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.andringar = andringar

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        nyckel = f"{request.url.host}{request.url.path}"
        svar = self.inspelad.handle_request(request)
        if nyckel not in self.andringar:
            return svar
        andring = self.andringar[nyckel]
        if isinstance(andring, int):
            return httpx.Response(andring, request=request)
        return httpx.Response(200, content=andring(svar.content), headers=svar.headers, request=request)


def inspelning(nyckel: str) -> bytes:
    manifest = InspeladTransport(INSPELNINGAR).manifest
    return (Path(INSPELNINGAR) / manifest[nyckel]).read_bytes()


def andra_excel(innehall: bytes, andra) -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(innehall))
    andra(wb.worksheets[0])
    ut = io.BytesIO()
    wb.save(ut)
    return ut.getvalue()


def hamta(kalla, transport: httpx.BaseTransport | None = None):
    with httpx.Client(transport=transport or InspeladTransport(INSPELNINGAR)) as client:
        return kalla.hamta(client, None)


def placeringar(h, kommun: str = "Härnösand") -> dict[int, object]:
    [r] = h.rankningar
    return {p.ar: p for p in r.placeringar if p.kommun == kommun}


def delmatt(h, kommun: str = "Härnösand") -> dict[tuple[str, int], object]:
    [r] = h.rankningar
    return {(d.delmatt, d.ar): d for d in r.delmatt if d.kommun == kommun}


# --- Tolkningen ----------------------------------------------------------------------------------------------

def test_lankarna_till_excelfilerna_hittas_via_lanktexten():
    lankar = hitta_lankar(inspelning("www.foretagsklimat.se/ladda-ner/").decode("utf-8"))
    assert set(lankar) == {"ranking", "enkat", "statistik"}
    # Enkätfilens länktext har ett "ä" som två tecken (a + trema). Den hittas ändå.
    assert "enkatresultatxlsx" in lankar["enkat"]
    assert lankar["ranking"].startswith("https://www.foretagsklimat.se/ladda-ner/")


def test_foretagsklimatet_tolkas_ur_excelfilerna():
    h = hamta(Foretagsklimat())
    assert h.fel == []
    harnosand = placeringar(h)
    assert (harnosand[2026].placering, harnosand[2026].antal) == (265, 290)
    assert (harnosand[2025].placering, harnosand[2025].antal) == (283, 290)
    # Hela historiken: totalrankingen finns från 2009 i filen (issuet säger från 2012).
    assert min(harnosand) <= 2012
    assert harnosand[2026].kalla_url.startswith("https://www.foretagsklimat.se/ladda-ner/")

    omdome = delmatt(h)[(OMDOME, 2026)]
    assert round(float(omdome.varde), 2) == 3.18
    assert round(float(omdome.riksvarde), 2) == 3.53
    assert omdome.grupp == "Enkät" and omdome.enhet == "medelbetyg"
    assert omdome.placering == 236
    skatt = delmatt(h)[("Kommunalskatt", 2026)]
    assert skatt.grupp == "Statistik" and skatt.placering == 260

    # Grannkommunerna hämtas också.
    assert {p.kommun for p in h.rankningar[0].placeringar} == {
        "Härnösand", "Sundsvall", "Kramfors", "Timrå", "Sollefteå", "Örnsköldsvik"}


def test_flervalsfragor_som_inte_rankas_blir_inga_delmatt():
    h = hamta(Foretagsklimat())
    namn = {d for d, _ in delmatt(h)}
    assert not any(n.startswith("Har du under senaste året haft kontakt") for n in namn)
    assert "Lokala tillväxthinder" not in namn


def test_enkatsvar_sparas_bara_for_ar_som_svenskt_naringsliv_har_rankat():
    """Användarvillkoren: enkätsvaren för ett år får inte användas innan rankningen är publicerad."""
    def utan_2026(ws):
        rubrik = [c.value for c in ws[1]]
        ws.delete_cols(rubrik.index("2026") + 1)

    h = hamta(Foretagsklimat(), Andrad({RANKNINGSFIL: lambda b: andra_excel(b, utan_2026)}))
    assert 2026 not in placeringar(h)
    assert not [d for (_, ar) in delmatt(h) for d in [ar] if ar == 2026]
    assert (OMDOME, 2025) in delmatt(h)


def test_miljorankningen_tolkas_ur_sidorna():
    h = hamta(Miljobarometern())
    assert h.fel == []
    harnosand = placeringar(h)
    assert harnosand[2026].placering == 52
    assert harnosand[2026].antal == 290
    assert float(harnosand[2026].poang) == 16.8 and float(harnosand[2026].max_poang) == 33.5
    assert harnosand[2025].placering == 69
    assert harnosand[2009].placering == 61
    assert min(harnosand) == 2009

    d = delmatt(h)
    assert float(d[("omrade:enkät", 2026)].varde) == 10.0
    assert d[("omrade:enkät", 2026)].namn == "Enkät (max 13 poäng)"
    pfos = d[("95", 2026)]
    assert (pfos.namn, pfos.svar, float(pfos.varde)) == ("PFOS/PFAS", "Nej", 0.0)
    assert float(d[("EMC", 2026)].varde) == 0.42
    assert float(d[("KS3", 2026)].varde) == -0.72
    assert d[("KS3", 2026)].grupp == "Klimatdata"
    # Poängen per indikator finns bara för det senaste året.
    assert {ar for _, ar in d} == {2026}


def test_ett_andrat_format_ger_delvis_fel_med_begripligt_meddelande():
    def utan_faktor(ws):
        for c in ws[1]:
            if c.value == "Faktor":
                c.value = "Fråga"

    h = hamta(Foretagsklimat(), Andrad({RANKNINGSFIL: lambda b: andra_excel(b, utan_faktor)}))
    assert h.fel == ["Rankingresultat.xlsx: Rankingresultat.xlsx har ändrat format: kolumnen Faktor saknas"]

    h = hamta(Miljobarometern(), Andrad({RESULTATSIDA: lambda b: b.replace("Totalpoäng".encode(), b"Summa")}))
    assert h.fel == ["Resultat för Härnösand: Resultatsidan för Härnösand har ändrat format: placeringen eller "
                     "totalpoängen saknas"]
    # Resten hämtades: placeringarna år för år och grannkommunerna.
    assert placeringar(h)[2026].placering == 52
    assert placeringar(h, "Sundsvall")


# --- Insamlingen och API:t -----------------------------------------------------------------------------------

def rankningsapp(database_url, google, transport=None) -> TestClient:
    kallor = [Foretagsklimat(anrop_per_sekund=None), Miljobarometern(anrop_per_sekund=None)]
    return TestClient(skapa_app(database_url, google, kallor=kallor, transport=transport, anonym_lasning=True))


def kor(api: TestClient) -> dict[str, dict]:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar")
    assert svar.status_code == 200
    api.post("/api/auth/logga-ut")
    return {k["datakalla_id"]: k for k in svar.json()["kallor"]}


@pytest.fixture
def api(database_url, google) -> TestClient:
    api = rankningsapp(database_url, google)
    resultat = kor(api)
    assert resultat["foretagsklimat"]["status"] == "lyckad"
    assert resultat["miljobasta-kommun"]["status"] == "lyckad"
    return api


def test_standardkallorna_har_bada_rankningarna():
    assert {"foretagsklimat", "miljobasta-kommun"} <= {k.id for k in standardkallor()}


def test_oversikten_visar_harnosands_senaste_placering_och_avsandaren(api):
    rankningar = {r["id"]: r for r in api.get("/api/rankningar").json()}
    fk = rankningar["foretagsklimat"]
    assert fk["avsandare"] == "Svenskt Näringsliv"
    assert fk["avsandartyp"] == "Arbetsgivar- och näringslivsorganisation"
    assert fk["senaste"] == {"ar": 2026, "placering": 265, "antal": 290, "poang": None, "max_poang": None,
                             "foregaende": {"ar": 2025, "placering": 283}, "andring": -18, "metodbyte": False}
    mb = rankningar["miljobasta-kommun"]
    assert mb["avsandare"] == "Aktuell Hållbarhet"
    assert mb["senaste"]["placering"] == 52 and mb["senaste"]["poang"] == 16.8
    assert mb["senaste"]["foregaende"] == {"ar": 2025, "placering": 69}


def test_sidan_per_rankning_har_grannkommunerna_delmatten_och_kallan(api):
    r = api.get("/api/rankningar/foretagsklimat").json()
    assert [k["kommun"] for k in r["kommuner"]] == [
        "Härnösand", "Sundsvall", "Kramfors", "Timrå", "Sollefteå", "Örnsköldsvik"]
    assert r["metod_url"] == "https://www.foretagsklimat.se/om-foretagsklimat/metod-for-rankingen/"
    assert "Källan ska alltid anges" in r["villkor"] or "källan ska alltid anges" in r["villkor"]
    assert r["datakalla"]["titel"] == "Lokalt företagsklimat"
    assert r["hamtad"] and r["kallor"]

    delmatt = {d["id"]: d for d in r["delmatt"]}
    omdome = delmatt[OMDOME]
    assert omdome["ar"] == 2026
    assert round(omdome["varde"], 2) == 3.18 and round(omdome["riksvarde"], 2) == 3.53
    assert omdome["foregaende"]["ar"] == 2025 and omdome["foregaende"]["placering"] == 263
    # Statistik som avser ett tidigare år visas med sitt år.
    assert all(d["ar"] >= 2024 for d in r["delmatt"])

    m = api.get("/api/rankningar/miljobasta-kommun").json()
    assert {p["ar"]: p["placering"] for p in m["kommuner"][0]["punkter"]}[2009] == 61
    assert {d["id"] for d in m["delmatt"]} >= {"omrade:enkät", "95", "EMC", "KS1"}
    assert api.get("/api/rankningar/finns-inte").status_code == 404


def test_samma_ar_igen_ger_inga_nya_uppgifter(api):
    resultat = kor(api)
    for kalla in ("foretagsklimat", "miljobasta-kommun"):
        assert resultat[kalla]["status"] == "inga_nya"
        assert resultat[kalla]["antal_nya"] == resultat[kalla]["antal_andrade"] == 0


def test_andrade_varden_blir_en_ny_version(database_url, google, api):
    def ny_placering(ws):
        rubrik = [c.value for c in ws[1]]
        for rad in ws.iter_rows(min_row=2):
            if rad[0].value == "Härnösand" and rad[rubrik.index("Faktor")].value == "Totalranking":
                rad[rubrik.index("2026")].value = 264

    andrad = rankningsapp(database_url, google, Andrad({RANKNINGSFIL: lambda b: andra_excel(b, ny_placering)}))
    resultat = kor(andrad)
    assert resultat["foretagsklimat"]["status"] == "lyckad"
    assert resultat["foretagsklimat"]["antal_andrade"] == 1
    assert resultat["foretagsklimat"]["antal_nya"] == 0
    assert api.get("/api/rankningar/foretagsklimat").json()["senaste"]["placering"] == 264

    import psycopg
    with psycopg.connect(database_url) as conn:
        versioner = conn.execute(
            "SELECT placering, version FROM rankning_placering WHERE rankning_id = 'foretagsklimat' "
            "AND kommun = 'Härnösand' AND ar = 2026 ORDER BY version").fetchall()
    assert versioner == [(265, 1), (264, 2)]


def test_en_fil_som_inte_gar_att_hamta_ger_delvis_fel_men_ingen_ny_version(database_url, google, api):
    trasig = rankningsapp(database_url, google, Andrad({ENKATFIL: 500, RESULTATSIDA: 503}))
    resultat = kor(trasig)
    for kalla in ("foretagsklimat", "miljobasta-kommun"):
        assert resultat[kalla]["status"] == "delvis_fel"
        assert resultat[kalla]["antal_andrade"] == 0
    assert "Enkätresultat.xlsx" in resultat["foretagsklimat"]["fel"]
    assert "Resultat för Härnösand" in resultat["miljobasta-kommun"]["fel"]
    # Värdena från förra hämtningen finns kvar.
    r = api.get("/api/rankningar/foretagsklimat").json()
    assert round({d["id"]: d for d in r["delmatt"]}[OMDOME]["varde"], 2) == 3.18
    assert api.get("/api/rankningar/miljobasta-kommun").json()["senaste"]["poang"] == 16.8


def test_metodbyten_registreras_av_redaktionen_och_visas(api):
    svar = api.post("/api/rankningar/foretagsklimat/metodbyten", json={"ar": 2012, "beskrivning": "Ny enkät"})
    assert svar.status_code in (401, 403)

    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/rankningar/foretagsklimat/metodbyten", json={"ar": 2012}).status_code == 422
    assert api.post("/api/rankningar/finns-inte/metodbyten",
                    json={"ar": 2012, "beskrivning": "x"}).status_code == 404
    svar = api.post("/api/rankningar/foretagsklimat/metodbyten",
                    json={"ar": 2012, "beskrivning": "Enkäten fick nya frågor"})
    assert svar.status_code == 201
    assert svar.json() == [{"ar": 2012, "beskrivning": "Enkäten fick nya frågor"}]
    api.post("/api/auth/logga-ut")

    assert api.get("/api/rankningar/foretagsklimat").json()["metodbyten"] == [
        {"ar": 2012, "beskrivning": "Enkäten fick nya frågor"}]

    # Ett metodbyte före föregående år påverkar inte jämförelsen mellan de två senaste åren.
    assert api.get("/api/rankningar/foretagsklimat").json()["senaste"]["metodbyte"] is False

    assert api.delete("/api/rankningar/foretagsklimat/metodbyten/2012").status_code in (401, 403)
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.delete("/api/rankningar/foretagsklimat/metodbyten/2012").json() == []
    assert api.delete("/api/rankningar/foretagsklimat/metodbyten/2012").status_code == 404


def test_ett_metodbyte_mellan_de_tva_senaste_aren_markeras_pa_sammanfattningen(api):
    # #177: placeringarna 2025 och 2026 går inte att jämföra om metoden byttes 2026.
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post("/api/rankningar/foretagsklimat/metodbyten",
                    json={"ar": 2026, "beskrivning": "Ny enkät"}).status_code == 201
    assert api.get("/api/rankningar/foretagsklimat").json()["senaste"]["metodbyte"] is True
    rankningar = {r["id"]: r for r in api.get("/api/rankningar").json()}
    assert rankningar["foretagsklimat"]["senaste"]["metodbyte"] is True
    assert rankningar["miljobasta-kommun"]["senaste"]["metodbyte"] is False
    api.delete("/api/rankningar/foretagsklimat/metodbyten/2026")
    assert api.get("/api/rankningar/foretagsklimat").json()["senaste"]["metodbyte"] is False
