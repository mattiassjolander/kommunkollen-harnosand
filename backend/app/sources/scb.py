"""SCB:s statistikdatabas (PxWeb API v1): räkenskapssammandraget för kommuner.

Tabellerna redovisar kommunens resultat- och balansräkning i tkr, löpande priser, från 1998.
Hela tidsserien hämtas vid varje kontroll (den är liten), och insamlingen avgör vad som är nytt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx

from .base import Hamtning, Matt, Uppgift

BAS = "https://api.scb.se/OV0104/v1/doris/sv/ssd/OE/OE0107/OE0107A"

# Kolumnen för posten i respektive tabell.
POSTVARIABEL = {
    "ResultKnN": "Resultatraknposter",
    "BalansKnN": "Balansraknposter",
    "SkatteIntKnN": "Kontopost",
}


@dataclass(frozen=True)
class ScbMatt:
    tabell: str
    post: str
    titel: str
    beskrivning: str
    enhet: str = "tkr"

    @property
    def id(self) -> str:
        return f"scb:{self.tabell}:{self.post}"


@dataclass(frozen=True)
class Differens:
    """Ett mått som beräknas som skillnaden mellan två SCB-poster, t.ex. rörelsekapital."""

    id: str
    titel: str
    beskrivning: str
    plus: str  # mått-id
    minus: str  # mått-id
    enhet: str = "tkr"


def _varde(s: str) -> Decimal | None:
    # SCB: ".." = uppgift saknas, "." = uppgift kan inte förekomma. Tomt är också saknat.
    s = s.strip()
    if s == "-":  # "-" betyder att inget finns att redovisa, alltså noll
        return Decimal(0)
    if s in ("", ".", "..", "..."):
        return None
    return Decimal(s)


class Scb:
    id = "scb"
    titel = "SCB"
    url = "https://www.statistikdatabasen.scb.se"

    def __init__(self, matt: list[ScbMatt], differenser: list[Differens] | None = None, kommun: str = "2280",
                 anrop_per_sekund: float | None = 2.0) -> None:
        # SCB tillåter högst 30 anrop per 10 sekunder och IP-adress.
        self.anrop_per_sekund = anrop_per_sekund
        self.matt = matt
        self.differenser = differenser or []
        self.kommun = kommun

    def _hamta_tabell(self, client: httpx.Client, tabell: str, poster: list[str]) -> tuple[date | None, dict]:
        fraga = {
            "query": [
                {"code": "Region", "selection": {"filter": "item", "values": [self.kommun]}},
                {"code": POSTVARIABEL[tabell], "selection": {"filter": "item", "values": poster}},
            ],
            "response": {"format": "json"},
        }
        svar = client.post(f"{BAS}/{tabell}", json=fraga)
        svar.raise_for_status()
        data = svar.json()
        uppdaterad = (data.get("metadata") or [{}])[0].get("updated")
        publicerad = datetime.fromisoformat(uppdaterad.replace("Z", "+00:00")).date() if uppdaterad else None
        varden = {(rad["key"][1], rad["key"][2]): _varde(rad["values"][0]) for rad in data["data"]}
        return publicerad, varden

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        resultat = Hamtning()
        per_tabell: dict[str, list[ScbMatt]] = {}
        for m in self.matt:
            per_tabell.setdefault(m.tabell, []).append(m)

        serier: dict[str, dict[str, Decimal | None]] = {}
        publiceringar: dict[str, date | None] = {}
        senaste_fel: Exception | None = None
        for tabell, matt in per_tabell.items():
            try:
                publicerad, varden = self._hamta_tabell(client, tabell, [m.post for m in matt])
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                senaste_fel = e
                resultat.fel.append(f"{tabell}: {type(e).__name__}: {e}")
                continue
            for m in matt:
                resultat.matt.append(Matt(m.id, m.titel, m.beskrivning, m.enhet, publicerad))
                serie = {period: v for (post, period), v in varden.items() if post == m.post}
                serier[m.id], publiceringar[m.id] = serie, publicerad
                for period, v in sorted(serie.items()):
                    resultat.uppgifter.append(Uppgift(m.id, self.kommun, period, v, publicerad))
        if senaste_fel is not None and len(resultat.fel) == len(per_tabell):
            raise senaste_fel

        for d in self.differenser:
            if d.plus not in serier or d.minus not in serier:
                continue
            publicerad = max(filter(None, [publiceringar[d.plus], publiceringar[d.minus]]), default=None)
            resultat.matt.append(Matt(d.id, d.titel, d.beskrivning, d.enhet, publicerad))
            for period in sorted(serier[d.plus].keys() | serier[d.minus].keys()):
                a, b = serier[d.plus].get(period), serier[d.minus].get(period)
                v = None if a is None or b is None else a - b
                resultat.uppgifter.append(Uppgift(d.id, self.kommun, period, v, publicerad))
        return resultat
