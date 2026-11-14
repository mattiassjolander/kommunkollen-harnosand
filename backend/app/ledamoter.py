"""Ledamotsregister: personer ur protokollens närvarolistor (#30).

En ledamot identifieras på namn, exakt som det står i protokollet. Partitillhörighet, roll och
tjänstgöring läses per sammanträde ur närvaron (ADR-0004), så ett partibyte syns och inget parti
fylls i från andra källor. Övriga närvarande (t.ex. tjänstepersoner) ingår inte.

En redaktör kan slå ihop namn som är samma person ("Britta Thyr" och "Knapp Britta Thyr") och
dela upp en sammanslagning som blev fel. Personen visas under huvudnamnet, det namn som de andra
slogs ihop med.
"""

from __future__ import annotations

from collections.abc import Iterable

import psycopg

from .sources.harnosand import ORGAN

KATEGORIER = ("beslutande", "ej_tjanstgorande", "franvarande")


class Konflikt(Exception):
    """En sammanslagning eller uppdelning som inte går att göra."""


def registrera(conn: psycopg.Connection, namn: Iterable[str]) -> None:
    """Ger nya namn ur en närvarolista en rad i registret."""
    namn = sorted(set(namn))
    if namn:
        conn.execute("INSERT INTO ledamot (namn) SELECT unnest(%s::text[]) ON CONFLICT DO NOTHING", (namn,))


def personer_for(conn: psycopg.Connection, namn: Iterable[str]) -> dict[str, int]:
    """Namn → personens id (huvudnamnets id)."""
    rader = conn.execute(
        "SELECT namn, coalesce(huvud_id, id) AS person FROM ledamot WHERE namn = ANY(%s)", (list(set(namn)),)
    ).fetchall()
    return {r["namn"]: r["person"] for r in rader}


def _organ(organ_id: str) -> dict:
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}


def _sorteringsnyckel(namn: str) -> str:
    # Svensk ordning: å, ä, ö efter z.
    return namn.casefold().translate(str.maketrans({"å": "{", "ä": "|", "ö": "}", "é": "e"}))


_FOREKOMSTER = """
    SELECT coalesce(l.huvud_id, l.id) AS person, l.id AS namn_id, n.namn, n.parti, n.roll, n.kategori,
           n.tjanstgor_for, n.tjanstgor_for_parti, n.paragrafer, n.jav,
           s.id AS sammantrade_id, s.organ, s.datum, s.starttid, s.tolkning
    FROM narvaro n
    JOIN ledamot l ON l.namn = n.namn
    JOIN sammantrade s ON s.id = n.sammantrade_id
    WHERE n.kategori <> 'ovrig'
"""


def lista(conn: psycopg.Connection, q: str | None = None, parti: str | None = None,
          organ: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"""
        WITH f AS ({_FOREKOMSTER})
        SELECT p.id, p.namn,
               array_agg(DISTINCT f.namn) AS namn_varianter,
               array_agg(DISTINCT f.organ) AS organ,
               array_agg(DISTINCT coalesce(f.parti, '')) AS partier,
               (array_agg(f.parti ORDER BY f.datum DESC NULLS LAST, f.starttid DESC NULLS LAST,
                          f.sammantrade_id DESC))[1] AS senaste_parti,
               count(DISTINCT f.sammantrade_id) AS antal_sammantraden,
               max(f.datum) AS senast
        FROM f JOIN ledamot p ON p.id = f.person
        GROUP BY p.id, p.namn
        """
    ).fetchall()
    ut = []
    for r in rader:
        if q and not any(q.casefold() in n.casefold() for n in [r["namn"], *r["namn_varianter"]]):
            continue
        if parti and parti not in r["partier"]:
            continue
        if organ and organ not in r["organ"]:
            continue
        ut.append({
            "id": r["id"],
            "namn": r["namn"],
            "andra_namn": sorted(n for n in r["namn_varianter"] if n != r["namn"]),
            "parti": r["senaste_parti"],
            # Partierna personen haft enligt protokollen ('-' = partilös). Saknat parti räknas inte.
            "partier": sorted(p for p in r["partier"] if p),
            "organ": [_organ(o) for o in sorted(r["organ"], key=list(ORGAN).index)],
            "antal_sammantraden": r["antal_sammantraden"],
            "senast": r["senast"],
        })
    return sorted(ut, key=lambda p: _sorteringsnyckel(p["namn"]))


def _perioder(forekomster: list[dict]) -> list[dict]:
    """Partitillhörighet över tid: följd av sammanträden med samma parti, äldst först."""
    perioder: list[dict] = []
    for f in forekomster:
        if perioder and perioder[-1]["parti"] == f["parti"]:
            p = perioder[-1]
            p["till"], p["antal"] = f["datum"], p["antal"] + 1
        else:
            perioder.append({"parti": f["parti"], "fran": f["datum"], "till": f["datum"], "antal": 1})
    return perioder


