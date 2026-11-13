"""Ekonomiska nyckeltal (kravspec 3.1 och 3.3): vilka mått som samlas in och hur ekonomivyn grupperar dem.

Täckningen mot kravspecen redovisas i docs/tackning-ekonomi.md. Ändras katalogen ska den filen
uppdateras samtidigt.
"""

from __future__ import annotations

from dataclasses import dataclass

from .sources.scb import Differens, ScbMatt

KOLADA = [
    "N03007",  # Årets resultat, kr/inv
    "N03102",  # Årets resultat som andel av skatt & generella statsbidrag, %
    "N03010",  # Skatteintäkter, kr/inv
    "N03009",  # Generella statsbidrag och utjämning, kr/inv
    "N03011",  # Verksamhetens nettokostnader, kr/inv
    "N03100",  # Nettokostnad som andel av skatt och generella statsbidrag, %
    "N03132",  # Nettoinvesteringar totalt, kr/inv
    "N03103",  # Självfinansieringsgrad för investeringar, %
    "N03046",  # Långfristiga skulder, kr/inv
    "N03047",  # Kortfristiga skulder, kr/inv
    "N03044",  # Avsättning för pensioner och löneskatt, kr/inv
    "N03048",  # Pensionsförpliktelser och löneskatt utanför balansräkningen, kr/inv
    "N03105",  # Kassalikviditet, %
    "N03002",  # Soliditet inklusive pensionsåtaganden, %
    "N03106",  # Soliditet (exklusive pensionsförpliktelser utanför balansräkningen), %
]

SCB = [
    ScbMatt("ResultKnN", "120", "Årets resultat", "Kommunens resultat enligt resultaträkningen: intäkter minus kostnader, inklusive finansiella poster."),
    ScbMatt("ResultKnN", "040", "Skatteintäkter", "Intäkter från kommunalskatten, inklusive slutavräkningar."),
    ScbMatt("ResultKnN", "050", "Generella statsbidrag och utjämning", "Statsbidrag som inte är knutna till en viss verksamhet, plus nettot från de kommunalekonomiska utjämningssystemen."),
    ScbMatt("SkatteIntKnN", "080", "Bidrag från utjämningssystemen och generella statsbidrag", "Det kommunen får från inkomst-, kostnads- och LSS-utjämningen, regleringsbidrag och generella bidrag från staten (brutto)."),
    ScbMatt("SkatteIntKnN", "160", "Avgifter till utjämningssystemen", "Det kommunen betalar in till utjämningssystemen, t.ex. kostnadsutjämnings- och regleringsavgift."),
    ScbMatt("ResultKnN", "030", "Verksamhetens nettokostnader", "Verksamheternas kostnader minus deras egna intäkter (avgifter, riktade bidrag m.m.), inklusive avskrivningar. Redovisas som negativt tal."),
    ScbMatt("BalansKnN", "081", "Långfristiga lån i banker och kreditinstitut", "Kommunens långfristiga lån, främst hos Kommuninvest och banker. Den del som ska betalas inom ett år ingår inte."),
    ScbMatt("BalansKnN", "089", "Långfristiga skulder", "Skulder som förfaller senare än om ett år: lån, skulder till koncernföretag och förutbetalda investeringsbidrag."),
    ScbMatt("BalansKnN", "098", "Kortfristiga skulder", "Skulder som förfaller inom ett år, t.ex. leverantörsskulder, semesterlöneskuld och kortfristig del av lån."),
    ScbMatt("BalansKnN", "072", "Pensionsavsättningar i balansräkningen", "Avsättningar för pensioner och särskild löneskatt som redovisas som skuld i balansräkningen."),
    ScbMatt("BalansKnN", "065", "Likvida medel", "Kassa och bank vid årets slut."),
    ScbMatt("BalansKnN", "069", "Omsättningstillgångar", "Tillgångar som kan omsättas inom ett år: likvida medel, kortfristiga fordringar och placeringar, förråd och exploateringsfastigheter."),
    ScbMatt("BalansKnN", "075", "Eget kapital", "Eget kapital vid årets slut: tillgångar minus skulder och avsättningar."),
]

RORELSEKAPITAL = Differens(
    id="scb:rorelsekapital",
    titel="Rörelsekapital",
    beskrivning="Omsättningstillgångar minus kortfristiga skulder. Beräknat av Kommunkollen från SCB:s balansräkning.",
    plus="scb:BalansKnN:069",
    minus="scb:BalansKnN:098",
)


@dataclass(frozen=True)
class Grupp:
    id: str
    titel: str
    matt: list[str]


GRUPPER = [
    Grupp("resultat", "Resultat", ["kolada:N03007", "kolada:N03102", "scb:ResultKnN:120"]),
    Grupp("intakter", "Skatter, statsbidrag och utjämning", [
        "scb:ResultKnN:040", "kolada:N03010", "scb:ResultKnN:050", "kolada:N03009",
        "scb:SkatteIntKnN:080", "scb:SkatteIntKnN:160",
    ]),
    Grupp("kostnader", "Kostnader och investeringar", [
        "scb:ResultKnN:030", "kolada:N03011", "kolada:N03100", "kolada:N03132", "kolada:N03103",
    ]),
    Grupp("skulder", "Skulder och pensioner", [
        "scb:BalansKnN:081", "scb:BalansKnN:089", "kolada:N03046", "scb:BalansKnN:098", "kolada:N03047",
        "scb:BalansKnN:072", "kolada:N03044", "kolada:N03048",
    ]),
    Grupp("stallning", "Likviditet och soliditet", [
        "scb:BalansKnN:065", "kolada:N03105", "scb:BalansKnN:069", "scb:rorelsekapital", "kolada:N03002", "kolada:N03106",
        "scb:BalansKnN:075",
    ]),
]


def prisniva(enhet: str) -> str | None:
    """Alla kronbelopp från Kolada och SCB redovisas i löpande priser. Ingen av källorna har fasta priser."""
    return "löpande priser" if "kr" in enhet else None
