"""Härlett parti för en person som närvarolistan inte anger parti för.

Partiet tas i första hand ur protokollet för sammanträdet (ADR-0004). Saknas det i närvarolistan
används i tur och ordning:

1. Samma protokoll: voteringslistan ("Namn (S)"), eller en tjänstgöring där personen är den som
   ersätts ("för Namn (S)"). Bara om protokollet ger ett enda parti.
2. Närvarolistan i det protokoll som ligger närmast i tid där personen har ett parti.

Ett härlett parti visas med markering och källa, så att läsaren ser att det inte står i närvarolistan.
En publicerad rättelse av partiet går före det härledda.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import psycopg

from .sources.harnosand import ORGAN

_SAMMA_PROTOKOLL = """
    SELECT r.namn, r.parti FROM rost r
        JOIN votering v ON v.id = r.votering_id JOIN behandling b ON b.id = v.behandling_id
    WHERE b.sammantrade_id = %(s)s AND r.namn = ANY(%(n)s) AND r.parti IS NOT NULL
    UNION ALL
    SELECT r.ersatt, r.ersatt_parti FROM rost r
        JOIN votering v ON v.id = r.votering_id JOIN behandling b ON b.id = v.behandling_id
    WHERE b.sammantrade_id = %(s)s AND r.ersatt = ANY(%(n)s) AND r.ersatt_parti IS NOT NULL
    UNION ALL
    SELECT tjanstgor_for, tjanstgor_for_parti FROM narvaro
    WHERE sammantrade_id = %(s)s AND tjanstgor_for = ANY(%(n)s) AND tjanstgor_for_parti IS NOT NULL
"""

_NARMASTE = """
    SELECT DISTINCT ON (n.namn) n.namn, n.parti, s.id, s.datum, s.organ
    FROM narvaro n
    JOIN sammantrade s ON s.id = n.sammantrade_id
    CROSS JOIN (SELECT datum FROM sammantrade WHERE id = %(s)s) d
    WHERE n.namn = ANY(%(n)s) AND n.parti IS NOT NULL AND s.id <> %(s)s
    ORDER BY n.namn, abs(s.datum - d.datum) NULLS LAST, s.datum DESC, s.id DESC
"""


def harled(conn: psycopg.Connection, sammantrade_id: int, namn: Iterable[str]) -> dict[str, dict]:
    """namn → {"parti": ..., "kalla": {"grund": "samma_protokoll" | "annat_protokoll", "sammantrade": ...}}."""
    namn = sorted({n for n in namn if n})
    if not namn:
        return {}
    param = {"s": sammantrade_id, "n": namn}
    partier: dict[str, set[str]] = defaultdict(set)
    for r in conn.execute(_SAMMA_PROTOKOLL, param):
        partier[r["namn"]].add(r["parti"])
    ut = {n: {"parti": p.pop(), "kalla": {"grund": "samma_protokoll", "sammantrade": None}}
          for n, p in partier.items() if len(p) == 1}
    if rest := [n for n in namn if n not in ut]:
        for r in conn.execute(_NARMASTE, param | {"n": rest}):
            o = ORGAN.get(r["organ"])
            ut[r["namn"]] = {"parti": r["parti"], "kalla": {"grund": "annat_protokoll", "sammantrade": {
                "id": r["id"], "datum": r["datum"], "organ": {"id": r["organ"], "namn": o.namn if o else r["organ"]},
            }}}
    return ut


def fyll_i(conn: psycopg.Connection, sammantrade_id: int, personer: list[dict]) -> list[dict]:
    """Lägger härlett parti på personer (dicts med namn, parti, kategori) som saknar parti och inte har
    en publicerad partirättelse. Personen får "parti_harlett" med källan."""
    saknar = [p for p in personer if p["parti"] is None and p.get("kategori") != "ovrig"
              and "parti" not in (p.get("rattelser") or {})]
    harlett = harled(conn, sammantrade_id, (p["namn"] for p in saknar))
    for p in saknar:
        if h := harlett.get(p["namn"]):
            p["parti"], p["parti_harlett"] = h["parti"], h["kalla"]
    return personer
