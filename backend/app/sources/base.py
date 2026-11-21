"""Det gemensamma gränssnittet för datakällor.

En ny källa läggs till genom att skriva en klass som uppfyller `Datakalla`. Inget annat
i insamlingen eller API:t behöver ändras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Matt:
    """Ett mått som en källa publicerar, t.ex. ett Kolada-nyckeltal."""

    id: str
    titel: str
    beskrivning: str
    enhet: str
    kallans_publicering: date | None


@dataclass(frozen=True)
class Uppgift:
    """Ett värde för ett mått, ett område och en avsedd period, så som källan anger det."""

    matt_id: str
    omrade: str
    period: str
    varde: Decimal | None
    kallans_publicering: date | None


@dataclass(frozen=True)
class Dokument:
    """Ett dokument som källan publicerar, t.ex. ett protokoll som PDF, med hela innehållet."""

    url: str
    filnamn: str
    typ: str  # 'protokoll'
    organ: str  # t.ex. 'KF'
    innehall: bytes


@dataclass
class Hamtning:
    matt: list[Matt] = field(default_factory=list)
    uppgifter: list[Uppgift] = field(default_factory=list)
    dokument: list[Dokument] = field(default_factory=list)
    # Filer med SKR:s prognosunderlag (skatteunderlag.Prognosfil), som räknas om när de lagras.
    prognosfiler: list = field(default_factory=list)
    # Delar av hämtningen som misslyckades medan resten gick bra. Ger status "delvis fel".
    # Om ingenting gick att hämta ska källan i stället kasta ett undantag.
    fel: list[str] = field(default_factory=list)


class Datakalla(Protocol):
    id: str
    titel: str
    url: str
    # Högsta anropsfrekvens mot källan. None = ingen gräns. Insamlingen håller gränsen.
    anrop_per_sekund: float | None

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        """Hämta det som är nytt eller ändrat sedan `sedan` (allt om `sedan` är None)."""
        ...
