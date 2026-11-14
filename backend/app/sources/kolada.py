"""Kolada (api.kolada.se, v3): kommunala nyckeltal."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx

from .base import Hamtning, Matt, Uppgift

BAS = "https://api.kolada.se/v3"


def _datum(s: str | None) -> date | None:
    # Kolada anger ibland nästa planerade publicering. Ett framtida datum är ingen publicering än.
    d = date.fromisoformat(s) if s else None
    return d if d and d <= date.today() else None


def _enhet(titel: str) -> str:
    # Kolada skriver enheten sist i titeln, t.ex. "Årets resultat kommun, kr/inv".
    if titel.endswith(")") and "(" in titel:
        return titel[titel.rindex("(") + 1 : -1]
    return titel.rsplit(",", 1)[-1].strip() if "," in titel else ""


class Kolada:
    id = "kolada"
    titel = "Kolada"
    url = "https://www.kolada.se"

    def __init__(self, nyckeltal: list[str], kommun: str = "2280", anrop_per_sekund: float | None = 5.0) -> None:
        self.anrop_per_sekund = anrop_per_sekund
        self.nyckeltal = nyckeltal
        self.kommun = kommun

    def _hamta_alla(self, client: httpx.Client, url: str, params: dict | None = None) -> list[dict]:
        varden: list[dict] = []
        while url:
            svar = client.get(url, params=params)
            svar.raise_for_status()
            data = svar.json()
            varden.extend(data["values"])
            url, params = data.get("next_url"), None
        return varden

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        resultat = Hamtning()
        senaste_fel: Exception | None = None
        for kpi_id in self.nyckeltal:
            try:
                self._hamta_nyckeltal(client, kpi_id, sedan, resultat)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                senaste_fel = e
                resultat.fel.append(f"{kpi_id}: {type(e).__name__}: {e}")
        if senaste_fel is not None and len(resultat.fel) == len(self.nyckeltal):
            raise senaste_fel
        return resultat

    def _hamta_nyckeltal(self, client: httpx.Client, kpi_id: str, sedan: datetime | None, resultat: Hamtning) -> None:
        kpi = self._hamta_alla(client, f"{BAS}/kpi/{kpi_id}")[0]
        publicerad = _datum(kpi.get("publication_date"))
        matt_id = f"kolada:{kpi_id}"
        # Hela serien hämtas varje gång (den är liten). Med from_date skulle ett nyckeltal som lagts
        # till i katalogen efter källans senaste kontroll bara få de senast ändrade åren.
        # Insamlingen lagrar ändå bara det som är nytt eller ändrat.
        rader = self._hamta_alla(client, f"{BAS}/data/kpi/{kpi_id}/municipality/{self.kommun}")
        resultat.matt.append(
            Matt(
                id=matt_id,
                titel=kpi["title"],
                beskrivning=kpi.get("description") or "",
                enhet=_enhet(kpi["title"]),
                kallans_publicering=publicerad,
            )
        )
        for rad in rader:
            for v in rad["values"]:
                if v.get("gender") != "T" or v.get("isdeleted"):
                    continue
                resultat.uppgifter.append(
                    Uppgift(
                        matt_id=matt_id,
                        omrade=rad["municipality"],
                        period=str(rad["period"]),
                        varde=None if v["value"] is None else Decimal(str(v["value"])),
                        kallans_publicering=publicerad,
                    )
                )
