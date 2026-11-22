"""Redaktionella rättelser av automatiskt tolkade uppgifter (#33).

En redaktör skriver en rättelse som utkast. En utgivare som inte skrev den granskar och
publicerar den (kravspec 18: utkast → granskad → publicerad, ingen godkänner sin egen
registrering). En publicerad rättelse läggs på uppgiften när den läses, och läsaren ser både
rättelsen och vad tolkningen sa. Tolkningen ändras aldrig, så en ny insamling eller omtolkning
bevarar rättelsen.

Rättningsbara uppgifter:

- en behandlings rubrik, beslut, diarienummer och typ (behandlingstyper.py),
- motionärerna för en motion, på ärendets behandling där motionen väcktes (motionarer.py, #78),
- en röst i en votering (rösten och partiet),
- partiet för en person i närvarolistan.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import motionarer
from .behandlingstyper import TYPER, klassa

FALT = {"behandling": ("rubrik", "beslut", "diarienummer", "typ", "motionarer"), "rost": ("rost", "parti"), "narvaro": ("parti",)}
ROSTER = ("ja", "nej", "avstar", "franvarande")
# Fält som kopplingarna mellan behandlingar bygger på.
KOPPLANDE_FALT = ("rubrik", "diarienummer")
_PARTI = re.compile(r"[A-ZÅÄÖ]{1,4}|-")
_DNR = re.compile(r"[\w/ .:-]{2,40}")


class Ogiltig(ValueError):
    """Rättelsen är inte giltig (fel fält eller värde)."""


class EjTillatet(PermissionError):
    """Användaren får inte göra det här med rättelsen."""


class Konflikt(Exception):
    """Rättelsen har inte den status som steget kräver."""


def _ursprungligt(conn: psycopg.Connection, m: dict) -> Any:
    """Tolkningens värde för uppgiften. LookupError om uppgiften inte finns."""
    if m["objekt"] == "behandling":
        rad = conn.execute(
            "SELECT rubrik, beslut, diarienummer, motionarer FROM behandling WHERE sammantrade_id = %s AND paragraf = %s "
            "ORDER BY ordning LIMIT 1",
            (m["sammantrade_id"], m["paragraf"]),
        ).fetchone()
        if rad is None:
            raise LookupError(f"§ {m['paragraf']} finns inte i sammanträdet {m['sammantrade_id']}")
        if m["falt"] == "typ":
            return klassa(rad["rubrik"], rad["beslut"])
        if m["falt"] == "motionarer":
            return rad["motionarer"] or []
        return rad[m["falt"]]
    if m["objekt"] == "rost":
        rad = conn.execute(
            """
            SELECT r.rost, r.parti FROM rost r
            JOIN votering v ON v.id = r.votering_id
            JOIN behandling b ON b.id = v.behandling_id
            WHERE b.sammantrade_id = %s AND b.paragraf = %s AND v.ordning = %s AND r.namn = %s
            ORDER BY b.ordning, r.ordning LIMIT 1
            """,
            (m["sammantrade_id"], m["paragraf"], m["votering"] - 1, m["namn"]),
        ).fetchone()
        if rad is None:
            raise LookupError(f"{m['namn']} röstade inte i votering {m['votering']} vid § {m['paragraf']}")
        return rad[m["falt"]]
    rad = conn.execute(
        "SELECT parti FROM narvaro WHERE sammantrade_id = %s AND namn = %s ORDER BY ordning LIMIT 1",
        (m["sammantrade_id"], m["namn"]),
    ).fetchone()
    if rad is None:
        raise LookupError(f"{m['namn']} finns inte i närvarolistan")
    return rad["parti"]


def _mal(data: dict) -> dict:
    objekt = data.get("objekt")
    if objekt not in FALT:
        raise Ogiltig("objekt ska vara behandling, rost eller narvaro")
    if data.get("falt") not in FALT[objekt]:
        raise Ogiltig(f"Fältet för {objekt} ska vara {', '.join(FALT[objekt])}")
    m = {"sammantrade_id": data.get("sammantrade_id"), "objekt": objekt, "falt": data["falt"],
         "paragraf": data.get("paragraf") if objekt != "narvaro" else None,
         "votering": data.get("votering") if objekt == "rost" else None,
         "namn": (data.get("namn") or "").strip() if objekt != "behandling" else ""}
    if not isinstance(m["sammantrade_id"], int):
        raise Ogiltig("sammantrade_id saknas")
    if objekt != "narvaro" and not isinstance(m["paragraf"], int):
        raise Ogiltig("paragraf saknas")
    if objekt == "rost" and not isinstance(m["votering"], int):
        raise Ogiltig("votering saknas")
    if objekt != "behandling" and not m["namn"]:
        raise Ogiltig("namn saknas")
    return m


def _nytt(falt: str, varde: Any, conn: psycopg.Connection | None = None) -> Any:
    if falt == "motionarer":
        try:
            return motionarer.normalisera(conn, varde)
        except motionarer.Ogiltig as e:
            raise Ogiltig(str(e)) from e
    if falt in ("rubrik", "beslut"):
        if not isinstance(varde, str) or not varde.strip():
            raise Ogiltig(f"Ange en text för {falt}")
        return varde.strip()
    if falt == "diarienummer":
        if not isinstance(varde, list) or not all(isinstance(d, str) and _DNR.fullmatch(d.strip()) for d in varde):
            raise Ogiltig("Diarienummer ska vara en lista med nummer")
        return [d.strip() for d in varde]
    if falt == "typ":
        if varde is not None and varde not in TYPER:
            raise Ogiltig(f"Typen ska vara {', '.join(TYPER)}, eller tom om den inte går att avgöra")
        return varde
    if falt == "rost":
        if varde not in ROSTER:
            raise Ogiltig(f"Rösten ska vara {', '.join(ROSTER)}")
        return varde
    if varde is None:
        return None  # parti: protokollet anger inget parti
    if not isinstance(varde, str) or not _PARTI.fullmatch(varde.strip()):
        raise Ogiltig("Partiet anges med förkortning, t.ex. S, eller - för partilös")
    return varde.strip()


def _motivering(data: dict) -> str:
    text = (data.get("motivering") or "").strip()
    if not text:
        raise Ogiltig("Ange varför uppgiften rättas, till exempel var i protokollet det står")
    return text


def skapa(conn: psycopg.Connection, data: dict, redaktor: str) -> dict:
    m = _mal(data)
    ursprungligt = _ursprungligt(conn, m)
    nytt = _nytt(m["falt"], data.get("nytt"), conn)
    if nytt == ursprungligt:
        raise Ogiltig("Det nya värdet är samma som tolkningen")
    rid = conn.execute(
        """
        INSERT INTO rattelse (sammantrade_id, objekt, paragraf, votering, namn, falt, ursprungligt, nytt,
                              motivering, status, redaktor)
        VALUES (%(sammantrade_id)s, %(objekt)s, %(paragraf)s, %(votering)s, %(namn)s, %(falt)s, %(u)s, %(n)s,
                %(mot)s, 'utkast', %(red)s)
        RETURNING id
        """,
        m | {"u": Jsonb(ursprungligt), "n": Jsonb(nytt), "mot": _motivering(data), "red": redaktor},
    ).fetchone()["id"]
    return las(conn, rid)


def _hamta(conn: psycopg.Connection, rattelse_id: int) -> dict:
    rad = conn.execute("SELECT * FROM rattelse WHERE id = %s FOR UPDATE", (rattelse_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Rättelsen {rattelse_id} finns inte")
    return rad


def andra(conn: psycopg.Connection, rattelse_id: int, data: dict, redaktor: str) -> dict:
    """Redaktören ändrar sitt utkast."""
    r = _hamta(conn, rattelse_id)
    if r["redaktor"] != redaktor:
        raise EjTillatet("Bara redaktören som skrev rättelsen kan ändra den")
    if r["status"] != "utkast":
        raise Konflikt("Bara ett utkast kan ändras")
    nytt = _nytt(r["falt"], data.get("nytt", r["nytt"]), conn)
    motivering = _motivering(data) if "motivering" in data else r["motivering"]
    conn.execute("UPDATE rattelse SET nytt = %s, motivering = %s WHERE id = %s", (Jsonb(nytt), motivering, rattelse_id))
    return las(conn, rattelse_id)


def ta_bort(conn: psycopg.Connection, rattelse_id: int, redaktor: str) -> None:
    r = _hamta(conn, rattelse_id)
    if r["redaktor"] != redaktor:
        raise EjTillatet("Bara redaktören som skrev rättelsen kan ta bort den")
    if r["status"] != "utkast":
        raise Konflikt("Bara ett utkast kan tas bort")
    conn.execute("DELETE FROM rattelse WHERE id = %s", (rattelse_id,))


def _godkann(conn: psycopg.Connection, rattelse_id: int, utgivare: str, fran: str) -> dict:
    r = _hamta(conn, rattelse_id)
    if r["redaktor"] == utgivare:
        raise EjTillatet("Ingen godkänner sin egen rättelse")
    if r["status"] != fran:
        raise Konflikt(f"Rättelsen är {r['status']}, inte {fran}")
    return r


def granska(conn: psycopg.Connection, rattelse_id: int, utgivare: str) -> dict:
    _godkann(conn, rattelse_id, utgivare, "utkast")
    conn.execute("UPDATE rattelse SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), rattelse_id))
    return las(conn, rattelse_id)


def publicera(conn: psycopg.Connection, rattelse_id: int, utgivare: str) -> dict:
    r = _godkann(conn, rattelse_id, utgivare, "granskad")
    conn.execute(
        """
        UPDATE rattelse SET status = 'ersatt'
        WHERE status = 'publicerad' AND sammantrade_id = %(s)s AND objekt = %(o)s
          AND paragraf IS NOT DISTINCT FROM %(p)s AND votering IS NOT DISTINCT FROM %(v)s
          AND namn = %(n)s AND falt = %(f)s
        """,
        {"s": r["sammantrade_id"], "o": r["objekt"], "p": r["paragraf"], "v": r["votering"], "n": r["namn"],
         "f": r["falt"]},
    )
    conn.execute("UPDATE rattelse SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), rattelse_id))
    if r["objekt"] == "behandling" and r["falt"] in KOPPLANDE_FALT:
        # Kopplingarna bygger på de publicerade rättelserna (ADR-0003) och räknas om direkt.
        from .arenden import koppla

        koppla(conn)
    return las(conn, rattelse_id)


_LISTA = """
    SELECT r.*, s.organ, s.datum,
           (SELECT rubrik FROM behandling b WHERE b.sammantrade_id = r.sammantrade_id AND b.paragraf = r.paragraf
            ORDER BY ordning LIMIT 1) AS rubrik
    FROM rattelse r JOIN sammantrade s ON s.id = r.sammantrade_id
