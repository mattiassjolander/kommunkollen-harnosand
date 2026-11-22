"""Slår ihop planerade sammanträden med protokollet samma dag: `python -m app.sla_ihop_planer` (#107).

Före #107 kopplades ett protokoll inte till det planerade sammanträdet när mötet började mer än en timme
senare än planerat. Då blev det två sammanträden: det planerade utan protokoll och protokollet utan plan.
Kommandot flyttar planen (plan_*-kolumnerna och versionerna) till protokollets sammanträde och tar bort
det tomma planerade. Kallelser och webbsändningar hör till organ och datum och följer med.

Utan --utfor visas bara paren och inget ändras. Ta en säkerhetskopia (pg_dump) innan det körs på servern
(docs/drift.md). Kräver DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os

from . import db, sammantradesplan


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.sla_ihop_planer", description=__doc__.splitlines()[0])
    p.add_argument("--utfor", action="store_true", help="spara sammanslagningen (annars bara en torrkörning)")
    a = p.parse_args(argv)
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn:
        par = sammantradesplan.sla_ihop_dubbletter(conn)
        for x in par:
            print(f"{x['organ']} {x['datum']}: planerat {x['planerat_id']} ({x['plan_starttid'] or 'utan tid'}) "
                  f"→ protokollets sammanträde {x['protokoll_id']} ({x['starttid'] or 'utan tid'})")
        if a.utfor:
            conn.commit()
            print(f"{len(par)} planerade sammanträden slogs ihop med protokollen.")
        else:
            conn.rollback()
            print(f"{len(par)} planerade sammanträden kan slås ihop. Inget ändrades (kör med --utfor).")


if __name__ == "__main__":
    main()
