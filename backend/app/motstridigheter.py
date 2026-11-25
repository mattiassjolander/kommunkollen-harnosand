"""Motstridigheter i styrande dokument (#151): något i eller mellan dokumenten som inte går ihop.

Tre typer (GLOSSARY.md):

- **Motsägelse**: två bestämmelser säger olika saker om samma sak. Båda ställena citeras med dokument, version,
  sida och paragraf.
- **Felaktig hänvisning**: en hänvisning till något som inte finns. Hänvisningen citeras med en kontrollerbar
  uppgift med källa om det som finns.
- **Flera gällande versioner**: samma dokument eller sak ligger ute flera gånger som gällande.

Förslagen kommer från två håll. Insamlingen tar fram kandidater till flera gällande versioner (`foresla_kandidater`):
dokument med samma diarienummer i dokumentinformationen, och titlar som bara skiljer sig i skiljetecken eller årtal.
Skillen `harnosandskollen-styrande-dokument` läser reglementena och delegationsordningarna och läser in förslag av
alla tre typerna (`las_in`, formatet i docs/styrande-dokument.md). Backend anropar ingen AI (ADR-0009).

Allt blir utkast. En utgivare som inte har läst in förslaget granskar och publicerar det, eller avvisar det
(ADR-0002). En publicerad motstridighet har status ny, anmäld till kommunen eller åtgärdad av kommunen, och kan
återkallas. När ett berört dokument får en ny version märks den "Dokumentet har ändrats" tills en redaktör har
tagit ställning. Analysen körs inte om av sig själv.

`python -m app.motstridigheter FIL --redaktor EPOST` läser in skillens fil. Med `-` läses filen från stdin, så att
den kan skickas till servern. Med `--prova` kontrolleras filen utan att något sparas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import db, kalender
from .styrande_dokument import faststallt_organ, giltighet, normalisera_diarienummer

TYPER = {
    "motsagelse": "Motsägelse",
    "felaktig_hanvisning": "Felaktig hänvisning",
    "flera_versioner": "Flera gällande versioner",
}
ANMALAN = {"ny": "Ny", "anmald": "Anmäld till kommunen", "atgardad": "Åtgärdad av kommunen"}

# Skillens omfång: reglementena och delegationsordningarna, utom överförmyndarnämndens (organet ligger utanför
# plattformen, kravspec avsnitt 18).
OMFANG = ("Reglementen, ägardirektiv och bolagsordning", "Delegationer")
UTANFOR = re.compile(r"överförmyndar", re.IGNORECASE)

_FORBJUDNA = re.compile(r"\b(?:fel(?:et|en|a)?|brist\w*|slarv\w*)\b|motsäger\s+sig\s+själv", re.IGNORECASE)
_MENING = re.compile(r"[.!?](?=\s+[A-ZÅÄÖ\"”]|\s*$)")


class Ogiltig(ValueError):
    pass


class EjTillatet(Exception):
    pass


class Konflikt(Exception):
    pass


def kontrollera_forklaring(text: Any) -> str:
    """Förklaringen återger vad dokumenten säger, i högst två meningar och utan värderande ord."""
    if not isinstance(text, str) or not text.strip():
        raise Ogiltig("Förklaringen saknas")
    text = " ".join(text.split())
    if m := _FORBJUDNA.search(text):
        raise Ogiltig(f"Förklaringen innehåller ordet \"{m[0]}\". Återge vad dokumenten säger, utan att värdera")
    if len(_MENING.findall(text)) > 2:
        raise Ogiltig("Förklaringen är längre än två meningar")
    return text


# Maskinella kandidater till flera gällande versioner

_ARTAL = re.compile(r"(?<!\d)(?:19|20)\d{2}(?:[-–—/.]\d{1,2}[-–—/.]\d{1,2})?(?!\d)")


def titelnyckel(titel: str) -> str:
    """Titeln utan årtal, datum, skiljetecken och blanksteg. Två titlar med samma nyckel skiljer sig bara i
    skiljetecken eller årtal."""
    t = _ARTAL.sub(" ", unicodedata.normalize("NFKC", titel).casefold())
    return "".join(c for c in t if c.isalnum())


def _gallande(conn: psycopg.Connection, idag: date) -> list[dict]:
    rader = conn.execute(
        """
        SELECT d.id, d.sitevision_id, d.titel, d.kategorier, d.borttagen, v.version, v.dokumentinformation, v.sidor
        FROM styrande_dokument d
        JOIN LATERAL (SELECT version, dokumentinformation, sidor FROM styrande_dokument_version
                      WHERE dokument_id = d.id ORDER BY version DESC LIMIT 1) v ON true
        WHERE d.borttagen IS NULL ORDER BY d.id
        """
    ).fetchall()
    return [r for r in rader
            if giltighet(r["titel"], r["dokumentinformation"], r["borttagen"], idag)["status"] == "gallande"]


def _uppraknat(titlar: list[str]) -> str:
    t = [f"”{x}”" for x in titlar]
    return t[0] if len(t) == 1 else ", ".join(t[:-1]) + " och " + t[-1]


def _nyckel_flera(dokument_ids: list[int]) -> str:
    return "flera_versioner:" + ",".join(str(i) for i in sorted(set(dokument_ids)))


def foresla_kandidater(conn: psycopg.Connection, idag: date, nu: datetime) -> int:
    """Kandidater till flera gällande versioner bland alla gällande styrande dokument, som utkast. Ger antalet nya.
    Ett förslag som redan finns, i vilken status som helst, föreslås inte igen."""
    dokument = _gallande(conn, idag)
    grupper: dict[tuple, list[dict]] = {}
    for d in dokument:
        info = d["dokumentinformation"]
        dnr = normalisera_diarienummer(info.get("diarienummer"), faststallt_organ(info.get("faststalld_av")))
        if dnr is not None:
            grupper.setdefault(("dnr", dnr), []).append(d)
        grupper.setdefault(("titel", titelnyckel(d["titel"])), []).append(d)
    nya = 0
    sedda: set[str] = set()
    for (grund, varde), docs in grupper.items():
        if len(docs) < 2:
            continue
        nyckel = _nyckel_flera([d["id"] for d in docs])
        if nyckel in sedda:
            continue
        sedda.add(nyckel)
        titlar = [d["titel"] for d in docs]
        if grund == "dnr":
            dnr = next(d["dokumentinformation"]["diarienummer"] for d in docs)
            forklaring = f"{_uppraknat(titlar)} har samma diarienummer i dokumentinformationen, {dnr}."
            grundtext = "samma diarienummer"
        else:
            forklaring = f"Titlarna {_uppraknat(titlar)} skiljer sig bara i skiljetecken eller årtal."
            grundtext = "titlar som bara skiljer sig i skiljetecken eller årtal"
        nya += _skapa(conn, "flera_versioner", nyckel, forklaring, [], None, docs, "insamling", grundtext, [], nu)
    return nya


def _skapa(conn: psycopg.Connection, typ: str, nyckel: str, forklaring: str, citat: list[dict], uppgift: dict | None,
           dokument: list[dict], kalla: str, grund: str | None, redaktorer: list[str], nu: datetime) -> int:
    """Skapar ett utkast om nyckeln är ny. Ger 1 för ett nytt utkast och 0 annars."""
    if conn.execute("SELECT 1 FROM motstridighet WHERE nyckel = %s", (nyckel,)).fetchone():
        return 0
    ids = sorted({d["id"] for d in dokument})
    conn.execute(
        """
        INSERT INTO motstridighet (typ, nyckel, forklaring, citat, uppgift, dokument_ids, versioner, kalla, grund,
                                   redaktorer, skapad)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (typ, nyckel, forklaring, Jsonb(citat), Jsonb(uppgift) if uppgift else None, ids,
         Jsonb({str(d["id"]): d["version"] for d in dokument}), kalla, grund, redaktorer, nu),
    )
    return 1


