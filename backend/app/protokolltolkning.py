"""Tolkning av protokoll från Härnösands kommun: PDF-text in, ett tolkat protokoll ut.

Tolkningen är reglerbaserad (ADR-0002: ingen AI här). Den gissar aldrig. Det som inte går
att läsa ut lämnas tomt, och allt som avviker från det förväntade samlas i `avvikelser`.
Ett protokoll som saknar sammanträdesdatum eller behandlingar räknas som ej tolkat.

Närvarolistan finns i två former:
- en lista på första sidan, "Namn (Parti)  Roll  Tjänstgörande för …/Jäv § N", eller
- tabeller på egna sidor, "Närvaro- och voteringslista, ledamöter" och
  "Närvaro- och tjänstgöringslista, ersättare".
Närvarolistan läses med layout bevarad (kolumnerna betyder något), paragraferna som löptext.
"""

from __future__ import annotations

import copy
import io
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import date

from pypdf import PdfReader

PARTILOS = "-"  # "(-)" i protokollet. None betyder att protokollet inte anger parti.


@dataclass
class Narvaro:
    namn: str
    parti: str | None
    roll: str | None
    # 'beslutande' | 'ej_tjanstgorande' | 'franvarande' | 'ovrig'
    kategori: str
    tjanstgor_for: str | None = None
    tjanstgor_for_parti: str | None = None
    # Paragrafer personen var beslutande vid, om inte alla. None = hela sammanträdet. För den som inte
    # var beslutande: paragraferna vid de sittningar personen var närvarande, i ett protokoll med flera.
    paragrafer: list[int] | None = None
    jav: list[int] = field(default_factory=list)


@dataclass
class Yrkande:
    text: str
    # De som yrkar eller ställer sig bakom. Tom när yrkandet inte står med namn,
    # t.ex. "Ordförande yrkar bifall till liggande förslag."
    personer: list[tuple[str, str | None]] = field(default_factory=list)


@dataclass
class Reservation:
    text: str
    # De som reserverar sig, med namn i texten eller som parti ("Sverigedemokraterna reserverar sig").
    personer: list[tuple[str, str | None]] = field(default_factory=list)
    partier: list[str] = field(default_factory=list)


@dataclass
class Rost:
    # Den som röstade, en tjänstgörande ersättare när en sådan står i listan. None för en tom stol
    # utan namn ("--- tom stol ---").
    namn: str | None
    parti: str | None
    rost: str  # 'ja' | 'nej' | 'avstar' | 'franvarande'
    ersatt: str | None = None  # ledamoten som ersättaren tjänstgjorde för
    ersatt_parti: str | None = None


@dataclass
class Votering:
    ja_forslag: str | None
    nej_forslag: str | None
    # Siffrorna som protokollets text anger. None när texten inte anger dem.
    ja: int | None
    nej: int | None
    avstar: int | None
    resultat: str | None  # "kommunfullmäktige beslutat enligt kommunstyrelsens förslag"
    franvarande: int | None = None  # "2 frånvarande", "1 tom stol"
    roster: list[Rost] = field(default_factory=list)

    @property
    def vinnare(self) -> str | None:
        """'ja' eller 'nej': det förslag som ordförandens konstaterande anger. Det räknas inte fram ur
        siffrorna, eftersom en minoritet kan kräva återremiss trots att ja-sidan har flest röster."""
        if not (self.resultat and self.ja_forslag and self.nej_forslag):
            return None
        def karna(s: str) -> str:
            # "att kommunfullmäktige ska bifalla liggande förslag" → "liggandeförslag"
            s = re.sub(
                r"^(?:att\s+)?(?:(?:kommunfullmäktige|fullmäktige|kommunstyrelsen|nämnden|\w+nämnden)\s+)?"
                r"(?:ska\s+|beslutar\s+|beslutat\s+)?(?:besluta\s+|bifalla\s+)?(?:enligt\s+)?",
                "", s.strip(), flags=re.I,
            )
            return re.sub(r"\s+", "", s).casefold()

        res = re.sub(r"\s+", "", self.resultat).casefold()
        ja, nej = karna(self.ja_forslag) in res, karna(self.nej_forslag) in res
        return "ja" if ja and not nej else "nej" if nej and not ja else None


@dataclass
class Behandling:
    paragraf: int
    rubrik: str
    diarienummer: list[str]
    beslut: str | None
    yrkanden: list[Yrkande] = field(default_factory=list)
    propositionsordning: str | None = None
    voteringar: list[Votering] = field(default_factory=list)
    reservationer: list[Reservation] = field(default_factory=list)
    hanvisningar: list[Hanvisning] = field(default_factory=list)
    # Den eller de som väckt motionen, enligt protokollets bakgrund: (namn, parti). Namnet är None
    # när protokollet bara anger partiet ("Centerpartiet har lämnat in en motion").
    motionarer: list[tuple[str | None, str | None]] = field(default_factory=list)
    # Rubriken hittades inte i paragrafen och är hämtad ur protokollets ärendelista (#88).
    rubrik_ur_arendelistan: bool = False


@dataclass
class Hanvisning:
    """En hänvisning i beslutsunderlaget till ett protokollsutdrag: "Protokollsutdrag
    samhällsnämnden 2026-05-21 § 61". `organ` är None när hänvisningen inte anger organet."""

    organ: str | None
    datum: date
    paragraf: int
    text: str


@dataclass
class Sittning:
    """En sittning i ett protokoll med flera sittningar samma dag (#85). Varje sittning har ett eget
    försättsblad med "Plats och tid", "Beslutande" och "Paragrafer"."""

    plats: str | None
    starttid: str | None
    sluttid: str | None
    paragrafer: list[int]
    # Den som fattade sittningens beslut på delegation, enligt beslutsformeln ("Kommunstyrelsens
    # presidium beslutar med delegation av kommunstyrelsen"): "kommunstyrelsens presidium".
    delegation: str | None = None


@dataclass
class Tolkning:
    datum: date | None = None
    starttid: str | None = None
    sluttid: str | None = None
    plats: str | None = None
    narvaro: list[Narvaro] = field(default_factory=list)
    behandlingar: list[Behandling] = field(default_factory=list)
    # Sittningarna, bara när protokollet har fler än en. Sammanträdets plats och tid är den första sittningens.
    sittningar: list[Sittning] = field(default_factory=list)
    avvikelser: list[str] = field(default_factory=list)
    # Texten är läst med OCR ur sidbilder (#52) och kan innehålla läsfel.
    ocr: bool = False

    @property
    def tolkad(self) -> bool:
        return self.datum is not None and bool(self.behandlingar)


# Text ur PDF


def sidtexter(pdf: bytes) -> tuple[list[str], list[str]]:
    """(löptext, layouttext) per sida."""
    r = PdfReader(io.BytesIO(pdf))
    lop = [p.extract_text() or "" for p in r.pages]
    layout = [p.extract_text(extraction_mode="layout") or "" for p in r.pages]
    return lop, layout


# Hjälpare

_DATUM = re.compile(r"(\d{4})-\s*(\d{2})-\s*(\d{2})")
_TID = re.compile(r"(\d{1,2})[.:](\d{2})")
_PARTI = re.compile(r"^(?P<namn>.+?)\s*\((?P<parti>[A-ZÅÄÖ]{1,4}|-)\)\s*$")
# Textlagret delar ibland förkortningen ("S AM/2026-131"), så ett mellanslag inuti tillåts.
_DIARIENUMMER = re.compile(r"\b([A-ZÅÄÖ]{1,5} ?[A-ZÅÄÖ]{1,5})\s?/\s?(\d{4})\s?[-:]\s?(\d+)\b")


def _diarienummer(text: str) -> list[str]:
    return [f"{d[0].replace(' ', '')}/{d[1]}-{d[2]}" for d in _DIARIENUMMER.findall(text)]
_SIGNERING = "Följande parter har signerat detta dokument"


def _datum(text: str) -> date | None:
    m = _DATUM.search(text)
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def _tid(m: re.Match) -> str:
    return f"{int(m[1]):02d}:{m[2]}"


def paragraflista(text: str) -> list[int]:
    """"129", "88-89", "88, 92", "1-6, 8-14", "121-128 samt 130-136" → paragrafnummer."""
    nummer: list[int] = []
    for a, b in re.findall(r"(\d+)\s*(?:[-–]\s*(\d+))?", text):
        start, slut = int(a), int(b) if b else int(a)
        if slut < start or slut - start > 500:
            continue
        nummer.extend(range(start, slut + 1))
    return sorted(set(nummer))


def _namn_parti(text: str) -> tuple[str, str | None]:
    text = " ".join(text.split())
    m = _PARTI.match(text)
    return (m["namn"].strip(), m["parti"]) if m else (text, None)


def _falt(rad: str) -> list[tuple[int, str]]:
    """Fält i en layoutrad: text åtskild av minst två mellanslag, med startkolumn."""
    return [(m.start(), m.group()) for m in re.finditer(r"\S+(?: \S+)*", rad)]


# Sammanträdet


def _sammantrade(t: Tolkning, lop: list[str], layout: list[str]) -> None:
    forsta = lop[0] if lop else ""
    rader = [r.strip() for r in forsta.splitlines()]
    for i, r in enumerate(rader):
        if r.startswith("Sammanträdesdatum"):
            t.datum = _datum(" ".join(rader[i : i + 2]))
            break
    plats_rad = next((r for r in (layout[0] if layout else "").splitlines() if "Plats och tid" in r), None)
    if plats_rad:
        t.plats, t.starttid, t.sluttid = _plats_och_tid(plats_rad)
        if t.datum is None:
            t.datum = _datum(plats_rad)
    if t.datum is None:
        t.avvikelser.append("Sammanträdesdatum hittades inte")


def _plats_och_tid(plats_rad: str) -> tuple[str | None, str | None, str | None]:
    """(plats, starttid, sluttid) ur raden "Plats och tid  Rådhuset, 2026-05-21 kl. 08.30–12.00"."""
    text = " ".join(plats_rad.split("Plats och tid", 1)[1].split())
    kl = re.search(r"\bkl\.?\s*", text)
    fore = text[: kl.start()] if kl else text
    plats = re.split(r",\s*(?=\d{4}-)|,?\s+(?:måndagen|tisdagen|onsdagen|torsdagen|fredagen|lördagen|söndagen)\b", fore)[0]
    tider = list(_TID.finditer(text[kl.end() :])) if kl else []
    return (plats.strip(" ,") or None, _tid(tider[0]) if tider else None,
            _tid(tider[1]) if len(tider) > 1 else None)


# Närvaro, form 1: lista på första sidan
#
# Två varianter: kolumner ("Namn (S)  Ledamot  Tjänstgörande för …") eller en rad per person
# ("Namn (S), ordförande" / "Namn (S) tjänstgörande ersättare för Annan (M)") under rubrikerna
# Ledamöter och Ersättare.

_SLUT_PA_LISTA = ("justerare", "justeringens", "sekreterare", "utses att justera", "underskrifter", "paragrafer")
_UNDERRUBRIKER = {"Ledamöter": "Ledamot", "Ersättare": "Ersättare", "Tjänstgörande ersättare": "Ersättare"}
_PARAGRAFER = r"§+\s*(?P<par>[\d\s,\-–§]+(?:\s*(?:och|samt)\s*[\d\s,\-–§]+)*)"
# "Namn (S)", "Namn (S), ordförande", "Namn (S) tjänstgörande för …", "Namn ()" (parti saknas),
# "Namn (KD" (parentesen inte stängd).
_PERSON = re.compile(
    r"^(?P<namn>[^(),]+?)\s*\((?P<parti>[A-ZÅÄÖa-zåäö]{0,4}|-)\)?"
    r"(?:\s*,\s*(?P<roll>(?!tjänstgör|§|kl\b|närvarande)[^\s,§][^,§]*?))?"
    r"(?:[\s,]+(?P<rest>(?:tjänstgör|ersätter|för\s|jäv|§|kl\b|närvarande).*))?$",
    re.IGNORECASE,
)
_TJANSTGOR = re.compile(
    r"(?:Tjänstgörande (?:ers\w*ttare )?för|ersätter|^för)\s+(?P<for>[^()§,]+?(?:\s*\([^)]*\))?)"
    r"(?=\s*(?:,|§|närvarande|kl\b|$))(?:.*?" + _PARAGRAFER + r")?",
    re.IGNORECASE,
)


