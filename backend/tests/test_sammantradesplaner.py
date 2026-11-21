"""Sammanträdesplanerna som datakälla och planerade sammanträden kopplade till protokollen (#68).

Tolkningen testas mot de inspelade organsidorna på harnosand.se (kontrollerade 2026-11-17).
Facit: kommunfullmäktige 2026 har 10 rader, 2026-10-15 är inställt, 2026-10-26 har starttid 11.00
och övriga 13.15. Kommunstyrelsen har 2026 och 2027 med 08.15, och 2026-09-08 är inställt enligt
"(8/9 ställs in)". Socialnämnden har juni 2026 inställd.
"""

from __future__ import annotations

from datetime import date

import httpx
import psycopg
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient

from app import db, statistik
from app.recorded import InspeladTransport
from app.sammantradesplan import tolka_beslut
from app.sources.harnosand import Protokollkalla
from app.sources.sammantradesplaner import Sammantradesplaner, tolka_sida, tolka_tabell

KALLA = "harnosand-sammantradesplaner"
SIDOR = {
    "KF": "kommunfullmaktige",
    "KS": "kommunstyrelse",
    "SAM": "namnder_samhallsnamnden",
    "SOC": "namnder_socialnamnden",
    "SKOL": "namnder_skolnamnden",
}


def sida(organ: str) -> str:
    fil = INSPELNINGAR / "harnosand" / f"kommun_styrning_politik_och_demokrati_{SIDOR[organ]}.html"
    return fil.read_text(encoding="utf-8")


def plan(organ: str):
    return tolka_sida(organ, "https://harnosand.se/x.html", sida(organ))


def test_kommunfullmaktiges_plan_med_installt_och_andrad_tid():
    p = plan("KF")
    assert p.ar == [2026] and p.fel == []
    assert len(p.rader) == 10
    rader = {r.nyckel: r for r in p.rader}
    assert (rader["2026-10-15"].status, rader["2026-10-15"].starttid) == ("installt", None)
    assert (rader["2026-10-26"].status, rader["2026-10-26"].starttid) == ("planerat", "11:00")
    ovriga = [r for n, r in rader.items() if n not in ("2026-10-15", "2026-10-26")]
    assert {(r.status, r.starttid) for r in ovriga} == {("planerat", "13:15")}
    assert rader["2026-10-26"].kalltext == "Oktober | 26 | OBS tiden: 11.00"


def test_kommunstyrelsens_plan_for_tva_ar_med_hanvisning_till_installt():
    p = plan("KS")
    assert p.ar == [2026, 2027] and p.fel == []
    assert {r.starttid for r in p.rader} == {"08:15"}
    rader = {r.nyckel: r for r in p.rader}
    assert rader["2026-09-08"].status == "installt"
    assert rader["2026-09-15"].status == rader["2026-09-29"].status == "planerat"
    assert {"2026-05-05", "2026-05-26", "2027-04-06", "2027-04-27"} <= set(rader)
    assert len([r for r in p.rader if r.ar == 2027]) == 9


def test_socialnamndens_installda_manad_utan_datum():
    p = plan("SOC")
    [juni] = [r for r in p.rader if r.manad == 6]
    assert (juni.datum, juni.status, juni.nyckel) == (None, "installt", "2026-06")


def test_text_som_inte_kanns_igen_blir_anmarkning_och_fel():
    tabell = """<table><tr><th>Månad</th><th>Datum</th><th>Tid</th></tr>
      <tr><td>Mars</td><td>12</td><td>Lokal meddelas senare</td></tr>
      <tr><td>April</td><td>Ny dag kommer</td><td>-</td></tr></table>"""
    rader, fel = tolka_tabell("SAM", 2026, tabell)
    assert [(r.nyckel, r.starttid, r.anmarkning) for r in rader] == [
        ("2026-03-12", None, "Lokal meddelas senare"), ("2026-04", None, "Ny dag kommer")]
    assert len(fel) == 2 and "Samhällsnämnden 2026, mars" in fel[0]


