"""Återkommande ärenden (#46): ärenden som behandlats vid flera sammanträden.

Ett ärende kommer från ärendespårningen (ADR-0003). Ett ärende är återkommande när minst två av
dess behandlingar ligger inom det valda urvalet (år och organ). Samlingspunkter (val av justerare,
delegationsbeslut, informationsärenden …) är inga ärenden och tas inte med. Återremisser och
bordläggningar räknas för sig, eftersom de förklarar varför ett ärende återkommer.

Kopplingar som bara är föreslagna ingår inte i ärendet. Har ett ärende sådana förslag visas antalet,
så att läsaren ser att ärendet kan vara större än det som räknats.
"""

from __future__ import annotations

import re
from collections import defaultdict

import psycopg

from .behandlingar import las as behandlingar_las
from .arenden import NIVA, SAMLING
from .sources.harnosand import organ_ref

_ATERREMISS = re.compile(r"\båterremitter", re.I)
_BORDLAGG = re.compile(r"\bbordlägg", re.I)


def handelse(beslut: str | None) -> str | None:
    """'aterremiss' eller 'bordlaggning' när beslutet skjuter upp ärendet, annars None."""
    if _ATERREMISS.search(beslut or ""):
        return "aterremiss"
    if _BORDLAGG.search(beslut or ""):
        return "bordlaggning"
    return None


def aterkommande(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None) -> dict:
    per: dict[int, list[dict]] = defaultdict(list)
    for r in behandlingar_las(conn, fran=fran, till=till, organ=organ):
        if r["arende_id"] is None or SAMLING.search(r["rubrik"]):
            continue
        per[r["arende_id"]].append(r)
    per = {a: bs for a, bs in per.items() if len({b["sammantrade_id"] for b in bs}) >= 2}

    forslag: dict[int, int] = defaultdict(int)
    if per:
        for k in conn.execute(
            """
            SELECT a.arende_id, count(*) AS n FROM koppling k
            JOIN arende_behandling a ON (a.sammantrade_id, a.paragraf) IN
                 ((k.fran_sammantrade_id, k.fran_paragraf), (k.till_sammantrade_id, k.till_paragraf))
            WHERE k.status = 'forslag' AND a.arende_id = ANY(%s)
            GROUP BY a.arende_id
            """,
            (list(per),),
        ):
            forslag[k["arende_id"]] = k["n"]

    arenden = []
    for arende_id, bs in per.items():
        bs.sort(key=lambda r: (r["datum"], NIVA.get(r["organ"], 0), r["paragraf"]))
        behandlingar = [{
            "sammantrade": {"id": b["sammantrade_id"], "datum": b["datum"], "organ": organ_ref(b["organ"])},
            "paragraf": b["paragraf"], "rubrik": b["rubrik"], "handelse": handelse(b["beslut"]),
        } for b in bs]
        arenden.append({
            "id": arende_id,
            "rubrik": bs[-1]["rubrik"],
            "antal_behandlingar": len(bs),
            "aterremisser": sum(1 for b in behandlingar if b["handelse"] == "aterremiss"),
            "bordlaggningar": sum(1 for b in behandlingar if b["handelse"] == "bordlaggning"),
            "foreslagna_kopplingar": forslag[arende_id],
            "forsta": bs[0]["datum"],
            "senaste": bs[-1]["datum"],
            "behandlingar": behandlingar,
        })
    arenden.sort(key=lambda a: (-a["antal_behandlingar"], -(a["aterremisser"] + a["bordlaggningar"]),
                                -a["senaste"].toordinal()))
    return {
        "fran": fran,
        "till": till,
        "organ": organ_ref(organ) if organ else None,
        "arenden": arenden,
        "summa": {
            "arenden": len(arenden),
            "aterremisser": sum(a["aterremisser"] for a in arenden),
            "bordlaggningar": sum(a["bordlaggningar"] for a in arenden),
        },
    }
