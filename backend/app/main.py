"""HTTP-API:t."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db
from .auth import Inloggning, krav_roll
from .insamling import kor_insamling
from .recorded import InspeladTransport
from .sources.base import Datakalla
from .sources.kolada import Kolada

KOMMUN = "2280"  # Härnösand


def standardkallor() -> list[Datakalla]:
    nyckeltal = os.environ.get("KOLADA_NYCKELTAL", "N03007").split(",")
    return [Kolada(nyckeltal=[n.strip() for n in nyckeltal if n.strip()], kommun=KOMMUN)]


def create_app(
    database_url: str | None = None,
    kallor: list[Datakalla] | None = None,
    transport: httpx.BaseTransport | None = None,
    inloggning: Inloggning | None = None,
    auth_transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    database_url = database_url or os.environ["DATABASE_URL"]
    kallor = kallor if kallor is not None else standardkallor()
    if transport is None and os.environ.get("INSPELNINGAR"):
        transport = InspeladTransport(Path(os.environ["INSPELNINGAR"]))

    db.migrate(database_url)
    app = FastAPI(title="Kommunkollen Härnösand")
    app.state.inloggning = inloggning or Inloggning.fran_miljo()
    app.add_middleware(
        SessionMiddleware,
        # Utan SESSION_SECRET blir alla utloggade när appen startas om.
        secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32),
        session_cookie="kommunkollen_session",
        same_site="lax",
        https_only=os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true",
        max_age=14 * 24 * 3600,
    )

    def http_klient() -> httpx.Client:
        return httpx.Client(transport=transport, timeout=30.0, headers={"User-Agent": "kommunkollen/0.1"})

    def auth_klient() -> httpx.Client:
        return httpx.Client(transport=auth_transport, timeout=15.0)

    app.include_router(auth.router(auth_klient))

    @app.get("/api/halsa")
    def halsa() -> dict:
        return {"status": "ok"}

    @app.post("/api/insamlingar", dependencies=[Depends(krav_roll("redaktor"))])
    def starta_insamling() -> dict:
        with db.connect(database_url) as conn, http_klient() as client:
            res = kor_insamling(conn, kallor, client, utlosare="manuell")
        return {
            "korning_id": res.korning_id,
            "status": res.status,
            "kallor": [vars(k) for k in res.kallor],
        }

    @app.get("/api/matt/{matt_id}/serie", dependencies=[Depends(krav_roll("lasare"))])
    def serie(matt_id: str, omrade: str = KOMMUN) -> dict:
        with db.connect(database_url) as conn:
            matt = conn.execute(
                """
                SELECT m.id, m.titel, m.beskrivning, m.enhet, m.kallans_publicering,
                       d.id AS datakalla_id, d.titel AS datakalla_titel, d.url AS datakalla_url
                FROM matt m JOIN datakalla d ON d.id = m.datakalla_id
                WHERE m.id = %s
                """,
                (matt_id,),
            ).fetchone()
            if matt is None:
                raise HTTPException(404, f"Måttet {matt_id} finns inte")
            punkter = conn.execute(
                """
                SELECT DISTINCT ON (period) period, varde, kallans_publicering, hamtad, version
                FROM observation
                WHERE matt_id = %s AND omrade = %s
                ORDER BY period, version DESC
                """,
                (matt_id, omrade),
            ).fetchall()
        return {
            "matt": {
                "id": matt["id"],
                "titel": matt["titel"],
                "beskrivning": matt["beskrivning"],
                "enhet": matt["enhet"],
                "kallans_publicering": matt["kallans_publicering"],
                "datakalla": {
                    "id": matt["datakalla_id"],
                    "titel": matt["datakalla_titel"],
                    "url": matt["datakalla_url"],
                },
            },
            "omrade": omrade,
            "punkter": [
                {
                    "period": p["period"],
                    "varde": None if p["varde"] is None else float(p["varde"]),
                    "kallans_publicering": p["kallans_publicering"],
                    "hamtad": p["hamtad"],
                    "version": p["version"],
                }
                for p in punkter
            ],
        }

    return app
