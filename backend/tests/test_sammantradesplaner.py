"""Sammanträdesplanerna som datakälla och planerade sammanträden kopplade till protokollen (#68).

Tolkningen testas mot de inspelade organsidorna på harnosand.se (kontrollerade 2026-11-17).
Facit: kommunfullmäktige 2026 har 10 rader, 2026-10-15 är inställt, 2026-10-26 har starttid 11.00
och övriga 13.15. Kommunstyrelsen har 2026 och 2027 med 08.15, och 2026-09-08 är inställt enligt
"(8/9 ställs in)". Socialnämnden har juni 2026 inställd.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import psycopg
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient

from app import db, sammantradesplan, sla_ihop_planer, statistik
from app.recorded import InspeladTransport
from app.sammantradesplan import narmast, tolka_beslut
from app.sources.harnosand import Protokollkalla
from app.sources.sammantradesplaner import Planrad, Sammantradesplan, Sammantradesplaner, tolka_sida, tolka_tabell

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
    # 59 planerade sammanträden, och kallelserna och webbsändningarna (#68, del 3).
    assert res["antal_nya"] > 10 + 19 + 10 + 11 + 9
    nya = res["antal_nya"]

    p = planer(api)
    assert sum(len(x["sammantraden"]) for x in p.values()) == 10 + 19 + 10 + 11 + 9
    assert set(p) == {("KF", 2026), ("KS", 2026), ("KS", 2027), ("SAM", 2026), ("SOC", 2026), ("SKOL", 2026)}
    assert rad(p[("KF", 2026)], "2026-10-15")["status"] == "installt"
    assert rad(p[("SOC", 2026)], "2026-06")["datum"] is None
    assert p[("KF", 2026)]["url"].endswith("/kommunfullmaktige.html")

    # Ingen ändring: allt oförändrat.
    [res] = kor(api)["kallor"]
    assert (res["status"], res["antal_oforandrade"]) == ("inga_nya", nya)

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
    # 2027 saknar plan på webbsidan och kommer från beslutet 2026-09-28 § 130 (#99).
    p27 = planer(api)[("KF", 2027)]
    assert p27["bara_beslut"] and len(p27["sammantraden"]) == 9
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM sammantrade WHERE organ = 'KF'").fetchone()[0] == \
            len(p["sammantraden"]) + len(p27["sammantraden"]) + 1


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


# Koppling på datum när den är entydig (#107)


def test_en_enda_kandidat_kopplas_oavsett_tid():
    assert narmast("11:05", [{"id": 1, "starttid": "08:15"}]) == {"id": 1, "starttid": "08:15"}
    # Finns fler sammanträden den dagen på andra sidan avgör tiden.
    assert narmast("11:05", [{"id": 1, "starttid": "08:15"}], entydig=False) is None


def test_flera_kandidater_samma_dag_skiljs_at_med_tiden():
    kf = [{"id": 1, "starttid": "11:00"}, {"id": 2, "starttid": "13:15"}]
    assert narmast("11:10", kf)["id"] == 1
    assert narmast("13:20", kf)["id"] == 2
    # Ingen ligger inom en timme: ingen koppling.
    assert narmast("16:30", kf) is None


def skol_och_plan(protokoll_forst: bool):
    protokoll = Protokollkalla("SKOL", arkiv_fran=None, anrop_per_sekund=None)
    planer = Sammantradesplaner(anrop_per_sekund=None)
    return [protokoll, planer] if protokoll_forst else [planer, protokoll]


@pytest.mark.parametrize("protokoll_forst", [True, False])
def test_ett_mote_som_borjar_senare_an_planerat_kopplas_till_planen(database_url, google, protokoll_forst):
    # Skolnämnden 2026-10-01: planerat 08.15, protokollet anger "kl 11:05 - 11:16".
    api = TestClient(skapa_app(database_url, google, kallor=skol_och_plan(protokoll_forst)))
    kor(api)
    s = rad(planer(api)[("SKOL", 2026)], "2026-10-01")
    assert s["protokoll"] is True
    assert (s["starttid"], [v["starttid"] for v in s["versioner"]]) == ("08:15", ["08:15"])
    hallna = {x["datum"]: x for x in api.get("/api/sammantraden", params={"organ": "SKOL"}).json()}
    assert (hallna["2026-10-01"]["id"], hallna["2026-10-01"]["starttid"]) == (s["id"], "11:05")
    # Kalendern visar ett sammanträde, hållet och med protokollets tid.
    dagens = [h for h in api.get("/api/kalender", params={"organ": "SKOL"}).json()["handelser"]
              if h["datum"] == "2026-10-01"]
    assert [(h["id"], h["starttid"], h["status"], h["protokoll"]) for h in dagens] == [
        (s["id"], "11:05", "hallet", True)]
    with psycopg.connect(database_url) as conn:
        assert conn.execute(DUBBLETTER).fetchall() == []


DUBBLETTER = """
SELECT p.organ, p.plan_datum FROM sammantrade p
JOIN sammantrade s ON s.organ = p.organ AND s.datum = p.plan_datum
                  AND s.dokument_id IS NOT NULL AND s.plan_nyckel IS NULL
