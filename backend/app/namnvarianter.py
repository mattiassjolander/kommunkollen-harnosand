"""Namnvarianter i ledamotsregistret (#165).

Efter varje tolkning (insamling och omtolkning) städas registret i tre steg:

1. **Felaktiga namn tas bort.** Ett namn som tolkningen inte längre ger ("Glenn Sehlin, §§ 131-138",
   "Tom plats för Ester Sundin Hemström") och som inte förekommer i någon närvarolista eller votering tas bort.
   Var det sammanslaget med en person, följer det rensade namnet med till personen.
2. **Bindestreck och mellanslag slås ihop automatiskt.** Namn som är identiska när bindestreck och extra
   mellanslag tas bort ("Höglund-Bystedt", "Höglund- Bystedt", "Höglund Bystedt") är samma person.
   Huvudnamnet är den stavning som förekommer oftast.
3. **Andra skillnader blir förslag.** Samma förnamn och sista efternamn (eller en liten skillnad i stavningen),
   samma parti och aldrig i samma närvarolista. En redaktör bekräftar eller avvisar (ADR-0002).

Manuella beslut har företräde. En automatisk regel delar aldrig upp en sammanslagning och slår aldrig ihop två
personer som en redaktör har delat upp. Ett avvisat förslag kommer inte tillbaka.
"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

import psycopg

from . import ledamoter
from .ledamoter import Konflikt, flytta
from .protokolltolkning import rensat_namn

AUTOMATIK = "automatik"


def normaliserad(namn: str) -> str:
    """Namnet utan bindestreck och extra mellanslag."""
    return " ".join(re.sub(r"[-‐‑–]", " ", namn).split())


def underhall(conn: psycopg.Connection) -> dict[str, list[dict]]:
    """Kör de tre stegen och returnerar vad som ändrades. Sökindexet uppdateras av den som anropar."""
    return {
        "borttagna": _ta_bort_felaktiga(conn),
        "sammanslagna": _sla_ihop_varianter(conn),
        "forslag": _foresla(conn),
    }


_NAMNEN = """
    SELECT l.id, l.namn, l.huvud_id, coalesce(l.huvud_id, l.id) AS person,
           (SELECT count(*) FROM narvaro n WHERE n.namn = l.namn AND n.kategori <> 'ovrig') AS antal,
           EXISTS (SELECT 1 FROM rost r WHERE r.namn = l.namn OR r.ersatt = l.namn) AS i_rost
    FROM ledamot l
