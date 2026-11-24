"""Protokollavvikelser (#47): uppgifter i protokollen som inte stämmer med varandra, att anmäla till kommunen.

Kontrollerna finns i `protokollkontroller` och körs vid varje tolkning. Här sparas resultatet med redaktörens
status: ny, anmäld till kommunen, rättad av kommunen eller inte ett fel. En avvikelse identifieras av sin nyckel
inom sammanträdet, så statusen bevaras vid omtolkning.

En avvikelse som inte längre hittas
- i samma version av protokollet beror på tolkningen. Den tas bort om ingen har satt någon status, och sparas
  annars som "hittas inte längre".
- i en ny version av protokollet (samma adress) har rättats av kommunen: den sparas med den nya versionen
  (Reviderad av källan).
"""

from __future__ import annotations

from datetime import date, datetime

import psycopg

from . import kalender
from .protokollkontroller import TYPER, Fynd
from .sources.harnosand import organ_ref

STATUSAR = {
    "ny": "Ny",
    "anmald": "Anmäld till kommunen",
    "rattad": "Rättad av kommunen",
    "inte_fel": "Inte ett fel",
}


class Ogiltig(ValueError):
    pass


def lagra(conn: psycopg.Connection, sammantrade_id: int, dokument_id: int, dokument_typ: str, fynd: list[Fynd],
          tid: datetime) -> None:
    """Sparar kontrollernas resultat för sammanträdets protokoll och bevarar redaktörens status."""
    if dokument_typ == "paragrafprotokoll":
        # Ett paragrafprotokoll har bara några av sammanträdets paragrafer.
        fynd = [f for f in fynd if f.typ != "paragrafnummer"]
    # En ny version av samma protokoll har samma adress. Ett hela protokoll som ersätter ett paragrafprotokoll
    # är ingen ny version.
    tidigare = {r["nyckel"]: r for r in conn.execute(
        """
        SELECT a.id, a.nyckel, a.status, a.dokument_id,
               d.url = (SELECT url FROM dokument WHERE id = %s) AND a.dokument_id <> %s AS ny_version
        FROM protokollavvikelse a JOIN dokument d ON d.id = a.dokument_id WHERE a.sammantrade_id = %s
        """,
        (dokument_id, dokument_id, sammantrade_id))}
    for f in fynd:
        conn.execute(
            """
            INSERT INTO protokollavvikelse (sammantrade_id, typ, nyckel, paragraf, sida, text, dokument_id, hittad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sammantrade_id, nyckel) DO UPDATE SET
                typ = EXCLUDED.typ, paragraf = EXCLUDED.paragraf, sida = EXCLUDED.sida, text = EXCLUDED.text,
                dokument_id = EXCLUDED.dokument_id, hittas = true, atgardad_dokument_id = NULL
            """,
            (sammantrade_id, f.typ, f.nyckel, f.paragraf, f.sida, f.text, dokument_id, tid),
        )
    hittade = {f.nyckel for f in fynd}
    for nyckel, r in tidigare.items():
        if nyckel in hittade:
            continue
        if r["ny_version"]:
            # Kommunen har publicerat protokollet på nytt, och där stämmer uppgifterna.
            conn.execute("UPDATE protokollavvikelse SET hittas = false, atgardad_dokument_id = %s WHERE id = %s",
                         (dokument_id, r["id"]))
        elif r["status"] == "ny":
            conn.execute("DELETE FROM protokollavvikelse WHERE id = %s", (r["id"],))
        else:
            conn.execute("UPDATE protokollavvikelse SET hittas = false WHERE id = %s", (r["id"],))


