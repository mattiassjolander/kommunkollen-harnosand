"""Inspelade svar från externa källor, för tester och lokal utveckling utan nätverk.

En inspelningskatalog innehåller `manifest.json`, som mappar "värd/sökväg" till en fil
med svarets innehåll, t.ex. {"api.kolada.se/v3/kpi/N03007": "kolada/kpi_N03007.json"}.
Querysträngen ignoreras. En förfrågan som saknas i manifestet ger ett fel, så att ett
test aldrig av misstag går mot nätet.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx


class InspeladTransport(httpx.BaseTransport):
    def __init__(self, katalog: Path) -> None:
        self.katalog = Path(katalog)
        self.manifest: dict[str, str] = json.loads(
            (self.katalog / "manifest.json").read_text(encoding="utf-8")
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        nyckel = f"{request.url.host}{request.url.path}"
        fil = self.manifest.get(nyckel)
        if fil is None:
            raise httpx.ConnectError(f"Ingen inspelning för {nyckel}", request=request)
        innehall = (self.katalog / fil).read_bytes()
        return httpx.Response(
            200, content=innehall, headers={"content-type": "application/json"}, request=request
        )
