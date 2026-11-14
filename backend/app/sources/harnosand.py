"""Härnösands kommun (harnosand.se): protokoll från de beslutande organen.

Organens sidor listar innevarande års protokoll som PDF-länkar. Varje protokoll hämtas i sin
helhet. Tolkningen görs när protokollet lagras (se `app.protokoll`), inte här.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urljoin

import httpx

from .base import Dokument, Hamtning

BAS = "https://harnosand.se"


@dataclass(frozen=True)
class Organ:
    id: str
    namn: str
    sida: str  # sökväg på harnosand.se


ORGAN = {
    "KF": Organ("KF", "Kommunfullmäktige", "/kommun--styrning/politik-och-demokrati/kommunfullmaktige.html"),
}

_LANK = re.compile(r'href="(/download/[^"]+\.pdf)"', re.IGNORECASE)


def ar_protokoll(filnamn: str) -> bool:
    return "protokoll" in filnamn.lower()


def ar_paragrafprotokoll(filnamn: str) -> bool:
    """Protokoll för enstaka paragrafer (direktjustering, protokollsutdrag). De hanteras i en senare skiva."""
    return "§" in filnamn or "utdrag" in filnamn.lower() or "direktjuster" in filnamn.lower()


def protokollankar(sida: str) -> list[tuple[str, str]]:
    """(url, filnamn) för organsidans protokoll, i sidans ordning och utan dubbletter."""
    sett: dict[str, str] = {}
    for href in _LANK.findall(sida):
        href = html.unescape(href)
        filnamn = unquote(href.rsplit("/", 1)[-1])
        if ar_protokoll(filnamn) and not ar_paragrafprotokoll(filnamn):
            sett.setdefault(urljoin(BAS, href), filnamn)
    return list(sett.items())


class Protokollkalla:
    """Protokoll från ett organ. En instans per organ, så att varje organ har en egen kontroll."""

    def __init__(self, organ: str, anrop_per_sekund: float | None = 2.0) -> None:
        self.organ = ORGAN[organ]
        self.id = f"harnosand-protokoll-{organ.lower()}"
        self.titel = f"Härnösands kommun – protokoll, {self.organ.namn.lower()}"
        self.url = urljoin(BAS, self.organ.sida)
        self.anrop_per_sekund = anrop_per_sekund

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        # Alla listade protokoll hämtas varje gång: kommunen kan byta innehållet i en fil.
        svar = client.get(self.url)
        svar.raise_for_status()
        resultat = Hamtning()
        for url, filnamn in protokollankar(svar.text):
            try:
                pdf = client.get(url)
                pdf.raise_for_status()
                resultat.dokument.append(Dokument(url=url, filnamn=filnamn, typ="protokoll", organ=self.organ.id,
                                                  innehall=pdf.content))
            except httpx.HTTPError as e:
                resultat.fel.append(f"{filnamn}: {type(e).__name__}: {e}")
        return resultat
