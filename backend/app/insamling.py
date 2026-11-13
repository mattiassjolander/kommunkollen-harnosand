"""Insamlingsmotorn: kör datakällor och lagrar deras uppgifter som observationer.

Observationer är append-only. En uppgift som redan finns med samma värde räknas som
oförändrad. En uppgift med ändrat värde blir en ny version, och den tidigare versionen
finns kvar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
import psycopg

from .sources.base import Datakalla, Hamtning


@dataclass
class Kallresultat:
    datakalla_id: str
    status: str  # 'lyckad' | 'inga_nya' | 'delvis_fel' | 'misslyckad'
    antal_nya: int = 0
    antal_andrade: int = 0
    antal_oforandrade: int = 0
    fel: str | None = None
    senaste_publicering: date | None = None


@dataclass
class Korningsresultat:
    korning_id: int
    status: str  # 'lyckad' | 'delvis_fel' | 'misslyckad'
    kallor: list[Kallresultat]


UTAN_FEL = ("lyckad", "inga_nya")


def korningsstatus(kallstatusar: list[str]) -> str:
    """En körning är lyckad om alla källor kontrollerades utan fel, även om inget var nytt."""
    if all(s in UTAN_FEL for s in kallstatusar):
        return "lyckad"
    if all(s == "misslyckad" for s in kallstatusar):
        return "misslyckad"
    return "delvis_fel"


def _senast_lyckad(conn: psycopg.Connection, datakalla_id: str) -> datetime | None:
    rad = conn.execute(
        "SELECT max(startad) AS t FROM kallkorning WHERE datakalla_id = %s AND status IN ('lyckad', 'inga_nya')",
        (datakalla_id,),
    ).fetchone()
    return rad["t"] if rad else None


def _lagra(conn: psycopg.Connection, kalla: Datakalla, hamtning: Hamtning, korning_id: int, hamtad: datetime) -> Kallresultat:
    res = Kallresultat(datakalla_id=kalla.id, status="inga_nya")
    for m in hamtning.matt:
        conn.execute(
            """
            INSERT INTO matt (id, datakalla_id, titel, beskrivning, enhet, kallans_publicering, uppdaterad)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET titel = EXCLUDED.titel, beskrivning = EXCLUDED.beskrivning,
                enhet = EXCLUDED.enhet, kallans_publicering = EXCLUDED.kallans_publicering,
                uppdaterad = EXCLUDED.uppdaterad
            """,
            (m.id, kalla.id, m.titel, m.beskrivning, m.enhet, m.kallans_publicering, hamtad),
        )
    for u in hamtning.uppgifter:
        senaste = conn.execute(
            """
            SELECT varde, version FROM observation
            WHERE matt_id = %s AND omrade = %s AND period = %s
            ORDER BY version DESC LIMIT 1
            """,
            (u.matt_id, u.omrade, u.period),
        ).fetchone()
        if senaste is not None and senaste["varde"] == u.varde:
            res.antal_oforandrade += 1
            continue
        version = 1 if senaste is None else senaste["version"] + 1
        conn.execute(
            """
            INSERT INTO observation (matt_id, omrade, period, varde, kallans_publicering, hamtad, version, korning_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (u.matt_id, u.omrade, u.period, u.varde, u.kallans_publicering, hamtad, version, korning_id),
        )
        if senaste is None:
            res.antal_nya += 1
        else:
            res.antal_andrade += 1
    publiceringar = [d for d in (*(m.kallans_publicering for m in hamtning.matt),
                                 *(u.kallans_publicering for u in hamtning.uppgifter)) if d]
    res.senaste_publicering = max(publiceringar, default=None)
    if hamtning.fel:
        res.status = "delvis_fel"
        res.fel = "; ".join(hamtning.fel)
    elif res.antal_nya or res.antal_andrade:
        res.status = "lyckad"
    return res


# Nyckel för Postgres advisory lock som hindrar att två insamlingar körs samtidigt,
# oavsett om de startas av schemaläggaren eller manuellt (också från olika processer).
LASNYCKEL = 0x6B6B_0001


class InsamlingPagar(Exception):
    """En annan insamling pågår redan."""


def kor_insamling(
    conn: psycopg.Connection,
    kallor: list[Datakalla],
    client: httpx.Client,
    utlosare: str = "manuell",
    planerad_tid: datetime | None = None,
) -> Korningsresultat:
    if not conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (LASNYCKEL,)).fetchone()["ok"]:
        conn.rollback()
        raise InsamlingPagar("En insamling pågår redan. Försök igen när den är klar.")
    try:
        return _kor(conn, kallor, client, utlosare, planerad_tid)
    finally:
        conn.rollback()
        conn.execute("SELECT pg_advisory_unlock(%s)", (LASNYCKEL,))
        conn.commit()


def _kor(
    conn: psycopg.Connection, kallor: list[Datakalla], client: httpx.Client, utlosare: str, planerad_tid: datetime | None
) -> Korningsresultat:
    korning_id = conn.execute(
        "INSERT INTO insamlingskorning (utlosare, planerad_tid) VALUES (%s, %s) RETURNING id", (utlosare, planerad_tid)
    ).fetchone()["id"]
    conn.commit()

    resultat: list[Kallresultat] = []
    for kalla in kallor:
        startad = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO datakalla (id, titel, url) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET titel = EXCLUDED.titel, url = EXCLUDED.url",
            (kalla.id, kalla.titel, kalla.url),
        )
        try:
            hamtning = kalla.hamta(client, _senast_lyckad(conn, kalla.id))
            res = _lagra(conn, kalla, hamtning, korning_id, startad)
        except Exception as e:  # ett fel i en källa får inte stoppa de andra
            conn.rollback()
            conn.execute(
                "INSERT INTO datakalla (id, titel, url) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (kalla.id, kalla.titel, kalla.url),
            )
            res = Kallresultat(datakalla_id=kalla.id, status="misslyckad", fel=f"{type(e).__name__}: {e}")
        conn.execute(
            """
            INSERT INTO kallkorning (korning_id, datakalla_id, status, antal_nya, antal_andrade, antal_oforandrade,
                                     fel, kallans_senaste_publicering, startad, avslutad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            """,
            (korning_id, kalla.id, res.status, res.antal_nya, res.antal_andrade, res.antal_oforandrade,
             res.fel, res.senaste_publicering, startad),
        )
        conn.commit()
        resultat.append(res)

    status = korningsstatus([r.status for r in resultat])
    conn.execute(
        "UPDATE insamlingskorning SET avslutad = now(), status = %s WHERE id = %s", (status, korning_id)
    )
    conn.commit()
    return Korningsresultat(korning_id=korning_id, status=status, kallor=resultat)
