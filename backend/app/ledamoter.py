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

from . import partier, partitillhorighet
from .partitillhorighet import Gallande
from .rattelser import Publicerade
from .sources.harnosand import organ_ref, ORGAN

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


def _sorteringsnyckel(namn: str) -> str:
    # Svensk ordning: å, ä, ö efter z.
    return namn.casefold().translate(str.maketrans({"å": "{", "ä": "|", "ö": "}", "é": "e"}))


_FOREKOMSTER = """
    SELECT coalesce(l.huvud_id, l.id) AS person, l.id AS namn_id, n.namn, n.parti, n.roll, n.kategori,
           n.tjanstgor_for, n.tjanstgor_for_parti, n.paragrafer, n.jav,
           s.id AS sammantrade_id, s.organ, s.datum, s.starttid, s.tolkning,
           -- Fastställd partitillhörighet vid sammanträdet (#100).
           (SELECT t.parti FROM partitillhorighet t JOIN ledamot lp ON lp.id = t.ledamot_id
            WHERE t.status = 'publicerad' AND coalesce(lp.huvud_id, lp.id) = coalesce(l.huvud_id, l.id)
              AND s.datum >= t.fran AND (t.till IS NULL OR s.datum <= t.till) LIMIT 1) AS period_parti
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
               array_agg(DISTINCT coalesce(f.period_parti, f.parti, '')) AS partier,
               (array_agg(coalesce(f.period_parti, f.parti) ORDER BY f.datum DESC NULLS LAST, f.starttid DESC NULLS LAST,
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
            # Partierna personen haft enligt protokollen och fastställda partitillhörigheter ('-' = partilös).
            # Saknat parti räknas inte.
            "partier": sorted(p for p in r["partier"] if p),
            "organ": [organ_ref(o) for o in sorted(r["organ"], key=list(ORGAN).index)],
            "antal_sammantraden": r["antal_sammantraden"],
            "senast": r["senast"],
        })
    return sorted(ut, key=lambda p: _sorteringsnyckel(p["namn"]))


def _per_sammantrade(forekomster: list[dict]) -> list[dict]:
    """En post per sammanträde. En ersättare som tjänstgjorde för flera ledamöter har en rad per
    tjänstgöring i närvarolistan. De slås ihop, med alla tjänstgöringar och paragrafer."""
    ut: dict[int, dict] = {}
    for f in forekomster:
        tjanstgoring = ({"namn": f["tjanstgor_for"], "parti": f["tjanstgor_for_parti"], "paragrafer": f["paragrafer"]}
                        if f["tjanstgor_for"] else None)
        if (tidigare := ut.get(f["sammantrade_id"])) is None:
            ut[f["sammantrade_id"]] = dict(f) | {"tjanstgoringar": [tjanstgoring] if tjanstgoring else []}
            continue
        if tjanstgoring:
            tidigare["tjanstgoringar"].append(tjanstgoring)
        if f["kategori"] != "beslutande" and tidigare["kategori"] == "beslutande":
            continue  # "Tom stol Namn §§ 50, 61" (#203): vid de paragraferna var personen inte beslutande.
        if tidigare["kategori"] != "beslutande" and f["kategori"] == "beslutande":
            tidigare["kategori"], tidigare["paragrafer"] = "beslutande", f["paragrafer"]
        elif tidigare["paragrafer"] is not None:
            tidigare["paragrafer"] = None if f["paragrafer"] is None else sorted({*tidigare["paragrafer"], *f["paragrafer"]})
    return list(ut.values())


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
    """Ledamotens sida. Samma svar efter läsning, sammanslagning och uppdelning, så att sidan kan visa det direkt."""
    resultat = _las(conn, ledamot_id)
    if resultat is not None:
        from . import markningar  # markningar läser behandlingarna

        # Märkningarna på behandlingarna där ledamoten röstade (#162).
        markningar.satt_pa_paragrafer(conn, resultat["roster"])
    return resultat


def _las(conn: psycopg.Connection, ledamot_id: int) -> dict | None:
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
    forekomster = _per_sammantrade(forekomster)
    # Publicerade partirättelser och fastställda partitillhörigheter läggs på. Saknat parti härleds ur samma
    # eller närmaste protokoll.
    pub = Publicerade(conn, [f["sammantrade_id"] for f in forekomster])
    gal = Gallande(conn, [n for f in forekomster for n in (f["namn"], *(t["namn"] for t in f["tjanstgoringar"]))])
    for f in forekomster:
        pub.person(f["sammantrade_id"], f)
        gal.satt(f, f["datum"])
        f["tjanstgor_for_parti"] = (gal.satt({"namn": f["tjanstgor_for"], "parti": f["tjanstgor_for_parti"]},
                                             f["datum"]) or {}).get("parti") if f["tjanstgor_for"] else None
        for t in f["tjanstgoringar"]:
            gal.satt(t, f["datum"])
        if f["parti"] is None:
            partier.fyll_i(conn, f["sammantrade_id"], [f])

    per_organ: dict[str, dict] = {}
    for f in forekomster:
        o = per_organ.setdefault(f["organ"], {
            "organ": organ_ref(f["organ"]), "roller": [], "antal": 0, "fran": f["datum"], "till": f["datum"],
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
        # Fastställda partitillhörigheter (#100).
        "partitillhorighet": partitillhorighet.lista(conn, ledamot_id=person, bara_publicerade=True),
        "organ": sorted(per_organ.values(), key=lambda o: list(ORGAN).index(o["organ"]["id"])
                        if o["organ"]["id"] in ORGAN else 99),
        "sammantraden": [
            {
                "sammantrade": {"id": f["sammantrade_id"], "datum": f["datum"], "starttid": f["starttid"],
                                "organ": organ_ref(f["organ"]), "tolkning": f["tolkning"]},
                "namn": f["namn"], "parti": f["parti"], "parti_harlett": f.get("parti_harlett"),
                "rattelser": f.get("rattelser"), "partitillhorighet": f.get("partitillhorighet"),
                "roll": f["roll"], "kategori": f["kategori"],
                "tjanstgor_for": {"namn": f["tjanstgor_for"], "parti": f["tjanstgor_for_parti"]}
                if f["tjanstgor_for"] else None,
                "tjanstgoringar": f["tjanstgoringar"],
                "paragrafer": f["paragrafer"], "jav": f["jav"],
            }
            for f in reversed(forekomster)
        ],
        "roster": _roster(conn, [n["namn"] for n in namn]),
    }


def _roster(conn: psycopg.Connection, namn: list[str]) -> list[dict]:
    """Personens röster i voteringar under något av sina namn, senaste först."""
    rader = conn.execute(
        """
        SELECT r.namn, r.parti, r.rost, r.ersatt, r.ersatt_parti,
               v.ordning, v.ja_forslag, v.nej_forslag, v.vinnare, v.resultat,
               (SELECT count(*) FROM votering v2 WHERE v2.behandling_id = b.id) AS antal_voteringar,
               b.paragraf, b.rubrik, s.id AS sammantrade_id, s.datum, s.organ
        FROM rost r
        JOIN votering v ON v.id = r.votering_id
        JOIN behandling b ON b.id = v.behandling_id
        JOIN sammantrade s ON s.id = b.sammantrade_id
        WHERE r.namn = ANY(%s)
        ORDER BY s.datum DESC, s.id DESC, b.ordning, v.ordning
        """,
        (namn,),
    ).fetchall()
    gal = Gallande(conn, [n for r in rader for n in (r["namn"], r["ersatt"])])
    return [
        {
            "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": organ_ref(r["organ"])},
            "paragraf": r["paragraf"], "rubrik": r["rubrik"],
            "votering": r["ordning"] + 1, "antal_voteringar": r["antal_voteringar"],
            **gal.satt({"namn": r["namn"], "parti": r["parti"]}, r["datum"]), "rost": r["rost"],
            "ersatt": gal.satt({"namn": r["ersatt"], "parti": r["ersatt_parti"]}, r["datum"]) if r["ersatt"] else None,
            "ja_forslag": r["ja_forslag"], "nej_forslag": r["nej_forslag"],
            "vinnare": r["vinnare"], "resultat": r["resultat"],
        }
        for r in rader
    ]


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
    flytta(conn, huvud, annan, redaktor)
    _uppdatera_sokindex(conn)
    return las(conn, huvud)


def flytta(conn: psycopg.Connection, huvud: int, annan: int, redaktor: str, automatisk: bool = False) -> None:
    """Flyttar personen `annan`s namn till personen `huvud` och loggar det. Båda är huvudnamnens id."""
    flyttade = conn.execute(
        """
        UPDATE ledamot SET huvud_id = %(huvud)s WHERE id = %(annan)s OR huvud_id = %(annan)s
        RETURNING id, namn
        """,
        {"huvud": huvud, "annan": annan},
    ).fetchall()
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO ledamot_handelse (typ, ledamot_id, namn, huvud_id, tidigare_huvud_id, redaktor, automatisk)
               VALUES ('sammanslagning', %s, %s, %s, %s, %s, %s)""",
            [(r["id"], r["namn"], huvud, annan if r["id"] != annan else None, redaktor, automatisk) for r in flyttade],
        )


def dela_upp(conn: psycopg.Connection, namn_id: int, redaktor: str) -> dict:
    """Gör ett sammanslaget namn till en egen person igen."""
    rad = conn.execute("SELECT id, namn, huvud_id FROM ledamot WHERE id = %s", (namn_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Ledamoten {namn_id} finns inte")
    if rad["huvud_id"] is None:
        raise Konflikt("Namnet är inte sammanslaget med någon annan")
    conn.execute("UPDATE ledamot SET huvud_id = NULL WHERE id = %s", (namn_id,))
    conn.execute(
        """INSERT INTO ledamot_handelse (typ, ledamot_id, namn, huvud_id, tidigare_huvud_id, redaktor)
           VALUES ('uppdelning', %s, %s, NULL, %s, %s)""",
        (namn_id, rad["namn"], rad["huvud_id"], redaktor),
    )
    _uppdatera_sokindex(conn)
    return las(conn, namn_id)


def _uppdatera_sokindex(conn: psycopg.Connection) -> None:
    from . import sokindex  # sokindex läser behandlingarna, som läser ledamöterna

    sokindex.uppdatera(conn, typer=("ledamot",))
