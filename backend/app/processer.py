"""Processer ur reglementen och delegationsordningar (#152).

En process är en arbetsgång som redaktionen har valt att beskriva (GLOSSARY.md), till exempel kallelse till
sammanträde. AI hittar och grupperar inte processer på egen hand. Redaktionen bestämmer listan (`lagg_till`), och
skillen `harnosandskollen-styrande-dokument` fyller i stegen ur de 25 reglementena och delegationsordningarna
(`las_in`, formatet i docs/styrande-dokument.md). Backend anropar ingen AI (ADR-0009).

Ett steg anger vem som gör något, vad som görs, när eller inom vilken tidsfrist (om dokumentet anger det) och källan:
ett ordagrant citat med dokument, version, sida och paragraf. Stegen kan hämtas ur flera dokument.

Processen går som en helhet, med alla sina steg, från utkast via granskad till publicerad (ADR-0002). Ingen godkänner
en process som hen själv har lagt till eller läst in steg i. När ett dokument som ett steg citerar får en ny version
märks steget "Dokumentet har ändrats" tills en redaktör har tagit ställning. Processen förblir publicerad.

`python -m app.processer FIL --redaktor EPOST` läser in skillens fil. Med `-` läses filen från stdin, så att den kan
skickas till servern. Med `--prova` kontrolleras filen utan att något sparas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from typing import Any

import psycopg

from . import db, motstridigheter
from .motstridigheter import EjTillatet, Konflikt, Ogiltig, citerat_stalle, jamforbar

GRANSKNING = ("utkast", "granskad", "publicerad", "avvisad", "aterkallad")


# Listan


def lagg_till(conn: psycopg.Connection, data: Any, redaktor: str, nu: datetime) -> dict:
    """En redaktör lägger till en process på listan: {namn, beskrivning}. Den blir ett utkast utan steg."""
    if not isinstance(data, dict):
        raise Ogiltig("Ange processens namn")
    namn = " ".join(str(data.get("namn") or "").split())
    if not namn:
        raise Ogiltig("Ange processens namn")
    if len(namn) > 80:
        raise Ogiltig("Namnet är längre än 80 tecken")
    beskrivning = " ".join(str(data.get("beskrivning") or "").split()) or None
    if conn.execute("SELECT 1 FROM process WHERE lower(namn) = lower(%s)", (namn,)).fetchone():
        raise Konflikt(f"Processen {namn} finns redan på listan")
    pid = conn.execute(
        "INSERT INTO process (namn, beskrivning, ordning, redaktorer, skapad, skapad_av) "
        "VALUES (%s, %s, (SELECT coalesce(max(ordning), 0) + 1 FROM process), %s, %s, %s) RETURNING id",
        (namn, beskrivning, [redaktor], nu, redaktor),
    ).fetchone()["id"]
    conn.commit()
    return las(conn, pid, redaktion=True)


# Inläsning från skillen


def _text(v: Any, var: str, falt: str, kravs: bool = True) -> str | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        if kravs:
            raise Ogiltig(f"{var}: {falt} saknas")
        return None
    if not isinstance(v, str):
        raise Ogiltig(f"{var}: {falt} ska vara en text")
    return " ".join(v.split())


def tolka(conn: psycopg.Connection, data: Any) -> list[dict]:
    """Kontrollerar skillens fil och ger processerna med sina steg. Ogiltig med processens och stegets nummer."""
    if not isinstance(data, dict) or not isinstance(data.get("processer"), list):
        raise Ogiltig("Filen ska ha formen {\"processer\": [...]}")
    listan = {r["namn"].casefold(): r for r in conn.execute("SELECT * FROM process ORDER BY ordning")}
    cache: dict = {}
    ut = []
    sedda: set[int] = set()
    for i, p in enumerate(data["processer"], 1):
        var = f"Process {i}"
        if not isinstance(p, dict):
            raise Ogiltig(f"{var}: ska vara ett objekt")
        if okanda := set(p) - {"process", "steg"}:
            raise Ogiltig(f"{var}: okända fält {', '.join(sorted(okanda))}")
        namn = _text(p.get("process"), var, "processens namn")
        rad = listan.get(namn.casefold())
        if rad is None:
            raise Ogiltig(f"{var}: {namn} finns inte på redaktionens lista. En redaktör lägger till den under "
                          "Redaktion → Processer")
        var = f"{var} ({rad['namn']})"
        if rad["id"] in sedda:
            raise Ogiltig(f"{var}: processen finns två gånger i filen")
        sedda.add(rad["id"])
        steg_in = p.get("steg")
        if not isinstance(steg_in, list) or not steg_in:
            raise Ogiltig(f"{var}: stegen saknas")
        steg = []
        for j, s in enumerate(steg_in, 1):
            sv = f"{var}, steg {j}"
            if not isinstance(s, dict):
                raise Ogiltig(f"{sv}: ska vara ett objekt med vem, vad, när och källa")
            if okanda := set(s) - {"vem", "vad", "nar", "kalla"}:
                raise Ogiltig(f"{sv}: okända fält {', '.join(sorted(okanda))}")
            vem = _text(s.get("vem"), sv, "vem som gör något")
            vad = _text(s.get("vad"), sv, "vad som görs")
            nar = _text(s.get("nar"), sv, "när", kravs=False)
            if s.get("kalla") is None:
                raise Ogiltig(f"{sv}: källan saknas. Ange dokument, sida, paragraf och ett ordagrant citat")
            _, kalla = citerat_stalle(conn, s["kalla"], f"{sv}, källan", cache, paragraf=True)
            steg.append({"vem": vem, "vad": vad, "nar": nar} | kalla)
        delar = [f"{s['vem']}|{s['vad']}|{s['nar']}|{s['dokument_id']}|{s['sida']}|{s['paragraf']}|"
                 f"{jamforbar(s['text'])}" for s in steg]
        nyckel = hashlib.sha256("\n".join(delar).encode()).hexdigest()[:24]
        ut.append({"process": rad, "steg": steg, "nyckel": nyckel})
    return ut


def las_in(conn: psycopg.Connection, data: Any, redaktor: str, nu: datetime) -> dict:
    """Läser in skillens steg som utkast. Stegen ersätter processens tidigare steg, och processen blir ett utkast som
    granskas på nytt. Samma steg som redan finns läses inte in igen. En publicerad process ändras inte: håller den inte
    längre återkallar en utgivare den först. Committar inte."""
    nya = oforandrade = 0
    for f in tolka(conn, data):
        p = f["process"]
        # Samma steg igen är oförändrade, utom i en återkallad process: då blir de ett nytt utkast.
        if p["stegnyckel"] == f["nyckel"] and p["status"] != "aterkallad":
            oforandrade += 1
            continue
        if p["status"] == "publicerad":
            raise Konflikt(f"{p['namn']} är publicerad. Ta ställning till de ändrade stegen, eller be en utgivare "
                           "återkalla processen innan nya steg läses in")
        if p["status"] == "avvisad":
            raise Konflikt(f"{p['namn']} är avvisad och ska inte beskrivas")
        conn.execute("DELETE FROM process_steg WHERE process_id = %s", (p["id"],))
        for n, s in enumerate(f["steg"], 1):
            conn.execute(
                "INSERT INTO process_steg (process_id, ordning, vem, vad, nar, dokument_id, version, sida, paragraf, "
                "citat) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (p["id"], n, s["vem"], s["vad"], s["nar"], s["dokument_id"], s["version"], s["sida"], s["paragraf"],
                 s["text"]),
            )
        conn.execute(
            "UPDATE process SET status = 'utkast', stegnyckel = %s, steg_inlasta = %s, granskad_av = NULL, "
            "granskad = NULL, redaktorer = CASE WHEN %s = ANY(redaktorer) THEN redaktorer "
            "ELSE array_append(redaktorer, %s) END WHERE id = %s",
            (f["nyckel"], nu, redaktor, redaktor, p["id"]),
        )
        nya += 1
    return {"nya": nya, "oforandrade": oforandrade}


# Nya versioner av citerade dokument


def markera_andrat(conn: psycopg.Connection, dokument_id: int, dag: date) -> None:
    """Dokumentet har fått en ny version: stegen som citerar det märks "Dokumentet har ändrats". Bara de stegen."""
    conn.execute(
        "UPDATE process_steg s SET dokument_andrat = %s FROM process p WHERE p.id = s.process_id "
        "AND s.dokument_id = %s AND s.dokument_andrat IS NULL AND p.status <> 'avvisad'", (dag, dokument_id))


def ta_stallning(conn: psycopg.Connection, pid: int, sid: int, redaktor: str) -> dict:
    """En redaktör har läst den nya versionen och steget håller: märkningen tas bort och versionen blir den senaste.
    Citatet ska stå kvar på sidan i den nya versionen. Annars läses nya steg in."""
    s = conn.execute("SELECT * FROM process_steg WHERE id = %s AND process_id = %s", (sid, pid)).fetchone()
    if s is None:
        raise LookupError(f"Steget {sid} finns inte i processen {pid}")
    if s["dokument_andrat"] is None:
        raise Konflikt("Dokumentet som steget citerar har inte ändrats")
    d = conn.execute("SELECT version, sidor FROM styrande_dokument_version WHERE dokument_id = %s "
                     "ORDER BY version DESC LIMIT 1", (s["dokument_id"],)).fetchone()
    sidor = d["sidor"] or []
    if not 1 <= s["sida"] <= len(sidor) or jamforbar(s["citat"]) not in jamforbar(sidor[s["sida"] - 1]):
        raise Konflikt(f"Citatet står inte längre på sidan {s['sida']} i version {d['version']}. "
                       "Kör skillen för processen och läs in nya steg")
    conn.execute("UPDATE process_steg SET dokument_andrat = NULL, version = %s WHERE id = %s", (d["version"], sid))
    conn.commit()
    return las(conn, pid, redaktion=True)


# Granskning


def _rad(conn: psycopg.Connection, pid: int) -> dict:
    r = conn.execute("SELECT * FROM process WHERE id = %s", (pid,)).fetchone()
    if r is None:
        raise LookupError(f"Processen {pid} finns inte")
    return r


def _godkann(conn: psycopg.Connection, pid: int, utgivare: str, fran: str) -> dict:
    r = _rad(conn, pid)
    if utgivare in r["redaktorer"]:
        raise EjTillatet("Ingen godkänner en process som hen själv har lagt till eller läst in steg i")
    if r["status"] != fran:
        raise Konflikt(f"Processen är {r['status']}, inte {fran}")
    if not conn.execute("SELECT 1 FROM process_steg WHERE process_id = %s", (pid,)).fetchone():
        raise Konflikt("Processen har inga steg än. Skillen läser in dem")
    return r


def granska(conn: psycopg.Connection, pid: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, pid, utgivare, "utkast")
    conn.execute("UPDATE process SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, nu, pid))
    conn.commit()
    return las(conn, pid, redaktion=True)


def publicera(conn: psycopg.Connection, pid: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, pid, utgivare, "granskad")
    conn.execute("UPDATE process SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, nu, pid))
    conn.commit()
    return las(conn, pid, redaktion=True)


def _motivering(data: Any, vad: str) -> str:
    m = (data.get("motivering") or "").strip() if isinstance(data, dict) else ""
    if not m:
        raise Ogiltig(f"Ange varför processen {vad}")
    return m


def avvisa(conn: psycopg.Connection, pid: int, data: Any, utgivare: str, nu: datetime) -> dict:
    """En process som inte ska beskrivas, eller vars steg inte håller, avvisas med motivering."""
    r = _rad(conn, pid)
    if r["status"] not in ("utkast", "granskad"):
        raise Konflikt(f"Bara ett utkast eller en granskad process kan avvisas, den här är {r['status']}")
    conn.execute("UPDATE process SET status = 'avvisad', avvisad_av = %s, avvisad = %s, avvisning = %s WHERE id = %s",
                 (utgivare, nu, _motivering(data, "avvisas"), pid))
    conn.commit()
    return las(conn, pid, redaktion=True)


def aterkalla(conn: psycopg.Connection, pid: int, data: Any, utgivare: str, nu: datetime) -> dict:
    """En utgivare återkallar en publicerad process, med motivering. Skillen kan sedan läsa in nya steg."""
    r = _rad(conn, pid)
    if r["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad process kan återkallas, den här är {r['status']}")
    conn.execute("UPDATE process SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, aterkallelse = %s "
                 "WHERE id = %s", (utgivare, nu, _motivering(data, "återkallas"), pid))
    conn.commit()
    return las(conn, pid, redaktion=True)


# Läsning


def _steg(conn: psycopg.Connection, pids: list[int]) -> dict[int, list[dict]]:
    rader = conn.execute(
        "SELECT s.*, d.titel FROM process_steg s JOIN styrande_dokument d ON d.id = s.dokument_id "
        "WHERE s.process_id = ANY(%s) ORDER BY s.process_id, s.ordning", (pids,)).fetchall()
    vid = motstridigheter.vid_stallen(conn, rader)
    ut: dict[int, list[dict]] = {p: [] for p in pids}
    for s, m in zip(rader, vid):
        ut[s["process_id"]].append({
            "id": s["id"], "ordning": s["ordning"], "vem": s["vem"], "vad": s["vad"], "nar": s["nar"],
            "kalla": {"dokument_id": s["dokument_id"], "titel": s["titel"], "version": s["version"], "sida": s["sida"],
                      "paragraf": s["paragraf"], "text": s["citat"],
                      "lank": f"/politik/styrande-dokument/{s['dokument_id']}",
                      "kopia": f"/api/styrande-dokument/{s['dokument_id']}/versioner/{s['version']}#page={s['sida']}"},
            "dokument_andrat": s["dokument_andrat"].isoformat() if s["dokument_andrat"] else None,
            "motstridigheter": m,
        })
    return ut


def _iso(v: Any) -> str | None:
    return v.isoformat() if v else None


def _ut(r: dict, steg: list[dict], redaktion: bool) -> dict:
    dokument: dict[int, dict] = {}
    for s in steg:
        dokument.setdefault(s["kalla"]["dokument_id"], {"id": s["kalla"]["dokument_id"], "titel": s["kalla"]["titel"]})
    ut = {
        "id": r["id"], "namn": r["namn"], "beskrivning": r["beskrivning"], "ordning": r["ordning"],
        "publicerad": _iso(r["publicerad"]), "steg": steg, "dokument": list(dokument.values()),
        "dokument_andrat": any(s["dokument_andrat"] for s in steg),
    }
    if redaktion:
        ut |= {
            "granskning": r["status"], "redaktorer": r["redaktorer"], "skapad": _iso(r["skapad"]),
            "skapad_av": r["skapad_av"], "steg_inlasta": _iso(r["steg_inlasta"]),
            "granskad_av": r["granskad_av"], "granskad": _iso(r["granskad"]), "publicerad_av": r["publicerad_av"],
            "avvisad_av": r["avvisad_av"], "avvisning": r["avvisning"], "avvisad": _iso(r["avvisad"]),
            "aterkallad_av": r["aterkallad_av"], "aterkallelse": r["aterkallelse"], "aterkallad": _iso(r["aterkallad"]),
        }
    return ut


def las(conn: psycopg.Connection, pid: int, redaktion: bool = False) -> dict:
    r = _rad(conn, pid)
    if not redaktion and r["status"] != "publicerad":
        raise LookupError(f"Processen {pid} finns inte")
    return _ut(r, _steg(conn, [pid])[pid], redaktion)


def publicerade(conn: psycopg.Connection) -> list[dict]:
    """De publicerade processerna i listans ordning, med sina steg."""
    rader = conn.execute("SELECT * FROM process WHERE status = 'publicerad' ORDER BY ordning, id").fetchall()
    steg = _steg(conn, [r["id"] for r in rader])
    return [_ut(r, steg[r["id"]], False) for r in rader]


def for_dokument(conn: psycopg.Connection, dokument_id: int) -> list[dict]:
    """De publicerade processerna som dokumentet ingår i, med antalet steg ur dokumentet."""
    return [{"id": r["id"], "namn": r["namn"], "steg": r["steg"]} for r in conn.execute(
        "SELECT p.id, p.namn, count(*) AS steg FROM process p JOIN process_steg s ON s.process_id = p.id "
        "WHERE p.status = 'publicerad' AND s.dokument_id = %s GROUP BY p.id ORDER BY p.ordning, p.id", (dokument_id,))]


def antal_per_dokument(conn: psycopg.Connection) -> dict[int, int]:
    """Antalet publicerade processer som varje dokument ingår i."""
    return {r["id"]: r["antal"] for r in conn.execute(
        "SELECT s.dokument_id AS id, count(DISTINCT p.id) AS antal FROM process p "
        "JOIN process_steg s ON s.process_id = p.id WHERE p.status = 'publicerad' GROUP BY 1")}


def redaktionen(conn: psycopg.Connection) -> dict:
    """Redaktionens vy: hela listan i alla granskningsstatusar, med stegen. Publicerade processer med ändrade
    dokument står för sig."""
    rader = conn.execute(
        "SELECT * FROM process ORDER BY array_position(%s::text[], status), ordning, id", (list(GRANSKNING),)
    ).fetchall()
    steg = _steg(conn, [r["id"] for r in rader])
    alla = [_ut(r, steg[r["id"]], True) for r in rader]
    return {"processer": alla,
            "andrade": [p for p in alla if p["granskning"] == "publicerad" and p["dokument_andrat"]]}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.processer",
                                description="Läser in skillens steg för redaktionens processer som utkast.")
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
        except (Ogiltig, Konflikt) as e:
            raise SystemExit(str(e)) from None
        if a.prova:
            conn.rollback()
        else:
            conn.commit()
    print(f"{res['nya'] + res['oforandrade']} processer: {res['nya']} med nya steg som utkast, "
          f"{res['oforandrade']} oförändrade." + (" Provet sparades inte." if a.prova else ""))


if __name__ == "__main__":
    main()
