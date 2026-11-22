"""Behandlingar med publicerade rättelser (#101): det enda sättet att läsa behandlingar i listor.

`las` ger en rad per behandling (organ, sammanträde och paragraf) med de publicerade rättelserna
pålagda (ADR-0002). Typen räknas ur den rättade rubriken och det rättade beslutet, och kan själv vara
rättad. Raderna sorteras i ärendeordning: datum, organets beslutsnivå, paragraf. Ett sammanträde utan
datum kommer sist.

Detaljvyerna för ett sammanträde och en behandling (protokoll.py) läser alla rader med voteringar och
reservationer och ligger utanför.

Varje rad är en dict med nycklarna:

- `id`: behandlingens id (för hänvisningar och andra uppgifter knutna till raden)
- `sammantrade_id`, `datum`, `organ` (organets id), `tolkning` (sammanträdets tolkningsstatus)
- `paragraf`, `rubrik`, `beslut`, `diarienummer`, `typ`: rättade när en rättelse är publicerad
- `diarienummer_kallelse`: kallelsen (titel, typ, url till sidan, sida) när diarienumret kommer därifrån
  och inte från protokollet eller en rättelse (#109), annars None
- `rattelser`: per rättat fält {id, ursprungligt, nytt, motivering, publicerad}, bara när det finns
- `motionarer`: motionärerna enligt tolkningen, `motionarer_rattelse`: den publicerade rättelsen eller None
- `arende_id`: ärendet som behandlingen hör till, eller None
"""

from __future__ import annotations

from datetime import date

import psycopg

from .kallelsepunkter import Kallelsenummer, efter_rattelser
from .rattelser import Publicerade
from .sources.harnosand import NIVA

_FALT = ("paragraf", "rubrik", "beslut", "diarienummer")


def las(
    conn: psycopg.Connection,
    *,
    fran: int | None = None,
    till: int | None = None,
    organ: str | None = None,
    arende: int | None = None,
    rubrik: str | None = None,
) -> list[dict]:
    """Behandlingarna med publicerade rättelser.

    fran och till är år (båda inräknade) och utesluter sammanträden utan datum. organ är organets id,
    arende ett ärendes id och rubrik ett reguljärt uttryck (skiftlägesokänsligt) för den tolkade rubriken.
    """
    villkor = []
    if fran is not None:
        villkor.append("s.datum >= make_date(%(fran)s, 1, 1)")
    if till is not None:
        villkor.append("s.datum < make_date(%(till)s + 1, 1, 1)")
    if organ is not None:
        villkor.append("s.organ = %(organ)s")
    if arende is not None:
        villkor.append("a.arende_id = %(arende)s")
    if rubrik is not None:
        villkor.append("b.rubrik ~* %(rubrik)s")
    where = f"WHERE {' AND '.join(villkor)}" if villkor else ""
    rader = conn.execute(
        f"""
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf)
               b.id, b.sammantrade_id, b.paragraf, b.rubrik, b.beslut, b.diarienummer, b.motionarer,
               s.organ, s.datum, s.tolkning, a.arende_id
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        LEFT JOIN arende_behandling a ON a.sammantrade_id = b.sammantrade_id AND a.paragraf = b.paragraf
        {where}
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """,
        {"fran": fran, "till": till, "organ": organ, "arende": arende, "rubrik": rubrik},
    ).fetchall()
    sammantraden = list({r["sammantrade_id"] for r in rader})
    pub, kn = Publicerade(conn, sammantraden), Kallelsenummer(conn, sammantraden)
    ut = []
    for r in rader:
        # Protokollet, annars kallelsen, och en publicerad rättelse före båda.
        b = efter_rattelser(pub.behandling(r["sammantrade_id"], kn.satt(r["sammantrade_id"], {k: r[k] for k in _FALT})))
        ut.append(dict(r) | b | {"motionarer_rattelse": pub.motionarer(r["sammantrade_id"], r["paragraf"])})
    ut.sort(key=lambda r: (r["datum"] or date.max, NIVA.get(r["organ"], 0), r["paragraf"]))
    return ut
