"""Kör en insamling från kommandoraden: `python -m app.insamla`.

Används på servern (`docker compose exec backend /app/.venv/bin/python -m app.insamla`).
Kräver DATABASE_URL.
"""

from __future__ import annotations

import os

import httpx

from . import db
from .insamling import InsamlingPagar, kor_insamling
from .main import standardkallor


def main() -> None:
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn, httpx.Client(timeout=30.0, headers={"User-Agent": "kommunkollen/0.1"}) as client:
        try:
            res = kor_insamling(conn, standardkallor(), client, utlosare="manuell")
        except InsamlingPagar as e:
            raise SystemExit(str(e)) from None
    print(f"Körning {res.korning_id}: {res.status}")
    for k in res.kallor:
        print(f"  {k.datakalla_id}: {k.status} (nya {k.antal_nya}, ändrade {k.antal_andrade}, oförändrade {k.antal_oforandrade})" + (f" – {k.fel}" if k.fel else ""))


if __name__ == "__main__":
    main()
