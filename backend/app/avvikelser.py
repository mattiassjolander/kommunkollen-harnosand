"""Avvikelser i protokollen: en samlad lista att gå igenom och vid behov lämna till kommunen.

Tolkningen jämför protokollets delar med varandra och sparar det som inte stämmer (`avvikelser`).
En del avvikelser finns i själva protokollet, till exempel en voteringslista som inte stämmer med
protokollets text, eller en PDF som saknar sidor. Andra beror på att plattformen inte kunde läsa
en del av protokollet. Listan skiljer på dem så gott det går, men säger inte att protokollet är fel
förrän någon har tittat på originalet.

Publicerade rättelser (ADR-0002) räknas med, eftersom en rättelse visar att protokollet eller
tolkningen innehöll något som en redaktör har rättat.

Avvikelser mellan kallelsen och protokollet (#109) räknas också med: en kallelse som bara delvis kunde
läsas, och ett diarienummer i kallelsen vars rubrik inte liknar någon paragraf i protokollet. Varje rättelse listas med vad den rättar, före
och efter, motiveringen och var felet finns (#74): i protokollet, i inläsningen eller inte angivet.
Rättelser av fel i protokollet är felaktigheter i protokollet.
"""

from __future__ import annotations

import re

import psycopg

from .rattelser import FELET_I
from .sources.harnosand import organ_ref

# (kategori, regel). Den första regeln som passar avgör kategorin.
KATEGORIER = {
    "motsagelse": "Motsägelse i protokollet",
    "felskrivet": "Felskrivet i protokollet",
    "ofullstandigt": "Ofullständigt dokument",
    "paragrafer": "Paragraferna stämmer inte",
    "kallelsen": "Stämmer inte med kallelsen",
    "tolkning": "Kunde inte läsas av plattformen",
}
I_PROTOKOLLET = {"motsagelse", "felskrivet", "ofullstandigt"}
_REGLER = [
    ("motsagelse", re.compile(r"voteringslistan har .* protokollets text", re.I)),
    # Motkontrollen mot ärendelistan (#88): bara en rubrik som liknar ärendelistans men skiljer sig är ett
    # fel i protokollet. Övriga skillnader beror troligen på inläsningen.
    ("motsagelse", re.compile(r"skiljer sig från ärendelistan i protokollet", re.I)),
    ("felskrivet", re.compile(r"felskriven i protokollet", re.I)),
    ("ofullstandigt", re.compile(r"PDF:en (?:har \d+ av|saknar text)|paragrafprotokoll", re.I)),
    ("paragrafer", re.compile(r"paragrafintervall|samma paragraf förekommer", re.I)),
    ("kallelsen", re.compile(r"liknar ingen paragraf i protokollet", re.I)),
]


def kategori(avvikelse: str) -> str:
    return next((k for k, r in _REGLER if r.search(avvikelse)), "tolkning")


def lista(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None) -> dict:
    """Sammanträden för åren fran–till med avvikelser, ett otolkat protokoll eller publicerade rättelser."""
    rader = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.tolkning, s.avvikelser || s.kallelse_avvikelser AS avvikelser,
               d.typ AS dokument_typ, d.url,
               EXISTS (SELECT 1 FROM rattelse r WHERE r.sammantrade_id = s.id AND r.status = 'publicerad')
                 AS har_rattelser
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        WHERE s.datum >= make_date(%(fran)s, 1, 1) AND s.datum < make_date(%(till)s + 1, 1, 1)
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY s.datum DESC, s.id
        """,
        {"fran": fran, "till": till, "organ": organ},
    ).fetchall()
    rattelser: dict[int, list[dict]] = {}
    for r in conn.execute(
        """
        SELECT r.id, r.sammantrade_id, r.objekt, r.paragraf, r.votering, r.namn, r.falt, r.ursprungligt, r.nytt,
               r.motivering, r.felet_i, r.publicerad,
               (SELECT rubrik FROM behandling b WHERE b.sammantrade_id = r.sammantrade_id AND b.paragraf = r.paragraf
                ORDER BY ordning LIMIT 1) AS rubrik
        FROM rattelse r
        WHERE r.status = 'publicerad' AND r.sammantrade_id = ANY(%s)
        ORDER BY r.paragraf NULLS FIRST, r.votering NULLS FIRST, r.namn, r.falt
        """,
        ([r["id"] for r in rader if r["har_rattelser"]],),
    ):
        rattelser.setdefault(r["sammantrade_id"], []).append({
            "id": r["id"], "objekt": r["objekt"], "paragraf": r["paragraf"], "votering": r["votering"],
            "namn": r["namn"] or None, "rubrik": r["rubrik"], "falt": r["falt"], "ursprungligt": r["ursprungligt"],
            "nytt": r["nytt"], "motivering": r["motivering"], "felet_i": r["felet_i"], "publicerad": r["publicerad"],
        })
    ut = []
    for r in rader:
        avv = [{"text": a, "kategori": kategori(a)} for a in r["avvikelser"]]
        if r["dokument_typ"] == "paragrafprotokoll":
            avv.append({"text": "Bara paragrafprotokoll finns, inte hela protokollet", "kategori": "ofullstandigt"})
        if r["tolkning"] == "ej_tolkad" and not avv:
            avv.append({"text": "Protokollet kunde inte tolkas", "kategori": "tolkning"})
        ratt = rattelser.get(r["id"], [])
        if not avv and not ratt:
            continue
        ut.append({
            "sammantrade": {"id": r["id"], "datum": r["datum"], "organ": organ_ref(r["organ"]), "tolkning": r["tolkning"]},
            "url": r["url"],
            "avvikelser": avv,
            "i_protokollet": any(a["kategori"] in I_PROTOKOLLET for a in avv)
            or any(x["felet_i"] == "protokollet" for x in ratt),
            "felaktigheter": sum(1 for x in ratt if x["felet_i"] == "protokollet"),
            "rattelser": ratt,
        })
    antal = {k: sum(1 for s in ut for a in s["avvikelser"] if a["kategori"] == k) for k in KATEGORIER}
    return {
        "fran": fran,
        "till": till,
        "organ": organ_ref(organ) if organ else None,
        "kategorier": [{"id": k, "namn": n, "i_protokollet": k in I_PROTOKOLLET, "antal": antal[k]}
                       for k, n in KATEGORIER.items()],
        "felet_i": [{"id": f, "antal": sum(1 for x in ut for y in x["rattelser"] if y["felet_i"] == f)}
                    for f in (*FELET_I, None)],
        "sammantraden": ut,
        "granskade": len(rader),
    }
