"""Kolada (api.kolada.se, v3): kommunala nyckeltal."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx

from .base import Hamtning, Matt, Uppgift

BAS = "https://api.kolada.se/v3"


def _datum(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _enhet(titel: str) -> str:
    # Kolada skriver enheten sist i titeln, t.ex. "Årets resultat kommun, kr/inv".
    if titel.endswith(")") and "(" in titel:
        return titel[titel.rindex("(") + 1 : -1]
    return titel.rsplit(",", 1)[-1].strip() if "," in titel else ""


class Kolada:
    id = "kolada"
    titel = "Kolada"
    url = "https://www.kolada.se"

    def __init__(self, nyckeltal: list[str], kommun: str = "2280") -> None:
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
        for kpi_id in self.nyckeltal:
            kpi = self._hamta_alla(client, f"{BAS}/kpi/{kpi_id}")[0]
            publicerad = _datum(kpi.get("publication_date"))
            matt_id = f"kolada:{kpi_id}"
            resultat.matt.append(
                Matt(
                    id=matt_id,
                    titel=kpi["title"],
                    beskrivning=kpi.get("description") or "",
                    enhet=_enhet(kpi["title"]),
                    kallans_publicering=publicerad,
                )
            )
            params = {"from_date": sedan.date().isoformat()} if sedan else None
            for rad in self._hamta_alla(
                client, f"{BAS}/data/kpi/{kpi_id}/municipality/{self.kommun}", params
            ):
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
        return resultat
