"""HTTP-API:t."""

from __future__ import annotations

import os
from datetime import datetime
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db, ekonomi, floden, serier, status
from .auth import Inloggning, krav_roll
from .insamling import InsamlingPagar, kor_insamling
from .recorded import InspeladTransport
from .robust import Robusthet
from .schema import SVERIGE, Schema
from .sources.base import Datakalla
from .sources.kolada import Kolada
from .sources.scb import Scb

KOMMUN = "2280"  # Härnösand
FRAN_MILJO = object()  # create_app läser schemat från miljön om inget anges


def _unika(matt: list) -> list:
    return list({m.id: m for m in matt}.values())


def _anropsgrans(namn: str, standard: float) -> float | None:
    """Anrop per sekund från miljön, t.ex. SCB_ANROP_PER_SEKUND=2. 0 betyder ingen gräns."""
    varde = float(os.environ.get(f"{namn}_ANROP_PER_SEKUND") or standard)
    return varde or None


def standardkallor() -> list[Datakalla]:
    return [
        Kolada(nyckeltal=[*ekonomi.KOLADA, floden.INVANARE.split(":")[1]], kommun=KOMMUN,
               anrop_per_sekund=_anropsgrans("KOLADA", 5)),
        Scb(matt=_unika([*ekonomi.SCB, *floden.SCB_MATT]), differenser=[ekonomi.RORELSEKAPITAL], kommun=KOMMUN,
            anrop_per_sekund=_anropsgrans("SCB", 2)),
    ]


def create_app(
    database_url: str | None = None,
    kallor: list[Datakalla] | None = None,
    transport: httpx.BaseTransport | None = None,
    inloggning: Inloggning | None = None,
    auth_transport: httpx.BaseTransport | None = None,
    schema: Schema | None | object = FRAN_MILJO,
    robusthet: Robusthet | None = None,
) -> FastAPI:
    if schema is FRAN_MILJO:
        schema = Schema.fran_miljo()
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
    def starta_insamling(kalla: str | None = None) -> dict:
        """Kör alla källor, eller bara `kalla` (omkörning av en enskild källa)."""
        valda = kallor if kalla is None else [k for k in kallor if k.id == kalla]
        if not valda:
            raise HTTPException(404, f"Datakällan {kalla} finns inte")
        with db.connect(database_url) as conn, http_klient() as client:
            try:
                res = kor_insamling(conn, valda, client, utlosare="manuell", robusthet=robusthet)
            except InsamlingPagar as e:
                raise HTTPException(409, str(e)) from None
        return {
            "korning_id": res.korning_id,
            "status": res.status,
            "kallor": [vars(k) for k in res.kallor],
        }

    @app.get("/api/status", dependencies=[Depends(krav_roll("lasare"))])
    def uppdateringsstatus() -> dict:
        with db.connect(database_url) as conn:
            resultat = status.global_status(conn, kallor)
        resultat["nasta_korning"] = schema.nasta(datetime.now(SVERIGE)) if schema else None
        return resultat

    @app.get("/api/datakallor", dependencies=[Depends(krav_roll("lasare"))])
    def datakallor() -> list[dict]:
        with db.connect(database_url) as conn:
            return status.datakallor(conn, kallor)

    @app.get("/api/insamlingar", dependencies=[Depends(krav_roll("lasare"))])
    def korningslogg(antal: int = Query(50, ge=1, le=500)) -> list[dict]:
        with db.connect(database_url) as conn:
            return status.korningslogg(conn, antal)

    @app.get("/api/matt/{matt_id}/serie", dependencies=[Depends(krav_roll("lasare"))])
    def serie(matt_id: str, omrade: str = KOMMUN) -> dict:
        with db.connect(database_url) as conn:
            resultat = serier.las_serie(conn, matt_id, omrade)
        if resultat is None:
            raise HTTPException(404, f"Måttet {matt_id} finns inte")
        return resultat

    @app.get("/api/ekonomi", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomiska_nyckeltal(omrade: str = KOMMUN) -> dict:
        """Alla ekonomiska nyckeltal i katalogen, grupperade. Ett mått som inte samlats in än har serie null."""
        with db.connect(database_url) as conn:
            grupper = []
            for g in ekonomi.GRUPPER:
                nyckeltal = []
                for matt_id in g.matt:
                    s = serier.las_serie(conn, matt_id, omrade)
                    nyckeltal.append({
                        "id": matt_id,
                        "prisniva": ekonomi.prisniva(s["matt"]["enhet"]) if s else None,
                        "serie": s,
                    })
                grupper.append({"id": g.id, "titel": g.titel, "nyckeltal": nyckeltal})
        return {"omrade": omrade, "grupper": grupper}

    @app.get("/api/floden", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomiska_floden(
        ar: str | None = None, jamfor: str | None = None, verksamhet: str | None = None, omrade: str = KOMMUN
    ) -> dict:
        """Sankey-modellen för ett år. Utan år: senaste år med fullständigt underlag.

        `verksamhet` (t.ex. 490) ger fördjupningen i ett verksamhetsområdes kostnadsslag.
        `jamfor` lägger till förändringen per flöde mot ett annat år.
        """
        if verksamhet is not None and verksamhet not in floden.OMRADESNAMN:
            raise HTTPException(404, f"Verksamhetsområdet {verksamhet} finns inte")
        with db.connect(database_url) as conn:
            varden = floden.las_varden(conn, omrade)
            titlar = {r["id"]: r["titel"] for r in conn.execute("SELECT id, titel FROM matt")}

        def berakna(a: str) -> dict:
            if verksamhet is None:
                return floden.modell(varden, a, titlar)
            return floden.fordjupning(varden, a, verksamhet, titlar)

        ar_lista = [{"ar": a, "fullstandig": berakna(a)["fullstandig"]} for a in floden.tillgangliga_ar(varden)]
        if ar is None:
            fullstandiga = [a["ar"] for a in ar_lista if a["fullstandig"]]
            ar = fullstandiga[-1] if fullstandiga else (ar_lista[-1]["ar"] if ar_lista else None)
        if ar is None:
            return {"ar": None, "tillgangliga_ar": [], "fullstandig": False, "saknas": [], "noder": [], "floden": [],
                    "verksamhet": None}
        resultat = berakna(ar)
        if jamfor is not None and jamfor != ar:
            resultat = floden.jamfor(resultat, berakna(jamfor))
        return resultat | {"omrade": omrade, "tillgangliga_ar": ar_lista}

    return app
