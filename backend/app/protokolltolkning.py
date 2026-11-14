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
    # Paragrafer personen var beslutande vid, om inte alla. None = hela sammanträdet.
    paragrafer: list[int] | None = None
    jav: list[int] = field(default_factory=list)


@dataclass
class Behandling:
    paragraf: int
    rubrik: str
    diarienummer: list[str]
    beslut: str | None


@dataclass
class Tolkning:
    datum: date | None = None
    starttid: str | None = None
    sluttid: str | None = None
    plats: str | None = None
    narvaro: list[Narvaro] = field(default_factory=list)
    behandlingar: list[Behandling] = field(default_factory=list)
    avvikelser: list[str] = field(default_factory=list)

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
_DIARIENUMMER = re.compile(r"\b([A-ZÅÄÖ]{2,6})\s?/\s?(\d{4})\s?[-:]\s?(\d+)\b")
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
        text = " ".join(plats_rad.split("Plats och tid", 1)[1].split())
        kl = re.search(r"\bkl\.?\s*", text)
        fore = text[: kl.start()] if kl else text
        plats = re.split(r",\s*(?=\d{4}-)|,?\s+(?:måndagen|tisdagen|onsdagen|torsdagen|fredagen|lördagen|söndagen)\b", fore)[0]
        t.plats = plats.strip(" ,") or None
        if kl:
            tider = list(_TID.finditer(text[kl.end() :]))
            if tider:
                t.starttid = _tid(tider[0])
            if len(tider) > 1:
                t.sluttid = _tid(tider[1])
        if t.datum is None:
            t.datum = _datum(text)
    if t.datum is None:
        t.avvikelser.append("Sammanträdesdatum hittades inte")


# Närvaro, form 1: lista på första sidan

_AVSNITT = {"Beslutande": "beslutande", "Ej tjänstgörande": "ej_tjanstgorande", "Övriga": "ovrig"}
_SLUT_PA_LISTA = ("Justerare", "Justeringens", "Sekreterare", "Utses att justera", "Underskrifter")


def _anteckning(n: Narvaro, text: str) -> None:
    text = " ".join(text.split())
    if m := re.search(r"Jäv\s*§+\s*([\d\s,\-–och]+)", text):
        n.jav = paragraflista(m[1])
        text = (text[: m.start()] + text[m.end() :]).strip()
    if m := re.search(r"Tjänstgörande för\s+(.+?)(?:\s*§+\s*([\d\s,\-–och]+))?$", text):
        n.tjanstgor_for, n.tjanstgor_for_parti = _namn_parti(m[1])
        if m[2]:
            n.paragrafer = paragraflista(m[2])
    elif m := re.fullmatch(r"§+\s*([\d\s,\-–och]+)", text):
        n.paragrafer = paragraflista(m[1])


def _narvaro_forsta_sidan(t: Tolkning, layout: str) -> bool:
    rader = layout.splitlines()
    start = next((i for i, r in enumerate(rader) if re.match(r"\s*Beslutande\s{2,}", r)), None)
    if start is None:
        return False
    kategori = "beslutande"
    namnkolumn = rollkolumn = None
    for rad in rader[start:]:
        if not rad.strip():
            continue
        falt = _falt(rad)
        etikett = falt[0][1] if falt and falt[0][0] < 10 else None
        if etikett:
            if etikett.startswith(_SLUT_PA_LISTA):
                break
            if etikett in _AVSNITT:
                kategori = _AVSNITT[etikett]
            elif etikett in ("Närvarande ej tjänstgörande", "Övriga närvarande", "Ersättare", "ersättare"):
                kategori = "ej_tjanstgorande" if "rsättare" in etikett or "ej" in etikett else "ovrig"
            else:
                break
            falt = falt[1:]
        if not falt:
            continue
        if namnkolumn is None:
            namnkolumn = falt[0][0]
            if len(falt) > 1:
                rollkolumn = falt[1][0]
        if "Se närvaro" in rad or "närvarolista" in rad:
            return False  # Listan finns på egna sidor.
        # En rad som bara fortsätter rollen ("ordförande" under "1:e vice").
        if t.narvaro and falt[0][0] > namnkolumn + 15:
            for kol, text in falt:
                if rollkolumn is not None and abs(kol - rollkolumn) < 15:
                    t.narvaro[-1].roll = f"{t.narvaro[-1].roll or ''} {text}".strip()
                else:
                    _anteckning(t.narvaro[-1], text)
            continue
        namn, parti = _namn_parti(falt[0][1])
        roll = falt[1][1] if len(falt) > 1 else None
        n = Narvaro(namn=namn, parti=parti, roll=roll, kategori=kategori)
        for _, text in falt[2:]:
            _anteckning(n, text)
        t.narvaro.append(n)
    return bool(t.narvaro)


