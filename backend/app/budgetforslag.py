"""Partiernas budgetförslag (#48, #58, kravspec 17A).

Förslagen läggs lokalt i `data/budgetforslag/<budgetår>/` med filnamnet efter partiförkortningarna
bakom förslaget (`S.pdf`, `L+M.pdf`, `S-tillagg.pdf`). Budgetåret är året budgeten gäller. Bredvid
filerna beskriver `budget.json` varje förslag: ram per nämnd, skattesatsens förändring och budgeterat
resultat för budgetåret, med sidhänvisning för varje siffra. Filen tas fram en gång per år genom att
läsa dokumenten (de har olika tabelluppläggning och en del är inskannade).

Alla förslag för ett budgetår utgår från samma planförutsättningar (`planforutsattningar.xlsx` i
mappen, se `planforutsattningar.py`). Ett förslag lagrar ramar i mnkr, skattesatsens förändring i öre
och resultatet i procent av skatteintäkter och generella bidrag. Förändringen per nämnd, resultatet
i mnkr och det beräknade resultatet räknas fram.

`python -m app.budgetforslag MAPP --redaktor EPOST` läser planförutsättningarna och förslagen i mappen
och skapar utkast. Med `-` som mapp läses en tar-ström från stdin, så att mappen kan skickas till servern:

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

from . import planforutsattningar as pf
from .planforutsattningar import EjTillatet, Konflikt, Ogiltig

__all__ = ["EjTillatet", "Konflikt", "Ogiltig"]

FILTYPER = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
BESKRIVNING = "budget.json"
_PARTI = re.compile(r"[A-ZÅÄÖ]{1,4}")
_NYCKEL = re.compile(r"(?P<partier>[A-Za-zÅÄÖåäö]+(?:\+[A-ZÅÄÖ]{1,4})*)(?:-(?P<variant>[\w-]+))?")


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


def _ar(post: dict, budgetar: int, falt: str) -> int | None:
    """Året i en post i det tidigare formatet med planår. Saknas det gäller posten budgetåret."""
    v = post.get("ar")
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not budgetar - 1 <= v <= budgetar + 4:
        raise Ogiltig(f"{falt}: året ska ligga mellan {budgetar - 1} och {budgetar + 4}")
    return v


def _valfria(post: dict, falt: str, namn: tuple[str, ...]) -> dict:
    """De av fälten `namn` som finns, som tal. Minst ett krävs."""
    ut = {n: _tal(post[n], f"{falt} ({n})") for n in namn if post.get(n) is not None}
    if not ut:
        raise Ogiltig(f"{falt}: ange {' eller '.join(namn)}")
    return ut


def skattejustering(nt: dict, ore: int) -> float:
    """Skatteintäkternas förändring i mnkr när skattesatsen ändras med `ore` öre."""
    return nt["skatteintakter"] * ore / 100 / nt["skattesats"]


def bas(nt: dict, ore: int) -> float:
    """Basen för resultatet i procent: förslagets skatteintäkter och generella bidrag och utjämning."""
    return nt["skatteintakter"] + nt["bidrag"] + skattejustering(nt, ore)


def uppgifter(data: Any, budgetar: int, sidor: bool = True, nt: dict | None = None) -> dict:
    """Validerar uppgifterna och för dem till budgetmodellen för budgetåret. Ogiltig vid fel.

    `nt` är nyckeltalen ur årets planförutsättningar (`planforutsattningar.nyckeltal`), None om de saknas.
    Uppgifterna är det som står i dokumentet, med sida när dokumentet har fasta sidor (`sidor`, PDF):

    - `ramar`: per nämnd, {mnkr} eller {forandring} mot planförutsättningen. Lagras som mnkr.
    - `skattesats`: {ore}, {forandring} i procentenheter (−0,10 för "10 öre lägre") eller {procent}.
      Lagras som förändring i öre, eller som procent när planförutsättningar saknas. Utelämnad är 0 öre.
    - `resultat`: {procent} av skatteintäkter och generella bidrag, eller {mnkr}. Lagras som procent.

    Det tidigare formatet med planår (listor med `ar`) och `utgangslage` tas emot: bara budgetåret läses.
    """
    if not isinstance(data, dict):
        raise Ogiltig("Uppgifterna ska vara ett objekt")
    okanda = set(data) - {"skattesats", "resultat", "ramar", "utgangslage"}
    if okanda:
        raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")

    skatt_in = data.get("skattesats")
    if skatt_in is None or skatt_in == {"ore": 0}:  # förslaget anger ingen skattesats: oförändrad
        skatt: dict = {"ore": 0}
    else:
        if not isinstance(skatt_in, dict):
            raise Ogiltig("skattesats ska vara {ore, sida}, {forandring, sida} eller {procent, sida}")
        v = _valfria(skatt_in, "skattesats", ("ore", "forandring", "procent"))
        sida = _sida(skatt_in.get("sida"), "skattesats", sidor)
        if "procent" in v and not 10 <= v["procent"] <= 40:
            raise Ogiltig("skattesatsen ska anges i procent, t.ex. 23.34")
        if "ore" in v:
            ore = v["ore"]
        elif "forandring" in v:
            ore = v["forandring"] * 100
        elif nt is not None:
            ore = (v["procent"] - nt["skattesats"]) * 100
        else:
            ore = None
        if ore is not None and abs(ore - round(ore)) > 0.001:
            raise Ogiltig("skattesatsens förändring ska vara hela öre")
        skatt = ({"ore": int(round(ore))} if ore is not None else {"procent": v["procent"]}) | sida
    ore_ = skatt.get("ore", 0)

    res_in = data.get("resultat")
    if isinstance(res_in, list):  # planår: bara budgetåret
        res_in = next((r for i, r in enumerate(res_in) if _ar(r, budgetar, f"resultat {i + 1}") in (None, budgetar)), None)
    resultat = None
    if res_in is not None:
        if not isinstance(res_in, dict):
            raise Ogiltig("resultat ska vara {procent, sida} eller {mnkr, sida}")
        v = _valfria(res_in, "resultat", ("procent", "mnkr"))
        if "procent" in v:
            procent = v["procent"]
        elif nt is not None:
            procent = round(v["mnkr"] / bas(nt, ore_) * 100, 3)
        else:
            raise Ogiltig(f"resultat: ange procent, mnkr räknas bara om när planförutsättningarna för {budgetar} finns")
        if not -50 <= procent <= 50:
            raise Ogiltig("resultat: procenten ska vara en andel av skatter och bidrag, t.ex. 2.3")
        resultat = {"procent": procent} | _sida(res_in.get("sida"), "resultat", sidor)

    ramar = []
    for i, r in enumerate(data.get("ramar") or []):
        f = f"ram {i + 1}"
        if not isinstance(r, dict):
            raise Ogiltig(f"{f} ska vara ett objekt")
        if _ar(r, budgetar, f) not in (None, budgetar):
            continue  # planår
        organ = r.get("organ")
        if not isinstance(organ, str) or not organ.strip():
            raise Ogiltig(f"{f}: organ saknas")
        organ = organ.strip()
        v = _valfria(r, f, ("mnkr", "forandring"))
        if "mnkr" in v:
            mnkr = v["mnkr"]
        elif nt is None:
            raise Ogiltig(f"{f} ({organ}): ange mnkr, förändringen räknas bara om när planförutsättningarna för "
                          f"{budgetar} finns")
        elif organ not in nt["ramar"]:
            raise Ogiltig(f"{f}: {organ} finns inte i planförutsättningarna för {budgetar}, ange mnkr")
        else:
            mnkr = nt["ramar"][organ] + v["forandring"]
        ramar.append({"organ": organ, "mnkr": round(mnkr, 3)} | _sida(r.get("sida"), f, sidor))
    if len({r["organ"] for r in ramar}) != len(ramar):
        raise Ogiltig("Samma nämnd står flera gånger")
    return {"skattesats": skatt, "resultat": resultat, "ramar": ramar}


def tidigare_format(u: dict) -> bool:
    """Uppgifter i formatet före #58, med planår och utgångsläge."""
    return "utgangslage" in u or isinstance(u.get("resultat"), list)


