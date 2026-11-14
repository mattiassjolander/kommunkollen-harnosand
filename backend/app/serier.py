"""Tidsserier: aktuellt värde och versionshistorik för varje period, för ett mått och ett område."""

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
    versioner = conn.execute(
        """
        SELECT period, varde, kallans_publicering, hamtad, version
        FROM observation
        WHERE matt_id = %s AND omrade = %s
        ORDER BY period, version DESC
        """,
        (matt_id, omrade),
    ).fetchall()
    # Senast hämtad: senaste gången källan kontrollerades utan fel. Ett oförändrat värde sparas inte
    # igen, men det har ändå hämtats och jämförts.
    kontroll = conn.execute(
        "SELECT max(startad) AS t FROM kallkorning WHERE datakalla_id = %s AND status IN ('lyckad', 'inga_nya')",
        (matt["datakalla_id"],),
    ).fetchone()["t"]

    per_period: dict[str, list] = {}
    for v in versioner:
        per_period.setdefault(v["period"], []).append(v)

    def version(v) -> dict:
        return {
            # Ett saknat värde är null, aldrig noll.
            "varde": None if v["varde"] is None else float(v["varde"]),
            "kallans_publicering": v["kallans_publicering"],
            "hamtad": v["hamtad"],
            "version": v["version"],
        }

    punkter = []
    for period, lista in per_period.items():
        aktuell, *tidigare = lista
        punkter.append(version(aktuell) | {
            "period": period,
            # De fyra tidpunkterna (kravspec 12.3): källans publicering, avsedd period (ovan),
            # när systemet senast hämtade uppgiften och när den senast ändrades i systemet.
            "senast_hamtad": max(filter(None, [kontroll, aktuell["hamtad"]])),
            "senast_andrad": aktuell["hamtad"],
            "reviderad": bool(tidigare),
            # Tidigare versioner, senaste först. Skrivs aldrig över.
            "historik": [version(v) for v in tidigare],
        })
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
        "punkter": punkter,
    }
