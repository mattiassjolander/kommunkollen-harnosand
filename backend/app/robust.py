"""Robusta anrop mot externa källor: timeout, omförsök med fördröjning och anropsgräns.

Insamlingsmotorn ger varje datakälla en egen klient som går via `RobustTransport`.
Tillfälliga fel (nätverksfel, timeout, 429 och 5xx) försöks igen med växande fördröjning.
Mellan två anrop från samma källa går minst 1/`anrop_per_sekund` sekunder.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

TILLFALLIGA_STATUSKODER = {429, 500, 502, 503, 504}


@dataclass
class Robusthet:
    forsok: int = 3  # totalt antal försök per anrop
    fordrojning: float = 2.0  # sekunder före första omförsöket, fördubblas sedan
    timeout: float = 30.0
    sov: Callable[[float], None] = field(default=time.sleep, repr=False)
    klocka: Callable[[], float] = field(default=time.monotonic, repr=False)


class _Via(httpx.BaseTransport):
    """Skickar vidare genom en befintlig klient (och därmed dess transport)."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.client.send(request)


class RobustTransport(httpx.BaseTransport):
    def __init__(self, inre: httpx.BaseTransport, robusthet: Robusthet, anrop_per_sekund: float | None = None) -> None:
        self.inre = inre
        self.r = robusthet
        self.intervall = 1 / anrop_per_sekund if anrop_per_sekund else 0.0
        self._senast: float | None = None
        self.omforsok = 0  # antal omförsök som gjorts, för loggning

    def _vanta_pa_tur(self) -> None:
        if self.intervall and self._senast is not None:
            kvar = self._senast + self.intervall - self.r.klocka()
            if kvar > 0:
                self.r.sov(kvar)
        self._senast = self.r.klocka()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for forsok in range(1, self.r.forsok + 1):
            self._vanta_pa_tur()
            sista = forsok == self.r.forsok
            try:
                svar = self.inre.handle_request(request)
            except (httpx.TransportError, httpx.TimeoutException):
                if sista:
                    raise
            else:
                if svar.status_code not in TILLFALLIGA_STATUSKODER or sista:
                    return svar
                svar.close()
            self.omforsok += 1
            self.r.sov(self.r.fordrojning * 2 ** (forsok - 1))
        raise AssertionError("oåtkomligt")


def kallklient(client: httpx.Client, robusthet: Robusthet, anrop_per_sekund: float | None) -> httpx.Client:
    """En klient för en datakälla: går via `client` men med timeout, omförsök och anropsgräns."""
    transport = RobustTransport(_Via(client), robusthet, anrop_per_sekund)
    return httpx.Client(transport=transport, timeout=robusthet.timeout, headers=client.headers)