# Inläsning från skillen


def jamforbar(text: str) -> str:
    """Text som går att jämföra med sidans text: utan blanksteg, avstavning och skillnader i streck och citattecken."""
    t = unicodedata.normalize("NFKC", text).casefold().replace("\xad", "")
    t = re.sub(r"[-‐‑–—]\s*\n\s*", "", t)  # avstavning vid radslut
    t = re.sub(r"[‐‑–—−]", "-", t)
    t = re.sub(r"[”“„\"’‘']", "", t)
    return re.sub(r"\s+", "", t)


def _i_omfang(d: dict) -> bool:
    return any(k in OMFANG for k in d["kategorier"]) and not UTANFOR.search(d["titel"])


def _dokumentet(conn: psycopg.Connection, ref: Any, var: str, cache: dict) -> dict:
    if not isinstance(ref, str) or not ref.strip():
        raise Ogiltig(f"{var}: ange dokumentet med sitt id på kommunens sida, till exempel 18.580e43d7163221b2781b73fe")
    ref = ref.strip()
    if ref not in cache:
        cache[ref] = conn.execute(
            """
            SELECT d.id, d.sitevision_id, d.titel, d.kategorier, v.version, v.sidor
            FROM styrande_dokument d
            JOIN LATERAL (SELECT version, sidor FROM styrande_dokument_version
                          WHERE dokument_id = d.id ORDER BY version DESC LIMIT 1) v ON true
            WHERE d.sitevision_id = %s AND d.borttagen IS NULL
            """,
            (ref,),
        ).fetchone()
    d = cache[ref]
    if d is None:
        raise Ogiltig(f"{var}: dokumentet {ref} finns inte bland de styrande dokumenten på kommunens sida")
    if not _i_omfang(d):
        raise Ogiltig(f"{var}: {d['titel']} ingår inte i analysen (reglementen och delegationsordningar)")
    return d