def berakning(u: dict, nt: dict | None) -> dict:
    """Det som räknas fram ur förslaget och planförutsättningarna.

    - ram och förändring per nämnd mot planförutsättningen (nämnder som förslaget inte tar upp är oförändrade),
    - skattesatsen (planförutsättningen ± förändringen) och skatteintäkternas förändring,
    - resultatet i procent och mnkr (av förslagets skatteintäkter och generella bidrag),
    - beräknat resultat: planförutsättningens resultat − summan av förändringarna + skatteförändringen,
    - differensen mellan förslagets resultat och det beräknade.

    Utan planförutsättningar (`nt` None) visas bara förslagets egna siffror."""
    ore = u["skattesats"].get("ore")
    res = u["resultat"]
    if nt is None:
        return {"planforutsattningar": False,
                "skattesats": {"procent": u["skattesats"].get("procent"), "ore": ore, "plan": None},
                "skattejustering": None,
                "ramar": [{"organ": r["organ"], "mnkr": r["mnkr"], "plan": None, "forandring": None} for r in u["ramar"]],
                "forandring": None, "resultat": {"procent": res["procent"], "mnkr": None} if res else None,
                "plan_resultat": None, "beraknat": None, "differens": None}
    ore = ore or 0
    ramar = []
    for r in u["ramar"]:
        plan = nt["ramar"].get(r["organ"])
        ramar.append({"organ": r["organ"], "mnkr": r["mnkr"], "plan": plan,
                      "forandring": round(r["mnkr"] - plan, 3) if plan is not None else None})
    forandring = round(sum(r["forandring"] or 0 for r in ramar), 3)
    justering = skattejustering(nt, ore)
    beraknat = nt["resultat"] - forandring + justering
    mnkr = res["procent"] / 100 * bas(nt, ore) if res else None
    return {
        "planforutsattningar": True,
        "skattesats": {"procent": round(nt["skattesats"] + ore / 100, 2), "ore": ore, "plan": nt["skattesats"]},
        "skattejustering": round(justering, 1),
        "ramar": ramar,
        "forandring": forandring,
        "resultat": {"procent": res["procent"], "mnkr": round(mnkr, 1)} if res else None,
        "plan_resultat": nt["resultat"],
        "beraknat": round(beraknat, 1),
        "differens": round(mnkr - beraknat, 1) if mnkr is not None else None,
    }


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


