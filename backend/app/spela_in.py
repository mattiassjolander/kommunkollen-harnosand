"""Spelar in svar från de riktiga källorna till en inspelningskatalog (för tester och lokal utveckling).

    uv run python -m app.spela_in tests/recordings [källa ...]

Kör standardkällorna (alla, eller bara de angivna, t.ex. harnosand-protokoll-kf) en gång mot
nätet och sparar varje svar. Befintliga inspelningar
för samma adress skrivs över, övriga lämnas kvar.
"""

from __future__ import annotations

import argparse
import json
import re
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
            # Filändelsen behålls för annat än JSON (HTML-sidor, PDF:er), så att svarets typ går att återskapa.
            andelse = Path(delar[-1]).suffix.lower() if delar else ""
            if andelse not in (".pdf", ".html"):
                andelse = ".json"
            stam = "_".join(delar[-4:])
            if stam.lower().endswith(andelse):
                stam = stam[: -len(andelse)]
            fraga = request.url.query.decode()
            if fraga and andelse == ".html":
                # Samma sida med olika frågesträng (Sitevisions arkivmappar) är olika svar.
                nyckel = f"{nyckel}?{fraga}"
                stam = f"{stam}_{fraga}"
            fil = f"{request.url.host.split('.')[-2]}/{re.sub(r'[^A-Za-z0-9]+', '_', stam)}{andelse}"
            (self.katalog / fil).parent.mkdir(parents=True, exist_ok=True)
            (self.katalog / fil).write_bytes(innehall)
            self.ny_manifest[nyckel] = fil
        # Innehållet är redan avkodat, så kodningshuvudena (t.ex. gzip) får inte följa med.
        huvuden = {k: v for k, v in svar.headers.items() if k.lower() not in ("content-encoding", "content-length")}
        return httpx.Response(svar.status_code, headers=huvuden, content=innehall, request=request)


def main() -> None:
    p = argparse.ArgumentParser(description="Spelar in svar från de riktiga källorna till testerna.")
    p.add_argument("katalog", type=Path, nargs="?", default=Path("tests/recordings"))
    p.add_argument("kallor", nargs="*", metavar="kalla", help="källans id, t.ex. harnosand-protokoll-kf (standard: alla)")
    a = p.parse_args()
    katalog: Path = a.katalog
    manifestfil = katalog / "manifest.json"
    manifest = json.loads(manifestfil.read_text(encoding="utf-8")) if manifestfil.exists() else {}
    transport = InspelandeTransport(katalog)
    with httpx.Client(transport=transport, timeout=60.0, headers={"User-Agent": "kommunkollen/0.1"}) as client:
        valda = set(a.kallor)
        for kalla in standardkallor():
            if valda and kalla.id not in valda:
                continue
            h = kalla.hamta(client, None)
            print(f"{kalla.id}: {len(h.matt)} mått, {len(h.uppgifter)} uppgifter, {len(h.dokument)} dokument, "
                  f"fel: {h.fel or 'inga'}")
    manifest.update(transport.ny_manifest)
    manifestfil.write_text(json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(transport.ny_manifest)} svar inspelade i {katalog}")


if __name__ == "__main__":
    main()