def citerat_stalle(conn: psycopg.Connection, c: Any, var: str, cache: dict, paragraf: bool) -> tuple[dict, dict]:
    """Ett citerat ställe: {dokument, sida, paragraf, text}. Texten ska stå på sidan i dokumentets senaste version."""
    if not isinstance(c, dict):
        raise Ogiltig(f"{var}: ska vara ett objekt med dokument, sida och text")
    if okanda := set(c) - {"dokument", "sida", "paragraf", "text"}:
        raise Ogiltig(f"{var}: okända fält {', '.join(sorted(okanda))}")
    d = _dokumentet(conn, c.get("dokument"), var, cache)
    sida = c.get("sida")
    if not isinstance(sida, int) or isinstance(sida, bool):
        raise Ogiltig(f"{var}: sidan saknas. Ange sidan i PDF:en räknat från 1")
    if not 1 <= sida <= len(d["sidor"]):
        raise Ogiltig(f"{var}: {d['titel']} har {len(d['sidor'])} sidor, inte sidan {sida}")
    text = c.get("text")
    if not isinstance(text, str) or not text.strip():
        raise Ogiltig(f"{var}: citatet saknas")
    if jamforbar(text) not in jamforbar(d["sidor"][sida - 1]):
        raise Ogiltig(f"{var}: citatet står inte ordagrant på sidan {sida} i {d['titel']}")
    para = c.get("paragraf")
    if para is not None and (not isinstance(para, str) or not para.strip()):
        raise Ogiltig(f"{var}: paragrafen ska vara en text, till exempel \"3 kap. 2 §\"")
    if paragraf and not para:
        raise Ogiltig(f"{var}: paragrafen saknas, till exempel \"3 kap. 2 §\" eller \"§ 13\"")
    return d, {"dokument_id": d["id"], "version": d["version"], "sida": sida,
               "paragraf": para.strip() if para else None, "text": " ".join(text.split())}


