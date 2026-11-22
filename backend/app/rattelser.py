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

Varje rättelse anger var felet finns (#74): i protokollet (källan saknar eller anger fel uppgift)
eller i inläsningen (plattformen läste eller tolkade fel). Ett protokoll med publicerade rättelser
av fel i protokollet märks "Innehåller felaktigheter". Rättelser från före #74 saknar valet.

En granskad eller publicerad rättelse ändras inte på plats. Redaktören skapar en ny version, som går
igenom granskning och publicering som vanligt och ersätter den gamla när den publiceras. En utgivare kan
återkalla en publicerad rättelse direkt, med motivering, och då gäller tolkningen igen. De gamla
versionerna bevaras som historik (#74, del 3).
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
FELET_I = ("protokollet", "inlasningen")


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
        if m["falt"] == "diarienummer" and not rad["diarienummer"]:
            # Saknar protokollet diarienummer gäller kallelsens (#109).
            ur_kallelsen = conn.execute(
                "SELECT diarienummer FROM kallelse_diarienummer WHERE sammantrade_id = %s AND paragraf = %s",
                (m["sammantrade_id"], m["paragraf"]),
            ).fetchone()
            return ur_kallelsen["diarienummer"] if ur_kallelsen else rad["diarienummer"]
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


def _felet_i(data: dict) -> str:
    if data.get("felet_i") not in FELET_I:
        raise Ogiltig("Ange om felet finns i protokollet eller i inläsningen")
    return data["felet_i"]


def skapa(conn: psycopg.Connection, data: dict, redaktor: str) -> dict:
    m = _mal(data)
    ursprungligt = _ursprungligt(conn, m)
    nytt = _nytt(m["falt"], data.get("nytt"), conn)
    if nytt == ursprungligt:
        raise Ogiltig("Det nya värdet är samma som tolkningen")
    rid = conn.execute(
        """
        INSERT INTO rattelse (sammantrade_id, objekt, paragraf, votering, namn, falt, ursprungligt, nytt,
                              motivering, felet_i, status, redaktor)
        VALUES (%(sammantrade_id)s, %(objekt)s, %(paragraf)s, %(votering)s, %(namn)s, %(falt)s, %(u)s, %(n)s,
                %(mot)s, %(felet_i)s, 'utkast', %(red)s)
        RETURNING id
        """,
        m | {"u": Jsonb(ursprungligt), "n": Jsonb(nytt), "mot": _motivering(data), "felet_i": _felet_i(data),
             "red": redaktor},
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
    felet_i = _felet_i(data) if "felet_i" in data else r["felet_i"]
    conn.execute("UPDATE rattelse SET nytt = %s, motivering = %s, felet_i = %s WHERE id = %s",
                 (Jsonb(nytt), motivering, felet_i, rattelse_id))
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
    if r["ersatter_id"] is not None:
        # Versionen den ersätter, om den inte hann publiceras.
        conn.execute("UPDATE rattelse SET status = 'ersatt' WHERE id = %s AND status IN ('utkast', 'granskad')",
                     (r["ersatter_id"],))
    _rakna_om(conn, r)
    return las(conn, rattelse_id)


def ny_version(conn: psycopg.Connection, rattelse_id: int, data: dict, redaktor: str, roller: set[str]) -> dict:
    """En ny version av en granskad eller publicerad rättelse, som utkast. Den ersätter den gamla när den publiceras."""
    r = _hamta(conn, rattelse_id)
    if "redaktor" not in roller and r["falt"] != "motionarer":
        raise EjTillatet("Kräver rollen redaktör")
    if r["status"] == "utkast":
        raise Konflikt("Ett utkast ändras direkt, utan ny version")
    if r["status"] not in ("granskad", "publicerad"):
        raise Konflikt(f"Rättelsen är {r['status']} och kan inte få en ny version")
    if conn.execute("SELECT 1 FROM rattelse WHERE ersatter_id = %s AND status IN ('utkast', 'granskad')",
                    (rattelse_id,)).fetchone():
        raise Konflikt("Det finns redan en ny version som väntar på granskning")
    m = {k: r[k] for k in ("sammantrade_id", "objekt", "paragraf", "votering", "namn", "falt")}
    ursprungligt = _ursprungligt(conn, m)
    nytt = _nytt(r["falt"], data.get("nytt", r["nytt"]), conn)
    if nytt == ursprungligt:
        raise Ogiltig("Det nya värdet är samma som tolkningen. Återkalla rättelsen i stället")
    felet_i = _felet_i(data if "felet_i" in data else {"felet_i": r["felet_i"]})
    rid = conn.execute(
        """
        INSERT INTO rattelse (sammantrade_id, objekt, paragraf, votering, namn, falt, ursprungligt, nytt,
                              motivering, felet_i, status, redaktor, ersatter_id)
        VALUES (%(sammantrade_id)s, %(objekt)s, %(paragraf)s, %(votering)s, %(namn)s, %(falt)s, %(u)s, %(n)s,
                %(mot)s, %(felet_i)s, 'utkast', %(red)s, %(ersatter)s)
        RETURNING id
        """,
        m | {"u": Jsonb(ursprungligt), "n": Jsonb(nytt), "mot": _motivering(data), "felet_i": felet_i,
             "red": redaktor, "ersatter": rattelse_id},
    ).fetchone()["id"]
    return las(conn, rid)


def aterkalla(conn: psycopg.Connection, rattelse_id: int, data: dict, utgivare: str) -> dict:
    """En utgivare återkallar en publicerad rättelse direkt. Tolkningen gäller igen."""
    r = _hamta(conn, rattelse_id)
    if r["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad rättelse kan återkallas, den här är {r['status']}")
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför rättelsen återkallas")
    conn.execute(
        "UPDATE rattelse SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, aterkallelse = %s WHERE id = %s",
        (utgivare, datetime.now(timezone.utc), motivering, rattelse_id),
    )
    _rakna_om(conn, r)
    return las(conn, rattelse_id)


def _rakna_om(conn: psycopg.Connection, r: dict) -> None:
    """Det som bygger på de publicerade rättelserna räknas om när en rättelse publiceras eller återkallas."""
    if r["objekt"] == "behandling" and r["falt"] in KOPPLANDE_FALT:
        # Kopplingarna bygger på de publicerade rättelserna (ADR-0003) och räknas om direkt.
        from .arenden import koppla

        koppla(conn)
    if r["objekt"] == "behandling" and r["falt"] == "beslut":
        # Ett rättat beslut om sammanträdestiderna kan ändra planen ur besluten (#99).
        from . import kalender, sammantradesplan

        sammantradesplan.lagra_beslut(conn, kalender.idag())


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
        "motivering": r["motivering"], "felet_i": r["felet_i"], "status": r["status"],
        "redaktor": r["redaktor"], "skapad": r["skapad"],
        "granskad_av": r["granskad_av"], "granskad": r["granskad"],
        "publicerad_av": r["publicerad_av"], "publicerad": r["publicerad"],
        "ersatter_id": r["ersatter_id"],
        "aterkallad_av": r["aterkallad_av"], "aterkallad": r["aterkallad"], "aterkallelse": r["aterkallelse"],
    }


def _med_historik(rader: list[dict], alla: dict[int, dict]) -> list[dict]:
    """Varje rättelse med de tidigare versionerna den ersätter, senaste först."""
    ut = []
    for r in rader:
        tidigare, fore = [], r["ersatter_id"]
        while fore is not None and fore in alla:
            tidigare.append(_ut(alla[fore]))
            fore = alla[fore]["ersatter_id"]
        ut.append(_ut(r) | {"tidigare": tidigare})
    return ut


def las(conn: psycopg.Connection, rattelse_id: int) -> dict:
    rad = conn.execute(f"{_LISTA} WHERE r.id = %s", (rattelse_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Rättelsen {rattelse_id} finns inte")
    kedja = conn.execute(
        f"""
        WITH RECURSIVE k AS (SELECT id, ersatter_id FROM rattelse WHERE id = %s
                             UNION SELECT r.id, r.ersatter_id FROM rattelse r JOIN k ON r.id = k.ersatter_id)
        {_LISTA} WHERE r.id IN (SELECT id FROM k)
        """,
        (rattelse_id,),
    ).fetchall()
    return _med_historik([rad], {r["id"]: r for r in kedja})[0]


def lista(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    alla = conn.execute(f"{_LISTA} ORDER BY r.skapad DESC, r.id DESC").fetchall()
    return _med_historik([r for r in alla if status is None or r["status"] == status], {r["id"]: r for r in alla})


# Pålägg vid läsning

class Publicerade:
    """De publicerade rättelserna för ett eller flera sammanträden, nycklade per uppgift."""

    def __init__(self, conn: psycopg.Connection, sammantrade_ids: list[int]) -> None:
        self._rader: dict[tuple, dict] = {}
        # Tidigare publicerade versioner av samma uppgift, som läsaren kan se som historik (#74).
        self._tidigare: dict[tuple, list[dict]] = {}
        if sammantrade_ids:
            for r in conn.execute(
                "SELECT * FROM rattelse WHERE status IN ('publicerad', 'ersatt') AND publicerad IS NOT NULL "
                "AND sammantrade_id = ANY(%s) ORDER BY publicerad DESC", (sammantrade_ids,)
            ):
                nyckel = (r["sammantrade_id"], r["objekt"], r["paragraf"], r["votering"], r["namn"], r["falt"])
                if r["status"] == "publicerad":
                    self._rader[nyckel] = r
                else:
                    self._tidigare.setdefault(nyckel, []).append(
                        {"nytt": r["nytt"], "motivering": r["motivering"], "felet_i": r["felet_i"],
                         "publicerad": r["publicerad"]})

    def _lagg_pa(self, mal: dict, nyckel: tuple, falt: str, ut_falt: str | None = None) -> None:
        r = self._rader.get((*nyckel, falt))
        if r is None:
            return
        ut_falt = ut_falt or falt
        mal.setdefault("rattelser", {})[ut_falt] = {
            "id": r["id"], "ursprungligt": mal.get(ut_falt), "nytt": r["nytt"], "motivering": r["motivering"],
            "felet_i": r["felet_i"], "publicerad": r["publicerad"],
            "tidigare": self._tidigare.get((*nyckel, falt), []),
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
