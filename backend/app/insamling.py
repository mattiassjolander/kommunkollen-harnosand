"""Insamlingsmotorn: kör datakällor och lagrar deras uppgifter som observationer.

Observationer är append-only. En uppgift som redan finns med samma värde räknas som
oförändrad. En uppgift med ändrat värde blir en ny version, och den tidigare versionen
finns kvar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import psycopg

from .sources.base import Datakalla, Hamtning


@dataclass
class Kallresultat:
    datakalla_id: str
    status: str  # 'lyckad' | 'inga_nya' | 'misslyckad'
    antal_nya: int = 0
    antal_andrade: int = 0
    antal_oforandrade: int = 0
    fel: str | None = None


@dataclass
class Korningsresultat:
    korning_id: int
    status: str  # 'lyckad' | 'delvis_fel' | 'misslyckad'
    kallor: list[Kallresultat]


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
    if res.antal_nya or res.antal_andrade:
        res.status = "lyckad"
    return res


def kor_insamling(
    conn: psycopg.Connection, kallor: list[Datakalla], client: httpx.Client, utlosare: str = "manuell"
) -> Korningsresultat:
    korning_id = conn.execute(
        "INSERT INTO insamlingskorning (utlosare) VALUES (%s) RETURNING id", (utlosare,)
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
            INSERT INTO kallkorning (korning_id, datakalla_id, status, antal_nya, antal_andrade, antal_oforandrade, fel, startad, avslutad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            """,
            (korning_id, kalla.id, res.status, res.antal_nya, res.antal_andrade, res.antal_oforandrade, res.fel, startad),
        )
        conn.commit()
        resultat.append(res)

    misslyckade = sum(r.status == "misslyckad" for r in resultat)
    status = "lyckad" if misslyckade == 0 else ("misslyckad" if misslyckade == len(resultat) else "delvis_fel")
    conn.execute(
        "UPDATE insamlingskorning SET avslutad = now(), status = %s WHERE id = %s", (status, korning_id)
    )
    conn.commit()
    return Korningsresultat(korning_id=korning_id, status=status, kallor=resultat)
