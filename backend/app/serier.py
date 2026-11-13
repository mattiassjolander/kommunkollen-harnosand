"""Tidsserier: senaste versionen av varje periods värde för ett mått och ett område."""

from __future__ import annotations

import psycopg


def las_serie(conn: psycopg.Connection, matt_id: str, omrade: str) -> dict | None:
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
        return None
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
                # Ett saknat värde är null, aldrig noll.
                "varde": None if p["varde"] is None else float(p["varde"]),
                "kallans_publicering": p["kallans_publicering"],
                "hamtad": p["hamtad"],
                "version": p["version"],
            }
            for p in punkter
        ],
    }