def test_besluten_om_sammantradesplanerna_tolkas():
    # Ur kommunstyrelsens protokoll 2026-05-26 § 93 och § 92, och socialnämndens 2026-05-28 § 72.
    ks = ("Kommunstyrelsen föreslår kommunfullmäktige besluta\natt kommunfullmäktige sammanträder 13.15 följande "
          "dagar: 22 februari, 26 april. Vidare, kommunstyrelsens beslutar\natt kommunstyrelsen sammanträder 08.15 "
          "följande datum: 2 februari, 6 april och 23 november.\natt kommunstyrelsens arbetsutskott sammanträder "
          "kl. 08.15 följande datum: 19 januari.")
    # Bara organets egna sammanträden: inte förslaget till fullmäktige och inte arbetsutskottet.
    assert tolka_beslut(ks, "KS", 2027) == [
        ("plan", ("08:15", [date(2027, 2, 2), date(2027, 4, 6), date(2027, 11, 23)]))]
    flytt = "Kommunstyrelsen beslutar\natt kommunstyrelsens sammanträde 8 september 2026 senareläggs till 15 september 2026"
    assert tolka_beslut(flytt, "KS", None) == [("flyttat", (date(2026, 9, 8), date(2026, 9, 15)))]
    soc = "Socialnämnden beslutar\natt sammanträdet den 17 juni ställs in, samt att nämnden kallar till en utbildningsdag."
    assert tolka_beslut(soc, "SOC", 2026) == [("installt", date(2026, 6, 17))]


# Insamling och lagring


def kf_och_planer(protokoll_forst: bool = True):
    protokoll = Protokollkalla("KF", arkiv_fran=None, anrop_per_sekund=None)
    planer = Sammantradesplaner(anrop_per_sekund=None)
    return [protokoll, planer] if protokoll_forst else [planer, protokoll]


def kor(api: TestClient, kalla: str | None = None) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar", params={"kalla": kalla} if kalla else None)
    assert svar.status_code == 200, svar.text
    return svar.json()


def planer(api: TestClient) -> dict[tuple[str, int], dict]:
    svar = api.get("/api/sammantradesplaner")
    assert svar.status_code == 200, svar.text
    return {(p["organ"]["id"], p["ar"]): p for p in svar.json()}


def rad(p: dict, nyckel: str) -> dict:
    [s] = [s for s in p["sammantraden"] if s["nyckel"] == nyckel]
    return s


class MedAndradSida(httpx.BaseTransport):
    """Inspelade svar, men en organsida får ersatt text."""

    def __init__(self, organ: str, byten: list[tuple[str, str]]) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.organ, self.byten = organ, byten

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(SIDOR[self.organ].split("_")[-1] + ".html") and not request.url.query:
            text = sida(self.organ)
            for gammal, ny in self.byten:
                assert gammal in text, gammal
                text = text.replace(gammal, ny)
            return httpx.Response(200, text=text, headers={"content-type": "text/html; charset=utf-8"},
                                  request=request)
        return self.inspelad.handle_request(request)


def test_datakallan_laser_alla_fem_organen(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)]))
    [res] = kor(api)["kallor"]
    assert (res["datakalla_id"], res["status"]) == (KALLA, "lyckad")
    assert res["antal_nya"] == 10 + 19 + 10 + 11 + 9

    p = planer(api)
    assert set(p) == {("KF", 2026), ("KS", 2026), ("KS", 2027), ("SAM", 2026), ("SOC", 2026), ("SKOL", 2026)}
    assert rad(p[("KF", 2026)], "2026-10-15")["status"] == "installt"
    assert rad(p[("SOC", 2026)], "2026-06")["datum"] is None
    assert p[("KF", 2026)]["url"].endswith("/kommunfullmaktige.html")

    # Ingen ändring: allt oförändrat.
    [res] = kor(api)["kallor"]
    assert (res["status"], res["antal_oforandrade"]) == ("inga_nya", 59)

    # Planerade sammanträden är inte hållna sammanträden med protokoll, och räknas inte i statistiken.
    assert api.get("/api/sammantraden", params={"organ": "KF"}).json() == []
    with db.connect(database_url) as conn:
        assert statistik.tillgangliga_ar(conn) == []


def test_planen_ar_bara_for_redaktionen(api):
    assert api.get("/api/sammantradesplaner").status_code == 401
    assert api.post("/api/auth/test/lasare").status_code == 200
    assert api.get("/api/sammantradesplaner").status_code == 403


