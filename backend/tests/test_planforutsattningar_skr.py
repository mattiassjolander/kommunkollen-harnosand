"""Planförutsättningarna jämfört med SKR:s skatteunderlagsprognoser (#62).

Söm 1: planförutsättningarna för 2027 läses in och publiceras som i test_budgetforslag. Prognoserna läggs
direkt i tabellen med summan för 2027 ur cirkulär 26:28 (2 222 069 tkr) och ett påhittat tidigare cirkulär,
så att jämförelsen inte beror på omräkningen med LibreOffice, som testas i test_skatteunderlag.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from psycopg.types.json import Jsonb
from test_budgetforslag import api, las_in, logga_in, publicera_alla  # noqa: F401  (api är en fixtur)

from app import db, skatteunderlag

# Planförutsättningarna 2027: skatteintäkter 1 483 och generella bidrag och utjämning 734 mnkr.
PLAN_2027 = 2217.0


def lagg_in_prognos(database_url: str, cirkular: str, publicerad: date, tkr: dict[str, int]) -> None:
    with db.connect(database_url) as conn:
        korning = conn.execute("INSERT INTO insamlingskorning (utlosare, status) VALUES ('manuell', 'lyckad') "
                               "RETURNING id").fetchone()["id"]
        ar = sorted(int(a) for a in tkr)
        rader = [{"id": "summa_intakter", "etikett": "Summa intäkter", "tkr": {a: v - 50_000 for a, v in tkr.items()}},
                 {"id": "summa_inkl", "etikett": "Summa intäkter (inkl avräkning och fastighetsavgift)", "tkr": tkr}]
        nr = cirkular.replace(":", "0")
        conn.execute(
            "INSERT INTO skatteunderlagsprognos (cirkular, kommun, version, publicerad, url, filnamn, sha256, "
            "skattesats, ar, rader, invanare, hamtad, korning_id) VALUES (%s, '2280', 1, %s, %s, %s, 'x', 23.34, "
            "%s, %s, %s, %s, %s)",
            (cirkular, publicerad, f"https://skr.se/download/x/1/Prognosunderlag-K-2026-2033-{nr}.xlsm",
             f"Prognosunderlag-K-2026-2033-{nr}.xlsm", Jsonb(ar), Jsonb(rader), Jsonb({a: 24_000 for a in tkr}),
             datetime.now(timezone.utc), korning),
        )


@pytest.fixture
def prognoser(api, database_url: str) -> None:  # api kör migreringarna
    # I omvänd ordning, så att sorteringen efter datum syns.
    lagg_in_prognos(database_url, "26:28", date(2026, 10, 6), {"2026": 2_123_232, "2027": 2_222_069})
    lagg_in_prognos(database_url, "26:12", date(2026, 2, 19), {"2026": 2_130_000, "2027": 2_210_000})


def test_differensen_mot_26_28_for_2027(database_url, prognoser):
    with db.connect(database_url) as conn:
        j = skatteunderlag.jamforelse(conn, 2027, PLAN_2027)
    assert j["saknas"] is None
    assert j["planforutsattningar_mnkr"] == PLAN_2027
    [p12, p28] = j["prognoser"]
    assert (p28["cirkular"], p28["publicerad"], p28["mnkr"]) == ("26:28", "2026-10-06", 2222.069)
    assert p28["differens"] == {"mnkr": 5.1, "procent": 0.23}  # SKR − planförutsättningar
    assert p28["url"].endswith("26028.xlsm")
    assert p12["differens"] == {"mnkr": -7.0, "procent": -0.32}


def test_ar_utan_prognos_har_ingen_tabell(database_url, prognoser):
    with db.connect(database_url) as conn:
        fore = skatteunderlag.jamforelse(conn, 2025, 2100.0)
        efter = skatteunderlag.jamforelse(conn, 2030, 2500.0)
        utan_plan = skatteunderlag.jamforelse(conn, 2027, None)
    assert (fore["prognoser"], fore["saknas"]) == ([], "SKR:s prognoser finns från 2026.")
    assert (efter["prognoser"], efter["saknas"]) == ([], "Ingen av SKR:s skatteunderlagsprognoser har en siffra för 2030.")
    assert (utan_plan["prognoser"], utan_plan["saknas"]) == ([], "Planförutsättningarna för 2027 är inte publicerade.")


def test_budgetaret_visar_jamforelsen_sorterad_efter_datum(api, database_url, monkeypatch, capsys, prognoser):
    las_in(database_url, monkeypatch, capsys)
    # Opublicerade planförutsättningar jämförs inte.
    logga_in(api, None)
    assert api.get("/api/budget/2027").json()["skr"]["saknas"] == "Planförutsättningarna för 2027 är inte publicerade."

    publicera_alla(api)
    j = api.get("/api/budget/2027").json()
    skr = j["skr"]
    assert skr["planforutsattningar_mnkr"] == PLAN_2027
    assert [p["cirkular"] for p in skr["prognoser"]] == ["26:12", "26:28"]
    assert skr["prognoser"][1]["differens"] == {"mnkr": 5.1, "procent": 0.23}
    # Budgetförslagen påverkas inte.
    [l] = [f for f in j["forslag"] if f["nyckel"] == "L"]
    assert l["berakning"]["differens"] == 20.0