def tolka(conn: psycopg.Connection, data: Any) -> list[dict]:
    """Kontrollerar skillens fil och ger förslagen. Ogiltig med motstridighetens nummer vid fel."""
    if not isinstance(data, dict) or not isinstance(data.get("motstridigheter"), list):
        raise Ogiltig("Filen ska ha formen {\"motstridigheter\": [...]}")
    cache: dict = {}
    ut = []
    for i, m in enumerate(data["motstridigheter"], 1):
        var = f"Motstridighet {i}"
        if not isinstance(m, dict):
            raise Ogiltig(f"{var}: ska vara ett objekt")
        typ = m.get("typ")
        if typ not in TYPER:
            raise Ogiltig(f"{var}: okänd typ {typ!r}. Typerna är {', '.join(TYPER)}")
        if okanda := set(m) - {"typ", "forklaring", "citat", "uppgift", "dokument"}:
            raise Ogiltig(f"{var}: okända fält {', '.join(sorted(okanda))}")
        try:
            forklaring = kontrollera_forklaring(m.get("forklaring"))
        except Ogiltig as e:
            raise Ogiltig(f"{var}: {e}") from None
        citat_in = m.get("citat") or []
        if not isinstance(citat_in, list):
            raise Ogiltig(f"{var}: citat ska vara en lista")
        dokument: dict[int, dict] = {}
        citat = []
        for j, c in enumerate(citat_in, 1):
            d, s = citerat_stalle(conn, c, f"{var}, citat {j}", cache, paragraf=typ == "motsagelse")
            dokument[d["id"]] = d
            citat.append(s)
        uppgift = None
        if typ == "motsagelse":
            if len(citat) < 2:
                raise Ogiltig(f"{var}: en motsägelse citerar båda ställena")
            if m.get("uppgift") or m.get("dokument"):
                raise Ogiltig(f"{var}: en motsägelse har bara citat")
        elif typ == "felaktig_hanvisning":
            if len(citat) != 1:
                raise Ogiltig(f"{var}: en felaktig hänvisning citerar hänvisningen, ett ställe")
            # Uppgiften om det som finns, till exempel "Reglementet har kapitel 1–8", med dokument och sida som källa.
            # Den är en sammanfattning. Ett ordagrant citat ur källan kan läggas till och kontrolleras då.
            u = m.get("uppgift")
            if not isinstance(u, dict) or not isinstance(u.get("text"), str) or not u["text"].strip():
                raise Ogiltig(f"{var}: uppgiften om det som finns saknas, med text, dokument och sida")
            if okanda := set(u) - {"text", "dokument", "sida", "citat"}:
                raise Ogiltig(f"{var}, uppgiften: okända fält {', '.join(sorted(okanda))}")
            if u.get("citat"):
                ud, kalla = citerat_stalle(conn, {"dokument": u.get("dokument"), "sida": u.get("sida"), "text": u["citat"]},
                                    f"{var}, uppgiften", cache, paragraf=False)
            else:
                ud = _dokumentet(conn, u.get("dokument"), f"{var}, uppgiften", cache)
                sida = u.get("sida")
                if not isinstance(sida, int) or isinstance(sida, bool) or not 1 <= sida <= len(ud["sidor"]):
                    raise Ogiltig(f"{var}, uppgiften: sidan saknas eller finns inte i {ud['titel']}")
                kalla = {"dokument_id": ud["id"], "version": ud["version"], "sida": sida}
            uppgift = {"text": " ".join(u["text"].split()), "dokument_id": kalla["dokument_id"],
                       "version": kalla["version"], "sida": kalla["sida"]}
            if u.get("citat"):
                uppgift["citat"] = kalla["text"]
            dokument[ud["id"]] = ud
        else:
            refs = m.get("dokument")
            if not isinstance(refs, list) or len({r for r in refs if isinstance(r, str)}) < 2:
                raise Ogiltig(f"{var}: flera gällande versioner anger minst två dokument")
            for j, r in enumerate(refs, 1):
                d = _dokumentet(conn, r, f"{var}, dokument {j}", cache)
                dokument[d["id"]] = d
            if m.get("uppgift"):
                raise Ogiltig(f"{var}: flera gällande versioner har ingen uppgift")
        if typ == "flera_versioner":
            nyckel = _nyckel_flera(list(dokument))
        else:
            delar = sorted(f"{c['dokument_id']}:{c['sida']}:{jamforbar(c['text'])}" for c in citat)
            nyckel = f"{typ}:" + hashlib.sha256("|".join(delar).encode()).hexdigest()[:24]
        ut.append({"typ": typ, "nyckel": nyckel, "forklaring": forklaring, "citat": citat, "uppgift": uppgift,
                   "dokument": list(dokument.values())})
    return ut


