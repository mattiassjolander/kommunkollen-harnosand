"""Gemensamma planförutsättningar per budgetår (#58).

Alla budgetförslag för ett budgetår utgår från samma planförutsättningar. De läses in från
`data/budgetforslag/planforutsattningar.xlsx`, en flik per budgetår (fliken heter året), med
kolumnerna A tabell, B post, C belopp i mnkr och D källa (förslag och sida, t.ex. "L s. 8").
Rubrikrader, rader med formler (resultatprocent, kontrollsummor), tomma belopp och anteckningarna
längst ner läses inte. Övriga kolumner och flikar som inte heter ett år hoppas över.

Planförutsättningarna går utkast → granskad → publicerad (ADR-0002). Ingen godkänner det hen själv
läst in. Förslagens förändringar och beräknade resultat visas publikt först när årets
planförutsättningar är publicerade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

FILNAMN = "planforutsattningar.xlsx"
# Kolumn A i filen → nyckeln i uppgifterna.
TABELLER = {"Resultatbudget": "resultatbudget", "Nämnder": "namnder", "Investeringar": "investeringar",
            "Balansbudget": "balansbudget", "Kassaflöde": "kassaflode"}
SKATTESATS = "Skattesats (%)"
SKATTEINTAKTER = "Skatteintäkter"
BIDRAG = "Generella bidrag och utjämning"
RESULTAT = "Årets resultat"
TOTALT = "Totalt"
_KALLA = re.compile(r"(?P<nyckel>[A-Za-zÅÄÖåäö+]+) s\. (?P<sida>\d+)(?:[–-]\d+)?")


class Ogiltig(ValueError):
    """Uppgifterna är inte giltiga."""


class EjTillatet(PermissionError):
    """Användaren får inte göra det här."""


class Konflikt(Exception):
    """Uppgifterna har inte den status som steget kräver."""


# Inläsningen


@dataclass
class Planforutsattning:
    budgetar: int
    filnamn: str
    uppgifter: dict


def _rad(ar: str, n: int, a: Any, b: Any, c: Any, d: Any) -> tuple[str, dict] | None:
    """(tabell, {post, mnkr, kalla}) för en rad med ett belopp, annars None."""
    if not isinstance(a, str) or b is None or a.strip() == "Tabell":
        return None
    tabell = TABELLER.get(a.strip())
    if tabell is None:
        if c is None:
            return None  # rubrik eller anteckning
        raise Ogiltig(f"flik {ar}, rad {n}: okänd tabell {a.strip()!r}, ska vara {', '.join(TABELLER)}")
    post = str(b).strip()
    if c is None or (isinstance(c, str) and (c.startswith("=") or not c.strip())):
        return None  # tomt belopp eller formel
    if post.startswith("Resultat i %"):
        return None  # räknas fram
    if isinstance(c, bool) or not isinstance(c, (int, float)):
        raise Ogiltig(f"flik {ar}, rad {n} ({post}): beloppet i kolumn C ska vara ett tal, inte {c!r}")
    return tabell, {"post": post, "mnkr": float(c), "kalla": str(d).strip() if d is not None else ""}


def las_flik(ar: str, rader: list[tuple]) -> dict:
    """Uppgifterna i en flik, rad för rad som (A, B, C, D). Ogiltig vid fel."""
    tabeller: dict[str, list[dict]] = {t: [] for t in TABELLER.values()}
    skattesats = None
    for n, (a, b, c, d, *_) in enumerate((*r, None, None, None, None) for r in rader):
        r = _rad(ar, n + 1, a, b, c, d)
        if r is None:
            continue
        tabell, post = r
        if tabell == "resultatbudget" and post["post"] == SKATTESATS:
            if not 10 <= post["mnkr"] <= 40:
                raise Ogiltig(f"flik {ar}, rad {n + 1}: skattesatsen ska anges i procent, t.ex. 23.34")
            skattesats = {"procent": post["mnkr"], "kalla": post["kalla"]}
            continue
        if any(p["post"] == post["post"] for p in tabeller[tabell]):
            raise Ogiltig(f"flik {ar}, rad {n + 1}: {post['post']} står flera gånger i {tabell}")
        tabeller[tabell].append(post)
    if skattesats is None:
        raise Ogiltig(f"flik {ar}: raden {SKATTESATS!r} i Resultatbudget saknas")
    poster = {p["post"] for p in tabeller["resultatbudget"]}
    for kravd in (SKATTEINTAKTER, BIDRAG, RESULTAT):
        if kravd not in poster:
            raise Ogiltig(f"flik {ar}: raden {kravd!r} i Resultatbudget saknas")
    if not [p for p in tabeller["namnder"] if p["post"] != TOTALT]:
        raise Ogiltig(f"flik {ar}: tabellen Nämnder saknar ramar")
    return {"skattesats": skattesats, "tabeller": tabeller}


def las_excel(fil: Path) -> list[Planforutsattning]:
    """Planförutsättningarna i filen, en per flik som heter ett år. Ogiltig med flik och rad vid fel."""
    import openpyxl

    try:
        bok = openpyxl.load_workbook(fil, read_only=True)  # formler läses som text, inte som värden
    except Exception as e:  # noqa: BLE001 – openpyxl har inget eget feltyp för en trasig fil
        raise Ogiltig(f"{fil.name} kan inte läsas som en Excelfil: {e}") from e
    ut = []
    for flik in bok.worksheets:
        namn = str(flik.title).strip()
        if not re.fullmatch(r"\d{4}", namn):
            continue
        rader = [tuple(c for c in r[:4]) for r in flik.iter_rows(values_only=True)]
        try:
            ut.append(Planforutsattning(int(namn), fil.name, las_flik(namn, rader)))
        except Ogiltig as e:
            raise Ogiltig(f"{fil.name}: {e}") from e
    bok.close()
    if not ut:
        raise Ogiltig(f"{fil.name}: ingen flik heter ett budgetår, t.ex. 2027")
    return ut


def las_in(conn: psycopg.Connection, lista_: list[Planforutsattning], redaktor: str, nu: datetime) -> dict:
    """Skapar eller uppdaterar utkast. Publicerade planförutsättningar ändras aldrig, utan får ett nytt utkast.

    Skriver i transaktionen men committar inte, så att inläsningen av förslagen hör till samma transaktion."""
    antal = {"nya": 0, "uppdaterade": 0, "oforandrade": 0}
    for p in lista_:
        senaste = conn.execute(
            "SELECT id, status, uppgifter FROM planforutsattningar WHERE budgetar = %s AND status <> 'ersatt' "
            "ORDER BY id DESC LIMIT 1", (p.budgetar,),
        ).fetchone()
        if senaste and senaste["uppgifter"] == p.uppgifter:
            antal["oforandrade"] += 1
            continue
        varden = {"b": p.budgetar, "fil": p.filnamn, "u": Jsonb(p.uppgifter), "r": [redaktor], "nu": nu}
        if senaste and senaste["status"] in ("utkast", "granskad"):
            conn.execute(
                "UPDATE planforutsattningar SET filnamn = %(fil)s, uppgifter = %(u)s, status = 'utkast', redaktorer = %(r)s, "
                "andrad = %(nu)s, granskad_av = NULL, granskad = NULL WHERE id = %(id)s", {**varden, "id": senaste["id"]},
            )
            antal["uppdaterade"] += 1
        else:
            conn.execute(
                "INSERT INTO planforutsattningar (budgetar, filnamn, uppgifter, status, redaktorer, skapad, andrad) "
                "VALUES (%(b)s, %(fil)s, %(u)s, 'utkast', %(r)s, %(nu)s, %(nu)s)", varden,
            )
            antal["nya"] += 1
    return antal


# Det förslagen räknar med


def nyckeltal(u: dict) -> dict:
    """Det budgetförslagen räknas mot: skattesats, skatteintäkter, bidrag, resultat och ram per organ."""
    res = {p["post"]: p["mnkr"] for p in u["tabeller"]["resultatbudget"]}
    return {
        "skattesats": u["skattesats"]["procent"],
        "skatteintakter": res[SKATTEINTAKTER],
        "bidrag": res[BIDRAG],
        "resultat": res[RESULTAT],
        "ramar": {p["post"]: p["mnkr"] for p in u["tabeller"]["namnder"] if p["post"] != TOTALT},
    }


def aktuella(conn: psycopg.Connection, publicerade: bool) -> dict[int, dict]:
    """Uppgifterna per budgetår: de publicerade, eller för redaktionen de senaste (utkast före publicerade)."""
    rader = conn.execute(
        "SELECT DISTINCT ON (budgetar) budgetar, uppgifter FROM planforutsattningar "
        "WHERE status = 'publicerad' OR (NOT %s AND status IN ('utkast', 'granskad')) ORDER BY budgetar, id DESC",
        (publicerade,),
    ).fetchall()
    return {r["budgetar"]: r["uppgifter"] for r in rader}


# Kontrollsummor: (tabell, posten som anges, posterna den ska vara summan av). Saknade termer räknas som 0.
_KONTROLLER = [
    ("resultatbudget", "Verksamhetens nettokostnader", ["Verksamhetens intäkter", "Verksamhetens kostnader", "Avskrivningar"]),
    ("resultatbudget", RESULTAT, ["Verksamhetens nettokostnader", SKATTEINTAKTER, BIDRAG, "Finansnetto"]),
    ("namnder", TOTALT, None),
    ("investeringar", TOTALT, None),
    ("balansbudget", "Summa tillgångar", ["Anläggningstillgångar", "Omsättningstillgångar"]),
    ("balansbudget", "Summa skulder", ["Långfristiga skulder", "Kortfristiga skulder"]),
    ("balansbudget", "Summa eget kapital, avsättningar och skulder", ["Eget kapital", "Avsättningar", "Summa skulder"]),
    ("kassaflode", "Totalt kassaflöde", ["Avskrivningar", "Nettoupplåning inkl. amortering", "Investeringar",
                                         "Övrigt kassaflöde", RESULTAT]),
    ("kassaflode", "Likvida medel vid årets slut", ["Likvida medel vid årets början", "Totalt kassaflöde"]),
]


def kontroller(u: dict) -> list[dict]:
    """Kontrollsummorna: summan av posterna mot det angivna beloppet. Differens 0 betyder att tabellen går ihop."""
    ut = []
    for tabell, post, termer in _KONTROLLER:
        poster = {p["post"]: p["mnkr"] for p in u["tabeller"][tabell]}
        if post not in poster:
            continue
        termer = termer if termer is not None else [p for p in poster if p != TOTALT]
        summa = round(sum(poster.get(t, 0.0) for t in termer), 3)
        ut.append({"tabell": tabell, "post": post, "summa": summa, "angivet": poster[post],
                   "differens": round(poster[post] - summa, 1)})
    res = {p["post"]: p["mnkr"] for p in u["tabeller"]["resultatbudget"]}
    if res.get(SKATTEINTAKTER, 0) + res.get(BIDRAG, 0):
        ut.append({"tabell": "resultatbudget", "post": "Resultat i % av skatter och bidrag",
                   "procent": round(res[RESULTAT] / (res[SKATTEINTAKTER] + res[BIDRAG]) * 100, 2)})
    return ut


def kallor(text: str, forslag: dict[str, int]) -> list[dict]:
    """Källan uppdelad i delar, med förslag och sida när delen är "X s. N" och förslaget X finns."""
    ut = []
    for del_ in (d.strip() for d in text.split(",")):
        if not del_:
            continue
        m = _KALLA.fullmatch(del_)
        if m and m["nyckel"] in forslag:
            ut.append({"text": del_, "forslag": forslag[m["nyckel"]], "sida": int(m["sida"])})
        else:
            ut.append({"text": del_})
    return ut


# Granskning och publicering

_KOLUMNER = ("id, budgetar, filnamn, uppgifter, status, redaktorer, andrad, granskad_av, granskad, publicerad_av, "
             "publicerad")


def _forslag(conn: psycopg.Connection, budgetar: int, publicerade: bool) -> dict[str, int]:
    """Förslagen för budgetåret, nyckel → id, för länkarna i källorna."""
    rader = conn.execute(
        "SELECT DISTINCT ON (nyckel) nyckel, id FROM budgetforslag WHERE budgetar = %s "
        "AND (status = 'publicerad' OR (NOT %s AND status IN ('utkast', 'granskad'))) "
        "ORDER BY nyckel, (status = 'publicerad') DESC, id DESC", (budgetar, publicerade),
    ).fetchall()
    return {r["nyckel"]: r["id"] for r in rader}


def _ut(conn: psycopg.Connection, r: dict, redaktion: bool) -> dict:
    lankar = _forslag(conn, r["budgetar"], publicerade=not redaktion)
    u = r["uppgifter"]
    tabeller = {t: [{**p, "kallor": kallor(p["kalla"], lankar)} for p in poster] for t, poster in u["tabeller"].items()}
    ut = {"id": r["id"], "budgetar": r["budgetar"], "status": r["status"], "filnamn": r["filnamn"],
          "skattesats": {**u["skattesats"], "kallor": kallor(u["skattesats"]["kalla"], lankar)},
          "tabeller": tabeller, "kontroller": kontroller(u),
          "publicerad": r["publicerad"].isoformat() if r["publicerad"] else None}
    if redaktion:
        ut |= {"redaktorer": r["redaktorer"], "granskad_av": r["granskad_av"], "publicerad_av": r["publicerad_av"],
               "andrad": r["andrad"].isoformat(), "granskad": r["granskad"].isoformat() if r["granskad"] else None}
    return ut


def _hamta(conn: psycopg.Connection, pf_id: int) -> dict:
    r = conn.execute(f"SELECT {_KOLUMNER} FROM planforutsattningar WHERE id = %s", (pf_id,)).fetchone()
    if r is None:
        raise LookupError(f"Planförutsättningarna {pf_id} finns inte")
    return r


def lista(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"SELECT {_KOLUMNER} FROM planforutsattningar WHERE (%(s)s::text IS NULL OR status = %(s)s) "
        "ORDER BY budgetar DESC, id DESC", {"s": status},
    ).fetchall()
    return [_ut(conn, r, redaktion=True) for r in rader]


def las(conn: psycopg.Connection, pf_id: int) -> dict:
    return _ut(conn, _hamta(conn, pf_id), redaktion=True)


def publicerad(conn: psycopg.Connection, budgetar: int) -> dict | None:
    r = conn.execute(f"SELECT {_KOLUMNER} FROM planforutsattningar WHERE budgetar = %s AND status = 'publicerad'",
                     (budgetar,)).fetchone()
    return _ut(conn, r, redaktion=False) if r else None


def _godkann(conn: psycopg.Connection, pf_id: int, utgivare: str, fran: str) -> dict:
    r = _hamta(conn, pf_id)
    if utgivare in r["redaktorer"]:
        raise EjTillatet("Ingen godkänner planförutsättningar som hen själv läst in")
    if r["status"] != fran:
        raise Konflikt(f"Planförutsättningarna är {r['status']}, inte {fran}")
    return r


def granska(conn: psycopg.Connection, pf_id: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, pf_id, utgivare, "utkast")
    conn.execute("UPDATE planforutsattningar SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, nu, pf_id))
    conn.commit()
    return las(conn, pf_id)


def publicera(conn: psycopg.Connection, pf_id: int, utgivare: str, nu: datetime) -> dict:
    r = _godkann(conn, pf_id, utgivare, "granskad")
    conn.execute("UPDATE planforutsattningar SET status = 'ersatt' WHERE status = 'publicerad' AND budgetar = %s",
                 (r["budgetar"],))
    conn.execute("UPDATE planforutsattningar SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, nu, pf_id))
    conn.commit()
    return las(conn, pf_id)