# Närvaro, form 2: tabeller på egna sidor


def _kolumner(rubrikrad: str) -> list[tuple[int, str]]:
    return _falt(rubrikrad)


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
    for sida in layout:
        rader = sida.splitlines()
        for i, rad in enumerate(rader):
            if re.search(r"Närvaro.*lista.*ledamöter|Närvarolista ledamöter", rad):
                hittade |= _ledamotstabell(t, rader[i + 1 :])
            elif re.search(r"Närvaro.*tjänstgöringslista.*ersättare", rad):
                hittade |= _ersattartabell(t, rader[i + 1 :])
    return hittade


def _tabellrader(rader: list[str]):
    for rad in rader:
        if not rad.strip():
            continue
        if rad.strip().startswith(("Justerandes sign", "Utdragsbestyrkande")) or "Sida " in rad.strip()[:5]:
            return
        yield rad


def _narvarotecken(text: str | None) -> tuple[bool, list[int] | None]:
    """'X' = närvarande, '-' eller tomt = frånvarande, '§§ 1-6, 8-14' = närvarande vid de paragraferna."""
    text = (text or "").strip()
    if text.upper().startswith("X"):
        return True, None
    if "§" in text or re.search(r"\d", text):
        return True, paragraflista(text)
    return False, None


def _ledamotstabell(t: Tolkning, rader: list[str]) -> bool:
    rad_iter = _tabellrader(rader)
    rubrik = next(rad_iter, None)
    if not rubrik or "Ledamot" not in rubrik:
        return False
    kolumner = _kolumner(rubrik)
    for rad in rad_iter:
        v = _per_kolumn(rad, kolumner)
        namn = v.get("Ledamot")
        if not namn or namn.lower().startswith("vakant"):
            continue
        parti = v.get("Parti") or None
        narvarande, paragrafer = _narvarotecken(v.get("Närvaro"))
        t.narvaro.append(Narvaro(
            namn=" ".join(namn.split()), parti=parti, roll="Ledamot",
            kategori="beslutande" if narvarande else "franvarande", paragrafer=paragrafer,
        ))
    return True


def _ersattartabell(t: Tolkning, rader: list[str]) -> bool:
    rad_iter = _tabellrader(rader)
    rubrik = next(rad_iter, None)
    if not rubrik or "Ersättare" not in rubrik:
        return False
    kolumner = _kolumner(rubrik)
    partier = {n.namn: n.parti for n in t.narvaro}
    for rad in rad_iter:
        v = _per_kolumn(rad, kolumner)
        namn = v.get("Ersättare")
        if not namn or namn.lower().startswith("vakant"):
            continue
        parti = v.get("Parti") or None
        narvarande, paragrafer = _narvarotecken(v.get("Närvaro"))
        for_namn = v.get("Tjänstgöring")
        if not narvarande:
            continue  # Frånvarande ersättare tas inte med: de var inte kallade att tjänstgöra.
        n = Narvaro(namn=" ".join(namn.split()), parti=parti, roll="Ersättare",
                    kategori="beslutande" if for_namn else "ej_tjanstgorande")
        if for_namn:
            n.tjanstgor_for, n.tjanstgor_for_parti = " ".join(for_namn.split()), partier.get(for_namn)
            if m := re.search(r"§+\s*([\d\s,\-–och]+)$", for_namn):
                n.tjanstgor_for = for_namn[: m.start()].strip()
                n.paragrafer = paragraflista(m[1])
            elif paragrafer:
                n.paragrafer = paragrafer
        t.narvaro.append(n)
    return True


# Behandlingar

_PARAGRAFRAD = re.compile(r"^§\s*(\d+)\s*(.*)$")
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


def _ar_rubrik(rad: str) -> bool:
    return rad in _RUBRIKER or _beslutsrubrik(rad) or _beslutar(rad)


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


