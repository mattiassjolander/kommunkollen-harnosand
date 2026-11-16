"""Partiernas budgetförslag (#48, kravspec 17A).

Förslagen läggs lokalt i `data/budgetforslag/<budgetår>/` med filnamnet efter partiförkortningarna
bakom förslaget (`S.pdf`, `L+M.pdf`, `S-tillagg.pdf`). Budgetåret är året budgeten gäller. Bredvid
filerna beskriver `budget.json` varje förslag i budgetmodellen: skattesats, budgeterat resultat och
ram per nämnd, för budgetåret och planåren, med sidhänvisning för varje siffra. Filen tas fram en
gång per år genom att läsa dokumenten (de har olika tabelluppläggning och en del är inskannade).

`python -m app.budgetforslag MAPP --redaktor EPOST` läser mappen och skapar ett utkast per förslag.
Med `-` som mapp läses en tar-ström från stdin, så att mappen kan skickas till servern:

    tar -C data -c budgetforslag | ssh server 'docker compose exec -T backend
        /app/.venv/bin/python -m app.budgetforslag - --redaktor EPOST'

Ett utkast rättas av en redaktör och publiceras av en utgivare (utkast → granskad → publicerad).
Ingen godkänner ett förslag som hen själv läst in eller ändrat. Läsaren ser bara publicerade
förslag, bredvid varandra och bredvid den antagna budgeten för året när den finns.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

FILTYPER = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
BESKRIVNING = "budget.json"
_PARTI = re.compile(r"[A-ZÅÄÖ]{1,4}")
_NYCKEL = re.compile(r"(?P<partier>[A-Za-zÅÄÖåäö]+(?:\+[A-ZÅÄÖ]{1,4})*)(?:-(?P<variant>[\w-]+))?")


class Ogiltig(ValueError):
    """Uppgifterna är inte giltiga."""


class EjTillatet(PermissionError):
    """Användaren får inte göra det här med förslaget."""


class Konflikt(Exception):
    """Förslaget har inte den status som steget kräver."""


# Uppgifterna


def _tal(v: Any, falt: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Ogiltig(f"{falt} ska vara ett tal")
    return float(v)


def _sida(v: Any, falt: str, sidor: bool) -> dict:
    """{"sida": n} för en PDF. Ett Word-dokument har inga fasta sidor, så där anges ingen."""
    if not sidor:
        if v is not None:
            raise Ogiltig(f"{falt}: ett Word-dokument har inga fasta sidor, ange ingen sida")
        return {}
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise Ogiltig(f"{falt}: sidan ska vara ett heltal från 1")
    return {"sida": v}


def _ar(v: Any, budgetar: int, falt: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not budgetar - 1 <= v <= budgetar + 4:
        raise Ogiltig(f"{falt}: året ska ligga mellan {budgetar - 1} och {budgetar + 4}")
    return v


def _valfria(post: dict, falt: str, namn: tuple[str, ...]) -> dict:
    """De av fälten `namn` som finns, som tal. Minst ett krävs."""
    ut = {n: _tal(post[n], f"{falt} ({n})") for n in namn if post.get(n) is not None}
    if not ut:
        raise Ogiltig(f"{falt}: ange {' eller '.join(namn)}")
    return ut


def uppgifter(data: Any, budgetar: int, sidor: bool = True) -> dict:
    """Validerar och normaliserar uppgifterna i budgetmodellen. Ogiltig vid fel.

    Uppgifterna är det som står i dokumentet, med sida när dokumentet har fasta sidor (`sidor`, PDF):

    - `skattesats`: {procent} och/eller {forandring} i procentenheter (−0,10 för "10 öre lägre"),
    - `resultat`: per år, {mnkr} och/eller {procent} av skatter och statsbidrag,
    - `ramar`: per nämnd och år, {mnkr} och/eller {forandring} i mnkr,
    - `utgangslage`: vad förändringarna räknas från, t.ex. "Planförutsättningar 2027".
    """
    if not isinstance(data, dict):
        raise Ogiltig("Uppgifterna ska vara ett objekt")
    okanda = set(data) - {"skattesats", "resultat", "ramar", "utgangslage"}
    if okanda:
        raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")
    skatt = data.get("skattesats")
    if skatt is not None:
        if not isinstance(skatt, dict):
            raise Ogiltig("skattesats ska vara {procent, sida} eller {forandring, sida}")
        skatt = {**_valfria(skatt, "skattesats", ("procent", "forandring")), **_sida(skatt.get("sida"), "skattesats", sidor)}
        if "procent" in skatt and not 10 <= skatt["procent"] <= 40:
            raise Ogiltig("skattesatsen ska anges i procent, t.ex. 23.34")
    resultat = []
    for i, r in enumerate(data.get("resultat") or []):
        f = f"resultat {i + 1}"
        resultat.append({"ar": _ar(r.get("ar"), budgetar, f), **_valfria(r, f, ("mnkr", "procent")),
                         **_sida(r.get("sida"), f, sidor)})
    ramar = []
    for i, r in enumerate(data.get("ramar") or []):
        f = f"ram {i + 1}"
        organ = r.get("organ")
        if not isinstance(organ, str) or not organ.strip():
            raise Ogiltig(f"{f}: organ saknas")
        ramar.append({"organ": organ.strip(), "ar": _ar(r.get("ar"), budgetar, f), **_valfria(r, f, ("mnkr", "forandring")),
                      **_sida(r.get("sida"), f, sidor)})
    if len({r["ar"] for r in resultat}) != len(resultat):
        raise Ogiltig("Resultatet står flera gånger för samma år")
    if len({(r["organ"], r["ar"]) for r in ramar}) != len(ramar):
        raise Ogiltig("Samma nämnd står flera gånger för samma år")
    utgangslage = data.get("utgangslage")
    if utgangslage is not None and not isinstance(utgangslage, str):
        raise Ogiltig("utgangslage ska vara en text")
    return {"skattesats": skatt, "resultat": sorted(resultat, key=lambda r: r["ar"]),
            "ramar": sorted(ramar, key=lambda r: r["ar"]),
            "utgangslage": (utgangslage or "").strip() or None}


def _partier(v: Any) -> list[str]:
    if not isinstance(v, list) or not v or not all(isinstance(p, str) and _PARTI.fullmatch(p) for p in v):
        raise Ogiltig("partier ska vara en lista med partiförkortningar, t.ex. [\"L\", \"M\"]")
    return sorted(set(v))


# Inläsning


@dataclass
class Forslag:
    budgetar: int
    nyckel: str
    filnamn: str
    innehall: bytes
    partier: list[str]
    titel: str
    typ: str
    antagen: bool
    uppgifter: dict
    anmarkning: str

    @property
    def inlast(self) -> dict:
        return {"sha256": hashlib.sha256(self.innehall).hexdigest(), "partier": self.partier, "titel": self.titel,
                "typ": self.typ, "antagen": self.antagen, "uppgifter": self.uppgifter, "anmarkning": self.anmarkning}


def las_mapp(rot: Path) -> list[Forslag]:
    """Förslagen i `rot/<budgetår>/`. Ogiltig med fil och fel när något inte stämmer."""
    forslag = []
    for katalog in sorted(p for p in rot.iterdir() if p.is_dir()):
        if not re.fullmatch(r"\d{4}", katalog.name):
            continue
        budgetar = int(katalog.name)
        beskrivning = katalog / BESKRIVNING
        poster = json.loads(beskrivning.read_text(encoding="utf-8")).get("forslag", {}) if beskrivning.exists() else {}
        filer = sorted(p for p in katalog.iterdir() if p.suffix.lower() in FILTYPER)
        for namn in set(poster) - {f.name for f in filer}:
            raise Ogiltig(f"{katalog.name}/{BESKRIVNING}: filen {namn} finns inte")
        for fil in filer:
            m = _NYCKEL.fullmatch(fil.stem)
            if not m:
                raise Ogiltig(f"{katalog.name}/{fil.name}: filnamnet ska vara partiförkortningarna, t.ex. L+M.pdf")
            post = poster.get(fil.name)
            sidor = fil.suffix.lower() == ".pdf"
            try:
                if post is None:
                    partier = m["partier"].split("+")
                    forslag.append(Forslag(budgetar, fil.stem, fil.name, fil.read_bytes(), _partier(partier),
                                           f"Budgetförslag {budgetar}", "tillagg" if m["variant"] else "budget", False,
                                           uppgifter({}, budgetar, sidor), f"Uppgifter saknas i {BESKRIVNING}."))
                    continue
                okanda = set(post) - {"partier", "titel", "typ", "antagen", "anmarkning", "skattesats", "resultat",
                                      "ramar", "utgangslage"}
                if okanda:
                    raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")
                partier = post.get("partier") or m["partier"].split("+")
                typ = post.get("typ", "tillagg" if m["variant"] else "budget")
                if typ not in ("budget", "tillagg"):
                    raise Ogiltig("typ ska vara budget eller tillagg")
                forslag.append(Forslag(
                    budgetar, fil.stem, fil.name, fil.read_bytes(), _partier(partier),
                    str(post.get("titel") or f"Budgetförslag {budgetar}"), typ, bool(post.get("antagen", False)),
                    uppgifter({k: post[k] for k in ("skattesats", "resultat", "ramar", "utgangslage") if k in post}, budgetar, sidor),
                    str(post.get("anmarkning") or ""),
                ))
            except Ogiltig as e:
                raise Ogiltig(f"{katalog.name}/{fil.name}: {e}") from e
    return forslag


def las_in(conn: psycopg.Connection, forslag: list[Forslag], redaktor: str, nu: datetime) -> dict:
    """Skapar eller uppdaterar utkast. Ett publicerat förslag ändras aldrig, utan får ett nytt utkast."""
    antal = {"nya": 0, "uppdaterade": 0, "oforandrade": 0}
    for f in forslag:
        senaste = conn.execute(
            "SELECT id, status, inlast FROM budgetforslag WHERE budgetar = %s AND nyckel = %s AND status <> 'ersatt' "
            "ORDER BY id DESC LIMIT 1", (f.budgetar, f.nyckel),
        ).fetchone()
        if senaste and senaste["inlast"] == f.inlast:
            antal["oforandrade"] += 1
            continue
        varden = {"b": f.budgetar, "n": f.nyckel, "p": f.partier, "t": f.titel, "typ": f.typ, "a": f.antagen,
                  "fil": f.filnamn, "sha": f.inlast["sha256"], "o": f.innehall, "i": Jsonb(f.inlast),
                  "u": Jsonb(f.uppgifter), "anm": f.anmarkning, "r": [redaktor], "nu": nu}
        if senaste and senaste["status"] in ("utkast", "granskad"):
            conn.execute(
                """
                UPDATE budgetforslag SET partier = %(p)s, titel = %(t)s, typ = %(typ)s, antagen = %(a)s, filnamn = %(fil)s,
                  sha256 = %(sha)s, original = %(o)s, inlast = %(i)s, uppgifter = %(u)s, anmarkning = %(anm)s,
                  status = 'utkast', redaktorer = %(r)s, andrad = %(nu)s, granskad_av = NULL, granskad = NULL
                WHERE id = %(id)s
                """, {**varden, "id": senaste["id"]},
            )
            antal["uppdaterade"] += 1
        else:
            conn.execute(
                """
                INSERT INTO budgetforslag (budgetar, nyckel, partier, titel, typ, antagen, filnamn, sha256, original, inlast,
                  uppgifter, anmarkning, status, redaktorer, skapad, andrad)
                VALUES (%(b)s, %(n)s, %(p)s, %(t)s, %(typ)s, %(a)s, %(fil)s, %(sha)s, %(o)s, %(i)s, %(u)s, %(anm)s,
                  'utkast', %(r)s, %(nu)s, %(nu)s)
                """, varden,
            )
            antal["nya"] += 1
    conn.commit()
    return antal


# Redigering och publicering

_KOLUMNER = ("id, budgetar, nyckel, partier, titel, typ, antagen, filnamn, sha256, uppgifter, anmarkning, status, "
             "redaktorer, skapad, andrad, granskad_av, granskad, publicerad_av, publicerad, inlast")


def _ut(r: dict, redaktion: bool = False) -> dict:
    ut = {k: r[k] for k in ("id", "budgetar", "nyckel", "partier", "titel", "typ", "antagen", "filnamn", "anmarkning",
                            "status", "uppgifter")}
    ut["original"] = f"/api/budgetforslag/{r['id']}/original"
    ut["publicerad"] = r["publicerad"].isoformat() if r["publicerad"] else None
    if redaktion:
        ut |= {"redaktorer": r["redaktorer"], "granskad_av": r["granskad_av"], "publicerad_av": r["publicerad_av"],
               "andrad": r["andrad"].isoformat(), "inlast": r["inlast"]["uppgifter"],
               "granskad": r["granskad"].isoformat() if r["granskad"] else None}
    return ut


def _hamta(conn: psycopg.Connection, forslag_id: int) -> dict:
    r = conn.execute(f"SELECT {_KOLUMNER} FROM budgetforslag WHERE id = %s", (forslag_id,)).fetchone()
    if r is None:
        raise LookupError(f"Budgetförslaget {forslag_id} finns inte")
    return r


def lista(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"SELECT {_KOLUMNER} FROM budgetforslag WHERE (%(s)s::text IS NULL OR status = %(s)s) "
        "ORDER BY budgetar DESC, antagen DESC, nyckel, id DESC", {"s": status},
    ).fetchall()
    return [_ut(r, redaktion=True) for r in rader]


def las(conn: psycopg.Connection, forslag_id: int) -> dict:
    return _ut(_hamta(conn, forslag_id), redaktion=True)


def andra(conn: psycopg.Connection, forslag_id: int, data: dict, redaktor: str, nu: datetime) -> dict:
    """Ändrar ett utkast: {uppgifter?, partier?, titel?, antagen?, anmarkning?}. Ett granskat förslag blir utkast igen."""
    r = _hamta(conn, forslag_id)
    if r["status"] not in ("utkast", "granskad"):
        raise Konflikt(f"Förslaget är {r['status']} och kan inte ändras")
    okanda = set(data) - {"uppgifter", "partier", "titel", "antagen", "anmarkning"}
    if okanda:
        raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")
    nytt = {
        "uppgifter": uppgifter(data["uppgifter"], r["budgetar"], r["filnamn"].lower().endswith(".pdf")) if "uppgifter" in data else r["uppgifter"],
        "partier": _partier(data["partier"]) if "partier" in data else r["partier"],
        "titel": str(data.get("titel", r["titel"])).strip() or r["titel"],
        "antagen": bool(data.get("antagen", r["antagen"])),
        "anmarkning": str(data.get("anmarkning", r["anmarkning"])),
    }
    redaktorer = r["redaktorer"] if redaktor in r["redaktorer"] else [*r["redaktorer"], redaktor]
    conn.execute(
        """
        UPDATE budgetforslag SET uppgifter = %s, partier = %s, titel = %s, antagen = %s, anmarkning = %s,
          redaktorer = %s, andrad = %s, status = 'utkast', granskad_av = NULL, granskad = NULL WHERE id = %s
        """,
        (Jsonb(nytt["uppgifter"]), nytt["partier"], nytt["titel"], nytt["antagen"], nytt["anmarkning"], redaktorer, nu,
         forslag_id),
    )
    conn.commit()
    return las(conn, forslag_id)


def _godkann(conn: psycopg.Connection, forslag_id: int, utgivare: str, fran: str) -> dict:
    r = _hamta(conn, forslag_id)
    if utgivare in r["redaktorer"]:
        raise EjTillatet("Ingen godkänner ett förslag som hen själv läst in eller ändrat")
    if r["status"] != fran:
        raise Konflikt(f"Förslaget är {r['status']}, inte {fran}")
    return r


def granska(conn: psycopg.Connection, forslag_id: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, forslag_id, utgivare, "utkast")
    conn.execute("UPDATE budgetforslag SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, nu, forslag_id))
    conn.commit()
    return las(conn, forslag_id)


def publicera(conn: psycopg.Connection, forslag_id: int, utgivare: str, nu: datetime) -> dict:
    r = _godkann(conn, forslag_id, utgivare, "granskad")
    conn.execute("UPDATE budgetforslag SET status = 'ersatt' WHERE status = 'publicerad' AND budgetar = %s AND nyckel = %s",
                 (r["budgetar"], r["nyckel"]))
    conn.execute("UPDATE budgetforslag SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, nu, forslag_id))
    conn.commit()
    return las(conn, forslag_id)


def original(conn: psycopg.Connection, forslag_id: int, redaktion: bool) -> tuple[bytes, str, str]:
    """(innehåll, mediatyp, filnamn). Ett opublicerat förslag visas bara för redaktionen."""
    r = conn.execute("SELECT original, filnamn, status, budgetar FROM budgetforslag WHERE id = %s", (forslag_id,)).fetchone()
    if r is None or (r["status"] != "publicerad" and not redaktion):
        raise LookupError(f"Budgetförslaget {forslag_id} finns inte")
    return bytes(r["original"]), FILTYPER[Path(r["filnamn"]).suffix.lower()], f"{r['budgetar']}-{r['filnamn']}"


# Jämförelse


def _differens(varde: float | None, mot: float | None) -> dict | None:
    if varde is None or mot is None:
        return None
    return {"mnkr": round(varde - mot, 1), "procent": round((varde - mot) / abs(mot) * 100, 1) if mot else None}


def budgetar(conn: psycopg.Connection) -> list[dict]:
    """Budgetåren med publicerade förslag."""
    return conn.execute(
        "SELECT budgetar, count(*) AS forslag, bool_or(antagen AND typ = 'budget') AS antagen FROM budgetforslag "
        "WHERE status = 'publicerad' GROUP BY budgetar ORDER BY budgetar DESC"
    ).fetchall()


def jamforelse(conn: psycopg.Connection, ar: int) -> dict:
    """De publicerade förslagen för budgetåret bredvid varandra, med skillnaden mot den antagna budgeten.

    Skillnaden räknas för det år som visas (budgetåret och planåren) när den antagna budgeten har en
    siffra för samma år och nämnd."""
    rader = conn.execute(
        f"SELECT {_KOLUMNER} FROM budgetforslag WHERE status = 'publicerad' AND budgetar = %s "
        "ORDER BY antagen DESC, typ, nyckel", (ar,),
    ).fetchall()
    forslag = [_ut(r) for r in rader]
    antagen = next((f for f in forslag if f["antagen"] and f["typ"] == "budget"), None)
    ar_lista = sorted({x["ar"] for f in forslag for x in f["uppgifter"]["resultat"] + f["uppgifter"]["ramar"]} | {ar})
    # Nämnderna i den ordning de står i första förslaget (den antagna budgeten när den finns).
    organ = list(dict.fromkeys(x["organ"] for f in forslag for x in f["uppgifter"]["ramar"]))
    for f in forslag:
        u = f["uppgifter"]
        if antagen is None or f is antagen:
            f["differens"] = None
            continue
        a = antagen["uppgifter"]
        skatt_u, skatt_a = (x["skattesats"].get("procent") if x["skattesats"] else None for x in (u, a))
        skatt = round(skatt_u - skatt_a, 2) if skatt_u is not None and skatt_a is not None else None
        res_a = {x["ar"]: x.get("mnkr") for x in a["resultat"]}
        ram_a = {(x["organ"], x["ar"]): x.get("mnkr") for x in a["ramar"]}
        f["differens"] = {
            "skattesats": skatt,
            "resultat": [{"ar": x["ar"], **d} for x in u["resultat"] if (d := _differens(x.get("mnkr"), res_a.get(x["ar"])))],
            "ramar": [{"organ": x["organ"], "ar": x["ar"], **d} for x in u["ramar"]
                      if (d := _differens(x.get("mnkr"), ram_a.get((x["organ"], x["ar"]))))],
        }
    return {"budgetar": ar, "ar": ar_lista, "organ": organ, "antagen": antagen["id"] if antagen else None,
            "forslag": forslag}


# Kommandot


def _fran_tar(strom: io.BufferedReader, mal: Path) -> Path:
    with tarfile.open(fileobj=strom, mode="r|*") as tar:
        tar.extractall(mal, filter="data")
    kataloger = [p for p in mal.iterdir() if p.is_dir()]
    # `tar -c budgetforslag` ger en toppkatalog, `tar -C budgetforslag -c .` ger årsmapparna direkt.
    return kataloger[0] if len(kataloger) == 1 and not re.fullmatch(r"\d{4}", kataloger[0].name) else mal


def main(argv: list[str] | None = None) -> None:
    from . import db

    p = argparse.ArgumentParser(prog="python -m app.budgetforslag", description="Läser in partiernas budgetförslag som utkast.")
    p.add_argument("mapp", help="mappen med <budgetår>/, eller - för en tar-ström på stdin")
    p.add_argument("--redaktor", required=True, help="e-post för redaktören som läser in (kan inte själv publicera)")
    a = p.parse_args(argv)
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with tempfile.TemporaryDirectory() as tmp:
        rot = _fran_tar(sys.stdin.buffer, Path(tmp)) if a.mapp == "-" else Path(a.mapp)
        try:
            forslag = las_mapp(rot)
        except Ogiltig as e:
            sys.exit(f"Inläsningen avbröts: {e}")
        with db.connect(url) as conn:
            antal = las_in(conn, forslag, a.redaktor.strip().lower(), datetime.now(timezone.utc))
    print(f"{len(forslag)} budgetförslag: {antal['nya']} nya utkast, {antal['uppdaterade']} uppdaterade, "
          f"{antal['oforandrade']} oförändrade.")


if __name__ == "__main__":
    main()
