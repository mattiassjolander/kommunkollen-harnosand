"""Kallelser och webbsändningar på harnosand.se (#68, del 3).

Kallelser: organens sidor länkar kallelser (för fullmäktige kungörelser) och handlingar som PDF, med datum,
ibland klockslag, och filstorlek i länktexten. Kallelsen kopplas till sammanträdet med samma organ och datum.
Platsen läses ur kallelsens första sida ("… kallas härmed till sammanträde 2026-10-26 kl. 11:00 - i Rådhuset -
KF-salen."), men bara ur små filer: kallelser med handlingar kan vara flera hundra MB.

Föredragningslistan läses ur nya kallelser, kungörelser och handlingar, för diarienumren (#109, se
`foredragningslista`). Filen hämtas till en tillfällig fil, eftersom handlingarna kan vara mycket stora.

Webbsändningar: sidan för webb-tv listar en länk per sammanträde i fullmäktige ("Sammanträde 2026-10-26"),
till qcnl.tv från 2026 och play.quickchannel.com för 2024–2025. Ingen livelänk är känd i förväg.
"""

from __future__ import annotations

import html
import io
import os
import re
from dataclasses import dataclass, replace
from datetime import date
from urllib.parse import unquote, urljoin

from pypdf import PdfReader

from .foredragningslista import Foredragningslista
from .harnosand import BAS, POLITIK

WEBB_TV = urljoin(BAS, f"{POLITIK}/kommunfullmaktige/webb-tv.html")
# Kallelser större än så hämtas inte för att läsa platsen.
MAX_STORLEK_FOR_PLATS = 2_000_000


def max_storlek_for_lista() -> int:
    """Kallelser större än så hämtas inte för att läsa föredragningslistan (kommunstyrelsens största
    handlingar 2026 var 316 MB)."""
    return int(os.environ.get("KALLELSE_MAX_STORLEK_FOR_LISTA", 600_000_000))


@dataclass(frozen=True)
class Kallelse:
    organ: str
    datum: date
    tid: str | None  # "HH:MM" ur filnamnet eller kallelsen
    typ: str  # 'kungorelse' | 'kallelse' | 'handlingar'
    titel: str
    url: str
    storlek: int | None  # byte, enligt sidan
    plats: str | None = None
    pdf_last: bool = False  # kallelsen är hämtad och läst (oavsett om platsen stod där)
    foredragningslista: Foredragningslista | None = None  # None: inte läst


@dataclass(frozen=True)
class Webbsandning:
    organ: str
    datum: date
    url: str
    titel: str


_LANK = re.compile(r'<a\b[^>]*href="(/download/[^"]+\.pdf)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_DATUM_TID = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:,?\s*(?:kl\.?\s*)?(\d{1,2})[ .:](\d{2})(?!\d))?")
_STORLEK = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kB|MB|GB|B)\b", re.IGNORECASE)
_ANNAT_ORGAN = re.compile(r"utskott|beredning", re.IGNORECASE)
_KALLAS = re.compile(
    r"kallas\s+härmed\s+till\s+sammanträde\s+(\d{4}-\d{2}-\d{2})\s+kl\.?\s*(\d{1,2})[.:](\d{2})\s*-?\s*i\s+(.+?)\.(?:\s|$)",
    re.IGNORECASE | re.DOTALL,
)
_WEBBSANDNING = re.compile(
    r'<a\b[^>]*href="(https://(?:qcnl\.tv|play\.quickchannel\.com)/[^"]+)"[^>]*>\s*([^<]*?(\d{4}-\d{2}-\d{2})[^<]*?)\s*<',
    re.IGNORECASE,
)


def _text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").split())


def _storlek(text: str) -> int | None:
    m = _STORLEK.search(text)
    if not m:
        return None
    faktor = {"b": 1, "kb": 1_000, "mb": 1_000_000, "gb": 1_000_000_000}[m[2].lower()]
    return int(float(m[1].replace(",", ".")) * faktor)


def typ(namn: str) -> str | None:
    n = namn.lower()
    if _ANNAT_ORGAN.search(n):
        return None
    if n.startswith("kungörelse"):
        return "kungorelse"
    if "kallelse" in n:
        return "kallelse"
    if n.startswith("handlingar"):
        return "handlingar"
    return None


def kallelser_pa_sidan(organ: str, sida: str) -> list[Kallelse]:
    """Kallelser, kungörelser och handlingar som organets sida länkar till, utan dubbletter."""
    ut: dict[str, Kallelse] = {}
    for href, innehall in _LANK.findall(sida):
        filnamn = unquote(html.unescape(href).rsplit("/", 1)[-1])
        t = typ(filnamn)
        m = _DATUM_TID.search(filnamn)
        if t is None or m is None:
            continue
        try:
            d = date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
        tid = f"{int(m[4]):02d}:{m[5]}" if m[4] else None
        url = urljoin(BAS, html.unescape(href))
        titel = re.sub(r"(\.pdf)+$", "", filnamn, flags=re.IGNORECASE)
        ut.setdefault(url, Kallelse(organ, d, tid, t, titel, url, _storlek(_text(innehall))))
    return list(ut.values())


def las_kallelse(k: Kallelse, pdf: bytes) -> Kallelse:
    """Platsen och klockslaget ur kallelsens första sida, om de står där."""
    try:
        text = " ".join((PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or "").split())
    except Exception:  # en trasig PDF ska inte stoppa resten
        return replace(k, pdf_last=True)
    m = _KALLAS.search(text)
    if not m or m[1] != k.datum.isoformat():
        return replace(k, pdf_last=True)
    # Ett avstavat ord vid radbrytning, t.ex. "KF- salen", sätts ihop. "Rådhuset - KF" har mellanslag före.
    plats = re.sub(r"(\w)-\s+(?=\w)", r"\1-", m[4]).strip()
    return replace(k, tid=k.tid or f"{int(m[2]):02d}:{m[3]}", plats=plats, pdf_last=True)


def webbsandningar(sida: str) -> list[Webbsandning]:
    ut: dict[str, Webbsandning] = {}
    for url, titel, iso in _WEBBSANDNING.findall(sida):
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        ut.setdefault(html.unescape(url), Webbsandning("KF", d, html.unescape(url), _text(titel)))
    return list(ut.values())