"""


def _ut(r: dict) -> dict:
    from .sources.harnosand import ORGAN

    organ = ORGAN.get(r["organ"])
    return {
        "id": r["id"],
        "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"],
                        "organ": {"id": r["organ"], "namn": organ.namn if organ else r["organ"]}},
        "objekt": r["objekt"], "paragraf": r["paragraf"], "votering": r["votering"], "namn": r["namn"] or None,
        "rubrik": r["rubrik"], "falt": r["falt"], "ursprungligt": r["ursprungligt"], "nytt": r["nytt"],
        "motivering": r["motivering"], "status": r["status"],
        "redaktor": r["redaktor"], "skapad": r["skapad"],
        "granskad_av": r["granskad_av"], "granskad": r["granskad"],
        "publicerad_av": r["publicerad_av"], "publicerad": r["publicerad"],
    }


def las(conn: psycopg.Connection, rattelse_id: int) -> dict:
    rad = conn.execute(f"{_LISTA} WHERE r.id = %s", (rattelse_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Rättelsen {rattelse_id} finns inte")
    return _ut(rad)


def lista(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"{_LISTA} WHERE (%(s)s::text IS NULL OR r.status = %(s)s) ORDER BY r.skapad DESC, r.id DESC",
        {"s": status},
    ).fetchall()
    return [_ut(r) for r in rader]


# Pålägg vid läsning

class Publicerade:
    """De publicerade rättelserna för ett eller flera sammanträden, nycklade per uppgift."""

    def __init__(self, conn: psycopg.Connection, sammantrade_ids: list[int]) -> None:
        self._rader: dict[tuple, dict] = {}
        if sammantrade_ids:
            for r in conn.execute(
                "SELECT * FROM rattelse WHERE status = 'publicerad' AND sammantrade_id = ANY(%s)", (sammantrade_ids,)
            ):
                self._rader[(r["sammantrade_id"], r["objekt"], r["paragraf"], r["votering"], r["namn"], r["falt"])] = r

    def _lagg_pa(self, mal: dict, nyckel: tuple, falt: str, ut_falt: str | None = None) -> None:
        r = self._rader.get((*nyckel, falt))
        if r is None:
            return
        ut_falt = ut_falt or falt
        mal.setdefault("rattelser", {})[ut_falt] = {
            "id": r["id"], "ursprungligt": mal.get(ut_falt), "nytt": r["nytt"], "motivering": r["motivering"],
            "publicerad": r["publicerad"],
        }
        mal[ut_falt] = r["nytt"]

    def behandling(self, sammantrade_id: int, b: dict) -> dict:
        nyckel = (sammantrade_id, "behandling", b["paragraf"], None, "")
        for falt in ("rubrik", "beslut", "diarienummer"):
            self._lagg_pa(b, nyckel, falt)
        # Typen räknas fram ur den (ev. rättade) rubriken och beslutet, och kan själv vara rättad.
        b["typ"] = klassa(b.get("rubrik"), b.get("beslut"))
        self._lagg_pa(b, nyckel, "typ")
        return b

    def motionarer(self, sammantrade_id: int, paragraf: int) -> dict | None:
        """Den publicerade rättelsen av motionärerna på behandlingen, eller None."""
        r = self._rader.get((sammantrade_id, "behandling", paragraf, None, "", "motionarer"))
        if r is None:
            return None
        return {"id": r["id"], "nytt": r["nytt"], "motivering": r["motivering"], "publicerad": r["publicerad"]}

    def rost(self, sammantrade_id: int, paragraf: int, votering: int, r: dict) -> dict:
        if r.get("namn"):
            for falt in FALT["rost"]:
                self._lagg_pa(r, (sammantrade_id, "rost", paragraf, votering, r["namn"]), falt)
        return r

    def person(self, sammantrade_id: int, p: dict) -> dict:
        self._lagg_pa(p, (sammantrade_id, "narvaro", None, None, p["namn"]), "parti")
        return p