def las_mapp(rot: Path, nyckeltal: dict[int, dict] | None = None) -> list[Forslag]:
    """Förslagen i `rot/<budgetår>/`, räknade mot planförutsättningarna per budgetår (`nyckeltal`).

    Ogiltig med fil och fel när något inte stämmer."""
    nyckeltal = nyckeltal or {}
    forslag = []
    for katalog in sorted(p for p in rot.iterdir() if p.is_dir()):
        if not re.fullmatch(r"\d{4}", katalog.name):
            continue
        budgetar = int(katalog.name)
        nt = nyckeltal.get(budgetar)
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
                                           uppgifter({}, budgetar, sidor, nt), f"Uppgifter saknas i {BESKRIVNING}."))
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
                    uppgifter({k: post[k] for k in ("skattesats", "resultat", "ramar") if k in post}, budgetar, sidor, nt),
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


def for_over(conn: psycopg.Connection, nyckeltal: dict[int, dict], redaktor: str, nu: datetime) -> dict:
    """För över förslag i formatet före #58 till budgetmodellen för budgetåret.

    Planåren tas bort, ett resultat i mnkr räknas om till procent och en skattesats i procent till en
    förändring i öre, mot årets planförutsättningar. Redaktörens ändringar följer med. Ett öppet utkast
    ändras och blir utkast igen, ett publicerat förslag får ett nytt utkast (om inget redan är öppet),
    och ett ersatt ändras där det står. Committar inte."""
    antal = {"utkast": 0, "nya_utkast": 0, "ersatta": 0}
    rader = conn.execute(
        "SELECT id, budgetar, nyckel, filnamn, status, uppgifter, inlast, redaktorer FROM budgetforslag ORDER BY id"
    ).fetchall()
    oppna = {(r["budgetar"], r["nyckel"]) for r in rader if r["status"] in ("utkast", "granskad")}
    for r in rader:
        if not tidigare_format(r["uppgifter"]):
            continue
        nt, sidor = nyckeltal.get(r["budgetar"]), r["filnamn"].lower().endswith(".pdf")
        try:
            ny = uppgifter(r["uppgifter"], r["budgetar"], sidor, nt)
            inlast = {**r["inlast"], "uppgifter": uppgifter(r["inlast"]["uppgifter"], r["budgetar"], sidor, nt)}
        except Ogiltig as e:
            raise Ogiltig(f"{r['budgetar']}/{r['filnamn']}: {e}") from e
        if r["status"] == "publicerad":
            if (r["budgetar"], r["nyckel"]) in oppna:
                continue  # det öppna utkastet förs över och ersätter det publicerade
            conn.execute(
                """
                INSERT INTO budgetforslag (budgetar, nyckel, partier, titel, typ, antagen, filnamn, sha256, original, inlast,
                  uppgifter, anmarkning, status, redaktorer, skapad, andrad)
                SELECT budgetar, nyckel, partier, titel, typ, antagen, filnamn, sha256, original, %s, %s, anmarkning,
                  'utkast', %s, %s, %s FROM budgetforslag WHERE id = %s
                """, (Jsonb(inlast), Jsonb(ny), [redaktor], nu, nu, r["id"]),
            )
            antal["nya_utkast"] += 1
        elif r["status"] == "ersatt":
            conn.execute("UPDATE budgetforslag SET uppgifter = %s, inlast = %s WHERE id = %s",
                         (Jsonb(ny), Jsonb(inlast), r["id"]))
            antal["ersatta"] += 1
        else:
            redaktorer = r["redaktorer"] if redaktor in r["redaktorer"] else [*r["redaktorer"], redaktor]
            conn.execute(
                "UPDATE budgetforslag SET uppgifter = %s, inlast = %s, status = 'utkast', redaktorer = %s, andrad = %s, "
                "granskad_av = NULL, granskad = NULL WHERE id = %s", (Jsonb(ny), Jsonb(inlast), redaktorer, nu, r["id"]),
            )
            antal["utkast"] += 1
    return antal