def satt_status(conn: psycopg.Connection, avvikelse_id: int, data: dict, redaktor: str) -> dict:
    """Sätter status: {status, datum (ÅÅÅÅ-MM-DD, standard i dag), anteckning}."""
    status = data.get("status")
    if status not in STATUSAR:
        raise Ogiltig(f"Okänd status: {status}")
    try:
        datum = date.fromisoformat(data["datum"]) if data.get("datum") else kalender.idag()
    except (TypeError, ValueError) as e:
        raise Ogiltig("Datumet ska skrivas ÅÅÅÅ-MM-DD") from e
    anteckning = (data.get("anteckning") or "").strip() or None
    rad = conn.execute(
        """
        UPDATE protokollavvikelse SET status = %s, statusdatum = %s, anteckning = %s, status_satt_av = %s,
               status_satt = now()
        WHERE id = %s RETURNING id, sammantrade_id
        """,
        (status, datum, anteckning, redaktor, avvikelse_id),
    ).fetchone()
    if rad is None:
        raise LookupError(f"Avvikelsen {avvikelse_id} finns inte")
    conn.execute(
        """
        INSERT INTO protokollavvikelse_status (protokollavvikelse_id, status, statusdatum, anteckning, satt_av)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (avvikelse_id, status, datum, anteckning, redaktor),
    )
    return next(a for s in _sammantraden(conn, sammantrade_id=rad["sammantrade_id"]) for a in s["avvikelser"]
                if a["id"] == avvikelse_id)


def lista(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None, typ: str | None = None,
          status: str | None = None) -> dict:
    """Protokollavvikelserna per protokoll för åren fran–till, med antal per typ och status."""
    alla = _sammantraden(conn, fran=fran, till=till, organ=organ)
    rader = [a for s in alla for a in s["avvikelser"]]
    visade = []
    for s in alla:
        avv = [a for a in s["avvikelser"] if (typ is None or a["typ"] == typ) and (status is None or a["status"] == status)]
        if avv:
            visade.append(s | {"avvikelser": avv})
    return {
        "fran": fran,
        "till": till,
        "organ": organ_ref(organ) if organ else None,
        "typer": [{"id": k, "namn": n, "antal": sum(1 for a in rader if a["typ"] == k)} for k, n in TYPER.items()],
        "statusar": [{"id": k, "namn": n, "antal": sum(1 for a in rader if a["status"] == k)}
                     for k, n in STATUSAR.items()],
        "sammantraden": visade,
    }


def for_sammantrade(conn: psycopg.Connection, sammantrade_id: int) -> list[dict]:
    """Protokollavvikelserna för ett sammanträde."""
    return [a for s in _sammantraden(conn, sammantrade_id=sammantrade_id) for a in s["avvikelser"]]


def _sammantraden(conn: psycopg.Connection, fran: int | None = None, till: int | None = None,
                  organ: str | None = None, sammantrade_id: int | None = None) -> list[dict]:
    rader = conn.execute(
        """
        SELECT a.*, s.organ, s.datum, d.url, d.version, n.hamtad AS reviderad, n.url AS reviderad_url,
               (SELECT rubrik FROM behandling b WHERE b.sammantrade_id = a.sammantrade_id AND b.paragraf = a.paragraf
                ORDER BY ordning LIMIT 1) AS rubrik
        FROM protokollavvikelse a
        JOIN sammantrade s ON s.id = a.sammantrade_id
        JOIN dokument d ON d.id = s.dokument_id
        LEFT JOIN dokument n ON n.id = a.atgardad_dokument_id
        WHERE (%(id)s::bigint IS NULL OR s.id = %(id)s)
          AND (%(fran)s::int IS NULL OR s.datum >= make_date(%(fran)s, 1, 1))
          AND (%(till)s::int IS NULL OR s.datum < make_date(%(till)s + 1, 1, 1))
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
        ORDER BY s.datum DESC, s.id, a.paragraf NULLS FIRST, a.typ, a.id
        """,
        {"id": sammantrade_id, "fran": fran, "till": till, "organ": organ},
    ).fetchall()
    ut: dict[int, dict] = {}
    for r in rader:
        s = ut.setdefault(r["sammantrade_id"], {
            "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": organ_ref(r["organ"])},
            "url": r["url"],
            "avvikelser": [],
        })
        s["avvikelser"].append({
            "id": r["id"],
            "typ": r["typ"],
            "typnamn": TYPER[r["typ"]],
            "paragraf": r["paragraf"],
            "rubrik": r["rubrik"],
            "sida": r["sida"],
            "lank": f"{r['url']}#page={r['sida']}" if r["sida"] else r["url"],
            "text": r["text"],
            "hittas": r["hittas"],
            # Kommunen har publicerat protokollet på nytt, och där finns avvikelsen inte (Reviderad av källan).
            "reviderad": {"datum": r["reviderad"], "url": r["reviderad_url"]} if r["atgardad_dokument_id"] else None,
            "status": r["status"],
            "statusnamn": STATUSAR[r["status"]],
            "statusdatum": r["statusdatum"],
            "anteckning": r["anteckning"],
        })
    for s in ut.values():
        s["sammanstallning"] = sammanstallning(s)
    return list(ut.values())


def sammanstallning(s: dict) -> str:
    """En saklig sammanställning för ett protokoll, att skicka till nämndsekreteraren. Den tar med avvikelser
    som finns i den senaste versionen av protokollet och som inte är markerade som "inte ett fel"."""
    avv = [a for a in s["avvikelser"] if a["hittas"] and a["status"] in ("ny", "anmald")]
    if not avv:
        return ""
    datum = s["sammantrade"]["datum"]
    rader = [
        f"Protokoll: {s['sammantrade']['organ']['namn']} {datum.isoformat() if datum else ''}".rstrip(),
        s["url"],
        "",
        "I protokollet stämmer följande uppgifter inte med varandra:",
        "",
    ]
    for i, a in enumerate(avv, 1):
        paragraf = a["paragraf"] is not None and not a["text"].startswith("§")
        plats = ", ".join(x for x in (f"§ {a['paragraf']}" if paragraf else "",
                                       f"sidan {a['sida']}" if a["sida"] else "") if x)
        rader.append(f"{i}. {plats + ': ' if plats else ''}{a['text']}")
    rader += ["", "Kan protokollet rättas, eller finns det en förklaring till uppgifterna?"]
    return "\n".join(rader)
