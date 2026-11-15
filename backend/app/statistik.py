"""Statistik över protokollen (#44): behandlingar per organ, år och behandlingstyp.

Siffrorna räknas ur de tolkade protokollen, med publicerade rättelser pålagda. Underlaget redovisas
alltid bredvid: hur många sammanträden som räknats, vilka protokoll som inte gick att tolka (deras
behandlingar saknas i siffrorna) och vilka som bara finns som paragrafprotokoll (ofullständiga).
"""

from __future__ import annotations

import psycopg

from .behandlingstyper import TYPER
from .rattelser import Publicerade
from .sources.harnosand import ORGAN

OKAND = "okand"


def _organ(organ_id: str) -> dict:
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}


def _organordning(organ_id: str) -> int:
    return list(ORGAN).index(organ_id) if organ_id in ORGAN else len(ORGAN)


def tillgangliga_ar(conn: psycopg.Connection) -> list[int]:
    rad = conn.execute(
        "SELECT extract(year FROM min(datum))::int AS fran, extract(year FROM max(datum))::int AS till FROM sammantrade"
    ).fetchone()
    return list(range(rad["fran"], rad["till"] + 1)) if rad and rad["fran"] else []


def behandlingar(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None) -> dict:
    """Antal behandlingar per år, organ och typ för åren fran–till (båda inräknade)."""
    param = {"fran": fran, "till": till, "organ": organ}
    sammantraden = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.tolkning, d.typ AS dokument_typ, extract(year FROM s.datum)::int AS ar
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        WHERE s.datum >= make_date(%(fran)s, 1, 1) AND s.datum < make_date(%(till)s + 1, 1, 1)
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY s.datum, s.id
        """,
        param,
    ).fetchall()
    rader = conn.execute(
        """
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.sammantrade_id, b.paragraf, b.rubrik, b.beslut,
               b.diarienummer
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        WHERE s.datum >= make_date(%(fran)s, 1, 1) AND s.datum < make_date(%(till)s + 1, 1, 1)
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """,
        param,
    ).fetchall()

    sammantrade = {s["id"]: s for s in sammantraden}
    pub = Publicerade(conn, list(sammantrade))
    tomt = lambda: {t: 0 for t in [*TYPER, OKAND]}  # noqa: E731
    per: dict[tuple[int, str], dict] = {}
    for s in sammantraden:
        r = per.setdefault((s["ar"], s["organ"]), {"sammantraden": 0, "behandlingar": 0, "antal": tomt()})
        r["sammantraden"] += 1
    for b in rader:
        s = sammantrade[b["sammantrade_id"]]
        typ = pub.behandling(s["id"], {k: b[k] for k in ("paragraf", "rubrik", "beslut", "diarienummer")})["typ"]
        r = per[(s["ar"], s["organ"])]
        r["behandlingar"] += 1
        r["antal"][typ or OKAND] += 1

    summa = {"sammantraden": 0, "behandlingar": 0, "antal": tomt()}
    for r in per.values():
        summa["sammantraden"] += r["sammantraden"]
        summa["behandlingar"] += r["behandlingar"]
        for t, n in r["antal"].items():
            summa["antal"][t] += n

    def kort(s: dict) -> dict:
        return {"id": s["id"], "datum": s["datum"], "organ": _organ(s["organ"])}

    utan_datum = conn.execute(
        "SELECT count(*) AS n FROM sammantrade WHERE datum IS NULL AND (%(organ)s::text IS NULL OR organ = %(organ)s)",
        param,
    ).fetchone()["n"]
    return {
        "fran": fran,
        "till": till,
        "organ": _organ(organ) if organ else None,
        "typer": [{"id": t, "namn": n} for t, n in TYPER.items()] + [{"id": OKAND, "namn": "Kunde inte klassas"}],
        "rader": [
            {"ar": ar, "organ": _organ(o)} | r
            for (ar, o), r in sorted(per.items(), key=lambda x: (x[0][0], _organordning(x[0][1])))
        ],
        "summa": summa,
        "underlag": {
            # Protokoll som inte gick att tolka: deras behandlingar saknas i siffrorna.
            "ej_tolkade": [kort(s) for s in sammantraden if s["tolkning"] == "ej_tolkad"],
            # Sammanträden som bara finns som paragrafprotokoll: bara en del av behandlingarna.
            "paragrafprotokoll": [kort(s) for s in sammantraden if s["dokument_typ"] == "paragrafprotokoll"],
            # Protokoll utan datum kan inte placeras på ett år och räknas inte.
            "utan_datum": utan_datum,
        },
        "tillgangliga_ar": tillgangliga_ar(conn),
    }
