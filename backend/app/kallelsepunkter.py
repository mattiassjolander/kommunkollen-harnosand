"""Diarienummer ur kallelsen (#109): komplettering av behandlingar som saknar diarienummer i protokollet.

Föredragningslistan läses ur kallelsen, kungörelsen eller handlingarna (`sources.foredragningslista`)
och sparas som kallelsepunkter. Varje sammanträde paras sedan ihop med sina kallelser (samma organ och
datum, närmaste klockslag när organet har flera sammanträden samma dag) och kallelsens punkter med
protokollets paragrafer:

- Punkterna och paragraferna paras ihop i ordning, på rubriken (`arenden.likhet` > `LIKHETSGRANS`).
  Kallelsens paragrafnummer används bara för att skilja lika rubriker åt, eftersom numren inte alltid
  är protokollets (kommunstyrelsen 2026-09-29: 116–131 i kallelsen, 131–143 i protokollet).
- En behandling utan diarienummer i protokollet får punktens diarienummer, med kallelsen som källa.
  Protokollets eget diarienummer går alltid före, och en publicerad rättelse går före båda
  (`satt` läggs på före `Publicerade.behandling`).
- En punkt med diarienummer som inte liknar någon paragraf ger ingen komplettering, utan en avvikelse
  för sammanträdet. Det gör också en kallelse som bara delvis kunde läsas.

Kompletteringen räknas om i sin helhet när ett protokoll eller en kallelse har lästs, så den följer
protokollets tolkning. Kopplingarna (ADR-0003) använder diarienumren oavsett källa, eftersom de läser
behandlingarna genom `behandlingar.las`.
"""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb

from .sources.foredragningslista import Foredragningslista

# Poängen för samma paragrafnummer i kallelsen och protokollet, när rubrikerna är lika lika.
_SAMMA_NUMMER = 0.01


def lagra_punkter(conn: psycopg.Connection, kallelse_id: int, f: Foredragningslista, last: datetime) -> None:
    conn.execute("DELETE FROM kallelsepunkt WHERE kallelse_id = %s", (kallelse_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO kallelsepunkt (kallelse_id, ordning, paragraf, rubrik, tabellrubrik, diarienummer, sida)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(kallelse_id, i, p.paragraf, p.rubrik, p.tabellrubrik, list(p.diarienummer), p.sida)
             for i, p in enumerate(f.punkter)],
        )
    conn.execute(
        "UPDATE kallelse SET punkter_status = %s, punkter_fel = %s, punkter_lasta = %s WHERE id = %s",
        (f.status, Jsonb(list(f.fel)), last, kallelse_id),
    )


def _para_ihop(punkter: list[dict], behandlingar: list[dict]) -> dict[int, int]:
    """Punkt (index) -> behandling (index), i ordning och med så lika rubriker som möjligt."""
    from .arenden import LIKHETSGRANS, likhet

    n, m = len(punkter), len(behandlingar)
    poang = [[0.0] * m for _ in range(n)]
    for i, p in enumerate(punkter):
        for j, b in enumerate(behandlingar):
            v = max(likhet(p["rubrik"], b["rubrik"]), likhet(p["tabellrubrik"], b["rubrik"]) if p["tabellrubrik"] else 0)
            poang[i][j] = (v + (_SAMMA_NUMMER if p["paragraf"] == b["paragraf"] else 0)) if v > LIKHETSGRANS else 0.0
    # Bästa ordnade ihopparning (som längsta gemensamma delföljd, viktad med likheten).
    bast = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            bast[i][j] = max(bast[i + 1][j], bast[i][j + 1],
                             bast[i + 1][j + 1] + poang[i][j] if poang[i][j] else 0.0)
    par, i, j = {}, 0, 0
    while i < n and j < m:
        if poang[i][j] and bast[i][j] == bast[i + 1][j + 1] + poang[i][j]:
            par[i] = j
            i, j = i + 1, j + 1
        elif bast[i][j] == bast[i + 1][j]:
            i += 1
        else:
            j += 1
    return par


