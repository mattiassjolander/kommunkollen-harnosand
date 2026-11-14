"""Protokoll: lagring av hämtade protokoll och läsning av det som tolkats ur dem.

Ett protokoll sparas som plattformens egen kopia med SHA-256. Nytt innehåll under samma
adress blir en ny version. Varje ny version tolkas (se `protokolltolkning`), och sammanträdets
automatiskt tolkade uppgifter ersätts med den nya tolkningen. Sammanträdet behåller sitt id,
så länkar till det fortsätter att fungera.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

import psycopg
from psycopg.types.json import Jsonb

from .protokolltolkning import Narvaro, Tolkning, beslutande_vid, tolka
from .sources.base import Dokument
from .sources.harnosand import ORGAN


def _datum_ur_filnamn(filnamn: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", filnamn)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


def lagra_dokument(
    conn: psycopg.Connection, datakalla_id: str, d: Dokument, korning_id: int, hamtad: datetime
) -> tuple[str, str | None]:
    """Sparar dokumentet och tolkar det. Returnerar ('ny' | 'andrad' | 'oforandrad', fel eller None)."""
    sha = hashlib.sha256(d.innehall).hexdigest()
    senaste = conn.execute(
        "SELECT sha256, version FROM dokument WHERE url = %s ORDER BY version DESC LIMIT 1", (d.url,)
    ).fetchone()
    if senaste is not None and senaste["sha256"] == sha:
        return "oforandrad", None
    if senaste is None and conn.execute("SELECT 1 FROM dokument WHERE sha256 = %s", (sha,)).fetchone():
        return "oforandrad", None  # samma innehåll har publicerats under en annan adress
    version = 1 if senaste is None else senaste["version"] + 1
    dokument_id = conn.execute(
        """
        INSERT INTO dokument (datakalla_id, url, version, filnamn, typ, organ, sha256, storlek, innehall, hamtad, korning_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (datakalla_id, d.url, version, d.filnamn, d.typ, d.organ, sha, len(d.innehall), d.innehall, hamtad, korning_id),
    ).fetchone()["id"]

    t = tolka(d.innehall)
    _lagra_tolkning(conn, d, dokument_id, t, hamtad)
    fel = None
    if not t.tolkad:
        fel = f"{d.filnamn}: kunde inte tolkas automatiskt ({'; '.join(t.avvikelser)})"
    return ("ny" if version == 1 else "andrad"), fel


