"""Lokal utvecklingsserver.

Startar API:t mot `DATABASE_URL` om den är satt, annars mot en inbäddad Postgres
(pgserver) i `backend/.dev-db`. Med `--inspelningar <katalog>` används inspelade
källsvar i stället för nätet, vilket e2e-testerna använder.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def inbaddad_postgres(katalog: Path) -> str:
    import pgserver  # utvecklingsberoende

    katalog.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(str(katalog), cleanup_mode="stop")
    return server.get_uri()


def main() -> None:
    p = argparse.ArgumentParser(description="Kommunkollen – lokal utvecklingsserver")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--inspelningar", type=Path, help="katalog med inspelade källsvar")
    p.add_argument("--databas", type=Path, default=Path(__file__).resolve().parent.parent / ".dev-db")
    a = p.parse_args()

    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = inbaddad_postgres(a.databas)
    # Testinloggning är på i utveckling om inget annat sagts.
    os.environ.setdefault("TESTENV", "true")
    if a.inspelningar:
        os.environ["INSPELNINGAR"] = str(a.inspelningar.resolve())
        # Inspelade svar behöver ingen anropsgräns.
        for kalla in ("KOLADA", "SCB", "PROTOKOLL"):
            os.environ.setdefault(f"{kalla}_ANROP_PER_SEKUND", "0")
        # Inspelningarna har två protokoll per sida och årsmapp.
        os.environ.setdefault("PROTOKOLL_URVAL", "2")

    from .main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
