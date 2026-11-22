"""Sammanträdestider ur protokollens beslut när webbsidan saknar plan för året (#99).

Databasen fylls direkt: ett sammanträde i fullmäktige med beslutet om sammanträdestiderna, som
KF 2026-09-28 § 130. Dagens datum låses till 2026-11-20.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from icalendar import Calendar

from app import db, kalender, rattelser, sammantradesplan
from app.sources.sammantradesplaner import Planrad, Sammantradesplan

IDAG = date(2026, 11, 20)
NU = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
SEPT = "Kommunfullmäktige beslutar\natt kommunfullmäktige sammanträder kl. 13.15 följande datum: "


@pytest.fixture(autouse=True)
def lasta_datum(monkeypatch):
    monkeypatch.setenv("KOMMUNKOLLEN_IDAG", IDAG.isoformat())


@pytest.fixture
def conn(database_url: str):
    db.migrate(database_url)
    with db.connect(database_url) as c:
        yield c


def beslut(conn, datum: date, paragraf: int, rubrik: str, text: str, organ: str = "KF") -> int:
    sid = conn.execute(
        "INSERT INTO sammantrade (organ, nyckel, datum) VALUES (%s, %s, %s) RETURNING id", (organ, str(datum), datum)
    ).fetchone()["id"]
    conn.execute("INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, beslut) VALUES (%s, 1, %s, %s, %s)",
                 (sid, paragraf, rubrik, text))
    return sid


def kf(conn, ar: int) -> list[dict]:
    return [h for h in kalender.handelser(conn, "KF", fran=date(ar, 1, 1)) if h["datum"].startswith(str(ar))]


def webbplan(organ: str, ar: int, *datum: date) -> Sammantradesplan:
    return Sammantradesplan(organ, "https://harnosand.se/plan", [ar],
                            [Planrad(organ, ar, d.month, d, "13:15", "planerat", None, f"{d}") for d in datum])


def test_beslutet_blir_planerade_sammantraden_med_markering(conn):
    sid = beslut(conn, date(2026, 9, 28), 130, "Svar på återremiss gällande sammanträdestider 2027",
                 SEPT + "22 februari, 22 mars och 26 april.")
    assert sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU)["nya"] == 3

    h = kf(conn, 2027)
    assert [(x["datum"], x["starttid"], x["status"]) for x in h] == [
        ("2027-02-22", "13:15", "planerat"), ("2027-03-22", "13:15", "planerat"), ("2027-04-26", "13:15", "planerat")]
    assert h[0]["beslut"] == {"sammantrade_id": sid, "paragraf": 130, "datum": "2026-09-28",
                              "organ": {"id": "KF", "namn": "Kommunfullmäktige"}}
    assert h[0]["plats_antagen"] is not None

    cal = Calendar.from_ical(kalender.ics(h, "Kommunfullmäktige", "https://kommunkollen.test"))
    [forsta, *_] = cal.walk("VEVENT")
    assert (f"Enligt beslut i protokollet (kommunfullmäktige 2026-09-28 § 130): "
            f"https://kommunkollen.test/politik/sammantraden/{sid}/paragraf/130") in str(forsta["DESCRIPTION"])

    # Sidan Planer: källan per sammanträde, och året har ingen plan på webbsidan än.
    [plan] = [p for p in sammantradesplan.lista(conn) if p["ar"] == 2027]
    assert plan["bara_beslut"] and {s["kalla"] for s in plan["sammantraden"]} == {"beslut"}
    assert plan["sammantraden"][0]["beslut"] == {"sammantrade_id": sid, "paragraf": 130, "datum": "2026-09-28"}

    # Samma beslut igen ändrar inget.
    assert sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU) == {"nya": 0, "andrade": 0, "oforandrade": 3}


def test_tabellen_tar_over_med_samma_uid(conn):
    beslut(conn, date(2026, 9, 28), 130, "Sammanträdestider 2027", SEPT + "22 februari och 22 mars.")
    sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU)
    fore = {x["datum"]: x for x in kf(conn, 2027)}

    # Webbsidan publicerar 2027: 22 februari som beslutat, 29 mars i stället för 22 mars.
    sammantradesplan.lagra(conn, webbplan("KF", 2027, date(2027, 2, 22), date(2027, 3, 29)), None, NU)
    efter = {x["datum"]: x for x in kf(conn, 2027)}
    assert efter["2027-02-22"]["uid"] == fore["2027-02-22"]["uid"]
    assert efter["2027-02-22"]["sekvens"] > fore["2027-02-22"]["sekvens"]
    assert efter["2027-02-22"]["beslut"] is None and efter["2027-02-22"]["plan_url"] == "https://harnosand.se/plan"
    assert efter["2027-03-22"]["status"] == "borttaget"
    assert efter["2027-03-29"]["status"] == "planerat"
    [plan] = [p for p in sammantradesplan.lista(conn) if p["ar"] == 2027]
    assert not plan["bara_beslut"]
    v = next(s for s in plan["sammantraden"] if s["datum"] == "2027-02-22")["versioner"]
    assert [x["kalla"] for x in v] == ["beslut", "webbsidan"]

    # Därefter gäller tabellen: besluten lagras inte längre för året.
    assert sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU) == {"nya": 0, "andrade": 0, "oforandrade": 0}


def test_ar_med_plan_pa_webbsidan_och_tidigare_ar_paverkas_inte(conn):
    sammantradesplan.lagra(conn, webbplan("KF", 2026, date(2026, 12, 14)), None, NU)
    beslut(conn, date(2025, 9, 29), 120, "Sammanträdestider 2026", SEPT + "23 november och 14 december.")
    beslut(conn, date(2024, 9, 30), 110, "Sammanträdestider 2025", SEPT + "24 november och 15 december.")
    assert sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU) == {"nya": 0, "andrade": 0, "oforandrade": 0}
    assert [x["datum"] for x in kf(conn, 2026)] == ["2026-12-14"]
    # 2025 är ett tidigare år: bara själva sammanträdet med beslutet finns.
    assert [x["datum"] for x in kf(conn, 2025)] == ["2025-09-29"]


def test_senare_beslut_flyttar_och_staller_in(conn):
    beslut(conn, date(2026, 9, 28), 130, "Sammanträdestider 2027", SEPT + "22 februari, 22 mars och 26 april.")
    sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU)
    fore = {x["datum"]: x for x in kf(conn, 2027)}

    beslut(conn, date(2026, 11, 23), 150, "Ändrade sammanträdesdagar 2027",
           "Kommunfullmäktige beslutar\natt sammanträdet den 22 mars 2027 flyttas till den 29 mars 2027"
           "\natt sammanträdet den 26 april 2027 ställs in.")
    sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU)
    efter = {x["datum"]: x for x in kf(conn, 2027)}
    assert set(efter) == {"2027-02-22", "2027-03-29", "2027-04-26"}
    # Det flyttade sammanträdet är samma händelse, med nytt datum och en ny version.
    assert efter["2027-03-29"]["uid"] == fore["2027-03-22"]["uid"]
    assert efter["2027-03-29"]["sekvens"] > fore["2027-03-22"]["sekvens"]
    assert efter["2027-04-26"]["status"] == "installt"
    assert efter["2027-03-29"]["beslut"]["paragraf"] == 150


def test_ett_rattat_beslut_andrar_planen(conn):
    sid = beslut(conn, date(2026, 9, 28), 130, "Sammanträdestider 2027", SEPT + "22 februari och 22 mars.")
    sammantradesplan.lagra_beslut(conn, IDAG, hamtad=NU)
    r = rattelser.skapa(conn, {"objekt": "behandling", "sammantrade_id": sid, "paragraf": 130, "falt": "beslut",
                               "nytt": SEPT + "22 februari, 22 mars och 26 april.",
                               "motivering": "Ett datum föll bort i tolkningen", "felet_i": "inlasningen"},
                              "redaktor@test")
    rattelser.granska(conn, r["id"], "utgivare@test")
    rattelser.publicera(conn, r["id"], "utgivare@test")
    assert [x["datum"] for x in kf(conn, 2027)] == ["2027-02-22", "2027-03-22", "2027-04-26"]