def las(conn: psycopg.Connection, ledamot_id: int) -> dict | None:
    rad = conn.execute("SELECT id, namn, huvud_id FROM ledamot WHERE id = %s", (ledamot_id,)).fetchone()
    if rad is None:
        return None
    person = rad["huvud_id"] or rad["id"]
    huvud = conn.execute("SELECT id, namn FROM ledamot WHERE id = %s", (person,)).fetchone()
    namn = conn.execute(
        """
        SELECT l.id, l.namn, l.huvud_id, count(n.id) AS antal
        FROM ledamot l LEFT JOIN narvaro n ON n.namn = l.namn AND n.kategori <> 'ovrig'
        WHERE l.id = %(p)s OR l.huvud_id = %(p)s
        GROUP BY l.id ORDER BY l.huvud_id IS NOT NULL, l.namn
        """,
        {"p": person},
    ).fetchall()
    forekomster = conn.execute(
        f"""{_FOREKOMSTER} AND coalesce(l.huvud_id, l.id) = %s
        ORDER BY s.datum NULLS FIRST, s.starttid NULLS FIRST, s.id""",
        (person,),
    ).fetchall()
    if not forekomster and rad["huvud_id"] is None and not [n for n in namn if n["huvud_id"]]:
        return None  # namnet finns inte längre i någon närvarolista

    per_organ: dict[str, dict] = {}
    for f in forekomster:
        o = per_organ.setdefault(f["organ"], {
            "organ": _organ(f["organ"]), "roller": [], "antal": 0, "fran": f["datum"], "till": f["datum"],
            **{k: 0 for k in KATEGORIER},
        })
        o["antal"] += 1
        o[f["kategori"]] += 1
        o["till"] = f["datum"]
        if f["roll"] and f["roll"] not in o["roller"]:
            o["roller"].append(f["roll"])

    return {
        "id": person,
        "namn": huvud["namn"],
        "sammanslagen_med": person if rad["huvud_id"] else None,
        "namn_varianter": [
            {"id": n["id"], "namn": n["namn"], "huvudnamn": n["huvud_id"] is None, "antal": n["antal"]}
            for n in namn
        ],
        "partier_over_tid": _perioder(forekomster),
        "organ": sorted(per_organ.values(), key=lambda o: list(ORGAN).index(o["organ"]["id"])
                        if o["organ"]["id"] in ORGAN else 99),
        "sammantraden": [
            {
                "sammantrade": {"id": f["sammantrade_id"], "datum": f["datum"], "starttid": f["starttid"],
                                "organ": _organ(f["organ"]), "tolkning": f["tolkning"]},
                "namn": f["namn"], "parti": f["parti"], "roll": f["roll"], "kategori": f["kategori"],
                "tjanstgor_for": {"namn": f["tjanstgor_for"], "parti": f["tjanstgor_for_parti"]}
                if f["tjanstgor_for"] else None,
                "paragrafer": f["paragrafer"], "jav": f["jav"],
            }
            for f in reversed(forekomster)
        ],
    }


def _person(conn: psycopg.Connection, ledamot_id: int) -> int:
    rad = conn.execute("SELECT coalesce(huvud_id, id) AS person FROM ledamot WHERE id = %s", (ledamot_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Ledamoten {ledamot_id} finns inte")
    return rad["person"]


def sla_ihop(conn: psycopg.Connection, huvud_id: int, annan_id: int, redaktor: str) -> dict:
    """Slår ihop `annan_id`s person med `huvud_id`s. Huvudpersonens namn visas."""
    huvud, annan = _person(conn, huvud_id), _person(conn, annan_id)
    if huvud == annan:
        raise Konflikt("Namnen hör redan till samma person")
    flyttade = conn.execute(
        """
        UPDATE ledamot SET huvud_id = %(huvud)s WHERE id = %(annan)s OR huvud_id = %(annan)s
        RETURNING id
        """,
        {"huvud": huvud, "annan": annan},
    ).fetchall()
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO ledamot_handelse (typ, ledamot_id, huvud_id, tidigare_huvud_id, redaktor)
               VALUES ('sammanslagning', %s, %s, %s, %s)""",
            [(r["id"], huvud, annan if r["id"] != annan else None, redaktor) for r in flyttade],
        )
    return las(conn, huvud)


def dela_upp(conn: psycopg.Connection, namn_id: int, redaktor: str) -> dict:
    """Gör ett sammanslaget namn till en egen person igen."""
    rad = conn.execute("SELECT id, huvud_id FROM ledamot WHERE id = %s", (namn_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Ledamoten {namn_id} finns inte")
    if rad["huvud_id"] is None:
        raise Konflikt("Namnet är inte sammanslaget med någon annan")
    conn.execute("UPDATE ledamot SET huvud_id = NULL WHERE id = %s", (namn_id,))
    conn.execute(
        """INSERT INTO ledamot_handelse (typ, ledamot_id, huvud_id, tidigare_huvud_id, redaktor)
           VALUES ('uppdelning', %s, NULL, %s, %s)""",
        (namn_id, rad["huvud_id"], redaktor),
    )
    return las(conn, namn_id)
