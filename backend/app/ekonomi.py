"""Ekonomiska nyckeltal (kravspec 3.1 och 3.3): vilka mått som samlas in och hur ekonomivyn grupperar dem.

Täckningen mot kravspecen redovisas i docs/tackning-ekonomi.md. Ändras katalogen ska den filen
uppdateras samtidigt.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import serier
from .sources.kolada import RIKET
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


# Beräknat av Kommunkollen vid läsning: SCB:s långfristiga lån delat med folkmängden från Kolada.
LANESKULD_PER_INVANARE = "kommunkollen:laneskuld-per-invanare"
LAN = "scb:BalansKnN:081"
INVANARE = "kolada:N01951"


@dataclass(frozen=True)
class Kort:
    """Ett kort per företeelse. Redovisar SCB totalt och Kolada per invånare får kortet växeln
    Totalt (mnkr) / Per invånare. Kortets id är `matt`."""

    matt: str
    per_invanare: str | None = None


@dataclass(frozen=True)
class Grupp:
    id: str
    titel: str  # en fråga en invånare kan ställa (ADR-0007)
    ingress: str
    kort: list[Kort]

    @property
    def matt(self) -> list[str]:
        return [m for k in self.kort for m in (k.matt, k.per_invanare) if m]


GRUPPER = [
    Grupp(
        "resultat",
        "Går kommunen med överskott?",
        "Årets resultat är skillnaden mellan kommunens intäkter och kostnader under året, inklusive finansiella poster.",
        [Kort("scb:ResultKnN:120", "kolada:N03007"), Kort("kolada:N03102")],
    ),
    Grupp(
        "intakter",
        "Var kommer pengarna ifrån?",
        "Det mesta av kommunens pengar kommer från kommunalskatten och från generella statsbidrag och utjämning. "
        "Avgifter och riktade bidrag räknas av från verksamhetens kostnader och syns inte här.",
        [
            Kort("scb:ResultKnN:040", "kolada:N03010"),
            Kort("scb:ResultKnN:050", "kolada:N03009"),
            Kort("scb:SkatteIntKnN:080"),
            Kort("scb:SkatteIntKnN:160"),
        ],
    ),
    Grupp(
        "kostnader",
        "Vad kostar verksamheten och investeringarna?",
        "Verksamhetens nettokostnader betalas med skatter, generella statsbidrag och utjämning. "
        "Investeringar betalas med årets resultat, avskrivningar eller lån.",
        [
            Kort("scb:ResultKnN:030", "kolada:N03011"),
            Kort("kolada:N03100"),
            Kort("kolada:N03132"),
            Kort("kolada:N03103"),
        ],
    ),
    Grupp(
        "skulder",
        "Hur mycket är lånat och vad är utlovat i pensioner?",
        "Kommunens lån och övriga skulder, och de pensioner som kommunen har lovat sina anställda. "
        "En del av pensionerna redovisas som skuld i balansräkningen och en del utanför.",
        [
            Kort(LAN, LANESKULD_PER_INVANARE),
            Kort("scb:BalansKnN:089", "kolada:N03046"),
            Kort("scb:BalansKnN:098", "kolada:N03047"),
            Kort("scb:BalansKnN:072", "kolada:N03044"),
            Kort("kolada:N03048"),
        ],
    ),
    Grupp(
        "stallning",
        "Klarar kommunen sina betalningar?",
        "Likviditeten visar hur mycket som finns att betala med på kort sikt. "
        "Soliditeten visar hur stor del av tillgångarna som är finansierad med eget kapital.",
        [
            Kort("scb:BalansKnN:065"),
            Kort("kolada:N03105"),
            Kort("scb:BalansKnN:069"),
            Kort("scb:rorelsekapital"),
            Kort("kolada:N03002"),
            Kort("kolada:N03106"),
            Kort("scb:BalansKnN:075"),
        ],
    ),
]


@dataclass(frozen=True)
class Huvudtal:
    matt: str
    kort: str  # kortet som huvudtalet länkar till
    titel: str  # kortare än källans titel
    forklaring: str  # en mening i klartext om vad måttet betyder, utan värdering


HUVUDTAL = [
    Huvudtal("kolada:N03102", "kolada:N03102", "Årets resultat, andel av skatter och statsbidrag",
             "Andel av skatteintäkterna och de generella statsbidragen som blev kvar efter årets kostnader."),
    Huvudtal("kolada:N03100", "kolada:N03100", "Nettokostnadsandel",
             "Andel av skatteintäkterna och de generella statsbidragen som gick till verksamhetens nettokostnader."),
    Huvudtal("kolada:N03103", "kolada:N03103", "Självfinansieringsgrad för investeringar",
             "Andel av årets investeringar som betalades med egna medel, alltså resultat och avskrivningar, utan nya lån."),
    Huvudtal("kolada:N03002", "kolada:N03002", "Soliditet inklusive pensionsåtaganden",
             "Andel av tillgångarna som är finansierad med eget kapital, när alla pensionsåtaganden räknas som skuld."),
    Huvudtal(LANESKULD_PER_INVANARE, LAN, "Låneskuld per invånare",
             "Kommunens långfristiga lån i banker och kreditinstitut delat med antalet invånare."),
]


# Kopplingar mellan korten (#81): "Hänger ihop med". Nyckeln är kortets id, och varje samband pekar på ett
# annat kort (eller skatteunderlagsprognosen) med en saklig mening om räknesambandet, utan värdering.
SKATTEUNDERLAGSPROGNOS = "skatteunderlagsprognos"


@dataclass(frozen=True)
class Samband:
    till: str  # kortets id, eller SKATTEUNDERLAGSPROGNOS
    text: str


SAMBAND: dict[str, list[Samband]] = {
    "scb:ResultKnN:120": [
        Samband("kolada:N03102", "Årets resultat delat med skatteintäkterna och de generella statsbidragen och utjämningen."),
        Samband("scb:ResultKnN:030", "Verksamhetens nettokostnader dras av från skatter och statsbidrag i resultatet."),
        Samband("scb:BalansKnN:075", "Årets resultat ökar eller minskar det egna kapitalet."),
    ],
    "kolada:N03102": [
        Samband("scb:ResultKnN:120", "Samma resultat i kronor."),
        Samband("kolada:N03100", "Räknas på samma intäkter: skatter och generella statsbidrag och utjämning."),
    ],
    "scb:ResultKnN:040": [
        Samband(SKATTEUNDERLAGSPROGNOS, "SKR:s prognos för skatteintäkterna de kommande åren."),
        Samband("kolada:N03100", "Nettokostnadsandelen räknas mot skatteintäkterna och de generella statsbidragen."),
        Samband("scb:ResultKnN:050", "Tillsammans med skatteintäkterna det som ska räcka till verksamhetens nettokostnader."),
    ],
    "scb:ResultKnN:050": [
        Samband("scb:SkatteIntKnN:080", "Bidragen från utjämningssystemen och de generella statsbidragen, brutto."),
        Samband("scb:SkatteIntKnN:160", "Avgifterna till utjämningssystemen dras av från bidragen i nettot."),
        Samband("kolada:N03100", "Nettokostnadsandelen räknas mot skatteintäkterna och de generella statsbidragen."),
    ],
    "scb:SkatteIntKnN:080": [
        Samband("scb:SkatteIntKnN:160", "Bidragen minus avgifterna ingår i nettot för generella statsbidrag och utjämning."),
        Samband("scb:ResultKnN:050", "Nettot som redovisas i resultaträkningen."),
    ],
    "scb:SkatteIntKnN:160": [
        Samband("scb:SkatteIntKnN:080", "Avgifterna dras av från bidragen."),
        Samband("scb:ResultKnN:050", "Nettot som redovisas i resultaträkningen."),
    ],
    "scb:ResultKnN:030": [
        Samband("kolada:N03100", "Nettokostnaderna delat med skatteintäkterna och de generella statsbidragen."),
        Samband("scb:ResultKnN:120", "Nettokostnaderna dras av i årets resultat."),
    ],
    "kolada:N03100": [
        Samband("scb:ResultKnN:030", "Täljaren: verksamhetens nettokostnader."),
        Samband("scb:ResultKnN:040", "Nämnaren: skatteintäkterna, tillsammans med generella statsbidrag och utjämning."),
        Samband("kolada:N03102", "Räknas på samma intäkter som resultatandelen."),
    ],
    "kolada:N03132": [
        Samband("kolada:N03103", "Hur stor del av investeringarna som betalades med egna medel."),
        Samband("scb:BalansKnN:081", "Det som inte betalas med egna medel kan betalas med lån."),
    ],
    "kolada:N03103": [
        Samband("kolada:N03132", "Investeringarna som självfinansieringsgraden räknas på."),
        Samband("scb:BalansKnN:081", "Investeringar som inte självfinansieras kan betalas med lån."),
    ],
    "scb:BalansKnN:081": [
        Samband("kolada:N03103", "Investeringar som inte självfinansieras kan betalas med lån."),
        Samband("scb:BalansKnN:089", "Lånen ingår i de långfristiga skulderna."),
    ],
    "scb:BalansKnN:089": [
        Samband("scb:BalansKnN:081", "Lånen i banker och kreditinstitut, som ingår i de långfristiga skulderna."),
        Samband("kolada:N03106", "Skulderna är en del av det som inte är eget kapital i soliditeten."),
    ],
    "scb:BalansKnN:098": [
        Samband("scb:rorelsekapital", "Rörelsekapitalet är omsättningstillgångarna minus de kortfristiga skulderna."),
        Samband("kolada:N03105", "Kassalikviditeten jämför de likvida tillgångarna med de kortfristiga skulderna."),
    ],
    "scb:BalansKnN:072": [
        Samband("kolada:N03106", "Avsättningarna är skuld i balansräkningen och ingår i båda soliditetsmåtten."),
        Samband("kolada:N03048", "Pensioner intjänade före 1998 redovisas utanför balansräkningen."),
    ],
    "kolada:N03048": [
        Samband("kolada:N03002", "Soliditeten inklusive pensionsåtaganden räknar även förpliktelserna utanför balansräkningen som skuld."),
        Samband("scb:BalansKnN:072", "Pensionerna som redovisas i balansräkningen."),
    ],
    "scb:BalansKnN:065": [
        Samband("kolada:N03105", "De likvida medlen ingår i kassalikviditeten."),
        Samband("scb:BalansKnN:069", "Likvida medel är en del av omsättningstillgångarna."),
    ],
    "kolada:N03105": [
        Samband("scb:BalansKnN:065", "De likvida medlen ingår i kassalikviditeten."),
        Samband("scb:BalansKnN:098", "Kassalikviditeten räknas mot de kortfristiga skulderna."),
    ],
    "scb:BalansKnN:069": [
        Samband("scb:rorelsekapital", "Rörelsekapitalet är omsättningstillgångarna minus de kortfristiga skulderna."),
        Samband("scb:BalansKnN:065", "Likvida medel är en del av omsättningstillgångarna."),
    ],
    "scb:rorelsekapital": [
        Samband("scb:BalansKnN:069", "Omsättningstillgångarna, det som räknas med."),
        Samband("scb:BalansKnN:098", "De kortfristiga skulderna, som dras av."),
        Samband("kolada:N03105", "Kassalikviditeten jämför också tillgångar och kortfristiga skulder, men utan förråd och exploateringsfastigheter."),
    ],
    "kolada:N03002": [
        Samband("scb:BalansKnN:075", "Soliditeten är det egna kapitalet delat med de totala tillgångarna."),
        Samband("kolada:N03106", "Skillnaden mellan måtten är pensionsförpliktelserna utanför balansräkningen."),
        Samband("kolada:N03048", "Förpliktelserna som räknas som skuld i det här måttet."),
    ],
    "kolada:N03106": [
        Samband("scb:BalansKnN:075", "Soliditeten är det egna kapitalet delat med de totala tillgångarna."),
        Samband("kolada:N03002", "Samma mått när även pensionsförpliktelserna utanför balansräkningen räknas som skuld."),
    ],
    "scb:BalansKnN:075": [
        Samband("kolada:N03002", "Det egna kapitalet delat med tillgångarna, med alla pensionsåtaganden som skuld."),
        Samband("kolada:N03106", "Det egna kapitalet delat med tillgångarna."),
        Samband("scb:ResultKnN:120", "Årets resultat ökar eller minskar det egna kapitalet."),
    ],
}


def laneskuld_per_invanare(lan: dict | None, invanare: dict | None) -> dict | None:
    """Långfristiga lån (tkr, SCB) delat med folkmängden (Kolada), i kr/inv. Ett år där någon av
    uppgifterna saknas blir saknat, aldrig noll."""
    if lan is None:
        return None
    folk = {p["period"]: p for p in (invanare or {}).get("punkter", [])}
    punkter = []
    for p in lan["punkter"]:
        f = folk.get(p["period"])
        varde = None
        if p["varde"] is not None and f and f["varde"]:
            varde = round(p["varde"] * 1000 / f["varde"])
        tider = [p] + ([f] if f else [])
        punkter.append({
            "period": p["period"],
            "varde": varde,
            "kallans_publicering": p["kallans_publicering"],
            "hamtad": max(t["hamtad"] for t in tider),
            "version": p["version"],
            "senast_hamtad": max(t["senast_hamtad"] for t in tider),
            "senast_andrad": max(t["senast_andrad"] for t in tider),
            "reviderad": False,
            "historik": [],
        })
    return {
        "matt": {
            "id": LANESKULD_PER_INVANARE,
            "titel": "Låneskuld per invånare",
            "beskrivning": "Långfristiga lån i banker och kreditinstitut (SCB, BalansKnN post 081) delat med antalet "
            "invånare den 31 december (Kolada N01951). Beräknat av Kommunkollen.",
            "enhet": "kr/inv",
            "kallans_publicering": lan["matt"]["kallans_publicering"],
            "datakalla": {
                "id": "kommunkollen",
                "titel": "Beräknat av Kommunkollen ur SCB och Kolada",
                "url": lan["matt"]["datakalla"]["url"],
            },
        },
        "omrade": lan["omrade"],
        "punkter": punkter,
    }


def las_riket(conn, matt_id: str) -> dict | None:
    """Genomsnittet för riket (Kolada, kommun-id 0000) för ett Kolada-mått, annars None. SCB-måtten och
    de beräknade måtten har ingen motsvarighet för riket i insamlingen."""
    if not matt_id.startswith("kolada:"):
        return None
    serie = serier.las_serie(conn, matt_id, RIKET)
    return serie if serie and serie["punkter"] else None


def las_nyckeltal(conn, matt_id: str, omrade: str) -> dict | None:
    """Ett nyckeltals serie. Låneskulden per invånare beräknas vid läsningen."""
    if matt_id == LANESKULD_PER_INVANARE:
        return laneskuld_per_invanare(serier.las_serie(conn, LAN, omrade), serier.las_serie(conn, INVANARE, omrade))
    return serier.las_serie(conn, matt_id, omrade)


def prisniva(enhet: str) -> str | None:
    """Alla kronbelopp från Kolada och SCB redovisas i löpande priser. Ingen av källorna har fasta priser."""
    return "löpande priser" if "kr" in enhet else None
