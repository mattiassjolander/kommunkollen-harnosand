"""Uppdateringsstatus: läser insamlingskörningarna och sammanställer dem för läsaren.

Kravspec avsnitt 12. En lyckad kontroll betyder inte att något var nytt: "inga nya
uppgifter" räknas som utan fel.
"""

from __future__ import annotations

import psycopg

from .insamling import UTAN_FEL
from .sources.base import Datakalla

_KORNING = "SELECT id, utlosare, startad, avslutad, status FROM insamlingskorning"


def global_status(conn: psycopg.Connection, kallor: list[Datakalla]) -> dict:
    senaste = conn.execute(
        f"{_KORNING} WHERE avslutad IS NOT NULL ORDER BY avslutad DESC, id DESC LIMIT 1"
    ).fetchone()
    senaste_lyckade = conn.execute(
        f"{_KORNING} WHERE status = 'lyckad' ORDER BY avslutad DESC, id DESC LIMIT 1"
    ).fetchone()

    # Varje konfigurerad källas senaste kontroll, oavsett i vilken körning den gjordes. En omkörning
    # av en enskild källa gör alltså inte de andra källornas kontroller inaktuella.
    rader = conn.execute(
        """
        SELECT DISTINCT ON (datakalla_id) datakalla_id, status FROM kallkorning
        WHERE datakalla_id = ANY(%s) ORDER BY datakalla_id, startad DESC
        """,
        ([k.id for k in kallor],),
    ).fetchall()
    kontrollerade = len(rader)
    utan_fel = sum(r["status"] in UTAN_FEL for r in rader)

    # Fullständigt uppdaterad: varje konfigurerad källa är kontrollerad och dess senaste kontroll var utan fel.
    fullstandigt = bool(kallor) and utan_fel == kontrollerade == len(kallor)
    return {
        "senaste_korning": senaste,
        "senaste_lyckade_korning": senaste_lyckade,
        "kallor_kontrollerade": kontrollerade,
        "kallor_utan_fel": utan_fel,
        "fullstandigt_uppdaterad": fullstandigt,
    }


def datakallor(conn: psycopg.Connection, kallor: list[Datakalla]) -> list[dict]:
    """Alla källor: de konfigurerade i ordning, sedan tidigare källor som finns i databasen."""
    rader = conn.execute(
        """
        SELECT d.id, d.titel, d.url,
               senaste.startad AS senaste_kontroll, senaste.status, senaste.fel,
               (SELECT max(k.startad) FROM kallkorning k
                 WHERE k.datakalla_id = d.id AND k.status IN ('lyckad', 'inga_nya')) AS senaste_lyckade_hamtning,
               (SELECT max(k.kallans_senaste_publicering) FROM kallkorning k
                 WHERE k.datakalla_id = d.id) AS senaste_publicering
        FROM datakalla d
        LEFT JOIN LATERAL (
            SELECT startad, status, fel FROM kallkorning k
            WHERE k.datakalla_id = d.id ORDER BY startad DESC LIMIT 1
        ) senaste ON true
        """
    ).fetchall()
    i_databasen = {r["id"]: r for r in rader}
    tom = {"senaste_kontroll": None, "status": None, "fel": None,
           "senaste_lyckade_hamtning": None, "senaste_publicering": None}
    resultat = [
        i_databasen.pop(k.id, None) or {"id": k.id, "titel": k.titel, "url": k.url, **tom} for k in kallor
    ]
    return resultat + sorted(i_databasen.values(), key=lambda r: r["titel"])


def korningslogg(conn: psycopg.Connection, antal: int) -> list[dict]:
    korningar = conn.execute(f"{_KORNING} ORDER BY startad DESC, id DESC LIMIT %s", (antal,)).fetchall()
    if not korningar:
        return []
    kallrader = conn.execute(
        """
        SELECT k.korning_id, k.datakalla_id, d.titel, k.status, k.antal_nya, k.antal_andrade,
               k.antal_oforandrade, k.fel, k.kallans_senaste_publicering AS senaste_publicering,
               k.startad, k.avslutad
        FROM kallkorning k JOIN datakalla d ON d.id = k.datakalla_id
        WHERE k.korning_id = ANY(%s)
        ORDER BY k.startad
        """,
        ([k["id"] for k in korningar],),
    ).fetchall()
    per_korning: dict[int, list[dict]] = {}
    for r in kallrader:
        per_korning.setdefault(r.pop("korning_id"), []).append(r)
    return [k | {"kallor": per_korning.get(k["id"], [])} for k in korningar]
