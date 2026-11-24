"""Kontroller av protokollet mot sig självt (#47): uppgifter i samma protokoll som inte stämmer med varandra.

Det som hittas är protokollavvikelser, möjliga fel i källan som kan anmälas till kommunen. De skiljer sig från
tolkningens egna avvikelser (`Tolkning.avvikelser`), som oftast beror på att plattformen inte kunde läsa något.
Varje kontroll är därför försiktig: den hoppar över det som tolkningen själv har flaggat, och en avvikelse
beskriver bara vad som står i protokollet, med paragraf och sida, inte vem som gjort fel.

Kontrollerna körs vid varje tolkning och omtolkning. En avvikelse identifieras av sin `nyckel` inom sammanträdet,
så att redaktörens status (`protokollavvikelser`) bevaras när protokollet tolkas om.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .protokolltolkning import PARTILOS, Narvaro, Tolkning, beslutande_vid

TYPER = {
    "rostsumma": "Rösterna stämmer inte med antalet beslutande",
    "parti_olika": "Olika parti i närvarolistan och voteringslistan",
    "ersattare": "Ersättare för en beslutande ledamot",
    "paragrafnummer": "Paragrafnumren stämmer inte",
    "parti_saknas": "Parti saknas i närvarolistan",
    "stavning": "Namnet stavas olika",
}


@dataclass
class Fynd:
    typ: str
    # Identifierar avvikelsen inom sammanträdet, också efter en omtolkning.
    nyckel: str
    paragraf: int | None
    sida: int | None
    text: str


def kontrollera(t: Tolkning, sidor: list[str], intervall: list[int] | None = None) -> list[Fynd]:
    """Alla kontroller för en tolkning. `sidor` är protokollets sidtexter i löpande ordning och `intervall`
    paragraferna som försättsbladet anger."""
    if not t.tolkad:
        return []
    fynd = [
        *_rostsumma(t),
        *_parti_olika(t, sidor),
        *_ersattare(t, sidor),
        *_paragrafnummer(t, sidor, intervall or []),
        *_parti_saknas(t, sidor),
        *([] if t.ocr else _stavning(t, sidor)),
    ]
    sedda: set[str] = set()
    return [f for f in fynd if not (f.nyckel in sedda or sedda.add(f.nyckel))]


# Hjälpfunktioner

def _norm(text: str) -> str:
    return " ".join(text.split())


def _sidnummer(sida: str, index: int) -> int:
    m = re.search(r"\b(\d+)\(\d+\)", sida)
    return int(m[1]) if m else index + 1


def _sida_med(sidor: list[str], text: str, fran: int | None = None) -> int | None:
    """Numret på den första sidan, från och med sidan `fran` (som den numreras), där texten står."""
    sokt = _norm(text)
    traffar = [(_sidnummer(s, i), i) for i, s in enumerate(sidor) if sokt in _norm(s)]
    if fran is not None:
        efter = [n for n, _ in traffar if n >= fran]
        if efter:
            return efter[0]
    return traffar[0][0] if traffar else None


def _narvarolistan_finns(t: Tolkning) -> bool:
    return bool(t.narvaro) and not any(a.startswith("Närvarolistan") for a in t.avvikelser)


def _paragrafer(lista: list[int]) -> str:
    return "§ " + ", ".join(map(str, lista))


# Kontrollerna

def _rostsumma(t: Tolkning) -> list[Fynd]:
    """Summan av rösterna i en votering stämmer inte med antalet beslutande vid paragrafen.

    Jämförelsen görs bara när tolkningen av närvarolistan går att lita på för paragrafen: med en voteringslista
    ska alla som röstar finnas i närvarolistan, och utan en lista får ingen beslutande ha egna paragrafer.
    Annars kan skillnaden bero på tolkningen.
    """
    if not _narvarolistan_finns(t):
        return []
    alla_namn = {n.namn for n in t.narvaro}
    begransad = any(n.kategori == "beslutande" and n.paragrafer is not None for n in t.narvaro)
    ut = []
    for b in t.behandlingar:
        beslutande = len(beslutande_vid(t.narvaro, b.paragraf))
        for v_nr, v in enumerate(b.voteringar, 1):
            if v.roster:
                if any(r.rost != "franvarande" and r.namn not in alla_namn for r in v.roster):
                    continue
                ja, nej, avstar = (sum(1 for r in v.roster if r.rost == x) for x in ("ja", "nej", "avstar"))
            elif v.ja is not None and v.nej is not None and not begransad:
                ja, nej, avstar = v.ja, v.nej, v.avstar or 0
            else:
                continue
            summa = ja + nej + avstar
            if summa == beslutande:
                continue
            rad = f"{ja} ja, {nej} nej" + (f" och {avstar} avstår" if avstar else "")
            ut.append(Fynd(
                "rostsumma", f"rostsumma|{b.paragraf}|{v_nr}", b.paragraf, b.sida,
                f"§ {b.paragraf}, votering {v_nr}: rösterna är {rad}, sammanlagt {summa}. "
                f"Närvarolistan anger {beslutande} beslutande vid paragrafen.",
            ))
    return ut


def _parti_olika(t: Tolkning, sidor: list[str]) -> list[Fynd]:
    """En person står med olika parti i närvarolistan och voteringslistan."""
    i_narvaro: dict[str, set[str]] = {}
    for n in t.narvaro:
        if n.kategori != "ovrig" and n.parti:
            i_narvaro.setdefault(n.namn, set()).add(n.parti)
    ut = []
    for b in t.behandlingar:
        for v in b.voteringar:
            for r in v.roster:
                partier = i_narvaro.get(r.namn or "")
                if not r.parti or not partier or r.parti in partier or len(partier) > 1:
                    continue
                [p] = partier
                ut.append(Fynd(
                    "parti_olika", f"parti_olika|{r.namn}|{p}|{r.parti}", b.paragraf,
                    _sida_med(sidor, r.namn, b.sida) or b.sida,
                    f"{r.namn} står som ({_visa(p)}) i närvarolistan och som ({_visa(r.parti)}) i voteringslistan "
                    f"vid § {b.paragraf}.",
                ))
    return ut


def _visa(parti: str) -> str:
    return "-" if parti == PARTILOS else parti


def _ersattare(t: Tolkning, sidor: list[str]) -> list[Fynd]:
    """En ersättare tjänstgör för någon som själv står som beslutande vid samma paragraf.

    En ledamot med klockslag i närvarolistan ("Agneta Jonsson (S) kl. 09.15 – 14.25") var bara med en del av
    sammanträdet, och ersättaren kan ha tjänstgjort under resten. Det räknas inte.
    """
    alla = [b.paragraf for b in t.behandlingar]
    rader = [_norm(r) for s in sidor for r in s.splitlines()]
    ut = []
    for n in t.narvaro:
        if n.kategori != "beslutande" or not n.tjanstgor_for:
            continue
        if any(_osaker_rad(r, n, t) for r in rader):
            continue
        egna = sorted({p for p in (n.paragrafer if n.paragrafer is not None else alla) if p not in n.jav})
        krock = [p for p in egna if any(m.namn == n.tjanstgor_for and not m.tjanstgor_for
                                         for m in beslutande_vid(t.narvaro, p))]
        if krock and egna:
            ut.append(Fynd(
                "ersattare", f"ersattare|{n.namn}|{n.tjanstgor_for}", krock[0], _forsta_sida(t, krock[0]),
                f"{n.namn} tjänstgör för {n.tjanstgor_for}, som själv står som beslutande vid "
                f"{_paragrafer(krock)}." if len(krock) < len(set(alla)) else
                f"{n.namn} tjänstgör för {n.tjanstgor_for}, som själv står som beslutande i närvarolistan.",
            ))
    # I en voteringslista: en ersättare röstar för en ledamot som själv röstar i samma votering.
    for b in t.behandlingar:
        for v_nr, v in enumerate(b.voteringar, 1):
            roster = {r.namn for r in v.roster if r.namn}
            for r in v.roster:
                if r.ersatt and r.ersatt in roster:
                    ut.append(Fynd(
                        "ersattare", f"ersattare|{r.namn}|{r.ersatt}|{b.paragraf}|{v_nr}", b.paragraf, b.sida,
                        f"§ {b.paragraf}, votering {v_nr}: {r.namn} röstar för {r.ersatt}, som själv röstar "
                        "i samma votering.",
                    ))
    return ut


def _osaker_rad(rad: str, ersattare: Narvaro, t: Tolkning) -> bool:
    """Ledamotens egen rad i närvarolistan säger något som tolkningen inte tar hänsyn till, så att ersättaren kan
    ha tjänstgjort när ledamoten inte var beslutande: klockslag ("kl. 09.15 – 14.25"), "ej tjänstgörande" eller
    "närvarande under föredragningarna", paragrafer som tolkningen inte har läst, eller en tabellrad med både
    ledamoten och ersättaren."""
    namn = ersattare.tjanstgor_for
    i = rad.find(namn)
    if i < 0 or rad[:i].rstrip().endswith(("för", "ersätter")):
        return False
    resten = rad[i + len(namn):]
    ledamot = next((m for m in t.narvaro if m.namn == namn and not m.tjanstgor_for), None)
    return bool(
        re.search(r"\bkl\.?\s*\d|\bej\b|närvarande", resten, re.I)
        or ("§" in resten and (ledamot is None or ledamot.paragrafer is None))
        or ersattare.namn in resten
    )


def _forsta_sida(t: Tolkning, paragraf: int) -> int | None:
    return next((b.sida for b in t.behandlingar if b.paragraf == paragraf), None)


def _paragrafnummer(t: Tolkning, sidor: list[str], intervall: list[int]) -> list[Fynd]:
    """Ett paragrafnummer saknas i följden eller förekommer två gånger.

    Kontrollen görs bara när paragraferna kommer i stigande ordning: en paragraf ur ordningen beror oftast på
    att tolkningen har läst en ärendelista eller ett felaktigt textlager. Ett nummer som saknas räknas bara när
    det ingår i protokollets egna paragrafer (försättsbladets "Paragrafer") och inte står som rubrik någonstans,
    eftersom tolkningen annars kan ha missat paragrafen. Ett nummer som förekommer två gånger räknas när båda
    paragraferna har ett beslut.
    """
    nummer = [b.paragraf for b in t.behandlingar]
    if any(a > b for a, b in zip(nummer, nummer[1:])):
        return []
    ut = []
    for a, b in zip(t.behandlingar, t.behandlingar[1:]):
        if a.paragraf == b.paragraf and a.beslut and b.beslut:
            ut.append(Fynd(
                "paragrafnummer", f"paragrafnummer|dubbel|{b.paragraf}", b.paragraf, b.sida,
                f"§ {b.paragraf} förekommer två gånger, på sidan {a.sida} och sidan {b.sida}.",
            ))
    rubriker = {int(m[1]) for s in sidor for m in re.finditer(r"(?m)^\s*§\s*(\d+)\s*(?:$|Dnr|[A-ZÅÄÖ]{2,5}\s?/)", s)}
    vantade = set(intervall) if intervall else set(range(min(nummer), max(nummer) + 1))
    for p in sorted(vantade - set(nummer) - rubriker):
        fore = [x for x in nummer if x < p]
        efter = [x for x in nummer if x > p]
        if not fore or not efter:
            continue
        ut.append(Fynd(
            "paragrafnummer", f"paragrafnummer|saknas|{p}", p, _forsta_sida(t, efter[0]),
            f"§ {p} finns inte i protokollet. Paragraferna går från § {fore[-1]} till § {efter[0]}"
            + (", fast försättsbladet anger att protokollet omfattar paragrafen." if intervall else "."),
        ))
    return ut


def _parti_saknas(t: Tolkning, sidor: list[str]) -> list[Fynd]:
    """Ett parti saknas eller står som "()" i närvarolistan."""
    personer = [n for n in t.narvaro if n.kategori in ("beslutande", "ej_tjanstgorande")]
    tomma = [n for n in personer if re.search(r"\(\s*\)$", n.namn)]
    utan = [n for n in personer if n.parti is None and n not in tomma]
    ut = [Fynd(
        "parti_saknas", f"parti_saknas|{_utan_parentes(n.namn)}", None, _sida_med(sidor, n.namn),
        f'{_utan_parentes(n.namn)} står med partiet "()" i närvarolistan.',
    ) for n in tomma]
    if utan and len(utan) == len(personer):
        ut.append(Fynd(
            "parti_saknas", "parti_saknas|alla", None, _sida_med(sidor, utan[0].namn),
            f"Närvarolistan anger inget parti för någon av de {len(utan)} beslutande och ersättarna.",
        ))
    else:
        ut += [Fynd(
            "parti_saknas", f"parti_saknas|{n.namn}", None, _sida_med(sidor, n.namn),
            f"Närvarolistan anger inget parti för {n.namn}.",
        ) for n in utan]
    return ut


def _utan_parentes(namn: str) -> str:
    return re.sub(r"\s*\(\s*\)$", "", namn)


def _stavning(t: Tolkning, sidor: list[str]) -> list[Fynd]:
    """Samma person stavas olika i samma protokoll.

    Närvarolistan är utgångspunkten. Ett namn i en voteringslista, ett yrkande eller en reservation som inte
    står i närvarolistan men skiljer sig från ett namn där med högst två bokstäver räknas. Två namn i
    närvarolistan jämförs inte med varandra, eftersom de är olika personer.
    """
    narvaro = {_utan_parentes(n.namn) for n in t.narvaro if n.kategori != "ovrig"}
    narvaro |= {n.tjanstgor_for for n in t.narvaro if n.tjanstgor_for}
    andra: dict[str, int | None] = {}
    for b in t.behandlingar:
        namn = [r.namn for v in b.voteringar for r in v.roster] + [r.ersatt for v in b.voteringar for r in v.roster]
        namn += [n for y in b.yrkanden for n, _ in y.personer] + [n for r in b.reservationer for n, _ in r.personer]
        for x in namn:
            if x and x not in narvaro:
                andra.setdefault(_norm(x), b.paragraf)
    ut = []
    for x, paragraf in andra.items():
        lika = [n for n in narvaro if _samma_person(n, x)]
        if len(lika) != 1:
            continue
        [n] = lika
        b_sida = _forsta_sida(t, paragraf)
        ut.append(Fynd(
            "stavning", f"stavning|{n}|{x}", paragraf, _sida_med(sidor, x, b_sida) or b_sida,
            f'Namnet står som "{n}" i närvarolistan och som "{x}" vid § {paragraf}.',
        ))
    return ut


def _samma_person(a: str, b: str) -> bool:
    """Två stavningar som sannolikt avser samma person: lika många namn, samma efternamn eller förnamn, och högst
    två bokstäver skiljer, eller bara accenter, bindestreck och mellanslag."""
    if a == b or _genitiv(a, b) or _genitiv(b, a) or _avstavat(a) or _avstavat(b):
        return False
    if _enkel(a) == _enkel(b):
        return True
    da, db = a.split(), b.split()
    if len(da) != len(db) or len(a) < 8 or (da[0] != db[0] and da[-1] != db[-1]):
        return False
    return _avstand(a.casefold(), b.casefold()) <= 2


def _genitiv(a: str, b: str) -> bool:
    """"Per-Eric Norbergs" är genitiv av "Per-Eric Norberg", ingen annan stavning."""
    da, db = a.split(), b.split()
    return len(da) == len(db) and any(y == x + "s" for x, y in zip(da, db)) and         sum(x != y for x, y in zip(da, db)) == 1


def _avstavat(namn: str) -> bool:
    """Ett namn som textlagret har delat mitt i ett ord: "Elisabeth Strömqu ist"."""
    return any(d[0].islower() and d not in ("von", "af", "de", "van", "der", "la") for d in namn.split())


def _enkel(namn: str) -> str:
    utan = "".join(c for c in unicodedata.normalize("NFKD", namn) if not unicodedata.combining(c))
    return re.sub(r"[\s-]+", "", utan).casefold()


def _avstand(a: str, b: str) -> int:
    """Levenshteinavståndet."""
    foreg = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        rad = [i]
        for j, cb in enumerate(b, 1):
            rad.append(min(foreg[j] + 1, rad[j - 1] + 1, foreg[j - 1] + (ca != cb)))
        foreg = rad
    return foreg[-1]
