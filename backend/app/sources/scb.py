"""SCB:s statistikdatabas (PxWeb API v1): räkenskapssammandraget för kommuner.

Tabellerna redovisar kommunens resultat- och balansräkning, intäkter per kontopost och
driftredovisningen per verksamhetsområde, i tkr och löpande priser.
Hela tidsserien hämtas vid varje kontroll (den är liten), och insamlingen avgör vad som är nytt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from .base import Hamtning, Matt, Uppgift

API = "https://api.scb.se/OV0104/v1/doris/sv/ssd"
WEBB = "https://www.statistikdatabasen.scb.se/pxweb/sv/ssd"


@dataclass(frozen=True)
class Tabell:
    sokvag: str  # t.ex. "OE/OE0107/OE0107A/ResultKnN"
    postvariabel: str

    @property
    def url(self) -> str:
        """Tabellen i SCB:s statistikdatabas, för läsare som vill se källan."""
        *mappar, namn = self.sokvag.split("/")
        return f"{WEBB}/START__{'__'.join(mappar)}/{namn}/"


TABELLER = {
    "ResultKnN": Tabell("OE/OE0107/OE0107A/ResultKnN", "Resultatraknposter"),
    "BalansKnN": Tabell("OE/OE0107/OE0107A/BalansKnN", "Balansraknposter"),
    "SkatteIntKnN": Tabell("OE/OE0107/OE0107A/SkatteIntKnN", "Kontopost"),
    "VerksInt": Tabell("OE/OE0107/OE0107A/VerksInt", "Kontopost"),
    "Driftredovisning": Tabell("OE/OE0107/OE0107B/Driftredovisning", "Verksomrkom"),
}


@dataclass(frozen=True)
class ScbMatt:
    tabell: str  # nyckel i TABELLER
    post: str
    titel: str
    beskrivning: str
    enhet: str = "tkr"
    innehall: str | None = None  # tabellinnehåll (ContentsCode) när tabellen har flera, t.ex. "000000Z3"

    @property
    def id(self) -> str:
        return f"scb:{self.tabell}:{self.post}" + (f":{self.innehall}" if self.innehall else "")


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
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


class Scb:
    id = "scb"
    titel = "SCB"
    url = "https://www.statistikdatabasen.scb.se"

    def __init__(self, matt: list[ScbMatt], differenser: list[Differens] | None = None, kommun: str = "2280") -> None:
        self.matt = matt
        self.differenser = differenser or []
        self.kommun = kommun

    def _hamta_tabell(
        self, client: httpx.Client, tabell: str, matt: list[ScbMatt]
    ) -> tuple[date | None, dict[tuple[str, str | None, str], Decimal | None]]:
        """Returnerar publiceringsdatum och värden per (post, tabellinnehåll, period)."""
        t = TABELLER[tabell]
        poster = sorted({m.post for m in matt})
        innehall = sorted({m.innehall for m in matt if m.innehall})
        fraga = [
            {"code": "Region", "selection": {"filter": "item", "values": [self.kommun]}},
            {"code": t.postvariabel, "selection": {"filter": "item", "values": poster}},
        ]
        if innehall:
            fraga.append({"code": "ContentsCode", "selection": {"filter": "item", "values": innehall}})
        svar = client.post(f"{API}/{t.sokvag}", json={"query": fraga, "response": {"format": "json"}})
        svar.raise_for_status()
        data = svar.json()
        uppdaterad = (data.get("metadata") or [{}])[0].get("updated")
        publicerad = datetime.fromisoformat(uppdaterad.replace("Z", "+00:00")).date() if uppdaterad else None
        kolumner = [k["code"] for k in data["columns"] if k["type"] == "c"]
        varden = {}
        for rad in data["data"]:
            post, period = rad["key"][1], rad["key"][2]
            for kod, v in zip(kolumner, rad["values"]):
                varden[(post, kod if innehall else None, period)] = _varde(v)
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
                publicerad, varden = self._hamta_tabell(client, tabell, matt)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                senaste_fel = e
                resultat.fel.append(f"{tabell}: {type(e).__name__}: {e}")
                continue
            for m in matt:
                resultat.matt.append(Matt(m.id, m.titel, m.beskrivning, m.enhet, publicerad))
                serie = {
                    period: v for (post, kod, period), v in varden.items() if post == m.post and kod == m.innehall
                }
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
