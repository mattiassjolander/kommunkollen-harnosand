"""Krockar mellan protokollen och fastställda partitillhörigheter, och personerna i fliken (#100, del 3).

En krock är ett sammanträde där närvarolistan uttryckligen anger ett annat parti än personens fastställda
partitillhörighet, publicerad eller väntande (utkast eller granskad). Ett sammanträde där protokollet saknar parti
är ingen krock. Krockarna räknas fram när de hämtas, så att nya protokoll kommer med.

Perioden gäller även för en krock, men krocken visas för redaktionen tills den är bekräftad. Redaktören bekräftar
den med en rättelse av partiet i närvarolistan, med periodens parti som värde och med om felet finns i protokollet
eller i inläsningen (#74). Rättelsen går igenom samma granskning, och ett fel i protokollet räknas som en
felaktighet i protokollet. En krock med en rättelse som är utkast, granskad eller publicerad visas inte. Visar
krocken ett riktigt partibyte ändrar redaktören perioderna i stället.
"""

from __future__ import annotations

from collections import defaultdict

import psycopg

from . import partitillhorighet, rattelser
from .sources.harnosand import organ_ref

_KROCKAR = """
    SELECT DISTINCT ON (n.id)
           p.id AS person, p.namn AS person_namn, n.namn, n.parti AS protokollet,
           s.id AS sammantrade_id, s.datum, s.organ,
           t.id AS period_id, t.parti AS period_parti, t.fran, t.till, t.status AS period_status
    FROM narvaro n
    JOIN ledamot l ON l.namn = n.namn
    JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id)
    JOIN sammantrade s ON s.id = n.sammantrade_id
    JOIN partitillhorighet t ON t.status IN ('utkast', 'granskad', 'publicerad')
         AND t.ledamot_id IN (SELECT id FROM ledamot WHERE coalesce(huvud_id, id) = p.id)
         AND s.datum >= t.fran AND (t.till IS NULL OR s.datum <= t.till)
    WHERE n.kategori <> 'ovrig' AND n.parti IS NOT NULL AND n.parti <> t.parti
      AND NOT EXISTS (
          SELECT 1 FROM rattelse r WHERE r.sammantrade_id = n.sammantrade_id AND r.objekt = 'narvaro'
             AND r.namn = n.namn AND r.falt = 'parti' AND r.status IN ('utkast', 'granskad', 'publicerad'))
"""


def _krock(r: dict) -> dict:
    return {
        "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": organ_ref(r["organ"])},
        "namn": r["namn"], "protokollet": r["protokollet"],
        "period": {"id": r["period_id"], "parti": r["period_parti"], "fran": r["fran"], "till": r["till"],
                   "status": r["period_status"]},
    }


def _rader(conn: psycopg.Connection, villkor: str = "", params: dict | None = None) -> list[dict]:
    # En publicerad period går före en väntande när de överlappar.
    return conn.execute(
        f"""SELECT * FROM ({_KROCKAR} {villkor}
            ORDER BY n.id, t.status = 'publicerad' DESC, t.id DESC) k
            ORDER BY k.person_namn, k.person, k.datum, k.sammantrade_id""",
        params or {},
    ).fetchall()


def lista(conn: psycopg.Connection) -> list[dict]:
    """Krockarna per person: [{ledamot: {id, namn}, krockar: [...]}]."""
    per: dict[int, dict] = {}
    for r in _rader(conn):
        per.setdefault(r["person"], {"ledamot": {"id": r["person"], "namn": r["person_namn"]}, "krockar": []})
        per[r["person"]]["krockar"].append(_krock(r))
    return list(per.values())


def bekrafta(conn: psycopg.Connection, data: dict, redaktor: str) -> list[dict]:
    """Bekräftar krockar: {felet_i, motivering, krockar: [{sammantrade_id, namn}]}. Varje krock blir en rättelse av
    partiet i närvarolistan, som utkast, med periodens parti. Allt eller inget."""
    valda = data.get("krockar")
    if not isinstance(valda, list) or not valda:
        raise rattelser.Ogiltig("Välj minst en krock")
    ut = []
    for k in valda:
        if not isinstance(k, dict) or not isinstance(k.get("sammantrade_id"), int) or not k.get("namn"):
            raise rattelser.Ogiltig("En krock anges med sammantrade_id och namn")
        rad = _rader(conn, "AND n.sammantrade_id = %(s)s AND n.namn = %(n)s",
                     {"s": k["sammantrade_id"], "n": k["namn"]})
        if not rad:
            raise rattelser.Konflikt(f"{k['namn']} har ingen obekräftad krock vid sammanträdet {k['sammantrade_id']}")
        ut.append(rattelser.skapa(conn, {
            "sammantrade_id": k["sammantrade_id"], "objekt": "narvaro", "namn": k["namn"], "falt": "parti",
            "nytt": rad[0]["period_parti"], "motivering": data.get("motivering"), "felet_i": data.get("felet_i"),
        }, redaktor))
    return ut


def personer(conn: psycopg.Connection) -> list[dict]:
    """Alla personer med förekomster i närvarolistorna, med perioder och antal krockar, för filtren i fliken:
    har krockar, saknar fastställd period och väntar på granskning."""
    rader = conn.execute(
        """
        SELECT p.id, p.namn, count(DISTINCT n.sammantrade_id) AS antal_sammantraden, max(s.datum) AS senast
        FROM narvaro n JOIN ledamot l ON l.namn = n.namn JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id)
        JOIN sammantrade s ON s.id = n.sammantrade_id
        WHERE n.kategori <> 'ovrig'
        GROUP BY p.id, p.namn ORDER BY p.namn, p.id
        """
    ).fetchall()
    perioder: dict[int, list[dict]] = defaultdict(list)
    for t in partitillhorighet.lista(conn):
        perioder[t["ledamot"]["id"]].append(t)
    krockar: dict[int, int] = defaultdict(int)
    for r in _rader(conn):
        krockar[r["person"]] += 1
    ut = []
    for r in rader:
        egna = perioder.get(r["id"], [])
        ut.append({
            "ledamot": {"id": r["id"], "namn": r["namn"]},
            "antal_sammantraden": r["antal_sammantraden"], "senast": r["senast"],
            "publicerade": [t for t in egna if t["status"] == "publicerad"],
            "vantande": sum(1 for t in egna if t["status"] in ("utkast", "granskad")),
            "krockar": krockar.get(r["id"], 0),
        })
    return ut
