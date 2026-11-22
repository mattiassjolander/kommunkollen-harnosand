"""Förslag på fastställda partitillhörigheter ur protokollen (#100, del 2, ADR-0006).

För varje person räknas partiet som närvarolistorna anger fram, med publicerade rättelser av partiet men utan
härledda partier. En följd av sammanträden med samma parti blir en föreslagen period. Ett nytt parti blir en
egen period först när det står vid minst tre sammanträden i följd, eller två i följd vid personens sista
sammanträden. Annars är förekomsten en krock: protokollet anger ett annat parti än perioden, troligen ett läsfel.

- Den första perioden börjar vid personens första sammanträde, även ett utan parti.
- En ny period börjar vid det första sammanträdet med det nya partiet, och den föregående slutar dagen före.
- Den sista perioden gäller tills vidare.

Förslag ges bara för personer som inte har någon period som utkast, granskad eller publicerad, och som har minst
ett angivet parti. Förslagen räknas fram när de hämtas och sparas inte.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import psycopg

from .sources.harnosand import organ_ref

STABIL = 3
STABIL_VID_SLUTET = 2


@dataclass(frozen=True)
class Forekomst:
    datum: date
    sammantrade_id: int
    organ: str
    parti: str | None


def _foljder(angivna: list[Forekomst]) -> list[list[Forekomst]]:
    foljder: list[list[Forekomst]] = []
    for f in angivna:
        if foljder and foljder[-1][0].parti == f.parti:
            foljder[-1].append(f)
        else:
            foljder.append([f])
    return foljder


def perioder(forekomster: list[Forekomst]) -> list[dict]:
    """Föreslagna perioder för en person: [{parti, fran, till, forekomster, krockar}], äldst först.
    forekomster är en per sammanträde, sorterade på datum. Tom lista om inget parti anges."""
    angivna = [f for f in forekomster if f.parti]
    if not angivna:
        return []
    foljder = _foljder(angivna)
    stabila = [i for i, fl in enumerate(foljder)
               if len(fl) >= STABIL or (i == len(foljder) - 1 and len(fl) >= STABIL_VID_SLUTET)]
    if len({f.parti for f in angivna}) == 1:
        stabila = [0]
    if not stabila:
        # Inget parti består: det vanligaste gäller, vid lika det senaste.
        antal = Counter(f.parti for f in angivna)
        bast = max(antal.values())
        parti = next(f.parti for f in reversed(angivna) if antal[f.parti] == bast)
        starter = [(forekomster[0].datum, parti)]
    else:
        starter = []
        for i in stabila:
            parti = foljder[i][0].parti
            if starter and starter[-1][1] == parti:
                continue
            starter.append((foljder[i][0].datum if starter else forekomster[0].datum, parti))
    ut = []
    for j, (fran, parti) in enumerate(starter):
        till = starter[j + 1][0] - timedelta(days=1) if j + 1 < len(starter) else None
        inom = [f for f in forekomster if f.datum >= fran and (till is None or f.datum <= till)]
        ut.append({"parti": parti, "fran": fran, "till": till, "forekomster": inom,
                   "krockar": [f for f in inom if f.parti and f.parti != parti]})
    return ut


def _sammantrade(f: Forekomst) -> dict:
    return {"id": f.sammantrade_id, "datum": f.datum, "organ": organ_ref(f.organ)}


def _belagg(p: dict) -> dict:
    inom = p["forekomster"]
    egna = [f for f in inom if f.parti == p["parti"]]
    return {
        "parti": p["parti"], "fran": p["fran"], "till": p["till"],
        "antal_per_parti": dict(Counter(f.parti for f in inom if f.parti).most_common()),
        "utan_parti": sum(1 for f in inom if not f.parti),
        "forsta": egna[0].datum if egna else None,
        "sista": egna[-1].datum if egna else None,
        "exempel": _sammantrade(egna[0]) if egna else None,
        "krockar": [_sammantrade(f) | {"parti": f.parti} for f in p["krockar"]],
    }


def forslag(conn: psycopg.Connection) -> list[dict]:
    """Förslagen per person: [{ledamot: {id, namn}, perioder: [...]}], i namnordning."""
    rader = conn.execute(
        """
        SELECT p.id AS person, p.namn AS person_namn, s.id AS sammantrade_id, s.datum, s.organ,
               CASE WHEN r.id IS NOT NULL THEN r.nytt #>> '{}' ELSE n.parti END AS parti
        FROM narvaro n
        JOIN ledamot l ON l.namn = n.namn
        JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id)
        JOIN sammantrade s ON s.id = n.sammantrade_id
        LEFT JOIN rattelse r ON r.sammantrade_id = n.sammantrade_id AND r.objekt = 'narvaro' AND r.namn = n.namn
             AND r.falt = 'parti' AND r.status = 'publicerad'
        WHERE n.kategori <> 'ovrig' AND s.datum IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM partitillhorighet t JOIN ledamot lt ON lt.id = t.ledamot_id
              WHERE coalesce(lt.huvud_id, lt.id) = p.id AND t.status IN ('utkast', 'granskad', 'publicerad'))
        ORDER BY p.id, s.datum, s.starttid NULLS LAST, s.id, n.ordning
        """
    ).fetchall()
    per_person: dict[int, dict] = {}
    forekomster: dict[int, dict[int, Forekomst]] = defaultdict(dict)
    for r in rader:
        per_person.setdefault(r["person"], {"id": r["person"], "namn": r["person_namn"]})
        tidigare = forekomster[r["person"]].get(r["sammantrade_id"])
        # En förekomst per sammanträde, med det första angivna partiet.
        if tidigare is None or (tidigare.parti is None and r["parti"]):
            forekomster[r["person"]][r["sammantrade_id"]] = Forekomst(
                r["datum"], r["sammantrade_id"], r["organ"], r["parti"] or None)
    ut = []
    for person, ledamot in per_person.items():
        if perioderna := perioder(list(forekomster[person].values())):
            ut.append({"ledamot": ledamot, "perioder": [_belagg(p) for p in perioderna]})
    return sorted(ut, key=lambda x: _namnordning(x["ledamot"]["namn"]))


def _namnordning(namn: str) -> str:
    return namn.casefold().translate(str.maketrans({"å": "{", "ä": "|", "ö": "}", "é": "e"}))
