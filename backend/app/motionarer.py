"""Rättade motionärer (#78): personer ur ledamotsregistret med parti, eller ett parti utan namn.

En rättelse av motionärerna anger hela listan och hör till ärendets behandling i kommunfullmäktige där
motionen väcktes, annars till ärendets första behandling. Den följer det vanliga flödet för rättelser
(rattelser.py, ADR-0002). Bara personer som finns i registret kan anges, och namnet blir personens
huvudnamn, så att namnvarianter räknas som samma person.

Partiet förifylls ur personens närvaro vid sammanträdet där motionen väcktes. Saknas det där härleds
det som för närvarolistan (partier.harled, ADR-0004): samma protokoll, annars närmaste protokoll.
"""

from __future__ import annotations

import re
from typing import Any

import psycopg

from . import partier

_PARTI = re.compile(r"[A-ZÅÄÖ]{1,4}|-")


class Ogiltig(ValueError):
    """Listan med motionärer är inte giltig."""


def _person(conn: psycopg.Connection, person_id: int) -> dict:
    """Personens huvudnamn och id. LookupError om personen inte finns i registret."""
    rad = conn.execute(
        "SELECT h.id, h.namn FROM ledamot l JOIN ledamot h ON h.id = coalesce(l.huvud_id, l.id) WHERE l.id = %s",
        (person_id,),
    ).fetchone()
    if rad is None:
        raise Ogiltig(f"Personen {person_id} finns inte i personregistret")
    return rad


def normalisera(conn: psycopg.Connection, varde: Any) -> list[dict]:
    """Rättelsens värde: [{person_id, namn, parti}], där en partigrupp har person_id och namn None."""
    if not isinstance(varde, list) or not varde:
        raise Ogiltig("Ange minst en motionär, en person ur registret eller ett parti")
    ut: list[dict] = []
    for m in varde:
        if not isinstance(m, dict):
            raise Ogiltig("Varje motionär ska ha person_id eller parti")
        parti = m.get("parti")
        if parti is not None:
            if not isinstance(parti, str) or not _PARTI.fullmatch(parti.strip()):
                raise Ogiltig("Partiet anges med förkortning, t.ex. S, eller - för partilös")
            parti = parti.strip()
        pid = m.get("person_id")
        if pid is None:
            if parti is None:
                raise Ogiltig("En motionär utan person ska ha ett parti")
            ut.append({"person_id": None, "namn": None, "parti": parti})
            continue
        if not isinstance(pid, int):
            raise Ogiltig("person_id ska vara ett id i personregistret")
        p = _person(conn, pid)
        ut.append({"person_id": p["id"], "namn": p["namn"], "parti": parti})
    nycklar = [(m["person_id"], m["parti"] if m["person_id"] is None else None) for m in ut]
    if len(set(nycklar)) != len(nycklar):
        raise Ogiltig("Samma motionär står två gånger")
    return ut


def parti_for(conn: psycopg.Connection, person_id: int, sammantrade_id: int) -> dict:
    """Förslag på parti för personen vid sammanträdet: {parti, kalla}. Källan är närvaron vid
    sammanträdet, eller den härledning som partier.harled gör. parti är None om inget hittas."""
    p = _person(conn, person_id)
    namn = [r["namn"] for r in conn.execute(
        "SELECT namn FROM ledamot WHERE coalesce(huvud_id, id) = %s ORDER BY id", (p["id"],))]
    rad = conn.execute(
        "SELECT parti FROM narvaro WHERE sammantrade_id = %s AND namn = ANY(%s) AND parti IS NOT NULL "
        "ORDER BY ordning LIMIT 1", (sammantrade_id, namn),
    ).fetchone()
    if rad:
        return {"parti": rad["parti"], "kalla": {"grund": "narvaro", "sammantrade": None}}
    harlett = partier.harled(conn, sammantrade_id, namn)
    # Samma protokoll går före ett annat protokoll.
    for grund in ("samma_protokoll", "annat_protokoll"):
        for n in namn:
            if (h := harlett.get(n)) and h["kalla"]["grund"] == grund:
                return h
    return {"parti": None, "kalla": None}