# Redigering och publicering

_KOLUMNER = ("id, budgetar, nyckel, partier, titel, typ, antagen, filnamn, sha256, uppgifter, anmarkning, status, "
             "redaktorer, skapad, andrad, granskad_av, granskad, publicerad_av, publicerad, inlast")


def _ut(r: dict, nyckeltal: dict[int, dict], redaktion: bool = False) -> dict:
    ut = {k: r[k] for k in ("id", "budgetar", "nyckel", "partier", "titel", "typ", "antagen", "filnamn", "anmarkning",
                            "status", "uppgifter")}
    ut["original"] = f"/api/budgetforslag/{r['id']}/original"
    ut["publicerad"] = r["publicerad"].isoformat() if r["publicerad"] else None
    nt = nyckeltal.get(r["budgetar"])
    ut["berakning"] = None if tidigare_format(r["uppgifter"]) else berakning(r["uppgifter"], nt)
    if redaktion:
        ut |= {"redaktorer": r["redaktorer"], "granskad_av": r["granskad_av"], "publicerad_av": r["publicerad_av"],
               "andrad": r["andrad"].isoformat(), "inlast": r["inlast"]["uppgifter"],
               "granskad": r["granskad"].isoformat() if r["granskad"] else None}
    return ut


def _nyckeltal(conn: psycopg.Connection, publicerade: bool) -> dict[int, dict]:
    return {ar: pf.nyckeltal(u) for ar, u in pf.aktuella(conn, publicerade).items()}


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
    nt = _nyckeltal(conn, publicerade=False)
    return [_ut(r, nt, redaktion=True) for r in rader]


def las(conn: psycopg.Connection, forslag_id: int) -> dict:
    return _ut(_hamta(conn, forslag_id), _nyckeltal(conn, publicerade=False), redaktion=True)


