"""Schemaläggaren: startar insamlingen automatiskt enligt schemat (kravspec 11.1).

Körs som en egen tjänst, oberoende av API:t och frontend:

    python -m app.schemalaggare

Varje minut kontrolleras om en planerad tidpunkt har passerat utan att en schemalagd körning
gjorts för den. Var tjänsten nere vid en tidpunkt körs insamlingen när den startar igen, en gång.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

import httpx
import psycopg

from . import db
from .insamling import InsamlingPagar, Korningsresultat, kor_insamling
from .main import standardkallor
from .schema import SVERIGE, Schema
from .sources.base import Datakalla

log = logging.getLogger("kommunkollen.schemalaggare")


def kor_om_dags(
    conn: psycopg.Connection, kallor: list[Datakalla], client: httpx.Client, schema: Schema, nu: datetime
) -> Korningsresultat | None:
    """Kör en insamling om den senast passerade planerade tidpunkten inte redan har körts."""
    planerad = schema.senaste(nu)
    redan = conn.execute(
        "SELECT 1 FROM insamlingskorning WHERE utlosare = 'schema' AND planerad_tid >= %s LIMIT 1", (planerad,)
    ).fetchone()
    conn.commit()
    if redan:
        return None
    try:
        return kor_insamling(conn, kallor, client, utlosare="schema", planerad_tid=planerad)
    except InsamlingPagar:
        log.info("En insamling pågår redan, försöker igen om en stund")
        return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    url = os.environ["DATABASE_URL"]
    schema = Schema.fran_miljo()
    if schema is None:
        log.info("Schemat är avstängt (INSAMLING_DAGAR är tomt). Ingen automatisk insamling.")
        while True:
            time.sleep(3600)
    db.migrate(url)
    log.info("Schemalagd insamling dag %s kl %s. Nästa: %s", schema.dagar, schema.klockan,
             schema.nasta(datetime.now(SVERIGE)).isoformat())
    while True:
        try:
            with db.connect(url) as conn, httpx.Client(timeout=30.0, headers={"User-Agent": "kommunkollen/0.1"}) as client:
                res = kor_om_dags(conn, standardkallor(), client, schema, datetime.now(SVERIGE))
            if res:
                log.info("Körning %s: %s. Nästa: %s", res.korning_id, res.status,
                         schema.nasta(datetime.now(SVERIGE)).isoformat())
        except Exception:  # schemaläggaren ska överleva t.ex. en databas som startar om
            log.exception("Kontrollen misslyckades, försöker igen om en minut")
        time.sleep(60)


if __name__ == "__main__":
    main()
