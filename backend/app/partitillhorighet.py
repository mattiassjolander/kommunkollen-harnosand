"""Fastställd partitillhörighet per period (#100, ADR-0006).

Enligt ADR-0004 tas en ledamots parti ur protokollet vid varje sammanträde. Protokollen saknar ofta parti
eller har lästs fel, och partibyten är sällsynta. Redaktionen kan därför fastställa en persons parti under en
period: parti (eller partilös, '-'), från och med ett datum och till och med ett datum eller tills vidare,
med motivering. Perioden går från utkast via granskad till publicerad, och en utgivare som inte skrev den
godkänner den (ADR-0002). Den ändras genom en ny version och kan återkallas, som en rättelse (#74).

En publicerad period gäller alla förekomster av personen, under alla ihopslagna namn, vid sammanträden inom
perioden: närvaro och "tjänstgör för", röster och ersatta i voteringslistan, yrkanden, reservationer och
motionärer. Den läggs på när uppgiften läses. Tolkningen ändras inte. Ordningen för vad som gäller:

1. en publicerad rättelse av en enskild förekomst,
2. en publicerad fastställd partitillhörighet,
3. det som protokollet anger,
4. det härledda partiet (partier.py).

En förekomst där perioden ändrade partiet (protokollet angav inget eller ett annat parti) får markeringen
"Parti fastställt av redaktionen" med vad protokollet sa. Ett sammanträde utan datum omfattas inte.
Perioder för samma person får inte överlappa.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timezone

import psycopg



class Ogiltig(ValueError):
    """Perioden är inte giltig."""


class EjTillatet(PermissionError):
    """Användaren får inte göra det här med perioden."""


class Konflikt(Exception):
    """Perioden har inte den status som steget kräver, eller överlappar en publicerad period."""

_PARTI = re.compile(r"[A-ZÅÄÖ]{1,4}|-")
STATUSAR = ("utkast", "granskad", "publicerad", "ersatt", "aterkallad")

__all__ = ["EjTillatet", "Konflikt", "Ogiltig", "Gallande", "skapa", "andra", "ta_bort", "granska", "publicera",
           "ny_version", "aterkalla", "las", "lista"]


def _datum(v, namn: str, tomt: bool = False) -> date | None:
    if v in (None, "") and tomt:
        return None
    try:
        return v if isinstance(v, date) else date.fromisoformat(str(v))
    except ValueError as e:
        raise Ogiltig(f"Ange {namn} som ett datum, t.ex. 2026-01-01") from e


def _varden(data: dict, gammal: dict | None = None) -> dict:
    g = gammal or {}
    parti = data.get("parti", g.get("parti"))
    if not isinstance(parti, str) or not _PARTI.fullmatch(parti.strip()):
        raise Ogiltig("Partiet anges med förkortning, t.ex. S, eller - för partilös")
    fran = _datum(data.get("fran", g.get("fran")), "från och med")
    till = _datum(data.get("till", g.get("till")), "till och med", tomt=True)
    if till is not None and till < fran:
        raise Ogiltig("Perioden slutar före den börjar")
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför partitillhörigheten fastställs, till exempel vilka protokoll som visar den")
    return {"parti": parti.strip(), "fran": fran, "till": till, "motivering": motivering}


def _person(conn: psycopg.Connection, ledamot_id) -> int:
    if not isinstance(ledamot_id, int):
        raise Ogiltig("ledamot_id saknas")
    rad = conn.execute("SELECT coalesce(huvud_id, id) AS person FROM ledamot WHERE id = %s", (ledamot_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Ledamoten {ledamot_id} finns inte")
    return rad["person"]


def _overlappar(conn: psycopg.Connection, person: int, fran: date, till: date | None,
                utom: Iterable[int] = ()) -> None:
    """Avvisar en period som överlappar en publicerad period för samma person."""
    rad = conn.execute(
        """
        SELECT t.parti, t.fran, t.till FROM partitillhorighet t JOIN ledamot l ON l.id = t.ledamot_id
        WHERE t.status = 'publicerad' AND coalesce(l.huvud_id, l.id) = %(p)s AND NOT (t.id = ANY(%(utom)s))
          AND t.fran <= coalesce(%(till)s::date, 'infinity'::date) AND coalesce(t.till, 'infinity'::date) >= %(fran)s
        LIMIT 1
        """,
        {"p": person, "fran": fran, "till": till, "utom": [i for i in utom if i is not None]},
    ).fetchone()
    if rad:
        slut = rad["till"].isoformat() if rad["till"] else "tills vidare"
        raise Konflikt(f"Perioden överlappar en publicerad period ({rad['parti']}, {rad['fran'].isoformat()}–{slut})")


def skapa(conn: psycopg.Connection, data: dict, redaktor: str) -> dict:
    person = _person(conn, data.get("ledamot_id"))
    v = _varden(data)
    _overlappar(conn, person, v["fran"], v["till"])
    pid = conn.execute(
        """
        INSERT INTO partitillhorighet (ledamot_id, parti, fran, till, motivering, status, redaktor)
        VALUES (%(l)s, %(parti)s, %(fran)s, %(till)s, %(motivering)s, 'utkast', %(red)s) RETURNING id
        """,
        v | {"l": person, "red": redaktor},
    ).fetchone()["id"]
    return las(conn, pid)


def _hamta(conn: psycopg.Connection, period_id: int) -> dict:
    rad = conn.execute(
        "SELECT t.*, coalesce(l.huvud_id, l.id) AS person FROM partitillhorighet t JOIN ledamot l ON l.id = t.ledamot_id "
        "WHERE t.id = %s FOR UPDATE OF t", (period_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Partitillhörigheten {period_id} finns inte")
    return rad


def andra(conn: psycopg.Connection, period_id: int, data: dict, redaktor: str) -> dict:
    """Redaktören ändrar sitt utkast."""
    t = _hamta(conn, period_id)
    if t["redaktor"] != redaktor:
        raise EjTillatet("Bara redaktören som skrev perioden kan ändra den")
    if t["status"] != "utkast":
        raise Konflikt("Bara ett utkast kan ändras. Skapa en ny version i stället")
    v = _varden({"motivering": t["motivering"]} | data, t)
    _overlappar(conn, t["person"], v["fran"], v["till"], [t["ersatter_id"]])
    conn.execute("UPDATE partitillhorighet SET parti = %(parti)s, fran = %(fran)s, till = %(till)s, "
                 "motivering = %(motivering)s WHERE id = %(id)s", v | {"id": period_id})
    return las(conn, period_id)


def ta_bort(conn: psycopg.Connection, period_id: int, redaktor: str) -> None:
    t = _hamta(conn, period_id)
    if t["redaktor"] != redaktor:
        raise EjTillatet("Bara redaktören som skrev perioden kan ta bort den")
    if t["status"] != "utkast":
        raise Konflikt("Bara ett utkast kan tas bort")
    conn.execute("DELETE FROM partitillhorighet WHERE id = %s", (period_id,))


def _godkann(conn: psycopg.Connection, period_id: int, utgivare: str, fran: str) -> dict:
    t = _hamta(conn, period_id)
    if t["redaktor"] == utgivare:
        raise EjTillatet("Ingen godkänner sin egen registrering")
    if t["status"] != fran:
        raise Konflikt(f"Perioden är {t['status']}, inte {fran}")
    return t


def granska(conn: psycopg.Connection, period_id: int, utgivare: str) -> dict:
    _godkann(conn, period_id, utgivare, "utkast")
    conn.execute("UPDATE partitillhorighet SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), period_id))
    return las(conn, period_id)


def publicera(conn: psycopg.Connection, period_id: int, utgivare: str) -> dict:
    t = _godkann(conn, period_id, utgivare, "granskad")
    # Andra perioder kan ha publicerats sedan utkastet skrevs.
    _overlappar(conn, t["person"], t["fran"], t["till"], [t["ersatter_id"]])
    if t["ersatter_id"] is not None:
        conn.execute("UPDATE partitillhorighet SET status = 'ersatt' WHERE id = %s AND status IN "
                     "('utkast', 'granskad', 'publicerad')", (t["ersatter_id"],))
    conn.execute("UPDATE partitillhorighet SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), period_id))
    return las(conn, period_id)


def ny_version(conn: psycopg.Connection, period_id: int, data: dict, redaktor: str) -> dict:
    """En ny version av en granskad eller publicerad period, som utkast. Den ersätter den gamla när den publiceras."""
    t = _hamta(conn, period_id)
    if t["status"] == "utkast":
        raise Konflikt("Ett utkast ändras direkt, utan ny version")
    if t["status"] not in ("granskad", "publicerad"):
        raise Konflikt(f"Perioden är {t['status']} och kan inte få en ny version")
    if conn.execute("SELECT 1 FROM partitillhorighet WHERE ersatter_id = %s AND status IN ('utkast', 'granskad')",
                    (period_id,)).fetchone():
        raise Konflikt("Det finns redan en ny version som väntar på granskning")
    v = _varden(data, t)
    _overlappar(conn, t["person"], v["fran"], v["till"], [period_id])
    pid = conn.execute(
        """
        INSERT INTO partitillhorighet (ledamot_id, parti, fran, till, motivering, status, redaktor, ersatter_id)
        VALUES (%(l)s, %(parti)s, %(fran)s, %(till)s, %(motivering)s, 'utkast', %(red)s, %(ersatter)s) RETURNING id
        """,
        v | {"l": t["person"], "red": redaktor, "ersatter": period_id},
    ).fetchone()["id"]
    return las(conn, pid)


def aterkalla(conn: psycopg.Connection, period_id: int, data: dict, utgivare: str) -> dict:
    """En utgivare återkallar en publicerad period direkt. Protokollet och härledningen gäller igen."""
    t = _hamta(conn, period_id)
    if t["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad period kan återkallas, den här är {t['status']}")
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför perioden återkallas")
    conn.execute("UPDATE partitillhorighet SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, "
                 "aterkallelse = %s WHERE id = %s", (utgivare, datetime.now(timezone.utc), motivering, period_id))
    return las(conn, period_id)


_LISTA = """
    SELECT t.*, p.id AS person, p.namn AS person_namn
    FROM partitillhorighet t JOIN ledamot l ON l.id = t.ledamot_id
    JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id)