def _lagra_tolkning(conn: psycopg.Connection, d: Dokument, dokument_id: int, t: Tolkning, tolkad: datetime) -> None:
    if t.tolkad:
        datum = t.datum
        nyckel = f"{datum.isoformat()} {t.starttid}" if t.starttid else datum.isoformat()
    else:
        # Utan tolkning identifieras sammanträdet av filen. Datumet tas ur filnamnet om det går.
        datum = t.datum or _datum_ur_filnamn(d.filnamn)
        nyckel = f"fil:{d.filnamn}"
    sammantrade_id = conn.execute(
        """
        INSERT INTO sammantrade (organ, nyckel, datum, starttid, sluttid, plats, dokument_id, tolkning, avvikelser, tolkad)
        VALUES (%(organ)s, %(nyckel)s, %(datum)s, %(starttid)s, %(sluttid)s, %(plats)s, %(dokument_id)s,
                %(tolkning)s, %(avvikelser)s, %(tolkad)s)
        ON CONFLICT (organ, nyckel) DO UPDATE SET
            datum = EXCLUDED.datum, starttid = EXCLUDED.starttid, sluttid = EXCLUDED.sluttid, plats = EXCLUDED.plats,
            dokument_id = EXCLUDED.dokument_id, tolkning = EXCLUDED.tolkning, avvikelser = EXCLUDED.avvikelser,
            tolkad = EXCLUDED.tolkad
        RETURNING id
        """,
        {"organ": d.organ, "nyckel": nyckel, "datum": datum, "starttid": t.starttid, "sluttid": t.sluttid,
         "plats": t.plats, "dokument_id": dokument_id, "tolkning": "tolkad" if t.tolkad else "ej_tolkad",
         "avvikelser": Jsonb(t.avvikelser), "tolkad": tolkad},
    ).fetchone()["id"]
    conn.execute("DELETE FROM narvaro WHERE sammantrade_id = %s", (sammantrade_id,))
    conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s", (sammantrade_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori, tjanstgor_for,
                                 tjanstgor_for_parti, paragrafer, jav)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(sammantrade_id, i, n.namn, n.parti, n.roll, n.kategori, n.tjanstgor_for, n.tjanstgor_for_parti,
              n.paragrafer, n.jav) for i, n in enumerate(t.narvaro)],
        )
        cur.executemany(
            """
            INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, diarienummer, beslut)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [(sammantrade_id, i, b.paragraf, b.rubrik, b.diarienummer, b.beslut) for i, b in enumerate(t.behandlingar)],
        )


# Läsning

_SAMMANTRADE = """
    SELECT s.id, s.organ, s.datum, s.starttid, s.sluttid, s.plats, s.tolkning, s.avvikelser, s.tolkad,
           d.id AS dokument_id, d.url AS dokument_url, d.filnamn, d.version AS dokument_version,
           d.sha256, d.storlek, d.hamtad, d.datakalla_id, k.titel AS datakalla_titel,
           (SELECT count(*) FROM behandling b WHERE b.sammantrade_id = s.id) AS antal_behandlingar,
           (SELECT min(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS forsta_paragraf,
           (SELECT max(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS sista_paragraf
    FROM sammantrade s
    JOIN dokument d ON d.id = s.dokument_id
    JOIN datakalla k ON k.id = d.datakalla_id
"""


def _sammantrade(rad: dict) -> dict:
    organ = ORGAN.get(rad["organ"])
    return {
        "id": rad["id"],
        "organ": {"id": rad["organ"], "namn": organ.namn if organ else rad["organ"]},
        "datum": rad["datum"],
        "starttid": rad["starttid"],
        "sluttid": rad["sluttid"],
        "plats": rad["plats"],
        "tolkning": rad["tolkning"],
        "avvikelser": rad["avvikelser"],
        "antal_behandlingar": rad["antal_behandlingar"],
        "paragrafer": [rad["forsta_paragraf"], rad["sista_paragraf"]] if rad["forsta_paragraf"] is not None else None,
        "protokoll": {
            "dokument_id": rad["dokument_id"],
            "url": rad["dokument_url"],
            "kopia": f"/api/dokument/{rad['dokument_id']}",
            "filnamn": rad["filnamn"],
            "version": rad["dokument_version"],
            "sha256": rad["sha256"],
            "storlek": rad["storlek"],
            "hamtad": rad["hamtad"],
            "tolkad": rad["tolkad"],
            "datakalla": {"id": rad["datakalla_id"], "titel": rad["datakalla_titel"]},
        },
    }


def lista_sammantraden(conn: psycopg.Connection, organ: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"{_SAMMANTRADE} WHERE (%(organ)s::text IS NULL OR s.organ = %(organ)s) "
        "ORDER BY s.datum DESC NULLS LAST, s.starttid DESC NULLS LAST, s.id DESC",
        {"organ": organ},
    ).fetchall()
    return [_sammantrade(r) for r in rader]


def _narvaro(rader: list[dict]) -> list[Narvaro]:
    return [Narvaro(namn=r["namn"], parti=r["parti"], roll=r["roll"], kategori=r["kategori"],
                    tjanstgor_for=r["tjanstgor_for"], tjanstgor_for_parti=r["tjanstgor_for_parti"],
                    paragrafer=r["paragrafer"], jav=r["jav"]) for r in rader]


def _person(n: Narvaro) -> dict:
    return {
        "namn": n.namn, "parti": n.parti, "roll": n.roll, "kategori": n.kategori,
        "tjanstgor_for": {"namn": n.tjanstgor_for, "parti": n.tjanstgor_for_parti} if n.tjanstgor_for else None,
        "paragrafer": n.paragrafer, "jav": n.jav,
    }


def _las_narvaro(conn: psycopg.Connection, sammantrade_id: int) -> list[Narvaro]:
    return _narvaro(conn.execute(
        "SELECT * FROM narvaro WHERE sammantrade_id = %s ORDER BY ordning", (sammantrade_id,)).fetchall())


def _behandling(r: dict) -> dict:
    return {"paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"], "beslut": r["beslut"]}


def las_sammantrade(conn: psycopg.Connection, sammantrade_id: int) -> dict | None:
    rad = conn.execute(f"{_SAMMANTRADE} WHERE s.id = %s", (sammantrade_id,)).fetchone()
    if rad is None:
        return None
    behandlingar = conn.execute(
        "SELECT * FROM behandling WHERE sammantrade_id = %s ORDER BY ordning", (sammantrade_id,)).fetchall()
    return _sammantrade(rad) | {
        "narvaro": [_person(n) for n in _las_narvaro(conn, sammantrade_id)],
        "behandlingar": [_behandling(b) for b in behandlingar],
    }


def las_behandling(conn: psycopg.Connection, sammantrade_id: int, paragraf: int) -> dict | None:
    rad = conn.execute(f"{_SAMMANTRADE} WHERE s.id = %s", (sammantrade_id,)).fetchone()
    if rad is None:
        return None
    b = conn.execute(
        "SELECT * FROM behandling WHERE sammantrade_id = %s AND paragraf = %s ORDER BY ordning LIMIT 1",
        (sammantrade_id, paragraf),
    ).fetchone()
    if b is None:
        return None
    grannar = conn.execute(
        """
        SELECT (SELECT max(paragraf) FROM behandling WHERE sammantrade_id = %(s)s AND paragraf < %(p)s) AS foregaende,
               (SELECT min(paragraf) FROM behandling WHERE sammantrade_id = %(s)s AND paragraf > %(p)s) AS nasta
        """,
        {"s": sammantrade_id, "p": paragraf},
    ).fetchone()
    narvaro = _las_narvaro(conn, sammantrade_id)
    return _behandling(b) | {
        "sammantrade": _sammantrade(rad),
        "beslutande": [_person(n) for n in beslutande_vid(narvaro, paragraf)],
        "jav": [_person(n) for n in narvaro if paragraf in n.jav],
        "foregaende": grannar["foregaende"],
        "nasta": grannar["nasta"],
    }


def las_dokument(conn: psycopg.Connection, dokument_id: int) -> dict | None:
    return conn.execute(
        "SELECT filnamn, innehall, sha256 FROM dokument WHERE id = %s", (dokument_id,)).fetchone()
