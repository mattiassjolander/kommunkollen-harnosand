"""Undersökningar (#67): SCB:s medborgarundersökning, SKR:s Insikt och anmälda brott från Brå, via Kolada.

Katalogen anger vilka nyckeltal som hämtas och hur sidan "Undersökningar" visar dem. Alla hämtas för
Härnösand och för riket (Kolada, kommun-id 0000) som referens. Texterna beskriver vad nyckeltalen mäter
och värderar inte resultaten (kravspec avsnitt 18).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ekonomi

# Alla nyckeltal i Kolada vars titel börjar med "Medborgarundersökningen -". Härnösand har värden från 2021.
MEDBORGARUNDERSOKNINGEN = [
    "N00528", "N00529", "N00530", "N00531", "N00532", "N00533", "N00534", "N00535", "N00536", "N00544",
    "N00545", "N00546", "N00547", "N00548", "N00549", "N00550", "N00551", "N00552", "N00553", "N00556",
    "N00557", "N00558", "N00559", "N00561", "N00562", "N00563", "N00564", "N00570", "N00571", "N00572",
    "N00573", "N00574", "N00575", "N00576", "N00577", "N00578", "N00586", "N00587", "N00588", "N00589",
    "N00590", "N00591", "N00592", "N00593", "N00594", "N00595", "N00596", "N00597", "N00598", "N00599",
    "N00600", "N00601", "N00602", "N00603", "N00604", "N00605", "N00606", "N00607", "N00608", "N00609",
    "N00610", "N00611", "N00612", "N00613", "N00614", "N00615", "N00616", "N00617", "N00618", "N00619",
    "N00620", "N00621", "N00622", "N00623", "N00624", "N00625", "N00626", "N00627", "N00628", "N00629",
    "N00630", "N00631", "N00632", "N00633", "N00634", "N00635", "N00636", "N00637", "N00638", "N00640",
    "N00641", "N00646", "N00647", "N00649", "N00650", "N00651", "N00652", "N00653", "N00654", "N00655",
    "N00656", "N00657", "N00658", "N00659", "N00660", "N00661", "N00662", "N00664", "N00665", "N00666",
    "N00667", "N00668", "N00669", "N00670",
]

INSIKT_NY = "U07453"  # Totalt, index, ny definition (från 2024)
INSIKT_GAMMAL = "U07451"  # Totalt, index, gammal definition (till 2024)
INSIKT = [
    INSIKT_NY,
    INSIKT_GAMMAL,
    "U07446",  # Brandskydd
    "U07447",  # Bygglov
    "U07448",  # Markupplåtelse
    "U07449",  # Miljö- och hälsoskydd
    "U07450",  # Serveringstillstånd
]

# Anmälda brott per 100 000 invånare (Brå via Kolada).
BROTT = [
    "N07540",  # brott totalt
    "N07403",  # våldsbrott
    "N07536",  # brott mot frihet och frid
    "N07537",  # sexualbrott
    "N07544",  # narkotikabrott
    "N07546",  # bostadsinbrott
    "N07547",  # bilbrott
    "N07548",  # trafikbrott
    "N07402",  # grov kvinnofridskränkning
]

# Det Kolada-källan hämtar, för kommunen och riket.
KOLADA = [*MEDBORGARUNDERSOKNINGEN, *INSIKT, *BROTT]


@dataclass(frozen=True)
class Metodbyte:
    """Källan har ändrat hur ett nyckeltal räknas. Serierna före och efter visas separat och slås aldrig ihop."""

    ar: int
    text: str
    serier: list[tuple[str, str]]  # (mått-id, namn i diagrammet), den gamla definitionen först


@dataclass(frozen=True)
class Delgrupp:
    titel: str
    matt: list[str]
    metodbyte: Metodbyte | None = None


@dataclass(frozen=True)
class Avsnitt:
    id: str
    titel: str
    kalla: str  # vem som tar fram uppgifterna, och att de hämtas från Kolada
    ingress: str
    grupper: list[Delgrupp]
    # Fast text om vad uppgifterna mäter, som alltid visas.
    om_matningen: str | None = None


def _k(*ids: str) -> list[str]:
    return [f"kolada:{i}" for i in ids]


AVSNITT = [
    Avsnitt(
        "medborgarundersokningen",
        "Medborgarundersökningen",
        "SCB/Kolada",
        "SCB:s medborgarundersökning skickas varje år till ett urval av kommunens invånare som är 18 år eller "
        "äldre. Värdena är andelen av dem som svarat på frågan. Här visas ett urval av frågorna. Alla "
        "frågor finns längst ned.",
        [
            # Svarsfrekvensen och antalet svar först, eftersom de påverkar hur säkra resultaten är.
            Delgrupp("Svar", _k("N00529", "N00528")),
            Delgrupp("Helhet", _k("N00667", "N00670", "N00668")),
            Delgrupp(
                "Verksamheter som fungerar bra",
                _k("N00530", "N00531", "N00532", "N00533", "N00534", "N00535", "N00536"),
            ),
            Delgrupp(
                "Förtroende och inflytande",
                _k("N00664", "N00657", "N00661", "N00662", "N00669", "N00650", "N00646"),
            ),
            Delgrupp("Bemötande", _k("N00640", "N00641", "N00647")),
            Delgrupp("Trygghet", _k("N00610", "N00614", "N00622", "N00631")),
        ],
        om_matningen="Svarsfrekvensen och antalet svar påverkar hur säkra resultaten är: ju färre som svarat, "
        "desto större osäkerhet. Från och med 2025 redovisar SCB svarsfrekvensen viktad, och den går då inte "
        "att jämföra med tidigare år.",
    ),
    Avsnitt(
        "insikt",
        "Insikt",
        "SKR/Kolada",
        "SKR:s undersökning Insikt frågar företag som haft ett ärende hos kommunen hur de bedömer kommunens "
        "service i myndighetsutövningen. Resultatet är ett index på en skala från 0 till 100. Ett värde "
        "redovisas bara när tillräckligt många företag har svarat.",
        [
            Delgrupp(
                "Totalindex",
                _k(INSIKT_GAMMAL, INSIKT_NY),
                Metodbyte(
                    2024,
                    "Från och med 2024 räknar SKR totalindex på fyra myndighetsområden i stället för sex. Den "
                    "gamla och den nya definitionen visas som separata serier och slås inte ihop.",
                    [(f"kolada:{INSIKT_GAMMAL}", "Gammal definition (till 2024)"),
                     (f"kolada:{INSIKT_NY}", "Ny definition (från 2024)")],
                ),
            ),
            Delgrupp("Per myndighetsområde", _k("U07446", "U07447", "U07448", "U07449", "U07450")),
        ],
    ),
    Avsnitt(
        "anmalda-brott",
        "Anmälda brott",
        "Brå/Kolada",
        "Brottsförebyggande rådets statistik över anmälda brott i kommunen, per 100 000 invånare.",
        [Delgrupp("Anmälda brott per 100 000 invånare", _k(*BROTT))],
        om_matningen="Statistiken visar brott som har anmälts, inte hur många brott som faktiskt begås. Antalet "
        "anmälda brott påverkas av hur benägna människor är att anmäla, och av polisens och andra myndigheters "
        "egna insatser. Brott som oftast upptäcks genom kontroller, som narkotikabrott och trafikbrott, "
        "beror mycket på hur många kontroller som görs.",
    ),
]


def nyckeltal(conn, matt_id: str, omrade: str) -> dict:
    """Ett nyckeltal som ekonomisidans kort visar det: kommunens serie och genomsnittet för riket."""
    return {
        "id": matt_id,
        "prisniva": None,  # inga kronbelopp
        "serie": ekonomi.las_nyckeltal(conn, matt_id, omrade),
        "riket": ekonomi.las_riket(conn, matt_id),
    }


def las(conn, omrade: str) -> dict:
    avsnitt = [
        {
            "id": a.id,
            "titel": a.titel,
            "kalla": a.kalla,
            "ingress": a.ingress,
            "om_matningen": a.om_matningen,
            "grupper": [
                {
                    "titel": g.titel,
                    "nyckeltal": [nyckeltal(conn, m, omrade) for m in g.matt],
                    "metodbyte": (
                        {"ar": g.metodbyte.ar, "text": g.metodbyte.text,
                         "serier": [{"id": i, "namn": n} for i, n in g.metodbyte.serier]}
                        if g.metodbyte else None
                    ),
                }
                for g in a.grupper
            ],
        }
        for a in AVSNITT
    ]
    # Alla frågor i medborgarundersökningen, för analysverktyget. Bara de som har hämtats.
    titlar = {
        r["id"]: r["titel"]
        for r in conn.execute("SELECT id, titel FROM matt WHERE id = ANY(%s)", (_k(*MEDBORGARUNDERSOKNINGEN),))
    }
    alla = [{"id": m, "titel": titlar[m]} for m in _k(*MEDBORGARUNDERSOKNINGEN) if m in titlar]
    return {"omrade": omrade, "avsnitt": avsnitt, "medborgarundersokningen": alla}


def i_katalogen(matt_id: str) -> bool:
    return matt_id in _k(*KOLADA)