"""


def _ut(t: dict) -> dict:
    return {
        "id": t["id"], "ledamot": {"id": t["person"], "namn": t["person_namn"]},
        "parti": t["parti"], "fran": t["fran"], "till": t["till"], "motivering": t["motivering"],
        "status": t["status"], "ersatter_id": t["ersatter_id"],
        "redaktor": t["redaktor"], "skapad": t["skapad"], "granskad_av": t["granskad_av"], "granskad": t["granskad"],
        "publicerad_av": t["publicerad_av"], "publicerad": t["publicerad"],
        "aterkallad_av": t["aterkallad_av"], "aterkallad": t["aterkallad"], "aterkallelse": t["aterkallelse"],
    }


def las(conn: psycopg.Connection, period_id: int) -> dict:
    rad = conn.execute(f"{_LISTA} WHERE t.id = %s", (period_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Partitillhörigheten {period_id} finns inte")
    return _ut(rad)


def lista(conn: psycopg.Connection, status: str | None = None, ledamot_id: int | None = None,
          bara_publicerade: bool = False) -> list[dict]:
    person = _person(conn, ledamot_id) if ledamot_id is not None else None
    rader = conn.execute(
        f"""{_LISTA}
        WHERE (%(s)s::text IS NULL OR t.status = %(s)s) AND (%(p)s::bigint IS NULL OR p.id = %(p)s)
          AND (NOT %(pub)s OR t.status = 'publicerad')
        ORDER BY p.namn, t.fran, t.id
        """,
        {"s": status, "p": person, "pub": bara_publicerade},
    ).fetchall()
    return [_ut(r) for r in rader]


# Pålägg vid läsning

class Gallande:
    """De publicerade perioderna för personerna bakom en uppsättning namn i protokollen."""

    def __init__(self, conn: psycopg.Connection, namn: Iterable[str]) -> None:
        namn = sorted({n for n in namn if n})
        self._person: dict[str, int] = {}
        self._perioder: dict[int, list[dict]] = defaultdict(list)
        if not namn:
            return
        for r in conn.execute(
            "SELECT namn, coalesce(huvud_id, id) AS person FROM ledamot WHERE namn = ANY(%s)", (namn,)
        ):
            self._person[r["namn"]] = r["person"]
        if not self._person:
            return
        for t in conn.execute(
            f"{_LISTA} WHERE t.status = 'publicerad' AND p.id = ANY(%s) ORDER BY t.fran",
            (sorted(set(self._person.values())),),
        ):
            self._perioder[t["person"]].append(t)

    def period(self, namn: str | None, datum: date | None) -> dict | None:
        if not namn or datum is None or (person := self._person.get(namn)) is None:
            return None
        return next((t for t in self._perioder.get(person, [])
                     if t["fran"] <= datum and (t["till"] is None or datum <= t["till"])), None)

    def satt(self, mal: dict | None, datum: date | None, namn: str = "namn", parti: str = "parti") -> dict | None:
        """Lägger perioden på en förekomst (dict med namn och parti), om ingen rättelse av partiet finns.
        Ändrar perioden partiet får förekomsten "partitillhorighet" med vad protokollet sa."""
        if mal is None or "parti" in (mal.get("rattelser") or {}):
            return mal
        t = self.period(mal.get(namn), datum)
        if t is not None and mal.get(parti) != t["parti"]:
            mal["partitillhorighet"] = {
                "id": t["id"], "protokollet": mal.get(parti), "fran": t["fran"], "till": t["till"],
                "motivering": t["motivering"], "publicerad": t["publicerad"],
            }
            mal[parti] = t["parti"]
            mal.pop("parti_harlett", None)
        return mal