def andra(conn: psycopg.Connection, forslag_id: int, data: dict, redaktor: str, nu: datetime) -> dict:
    """Ändrar ett utkast: {uppgifter?, partier?, titel?, antagen?, anmarkning?}. Ett granskat förslag blir utkast igen."""
    r = _hamta(conn, forslag_id)
    if r["status"] not in ("utkast", "granskad"):
        raise Konflikt(f"Förslaget är {r['status']} och kan inte ändras")
    okanda = set(data) - {"uppgifter", "partier", "titel", "antagen", "anmarkning"}
    if okanda:
        raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")
    nt = _nyckeltal(conn, publicerade=False).get(r["budgetar"])
    nytt = {
        "uppgifter": uppgifter(data["uppgifter"], r["budgetar"], r["filnamn"].lower().endswith(".pdf"), nt)
        if "uppgifter" in data else r["uppgifter"],
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
    """De publicerade förslagen för budgetåret bredvid varandra, mot planförutsättningarna och den antagna budgeten.

    Förändringarna och det beräknade resultatet räknas bara mot publicerade planförutsättningar.
    Skillnaden mot den antagna budgeten räknas per nämnd, för resultatet i mnkr och för skattesatsen i öre."""
    rader = conn.execute(
        f"SELECT {_KOLUMNER} FROM budgetforslag WHERE status = 'publicerad' AND budgetar = %s "
        "ORDER BY antagen DESC, typ, nyckel", (ar,),
    ).fetchall()
    plan = pf.publicerad(conn, ar)
    nt = {ar: pf.nyckeltal(plan)} if plan else {}
    forslag = [_ut(r, nt) for r in rader]
    antagen = next((f for f in forslag if f["antagen"] and f["typ"] == "budget"), None)
    # Nämnderna i planförutsättningarnas ordning, sedan i den ordning de står i förslagen.
    organ = list(dict.fromkeys([*(nt[ar]["ramar"] if nt else []), *(x["organ"] for f in forslag for x in f["uppgifter"]["ramar"])]))
    for f in forslag:
        if antagen is None or f is antagen:
            f["differens"] = None
            continue
        u, a = f["berakning"], antagen["berakning"]
        ore_u, ore_a = u["skattesats"]["ore"], a["skattesats"]["ore"]
        ram_a = {x["organ"]: x["mnkr"] for x in a["ramar"]}
        f["differens"] = {
            "skattesats": ore_u - ore_a if ore_u is not None and ore_a is not None else None,
            "resultat": _differens((u["resultat"] or {}).get("mnkr"), (a["resultat"] or {}).get("mnkr")),
            "ramar": [{"organ": x["organ"], **d} for x in u["ramar"] if (d := _differens(x["mnkr"], ram_a.get(x["organ"])))],
        }
    return {"budgetar": ar, "organ": organ, "antagen": antagen["id"] if antagen else None,
            "planforutsattningar": plan, "forslag": forslag}


# Kommandot


def _fran_tar(strom: io.BufferedReader, mal: Path) -> Path:
    with tarfile.open(fileobj=strom, mode="r|*") as tar:
        tar.extractall(mal, filter="data")
    kataloger = [p for p in mal.iterdir() if p.is_dir()]
    # `tar -c budgetforslag` ger en toppkatalog, `tar -C budgetforslag -c .` ger årsmapparna direkt.
    return kataloger[0] if len(kataloger) == 1 and not re.fullmatch(r"\d{4}", kataloger[0].name) else mal


def main(argv: list[str] | None = None) -> None:
    from . import db

    p = argparse.ArgumentParser(prog="python -m app.budgetforslag",
                                description="Läser in planförutsättningarna och partiernas budgetförslag som utkast.")
    p.add_argument("mapp", help=f"mappen med {pf.FILNAMN} och <budgetår>/, eller - för en tar-ström på stdin")
    p.add_argument("--redaktor", required=True, help="e-post för redaktören som läser in (kan inte själv publicera)")
    a = p.parse_args(argv)
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    redaktor, nu = a.redaktor.strip().lower(), datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        rot = _fran_tar(sys.stdin.buffer, Path(tmp)) if a.mapp == "-" else Path(a.mapp)
        with db.connect(url) as conn:
            try:
                fil = rot / pf.FILNAMN
                planer = pf.las_excel(fil) if fil.exists() else []
                # Förslagen räknas mot de planförutsättningar som läses in nu, annars de senaste i databasen.
                nyckeltal = _nyckeltal(conn, publicerade=False) | {x.budgetar: pf.nyckeltal(x.uppgifter) for x in planer}
                forslag = las_mapp(rot, nyckeltal)
                antal_pf = pf.las_in(conn, planer, redaktor, nu)
                overforda = for_over(conn, nyckeltal, redaktor, nu)
            except Ogiltig as e:
                conn.rollback()
                sys.exit(f"Inläsningen avbröts: {e}")
            antal = las_in(conn, forslag, redaktor, nu)
    if planer:
        print(f"{len(planer)} planförutsättningar: {antal_pf['nya']} nya utkast, {antal_pf['uppdaterade']} uppdaterade, "
              f"{antal_pf['oforandrade']} oförändrade.")
    if any(overforda.values()):
        print(f"Förda till budgetåret: {overforda['utkast']} utkast, {overforda['nya_utkast']} nya utkast för "
              f"publicerade förslag, {overforda['ersatta']} ersatta.")
    print(f"{len(forslag)} budgetförslag: {antal['nya']} nya utkast, {antal['uppdaterade']} uppdaterade, "
          f"{antal['oforandrade']} oförändrade.")


if __name__ == "__main__":
    main()