def _kategori(etikett: str, nu: str) -> str | None:
    """Kategorin som en etikett i vänstermarginalen anger. None = listan är slut."""
    e = etikett.lower()
    if e.startswith(_SLUT_PA_LISTA):
        return None
    if "övriga" in e:
        return "ovrig"
    if "ej tjänstgörande" in e or e.startswith("ej "):
        return "ej_tjanstgorande"
    if e.startswith("beslutande"):
        return "beslutande"
    if e.startswith("närvarande") or e in ("ersättare", "distans", "plats"):
        return nu  # "Närvarande på plats/distans", eller en radbruten etikett
    return None


def _anteckning(n: Narvaro, text: str) -> None:
    text = " ".join(text.split())
    if m := re.search(r"Jäv\s*" + _PARAGRAFER, text, re.IGNORECASE):
        n.jav = paragraflista(m["par"])
        text = (text[: m.start()] + text[m.end() :]).strip()
    if m := _TJANSTGOR.search(text):
        n.tjanstgor_for, n.tjanstgor_for_parti = _namn_parti(m["for"])
        if n.tjanstgor_for.lower().startswith("vakant"):  # "för vakant plats efter Namn (S)"
            n.tjanstgor_for = n.tjanstgor_for_parti = None
        if m["par"]:
            n.paragrafer = paragraflista(m["par"])
        if re.match(r"tjänstgörande ers\w*ttare", m[0], re.IGNORECASE):
            n.roll = "Ersättare"
    elif m := re.match(_PARAGRAFER, text):
        n.paragrafer = paragraflista(m["par"])


