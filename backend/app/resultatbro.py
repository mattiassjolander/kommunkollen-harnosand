"""Brodiagram för årets resultat (#81): skatteintäkter + generella statsbidrag och utjämning
− verksamhetens nettokostnader ± finansnetto (± extraordinära poster) = årets resultat.

Alla delar kommer ur SCB:s resultaträkning (ResultKnN) i tkr. Delarna kontrolleras mot årets resultat
enligt SCB. En avvikelse visas och döljs inte. Saknas en del räknas skillnaden fram som restposten
"Övrigt inklusive finansnetto", märkt Beräknat av Kommunkollen.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from . import serier

RESULTAT = "scb:ResultKnN:120"
# Avrundning i källan: SCB redovisar hela tkr.
TOLERANS_TKR = 1.0


@dataclass(frozen=True)
class Steg:
    id: str
    titel: str
    termer: list[str]  # mått-id som summeras
    markering: str | None = None  # när steget inte är en rad i källan
    bara_om_skilt_fran_noll: bool = False


STEG = [
    Steg("skatteintakter", "Skatteintäkter", ["scb:ResultKnN:040"]),
    Steg("statsbidrag", "Generella statsbidrag och utjämning", ["scb:ResultKnN:050"]),
    Steg("nettokostnader", "Verksamhetens nettokostnader", ["scb:ResultKnN:030"]),
    Steg("finansnetto", "Finansnetto", ["scb:ResultKnN:060", "scb:ResultKnN:072"],
         markering="Summerat av Kommunkollen ur SCB: finansiella intäkter och finansiella kostnader"),
    Steg("extraordinart", "Extraordinära poster", ["scb:ResultKnN:085"], bara_om_skilt_fran_noll=True),
]
REST = Steg("ovrigt", "Övrigt inklusive finansnetto", [], markering="Beräknat av Kommunkollen")


def _ar(varden: dict[str, dict[str, float | None]], ar: str) -> dict | None:
    resultat = varden[RESULTAT].get(ar)
    steg = []
    saknas = []
    for s in STEG:
        termer = [varden[t].get(ar) for t in s.termer]
        if any(v is None for v in termer):
            saknas.append(s)
            continue
        v = sum(termer)
        if s.bara_om_skilt_fran_noll and v == 0:
            continue
        steg.append({"id": s.id, "titel": s.titel, "varde": v, "matt": s.termer, "markering": s.markering})
    # Utan resultat eller utan intäkter och nettokostnader finns ingen bro att visa.
    if resultat is None or any(s.id in ("skatteintakter", "statsbidrag", "nettokostnader") for s in saknas):
        return None
    summa = sum(s["varde"] for s in steg)
    rest = None
    if saknas:
        rest = resultat - summa
        steg.append({"id": REST.id, "titel": REST.titel, "varde": rest,
                     "matt": [t for s in saknas for t in s.termer], "markering": REST.markering})
        summa += rest
    avvikelse = resultat - summa
    return {
        "steg": steg,
        "resultat": resultat,
        # Kontrollen: delarna ska summera till årets resultat enligt SCB.
        "kontroll": {
            "summa_av_delar": summa,
            "avvikelse": avvikelse if abs(avvikelse) > TOLERANS_TKR else 0.0,
            "restpost": rest is not None,
        },
    }


def bro(varden: dict[str, dict[str, float | None]]) -> dict:
    """Bron per år ur mått-id → period → värde (tkr). Standardår är senaste året med fullständigt underlag."""
    alla_ar = sorted(varden.get(RESULTAT, {}))
    ar = {a: b for a in alla_ar if (b := _ar(varden, a))}
    fullstandiga = [a for a, b in ar.items() if not b["kontroll"]["restpost"]]
    return {
        "enhet": "tkr",
        "ar": ar,
        "standardar": (fullstandiga or list(ar) or [None])[-1],
    }


def matt() -> list[str]:
    return [RESULTAT, *(t for s in STEG for t in s.termer)]


def las(conn: psycopg.Connection, omrade: str) -> dict:
    varden: dict[str, dict[str, float | None]] = {}
    kallor: dict[str, dict] = {}
    for m in matt():
        s = serier.las_serie(conn, m, omrade)
        varden[m] = {p["period"]: p["varde"] for p in (s["punkter"] if s else [])}
        if s:
            kallor[m] = {"titel": s["matt"]["titel"], "datakalla": s["matt"]["datakalla"],
                         "kallans_publicering": s["matt"]["kallans_publicering"]}
    return bro(varden) | {"matt": kallor, "resultat_matt": RESULTAT}