def _kallelser_per_sammantrade(conn: psycopg.Connection) -> dict[int, list[dict]]:
    """De lästa kallelserna för varje sammanträde med behandlingar, senast publicerade först."""
    from .sammantradesplan import narmast  # sammantradesplan läser behandlingarna, som läser härifrån

    sammantraden = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.starttid FROM sammantrade s
        WHERE s.datum IS NOT NULL AND EXISTS (SELECT 1 FROM behandling b WHERE b.sammantrade_id = s.id)
        """
    ).fetchall()
    per_dag: dict[tuple, list[dict]] = {}
    for s in sammantraden:
        per_dag.setdefault((s["organ"], s["datum"]), []).append(s)
    ut: dict[int, list[dict]] = {}
    for k in conn.execute(
        "SELECT id, organ, datum, tid, typ, titel, url, punkter_status, punkter_fel FROM kallelse "
        "WHERE punkter_status <> 'ej_last' ORDER BY forst_sedd DESC, id DESC"
    ):
        dagens = per_dag.get((k["organ"], k["datum"]), [])
        mal = [narmast(k["tid"], dagens)] if k["tid"] and len(dagens) > 1 else dagens
        for s in (x for x in mal if x is not None):
            ut.setdefault(s["id"], []).append(k)
    return ut


def komplettera(conn: psycopg.Connection) -> int:
    """Räknar om kompletteringen för alla sammanträden. Returnerar antalet ändrade behandlingar."""
    fore = {(r["sammantrade_id"], r["paragraf"]): (r["kallelsepunkt_id"], tuple(r["diarienummer"]))
            for r in conn.execute("SELECT * FROM kallelse_diarienummer")}
    nya: dict[tuple[int, int], tuple[int, tuple[str, ...]]] = {}
    avvikelser: dict[int, list[str]] = {}
    per_sammantrade = _kallelser_per_sammantrade(conn)
    punkter_per_kallelse: dict[int, list[dict]] = {}
    for r in conn.execute(
        "SELECT * FROM kallelsepunkt WHERE kallelse_id = ANY(%s) ORDER BY kallelse_id, ordning",
        ([k["id"] for ks in per_sammantrade.values() for k in ks],),
    ):
        punkter_per_kallelse.setdefault(r["kallelse_id"], []).append(r)

    for sammantrade_id, kallelser in per_sammantrade.items():
        behandlingar = conn.execute(
            """
            SELECT DISTINCT ON (paragraf) paragraf, rubrik, diarienummer, ordning FROM behandling
            WHERE sammantrade_id = %s ORDER BY paragraf, ordning
            """,
            (sammantrade_id,),
        ).fetchall()
        behandlingar.sort(key=lambda b: b["ordning"])
        avv: list[str] = []
        for k in kallelser:
            if k["punkter_status"] in ("delvis_fel", "fel"):
                avv.append(f"{k['titel']}: kunde bara delvis läsas ({'; '.join(k['punkter_fel'])})"
                           if k["punkter_status"] == "delvis_fel"
                           else f"{k['titel']}: kunde inte läsas ({'; '.join(k['punkter_fel'])})")
            punkter = punkter_per_kallelse.get(k["id"], [])
            par = _para_ihop(punkter, behandlingar)
            for i, p in enumerate(punkter):
                if not p["diarienummer"]:
                    continue
                if i not in par:
                    avv.append(f"{k['titel']}: diarienumret {', '.join(p['diarienummer'])} "
                               f"(§ {p['paragraf']} {p['rubrik']}) liknar ingen paragraf i protokollet")
                    continue
                b = behandlingar[par[i]]
                nyckel = (sammantrade_id, b["paragraf"])
                # Protokollets diarienummer går före, och den senast publicerade kallelsen före de äldre.
                if not b["diarienummer"] and nyckel not in nya:
                    nya[nyckel] = (p["id"], tuple(p["diarienummer"]))
        avvikelser[sammantrade_id] = list(dict.fromkeys(avv))

    conn.execute("DELETE FROM kallelse_diarienummer")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO kallelse_diarienummer (sammantrade_id, paragraf, kallelsepunkt_id, diarienummer) "
            "VALUES (%s, %s, %s, %s)",
            [(s, p, pid, list(d)) for (s, p), (pid, d) in nya.items()],
        )
    conn.execute(
        "UPDATE sammantrade SET kallelse_avvikelser = '[]' WHERE kallelse_avvikelser <> '[]' AND NOT (id = ANY(%s))",
        (list(avvikelser),),
    )
    for s, avv in avvikelser.items():
        conn.execute("UPDATE sammantrade SET kallelse_avvikelser = %s WHERE id = %s", (Jsonb(avv), s))
    return sum(1 for k in set(fore) | set(nya) if fore.get(k) != nya.get(k))


class Kallelsenummer:
    """Diarienumren ur kallelsen för ett eller flera sammanträden, för läsning."""

    def __init__(self, conn: psycopg.Connection, sammantrade_ids: list[int]) -> None:
        self._rader: dict[tuple[int, int], dict] = {}
        if sammantrade_ids:
            for r in conn.execute(
                """
                SELECT kd.sammantrade_id, kd.paragraf, kd.diarienummer, p.sida, k.titel, k.url, k.typ
                FROM kallelse_diarienummer kd
                JOIN kallelsepunkt p ON p.id = kd.kallelsepunkt_id
                JOIN kallelse k ON k.id = p.kallelse_id
                WHERE kd.sammantrade_id = ANY(%s)
                """,
                (list(sammantrade_ids),),
            ):
                self._rader[(r["sammantrade_id"], r["paragraf"])] = r

    def satt(self, sammantrade_id: int, b: dict) -> dict:
        """Lägger på kallelsens diarienummer när protokollet saknar dem. Före rättelserna."""
        b["diarienummer_kallelse"] = None
        r = self._rader.get((sammantrade_id, b["paragraf"]))
        if r is not None and not b.get("diarienummer"):
            b["diarienummer"] = list(r["diarienummer"])
            b["diarienummer_kallelse"] = kalla(r)
        return b


def kalla(r: dict) -> dict:
    url = f"{r['url']}#page={r['sida']}" if r["sida"] else r["url"]
    return {"titel": r["titel"], "typ": r["typ"], "url": url, "sida": r["sida"]}


def efter_rattelser(b: dict) -> dict:
    """En publicerad rättelse av diarienumret går före kallelsen: markeringen tas bort."""
    if "diarienummer" in (b.get("rattelser") or {}):
        b["diarienummer_kallelse"] = None
    return b
