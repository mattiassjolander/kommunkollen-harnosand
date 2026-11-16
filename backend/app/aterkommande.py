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

from .arenden import NIVA, SAMLING
from .rattelser import Publicerade
from .sources.harnosand import ORGAN

_ATERREMISS = re.compile(r"\båterremitter", re.I)
_BORDLAGG = re.compile(r"\bbordlägg", re.I)


def _organ(organ_id: str) -> dict:
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}


def handelse(beslut: str | None) -> str | None:
    """'aterremiss' eller 'bordlaggning' när beslutet skjuter upp ärendet, annars None."""
    if _ATERREMISS.search(beslut or ""):
        return "aterremiss"
    if _BORDLAGG.search(beslut or ""):
        return "bordlaggning"
    return None


def aterkommande(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None) -> dict:
    rader = conn.execute(
        """
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.sammantrade_id, b.paragraf, b.rubrik, b.beslut,
               b.diarienummer, s.organ, s.datum, a.arende_id
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        JOIN arende_behandling a ON a.sammantrade_id = b.sammantrade_id AND a.paragraf = b.paragraf
        WHERE s.datum >= make_date(%(fran)s, 1, 1) AND s.datum < make_date(%(till)s + 1, 1, 1)
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """,
        {"fran": fran, "till": till, "organ": organ},
    ).fetchall()
    pub = Publicerade(conn, list({r["sammantrade_id"] for r in rader}))
    per: dict[int, list[dict]] = defaultdict(list)
    for r in rader:
        b = pub.behandling(r["sammantrade_id"], {k: r[k] for k in ("paragraf", "rubrik", "beslut", "diarienummer")})
        if SAMLING.search(b["rubrik"]):
            continue
        per[r["arende_id"]].append(r | {"rubrik": b["rubrik"], "beslut": b["beslut"]})
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
            "sammantrade": {"id": b["sammantrade_id"], "datum": b["datum"], "organ": _organ(b["organ"])},
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
        "organ": _organ(organ) if organ else None,
        "arenden": arenden,
        "summa": {
            "arenden": len(arenden),
            "aterremisser": sum(a["aterremisser"] for a in arenden),
            "bordlaggningar": sum(a["bordlaggningar"] for a in arenden),
        },
    }