def las_in(conn: psycopg.Connection, data: Any, redaktor: str, nu: datetime) -> dict:
    """Läser in skillens förslag som utkast. Ett förslag som redan finns läses inte in igen. Committar inte."""
    forslag = tolka(conn, data)
    nya = sum(_skapa(conn, f["typ"], f["nyckel"], f["forklaring"], f["citat"], f["uppgift"], f["dokument"], "skill",
                     None, [redaktor], nu) for f in forslag)
    return {"nya": nya, "oforandrade": len(forslag) - nya}


# Nya versioner av berörda dokument


def markera_andrat(conn: psycopg.Connection, dokument_id: int, dag: date) -> None:
    """Ett berört dokument har fått en ny version: motstridigheten märks "Dokumentet har ändrats"."""
    conn.execute(
        "UPDATE motstridighet SET dokument_andrat = %s WHERE %s = ANY(dokument_ids) AND status <> 'avvisad' "
        "AND dokument_andrat IS NULL", (dag, dokument_id))


# Granskning och status


def _rad(conn: psycopg.Connection, mid: int) -> dict:
    r = conn.execute("SELECT * FROM motstridighet WHERE id = %s", (mid,)).fetchone()
    if r is None:
        raise LookupError(f"Motstridigheten {mid} finns inte")
    return r


def _godkann(conn: psycopg.Connection, mid: int, utgivare: str, fran: str) -> dict:
    r = _rad(conn, mid)
    if utgivare in r["redaktorer"]:
        raise EjTillatet("Ingen godkänner ett förslag som hen själv har läst in")
    if r["status"] != fran:
        raise Konflikt(f"Förslaget är {r['status']}, inte {fran}")
    return r


