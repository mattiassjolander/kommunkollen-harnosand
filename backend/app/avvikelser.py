"""Avvikelser i protokollen: en samlad lista att gå igenom och vid behov lämna till kommunen.

Tolkningen jämför protokollets delar med varandra och sparar det som inte stämmer (`avvikelser`).
En del avvikelser finns i själva protokollet, till exempel en voteringslista som inte stämmer med
protokollets text, eller en PDF som saknar sidor. Andra beror på att plattformen inte kunde läsa
en del av protokollet. Listan skiljer på dem så gott det går, men säger inte att protokollet är fel
förrän någon har tittat på originalet.

Publicerade rättelser (ADR-0002) räknas med, eftersom en rättelse visar att protokollet eller
tolkningen innehöll något som en redaktör har rättat.
"""

from __future__ import annotations

import re

import psycopg

from .sources.harnosand import organ_ref

# (kategori, regel). Den första regeln som passar avgör kategorin.
KATEGORIER = {
    "motsagelse": "Motsägelse i protokollet",
    "felskrivet": "Felskrivet i protokollet",
    "ofullstandigt": "Ofullständigt dokument",
    "paragrafer": "Paragraferna stämmer inte",
    "tolkning": "Kunde inte läsas av plattformen",
}
I_PROTOKOLLET = {"motsagelse", "felskrivet", "ofullstandigt"}
_REGLER = [
    ("motsagelse", re.compile(r"voteringslistan har .* protokollets text", re.I)),
    ("felskrivet", re.compile(r"felskriven i protokollet", re.I)),
    ("ofullstandigt", re.compile(r"PDF:en (?:har \d+ av|saknar text)|paragrafprotokoll", re.I)),
    ("paragrafer", re.compile(r"paragrafintervall|samma paragraf förekommer", re.I)),
]


def kategori(avvikelse: str) -> str:
    return next((k for k, r in _REGLER if r.search(avvikelse)), "tolkning")


def lista(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None) -> dict:
    """Sammanträden för åren fran–till med avvikelser, ett otolkat protokoll eller publicerade rättelser."""
    rader = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.tolkning, s.avvikelser, d.typ AS dokument_typ, d.url,
               (SELECT count(*) FROM rattelse r WHERE r.sammantrade_id = s.id AND r.status = 'publicerad') AS rattelser
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        WHERE s.datum >= make_date(%(fran)s, 1, 1) AND s.datum < make_date(%(till)s + 1, 1, 1)
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY s.datum DESC, s.id
        """,
        {"fran": fran, "till": till, "organ": organ},
    ).fetchall()
    ut = []
    for r in rader:
        avv = [{"text": a, "kategori": kategori(a)} for a in r["avvikelser"]]
        if r["dokument_typ"] == "paragrafprotokoll":
            avv.append({"text": "Bara paragrafprotokoll finns, inte hela protokollet", "kategori": "ofullstandigt"})
        if r["tolkning"] == "ej_tolkad" and not avv:
            avv.append({"text": "Protokollet kunde inte tolkas", "kategori": "tolkning"})
        if not avv and not r["rattelser"]:
            continue
        ut.append({
            "sammantrade": {"id": r["id"], "datum": r["datum"], "organ": organ_ref(r["organ"]), "tolkning": r["tolkning"]},
            "url": r["url"],
            "avvikelser": avv,
            "i_protokollet": any(a["kategori"] in I_PROTOKOLLET for a in avv),
            "rattelser": r["rattelser"],
        })
    antal = {k: sum(1 for s in ut for a in s["avvikelser"] if a["kategori"] == k) for k in KATEGORIER}
    return {
        "fran": fran,
        "till": till,
        "organ": organ_ref(organ) if organ else None,
        "kategorier": [{"id": k, "namn": n, "i_protokollet": k in I_PROTOKOLLET, "antal": antal[k]}
                       for k, n in KATEGORIER.items()],
        "sammantraden": ut,
        "granskade": len(rader),
    }