"""


def _delade(conn: psycopg.Connection) -> set[frozenset[int]]:
    """Personpar som en redaktör har delat upp. De slås inte ihop och föreslås inte igen."""
    return {
        frozenset((r["a"], r["b"]))
        for r in conn.execute(
            """
            SELECT coalesce(a.huvud_id, a.id) AS a, coalesce(b.huvud_id, b.id) AS b
            FROM ledamot_handelse h JOIN ledamot a ON a.id = h.ledamot_id JOIN ledamot b ON b.id = h.tidigare_huvud_id
            WHERE h.typ = 'uppdelning'
            """
        )
    }


def _huvudnamn(conn: psycopg.Connection, person: int) -> str:
    return conn.execute("SELECT namn FROM ledamot WHERE id = %s", (person,)).fetchone()["namn"]


# 1. Felaktiga namn


def _ta_bort_felaktiga(conn: psycopg.Connection) -> list[dict]:
    delade = _delade(conn)
    ut: list[dict] = []
    kandidater = [r for r in conn.execute(_NAMNEN).fetchall()
                  if r["antal"] == 0 and not r["i_rost"] and rensat_namn(r["namn"]) != r["namn"]]
    for k in kandidater:
        r = conn.execute(f"{_NAMNEN} WHERE l.id = %s", (k["id"],)).fetchone()
        person = r["person"]
        andra = conn.execute(f"{_NAMNEN} WHERE coalesce(l.huvud_id, l.id) = %s AND l.id <> %s ORDER BY antal DESC, l.namn",
                             (person, r["id"])).fetchall()
        rent = rensat_namn(r["namn"])
        foljde_med = None
        if andra and rent:
            # Det felaktiga namnet var sammanslaget med en person: det rensade namnet hör till samma person.
            ren = conn.execute("SELECT coalesce(huvud_id, id) AS person FROM ledamot WHERE namn = %s", (rent,)).fetchone()
            if ren and ren["person"] != person and frozenset((ren["person"], person)) not in delade:
                flytta(conn, person, ren["person"], AUTOMATIK, automatisk=True)
                foljde_med = rent
                andra = conn.execute(
                    f"{_NAMNEN} WHERE coalesce(l.huvud_id, l.id) = %s AND l.id <> %s ORDER BY antal DESC, l.namn",
                    (person, r["id"])).fetchall()
        refererat = conn.execute(
            """SELECT EXISTS (SELECT 1 FROM partitillhorighet WHERE ledamot_id = %(id)s)
                   OR EXISTS (SELECT 1 FROM personuppgift WHERE ledamot_id = %(id)s)
                   OR EXISTS (SELECT 1 FROM valkoppling WHERE ledamot_id = %(id)s) AS ja""",
            {"id": r["id"]},
        ).fetchone()["ja"]
        if refererat and not andra:
            continue  # uppgifter om personen finns bara under det här namnet, så det står kvar
        ny_person = None
        if andra:
            ny_person = person
            if r["huvud_id"] is None:
                # Namnet var huvudnamn. Det namn som förekommer oftast blir nytt huvudnamn.
                ny_person = andra[0]["id"]
                conn.execute("UPDATE ledamot SET huvud_id = NULL WHERE id = %s", (ny_person,))
                conn.execute("UPDATE ledamot SET huvud_id = %s WHERE huvud_id = %s", (ny_person, r["id"]))
            for tabell in ("partitillhorighet", "personuppgift"):
                conn.execute(f"UPDATE {tabell} SET ledamot_id = %s WHERE ledamot_id = %s", (ny_person, r["id"]))
            conn.execute(
                """UPDATE valkoppling k SET ledamot_id = %(ny)s WHERE ledamot_id = %(id)s AND NOT EXISTS (
                       SELECT 1 FROM valkoppling x WHERE x.valar = k.valar AND x.kandidatnummer = k.kandidatnummer
                       AND x.ledamot_id = %(ny)s)""",
                {"ny": ny_person, "id": r["id"]},
            )
            conn.execute("DELETE FROM valkoppling WHERE ledamot_id = %s", (r["id"],))
        conn.execute(
            """INSERT INTO ledamot_handelse (typ, ledamot_id, namn, huvud_id, tidigare_huvud_id, redaktor, automatisk)
               VALUES ('borttagning', %s, %s, %s, %s, %s, true)""",
            (r["id"], r["namn"], ny_person, r["huvud_id"], AUTOMATIK),
        )
        conn.execute("DELETE FROM ledamot WHERE id = %s", (r["id"],))
        ut.append({"namn": r["namn"], "rensat": rent, "foljde_med": foljde_med,
                   "person": _huvudnamn(conn, ny_person) if ny_person else None})
    return ut


# 2. Bindestreck och mellanslag


def _sla_ihop_varianter(conn: psycopg.Connection) -> list[dict]:
    grupper: dict[str, list[int]] = defaultdict(list)
    for r in conn.execute(_NAMNEN).fetchall():
        if r["antal"]:
            grupper[normaliserad(r["namn"])].append(r["id"])
    delade = _delade(conn)
    ut: list[dict] = []
    for ids in grupper.values():
        if len(ids) < 2:
            continue
        rader = conn.execute(f"{_NAMNEN} WHERE l.id = ANY(%s) ORDER BY antal DESC, l.namn", (ids,)).fetchall()
        if len({r["person"] for r in rader}) < 2:
            continue
        mal = rader[0]["person"]  # personen med den stavning som förekommer oftast
        med = {mal}
        for r in rader[1:]:
            q = conn.execute("SELECT coalesce(huvud_id, id) AS p FROM ledamot WHERE id = %s", (r["id"],)).fetchone()["p"]
            if q in med:
                continue
            if any(frozenset((q, m)) in delade for m in med):
                continue  # en redaktör har delat upp dem
            flytta(conn, mal, q, AUTOMATIK, automatisk=True)
            med.add(q)
            ut.append({"namn": r["namn"], "huvudnamn": _huvudnamn(conn, mal)})
    return ut


# 3. Förslag


def _avstand(a: str, b: str) -> int:
    rad = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        ny = [i]
        for j, y in enumerate(b, 1):
            ny.append(min(rad[j] + 1, ny[j - 1] + 1, rad[j - 1] + (x != y)))
        rad = ny
    return rad[-1]


def _nara(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 4 and _avstand(a, b) <= 1)


def liknar(a: str, b: str) -> str | None:
    """Skälet till att två namn kan vara samma person, eller None."""
    ta, tb = normaliserad(a).casefold().split(), normaliserad(b).casefold().split()
    if len(ta) < 2 or len(tb) < 2 or ta == tb:
        return None
    (fa, la), (fb, lb) = (ta[0], ta[-1]), (tb[0], tb[-1])
    if fa == fb and la == lb:
        return "Samma förnamn och efternamn, olika mellannamn"
    if (fa == fb and _nara(la, lb)) or (_nara(fa, fb) and la == lb):
        return "Samma förnamn och efternamn, med en liten skillnad i stavningen"
    return None


def _foresla(conn: psycopg.Connection) -> list[dict]:
    personer: dict[int, dict] = defaultdict(lambda: {"namn": {}, "partier": set(), "sammantraden": set()})
    for r in conn.execute(
        """SELECT coalesce(l.huvud_id, l.id) AS person, l.id, l.namn, n.parti, n.sammantrade_id
           FROM narvaro n JOIN ledamot l ON l.namn = n.namn WHERE n.kategori <> 'ovrig'"""
    ):
        p = personer[r["person"]]
        p["namn"][r["id"]] = r["namn"]
        p["sammantraden"].add(r["sammantrade_id"])
        if r["parti"]:
            p["partier"].add(r["parti"])
    delade = _delade(conn)
    befintliga = conn.execute(
        """SELECT f.id, f.status, coalesce(a.huvud_id, a.id) AS pa, coalesce(b.huvud_id, b.id) AS pb
           FROM namnforslag f JOIN ledamot a ON a.id = f.ledamot_id JOIN ledamot b ON b.id = f.annat_id"""
    ).fetchall()
    avvisade = {frozenset((r["pa"], r["pb"])) for r in befintliga if r["status"] == "avvisad"}

    kandidater: dict[frozenset[int], tuple[int, int, str]] = {}
    for p, q in combinations(sorted(personer), 2):
        a, b = personer[p], personer[q]
        par = frozenset((p, q))
        if not (a["partier"] & b["partier"]) or a["sammantraden"] & b["sammantraden"] or par in delade or par in avvisade:
            continue
        for (ia, na), (ib, nb) in ((x, y) for x in sorted(a["namn"].items()) for y in sorted(b["namn"].items())):
            if skal := liknar(na, nb):
                partier = ", ".join(sorted(a["partier"] & b["partier"]))
                kandidater[par] = (min(ia, ib), max(ia, ib),
                                   f"{skal}. Samma parti ({partier}), aldrig i samma närvarolista.")
                break

    for r in befintliga:
        if r["status"] != "forslag":
            continue
        if frozenset((r["pa"], r["pb"])) in kandidater:
            del kandidater[frozenset((r["pa"], r["pb"]))]  # finns redan
        else:
            conn.execute("DELETE FROM namnforslag WHERE id = %s", (r["id"],))
    ut: list[dict] = []
    for a, b, skal in kandidater.values():
        if conn.execute(
            """INSERT INTO namnforslag (ledamot_id, annat_id, skal, status) VALUES (%s, %s, %s, 'forslag')
               ON CONFLICT DO NOTHING RETURNING id""",
            (a, b, skal),
        ).fetchone():
            namn = {r["id"]: r["namn"] for r in conn.execute("SELECT id, namn FROM ledamot WHERE id = ANY(%s)", ([a, b],))}
            ut.append({"namn": namn[a], "annat_namn": namn[b], "skal": skal})
    return ut


# Redaktionens beslut


def lista_forslag(conn: psycopg.Connection, status: str = "forslag") -> list[dict]:
    rader = conn.execute(
        """SELECT f.*, a.namn AS namn, b.namn AS annat_namn,
                  coalesce(a.huvud_id, a.id) AS pa, coalesce(b.huvud_id, b.id) AS pb
           FROM namnforslag f JOIN ledamot a ON a.id = f.ledamot_id JOIN ledamot b ON b.id = f.annat_id
           WHERE f.status = %(status)s
             -- Ett förslag vars namn redan slagits ihop på annat sätt tas bort vid nästa tolkning.
             AND (f.status <> 'forslag' OR coalesce(a.huvud_id, a.id) <> coalesce(b.huvud_id, b.id))
           ORDER BY a.namn, b.namn""",
        {"status": status},
    ).fetchall()
    personer = {p["id"]: p for p in ledamoter.lista(conn)}
    return [_forslag(r, personer) for r in rader]


def _forslag(r: dict, personer: dict[int, dict]) -> dict:
    def sida(namn: str, person: int) -> dict:
        p = personer.get(person, {})
        return {"namn": namn, "ledamot": {k: p.get(k) for k in (
            "id", "namn", "andra_namn", "partier", "organ", "antal_sammantraden", "senast")} if p else None}

    return {
        "id": r["id"], "status": r["status"], "skal": r["skal"], "skapad": r["skapad"],
        "beslutad_av": r["beslutad_av"], "beslutad": r["beslutad"],
        "namn": [sida(r["namn"], r["pa"]), sida(r["annat_namn"], r["pb"])],
    }


def _las(conn: psycopg.Connection, forslag_id: int) -> dict:
    rad = conn.execute(
        """SELECT f.*, a.namn AS namn, b.namn AS annat_namn,
                  coalesce(a.huvud_id, a.id) AS pa, coalesce(b.huvud_id, b.id) AS pb,
                  (SELECT count(*) FROM narvaro n JOIN ledamot l ON l.namn = n.namn
                   WHERE coalesce(l.huvud_id, l.id) = coalesce(a.huvud_id, a.id) AND n.kategori <> 'ovrig') AS antal_a,
                  (SELECT count(*) FROM narvaro n JOIN ledamot l ON l.namn = n.namn
                   WHERE coalesce(l.huvud_id, l.id) = coalesce(b.huvud_id, b.id) AND n.kategori <> 'ovrig') AS antal_b
           FROM namnforslag f JOIN ledamot a ON a.id = f.ledamot_id JOIN ledamot b ON b.id = f.annat_id
           WHERE f.id = %s""",
        (forslag_id,),
    ).fetchone()
    if rad is None:
        raise LookupError(f"Namnförslaget {forslag_id} finns inte")
    return rad


def besluta(conn: psycopg.Connection, forslag_id: int, bekrafta: bool, redaktor: str) -> dict:
    """Bekräftar (namnen slås ihop, med namnet som förekommer oftast som huvudnamn) eller avvisar ett förslag."""
    r = _las(conn, forslag_id)
    if r["status"] != "forslag":
        raise Konflikt("Förslaget är redan beslutat")
    if bekrafta:
        if r["pa"] == r["pb"]:
            raise Konflikt("Namnen hör redan till samma person")
        huvud, annan = (r["pa"], r["pb"]) if r["antal_a"] >= r["antal_b"] else (r["pb"], r["pa"])
        flytta(conn, huvud, annan, redaktor)
        ledamoter._uppdatera_sokindex(conn)
    conn.execute(
        "UPDATE namnforslag SET status = %s, beslutad_av = %s, beslutad = now() WHERE id = %s",
        ("bekraftad" if bekrafta else "avvisad", redaktor, forslag_id),
    )
    personer = {p["id"]: p for p in ledamoter.lista(conn)}
    return _forslag(_las(conn, forslag_id), personer)


def skriv_plan(plan: dict[str, list[dict]]) -> list[str]:
    """Planen som text, för kommandoraden."""
    rader = [f"Namn som tas bort ur registret ({len(plan['borttagna'])}):"]
    for x in plan["borttagna"]:
        rad = f"  {x['namn']}"
        if x["person"]:
            rad += f" (var sammanslaget med {x['person']}"
            rad += f", {x['foljde_med']} följer med)" if x["foljde_med"] else ")"
        rader.append(rad)
    rader.append(f"Namn som slås ihop automatiskt ({len(plan['sammanslagna'])}):")
    rader += [f"  {x['namn']} → {x['huvudnamn']}" for x in plan["sammanslagna"]]
    rader.append(f"Nya förslag till redaktionen ({len(plan['forslag'])}):")
    rader += [f"  {x['namn']} / {x['annat_namn']}: {x['skal']}" for x in plan["forslag"]]
    return rader