def _behandlingar(t: Tolkning, lop: list[str]) -> None:
    rader: list[str] = []
    for sida in lop:
        sidrader = _sidmobler(sida)
        if any(r in ("Ärendelista", "Innehållsförteckning", "Nummer Rubrik Sida") for r in sidrader[:4]):
            continue
        if sidrader and not sidrader[0].startswith("§") and len(sidrader[0].split()) <= 3 and not _ar_rubrik(sidrader[0]):
            organ = sidrader[0]
            sidrader = [r for r in sidrader if r != organ]
        if _SIGNERING in sida:
            sidrader = sidrader[: next((i for i, r in enumerate(sidrader) if r.startswith("Signering")), len(sidrader))]
            rader.extend(sidrader)
            break
        rader.extend(sidrader)

    starter: list[tuple[int, int, list[str]]] = []
    for i, r in enumerate(rader):
        m = _PARAGRAFRAD.match(r)
        if not m:
            continue
        rest = m[2].strip()
        dnr = [f"{d[0]}/{d[1]}-{d[2]}" for d in _DIARIENUMMER.findall(rest)]
        rest = _DIARIENUMMER.sub("", rest).strip(" ,")
        # "Dnr 80117": ett diarienummer i annan form.
        if m2 := re.fullmatch(r"Dnr\.?:?\s*(\S*\d\S*)(?:\s+[\d.]+)?", rest):
            dnr.append(m2[1])
            rest = ""
        # Innehållsförteckningens rader har rubrik efter numret, eller rubrik och sidnummer på nästa rad.
        if rest or (i + 1 < len(rader) and re.search(r"\.{5,}\s*\d*$", rader[i + 1])):
            continue
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
                    dnr = ["/".join(d[0:1] + (f"{d[1]}-{d[2]}",)) for d in _DIARIENUMMER.findall(r)]
        if not rubrik:
            t.avvikelser.append(f"§ {nr}: rubriken hittades inte")
        if beslut is None and any(_beslutsrubrik(r) or _beslutar(r) for r in kropp):
            t.avvikelser.append(f"§ {nr}: beslutet hittades inte")
        t.behandlingar.append(Behandling(paragraf=nr, rubrik=rubrik, diarienummer=dnr, beslut=beslut))


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


# Kontroller mot protokollets egna uppgifter


def _kontrollera(t: Tolkning, lop: list[str], layout: list[str]) -> None:
    funna = [b.paragraf for b in t.behandlingar]
    if len(set(funna)) != len(funna):
        t.avvikelser.append("Samma paragraf förekommer flera gånger")
    forsta = " ".join(layout[0].split()) if layout else ""
    if m := re.search(r"Paragrafer\s+(?:§+\s*)?([\d\s\-–,]+)", forsta):
        vantade = paragraflista(m[1])
        if vantade and set(vantade) != set(funna):
            saknas = sorted(set(vantade) - set(funna))
            extra = sorted(set(funna) - set(vantade))
            delar = [f"saknas: {', '.join(map(str, saknas))}" if saknas else "",
                     f"oväntade: {', '.join(map(str, extra))}" if extra else ""]
            t.avvikelser.append(f"Paragraferna stämmer inte med protokollets paragrafintervall ({'; '.join(d for d in delar if d)})")


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
    if not any(s.strip() for s in lop):
        t.avvikelser.append("PDF:en saknar text (inskannad?)")
        return t
    _sammantrade(t, lop, layout)
    if not _narvaro_forsta_sidan(t, layout[0] if layout else ""):
        t.narvaro = []
        if not _narvarotabeller(t, layout[:6]):
            t.avvikelser.append("Närvarolistan hittades inte")
    _behandlingar(t, lop)
    if not t.behandlingar:
        t.avvikelser.append("Inga behandlingar hittades")
    _kontrollera(t, lop, layout)
    return t


def beslutande_vid(narvaro: list[Narvaro], paragraf: int) -> list[Narvaro]:
    """De som var beslutande vid en viss paragraf, med hänsyn till jäv och tjänstgöring för vissa paragrafer."""
    return [
        n for n in narvaro
        if n.kategori == "beslutande"
        and (n.paragrafer is None or paragraf in n.paragrafer)
        and paragraf not in n.jav
    ]
