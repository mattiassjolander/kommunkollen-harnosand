"""Ekonomiska flöden (kravspec 4): hur kommunens intäkter flödar till verksamhetsområdena under ett år.

Modellen bygger på SCB:s räkenskapssammandrag och är ett **bruttoflöde** i
**räkenskapssammandragets verksamhetsindelning**, inte kommunens nämnder.

    intäktstyper  →  Kommunens intäkter  →  verksamhetsområden, avskrivningar, finansiella kostnader, resultat

- Intäktssidan summerar till resultaträkningens intäkter: skatt, generella statsbidrag och utjämning,
  verksamhetens intäkter (fördelade på kontopost) och finansiella intäkter.
- Ett verksamhetsområdes flöde är dess externa bruttokostnad i driftredovisningen:
  bruttokostnad minus interna intäkter (det området sålt till andra områden) och minus kalkylerade
  kapitalkostnader (internt pris för kapital; de verkliga avskrivningarna visas för sig). Så räknas
  interna poster inte två gånger. Gemensamma verksamheter ingår i områdena genom fördelningen.
- Det som resultaträkningens kostnader inte går att fördela på ett område visas öppet som en egen post.
- Ett år där någon uppgift saknas markeras som ofullständigt och fylls inte ut.

Alla belopp är i tkr, löpande priser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import psycopg

from .sources.scb import TABELLER, ScbMatt

INDELNING = "Räkenskapssammandragets verksamhetsindelning (SCB), inte kommunens nämnder"
FLODESTYP = "brutto"
INVANARE = "kolada:N01951"

OMRADEN = [
    ("190", "Politisk verksamhet"),
    ("290", "Infrastruktur, skydd m.m."),
    ("390", "Kultur och fritid"),
    ("490", "Pedagogisk verksamhet"),
    ("590", "Vård och omsorg"),
    ("690", "Särskilt riktade insatser"),
    ("890", "Affärsverksamhet"),
]
BRUTTOKOSTNAD, INTERNA_INTAKTER, KAPITALKOSTNADER = "000000Z3", "000000Z7", "000000YY"

# Driftredovisningens kostnadsposter. Tillsammans summerar de exakt till bruttokostnaden (Z3).
KOSTNADSPOSTER = {
    "000000YR": "löner",
    "000000YS": "kalkylerad personalomkostnad",
    "000000YT": "varor m.m.",
    "000000YU": "köp av huvudverksamhet",
    "000000YV": "övriga externa kostnader",
    "000000YW": "lämnade bidrag",
    "000000YX": "externa lokalhyror",
    KAPITALKOSTNADER: "kalkylerade kapitalkostnader",
    "000000YZ": "interna lokalkostnader",
    "000000Z0": "internt köp och övriga interna kostnader",
    "000000Z1": "fördelad gemensam verksamhet, kommunnyckel",
    "000000Z2": "fördelad gemensam verksamhet, SCB-nyckel",
}

_INNEHALL = {
    BRUTTOKOSTNAD: "bruttokostnad",
    INTERNA_INTAKTER: "interna intäkter",
    **KOSTNADSPOSTER,
}

# Mått som modellen behöver utöver ekonomivyns. Samlas in av SCB-källan.
SCB_MATT = [
    ScbMatt("ResultKnN", "010", "Verksamhetens intäkter", "Verksamheternas egna intäkter enligt resultaträkningen."),
    ScbMatt("ResultKnN", "022", "Verksamhetens kostnader", "Verksamheternas kostnader enligt resultaträkningen, exklusive avskrivningar."),
    ScbMatt("ResultKnN", "025", "Avskrivningar", "Årets avskrivningar på anläggningstillgångar."),
    ScbMatt("ResultKnN", "060", "Finansiella intäkter", "Ränteintäkter, utdelningar och andra finansiella intäkter."),
    ScbMatt("ResultKnN", "072", "Finansiella kostnader", "Räntekostnader och andra finansiella kostnader."),
    ScbMatt("ResultKnN", "085", "Extraordinära poster (netto)", "Extraordinära intäkter minus extraordinära kostnader."),
    ScbMatt("SkatteIntKnN", "150", "Generella bidrag från staten", "Generella statsbidrag som inte är knutna till en viss verksamhet."),
    ScbMatt("VerksInt", "290", "Taxor och avgifter", "Intäkter från taxor och avgifter."),
    ScbMatt("VerksInt", "490", "Hyror och arrenden", "Intäkter från hyror och arrenden."),
    ScbMatt("VerksInt", "590", "Bidrag", "Kostnadsersättningar och bidrag till verksamheten, totalt."),
    ScbMatt("VerksInt", "390", "Försäljning av verksamhet och tjänster", "Intäkter från försäljning av verksamhet och tjänster."),
    ScbMatt("VerksInt", "500", "Riktade bidrag från staten", "Kostnadsersättningar och riktade bidrag från staten och statliga myndigheter."),
    ScbMatt("VerksInt", "510", "Riktade bidrag från Arbetsförmedlingen", "Kostnadsersättningar och riktade bidrag från Arbetsförmedlingen."),
    ScbMatt("VerksInt", "525", "Ersättning för personlig assistans", "Ersättning från Försäkringskassan för personlig assistans."),
    *[
        ScbMatt("Driftredovisning", kod, f"{namn}, {_INNEHALL[innehall]}",
                f"Driftredovisningen för verksamhetsområdet {namn.lower()}: {_INNEHALL[innehall]}.", innehall=innehall)
        for kod, namn in OMRADEN
        for innehall in _INNEHALL
    ],
]


def _id(tabell: str, post: str, innehall: str | None = None) -> str:
    return f"scb:{tabell}:{post}" + (f":{innehall}" if innehall else "")


R = lambda post: _id("ResultKnN", post)  # noqa: E731
V = lambda post: _id("VerksInt", post)  # noqa: E731


@dataclass(frozen=True)
class Post:
    """En nod i flödet. Värdet är summan av termerna. Ett negativt värde byter sida."""

    id: str
    titel: str
    termer: list[tuple[int, str]]  # (tecken, mått-id)
    titel_om_negativ: str | None = None
    forklaring: str = ""
    # Får saknas om summorna ändå går ihop (t.ex. extraordinära poster, som inte redovisas före 2019).
    valfri: bool = False


INTAKTER = [
    Post("kommunalskatt", "Kommunalskatt", [(1, R("040"))]),
    Post("generella_statsbidrag", "Generella statsbidrag", [(1, _id("SkatteIntKnN", "150"))]),
    Post("utjamning", "Utjämning och regleringsbidrag (netto)", [(1, R("050")), (-1, _id("SkatteIntKnN", "150"))],
         titel_om_negativ="Utjämning och regleringsavgift (netto)",
         forklaring="Bidrag från de kommunalekonomiska utjämningssystemen, inklusive regleringsbidraget, minus avgifter "
                    "till dem. Det mesta av statens generella stöd till kommunen kommer den här vägen."),
    Post("riktade_statsbidrag", "Riktade statsbidrag", [(1, V("500")), (1, V("510")), (1, V("525"))],
         forklaring="Kostnadsersättningar och riktade bidrag från staten, Arbetsförmedlingen och Försäkringskassan."),
    Post("ovriga_bidrag", "Övriga bidrag", [(1, V("590")), (-1, V("500")), (-1, V("510")), (-1, V("525"))],
         forklaring="Bidrag från EU, andra kommuner, regioner, föreningar och övriga, samt momsersättning."),
    Post("avgifter", "Taxor och avgifter", [(1, V("290"))]),
    Post("hyror", "Hyror och arrenden", [(1, V("490"))]),
    Post("forsaljning", "Försäljning av verksamhet", [(1, V("390"))]),
    Post("ovriga_intakter", "Övriga verksamhetsintäkter",
         [(1, R("010")), (-1, V("290")), (-1, V("490")), (-1, V("590")), (-1, V("390"))],
         forklaring="Verksamhetens intäkter enligt resultaträkningen som inte är avgifter, hyror, bidrag eller försäljning, t.ex. reavinster."),
    Post("finansiella_intakter", "Finansiella intäkter", [(1, R("060"))]),
    Post("extraordinara", "Extraordinära poster", [(1, R("085"))], titel_om_negativ="Extraordinära poster",
         valfri=True),
]

VERKSAMHETER = [
    Post(f"omrade_{kod}", namn, [
        (1, _id("Driftredovisning", kod, BRUTTOKOSTNAD)),
        (-1, _id("Driftredovisning", kod, INTERNA_INTAKTER)),
        (-1, _id("Driftredovisning", kod, KAPITALKOSTNADER)),
    ], forklaring="Extern bruttokostnad: bruttokostnad minus interna intäkter och kalkylerade kapitalkostnader.")
    for kod, namn in OMRADEN
]

OVRIGA_UTFLODEN = [
    Post("avskrivningar", "Avskrivningar", [(-1, R("025"))]),
    Post("finansiella_kostnader", "Finansiella kostnader", [(-1, R("072"))]),
    Post("resultat", "Årets överskott", [(1, R("120"))], titel_om_negativ="Årets underskott",
         forklaring="Årets resultat. Ett underskott finansieras med eget kapital och visas därför på intäktssidan."),
]

EJ_FORDELAT = Post(
    "ej_fordelat", "Ej fördelat på verksamhetsområde", [(-1, R("022"))],
    titel_om_negativ="Avstämningsdifferens mot verksamhetsindelningen",
    forklaring="Verksamhetens kostnader enligt resultaträkningen som inte syns i något verksamhetsområde, "
               "t.ex. pensionskostnader som bokförs centralt.",
)

ALLA_MATT = sorted(
    {mid for p in [*INTAKTER, *VERKSAMHETER, *OVRIGA_UTFLODEN, EJ_FORDELAT] for _, mid in p.termer} | {INVANARE}
)


def _d(kod: str, innehall: str) -> tuple[int, str]:
    return (1, _id("Driftredovisning", kod, innehall))


def _neg(term: tuple[int, str]) -> tuple[int, str]:
    return (-term[0], term[1])


def fordjupningsposter(kod: str) -> tuple[list[Post], list[Post]]:
    """Ett verksamhetsområdes bruttokostnad: varifrån den finansieras och vilka kostnadsslag den består av."""
    d = lambda innehall: _d(kod, innehall)  # noqa: E731
    finansiering = [
        Post("fran_kommunen", "Från kommunens intäkter", [d(BRUTTOKOSTNAD), _neg(d(INTERNA_INTAKTER)),
                                                         _neg(d(KAPITALKOSTNADER))],
             forklaring="Samma belopp som flödet till området på kommunnivån: extern bruttokostnad."),
        Post("interna_poster", "Interna poster", [d(INTERNA_INTAKTER), d(KAPITALKOSTNADER)],
             titel_om_negativ="Interna poster",
             forklaring="Interna intäkter från andra verksamheter och kalkylerade kapitalkostnader. De är "
                        "omföringar inom kommunen och räknas därför inte på kommunnivån, där de faktiska "
                        "avskrivningarna och räntorna visas i stället."),
    ]
    kostnadsslag = [
        Post("personal", "Personal", [d("000000YR"), d("000000YS")],
             forklaring="Löner och kalkylerade personalomkostnader (arbetsgivaravgifter, pensioner m.m.)."),
        Post("lokaler", "Lokaler", [d("000000YX"), d("000000YZ")],
             forklaring="Externa lokalhyror och interna lokalkostnader."),
        Post("kop_av_tjanster", "Köp av tjänster", [d("000000YU")],
             forklaring="Köp av huvudverksamhet, t.ex. från privata utförare, andra kommuner eller regionen."),
        Post("material", "Material och varor", [d("000000YT")]),
        Post("kapitalkostnader", "Kapitalkostnader", [d(KAPITALKOSTNADER)],
             forklaring="Kalkylerade kapitalkostnader (avskrivningar och internränta) för områdets anläggningar."),
        Post("ovrigt", "Övrigt", [d("000000YV"), d("000000YW"), d("000000Z0"), d("000000Z1"), d("000000Z2")],
             forklaring="Övriga externa kostnader, lämnade bidrag, interna köp och områdets andel av "
                        "gemensamma verksamheter."),
    ]
    return finansiering, kostnadsslag


ALLA_MATT = sorted(set(ALLA_MATT) | {
    mid for kod, _ in OMRADEN for p in sum(fordjupningsposter(kod), []) for _, mid in p.termer
})


@dataclass
class Nod:
    id: str
    titel: str
    sida: str  # "in" | "ut"
    belopp: Decimal
    forklaring: str
    kallor: list[str] = field(default_factory=list)  # mått-id


def _kallor(post: Post) -> list[dict]:
    tabeller = sorted({mid.split(":")[1] for _, mid in post.termer if mid.startswith("scb:")})
    return [{"titel": f"SCB, räkenskapssammandraget, tabell {t}", "url": TABELLER[t].url} for t in tabeller]


def las_varden(conn: psycopg.Connection, omrade: str) -> dict[str, dict[str, Decimal | None]]:
    rader = conn.execute(
        """
        SELECT DISTINCT ON (matt_id, period) matt_id, period, varde
        FROM observation WHERE omrade = %s AND matt_id = ANY(%s)
        ORDER BY matt_id, period, version DESC
        """,
        (omrade, ALLA_MATT),
    ).fetchall()
    varden: dict[str, dict[str, Decimal | None]] = {}
    for r in rader:
        varden.setdefault(r["matt_id"], {})[r["period"]] = r["varde"]
    return varden


def tillgangliga_ar(varden: dict[str, dict[str, Decimal | None]]) -> list[str]:
    return sorted(varden.get(R("120"), {}))


def _ofullstandig(grund: dict, saknas: list[str]) -> dict:
    return grund | {"fullstandig": False, "saknas": saknas, "noder": [], "floden": [], "totalt": None,
                    "invanare": None}


def _saknade(varden: dict, ar: str, poster: list[Post], extra: set[str] = frozenset()) -> list[str]:
    behov = {mid for p in poster if not p.valfri for _, mid in p.termer} | set(extra)
    return sorted(mid for mid in behov if varden.get(mid, {}).get(ar) is None)


def _summa(varden: dict, ar: str, post: Post) -> Decimal:
    return sum((tecken * (varden.get(mid, {}).get(ar) or 0) for tecken, mid in post.termer), Decimal(0))


def _bygg(grund: dict, poster: list[tuple[Post, str, Decimal]], mitt: dict, invanare: Decimal | None) -> dict:
    """Noder och flöden kring en mittnod. Ett negativt belopp byter sida, ett nollbelopp hoppas över."""
    noder: list[dict] = []
    for p, sida, belopp in poster:
        if belopp == 0:
            continue
        negativ = belopp < 0
        if negativ:  # ett negativt belopp är ett flöde åt andra hållet
            sida = "ut" if sida == "in" else "in"
        noder.append({
            "id": p.id,
            "titel": (p.titel_om_negativ or p.titel) if negativ else p.titel,
            "sida": sida,
            "belopp": float(abs(belopp)),
            "forklaring": p.forklaring,
            "kallor": _kallor(p),
        })

    totalt_in = sum(Decimal(str(n["belopp"])) for n in noder if n["sida"] == "in")
    totalt_ut = sum(Decimal(str(n["belopp"])) for n in noder if n["sida"] == "ut")
    if abs(totalt_in - totalt_ut) > 1:
        # Går in- och utflöden inte ihop saknas något i underlaget. Visa inget hellre än något felaktigt.
        return _ofullstandig(grund, [f"{mitt['summa_titel']} går inte ihop (differens {totalt_in - totalt_ut} tkr)"])
    floden = []
    for n in noder:
        fran, till = (n["id"], mitt["id"]) if n["sida"] == "in" else (mitt["id"], n["id"])
        floden.append({
            "fran": fran,
            "till": till,
            "belopp": n["belopp"],
            "andel": n["belopp"] / float(totalt_in),
            "kr_per_invanare": None if not invanare else n["belopp"] * 1000 / float(invanare),
            "kallor": n["kallor"],
        })
    noder.append({"id": mitt["id"], "titel": mitt["titel"], "sida": "mitt", "belopp": float(totalt_in),
                  "forklaring": mitt["forklaring"], "kallor": []})
    return grund | {
        "fullstandig": True,
        "saknas": [],
        "noder": noder,
        "floden": floden,
        "totalt": float(totalt_in),
        "differens": float(totalt_in - totalt_ut),
        "invanare": None if invanare is None else int(invanare),
    }


def _grund(ar: str) -> dict:
    return {"ar": ar, "flodestyp": FLODESTYP, "indelning": INDELNING, "enhet": "tkr", "prisniva": "löpande priser",
            "verksamhet": None}


def modell(varden: dict[str, dict[str, Decimal | None]], ar: str, mattitlar: dict[str, str]) -> dict:
    """Kommunnivån: intäkter → Kommunens intäkter → verksamhetsområden och övriga utflöden."""
    grund = _grund(ar)
    saknas = _saknade(varden, ar, [*INTAKTER, *VERKSAMHETER, *OVRIGA_UTFLODEN, EJ_FORDELAT])
    if saknas:
        return _ofullstandig(grund, [mattitlar.get(m, m) for m in saknas])

    poster: list[tuple[Post, str, Decimal]] = [(p, "in", _summa(varden, ar, p)) for p in INTAKTER]
    verksamheter = [(p, "ut", _summa(varden, ar, p)) for p in VERKSAMHETER]
    poster += verksamheter
    poster.append((EJ_FORDELAT, "ut", _summa(varden, ar, EJ_FORDELAT) - sum(b for _, _, b in verksamheter)))
    poster += [(p, "ut", _summa(varden, ar, p)) for p in OVRIGA_UTFLODEN]
    mitt = {"id": "kommunen", "titel": "Kommunens intäkter", "forklaring": "Alla intäkter samlade, innan de används.",
            "summa_titel": "Resultaträkningen"}
    return _bygg(grund, poster, mitt, varden.get(INVANARE, {}).get(ar))


OMRADESNAMN = dict(OMRADEN)


def fordjupning(varden: dict[str, dict[str, Decimal | None]], ar: str, kod: str, mattitlar: dict[str, str]) -> dict:
    """Ett verksamhetsområde: finansiering → områdets bruttokostnad → kostnadsslag."""
    namn = OMRADESNAMN[kod]
    grund = _grund(ar) | {"verksamhet": {"kod": kod, "id": f"omrade_{kod}", "titel": namn}}
    finansiering, kostnadsslag = fordjupningsposter(kod)
    saknas = _saknade(varden, ar, [*finansiering, *kostnadsslag], {_id("Driftredovisning", kod, BRUTTOKOSTNAD)})
    if saknas:
        return _ofullstandig(grund, [mattitlar.get(m, m) for m in saknas])
    poster = [(p, "in", _summa(varden, ar, p)) for p in finansiering]
    poster += [(p, "ut", _summa(varden, ar, p)) for p in kostnadsslag]
    mitt = {"id": f"omrade_{kod}", "titel": f"{namn}, bruttokostnad",
            "forklaring": "Områdets bruttokostnad enligt driftredovisningen.",
            "summa_titel": "Driftredovisningen"}
    return _bygg(grund, poster, mitt, varden.get(INVANARE, {}).get(ar))


def jamfor(nu: dict, tidigare: dict) -> dict:
    """Lägger till förändringen mot ett annat år för varje flöde, i kronor och procent.

    Flöden paras ihop på sin yttre nod. Har ett flöde bytt riktning (t.ex. ett överskott som blivit
    ett underskott) räknas det tidigare beloppet som negativt.
    """
    resultat = nu | {"jamforelse_ar": tidigare["ar"], "jamforelse_fullstandig": tidigare["fullstandig"]}
    if not (nu["fullstandig"] and tidigare["fullstandig"]):
        return resultat

    def yttre(f: dict, mitt: str) -> tuple[str, str]:
        return (f["fran"], "in") if f["till"] == mitt else (f["till"], "ut")

    mitt_nu = next(n["id"] for n in nu["noder"] if n["sida"] == "mitt")
    mitt_da = next(n["id"] for n in tidigare["noder"] if n["sida"] == "mitt")
    titlar_da = {n["id"]: n["titel"] for n in tidigare["noder"]}
    da = {yttre(f, mitt_da)[0]: (yttre(f, mitt_da)[1], f["belopp"]) for f in tidigare["floden"]}
    floden = []
    for f in nu["floden"]:
        nod, sida = yttre(f, mitt_nu)
        if nod not in da:
            floden.append(f | {"jamforelse": {"belopp": None, "titel": None, "forandring": None, "procent": None}})
            continue
        sida_da, belopp_da = da[nod]
        signerat = belopp_da if sida_da == sida else -belopp_da
        forandring = f["belopp"] - signerat
        floden.append(f | {"jamforelse": {
            "belopp": belopp_da,
            "titel": titlar_da[nod],
            "forandring": forandring,
            "procent": None if signerat == 0 else forandring / abs(signerat),
        }})
    resultat["floden"] = floden
    resultat["jamforelse_totalt"] = tidigare["totalt"]
    return resultat