WHERE p.dokument_id IS NULL
"""


def test_befintliga_dubbletter_slas_ihop(database_url, google, capsys, monkeypatch):
    api = TestClient(skapa_app(database_url, google, kallor=skol_och_plan(True)))
    kor(api)
    protokollets = rad(planer(api)[("SKOL", 2026)], "2026-10-01")["id"]
    # Så som det blev före #107: planen på ett eget sammanträde utan protokoll.
    with db.connect(database_url) as conn:
        planerat = conn.execute(
            "INSERT INTO sammantrade (organ, nyckel, datum) VALUES ('SKOL', 'plan:2026-10-01', '2026-10-01') RETURNING id"
        ).fetchone()["id"]
        sammantradesplan.flytta_plan(conn, protokollets, planerat)
        assert len(conn.execute(DUBBLETTER).fetchall()) == 1

    monkeypatch.setenv("DATABASE_URL", database_url)
    sla_ihop_planer.main([])
    assert "1 planerade sammanträden kan slås ihop. Inget ändrades" in capsys.readouterr().out
    with db.connect(database_url) as conn:
        assert len(conn.execute(DUBBLETTER).fetchall()) == 1

    sla_ihop_planer.main(["--utfor"])
    ut = capsys.readouterr().out
    assert f"SKOL 2026-10-01: planerat {planerat} (08:15) → protokollets sammanträde {protokollets} (11:05)" in ut
    with db.connect(database_url) as conn:
        assert conn.execute(DUBBLETTER).fetchall() == []
        assert conn.execute("SELECT 1 FROM sammantrade WHERE id = %s", (planerat,)).fetchone() is None
    s = rad(planer(api)[("SKOL", 2026)], "2026-10-01")
    assert (s["id"], s["protokoll"], len(s["versioner"])) == (protokollets, True, 1)
    dagens = [h for h in api.get("/api/kalender", params={"organ": "SKOL"}).json()["handelser"]
              if h["datum"] == "2026-10-01"]
    assert [(h["id"], h["starttid"]) for h in dagens] == [(protokollets, "11:05")]


def _protokoll(conn, organ: str, datum: str, starttid: str) -> int:
    """Ett protokoll utan innehåll, för att pröva kopplingen direkt i databasen."""
    conn.execute("INSERT INTO datakalla (id, titel, url) VALUES ('test', 'Test', 'https://example.test') "
                 "ON CONFLICT (id) DO NOTHING")
    k = conn.execute("INSERT INTO insamlingskorning (utlosare, status) VALUES ('manuell', 'lyckad') RETURNING id").fetchone()
    d = conn.execute(
        """
        INSERT INTO dokument (datakalla_id, url, version, filnamn, typ, organ, sha256, storlek, innehall, hamtad,
                              korning_id)
        VALUES ('test', %s, 1, 'p.pdf', 'protokoll', %s, '', 0, '', now(), %s) RETURNING id
        """,
        (f"https://example.test/{organ}/{datum}/{starttid}", organ, k["id"]),
    ).fetchone()
    return conn.execute(
        """
        INSERT INTO sammantrade (organ, nyckel, datum, starttid, dokument_id, tolkning, tolkad)
        VALUES (%s, %s, %s, %s, %s, 'tolkad', now()) RETURNING id
        """,
        (organ, f"{datum} {starttid}", datum, starttid, d["id"]),
    ).fetchone()["id"]


def test_ett_protokoll_som_passar_planen_battre_tar_over_den(database_url):
    # En plan kl. 11.00. Protokollet från 13.15 läses först och är dagens enda, så planen kopplas dit.
    # Sedan kommer protokollet från 11.10, som är det planerade sammanträdet.
    db.migrate(database_url)
    with db.connect(database_url) as conn:
        senare = _protokoll(conn, "KF", "2026-10-26", "13:15")
        plan = Sammantradesplan("KF", "https://example.test/kf", [2026],
                                [Planrad("KF", 2026, 10, date(2026, 10, 26), "11:00", "planerat")])
        sammantradesplan.lagra(conn, plan, None, datetime.now(timezone.utc))
        assert conn.execute("SELECT plan_nyckel FROM sammantrade WHERE id = %s", (senare,)).fetchone()["plan_nyckel"]
        # Ett nytt protokoll samma dag kopplas inte på datumet, eftersom dagen redan har ett protokoll.
        assert sammantradesplan.planerat_for_protokoll(conn, "KF", date(2026, 10, 26), "11:10") is None
        tidigare = _protokoll(conn, "KF", "2026-10-26", "11:10")
        assert sammantradesplan.koppla_om(conn, tidigare) == senare
        rader = {r["id"]: r for r in conn.execute(
            "SELECT id, plan_nyckel, plan_starttid FROM sammantrade WHERE organ = 'KF'")}
        assert (rader[tidigare]["plan_nyckel"], rader[tidigare]["plan_starttid"]) == ("2026-10-26", "11:00")
        assert rader[senare]["plan_nyckel"] is None
        assert [v["sammantrade_id"] for v in conn.execute("SELECT sammantrade_id FROM planversion")] == [tidigare]


def test_en_plan_som_lases_efter_protokollet_kopplas_aven_nar_tiden_skiljer(database_url):
    db.migrate(database_url)
    with db.connect(database_url) as conn:
        protokollet = _protokoll(conn, "SOC", "2026-09-24", "13:30")
        plan = Sammantradesplan("SOC", "https://example.test/soc", [2026],
                                [Planrad("SOC", 2026, 9, date(2026, 9, 24), "08:15", "planerat")])
        assert sammantradesplan.lagra(conn, plan, None, datetime.now(timezone.utc))["nya"] == 1
        assert conn.execute("SELECT count(*) AS n FROM sammantrade WHERE organ = 'SOC'").fetchone()["n"] == 1
        r = conn.execute("SELECT id, plan_starttid, starttid FROM sammantrade WHERE organ = 'SOC'").fetchone()
        assert (r["id"], r["plan_starttid"], r["starttid"]) == (protokollet, "08:15", "13:30")


def test_ett_protokoll_som_lases_efter_planen_kopplas_aven_nar_tiden_skiljer(database_url):
    db.migrate(database_url)
    with db.connect(database_url) as conn:
        plan = Sammantradesplan("SOC", "https://example.test/soc", [2026],
                                [Planrad("SOC", 2026, 5, date(2026, 5, 28), "08:15", "planerat")])
        sammantradesplan.lagra(conn, plan, None, datetime.now(timezone.utc))
        planerat = conn.execute("SELECT id FROM sammantrade WHERE organ = 'SOC'").fetchone()["id"]
        assert sammantradesplan.planerat_for_protokoll(conn, "SOC", date(2026, 5, 28), "10:00") == planerat
