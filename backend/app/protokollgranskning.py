"""Granskade protokoll (#176): redaktionen markerar ett helt protokoll som granskat.

En redaktör eller utgivare jämför tolkningen med protokollet och markerar protokollet som granskat. En person
räcker, eftersom tolkningen är plattformens arbete och inte en människas. Det bryter alltså inte mot ADR-0002,
där ingen godkänner sitt eget arbete. Läsaren ser "Granskad av redaktionen ÅÅÅÅ-MM-DD" men inte vem.

- Protokollet går inte att granska när det har rättelser som är utkast eller väntar på publicering.
  Avvikelserna i protokollet visas som en varning men stoppar inte granskningen.
- En redaktör eller utgivare kan ta tillbaka granskningen med en motivering.
- Granskningen upphör när en omtolkning ändrar någon uppgift i protokollet. Regeln är fingeravtrycket av
  tolkningen: det sparas när protokollet granskas, och räknas om efter varje tolkning. Är det ett annat har
  tolkningen ändrats. Fingeravtrycket täcker allt som tolkningen sparar om protokollet: sammanträdets datum,
  tider, plats och tolkningsstatus, sittningarna, närvarolistan och behandlingarna med yrkanden, reservationer,
  hänvisningar, voteringar och röster. Avvikelserna och tidpunkten för tolkningen är inga uppgifter och ingår
  inte. Rättelserna ligger bredvid tolkningen (rattelser.py) och ingår inte heller.

Varje granskning är en rad i `protokollgranskning`, och raderna är loggen.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import psycopg

from . import avvikelser as avvikelser_mod


class Ogiltig(ValueError):
    pass


class Konflikt(Exception):
    pass


# Raderna som tolkningen skapar för ett sammanträde. Id:n skapas om vid varje tolkning och ingår inte.
_DELAR = {
    "sammantrade": """
        SELECT jsonb_build_object('datum', datum, 'starttid', starttid, 'sluttid', sluttid, 'plats', plats,
                                  'tolkning', tolkning) AS rad
        FROM sammantrade WHERE id = %(s)s""",
    "sittning": "SELECT to_jsonb(x) - 'id' - 'sammantrade_id' AS rad FROM sittning x WHERE sammantrade_id = %(s)s "
                "ORDER BY ordning",
    "narvaro": "SELECT to_jsonb(x) - 'id' - 'sammantrade_id' AS rad FROM narvaro x WHERE sammantrade_id = %(s)s "
               "ORDER BY ordning",
    "behandling": "SELECT to_jsonb(x) - 'id' - 'sammantrade_id' AS rad FROM behandling x "
                  "WHERE sammantrade_id = %(s)s ORDER BY ordning",
    **{
        tabell: f"""
            SELECT jsonb_build_object('behandling', b.ordning) || (to_jsonb(x) - 'id' - 'behandling_id') AS rad
            FROM {tabell} x JOIN behandling b ON b.id = x.behandling_id
            WHERE b.sammantrade_id = %(s)s ORDER BY b.ordning, x.ordning"""
        for tabell in ("yrkande", "reservation", "hanvisning", "votering")
    },
    "rost": """
        SELECT jsonb_build_object('behandling', b.ordning, 'votering', v.ordning) || (to_jsonb(x) - 'id' - 'votering_id')
               AS rad
        FROM rost x JOIN votering v ON v.id = x.votering_id JOIN behandling b ON b.id = v.behandling_id
        WHERE b.sammantrade_id = %(s)s ORDER BY b.ordning, v.ordning, x.ordning""",
}


def fingeravtryck(conn: psycopg.Connection, sammantrade_id: int) -> str:
    """Ett fingeravtryck (sha256) av tolkningen av sammanträdets protokoll."""
    innehall = {del_: [r["rad"] for r in conn.execute(sql, {"s": sammantrade_id})] for del_, sql in _DELAR.items()}
    text = json.dumps(innehall, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def efter_tolkning(conn: psycopg.Connection, sammantrade_id: int, tid: datetime) -> None:
    """Granskningen upphör om tolkningen har ändrat någon uppgift sedan protokollet granskades."""
    g = conn.execute(
        "SELECT id, fingeravtryck FROM protokollgranskning WHERE sammantrade_id = %s AND status = 'gallande'",
        (sammantrade_id,)).fetchone()
    if g is not None and g["fingeravtryck"] != fingeravtryck(conn, sammantrade_id):
        conn.execute("UPDATE protokollgranskning SET status = 'andrad', andrad = %s WHERE id = %s", (tid, g["id"]))


def _sammantrade(conn: psycopg.Connection, sammantrade_id: int) -> dict:
    s = conn.execute("SELECT id, tolkning, dokument_id FROM sammantrade WHERE id = %s FOR UPDATE",
                     (sammantrade_id,)).fetchone()
    if s is None:
        raise LookupError(f"Sammanträdet {sammantrade_id} finns inte")
    return s


def _oppna_rattelser(conn: psycopg.Connection, sammantrade_id: int) -> list[dict]:
    return conn.execute(
        "SELECT id, objekt, paragraf, namn, falt, status FROM rattelse "
        "WHERE sammantrade_id = %s AND status IN ('utkast', 'granskad') ORDER BY id",
        (sammantrade_id,)).fetchall()


def _avvikelser(conn: psycopg.Connection, sammantrade_id: int) -> list[str]:
    """Avvikelserna som redaktionen varnas för: tolkningens och kallelsens, och protokollavvikelserna som
    finns i den senaste versionen och inte är markerade som "inte ett fel" eller rättade."""
    s = conn.execute("SELECT avvikelser || kallelse_avvikelser AS a FROM sammantrade WHERE id = %s",
                     (sammantrade_id,)).fetchone()
    texter = [avvikelser_mod.objekt(a)["text"] for a in (s["a"] if s else [])]
    texter += [r["text"] for r in conn.execute(
        "SELECT text FROM protokollavvikelse WHERE sammantrade_id = %s AND hittas AND status IN ('ny', 'anmald') "
        "ORDER BY paragraf NULLS FIRST, id", (sammantrade_id,))]
    return texter


def _rad(r: dict) -> dict:
    return {
        "id": r["id"], "status": r["status"], "granskad_av": r["granskad_av"], "granskad": r["granskad"],
        "andrad": r["andrad"], "aterkallad_av": r["aterkallad_av"], "aterkallad": r["aterkallad"],
        "aterkallelse": r["aterkallelse"],
    }


def las(conn: psycopg.Connection, sammantrade_id: int) -> dict:
    """Granskningen för redaktionen: den gällande, loggen, det som spärrar och avvikelserna att varna för."""
    s = conn.execute("SELECT id, tolkning, dokument_id FROM sammantrade WHERE id = %s", (sammantrade_id,)).fetchone()
    if s is None:
        raise LookupError(f"Sammanträdet {sammantrade_id} finns inte")
    logg = conn.execute("SELECT * FROM protokollgranskning WHERE sammantrade_id = %s ORDER BY granskad DESC, id DESC",
                        (sammantrade_id,)).fetchall()
    gallande = next((r for r in logg if r["status"] == "gallande"), None)
    rattelser = _oppna_rattelser(conn, sammantrade_id)
    return {
        "gallande": _rad(gallande) if gallande else None,
        # Den senaste granskningen upphörde för att en omtolkning ändrade någon uppgift.
        "andrad_efter_granskning": bool(logg) and logg[0]["status"] == "andrad",
        "kan_granskas": gallande is None and not rattelser and s["tolkning"] == "tolkad",
        "oppna_rattelser": rattelser,
        "avvikelser": _avvikelser(conn, sammantrade_id),
        "logg": [_rad(r) for r in logg],
    }


def granska(conn: psycopg.Connection, sammantrade_id: int, person: str) -> dict:
    s = _sammantrade(conn, sammantrade_id)
    if s["tolkning"] != "tolkad":
        raise Konflikt("Protokollet kunde inte tolkas automatiskt och har ingen tolkning att granska")
    if conn.execute("SELECT 1 FROM protokollgranskning WHERE sammantrade_id = %s AND status = 'gallande'",
                    (sammantrade_id,)).fetchone():
        raise Konflikt("Protokollet är redan granskat")
    if oppna := _oppna_rattelser(conn, sammantrade_id):
        raise Konflikt(f"Protokollet har {len(oppna)} rättelser som inte är publicerade. Publicera eller ta bort "
                       "dem innan protokollet granskas")
    conn.execute(
        "INSERT INTO protokollgranskning (sammantrade_id, granskad_av, granskad, fingeravtryck) VALUES (%s, %s, %s, %s)",
        (sammantrade_id, person, datetime.now(timezone.utc), fingeravtryck(conn, sammantrade_id)))
    return las(conn, sammantrade_id)


def ta_tillbaka(conn: psycopg.Connection, sammantrade_id: int, data: dict, person: str) -> dict:
    _sammantrade(conn, sammantrade_id)
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför granskningen tas tillbaka")
    rad = conn.execute(
        """
        UPDATE protokollgranskning SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, aterkallelse = %s
        WHERE sammantrade_id = %s AND status = 'gallande' RETURNING id
        """,
        (person, datetime.now(timezone.utc), motivering, sammantrade_id)).fetchone()
    if rad is None:
        raise Konflikt("Protokollet är inte granskat")
    return las(conn, sammantrade_id)
