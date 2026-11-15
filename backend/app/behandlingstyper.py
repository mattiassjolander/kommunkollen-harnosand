"""Behandlingstyp: vad en behandling är, utläst ur rubrik och beslutstext (#44).

Klassningen är regelbaserad (ADR-0002) och gissar aldrig. En behandling som inte passar någon
regel och saknar beslutstext får ingen typ (None). Reglerna prövas i den ordning de står, så att
till exempel "Svar på motion" blir en motion och inte ett förslag till ett annat organ.

En redaktör kan rätta typen (rattelser.py). Typen räknas fram när behandlingen läses, ur den
rättade rubriken och det rättade beslutet om sådana finns.
"""

from __future__ import annotations

import re

# id → visningsnamn, i den ordning de visas.
TYPER: dict[str, str] = {
    "beslut": "Beslut",
    "forslag": "Förslag till annat organ",
    "motion": "Motion",
    "medborgarforslag": "Medborgarförslag",
    "interpellation": "Interpellation eller fråga",
    "information": "Informationsärende",
    "formalia": "Formalia",
}

_MOTION = re.compile(r"^(?:svar på\s+)?(?:remiss\s+(?:angående|gällande)\s+)?motion(?:en)?\b", re.I)
# I Härnösand lämnas medborgarförslag som e-förslag.
_MEDBORGARFORSLAG = re.compile(r"^(?:svar på\s+)?(?:e-förslag|medborgarförslag)", re.I)
_FORMALIA = re.compile(
    r"justerare|justering av protokoll|dagordning|föredragningslista|eventuellt tillkommande ärende"
    r"|tillkommande motioner|^övrigt\b|^upprop|^sammanträdets öppnande|^öppnande|^parentation",
    re.I,
)
_INTERPELLATION = re.compile(
    r"^interpellation|korta frågor|frågestund|inkomna frågor|frågor och svar|^frågor?\b|^enkel fråga", re.I
)
_INFORMATION = re.compile(
    r"informationsärenden|^information\b|kännedom|^anmälan av|delegationsbeslut|delegeringsbeslut|delgivning"
    r"|meddelanden|^skrivelser|rapporterar|^övriga rapporter|^rapporter\b|^ärenden hos",
    re.I,
)
# "Socialnämnden beslutar att tacka för informationen och lägga den till handlingarna."
_TILL_HANDLINGARNA = re.compile(
    r"^\S+(?:\s\S+)?\s+beslutar\s+att\s+(?:tacka för (?:informationen|redovisningen)(?: och)?\s+)?"
    r"lägga\s+[^.]{0,120}?\s+till handlingarna\.?$",
    re.I,
)
# "Kommunstyrelsen föreslår kommunfullmäktige besluta", "Samhällsnämnden föreslår kommunstyrelsen att …".
# Inte "Skolförvaltningen föreslår skolnämnden besluta": där är det nämnden som beslutar.
_FORESLAR = re.compile(r"^(?:kommunstyrelsen|\S*nämnden)\s+föreslår\s+(?:kommunfullmäktige|kommunstyrelsen|\S*nämnden)\b",
                       re.I)
_BESLUTAR = re.compile(r"\bbesluta[rt]?\b", re.I)


def klassa(rubrik: str | None, beslut: str | None) -> str | None:
    rubrik = " ".join((rubrik or "").split())
    beslut = " ".join((beslut or "").split())
    if _MOTION.search(rubrik):
        return "motion"
    if _MEDBORGARFORSLAG.search(rubrik):
        return "medborgarforslag"
    if _FORMALIA.search(rubrik):
        return "formalia"
    if _INTERPELLATION.search(rubrik):
        return "interpellation"
    if _INFORMATION.search(rubrik) or _TILL_HANDLINGARNA.match(beslut):
        return "information"
    if _FORESLAR.search(beslut):
        return "forslag"
    if _BESLUTAR.search(beslut):
        return "beslut"
    return None
