"""Tolkar om de lagrade protokollen: `python -m app.tolka_om`.

Ett protokoll tolkas bara när det är nytt eller ändrat, så efter en förbättrad tolkning körs
det här en gång på servern (`docker compose exec backend /app/.venv/bin/python -m app.tolka_om`).
Inget hämtas från kommunen. Kräver DATABASE_URL.

Med --prov görs omtolkningen i en transaktion som rullas tillbaka. Kommandot skriver ut vad som skulle
ändras i ledamotsregistret (#165): namn som tas bort, slås ihop automatiskt eller blir förslag. Inget sparas,
och databasen migreras inte, så schemat måste redan vara aktuellt.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from . import db, kalender, kallelsepunkter, namnvarianter, sammantradesplan, sokindex
from .arenden import koppla
from .protokoll import tolka_om


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.tolka_om", description=__doc__.splitlines()[0])
    p.add_argument("--prov", action="store_true", help="visa vad omtolkningen skulle ändra, utan att spara något")
    a = p.parse_args(argv)
    url = os.environ["DATABASE_URL"]
    if not a.prov:
        db.migrate(url)
    with db.connect(url) as conn:
        fore = _namn(conn)
        antal = tolka_om(conn, datetime.now(timezone.utc))
        plan = namnvarianter.underhall(conn)
        nya = sorted(_namn(conn) - fore)
        if a.prov:
            conn.rollback()
            print(f"Provkörning: {antal['sammantraden']} sammanträden skulle tolkas om. Inget sparades.")
            print(f"{antal['nu_tolkade']} skulle kunna tolkas, {antal['nu_ej_tolkade']} skulle inte längre kunna tolkas.")
            _skriv(plan, nya)
            return
        kallelsepunkter.komplettera(conn)
        arenden = koppla(conn)
        sammantradesplan.lagra_beslut(conn, kalender.idag())
        # Dokumenten är desamma, så deras text läses inte om. Det gör `python -m app.sokindex --bygg-om`.
        sok = sokindex.indexera(conn, extrahera=False)
    print(
        f"{antal['sammantraden']} sammanträden tolkades om: {antal['nu_tolkade']} kunde nu tolkas, "
        f"{antal['nu_ej_tolkade']} kunde inte längre tolkas."
    )
    _skriv(plan, nya)
    print(f"{arenden['arenden']} ärenden, varav {arenden['kopplade']} med flera behandlingar.")
    print(f"Sökindexet: {sok['nya']} nya, {sok['andrade']} ändrade och {sok['borttagna']} borttagna enheter.")


def _namn(conn) -> set[str]:
    return {r["namn"] for r in conn.execute("SELECT namn FROM ledamot")}


def _skriv(plan: dict, nya: list[str]) -> None:
    print(f"Nya namn i registret ({len(nya)}):")
    for n in nya:
        print(f"  {n}")
    for rad in namnvarianter.skriv_plan(plan):
        print(rad)


if __name__ == "__main__":
    main()
