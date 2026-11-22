"""SKR:s skatteunderlagsprognoser (skr.se): prognosunderlaget för kommuner, en fil per cirkulär (#61).

Sidan listar under "Aktuellt prognosunderlag för kommuner och regioner" en fil per cirkulär, till
exempel "Prognosunderlag kommuner K 2026–2033 till cirkulär 26:28 (xlsx)". Länktexten kan säga
"(xlsx)" fast filen är `.xlsm`. Bara kommunernas filer läses, inte regionernas eller
uppdateringsfilerna till modellen "Skatter och bidrag". Filerna räknas om när de lagras
(`skatteunderlag.lagra`), där det går att se om filen redan är sparad.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin

import httpx

from ..skatteunderlag import Prognosfil
from .base import Hamtning

SIDA = "https://skr.se/ekonomiochbudgetplanering/skatteunderlagsprognoser.8271.html"
_CIRKULAR = re.compile(r"cirkulär\s+(\d{2}:\d{1,3})", re.IGNORECASE)


class _Lankar(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lankar: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.lankar.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def prognoslankar(html: str, bas: str = SIDA) -> list[tuple[str, str, str]]:
    """(cirkulär, url, filnamn) för kommunernas prognosunderlag på sidan, i sidans ordning."""
    p = _Lankar()
    p.feed(html)
    ut, sedda = [], set()
    for href, text in p.lankar:
        m = _CIRKULAR.search(text)
        if not href or not m or not text.lower().startswith("prognosunderlag kommuner"):
            continue
        url = urljoin(bas, href)
        if url in sedda:
            continue
        sedda.add(url)
        cirk = m.group(1)
        ut.append((cirk, url, unquote(url.rsplit("/", 1)[-1])))
    return ut


class SkrSkatteunderlag:
    id = "skr-skatteunderlagsprognos"
    titel = "SKR skatteunderlagsprognos"
    url = SIDA

    def __init__(self, anrop_per_sekund: float | None = 1.0) -> None:
        self.anrop_per_sekund = anrop_per_sekund

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        svar = client.get(self.url)
        svar.raise_for_status()
        lankar = prognoslankar(svar.text, str(svar.url))
        if not lankar:
            raise ValueError("Sidan har inga länkar till prognosunderlag för kommuner")
        resultat = Hamtning()
        for cirkular, url, filnamn in lankar:
            try:
                fil = client.get(url)
                fil.raise_for_status()
            except httpx.HTTPError as e:
                resultat.fel.append(f"{filnamn} (cirkulär {cirkular}): {type(e).__name__}: {e}")
                continue
            resultat.prognosfiler.append(Prognosfil(cirkular, url, filnamn, fil.content))
        if len(resultat.fel) == len(lankar):
            raise httpx.HTTPError("Ingen prognosfil gick att hämta: " + "; ".join(resultat.fel))
        return resultat