def granska(conn: psycopg.Connection, mid: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, mid, utgivare, "utkast")
    conn.execute("UPDATE motstridighet SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, nu, mid))
    conn.commit()
    return las(conn, mid, redaktion=True)


def publicera(conn: psycopg.Connection, mid: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, mid, utgivare, "granskad")
    conn.execute("UPDATE motstridighet SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, nu, mid))
    conn.commit()
    return las(conn, mid, redaktion=True)


def _motivering(data: dict, vad: str) -> str:
    m = (data.get("motivering") or "").strip() if isinstance(data, dict) else ""
    if not m:
        raise Ogiltig(f"Ange varför förslaget {vad}")
    return m


def avvisa(conn: psycopg.Connection, mid: int, data: dict, utgivare: str, nu: datetime) -> dict:
    """Ett förslag som inte håller avvisas i granskningen, med motivering."""
    r = _rad(conn, mid)
    if r["status"] not in ("utkast", "granskad"):
        raise Konflikt(f"Bara ett utkast eller ett granskat förslag kan avvisas, det här är {r['status']}")
    conn.execute("UPDATE motstridighet SET status = 'avvisad', avvisad_av = %s, avvisad = %s, avvisning = %s "
                 "WHERE id = %s", (utgivare, nu, _motivering(data, "avvisas"), mid))
    conn.commit()
    return las(conn, mid, redaktion=True)


def aterkalla(conn: psycopg.Connection, mid: int, data: dict, utgivare: str, nu: datetime) -> dict:
    """En utgivare återkallar en publicerad motstridighet direkt, med motivering."""
    r = _rad(conn, mid)
    if r["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad motstridighet kan återkallas, den här är {r['status']}")
    conn.execute("UPDATE motstridighet SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, "
                 "aterkallelse = %s WHERE id = %s", (utgivare, nu, _motivering(data, "återkallas"), mid))
    conn.commit()
    return las(conn, mid, redaktion=True)


def satt_status(conn: psycopg.Connection, mid: int, data: dict, redaktor: str) -> dict:
    """Status för en publicerad motstridighet: {status: ny | anmald | atgardad, datum (standard i dag), anteckning}."""
    r = _rad(conn, mid)
    if r["status"] != "publicerad":
        raise Konflikt("Status sätts på en publicerad motstridighet")
    status = data.get("status")
    if status not in ANMALAN:
        raise Ogiltig(f"Okänd status: {status}")
    try:
        dag = date.fromisoformat(data["datum"]) if data.get("datum") else kalender.idag()
    except (TypeError, ValueError) as e:
        raise Ogiltig("Datumet ska skrivas ÅÅÅÅ-MM-DD") from e
    anteckning = (data.get("anteckning") or "").strip() or None
    if status == "atgardad" and not anteckning:
        raise Ogiltig("Beskriv i anteckningen vad kommunen har åtgärdat")
    conn.execute("UPDATE motstridighet SET anmalan = %s, anmalan_datum = %s, anteckning = %s WHERE id = %s",
                 (status, None if status == "ny" else dag, anteckning, mid))
    conn.execute("INSERT INTO motstridighet_status (motstridighet_id, status, statusdatum, anteckning, satt_av) "
                 "VALUES (%s, %s, %s, %s, %s)", (mid, status, dag, anteckning, redaktor))
    conn.commit()
    return las(conn, mid, redaktion=True)


def ta_stallning(conn: psycopg.Connection, mid: int, redaktor: str) -> dict:
    """En redaktör har tagit ställning till ett ändrat dokument: märkningen tas bort och versionerna blir de
    senaste. Motstridigheten ligger kvar. Håller den inte längre återkallas eller avvisas den för sig."""
    r = _rad(conn, mid)
    if r["dokument_andrat"] is None:
        raise Konflikt("Inget berört dokument har ändrats")
    versioner = {str(x["dokument_id"]): x["version"] for x in conn.execute(
        "SELECT dokument_id, max(version) AS version FROM styrande_dokument_version WHERE dokument_id = ANY(%s) "
        "GROUP BY dokument_id", (r["dokument_ids"],))}
    conn.execute("UPDATE motstridighet SET dokument_andrat = NULL, versioner = %s WHERE id = %s",
                 (Jsonb(versioner), mid))
    conn.execute("INSERT INTO motstridighet_status (motstridighet_id, status, statusdatum, anteckning, satt_av) "
                 "VALUES (%s, %s, %s, %s, %s)",
                 (mid, r["anmalan"], kalender.idag(), "Tog ställning till ändrat dokument", redaktor))
    conn.commit()
    return las(conn, mid, redaktion=True)


# Läsning


def _ut(r: dict, titlar: dict[int, str], redaktion: bool) -> dict:
    def stalle(c: dict) -> dict:
        return c | {"titel": titlar.get(c["dokument_id"]),
                    "lank": f"/politik/styrande-dokument/{c['dokument_id']}",
                    "kopia": f"/api/styrande-dokument/{c['dokument_id']}/versioner/{c['version']}#page={c['sida']}"}

    ut = {
        "id": r["id"], "typ": r["typ"], "typnamn": TYPER[r["typ"]], "forklaring": r["forklaring"],
        "citat": [stalle(c) for c in r["citat"]],
        "uppgift": stalle(r["uppgift"]) if r["uppgift"] else None,
        "dokument": [{"id": i, "titel": titlar.get(i), "version": r["versioner"].get(str(i))} for i in r["dokument_ids"]],
        "kalla": r["kalla"], "grund": r["grund"],
        "status": r["anmalan"], "statusnamn": ANMALAN[r["anmalan"]],
        "statusdatum": r["anmalan_datum"].isoformat() if r["anmalan_datum"] else None,
        "anteckning": r["anteckning"],
        "dokument_andrat": r["dokument_andrat"].isoformat() if r["dokument_andrat"] else None,
        "publicerad": r["publicerad"].isoformat() if r["publicerad"] else None,
    }
    if redaktion:
        ut |= {
            "granskning": r["status"], "redaktorer": r["redaktorer"], "skapad": r["skapad"].isoformat(),
            "granskad_av": r["granskad_av"], "granskad": r["granskad"].isoformat() if r["granskad"] else None,
            "publicerad_av": r["publicerad_av"],
            "avvisad_av": r["avvisad_av"], "avvisning": r["avvisning"],
            "avvisad": r["avvisad"].isoformat() if r["avvisad"] else None,
            "aterkallad_av": r["aterkallad_av"], "aterkallelse": r["aterkallelse"],
            "aterkallad": r["aterkallad"].isoformat() if r["aterkallad"] else None,
        }
    return ut


def _titlar(conn: psycopg.Connection, rader: list[dict]) -> dict[int, str]:
    ids = sorted({i for r in rader for i in r["dokument_ids"]})
    return {r["id"]: r["titel"] for r in conn.execute("SELECT id, titel FROM styrande_dokument WHERE id = ANY(%s)", (ids,))}


def _hamta(conn: psycopg.Connection, granskning: tuple[str, ...], typ: str | None = None, status: str | None = None,
           dokument_id: int | None = None) -> list[dict]:
    return conn.execute(
        """
        SELECT * FROM motstridighet
        WHERE status = ANY(%(g)s) AND (%(typ)s::text IS NULL OR typ = %(typ)s)
          AND (%(status)s::text IS NULL OR anmalan = %(status)s)
          AND (%(dok)s::bigint IS NULL OR %(dok)s = ANY(dokument_ids))
        ORDER BY array_position(ARRAY['motsagelse', 'felaktig_hanvisning', 'flera_versioner'], typ),
                 publicerad DESC NULLS LAST, id
        """,
        {"g": list(granskning), "typ": typ, "status": status, "dok": dokument_id},
    ).fetchall()


def las(conn: psycopg.Connection, mid: int, redaktion: bool = False) -> dict:
    r = _rad(conn, mid)
    if not redaktion and r["status"] != "publicerad":
        raise LookupError(f"Motstridigheten {mid} finns inte")
    return _ut(r, _titlar(conn, [r]), redaktion)


def publicerade(conn: psycopg.Connection, typ: str | None = None, status: str | None = None) -> dict:
    """Den samlade listan: de publicerade motstridigheterna, med antal per typ och status."""
    alla = _hamta(conn, ("publicerad",))
    rader = [r for r in alla if (typ is None or r["typ"] == typ) and (status is None or r["anmalan"] == status)]
    titlar = _titlar(conn, rader)
    return {
        "typer": [{"id": k, "namn": n, "antal": sum(1 for r in alla if r["typ"] == k)} for k, n in TYPER.items()],
        "statusar": [{"id": k, "namn": n, "antal": sum(1 for r in alla if r["anmalan"] == k)}
                     for k, n in ANMALAN.items()],
        "motstridigheter": [_ut(r, titlar, False) for r in rader],
    }


def for_dokument(conn: psycopg.Connection, dokument_id: int) -> list[dict]:
    rader = _hamta(conn, ("publicerad",), dokument_id=dokument_id)
    titlar = _titlar(conn, rader)
    return [_ut(r, titlar, False) for r in rader]


def paragrafnyckel(paragraf: str | None) -> tuple[str, ...]:
    """Paragrafen utan skrivsätt: "§13", "13 §" och "§ 13" blir samma, "3 kap. 2 §" blir ("3", "kap", "2")."""
    return tuple(re.findall(r"\d+|kap", (paragraf or "").casefold()))


def samma_stalle(a: dict, b: dict) -> bool:
    """Två citat avser samma ställe: samma dokument och sida, och samma paragraf när båda anger en."""
    if (a["dokument_id"], a["sida"]) != (b["dokument_id"], b["sida"]):
        return False
    pa, pb = paragrafnyckel(a.get("paragraf")), paragrafnyckel(b.get("paragraf"))
    return not pa or not pb or pa == pb


def vid_stallen(conn: psycopg.Connection, stallen: list[dict]) -> list[list[dict]]:
    """De publicerade motstridigheter som citerar vart och ett av ställena ({dokument_id, sida, paragraf}), i samma
    ordning. Används för att visa motstridigheter vid stegen i en process (#152)."""
    ids = sorted({s["dokument_id"] for s in stallen})
    rader = [r for r in _hamta(conn, ("publicerad",)) if set(r["dokument_ids"]) & set(ids)]
    titlar = _titlar(conn, rader)
    return [[_ut(r, titlar, False) for r in rader if any(samma_stalle(c, s) for c in r["citat"])] for s in stallen]


def antal_per_dokument(conn: psycopg.Connection) -> dict[int, int]:
    return {r["id"]: r["antal"] for r in conn.execute(
        "SELECT unnest(dokument_ids) AS id, count(*) AS antal FROM motstridighet WHERE status = 'publicerad' GROUP BY 1")}


def forslag(conn: psycopg.Connection, granskning: str | None = None, typ: str | None = None,
            dokument_id: int | None = None) -> dict:
    """Redaktionens granskningsvy: förslagen (utkast och granskade, eller en annan granskningsstatus), filtrerbara på
    typ och dokument, och alla publicerade med märkningen "Dokumentet har ändrats"."""
    g = (granskning,) if granskning else ("utkast", "granskad")
    rader = _hamta(conn, g, typ=typ, dokument_id=dokument_id)
    andrade = [r for r in _hamta(conn, ("publicerad",)) if r["dokument_andrat"] is not None]
    alla = _hamta(conn, ("utkast", "granskad", "publicerad", "avvisad", "aterkallad"))
    titlar = _titlar(conn, rader + andrade + alla)
    return {
        "forslag": [_ut(r, titlar, True) for r in rader],
        "andrade": [_ut(r, titlar, True) for r in andrade],
        "typer": [{"id": k, "namn": n} for k, n in TYPER.items()],
        "dokument": sorted(({"id": i, "titel": titlar.get(i)} for i in {i for r in alla for i in r["dokument_ids"]}),
                           key=lambda d: (d["titel"] or "").casefold()),
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.motstridigheter",
                                description="Läser in skillens förslag till motstridigheter som utkast.")
    p.add_argument("fil", help="JSON-filen, eller - för stdin")
    p.add_argument("--redaktor", required=True, help="E-post till redaktören som läser in")
    p.add_argument("--prova", action="store_true", help="Kontrollera filen och visa resultatet utan att spara")
    a = p.parse_args(argv)
    data = json.load(sys.stdin if a.fil == "-" else open(a.fil, encoding="utf-8"))
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn:
        try:
            res = las_in(conn, data, a.redaktor, datetime.now(timezone.utc))
        except Ogiltig as e:
            raise SystemExit(str(e)) from None
        if a.prova:
            conn.rollback()
        else:
            conn.commit()
    print(f"{res['nya'] + res['oforandrade']} motstridigheter: {res['nya']} nya utkast, {res['oforandrade']} fanns redan."
          + (" Provet sparades inte." if a.prova else ""))


if __name__ == "__main__":
    main()
