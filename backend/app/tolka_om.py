"""Tolkar om de lagrade protokollen: `python -m app.tolka_om`.

Ett protokoll tolkas bara när det är nytt eller ändrat, så efter en förbättrad tolkning körs
det här en gång på servern (`docker compose exec backend /app/.venv/bin/python -m app.tolka_om`).
Inget hämtas från kommunen. Kräver DATABASE_URL.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from . import db, kalender, kallelsepunkter, sammantradesplan, sokindex
from .arenden import koppla
from .protokoll import tolka_om


def main() -> None:
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn:
        antal = tolka_om(conn, datetime.now(timezone.utc))
        kallelsepunkter.komplettera(conn)
        arenden = koppla(conn)
        sammantradesplan.lagra_beslut(conn, kalender.idag())
        # Dokumenten är desamma, så deras text läses inte om. Det gör `python -m app.sokindex --bygg-om`.
        sok = sokindex.indexera(conn, extrahera=False)
    print(
        f"{antal['sammantraden']} sammanträden tolkades om: {antal['nu_tolkade']} kunde nu tolkas, "
        f"{antal['nu_ej_tolkade']} kunde inte längre tolkas."
    )
    print(f"{arenden['arenden']} ärenden, varav {arenden['kopplade']} med flera behandlingar.")
    print(f"Sökindexet: {sok['nya']} nya, {sok['andrade']} ändrade och {sok['borttagna']} borttagna enheter.")


if __name__ == "__main__":
    main()
