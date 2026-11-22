"""Föredragningslistan i kallelser, kungörelser och handlingar (#109).

Från augusti 2026 saknar protokollen diarienummer. Kallelsen har dem: föredragningslistans tabell
"Paragraf Rubrik Sida" följs av en sida per paragraf, med diarienumret överst:

    Härnösands kommun  Datum 2026-10-01  Sida 13(15)
    SKN/2026-717
    Svar på motion om kontinuitet i allmän förskola
    Förslag till beslut …

Paragrafnumret står ibland under diarienumret och saknas ibland. Tabellen saknar ibland kolumnen
Sida. Kallelserna finns i tre former:

- **Med sidhuvud** (skolnämnden, kommunstyrelsen, fullmäktige): paragrafsidorna har "Sida N(M)",
  där M är föredragningslistans längd och N sidan i tabellen. Paragrafen bestäms av paragrafnumret
  på sidan, annars av tabellens sida. Bilagorna efter sidan M läses inte.
- **Utan sidhuvud** (samhällsnämnden, socialnämnden): varje paragrafsida följs av sina bilagor, och
  tabellens sidnummer gäller inte PDF:en. En paragrafsida känns igen på att diarienumret, rubriken
  och "Förslag till beslut" (eller "… föreslås besluta") står överst. Paragrafen bestäms av
  paragrafnumret när det står, annars av rubriken i tabellens ordning.
- **Bara tjänsteskrivelser** (socialnämnden och samhällsnämnden i augusti–september 2026): tabellen
  följs direkt av bilagorna. Diarienumret tas då ur tjänsteskrivelsens sidhuvud ("Dnr SOC/2026-189")
  för de paragrafer vars sida inte hittades, när tjänsteskrivelsens rubrik liknar tabellens.

Kallelsens paragrafnummer är inte alltid protokollets (kommunstyrelsen 2026-09-29: 116–131 i
kallelsen, 131–143 i protokollet). Ihopparningen med protokollet görs därför i `app.kallelsepunkter`.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

# Diarienummer överst på en paragrafsida: "SKN/2026-717", "KS/2026-504", "MNP/2026-5", "KS 2025-000475",
# och samhällsnämndens serie för bygg- och miljöärenden, "SAM-2026-2266".
_DNR = re.compile(r"(?:Dnr:?\s*)?([A-ZÅÄÖ]{2,5})\s?([/ -])\s?(\d{4})\s?-\s?(\d+)")
# Rubriken på tabellen. Textutvinningen bryter ibland ordet: "Parag" / "raf Rubrik Sida".
_TABELLRUBRIK = re.compile(r"^Paragraf\s*Rubrik(\s*Sida)?$", re.I)
_SIDA = re.compile(r"^(?:Sida\s+)?(\d{1,4})\s*\((\d{1,4})\)(?:\s+Härnösands kommun)?$")
_SIDA_1 = re.compile(r"Sida\s+1\s*\((\d{1,4})\)")
_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HUVUD = {"härnösands kommun", "datum", "sida"}
# Raden efter rubriken på en paragrafsida.
_FORSLAG = re.compile(r"förslag till beslut|föreslås besluta|föreslår .*besluta|\bbeslut(ar)?$", re.I)
_RAD_HEL = re.compile(r"^(\d{1,3})\s+(.+?)\s+(\d{1,3})$")
_RAD_UTAN_RUBRIK = re.compile(r"^(\d{1,3})\s+(\d{1,3})$")
_RAD_UTAN_SIDA = re.compile(r"^(\d{1,3})\s+(\D.*)$")
_TAL = re.compile(r"^\d{1,3}$")
_ORDFORANDE = re.compile(r"^(ordförande|kommunfullmäktiges ålderspresident)$", re.I)
# Hålltider och punktlistor efter tabellen hör inte till den.
_EFTER_TABELLEN = re.compile(r"^(•|\d{1,2}[.:]\d{2}\b)")
_TJANSTESKRIVELSE = re.compile(r"^TJÄNSTESKRIVELSE\b")
_DNR_ETIKETT = re.compile(r"^(Dnr|Diarienummer):?\s*(.*)$")
_TJ_PREFIX = re.compile(r"^Tjänsteskrivelse\s*[-–]?\s*", re.I)

# Organens egna serier: "KS 2025-000475" i en kallelse från kommunstyrelsen skrivs som protokollen,
# "2025-000475", och tillhör då organets serie (arenden.serie).
_EGEN_SERIE = {"KS": "KS", "KF": "KS", "SAM": "SAM", "SOC": "SOC", "SKOL": "SKN"}


@dataclass(frozen=True)
class Punkt:
    paragraf: int | None  # kallelsens paragrafnummer
    rubrik: str  # rubriken på paragrafsidan (eller tjänsteskrivelsen), annars tabellens
    diarienummer: tuple[str, ...]
    sida: int | None  # sidan i PDF:en (från 1) där diarienumret står, None om sidan inte hittades
    tabellrubrik: str = ""  # rubriken i tabellen "Paragraf Rubrik Sida"


@dataclass(frozen=True)
class Foredragningslista:
    # 'last': läst, 'delvis_fel': delar kunde inte läsas, 'fel': PDF:en kunde inte läsas,
    # 'saknas': ingen föredragningslista (t.ex. "ärenden för kännedom" i en egen fil)
    status: str
    punkter: tuple[Punkt, ...] = ()
    fel: tuple[str, ...] = ()


@dataclass
class _Rad:
    paragraf: int
    rubrik: str | None
    sida: int | None
    sida_vantas: bool = False
    dnr: list[str] = field(default_factory=list)
    pdf_sida: int | None = None
    sidrubrik: str | None = None


def diarienummer(organ: str, prefix: str, skiljetecken: str, ar: str, lopnummer: str) -> str:
    if skiljetecken in "/-":
        return f"{prefix}{skiljetecken}{ar}-{lopnummer}"
    return f"{ar}-{lopnummer}" if _EGEN_SERIE.get(organ) == prefix else f"{prefix}/{ar}-{lopnummer}"


def _rader(text: str) -> list[str]:
    return [r for r in (" ".join(x.split()) for x in text.splitlines()) if r]


def _utan_huvud(rader: list[str]) -> tuple[list[str], tuple[int, int] | None]:
    """Raderna utan sidhuvudet, och (N, M) ur "Sida N(M)" när sidan har ett."""
    sida, i = None, 0
    while i < len(rader) and i < 8:
        r = rader[i]
        if r.lower() in _HUVUD or _DATUM.match(r):
            i += 1
        elif m := _SIDA.match(r):
            sida = (int(m[1]), int(m[2]))
            i += 1
        else:
            break
    return rader[i:], sida


def _tabellrubrik(rader: list[str]) -> tuple[int, bool] | None:
    """(index för första raden efter rubriken, om tabellen har kolumnen Sida)."""
    for n, r in enumerate(rader):
        for k, text in ((n + 1, r), (n + 2, r + (rader[n + 1] if n + 1 < len(rader) else ""))):
            if m := _TABELLRUBRIK.match(text):
                return k, bool(m[1])
    return None


def _tabell(rader: list[str], tabell: list[_Rad], med_sida: bool) -> None:
    """Raderna i tabellen "Paragraf Rubrik Sida". Textutvinningen skiljer ibland rubrikerna från
    numren (samhällsnämnden: "128 11" … "134 19" och rubrikerna efter), och de fördelas då i ordning."""
    losa: list[str] = []
    forra = ""  # den senaste fortsättningsraden (utan kolumnen Sida)
    for r in rader:
        sista = tabell[-1] if tabell else None
        if _EFTER_TABELLEN.match(r):
            break
        if not med_sida:
            if m := _RAD_UTAN_SIDA.match(r):
                tabell.append(_Rad(int(m[1]), m[2], None, sida_vantas=True))
            elif _ORDFORANDE.match(r):
                # Namnet före "ordförande" hör inte till rubriken.
                if sista and forra and sista.rubrik and sista.rubrik.endswith(f" {forra}"):
                    sista.rubrik = sista.rubrik[: -len(forra) - 1]
                break
            elif sista:
                sista.rubrik, forra = f"{sista.rubrik} {r}", r
            continue
        if m := _RAD_HEL.match(r):
            tabell.append(_Rad(int(m[1]), m[2], int(m[3])))
        elif m := _RAD_UTAN_RUBRIK.match(r):
            tabell.append(_Rad(int(m[1]), None, int(m[2])))
        elif _TAL.match(r):
            if sista and sista.sida_vantas:
                sista.sida, sista.sida_vantas = int(r), False
            else:
                tabell.append(_Rad(int(r), None, None, sida_vantas=True))
        elif m := _RAD_UTAN_SIDA.match(r):
            tabell.append(_Rad(int(m[1]), m[2], None, sida_vantas=True))
        elif _ORDFORANDE.match(r):
            # Namnet före "ordförande" hör inte till tabellen.
            if forra and sista and sista.rubrik and sista.rubrik.endswith(f" {forra}"):
                sista.rubrik = sista.rubrik[: -len(forra) - 1]
            elif losa:
                losa.pop()
            forra = ""
        elif sista and sista.rubrik is not None:
            # En rubrik på flera rader. Sidnumret kan stå sist på den sista ("re 2"), men "2026" är rubrik.
            if sista.sida_vantas and (m := re.match(r"^(.*\D)\s+(\d{1,3})$", r)):
                sista.rubrik, sista.sida, sista.sida_vantas = f"{sista.rubrik} {m[1]}".strip(), int(m[2]), False
            else:
                sista.rubrik, forra = f"{sista.rubrik} {r}", r
        else:
            losa.append(r)
    utan = [t for t in tabell if t.rubrik is None]
    for t, r in zip(utan, losa):
        t.rubrik = r


def _topp(rader: list[str], organ: str) -> tuple[list[str], int | None, int]:
    """Diarienumret och paragrafnumret överst på sidan, och index för raden efter dem."""
    i, dnr, nr = 0, [], None
    if rader and (m := _DNR.fullmatch(rader[0])):
        dnr, i = [diarienummer(organ, *m.groups())], 1
    if i < len(rader) and _TAL.match(rader[i]):
        nr, i = int(rader[i]), i + 1
    return dnr, nr, i


def _paragrafsida(rader: list[str], organ: str) -> tuple[list[str], int | None, str] | None:
    """(diarienummer, paragrafnummer, rubrik) överst på en paragrafsida, eller None."""
    dnr, nr, i = _topp(rader, organ)
    j = i
    while j < len(rader) and j < i + 4 and not _FORSLAG.search(rader[j]):
        j += 1
    if j == i or j >= len(rader) or not _FORSLAG.search(rader[j]):
        return None
    return dnr, nr, " ".join(rader[i:j])


def _tjansteskrivelse(rader: list[str], organ: str) -> tuple[list[str], str] | None:
    """(diarienummer, rubrik) ur en tjänsteskrivelse: "Dnr" i sidhuvudet och rubriken före förslaget."""
    if not any(_TJANSTESKRIVELSE.match(r) for r in rader[:30]):
        return None
    dnr = None
    for n, r in enumerate(rader[:30]):
        if m := _DNR_ETIKETT.match(r):
            text = m[2] or (rader[n + 1] if n + 1 < len(rader) else "")
            if d := _DNR.fullmatch(text.strip()):
                dnr = diarienummer(organ, *d.groups())
                break
    forslag = next((n for n, r in enumerate(rader[:40]) if re.match(r"^förslag till beslut", r, re.I)), None)
    if dnr is None or forslag is None:
        return None
    rubrik = [r for r in rader[max(0, forslag - 3):forslag]
              if not (r.lower() in _HUVUD or _DATUM.match(r) or _DNR.fullmatch(r) or "@" in r
                      or r.endswith(("nämnden", "förvaltningen", "Kommunstyrelsen"))
                      or r.lower().startswith("dnr"))]
    return [dnr], _TJ_PREFIX.sub("", " ".join(rubrik)).strip()


def las(pdf: bytes | str | Path, organ: str) -> Foredragningslista:
    """Föredragningslistan med diarienummer ur en kallelse, kungörelse eller handlingar."""
    from ..arenden import LIKHETSGRANS, likhet

    try:
        reader = PdfReader(io.BytesIO(pdf) if isinstance(pdf, bytes) else pdf)
        antal_sidor = len(reader.pages)
    except Exception as e:  # en trasig PDF ska inte stoppa resten
        return Foredragningslista("fel", fel=(f"PDF:en kunde inte läsas: {type(e).__name__}",))

    fel: list[str] = []

    def text(i: int) -> list[str]:
        try:
            return _rader(reader.pages[i].extract_text() or "")
        except Exception as e:
            fel.append(f"Sidan {i + 1} kunde inte läsas: {type(e).__name__}")
            return []

    def layout(i: int) -> list[str]:
        """Tabellens sidor i layoutläge, som håller ihop raderna (standardläget bryter ibland mitt i ord:
        "Val av justera" / "re 2")."""
        try:
            return _rader(reader.pages[i].extract_text(extraction_mode="layout") or "")
        except Exception:
            return text(i)

    # Tabellen: från rubriken "Paragraf Rubrik Sida" till första paragrafsidan.
    tabell: list[_Rad] = []
    tabellage = "standard"
    langd: int | None = None
    med_sida = True
    i = 0
    while i < min(antal_sidor, 4):
        rader = text(i)
        if langd is None and (m := _SIDA_1.search(" ".join(rader))):
            langd = int(m[1])
        start = _tabellrubrik(rader)
        i += 1
        if start is not None:
            med_sida = start[1]
            _tabell(rader[start[0]:], tabell, med_sida)
            # Layoutläget håller ihop raderna bättre, utom när det tappar rubriker (samhällsnämnden
            # 2026-10-29, rad 135). Då gäller standardläget.
            lrader = layout(i - 1)
            if (lstart := _tabellrubrik(lrader)) is not None:
                ltabell: list[_Rad] = []
                _tabell(lrader[lstart[0]:], ltabell, med_sida)
                if len(ltabell) >= len(tabell) and all(t.rubrik for t in ltabell):
                    tabell = ltabell
                    tabellage = "layout"
            break
    if not tabell:
        return Foredragningslista("saknas")
    rad = _RAD_HEL if med_sida else _RAD_UTAN_SIDA
    while i < antal_sidor:
        rader, huvud = _utan_huvud(text(i))
        if huvud and huvud[0] in {t.sida for t in tabell}:
            break
        if not rader or not (rad.match(rader[0]) or _RAD_UTAN_RUBRIK.match(rader[0])
                             or _ORDFORANDE.match(rader[min(1, len(rader) - 1)])):
            break
        if _paragrafsida(rader, organ) is not None:
            break
        lrader = layout(i) if tabellage == "layout" else rader
        k = next((n for n, r in enumerate(lrader) if rad.match(r) or _RAD_UTAN_RUBRIK.match(r)), None)
        _tabell(lrader[k:] if k is not None else rader, tabell, med_sida)
        i += 1

    per_nr = {t.paragraf: t for t in tabell}
    per_sida: dict[int, _Rad] = {}
    for t in tabell:
        if t.sida is not None:
            per_sida.setdefault(t.sida, t)
    tabellsidor = sorted(s for s in per_sida if langd is None or s <= langd)
    funna_sidor: set[int] = set()
    sist = -1  # index i tabellen för den senast ihopparade paragrafen (på rubriken)
    med_sidhuvud = False
    tjansteskrivelser: list[tuple[int, list[str], str]] = []

    def para_pa_rubrik(rubrik: str, efter: int, villkor) -> _Rad | None:
        kandidater = [(likhet(rubrik, x.rubrik or ""), n) for n, x in enumerate(tabell) if n > efter and villkor(x)]
        kandidater = [k for k in kandidater if k[0] > LIKHETSGRANS]
        if not kandidater:
            return None
        bast = max(k[0] for k in kandidater)
        return tabell[next(n for v, n in kandidater if v == bast)]

    while i < antal_sidor:
        rader, huvud = _utan_huvud(text(i))
        i += 1
        if huvud and langd and huvud[1] == langd:
            # Med sidhuvud: tabellens sida N, eller paragrafnumret på sidan.
            med_sidhuvud = True
            funna_sidor.add(huvud[0])
            dnr, nr, k = _topp(rader, organ)
            p = _paragrafsida(rader, organ)
            rubrik = p[2] if p else (rader[k] if k < len(rader) else None)
            t = per_nr.get(nr) if nr is not None else per_sida.get(huvud[0])
            if t is None and p is not None and dnr:
                t = para_pa_rubrik(rubrik, -1, lambda x: x.pdf_sida is None)
            if t is not None and t.pdf_sida is None:
                t.dnr, t.pdf_sida, t.sidrubrik = dnr, i, rubrik
            if huvud[0] >= langd:
                break
            continue
        if med_sidhuvud and tabellsidor and all(s in funna_sidor for s in tabellsidor):
            break  # bilagorna efter föredragningslistan
        if (tj := _tjansteskrivelse(rader, organ)) is not None:
            tjansteskrivelser.append((i, *tj))
            continue
        if med_sidhuvud:
            continue
        p = _paragrafsida(rader, organ)
        if p is None:
            continue
        dnr, nr, rubrik = p
        if not dnr and nr is None:
            continue  # en sida utan diarienummer och nummer ger inget, och kan vara en bilaga
        if nr is not None and nr in per_nr and per_nr[nr].pdf_sida is None:
            t = per_nr[nr]
        elif (t := para_pa_rubrik(rubrik, sist, lambda x: x.pdf_sida is None)) is None:
            continue
        t.dnr, t.pdf_sida, t.sidrubrik = dnr, i, rubrik
        sist = tabell.index(t)
        if t is tabell[-1]:
            break

    # Bara tjänsteskrivelser: diarienumret för paragrafer vars sida inte hittades, i tabellens ordning.
    kanda = {d for t in tabell for d in t.dnr}
    sist = -1
    for sida, dnr, rubrik in tjansteskrivelser:
        if set(dnr) & kanda:
            continue
        t = para_pa_rubrik(rubrik, sist, lambda x: x.pdf_sida is None and not x.dnr)
        if t is None:
            continue
        t.dnr, t.pdf_sida, t.sidrubrik = dnr, sida, rubrik
        kanda |= set(dnr)
        sist = tabell.index(t)

    saknade = [str(s) for s in tabellsidor if med_sidhuvud and s not in funna_sidor]
    if len(saknade) == 1:
        fel.append(f"Sidan {saknade[0]} i föredragningslistan hittades inte")
    elif saknade:
        fel.append(f"Sidorna {', '.join(saknade)} i föredragningslistan hittades inte")
    punkter = tuple(
        Punkt(t.paragraf, t.sidrubrik or t.rubrik or "", tuple(t.dnr), t.pdf_sida, t.rubrik or "") for t in tabell
    )
    return Foredragningslista("delvis_fel" if fel else "last", punkter, tuple(fel))