def _sammanfoga(falt: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Layoutläget kan dela ett ord med bindestreck ("Höglund-   Bystedt") i två fält."""
    ut: list[tuple[int, str]] = []
    for kol, text in falt:
        if ut and ut[-1][1].endswith("-") and not ut[-1][1].endswith(" -"):
            ut[-1] = (ut[-1][0], ut[-1][1] + text)
        else:
            ut.append((kol, text))
    return ut


def _stor_bokstav(roll: str | None) -> str | None:
    return roll[:1].upper() + roll[1:] if roll else roll


def _person(text: str, kategori: str, standardroll: str | None) -> tuple[Narvaro, str] | None:
    """ "Namn (S), ordförande", "Namn (S) tjänstgörande för Annan (M)" → (person, anteckning)."""
    m = _PERSON.match(text)
    if not m:
        return None
    n = Narvaro(namn=m["namn"].strip(), parti=m["parti"].upper() or None,
                roll=_stor_bokstav(m["roll"]) or standardroll, kategori=kategori)
    if m["rest"]:
        _anteckning(n, m["rest"])
    return n, m["rest"] or ""


def _narvaro_forsta_sidan(t: Tolkning, layout: str) -> bool:
    rader = layout.splitlines()
    start = next((i for i, r in enumerate(rader) if re.match(r"\s*Beslutande\s{2,}", r)), None)
    if start is None:
        return False
    kategori: str | None = "beslutande"
    standardroll: str | None = None  # satt när listan har underrubriker (en rad per person)
    namnkolumn = rollkolumn = None
    lopande_text = False
    anteckning = ""  # anteckningen på föregående persons rad, som en radbruten rad kan fortsätta
    oppen: tuple[str, str | None, int] | None = None  # (namnfält, roll, antal poster) som kan fortsätta
    for rad in rader[start:]:
        if not rad.strip():
            continue
        falt = _sammanfoga(_falt(rad))
        if falt and falt[0][0] < 10:
            kategori = _kategori(falt[0][1], kategori or "beslutande")
            oppen = None
            if kategori is None:
                break
            falt = falt[1:]
            # En etikett med stort mellanrum ("Närvarande på        distans") ger ett fält till.
            while falt and namnkolumn is not None and falt[0][0] < namnkolumn - 4:
                falt = falt[1:]
        if not falt:
            continue
        if "Se närvaro" in rad or "närvarolista" in rad.lower():
            return False  # Listan finns på egna sidor.
        if len(falt) == 1 and falt[0][1] in _UNDERRUBRIKER:
            standardroll = _UNDERRUBRIKER[falt[0][1]]
            namnkolumn = namnkolumn if namnkolumn is not None else falt[0][0]
            continue
        forsta = falt[0][1]
        if forsta.strip() in ("-", "–") or forsta.lower().startswith("övriga"):
            continue  # "inga", "Övriga enligt § 13"
        if kategori == "ovrig" and "(" not in forsta and ("," in forsta or lopande_text or standardroll):
            # Tjänstepersoner i löptext ("Namn, förvaltningschef, Namn, …"), ev. över flera rader,
            # tas inte med.
            lopande_text = True
            continue
        lopande_text = False
        if standardroll is not None:
            # En rad per person.
            text = re.sub(r"(\w)-\s+(\w)", r"\1-\2", " ".join(" ".join(f for _, f in falt).split()))
            if ny := _person(text, kategori, standardroll):
                t.narvaro.append(ny[0])
                anteckning = ny[1]
            elif t.narvaro:
                # Radbruten fortsättning ("§§ 26-27", "16:10", "för Annan (M)") hör till raden ovanför.
                anteckning = f"{anteckning} {text}"
                _anteckning(t.narvaro[-1], anteckning)
            continue
        if oppen and len(falt) == 1 and abs(falt[0][0] - (namnkolumn or 0)) < 4:
            # "Monica Fällström, ersätter Magnus" / "Oskarsson §§ 131-138" i namnkolumnen
            text, roll, antal = oppen
            del t.narvaro[-antal:]
            oppen = _namnfalt_poster(t, f"{text} {forsta}", roll, kategori)
            continue
        oppen = None
        if t.narvaro and not forsta[:1].isupper():
            anteckning = f"{anteckning} {forsta}"
            _anteckning(t.narvaro[-1], anteckning)
            continue

        # Variant med kolumner: "Namn (S)   Ledamot   Tjänstgörande för …".
        if namnkolumn is None:
            namnkolumn = falt[0][0]
            if len(falt) > 1:
                rollkolumn = falt[1][0]
        # En rad som bara fortsätter rollen ("ordförande" under "1:e vice").
        if t.narvaro and falt[0][0] > namnkolumn + 15:
            for kol, text in falt:
                if rollkolumn is not None and abs(kol - rollkolumn) < 15:
                    t.narvaro[-1].roll = f"{t.narvaro[-1].roll or ''} {text}".strip()
                else:
                    _anteckning(t.narvaro[-1], text)
            continue
        roll = falt[1][1] if len(falt) > 1 else None
        anteckningar = [f for _, f in falt[2:]]
        if ny := _person(" ".join(forsta.split()), kategori, None):
            # "Namn (S) tjänstgörande ersättare" i namnkolumnen
            namn, parti = ny[0].namn, ny[0].parti
            if ny[1]:
                anteckningar.insert(0, ny[1])
        elif rollkolumn is not None and len(falt) == 2 and re.search(r",|§|\sersätter\s", forsta):
            # "Glenn Sehlin, §§ 131-138", "Britta Thyr, 1:e vice ordförande", "Namn, ersätter Annan § 138"
            oppen = _namnfalt_poster(t, forsta, roll, kategori)
            anteckning = ""
            continue
        else:
            namn, parti = _namn_parti(forsta)
        # "Ersättare ersätter Namn" står i rollkolumnen med ett mellanslag.
        # Även "Tjänstgörande ersättare för Namn (V) § 127" och "Ledamot §§ 121-126" står så.
        if roll and (m := re.search(r"(?:^|\s+)(?:ersätter|tjänstgör|§).*$", roll, re.IGNORECASE)):
            anteckningar.insert(0, m[0])
            roll = roll[: m.start()] or None
        n = Narvaro(namn=namn, parti=parti, roll=_stor_bokstav(roll), kategori=kategori)
        for a in anteckningar:
            _anteckning(n, a)
        anteckning = " ".join(anteckningar)
        t.narvaro.append(n)
    return bool(t.narvaro)


def _namnfalt_poster(t: Tolkning, text: str, roll: str | None, kategori: str) -> tuple[str, str | None, int] | None:
    """Poster ur ett namnfält utan parti: "Namn, §§ 1-3", "Namn, ordförande",
    "Namn, ersätter Annan § 138 samt Tredje § 139" (en post per tjänstgöring).
    Returnerar fältet om nästa rad kan fortsätta det, annars None."""
    text = " ".join(text.split())
    m = re.search(r",?\s*(?:(?P<ers>ersätter)\s+|(?=§))", text)
    namn, rest = (text[: m.start()], text[m.end() :]) if m else (text, "")
    namn = namn.split(",")[0].strip()
    poster: list[Narvaro] = []
    if m and m["ers"]:
        for for_namn, ref in _tjanstgoringar(rest):
            poster.append(Narvaro(namn=namn, parti=None, roll=_stor_bokstav(roll), kategori=kategori,
                                  tjanstgor_for=for_namn or None,
                                  paragrafer=paragraflista(ref) if ref else None))
    else:
        poster.append(Narvaro(namn=namn, parti=None, roll=_stor_bokstav(roll), kategori=kategori,
                              paragrafer=paragraflista(rest) or None if m else None))
    t.narvaro.extend(poster)
    fortsatter = text.endswith(("§", ",", " samt", " och")) or bool(m and m["ers"] and "§" not in rest)
    return (text, roll, len(poster)) if fortsatter else None


# Närvaro, form 2: tabeller på egna sidor


_KOLUMNNAMN = (("Part", "Parti"), ("När", "Närvaro"), ("Tjänstg", "Tjänstgöring"))


def _kolumner(rubrikrad: str) -> list[tuple[int, str]]:
    """Rubrikerna kan vara avstavade över två rader ("Part"/"i", "Närv"/"aro")."""
    def namn(text: str) -> str:
        return next((hel for borjan, hel in _KOLUMNNAMN if text.startswith(borjan)), text)
    return [(kol, namn(text)) for kol, text in _falt(rubrikrad)]


_PARTIKOD = re.compile(r"[A-ZÅÄÖ]{1,4}|-")
_PARAGRAFTEXT = re.compile(r"[\d\s,\-–§]*\d[\d\s,\-–§]*")


def _logiska_rader(rad_iter, kolumner: list[tuple[int, str]], namnkolumn: str):
    """En person per post. Rader utan parti fortsätter föregående (radbrutna namn, paragrafer).

    Ibland hamnar en del av en paragraflista under Parti ("S 1-", eller "57-61, 64-65,   67-76" på
    en fortsättningsrad). Den hör till ersättarkolumnen före Parti, eller till Närvaro.
    """
    namn = [k for _, k in kolumner]
    fore = namn[namn.index("Parti") - 1] if "Parti" in namn and namn.index("Parti") > 0 else None
    flytta_till = fore if fore and fore != namnkolumn else "Närvaro"

    def dela(v: dict[str, str]) -> dict[str, str]:
        parti = v.get("Parti", "")
        if not parti or _PARTIKOD.fullmatch(parti):
            return v
        delar = parti.split()
        koder = [d for d in delar if _PARTIKOD.fullmatch(d) and d != "-"]
        rest = " ".join(d for d in delar if d not in koder)
        if koder:
            v["Parti"] = koder[0]  # "S 1-", "SD SD"
        elif _PARAGRAFTEXT.fullmatch(parti):
            v.pop("Parti")
        else:
            return v
        if rest and _PARAGRAFTEXT.fullmatch(rest):
            v[flytta_till] = f"{v.get(flytta_till, '')} {rest}".strip()
        return v

    post: dict[str, str] | None = None
    for rad in rad_iter:
        v = dela(_per_kolumn(rad, kolumner))
        if v.get(namnkolumn) and v.get("Parti"):
            if post:
                yield post
            post = v
        elif post is not None:
            for k, text in v.items():
                if k == "Parti" and post.get("Parti"):
                    continue  # partiet upprepat på fortsättningsraden
                post[k] = f"{post.get(k, '')} {text}".strip()
    if post:
        yield post


def _per_kolumn(rad: str, kolumner: list[tuple[int, str]]) -> dict[str, str]:
    """Varje fält hamnar i den kolumn vars rubrik det ligger närmast (rubriker kan vara centrerade)."""
    varden: dict[str, str] = {}
    for kol, text in _falt(rad):
        mitt = kol + len(text) / 2
        namn = min(kolumner, key=lambda k: min(abs(kol - k[0]), abs(mitt - (k[0] + len(k[1]) / 2))))[1]
        varden[namn] = f"{varden.get(namn, '')} {text}".strip()
    return varden


def _narvarotabeller(t: Tolkning, layout: list[str]) -> bool:
    hittade = False
    fortsatt: list[tuple[int, str]] | None = None  # kolumnerna i ledamotstabellen på sidan före
    for sida in layout:
        rader = sida.splitlines()
        rubriker = [i for i, rad in enumerate(rader) if re.search(
            r"Närvaro.*lista.*ledamöter|Närvaro-\s+och\s+voteringslista|Närvaro.*tjänstgöringslista.*ersättare",
            rad, re.IGNORECASE)]
        if not rubriker and fortsatt:
            # Ledamotstabellen fortsätter på nästa sida utan rubrikrad.
            _ledamotsrader(t, _tabellrader(rader), fortsatt)
        fortsatt = None
        for i in rubriker:
            if re.search(r"tjänstgöringslista.*ersättare", rader[i]):
                hittade |= _ersattartabell(t, rader[i + 1 :])
            elif kolumner := _ledamotstabell(t, rader[i + 1 :]):
                hittade = True
                fortsatt = kolumner
    return hittade


def _tabellrader(rader: list[str]):
    for rad in rader:
        if not rad.strip():
            continue
        if rad.strip().startswith(("Justerandes sign", "Utdragsbestyrkande")) or "Sida " in rad.strip()[:5]:
            return
        yield rad


def _narvarotecken(text: str | None) -> tuple[bool, list[int] | None]:
    """'X' = närvarande, '-' eller tomt = frånvarande, '§§ 1-6, 8-14' eller 'X §§ 1-13' = närvarande
    vid de paragraferna."""
    text = (text or "").strip()
    if "§" in text or re.search(r"\d", text):
        return True, paragraflista(text)
    if text.upper().startswith("X"):
        return True, None
    return False, None


def _ledamotstabell(t: Tolkning, rader: list[str]) -> list[tuple[int, str]] | None:
    """Läser ledamotstabellen. Returnerar kolumnerna, så att en fortsättning på nästa sida kan läsas."""
    rad_iter = _tabellrader(rader)
    rubrik = next((r for r in rad_iter if re.search(r"\bPart", r) and re.search(r"\bLedamot\b", r)), None)
    if not rubrik:
        return None
    kolumner = _kolumner(rubrik)
    _ledamotsrader(t, rad_iter, kolumner)
    return kolumner


def _ledamotsrader(t: Tolkning, rad_iter, kolumner: list[tuple[int, str]]) -> None:
    redan = {n.namn for n in t.narvaro}
    for v in _logiska_rader(rad_iter, kolumner, "Ledamot"):
        namn = " ".join((v.get("Ledamot") or "").split())
        if not namn or namn.lower().startswith("vakant"):
            continue
        narvarande, paragrafer = _narvarotecken(v.get("Närvaro"))
        # "Andreas Sjölander §§ 57-61, 63-68, 70-76": ledamoten tjänstgjorde bara vid de paragraferna.
        if "§" in namn:
            namn, _, egna = namn.partition("§")
            namn = namn.strip()
            if narvarande and (lista := paragraflista(egna)):
                paragrafer = lista
        if namn in redan:
            continue
        redan.add(namn)
        t.narvaro.append(Narvaro(
            namn=namn, parti=v.get("Parti") or None, roll="Ledamot",
            kategori="beslutande" if narvarande else "franvarande", paragrafer=paragrafer,
        ))


def _ersattartabell(t: Tolkning, rader: list[str]) -> bool:
    rad_iter = _tabellrader(rader)
    rubrik = next((r for r in rad_iter if re.search(r"\bPart", r) and re.search(r"\bErsättare\b", r)), None)
    if not rubrik:
        return False
    kolumner = _kolumner(rubrik)
    partier = {n.namn: n.parti for n in t.narvaro}
    for v in _logiska_rader(rad_iter, kolumner, "Ersättare"):
        namn = v.get("Ersättare")
        if not namn or namn.lower().startswith("vakant"):
            continue
        parti = v.get("Parti") or None
        narvarande, paragrafer = _narvarotecken(v.get("Närvaro"))
        for_namn = v.get("Tjänstgöring")
        if not narvarande:
            continue  # Frånvarande ersättare tas inte med: de var inte kallade att tjänstgöra.
        namn = " ".join(namn.split())
        if "§" in namn:  # "Nissreen Khaie §§ 48-53"
            namn, _, egna = namn.partition("§")
            namn = namn.strip()
            paragrafer = paragraflista(egna) or paragrafer
        if not for_namn:
            t.narvaro.append(Narvaro(namn=namn, parti=parti, roll="Ersättare", kategori="ej_tjanstgorande"))
            continue
        # En ersättare kan tjänstgöra för flera ledamöter vid olika paragrafer:
        # "Monika Lindberg § 63 / Anders Nordin § 64 / Nina Skyttberg § 65". En post per tjänstgöring.
        for for_namn, ref in _tjanstgoringar(" ".join(for_namn.split())):
            t.narvaro.append(Narvaro(
                namn=namn, parti=parti, roll="Ersättare", kategori="beslutande",
                tjanstgor_for=for_namn, tjanstgor_for_parti=partier.get(for_namn),
                paragrafer=paragraflista(ref) if ref else paragrafer,
            ))
    return True


def _tjanstgoringar(text: str) -> list[tuple[str, str | None]]:
    """ "Monika Lindberg § 63 Anders Nordin § 64" → [("Monika Lindberg", "63"), ("Anders Nordin", "64")]."""
    delar = re.split(r"(§+\s*[\d\s,\-–]+(?:\s*(?:och|samt)\s*[\d\s,\-–]+)*)", text)
    ut: list[tuple[str, str | None]] = []
    for i in range(0, len(delar), 2):
        namn = delar[i].strip(" ,")
        ref = delar[i + 1] if i + 1 < len(delar) else None
        if namn:
            ut.append((namn, ref))
        elif ref and ut and ut[-1][1] is None:
            ut[-1] = (ut[-1][0], ref)
        elif ref and not ut:
            ut.append(("", ref))  # bara paragrafer, utan namn
    return ut or [(text, None)]


# Behandlingar

_PARAGRAFRAD = re.compile(r"^§\s*(\d+)\s*(.*)$")
# En felskriven paragrafrubrik med några tecken framför §, t.ex. "Ko§ 168" (#87). Godtas bara med motkontroll.
_FELSKRIVEN_PARAGRAFRAD = re.compile(r"^([^\s§\d]{1,3})§\s*(\d+)\s*(.*)$")
_INNEHALL = ("Ärendelista", "Innehållsförteckning", "Nummer Rubrik Sida")
_RUBRIKER = (
    "Yrkande", "Yrkanden", "Yttrande", "Yttranden", "Propositionsordning", "Propositionsordningar",
    "Reservation", "Reservationer", "Sammanfattning", "Bakgrund", "Beslutsunderlag", "Jäv", "Överläggning",
    "Överläggande", "Bilagor", "Bilaga", "Votering", "Voteringar", "Omröstning", "Protokollsanteckning",
    "Protokollsanteckningar", "Särskilt yttrande", "Särskilda yttranden", "Beslutet skickas till",
    "Ärendebeskrivning", "Ajournering", "Beslutsgång", "Förslag till beslut", "Ordförandens förslag",
    "Expediering", "Paus",
)


def _beslutsrubrik(rad: str) -> bool:
    """'Kommunfullmäktiges beslut', 'Kommunfullmäktige beslut', 'Samhällsnämndens beslut' osv."""
    return bool(re.fullmatch(r"[A-ZÅÄÖ][\wåäöé-]+ beslut", rad))


def _beslutar(rad: str) -> bool:
    """'Kommunfullmäktige beslutar' inleder beslutet och hör till beslutstexten."""
    return bool(re.fullmatch(r"[A-ZÅÄÖ][\wåäöé-]+ beslutar", rad))


# Rubriker inom en behandling som har ett nummer eller ordningstal: "Propositionsordning 2",
# "Votering och utfall 1", "Andra voteringen".
_NUMRERAD_RUBRIK = re.compile(
    r"(?:Propositionsordning|Votering och utfall|Votering|Omröstning)(?: \d+)?"
    r"|(?:Första|Andra|Tredje|Fjärde|Femte) voteringen|Voteringsbilagor?|Anteckning|Anteckningar"
)


def _ar_rubrik(rad: str) -> bool:
    return rad in _RUBRIKER or _beslutsrubrik(rad) or _beslutar(rad) or bool(_NUMRERAD_RUBRIK.fullmatch(rad))


def _sidmobler(sida: str) -> list[str]:
    """Löptextens rader utan sidhuvud och sidfot."""
    rader = [r.strip() for r in sida.splitlines()]
    ut: list[str] = []
    for i, r in enumerate(rader):
        if not r:
            continue
        if re.fullmatch(r"SAMMANTRÄDESPROTOKOLL|Sida|\d+\(\d+\)|Sammanträdesdatum|\d{4}-\d{2}-\d{2}|«?Instans»?", r):
            continue
        if re.fullmatch(r"Sida \d+ av \d+|\(Signerat, SHA-256 [0-9A-F]+\)", r):
            continue
        if r.startswith(("Justerandes sign", "Utdragsbestyrkande")):
            continue
        # Sidfotens dokumentnamn står direkt före signaturraden.
        if i + 1 < len(rader) and rader[i + 1].startswith("(Signerat"):
            continue
        ut.append(r)
    return ut


def _organrad(rader: list[str]) -> str | None:
    # Organets namn står ensamt överst på varje sida (före "SAMMANTRÄDESPROTOKOLL" i löptexten).
    return rader[0] if rader else None


def _sidnummer(sida: str, index: int) -> int:
    """Sidnumret som det står på sidan ("36(36)"), annars sidans plats i PDF:en."""
    m = re.search(r"\b(\d+)\(\d+\)", sida)
    return int(m[1]) if m else index + 1


def _sidans_intervall(sida: str) -> list[int]:
    """Paragraferna enligt ett försättsblad ("Paragrafer 144–168"), eller en tom lista."""
    m = re.search(r"Paragrafer\s+(?:§+\s*)?([\d\s\-–,]+)", " ".join(sida.split()))
    return paragraflista(m[1]) if m else []


def _sittningssidor(layout: list[str]) -> list[int]:
    """Försättsbladen: första sidan, och varje senare sida med en egen sittning samma dag, alltså
    med "Plats och tid", "Beslutande" och "Paragrafer" (#85)."""
    if not layout:
        return []
    return [0] + [i for i in range(1, len(layout))
                  if "Plats och tid" in layout[i] and re.search(r"^\s*Beslutande\s{2,}", layout[i], re.M)
                  and _sidans_intervall(layout[i])]


def paragrafintervall(layout: list[str]) -> list[int]:
    """Paragraferna enligt försättsbladen, alla sittningar tillsammans, eller en tom lista."""
    return sorted({p for i in _sittningssidor(layout) for p in _sidans_intervall(layout[i])})


def innehallsforteckning(lop: list[str]) -> dict[int, int]:
    """Paragraf → sida enligt ärendelistan eller innehållsförteckningen, om protokollet har en."""
    text = ""
    for sida in lop:
        sidrader = _sidmobler(sida)
        if any(r in _INNEHALL for r in sidrader[:4]):
            text += " " + " ".join(sidrader)
    text = re.sub(r"\.{3,}", " ", text)
    return {int(m[1]): int(m[2]) for m in re.finditer(r"§\s*(\d+)\s.*?\s(\d+)\s*(?=§|$)", text)}


def arendelista(lop: list[str]) -> dict[int, str]:
    """Paragraf → rubrik enligt ärendelistan eller innehållsförteckningen, om protokollet har en (#88).

    Två former: "§ 1 Dnr 34746 4" med rubriken och sidan ("Val av justerare ....... 4") på raderna under,
    eller "§ 78 Val av justerare 3", där en lång rubrik kan fortsätta på nästa rad och sidan stå ensam.
    """
    poster: dict[int, list[str]] = {}
    aktuell: list[str] | None = None
    for sida in lop:
        sidrader = _sidmobler(sida)
        if not any(r in _INNEHALL for r in sidrader[:4]):
            continue
        for r in sidrader:
            if r in _INNEHALL:
                continue
            if m := re.match(r"§\s*(\d+)\b\s*(.*)$", r):
                aktuell = poster.setdefault(int(m[1]), [])
                if m[2] and not re.match(r"Dnr\b", m[2]):
                    aktuell.append(m[2])
            elif aktuell is not None:
                aktuell.append(r)
    ut: dict[int, str] = {}
    for nr, rader in poster.items():
        text = " ".join(re.sub(r"\s*\.{3,}[\s.]*", " ", r).strip() for r in rader)
        text = re.sub(r"\s+\d+$", "", " ".join(text.split()))  # sidnumret
        if re.search(r"[^\W\d_]", text):  # en rubrik har bokstäver
            ut[nr] = text
    return ut


def _jamforbar(rubrik: str) -> str:
    """Rubriken för motkontrollen mot ärendelistan: utan mellanslag, radbrytningar och skiljetecken (punkter
    kan vara rester av ärendelistans punktlinje), och utan skillnad mellan bindestreck och tankstreck eller
    mellan versaler och gemener."""
    return re.sub(r"[\s.,;:]+", "", re.sub(r"[–—]", "-", rubrik)).casefold()


def _motkontroll(nr: int, rubrik: str, i_listan: str) -> str | None:
    """Avvikelsen när paragrafens rubrik inte stämmer med ärendelistans, eller None (#88).

    När den ena rubriken börjar eller slutar med den andra har inläsningen troligen tagit med för mycket
    eller för lite. En rubrik som liknar ärendelistans men skiljer sig på något ställe står så i protokollet.
    En rubrik som inte liknar den alls är troligen fel text, läst av plattformen."""
    a, b = _jamforbar(rubrik), _jamforbar(i_listan)
    if a == b:
        return None
    if a.startswith(b) or a.endswith(b):
        return (f'§ {nr}: rubriken är längre än i ärendelistan ("{i_listan}"). '
                "Inläsningen har troligen tagit med text ur paragrafen")
    if b.startswith(a):
        return (f'§ {nr}: rubriken är kortare än i ärendelistan ("{i_listan}"). '
                "Inläsningen har troligen inte fått med hela rubriken")
    if SequenceMatcher(None, a, b).ratio() >= 0.5:
        return (f'§ {nr}: rubriken skiljer sig från ärendelistan i protokollet: "{rubrik}" i paragrafen, '
                f'"{i_listan}" i ärendelistan')
    return (f'§ {nr}: rubriken stämmer inte med ärendelistan ("{i_listan}"). '
            "Inläsningen har troligen läst fel text som rubrik")


def _felskriven_rubrik(m: re.Match, sida: int, foregaende: int | None, intervall: list[int],
                       forteckning: dict[int, int]) -> bool:
    """En felskriven paragrafrubrik godtas bara om numret är nästa i följden, ligger inom
    försättsbladets intervall och, när protokollet har en ärendelista, står där på samma sida."""
    nr = int(m[2])
    nasta = foregaende + 1 if foregaende is not None else (intervall[0] if intervall else None)
    if nr != nasta or nr not in intervall:
        return False
    return not forteckning or forteckning.get(nr) == sida


def _rad(text: str) -> str:
    return " ".join(text.split())


def _ratta_lasordning(sidrader: list[str], layoutsida: str | None) -> list[str]:
    """En ensam "§ N"-rad som står sist på sidan i löptexten men först, före rubriken, i layouttexten
    är lagrad sist i PDF:ens textflöde (#88). Raden flyttas till sidans början. Inget annat flyttas."""
    if not layoutsida or len(sidrader) < 2 or not re.fullmatch(r"§\s*\d+", sidrader[-1]):
        return sidrader
    if any(_PARAGRAFRAD.match(r) for r in sidrader[:-1]):
        return sidrader  # sidan har redan en paragrafrad: då är den sista raden början på nästa paragraf
    paragrafrad, forsta = _rad(sidrader[-1]), _rad(sidrader[0])
    layoutrader = [_rad(r) for r in layoutsida.splitlines() if r.strip()]
    try:
        i, j = layoutrader.index(paragrafrad), layoutrader.index(forsta)
    except ValueError:
        return sidrader
    # Paragrafraden står direkt före löptextens första rad i layouten.
    return [sidrader[-1], *sidrader[:-1]] if i + 1 == j else sidrader


def _behandlingar(t: Tolkning, lop: list[str], layout: list[str] | None = None) -> None:
    intervall = paragrafintervall(layout or [])
    forteckning = innehallsforteckning(lop)
    lista = arendelista(lop)
    rader: list[str] = []
    sidor: list[int] = []
    for index, sida in enumerate(lop):
        sidrader = _sidmobler(sida)
        if any(r in _INNEHALL for r in sidrader[:4]):
            continue
        if sidrader and not sidrader[0].startswith("§") and len(sidrader[0].split()) <= 3 and not _ar_rubrik(sidrader[0]):
            organ = sidrader[0]
            sidrader = [r for r in sidrader if r != organ]
        sidrader = _ratta_lasordning(sidrader, layout[index] if layout and index < len(layout) else None)
        if _SIGNERING in sida:
            sidrader = sidrader[: next((i for i, r in enumerate(sidrader) if r.startswith("Signering")), len(sidrader))]
            rader.extend(sidrader)
            sidor.extend([_sidnummer(sida, index)] * len(sidrader))
            break
        rader.extend(sidrader)
        sidor.extend([_sidnummer(sida, index)] * len(sidrader))

    starter: list[tuple[int, int, list[str]]] = []
    for i, r in enumerate(rader):
        m = _PARAGRAFRAD.match(r)
        felskriven = False
        if not m:
            m = _FELSKRIVEN_PARAGRAFRAD.match(r)
            if not m or m[3].strip() or not _felskriven_rubrik(
                    m, sidor[i], starter[-1][1] if starter else None, intervall, forteckning):
                continue
            felskriven = True
            m = _PARAGRAFRAD.match(r[len(m[1]):])
        rest = m[2].strip()
        dnr = _diarienummer(rest)
        rest = _DIARIENUMMER.sub("", rest).strip(" ,")
        # "Dnr 80117": ett diarienummer i annan form.
        if m2 := re.fullmatch(r"Dnr\.?:?\s*(\S*\d\S*)(?:\s+[\d.]+)?", rest):
            dnr.append(m2[1])
            rest = ""
        # Innehållsförteckningens rader har rubrik efter numret, eller rubrik och sidnummer på nästa rad.
        if rest or (i + 1 < len(rader) and re.search(r"\.{5,}\s*\d*$", rader[i + 1])):
            continue
        if felskriven:
            t.avvikelser.append(f'Paragrafrubriken är felskriven i protokollet: "{r}" (s. {sidor[i]})')
        starter.append((i, int(m[1]), dnr))

    for k, (i, nr, dnr) in enumerate(starter):
        slut = starter[k + 1][0] if k + 1 < len(starter) else len(rader)
        kropp = rader[i + 1 : slut]
        rubrik_rader: list[str] = []
        j = 0
        while j < len(kropp) and not _ar_rubrik(kropp[j]) and len(rubrik_rader) < 4:
            rubrik_rader.append(kropp[j])
            j += 1
        if j < len(kropp) and not _ar_rubrik(kropp[j]):
            # Ingen rubrik hittades: bara första raden är paragrafens rubrik.
            rubrik_rader, j = rubrik_rader[:1], 1
        rubrik = " ".join(rubrik_rader).strip()
        beslut = _beslutstext(kropp[j:])
        if not dnr:
            # Diarienumret kan stå på en egen rad direkt efter paragrafnumret.
            for r in kropp[:2]:
                if _DIARIENUMMER.fullmatch(r.strip()):
                    dnr = _diarienummer(r)
        ur_listan = False
        if not rubrik and lista.get(nr):
            rubrik, ur_listan = lista[nr], True
            t.avvikelser.append(f"§ {nr}: rubriken hittades inte i paragrafen och är hämtad ur ärendelistan")
        elif not rubrik:
            t.avvikelser.append(f"§ {nr}: rubriken hittades inte")
        elif nr in lista and (avvikelse := _motkontroll(nr, rubrik, lista[nr])) and avvikelse not in t.avvikelser:
            t.avvikelser.append(avvikelse)
        if beslut is None and any(_beslutsrubrik(r) or _beslutar(r) for r in kropp):
            t.avvikelser.append(f"§ {nr}: beslutet hittades inte")
        sektioner = _sektioner(kropp[j:])
        prop = [_lopande(s) for s in sektioner.get("propositionsordning", []) if s]
        t.behandlingar.append(Behandling(
            paragraf=nr, rubrik=rubrik, diarienummer=dnr, beslut=beslut,
            yrkanden=[y for s in sektioner.get("yrkande", []) for y in _yrkanden(_lopande(s))],
            propositionsordning="\n\n".join(prop) or None,
            reservationer=[r for s in sektioner.get("reservation", []) for r in _reservationer(_lopande(s))],
            hanvisningar=[h for s in sektioner.get("beslutsunderlag", []) for h in hanvisningar("\n".join(s))],
            motionarer=motionarer(" ".join(_lopande(s) for s in sektioner.get("bakgrund", [])))
            if re.search(r"\bmotion", rubrik, re.I) else [],
            rubrik_ur_arendelistan=ur_listan,
        ))


def _beslutstext(kropp: list[str]) -> str | None:
    for i, r in enumerate(kropp):
        if not (_beslutsrubrik(r) or _beslutar(r)):
            continue
        text: list[str] = []
        for s in kropp[i:]:
            if _beslutsrubrik(s):
                continue
            if _beslutar(s):
                if text and not _beslutar(text[-1]):
                    break
                if not text:
                    text.append(s)  # "Kommunfullmäktige beslutar", en gång även om den står dubbelt
                continue
            if _ar_rubrik(s) or s.startswith("_____"):
                break
            text.append(s)
        return _stycke(text) if [r for r in text if not _beslutar(r)] else None
    return None


def _stycke(rader: list[str]) -> str:
    """Sätter ihop rader till stycken. En rad som börjar med 'att' eller '-' blir en ny rad."""
    ut: list[str] = []
    for r in rader:
        if ut and not re.match(r"^(att\b|-|•|\d+\.)", r):
            ut[-1] = f"{ut[-1][:-1]}{r}" if ut[-1].endswith("-") and not ut[-1].endswith(" -") else f"{ut[-1]} {r}"
        else:
            ut.append(r)
    return "\n".join(" ".join(s.split()) for s in ut)


# Yrkanden, propositionsordning och reservationer

_PARTINAMN = {
    "Socialdemokraterna": "S", "Moderaterna": "M", "Sverigedemokraterna": "SD", "Centerpartiet": "C",
    "Vänsterpartiet": "V", "Kristdemokraterna": "KD", "Liberalerna": "L", "Miljöpartiet": "MP",
}
_ORD = r"[A-ZÅÄÖÉ][\wåäöéüÅÄÖ'’-]*"
_NAMN_PARTI = re.compile(rf"(?P<namn>{_ORD}(?: {_ORD}){{1,3}}) \((?P<parti>[A-ZÅÄÖ]{{1,4}}|-)\)")


# Hänvisningar till protokollsutdrag i beslutsunderlaget

_HANV_ORGAN = (
    ("KF", r"kommunfullmäktige|KF"),
    ("KS", r"kommunstyrelsen|kommunstyrelse|KS"),
    ("SAM", r"samhällsnämnden|samhällsnämnd"),
    ("SOC", r"socialnämnden|socialnämnd"),
    ("SKOL", r"skolnämnden|skolnämnd"),
)
_HANV_GENITIV = {"kommunfullmäktiges": "KF", "kommunstyrelsens": "KS", "samhällsnämndens": "SAM",
                 "socialnämndens": "SOC", "skolnämndens": "SKOL"}
_HANV_DATUM = r"(?P<{0}ar>20\d\d)(?:\s?-\s?(?P<{0}man>\d\d)\s?-\s?(?P<{0}dag>\d\d)|(?P<{0}man2>\d\d)(?P<{0}dag2>\d\d))"
_HANV_PAR = r"§§?\s?(?P<{0}par>\d+)"
_HANV_STALLE = (
    rf"(?:{_HANV_DATUM.format('a')}[,:]?\s*{_HANV_PAR.format('a')}"
    rf"|{_HANV_PAR.format('b')}[,:]?\s*{_HANV_DATUM.format('b')})(?!\d)"
)
_HANVISNING = re.compile(
    r"(?:(?P<genitiv>" + "|".join(_HANV_GENITIV) + r")\s+)?protokollsutdrag(?:\s+med\s+bilagor?)?[,:]?\s+"
    r"(?:(?P<organ>" + "|".join(rf"(?P<o{k}>{p})" for k, p in _HANV_ORGAN) + r")(?:\s+Härnösand)?[,:]?\s+)?"
    + _HANV_STALLE,
    re.I,
)


def hanvisningar(text: str) -> list[Hanvisning]:
    """Hänvisningarna till protokollsutdrag i ett beslutsunderlag.

    Organet anges efter ordet ("Protokollsutdrag kommunstyrelsen 2026-02-24 § 31") eller i genitiv
    före ("Socialnämndens protokollsutdrag, 2023-01-26 § 5"). Utan organ räknas hänvisningen bara
    när den inleder en punkt i underlaget, så att "Kommunfullmäktige Kramfors kommun protokollsutdrag
    …" inte blir en hänvisning till Härnösand. Andra kommuner, utskott och beredningar tas inte med.
    """
    ut: list[Hanvisning] = []
    for m in _HANVISNING.finditer(text):
        if m["organ"]:
            organ = next(k for k, _ in _HANV_ORGAN if m[f"o{k}"])
        elif m["genitiv"]:
            organ = _HANV_GENITIV[m["genitiv"].lower()]
        else:
            fore = text[: m.start()].rsplit("\n", 1)[-1]
            if not re.fullmatch(r"[\s•\-–*\d.]*", fore):
                continue
            organ = None
        s = "a" if m["aar"] else "b"
        try:
            datum = date(int(m[f"{s}ar"]), int(m[f"{s}man"] or m[f"{s}man2"]), int(m[f"{s}dag"] or m[f"{s}dag2"]))
        except ValueError:
            continue
        ut.append(Hanvisning(organ=organ, datum=datum, paragraf=int(m[f"{s}par"]), text=" ".join(m[0].split())))
    return ut


def _sektioner(kropp: list[str]) -> dict[str, list[list[str]]]:
    """Raderna under rubrikerna Yrkande, Propositionsordning och Reservation, ett avsnitt per rubrik."""
    ut: dict[str, list[list[str]]] = {}
    aktuell: list[str] | None = None
    for r in kropp:
        if r.startswith("_____"):
            break
        if _ar_rubrik(r):
            nyckel = ("yrkande" if r.startswith("Yrkande") else "reservation" if r.startswith("Reservation")
                      else "propositionsordning" if r.startswith("Propositionsordning")
                      else "beslutsunderlag" if r == "Beslutsunderlag"
                      else "bakgrund" if r in ("Bakgrund", "Sammanfattning", "Ärendebeskrivning") else None)
            aktuell = None if nyckel is None else []
            if nyckel:
                ut.setdefault(nyckel, []).append(aktuell)
        elif aktuell is not None:
            aktuell.append(r)
    return ut


def _lopande(rader: list[str]) -> str:
    """Rader till löpande text. Ett avstavat ord i radslutet sätts ihop."""
    text = ""
    for r in rader:
        r = " ".join(r.split())
        if text.endswith("-") and not text.endswith(" -"):
            # "Eva-" / "Clara" är ett namn med bindestreck, "Sverige-" / "demokraterna" ett avstavat ord.
            text = text + r if r[:1].isupper() else text[:-1] + r
        else:
            text = f"{text} {r}" if text else r
    return text


def _meningar_med_person(text: str) -> list[tuple[str | None, str | None, str]]:
    """Delar texten där en mening börjar med "Namn (Parti)". Text före första personen får namn None."""
    starter = [m for m in _NAMN_PARTI.finditer(text) if m.start() == 0 or text[: m.start()].rstrip().endswith((".", ":"))]
    delar: list[tuple[str | None, str | None, str]] = []
    if not starter or starter[0].start() > 0:
        forsta = text[: starter[0].start()] if starter else text
        if forsta.strip():
            delar.append((None, None, forsta.strip()))
    for k, m in enumerate(starter):
        slut = starter[k + 1].start() if k + 1 < len(starter) else len(text)
        delar.append((m["namn"], m["parti"], text[m.start() : slut].strip()))
    return delar


def _yrkanden(text: str) -> list[Yrkande]:
    ut: list[Yrkande] = []
    for _, _, s in _meningar_med_person(text) if text else []:
        # Personerna före verbet: "Eva-Clara Viklund (M), Olle Löfgren (L) och Glenn Sehlin (SD) ställer sig bakom …"
        fore = re.split(r"\b(?:yrkar|föreslår|ställer|instämmer|tillstyrker|lämnar|bifaller)\b", s, maxsplit=1)[0]
        ut.append(Yrkande(text=s, personer=[(m["namn"], m["parti"]) for m in _NAMN_PARTI.finditer(fore)]))
    return ut


# "Johan Wester (C) har lämnat in en motion", "… har den 20 oktober 2023 lämnat in en motion",
# "… har till kommunfullmäktige inkommit med en motion", "… har i en motion föreslagit", "… har väckt en motion".
_MOTION_VACKT = re.compile(
    r"\bhar\b[^.]{0,60}?\b(?:lämnat in|inlämnat|inkommit med|väckt|i en)\s+(?:en\s+)?motion", re.I)
_NAMN = re.compile(rf"{_ORD}(?: {_ORD}){{1,3}}")


def motionarer(text: str) -> list[tuple[str | None, str | None]]:
    """Motionärerna i bakgrunden till en motion: personerna (eller partiet) före "har lämnat in en motion".

    "X och Y (SD)" ger båda partiet SD. "Johan Wester, Centerpartiet," och "Olle Löfgren (Liberalerna)"
    ger partiets förkortning."""
    m = _MOTION_VACKT.search(text)
    if not m:
        return []
    fore = re.split(r"[.:;]\s", text[: m.start()])[-1].strip(" ,")
    kod = {**{n: k for n, k in _PARTINAMN.items()}, **{k: k for k in _PARTINAMN.values()}, "-": "-"}
    ut: list[list] = []
    utan_parti: list[list] = []
    for del_ in re.split(r",\s*|\s+och\s+", fore):
        del_ = re.sub(r"\s+i Härnösand$", "", del_.strip())
        p = re.fullmatch(rf"(?P<namn>{_NAMN.pattern}) \((?P<parti>[^)]+)\)", del_)
        if p and p["parti"] in kod:
            utan_parti.append([p["namn"], None])
            for x in utan_parti:
                x[1] = kod[p["parti"]]
            ut += utan_parti
            utan_parti = []
        elif del_ in _PARTINAMN:
            if utan_parti:
                for x in utan_parti:
                    x[1] = _PARTINAMN[del_]
                ut += utan_parti
                utan_parti = []
            else:
                ut.append([None, _PARTINAMN[del_]])
        elif _NAMN.fullmatch(del_):
            utan_parti.append([del_, None])
        else:
            utan_parti = []
    ut += utan_parti
    return [(n, p) for n, p in ut]


def _reservationer(text: str) -> list[Reservation]:
    """En reservation per mening som innehåller "reserverar sig". Skriftliga reservationer följer
    i protokollet efter meningen och tas med i texten."""
    if not text:
        return []
    meningar = re.split(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ])", text)
    ut: list[Reservation] = []
    for m in meningar:
        if "reserver" in m or not ut:
            personer = [(p["namn"], p["parti"]) for p in _NAMN_PARTI.finditer(m.split("reserver")[0])]
            partier = [kort for namn, kort in _PARTINAMN.items() if re.search(rf"\b{namn}\b", m.split("reserver")[0])]
            ut.append(Reservation(text=m, personer=personer, partier=partier))
        else:
            ut[-1].text = f"{ut[-1].text} {m}"
    return ut


# Voteringar
#
# En votering inleds med ordförandens propositionsordning ("ställer följande propositionsordning")
# och följs av utfallet. Voteringslistorna står i samma paragraf, direkt efter utfallet eller
# samlade under "Voteringsbilagor", i samma ordning som voteringarna. Listorna läses ur layouten,
# eftersom rösten i de flesta protokoll är ett kryss i kolumnen Ja, Nej eller Avstår.

_PARTIER = ("S", "V", "MP", "M", "C", "L", "KD", "SD", "-")
_ROSTORD = {"ja": "ja", "nej": "nej", "avstår": "avstar", "avstod": "avstar", "frånvarande": "franvarande"}


def _layoutrader(layout: list[str]) -> list[str]:
    """Layoutens rader utan sidhuvud, sidfot och organets namn överst på sidan."""
    ut: list[str] = []
    for sida in layout:
        rader = sida.splitlines()
        kvar = _sidmobler(sida)
        organ = kvar[0] if kvar and not kvar[0].startswith("§") and len(kvar[0].split()) <= 3 and not _ar_rubrik(kvar[0]) else None
        if any(r in ("Ärendelista", "Innehållsförteckning") for r in kvar[:4]):
            continue
        tillatna = set(kvar) - ({organ} if organ else set())
        ut.extend(r for r in rader if r.strip() and r.strip() in tillatna and not _sidhuvud(r))
    return ut


def _sidhuvud(rad: str) -> bool:
    """Sidhuvudets delar, som i layouten kan stå på samma rad: "SAMMANTRÄDESPROTOKOLL 16(39)"."""
    s = " ".join(rad.split())
    return bool(re.fullmatch(
        r"(?:Sida\s*)?(?:SAMMANTRÄDESPROTOKOLL\s*)?(?:Sida\s*)?(?:\d+\(\d+\))?|(?:Sammanträdesdatum\s*)?\d{4}-\s?\d{2}-\s?\d{2}"
        r"|Sammanträdesdatum", s
    ))


def _voteringar(t: Tolkning, layout: list[str]) -> None:
    behandlingar = {b.paragraf: b for b in t.behandlingar}
    rader = _layoutrader(layout)
    # Rader som kan inleda en paragraf: "§ N" följt av högst ett diarienummer.
    kandidater: list[tuple[int, int]] = []
    for i, r in enumerate(rader):
        s = re.sub(r"(\d{4})-\s+(\d)", r"\1-\2", " ".join(r.split()))  # "Dnr 2025- 000008"
        m = _PARAGRAFRAD.match(s)
        if not m or int(m[1]) not in behandlingar:
            continue
        rest = _DIARIENUMMER.sub("", m[2]).strip(" ,")
        if rest and not re.fullmatch(r"Dnr\.?:?\s*(\S*\d\S*)(?:\s+[\d.]+)?", rest):
            continue
        kandidater.append((i, int(m[1])))
    starter = _stigande(kandidater)
    for k, (i, nr) in enumerate(starter):
        slut = starter[k + 1][0] if k + 1 < len(starter) else len(rader)
        behandlingar[nr].voteringar = _voteringar_i(rader[i + 1 : slut])
    # Röster i en kolumn i närvarolistan före paragraferna ("Vot § 6"): "Hur de enskilda ledamöterna
    # röstat framgår av voteringskolumnen på sidan 2."
    for nr, roster in _rosttabeller(rader[: starter[0][0]] if starter else []):
        utan_lista = [v for v in behandlingar[nr].voteringar if not v.roster] if nr in behandlingar else []
        if utan_lista:
            utan_lista[0].roster = roster
    for _, nr in starter:
        b = behandlingar[nr]
        for v_nr, v in enumerate(b.voteringar, 1):
            if not v.roster:
                continue
            # Listan ska stämma med siffrorna i protokollets text. Avstår och frånvarande jämförs bara
            # när texten anger dem: texten nämner ofta inte en ensam ledamot som avstod.
            angivet = {"ja": v.ja, "nej": v.nej, "avstar": v.avstar, "franvarande": v.franvarande}
            slag = [r for r in ("ja", "nej", "avstar", "franvarande") if r in ("ja", "nej") or angivet[r] is not None]
            raknat = {r: sum(1 for x in v.roster if x.rost == r) for r in slag}
            angivet = {r: angivet[r] for r in slag}
            if v.ja is not None and raknat != angivet:
                ord_ = {"ja": "ja", "nej": "nej", "avstar": "avstår", "franvarande": "frånvarande"}
                t.avvikelser.append(
                    f"§ {nr}, votering {v_nr}: voteringslistan har "
                    + ", ".join(f"{raknat[r]} {ord_[r]}" for r in slag)
                    + ", protokollets text " + ", ".join(f"{angivet[r]} {ord_[r]}" for r in slag)
                )


def _stigande(kandidater: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Den längsta följden med stigande paragrafnummer. Paragraferna kommer i nummerordning,
    medan en paragrafhänvisning i en förteckning före dem inte gör det."""
    if not kandidater:
        return []
    langd = [1] * len(kandidater)
    fore = [-1] * len(kandidater)
    for b in range(len(kandidater)):
        for a in range(b):
            if kandidater[a][1] < kandidater[b][1] and langd[a] + 1 > langd[b]:
                langd[b], fore[b] = langd[a] + 1, a
    k = max(range(len(kandidater)), key=lambda x: (langd[x], -x))
    ut = []
    while k != -1:
        ut.append(kandidater[k])
        k = fore[k]
    return ut[::-1]


# "Ordföranden ställer följande propositionsordning". Textlagret kan dela ordet: "propositi onsordning".
_PROPOSITION = re.compile(r"ställer (?:upp )?följande\s*" + r"\s?".join("propositionsordning"), re.I)


def _voteringar_i(rader: list[str]) -> list[Votering]:
    text = [" ".join(r.split()) for r in rader]
    anslag = [i for i, s in enumerate(text) if _PROPOSITION.search(s)]
    voteringar: list[Votering] = []
    for k, i in enumerate(anslag):
        slut = anslag[k + 1] if k + 1 < len(anslag) else len(text)
        # Utfallet står i texten direkt efter propositionsordningen, före en tabell eller nästa rubrik.
        stycke: list[str] = []
        for s in text[i:slut]:
            if _tabellhuvud(s) or (stycke and _ar_rubrik(s)):
                break
            stycke.append(s)
        v = _utfall(_lopande(stycke))
        if v.ja is None or v.resultat is None:
            # Utfallet kan stå efter voteringslistan.
            efter = _utfall(_lopande(text[i:slut]))
            if v.ja is None:
                v.ja, v.nej, v.avstar, v.franvarande = efter.ja, efter.nej, efter.avstar, efter.franvarande
            v.resultat = v.resultat or efter.resultat
        voteringar.append(v)
    tabeller = _rosttabeller(rader)
    for v, (_, roster) in zip(voteringar, tabeller):
        v.roster = roster
    return voteringar


def _utfall(text: str) -> Votering:
    ja_f = nej_f = None
    for monster in (
        # "ja för kommunstyrelsens förslag och nej för …", "ja till …", "ja för liggande förslag och nej återremiss"
        r"\bja (?:för|till) (?P<ja>.+?),? och nej (?:för |till )?(?P<nej>.+?)\s?\.",
        r"\bJa = (?P<ja>.+?)\s?\.\s*Nej = (?P<nej>.+?)\s?\.",
        r"vill att (?P<ja>.+?) röstar ja och den som vill att (?P<nej>.+?) röstar nej",
    ):
        if m := re.search(monster, text, re.I):
            # "Ja = ärendet ska avgöras idag (21)": siffran i parentes hör till utfallet.
            ja_f, nej_f = (re.sub(r"\s*\(\d+\)$", "", m[k].strip()) for k in ("ja", "nej"))
            break

    def tal(ord_: str) -> int | None:
        # "21 ja", "21 röstar ja", "6 stycken ja-röster". Inte paragrafen i ett tabellhuvud ("§ 121 Ja Nej").
        m = re.search(rf"(?<![§\d/.-])(?<!§ )\b(\d+)\s*(?:stycken\s+)?(?:som\s+)?(?:röstar\s+)?{ord_}", text, re.I)
        return int(m[1]) if m else None

    ja, nej, avstar = tal(r"ja\b"), tal(r"nej\b"), tal(r"avst(?:år|od)")
    franvarande = [int(m[1]) for m in re.finditer(r"(\d+)\s*(?:frånvarande|tom(?:ma)? stol(?:ar)?|som inte röstat)", text, re.I)]
    # Ordförandens sista konstaterande är beslutet ("… konstaterar att 21 röstar Ja, och 18 röstar Nej.
    # Ordförande konstaterar att fullmäktige beslutat enligt …").
    resultat = None
    for m in re.finditer(r"(?:finner|konstaterar)\s+(?:efter acklamation\s+)?(?:ordförande[n]?\s+)?(?:därmed\s+)?att\s+(?P<res>.+?)\.", text, re.I):
        if not re.match(r"\d+ röstar", m["res"]):
            resultat = m["res"].strip()
    return Votering(ja_forslag=ja_f, nej_forslag=nej_f, ja=ja, nej=nej, avstar=avstar, resultat=resultat,
                    franvarande=sum(franvarande) if franvarande else None)


def _tabellhuvud(s: str) -> bool:
    return bool(re.match(_KOLUMNHUVUD, s) or re.match(r"#\s+Namn och parti\s+Röst$", s)
                or _NAMNKOLUMN_HUVUD.fullmatch(s) or _NAMN_ROST_HUVUD.fullmatch(s))


_NAMN_ROST_HUVUD = re.compile(r"Namn\s+Röst")
_KOLUMNHUVUD = r"Ledamot\b.*\bParti?\b"  # "Part" med "i" på nästa rad
_NAMNKOLUMN_HUVUD = re.compile(r"Ledamot/tjänstgörande ersättare(?:\s*§\s*(\d+))?\s+Ja\s+Nej\b.*")


def _rosttabeller(rader: list[str]) -> list[tuple[int | None, list[Rost]]]:
    """Voteringslistorna, med paragrafen som tabellhuvudet anger ("Vot § 18") när det gör det."""
    tabeller: list[tuple[int | None, list[Rost]]] = []
    i = 0
    while i < len(rader):
        s = " ".join(rader[i].split())
        paragraf = re.search(r"§\s*(\d+)", s)
        nr = int(paragraf[1]) if paragraf else None
        # En närvarolista har samma kolumner men ingen kolumn för Ja och Nej.
        if re.match(_KOLUMNHUVUD, s) and any(
            re.search(r"\bJa\b.*\bNej\b", r, re.I) for r in rader[i : i + 3]
        ):
            ut, i = _kolumntabell(rader, i)
            tabeller += ut
        elif _NAMNKOLUMN_HUVUD.fullmatch(s):
            roster, i = _namnkolumntabell(rader, i)
            tabeller.append((nr, roster))
        elif re.match(r"#\s+Namn och parti\s+Röst$", s):
            roster, i = _numrerad_tabell(rader, i + 1)
            tabeller.append((nr, roster))
        elif _NAMN_ROST_HUVUD.fullmatch(s):
            roster, i = _namn_rost_tabell(rader, i + 1)
            tabeller.append((nr, roster))
        else:
            i += 1
    return tabeller


def _namnkolumntabell(rader: list[str], i: int) -> tuple[list[Rost], int]:
    """Tabell med "Namn (Parti)" i en kolumn och kryss under Ja, Nej eller Avstår."""
    kolumner = {
        ("avstar" if m[1].startswith("Avst") else _ROSTORD[m[1].lower()]): m.start()
        for m in re.finditer(r"\b(Ja|Nej|Avst\w*)", rader[i])
    }
    roster: list[Rost] = []
    i += 1
    while i < len(rader):
        m = re.fullmatch(r"\s*(?P<namn>\S.*?)(?: \((?P<parti>[A-ZÅÄÖ]{1,4}|-)\))?\s{2,}(?P<x>X|x)\s*", rader[i])
        if not m:
            break
        rost = min(kolumner, key=lambda k: abs(kolumner[k] - m.start("x")))
        roster.append(Rost(namn=" ".join(m["namn"].split()), parti=m["parti"], rost=rost))
        i += 1
    return roster, i


def _kolumntabell(rader: list[str], i: int) -> tuple[list[tuple[int | None, list[Rost]]], int]:
    """Tabell med kolumnerna Ledamot, Ersättare, Parti och Ja, Nej (och ibland Avstår). En
    närvaro- och voteringslista kan ha flera voteringar bredvid varandra ("Vot § 96", "Vot § 98")."""
    parti_pos = re.search(r"\bParti?\b", rader[i]).start()
    # "Vot § 18". Numret kan stå på raden under: "Vot §" / "158".
    voteringar: list[int] = []
    for m in re.finditer(r"§\s*(\d+)?", rader[i]):
        if m[1]:
            voteringar.append(int(m[1]))
        elif i + 1 < len(rader) and (n := re.compile(r"\d+").search(rader[i + 1], max(m.start() - 6, 0), m.end() + 8)):
            voteringar.append(int(n[0]))
    # Kolumnernas läge räknas från partikolumnen. Typsnittet är proportionellt, så krysset hamnar
    # längre till höger ju längre namnet är, men avståndet från partiet är stabilt. Det gäller även
    # när tabellen fortsätter på en ny sida med annan indragning. Rubrikerna för Ja och Nej kan stå
    # på flera rader när voteringarna har olika många rubrikrader.
    rubriker: list[tuple[str, int]] = []
    j = i
    for k in range(i, min(i + 4, len(rader))):
        if k > i and _kolumnrad(rader[k], {}):
            break
        traffar = list(re.finditer(r"\b(Ja|Nej|Avst\w*)\b", rader[k], re.I))  # avkortad: "Avst"
        rubriker += [("avstar" if m[1].lower().startswith("avst") else _ROSTORD[m[1].lower()], m.start() - parti_pos)
                     for m in traffar]
        if traffar:
            j = k
    rubriker.sort(key=lambda r: r[1])
    # Rester av avstavade rubriker under tabellhuvudet: "o" (När/var/o), "i" (Part/i).
    while j + 1 < len(rader) and re.fullmatch(r"\s*[a-zåäö.\d]{1,4}(?:\s+[a-zåäö.\d]{1,4})*\s*", rader[j + 1]):
        j += 1
    narvaro = re.search(r"\bNär", rader[i])  # närvaro- och voteringslistan har en kolumn för närvaro först
    # Varje votering har sina kolumner, som börjar med Ja.
    grupper: list[dict[str, float]] = []
    for slag, pos in rubriker:
        if slag == "ja" or not grupper:
            grupper.append({})
        grupper[-1][slag] = pos
    if len(voteringar) > 1 and len(grupper) == len(voteringar):
        grupper = _kolumnlagen(rader, j + 1, grupper, narvaro.start() - parti_pos if narvaro else None)
        tabeller = [(nr, _kolumnroster(rader, j + 1, kolumner, nr)) for nr, kolumner in zip(voteringar, grupper)]
        return [(nr, roster) for nr, (roster, _) in tabeller], max(slut for _, (_, slut) in tabeller)
    grupper = [{k: v for g in grupper for k, v in g.items()}]
    [kolumner] = _kolumnlagen(rader, j + 1, grupper, narvaro.start() - parti_pos if narvaro else None)
    if narvaro and "narvaro" not in kolumner:
        kolumner["narvaro"] = narvaro.start() - parti_pos
    paragraf = voteringar[0] if voteringar else None
    roster, i = _kolumnroster(rader, j + 1, kolumner, paragraf)
    return [(paragraf, roster)], i


def _markeringar(r: str) -> tuple[re.Match | None, list[re.Match]]:
    """Partiet på raden och kryssen och strecken till höger om det."""
    rad = _kolumnrad(r, {})
    if rad is None:
        return None, []
    p = rad.parti_match
    return p, [m for m in re.finditer(r"(?<=\s)(?:X|x|-)(?=\s|$)", r) if m.start() >= p.end()]


def _kolumnlagen(rader: list[str], i: int, grupper: list[dict[str, float]],
                 narvaro: float | None) -> list[dict[str, float]]:
    """Kolumnernas läge ur kryssen själva. Rubrikerna kan stå långt från kryssen, så långt att
    de inte avgör vilken kolumn eller votering ett kryss hör till. Kryssen samlas i klungor som
    tilldelas kolumnerna i ordning, så nära rubrikerna som möjligt. Bara rader med partiet på det
    vanligaste stället räknas: på en ny sida kan både indragning och avstånd vara andra."""
    _, slut = _kolumnroster(rader, i, {}, None)  # tabellens slut beror inte på kolumnerna
    rader_med_parti = [(p, marken) for r in rader[i:slut] for p, marken in [_markeringar(r)] if p is not None]
    vanligast = Counter(p.start() for p, _ in rader_med_parti).most_common(1)
    lagen = [m.start() - p.start() for p, marken in rader_med_parti
             if abs(p.start() - vanligast[0][0]) <= 2 for m in marken]
    klungor: list[list[int]] = []
    for x in sorted(lagen):
        if klungor and x - klungor[-1][-1] <= 2:
            klungor[-1].append(x)
        else:
            klungor.append([x])
    mitt = [sum(k) / len(k) for k in klungor]
    kolumner = ([("narvaro", -1, narvaro)] if narvaro is not None else []) + [
        (slag, g, pos) for g, grupp in enumerate(grupper) for slag, pos in grupp.items()
    ]
    if len(mitt) > len(kolumner):
        mitt = []  # kryssen bildar inga tydliga kolumner: rubrikernas läge gäller
    # Ordningsbevarande tilldelning av klungor till kolumner som minimerar avståndet.
    n, k = len(kolumner), len(mitt)
    kostnad = [[float("inf")] * (n + 1) for _ in range(k + 1)]
    kostnad[0] = [0.0] * (n + 1)
    for a in range(1, k + 1):
        for b in range(a, n + 1):
            kostnad[a][b] = min(kostnad[a][b - 1], kostnad[a - 1][b - 1] + abs(mitt[a - 1] - kolumner[b - 1][2]))
    lage = {c: c[2] for c in kolumner}
    a, b = k, n
    while a > 0:
        if kostnad[a][b] == kostnad[a][b - 1] and b > a:
            b -= 1
            continue
        lage[kolumner[b - 1]] = mitt[a - 1]
        a, b = a - 1, b - 1
    ut = [{slag: lage[(slag, g, pos)] for slag, pos in grupp.items()} for g, grupp in enumerate(grupper)]
    if narvaro is not None:
        for grupp in ut:
            grupp["narvaro"] = lage[kolumner[0]]
    # Övriga voteringars kolumner räknas som närvaro, så att deras kryss inte läses som röster här.
    for g, grupp in enumerate(ut):
        for h, annan in enumerate(ut):
            if h != g:
                for slag, pos in annan.items():
                    if slag != "narvaro":
                        grupp[f"annan{h}{slag}"] = pos
    return ut


def _kolumnroster(rader: list[str], i: int, kolumner: dict[str, float], paragraf: int | None) -> tuple[list[Rost], int]:
    rader_ut: list[_Tabellrad] = []
    while i < len(rader):
        r = rader[i]
        rad = _kolumnrad(r, kolumner)
        if rad:
            rader_ut.append(rad)
        elif set(r.split()) == {"röstat"}:
            pass  # "Ej" / "röstat" under varje kolumn
        elif r[:1].strip() and len(r.split()) <= 2:
            pass  # organets namn överst på en ny sida, i vänstermarginalen
        elif rader_ut and (delar := _fortsattningar(r)):
            # Ett namn som bryts över två rader ("Anne-Cathrine" / "Genberg §§ 30-32"), och paragrafer
            # under ledamoten och ersättaren på samma rad ("§§ 57-61, 63-65      § 66").
            sista = rader_ut[-1]
            for borjan, fortsattning in delar:
                if sista.ersattare and borjan >= sista.ers_borjan - 3:
                    person = sista.ersattare_alla[-1]
                    if fortsattning.namn and person.paragrafer:
                        # Flera ersättare vid olika paragrafer: "Brendan Mc Carthy §§ 57-61" / "Hans Rosengren § 66".
                        sista.ersattare_alla.append(fortsattning)
                        continue
                else:
                    person = sista.ledamot
                person.lagg_till(fortsattning)
        else:
            break
        i += 1
    return [rost for rad in rader_ut if (rost := rad.rost(paragraf))], i


@dataclass
class _Person:
    namn: str
    paragrafer: list[int] | None = None  # "Mohamed Abdulwahab § 12": bara vid vissa paragrafer
    ref: str = ""  # hänvisningen som den står, eftersom den kan brytas: "§§ 57-" / "61, 63-64"

    def lagg_till(self, annan: "_Person") -> None:
        self.namn = f"{self.namn} {annan.namn}".strip()
        if annan.ref:
            self.ref = f"{self.ref} {annan.ref}".strip()
            self.paragrafer = paragraflista(self.ref)


_PARAGRAFREF = r"§§?\s*\d[\d\s,\-–]*"


def _person_i_kolumn(text: str) -> _Person:
    # "Bengt Wallgren §" med paragrafnumret på nästa rad: tecknet tas bort, numret läses som fortsättning.
    m = re.fullmatch(rf"(?P<namn>.*?)\s*(?:(?P<ref>{_PARAGRAFREF})|§§?)?", text.strip())
    # Rollen efter namnet hör inte till namnet: "Hans Rosengren (1 vice)", "(ordf)".
    namn = re.sub(r"\s*\((?:\d:?e?\s*vice|vice|ordf\.?|ordförande)\)$", "", m["namn"], flags=re.I)
    return _Person(namn=namn, paragrafer=paragraflista(m["ref"]) if m["ref"] else None, ref=m["ref"] or "")


@dataclass
class _Tabellrad:
    ledamot: _Person
    ersattare: _Person | None
    ers_borjan: int  # var ersättarkolumnen börjar på raden
    parti: str
    markering: str | None  # 'ja' | 'nej' | 'avstar' ur krysset eller ordet, None utan kryss
    streck: bool
    avstar_kolumn: bool = False
    parti_match: re.Match | None = None

    ersattare_alla: list[_Person] = field(default_factory=list)

    def rost(self, paragraf: int | None) -> Rost | None:
        if len(self.ersattare_alla) > 1:
            # Flera ersättare: den som tjänstgjorde vid paragrafen, annars ingen.
            vid = [p for p in self.ersattare_alla if paragraf is not None and p.paragrafer and paragraf in p.paragrafer]
            return _eget_parti(_tabellrost(copy.copy(self) if not vid else _med_ersattare(self, vid[0]), paragraf, ingen=not vid))
        return _eget_parti(_tabellrost(self, paragraf))


def _eget_parti(r: Rost | None) -> Rost | None:
    """En ersättare från ett annat parti står med partiet efter namnet: "Keith Bryant (V)" på en
    plats för S. Partikolumnen gäller ledamoten."""
    if r is None:
        return None
    if r.namn and (m := re.fullmatch(r"(.+?) \(([A-ZÅÄÖ]{1,4}|-)\)", r.namn)):
        r.namn, r.parti = m[1], m[2]
    if r.ersatt and (m := re.fullmatch(r"(.+?) \(([A-ZÅÄÖ]{1,4}|-)\)", r.ersatt)):
        r.ersatt, r.ersatt_parti = m[1], m[2]
    return r


def _med_ersattare(rad: "_Tabellrad", ersattare: _Person) -> "_Tabellrad":
    ny = copy.copy(rad)
    ny.ersattare = ersattare
    return ny


def _tom(namn: str) -> bool:
    return bool(re.fullmatch(r"-*\s*(?:tom stol|vakant)\s*-*", namn, re.I))


def _tabellrost(rad: "_Tabellrad", paragraf: int | None, ingen: bool = False) -> Rost | None:
    """Vem som röstade och hur. Har ledamoten eller ersättaren paragrafer ("§§ 19-29") avgör
    voteringens paragraf vem av dem som var beslutande. `ingen`: ingen av ersättarna tjänstgjorde."""
    led, ers, rost = rad.ledamot, None if ingen else rad.ersattare, rad.markering

    def vid(p: _Person) -> bool | None:
        return None if p.paragrafer is None or paragraf is None else paragraf in p.paragrafer

    if ers and _tom(ers.namn):
        # Tom stol vid vissa paragrafer ("Tom stol § 12"), annars hela sammanträdet.
        if vid(ers) is False:
            ers = None
        else:
            # Ett kryss på en tom stol räknas inte: protokollets text räknar platsen som tom.
            return Rost(namn=None if _tom(led.namn) else led.namn, parti=rad.parti, rost="franvarande")
    if rost is None and rad.streck:
        # Streck i stället för kryss. Har tabellen en kolumn för Avstår betyder streck i alla kolumner
        # att ledamoten inte röstade. Utan den kolumnen markerar strecken att ledamoten avstod.
        rost = "franvarande" if rad.avstar_kolumn else "avstar"
    if _tom(led.namn):
        if not ers:
            return Rost(namn=None, parti=rad.parti, rost="franvarande")  # tom stol utan namn
        return Rost(namn=ers.namn, parti=rad.parti, rost=rost or "franvarande")
    if ers and (vid(ers) is False or vid(led) is True):
        ers = None  # ledamoten var beslutande vid den här paragrafen
    if rost is None:
        return Rost(namn=ers.namn if ers else led.namn, parti=rad.parti, rost="franvarande")
    if ers:
        return Rost(namn=ers.namn, parti=rad.parti, rost=rost, ersatt=led.namn, ersatt_parti=rad.parti)
    return Rost(namn=led.namn, parti=rad.parti, rost=rost)


def _fortsattningar(r: str) -> list[tuple[int, _Person]] | None:
    """En fortsättningsrad, uppdelad i kolumner. En rad med flera kolumner godtas bara när
    den har paragrafhänvisningar."""
    delar = [(m.start(), _fortsattning(m[0])) for m in re.finditer(r"\S+(?: \S+)*", r)]
    if not delar or any(f is None for _, f in delar):
        return None if len(delar) != 1 or (f := _fortsattning(r)) is None else [(len(r) - len(r.lstrip()), f)]
    if len(delar) > 1 and not any(f.paragrafer for _, f in delar):
        return None
    return delar  # type: ignore[return-value]


def _fortsattning(r: str) -> _Person | None:
    s = r.strip()
    if not s or _ar_rubrik(" ".join(s.split())):
        return None  # t.ex. "Reservationer" direkt efter tabellen
    if re.fullmatch(r"\d[\d\s,.\-–]*", s):  # "154, 156.169": punkt i stället för streck förekommer
        return _Person(namn="", paragrafer=paragraflista(s), ref=s)  # "§" på raden före
    p = _person_i_kolumn(s)
    if not p.namn:
        return p if p.paragrafer else None
    if len(p.namn.split()) <= 2 and re.fullmatch(rf"{_ORD}(?: {_ORD})?", p.namn) or _tom(p.namn):
        return p
    return None


_MARKERINGAR = re.compile(r"(?:\s+(?:X|x|-|[Jj]a|[Nn]ej|[Aa]vstår|Ej(?: röstat)?|§§?|[\d\-–,]+))*\s*")


def _kolumnrad(r: str, kolumner: dict[str, float]) -> "_Tabellrad | None":
    """En rad i tabellen. Partiet är det första parti som bara följs av röstmarkeringar
    ("X", "-", "Avstår", "§§ 19-30")."""
    p = next(
        (m for m in re.finditer(r"(?<=\s)(KD|SD|MP|S|V|M|C|L|-)(?=\s|$)", r)
         if r[: m.start()].strip() and _MARKERINGAR.fullmatch(r[m.end() :])),
        None,
    )
    if p is None:
        return None
    # Kolumnerna till vänster om partiet: ledamot och ersättare, där en paragrafhänvisning
    # ("§§ 19-29") kan stå i en egen kolumn efter namnet. Ett ensamt kryss räknas inte.
    personer: list[tuple[int, _Person]] = []
    for m in re.finditer(r"\S+(?: \S+)*", r[: p.start()]):
        if m[0] in ("X", "x", "-"):
            continue
        if re.fullmatch(_PARAGRAFREF, m[0]) and personer:
            personer[-1][1].lagg_till(_Person(namn="", ref=m[0]))
            continue
        personer.append((m.start(), _person_i_kolumn(m[0])))
    if not personer:
        return None
    rost = None
    streck = False
    for m in re.finditer(r"\S+", r[p.end() :]):
        tecken, pos = m[0], p.end() + m.start()
        kolumn = min(kolumner, key=lambda k: abs(kolumner[k] - (pos - p.start()))) if kolumner else None
        if kolumn not in (None, "ja", "nej", "avstar"):
            continue  # "X", "-" eller "§§ 1-11" i närvarokolumnen, eller en annan voterings kolumn
        if tecken.lower() in _ROSTORD:
            rost = _ROSTORD[tecken.lower()]
        elif tecken == "Ej":  # "Ej röstat"
            rost = "franvarande"
        elif tecken in ("X", "x") and kolumn:
            rost = kolumn
        elif tecken == "-":
            streck = True
        if rost:
            break
    ersattare = None
    if len(personer) > 1:
        ersattare = _Person(" ".join(q.namn for _, q in personer[1:]), personer[-1][1].paragrafer, personer[-1][1].ref)
    return _Tabellrad(ledamot=personer[0][1], ersattare=ersattare, ersattare_alla=[ersattare] if ersattare else [],
                      ers_borjan=personer[1][0] if len(personer) > 1 else 10**6,
                      parti=p[1], markering=rost, streck=streck, avstar_kolumn="avstar" in kolumner,
                      parti_match=p)


_NUMRERAD_RAD = re.compile(r"(\d+)\s+(?P<np>.+?)\s+(?P<rost>Ja|Nej|Avstår|Frånvarande)")
_NAMN_OCH_PARTI = re.compile(
    r"(?P<namn>.+?) \((?P<parti>[^)]*)\)(?: \(-\))?(?: ersatt av (?P<ers>.+?) \((?P<ersp>[^)]*)\))?"
)


def _numrerad_tabell(rader: list[str], i: int) -> tuple[list[Rost], int]:
    """Numrerad lista med "Namn och parti" och "Röst", där en ersättare står som "X ersatt av Y"."""
    roster: list[Rost] = []
    while i < len(rader):
        s = " ".join(rader[i].split())
        m = _NUMRERAD_RAD.fullmatch(s)
        n = _NAMN_OCH_PARTI.fullmatch(m["np"]) if m else None
        if not n:
            break
        rost = _ROSTORD[m["rost"].lower()]
        parti = n["parti"] or None
        if n["ers"]:
            roster.append(Rost(namn=n["ers"], parti=n["ersp"] or None, rost=rost, ersatt=n["namn"], ersatt_parti=parti))
        else:
            roster.append(Rost(namn=n["namn"], parti=parti, rost=rost))
        i += 1
    return roster, i


_NAMN_ROST_RAD = re.compile(r"\s*(?P<text>\S.*?)\s{2,}(?P<rost>ja|nej|avstår)\s*", re.I)
_NAMN_ROST_PERSON = re.compile(
    r"(?P<namn>.+?) \((?P<parti>[^)]*)\)(?: tjänstgörande ersättare för (?P<ers>.+?)(?: \((?P<ersp>[^)]*)\))?)?"
)


def _namn_rost_tabell(rader: list[str], i: int) -> tuple[list[Rost], int]:
    """Lista med "Namn (Parti)" och rösten (JA, NEJ) i en kolumn per svar. En tjänstgörande
    ersättare står som "Namn (S) tjänstgörande ersättare för Annan (S)", ofta över två rader."""
    rader_ut: list[list[str]] = []
    while i < len(rader):
        if m := _NAMN_ROST_RAD.fullmatch(rader[i]):
            rader_ut.append([m["text"], m["rost"].lower()])
        elif rader_ut and not rader[i].strip().startswith("Totalt") and not _ar_rubrik(" ".join(rader[i].split())):
            rader_ut[-1][0] += " " + rader[i].strip()
        else:
            break
        i += 1
    roster: list[Rost] = []
    for text, rost in rader_ut:
        n = _NAMN_ROST_PERSON.fullmatch(" ".join(text.split()))
        if not n:
            return [], i  # en rad som inte går att läsa: hellre ingen lista än en ofullständig
        roster.append(Rost(namn=n["namn"], parti=n["parti"] or None, rost=_ROSTORD[rost],
                           ersatt=n["ers"], ersatt_parti=n["ersp"] if n["ers"] else None))
    return roster, i


# Kontroller mot protokollets egna uppgifter


def _kontrollera(t: Tolkning, lop: list[str], layout: list[str]) -> None:
    funna = [b.paragraf for b in t.behandlingar]
    if len(set(funna)) != len(funna):
        t.avvikelser.append("Samma paragraf förekommer flera gånger")
    if vantade := paragrafintervall(layout):
        if set(vantade) != set(funna):
            saknas = sorted(set(vantade) - set(funna))
            extra = sorted(set(funna) - set(vantade))
            delar = [f"saknas: {', '.join(map(str, saknas))}" if saknas else "",
                     f"oväntade: {', '.join(map(str, extra))}" if extra else ""]
            t.avvikelser.append(f"Paragraferna stämmer inte med protokollets paragrafintervall ({'; '.join(d for d in delar if d)})")


_DELEGATION = re.compile(
    r"^(?P<vem>[A-ZÅÄÖ][\wåäö-]*s (?:presidium|arbetsutskott|ordförande))\s+beslutar\s+(?:med|på|enligt)\s+delegation\b")


def _sittningar(t: Tolkning, layout: list[str]) -> None:
    """Ett protokoll med flera sittningar samma dag (#85): varje sittnings plats, tid och paragrafer, och
    närvaron per sittning. En person som var med vid en sittning får den sittningens paragrafer."""
    sidor = _sittningssidor(layout)
    if len(sidor) < 2:
        return
    forsta = _sidans_intervall(layout[0])
    if not forsta:
        t.avvikelser.append("Protokollet har flera sittningar, men den första sittningens paragrafer anges inte")
        return
    sittningar = [Sittning(t.plats, t.starttid, t.sluttid, forsta)]
    narvaro = [t.narvaro]
    for i in sidor[1:]:
        plats_rad = next(r for r in layout[i].splitlines() if "Plats och tid" in r)
        egen = Tolkning()
        if not _narvaro_forsta_sidan(egen, layout[i]):
            t.avvikelser.append(f"Närvarolistan för sittningen på sida {i + 1} hittades inte")
            return
        sittningar.append(Sittning(*_plats_och_tid(plats_rad), _sidans_intervall(layout[i])))
        narvaro.append(egen.narvaro)
    alla = sorted({p for s in sittningar for p in s.paragrafer})
    sammanslagen: dict[tuple, Narvaro] = {}
    for s, personer in zip(sittningar, narvaro):
        for n in personer:
            egna = [p for p in (n.paragrafer if n.paragrafer is not None else s.paragrafer) if p in s.paragrafer]
            nyckel = (n.namn, n.kategori, n.tjanstgor_for)
            if (tidigare := sammanslagen.get(nyckel)) is None:
                sammanslagen[nyckel] = copy.copy(n)
                sammanslagen[nyckel].paragrafer = egna
                sammanslagen[nyckel].jav = list(n.jav)
            else:
                tidigare.paragrafer = sorted({*tidigare.paragrafer, *egna})
                tidigare.jav = sorted({*tidigare.jav, *n.jav})
    for n in sammanslagen.values():
        if n.paragrafer == alla:
            n.paragrafer = None
    t.narvaro = list(sammanslagen.values())
    for s in sittningar:
        beslut = [b.beslut or "" for b in t.behandlingar if b.paragraf in s.paragrafer]
        vem = {m["vem"] if (m := _DELEGATION.match(b.strip())) else None for b in beslut}
        if beslut and len(vem) == 1 and None not in vem:
            v = vem.pop()
            s.delegation = v[0].lower() + v[1:]
    t.sittningar = sittningar


def _forsta_sida(sida: str) -> bool:
    """Ett protokolls första sida. Sidnumret är 1 när det finns: en andra sittning samma dag
    kan ha egen 'Plats och tid' men fortsätter sidnumreringen."""
    nummer = re.search(r"\b(\d+)\(\d+\)", sida)
    return "Plats och tid" in sida and "Beslutande" in sida and (not nummer or nummer[1] == "1")


def _protokollets_sidor(lop: list[str], layout: list[str]) -> tuple[list[str], list[str]]:
    """Sidorna med själva protokollet. En kallelse före protokollet räknas inte, och inte heller
    ett protokollsutdrag eller bilagor efter det (de börjar med en ny förstasida)."""
    start = next((i for i, s in enumerate(lop[:3]) if _forsta_sida(s)), 0)
    slut = next((i for i in range(start + 1, len(lop)) if _forsta_sida(lop[i])), len(lop))
    return lop[start:slut], layout[start:slut]


def tolka(pdf: bytes) -> Tolkning:
    """Samma innehåll ger alltid samma tolkning, så resultatet återanvänds inom processen."""
    return copy.deepcopy(_tolka(pdf))


@lru_cache(maxsize=64)
def _tolka(pdf: bytes) -> Tolkning:
    t = Tolkning()
    try:
        lop, layout = sidtexter(pdf)
    except Exception as e:  # trasig eller krypterad PDF
        t.avvikelser.append(f"PDF:en kunde inte läsas ({type(e).__name__})")
        return t
    if not lop or not lop[0].strip():
        # Sidorna är bilder: inskannade, eller ett digitalt protokoll som plattats till bilder.
        # Texten läses då med OCR, om OCR finns.
        from . import ocr

        if not ocr.tillganglig():
            t.avvikelser.append("PDF:en saknar text (inskannad?)")
            return t
        try:
            lop, layout = ocr.sidtexter(pdf)
        except ocr.OcrSaknas as e:
            t.avvikelser.append(f"PDF:en saknar text och kunde inte läsas med OCR ({e})")
            return t
        if not lop or not lop[0].strip():
            t.avvikelser.append("PDF:en saknar text (inskannad?)")
            return t
        t.ocr = True
        t.avvikelser.append("PDF:en saknar text och har lästs med OCR")
    alla_sidor = len(lop)
    lop, layout = _protokollets_sidor(lop, layout)
    _sammantrade(t, lop, layout)
    if not _narvaro_forsta_sidan(t, layout[0] if layout else ""):
        t.narvaro = []
        if not _narvarotabeller(t, layout[:6]):
            t.avvikelser.append("Närvarolistan hittades inte")
    _behandlingar(t, lop, layout)
    _sittningar(t, layout)
    _voteringar(t, layout)
    if not t.behandlingar:
        t.avvikelser.append("Inga behandlingar hittades")
        # Ett protokollsutdrag har färre sidor än protokollet, men saknas alla behandlingar
        # kan filen vara ofullständig.
        angivna = re.search(r"\b1\((\d+)\)", lop[0])
        if angivna and alla_sidor < int(angivna[1]):
            t.avvikelser.append(f"PDF:en har {alla_sidor} av protokollets {angivna[1]} sidor")
    _kontrollera(t, lop, layout)
    return t


def beslutande_i(narvaro: list[Narvaro], paragrafer: list[int]) -> list[Narvaro]:
    """De som var beslutande vid någon av paragraferna, t.ex. en sittnings (#85)."""
    return [n for n in narvaro if n.kategori == "beslutande"
            and (n.paragrafer is None or set(n.paragrafer) & set(paragrafer))]


def beslutande_vid(narvaro: list[Narvaro], paragraf: int) -> list[Narvaro]:
    """De som var beslutande vid en viss paragraf, med hänsyn till jäv och tjänstgöring för vissa paragrafer."""
    return [
        n for n in narvaro
        if n.kategori == "beslutande"
        and (n.paragrafer is None or paragraf in n.paragrafer)
        and paragraf not in n.jav
    ]
