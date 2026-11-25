"""Kommunens styrande dokument (#63): sidan Kommunens styrande dokument på harnosand.se.

Sidan har en rubrik (`h2`) per grupp, till exempel Policy eller Delegationer, med länkar till PDF:er under. Rubriken
blir dokumentets kategori. En fil som står under två rubriker är ett dokument med två kategorier.

Länkarna har formen `/download/18.<id>/<tidsstämpel>/<filnamn>.pdf`. Id:t följer oftast med när kommunen byter ut
filen, och tidsstämpeln ändras. Ibland får filen ett nytt id med samma filnamn. Hur det tolkas avgörs när listan
lagras (`app.styrande_dokument`), inte här.

Bara filer som inte redan är hämtade laddas ner (`kanda_filer`, som insamlingen fyller i).
"""

from __future__ import annotations

import html
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote, urljoin

import httpx

from .base import Hamtning
from .harnosand import BAS

SIDA = urljoin(BAS, "/kommun--styrning/forvaltning-och-organisation/kommunens-styrande-dokument.html")

_DEL = re.compile(r'<h2\b[^>]*>(.*?)</h2>|<a\b[^>]*href="(/download/(18\.[0-9a-f]+)/(\d+)/[^"]+?\.pdf)"',
                  re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Lank:
    url: str
    sitevision_id: str  # '18.<id>'
    tidsstampel: int  # millisekunder, ur länken
    filnamn: str
    kategorier: tuple[str, ...]

    @property
    def titel(self) -> str:
        return re.sub(r"\.pdf$", "", self.filnamn, flags=re.IGNORECASE).strip()


@dataclass
class Dokumentlista:
    """Länkarna på sidan, i sidans ordning, och innehållet i de filer som hämtades nu."""

    lankar: list[Lank]
    kategorier: list[str]  # rubrikerna med länkar, i sidans ordning
    filer: dict[str, bytes] = field(default_factory=dict)
    ej_hamtade: set[str] = field(default_factory=set)  # filer som inte gick att hämta
    # Bara de första så många länkarna per rubrik (för inspelningar och test). None: alla.
    urval: int | None = None


def _text(s: str) -> str:
    return unicodedata.normalize("NFC", " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").split()))


def lankar_pa_sidan(sida: str, urval: int | None = None) -> tuple[list[Lank], list[str]]:
    """Länkarna till PDF:er, med rubrikerna de står under, och rubrikerna i sidans ordning.

    Samma fil (samma adress) under flera rubriker blir en länk med flera kategorier. `urval` tar bara med de
    första så många länkarna under varje rubrik.
    """
    per_url: dict[str, dict] = {}
    rubrik: str | None = None
    antal: dict[str, int] = {}
    ordning: list[str] = []
    for m in _DEL.finditer(sida):
        if m[1] is not None:
            rubrik = _text(m[1])
            continue
        if rubrik is None:
            continue
        if urval is not None and antal.get(rubrik, 0) >= urval:
            continue
        antal[rubrik] = antal.get(rubrik, 0) + 1
        if rubrik not in ordning:
            ordning.append(rubrik)
        href = html.unescape(m[2])
        url = urljoin(BAS, href)
        post = per_url.setdefault(url, {
            "url": url, "sitevision_id": m[3], "tidsstampel": int(m[4]),
            "filnamn": unicodedata.normalize("NFC", unquote(href.rsplit("/", 1)[-1])).strip(), "kategorier": [],
        })
        if rubrik not in post["kategorier"]:
            post["kategorier"].append(rubrik)
    return [Lank(**{**p, "kategorier": tuple(p["kategorier"])}) for p in per_url.values()], ordning


class StyrandeDokument:
    """Datakällan "Kommunens styrande dokument"."""

    id = "harnosand-styrande-dokument"
    titel = "Härnösands kommun – kommunens styrande dokument"
    url = SIDA

    def __init__(self, urval: int | None = None, anrop_per_sekund: float | None = 1.0) -> None:
        self.urval = urval or None
        self.anrop_per_sekund = anrop_per_sekund
        # Adresser (med tidsstämpel) som redan är hämtade. Fylls i av insamlingen.
        self.kanda_filer: set[str] = set()

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        svar = client.get(self.url)
        svar.raise_for_status()
        lankar, kategorier = lankar_pa_sidan(svar.text, self.urval)
        if not lankar:
            # En sida utan länkar är troligen en ändrad sida, inte en tom lista. Inget får märkas borttaget.
            raise ValueError("Sidan innehåller inga länkar till styrande dokument")
        lista = Dokumentlista(lankar=lankar, kategorier=kategorier, urval=self.urval)
        resultat = Hamtning(styrande_dokument=[lista])
        for lank in lankar:
            if lank.url in self.kanda_filer:
                continue
            try:
                pdf = client.get(lank.url)
                pdf.raise_for_status()
                lista.filer[lank.url] = pdf.content
            except httpx.HTTPError as e:
                lista.ej_hamtade.add(lank.url)
                resultat.fel.append(f"{lank.filnamn}: {type(e).__name__}: {e}")
        if lista.ej_hamtade and not lista.filer and len(lista.ej_hamtade) == len(lankar):
            raise httpx.HTTPError(f"Inget av {len(lankar)} styrande dokument kunde hämtas")
        return resultat


def urval_fran_miljo() -> int | None:
    """STYRANDE_URVAL: högst så många dokument per rubrik (för inspelningar och test). 0 eller tomt: alla."""
    return int(os.environ.get("STYRANDE_URVAL") or 0) or None
