"""Spelar in svar från de riktiga källorna till en inspelningskatalog (för tester och lokal utveckling).

    uv run python -m app.spela_in tests/recordings

Kör alla standardkällor en gång mot nätet och sparar varje svar. Befintliga inspelningar
för samma adress skrivs över, övriga lämnas kvar.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

from .main import standardkallor


class InspelandeTransport(httpx.BaseTransport):
    def __init__(self, katalog: Path) -> None:
        self.katalog = katalog
        self.ny_manifest: dict[str, str] = {}
        self.riktig = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        svar = self.riktig.handle_request(request)
        innehall = svar.read()
        nyckel = f"{request.url.host}{request.url.path}"
        if svar.status_code == 200:
            delar = [d for d in request.url.path.split("/") if d]
            fil = f"{request.url.host.split('.')[-2]}/{re.sub(r'[^A-Za-z0-9]+', '_', '_'.join(delar[-4:]))}.json"
            (self.katalog / fil).parent.mkdir(parents=True, exist_ok=True)
            (self.katalog / fil).write_bytes(innehall)
            self.ny_manifest[nyckel] = fil
        return httpx.Response(svar.status_code, headers=svar.headers, content=innehall, request=request)


def main() -> None:
    katalog = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/recordings")
    manifestfil = katalog / "manifest.json"
    manifest = json.loads(manifestfil.read_text(encoding="utf-8")) if manifestfil.exists() else {}
    transport = InspelandeTransport(katalog)
    with httpx.Client(transport=transport, timeout=60.0, headers={"User-Agent": "kommunkollen/0.1"}) as client:
        for kalla in standardkallor():
            h = kalla.hamta(client, None)
            print(f"{kalla.id}: {len(h.matt)} mått, {len(h.uppgifter)} uppgifter, fel: {h.fel or 'inga'}")
    manifest.update(transport.ny_manifest)
    manifestfil.write_text(json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(transport.ny_manifest)} svar inspelade i {katalog}")


if __name__ == "__main__":
    main()