def test_andringar_i_planen_blir_nya_versioner(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)]))
    kor(api)
    fore = rad(planer(api)[("KF", 2026)], "2026-11-23")

    # Kommunen ändrar tiden 23 november, tar bort 14 december och ställer in 28 september.
    andrad = MedAndradSida("KF", [
        ("<p>November</p></td><td>23</td><td>13.15</td>", "<p>November</p></td><td>23</td><td>OBS tiden: 09.00</td>"),
        ("<tr><td><p>December</p></td><td>14</td><td>13.15</td></tr>", ""),
        ("<p>September</p></td><td>28</td><td>13.15</td>", "<p>September</p></td><td>28</td><td>Inställt</td>"),
    ])
    api2 = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)],
                                transport=andrad))
    [res] = kor(api2)["kallor"]
    assert (res["status"], res["antal_andrade"]) == ("lyckad", 3)

    p = planer(api2)[("KF", 2026)]
    efter = rad(p, "2026-11-23")
    assert efter["id"] == fore["id"]  # samma sammanträde
    assert (efter["starttid"], efter["version"]) == ("09:00", 2)
    assert [(v["version"], v["starttid"]) for v in efter["versioner"]] == [(1, "13:15"), (2, "09:00")]
    assert efter["versioner"][1]["kalltext"] == "November | 23 | OBS tiden: 09.00"
    # Borttaget ur planen, men finns kvar.
    assert (rad(p, "2026-12-14")["status"], rad(p, "2026-12-14")["version"]) == ("borttaget", 2)
    assert rad(p, "2026-09-28")["status"] == "installt"


def test_en_installd_manad_utan_datum_galler_manadens_sammantrade(database_url, google):
    # Först står ett datum i juni, sedan bara "Inställd" (så som socialnämnden skriver).
    forst = MedAndradSida("SOC", [("<td><p>Inställd</p></td><td><p><br></p></td>", "<td><p>17</p></td><td><p>08.15</p></td>")])
    api = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)],
                               transport=forst))
    kor(api)
    fore = rad(planer(api)[("SOC", 2026)], "2026-06-17")
    assert fore["status"] == "planerat"

    api2 = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)]))
    kor(api2)
    p = planer(api2)[("SOC", 2026)]
    efter = rad(p, "2026-06-17")
    assert (efter["id"], efter["status"], efter["starttid"], efter["version"]) == (fore["id"], "installt", "08:15", 2)
    assert not [s for s in p["sammantraden"] if s["nyckel"] == "2026-06"]


@pytest.mark.parametrize("protokoll_forst", [True, False])
def test_protokollen_kopplas_till_de_planerade_sammantradena(database_url, google, protokoll_forst):
    api = TestClient(skapa_app(database_url, google, kallor=kf_och_planer(protokoll_forst)))
    kor(api)
    p = planer(api)[("KF", 2026)]
    hallna = api.get("/api/sammantraden", params={"organ": "KF"}).json()
    id_for = {(s["datum"], s["starttid"]): s["id"] for s in hallna}

    # Protokollet kopplas till det planerade sammanträdet i stället för att skapa ett nytt.
    assert rad(p, "2026-09-28")["id"] == id_for[("2026-09-28", "13:15")]
    assert rad(p, "2026-09-28")["protokoll"] is True
    # Fullmäktige hade två sammanträden 2026-10-26. Planen (11.00) gäller det som började 11.10,
    # det andra (13.15) är ett eget sammanträde.
    assert rad(p, "2026-10-26")["id"] == id_for[("2026-10-26", "11:10")]
    assert id_for[("2026-10-26", "13:15")] not in {s["id"] for s in p["sammantraden"]}
    # Kommande sammanträden har inget protokoll än.
    assert rad(p, "2026-12-14")["protokoll"] is False
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM sammantrade WHERE organ = 'KF'").fetchone()[0] == \
            len(p["sammantraden"]) + 1


def test_skillnader_mot_beslutet_i_protokollet_visas_for_redaktionen(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=kf_och_planer()))
    kor(api)
    with psycopg.connect(database_url) as conn:
        # Fullmäktiges beslut 2025-05-26 § 81 om sammanträdestider 2026 (protokollet ingår inte i
        # inspelningarna, så behandlingen läggs in här på ett av de inlästa sammanträdena).
        [s_id] = conn.execute("SELECT id FROM sammantrade WHERE organ = 'KF' AND datum = '2026-02-23'").fetchone()
        conn.execute(
            "INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, beslut) VALUES (%s, 999, 999, %s, %s)",
            (s_id, "Sammanträdestider 2026",
             "Kommunfullmäktige beslutar\natt kommunfullmäktige sammanträder kl.13.15 följande datum: 23 februari "
             "23 mars 27 april 25 maj 15 juni 28 september 26 oktober 23 november 14 december."),
        )
    p = planer(api)[("KF", 2026)]
    assert [(b["paragraf"], b["rubrik"]) for b in p["beslut"]] == [(999, "Sammanträdestider 2026")]
    # 15 oktober är inställt och står inte i beslutet. 26 oktober började 11.00 i stället för 13.15.
    assert p["skillnader"] == [{"datum": "2026-10-26", "typ": "tid", "sidan": "11:00", "beslutet": "13:15"}]
    # Utan beslut går planen inte att jämföra.
    assert planer(api)[("KS", 2027)]["skillnader"] is None
