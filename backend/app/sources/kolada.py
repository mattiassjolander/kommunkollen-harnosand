"""Kolada (api.kolada.se, v3): kommunala nyckeltal."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

import httpx

from .base import Hamtning, Matt, Uppgift

BAS = "https://api.kolada.se/v3"
# Koladas kommun-id för riket: genomsnittet för alla kommuner.
RIKET = "0000"
# Hur många nyckeltal som hämtas i samma anrop för de samlade nyckeltalen.
PER_ANROP = 25


def _datum(s: str | None) -> date | None:
    # Kolada anger ibland nästa planerade publicering. Ett framtida datum är ingen publicering än.
    d = date.fromisoformat(s) if s else None
    return d if d and d <= date.today() else None


def _enhet(titel: str) -> str:
    # Insikts nyckeltal är index, t.ex. "Företagsklimat Insikt - Totalt, Index, ny definition".
    if re.search(r"\bindex\b", titel, re.IGNORECASE):
        return "index"
    # Kolada skriver enheten sist i titeln, t.ex. "Årets resultat kommun, kr/inv".
    if titel.endswith(")") and "(" in titel:
        return titel[titel.rindex("(") + 1 : -1]
    if "," in titel:
        return titel.rsplit(",", 1)[-1].strip()
    # T.ex. "Medborgarundersökningen - Antal svar".
    return "antal" if titel.rsplit(" - ", 1)[-1].lower().startswith("antal") else ""


class Kolada:
    id = "kolada"
    titel = "Kolada"
    url = "https://www.kolada.se"

    def __init__(
        self,
        nyckeltal: list[str],
        kommun: str = "2280",
        anrop_per_sekund: float | None = 5.0,
        riket: list[str] | None = None,
        samlade: list[str] | None = None,
    ) -> None:
        self.anrop_per_sekund = anrop_per_sekund
        self.nyckeltal = nyckeltal
        self.kommun = kommun
        # Nyckeltal som också hämtas för riket (kommun-id 0000), som jämförelse (#82).
        self.riket = riket or []
        # Nyckeltal som hämtas flera åt gången, för kommunen och riket i samma anrop (#67). Används för
        # undersökningarna, som är många.
        self.samlade = samlade or []
        self._publicerad: dict[str, date | None] = {}

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
        # Riket hämtas i samma insamling. Ett fel redovisas per nyckeltal som för kommunen.
        for kpi_id in self.riket:
            try:
                self._hamta_varden(client, kpi_id, RIKET, resultat)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                senaste_fel = e
                resultat.fel.append(f"{kpi_id} (riket): {type(e).__name__}: {e}")
        paket = [self.samlade[i : i + PER_ANROP] for i in range(0, len(self.samlade), PER_ANROP)]
        for ids in paket:
            try:
                self._hamta_samlade(client, ids, resultat)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                senaste_fel = e
                resultat.fel.append(f"{ids[0]}–{ids[-1]}: {type(e).__name__}: {e}")
        if senaste_fel is not None and len(resultat.fel) == len(self.nyckeltal) + len(self.riket) + len(paket):
            raise senaste_fel
        return resultat

    def _matt(self, kpi: dict) -> Matt:
        publicerad = _datum(kpi.get("publication_date"))
        self._publicerad[kpi["id"]] = publicerad
        return Matt(
            id=f"kolada:{kpi['id']}",
            titel=kpi["title"],
            beskrivning=kpi.get("description") or "",
            enhet=_enhet(kpi["title"]),
            kallans_publicering=publicerad,
        )

    def _hamta_samlade(self, client: httpx.Client, ids: list[str], resultat: Hamtning) -> None:
        """Flera nyckeltal i ett anrop, för kommunen och riket. Kolada tar kommaseparerade id."""
        kpier = {k["id"]: k for k in self._hamta_alla(client, f"{BAS}/kpi/{','.join(ids)}")}
        saknas = [i for i in ids if i not in kpier]
        if saknas:
            raise KeyError(f"Kolada saknar {', '.join(saknas)}")
        matt = [self._matt(kpier[i]) for i in ids]
        kommuner = ",".join(dict.fromkeys([self.kommun, RIKET]))
        rader = self._hamta_alla(client, f"{BAS}/data/kpi/{','.join(ids)}/municipality/{kommuner}")
        resultat.matt.extend(matt)
        resultat.uppgifter.extend(self._uppgifter(rader))

    def _hamta_nyckeltal(self, client: httpx.Client, kpi_id: str, sedan: datetime | None, resultat: Hamtning) -> None:
        kpi = self._hamta_alla(client, f"{BAS}/kpi/{kpi_id}")[0]
        resultat.matt.append(self._matt(kpi | {"id": kpi_id}))
        self._hamta_varden(client, kpi_id, self.kommun, resultat)

    def _hamta_varden(self, client: httpx.Client, kpi_id: str, kommun: str, resultat: Hamtning) -> None:
        # Hela serien hämtas varje gång (den är liten). Med from_date skulle ett nyckeltal som lagts
        # till i katalogen efter källans senaste kontroll bara få de senast ändrade åren.
        # Insamlingen lagrar ändå bara det som är nytt eller ändrat.
        rader = self._hamta_alla(client, f"{BAS}/data/kpi/{kpi_id}/municipality/{kommun}")
        resultat.uppgifter.extend(self._uppgifter(rader, kpi_id))

    def _uppgifter(self, rader: list[dict], kpi_id: str | None = None) -> list[Uppgift]:
        """Värdena för båda könen sammantaget. Raderna anger nyckeltalet när flera hämtas samtidigt."""
        ut = []
        for rad in rader:
            kpi = rad.get("kpi") or kpi_id
            for v in rad["values"]:
                if v.get("gender") != "T" or v.get("isdeleted"):
                    continue
                ut.append(
                    Uppgift(
                        matt_id=f"kolada:{kpi}",
                        omrade=rad["municipality"],
                        period=str(rad["period"]),
                        varde=None if v["value"] is None else Decimal(str(v["value"])),
                        kallans_publicering=self._publicerad.get(kpi),
                    )
                )
        return ut
