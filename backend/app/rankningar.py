"""Rankningar (#66): externa aktörers återkommande jämförelser av Sveriges kommuner.

Källorna (`sources/foretagsklimat.py`, `sources/miljobarometern.py`) lämnar en `Rankningsdata` per rankning.
Här lagras den och läses ut för sidan "Rankningar". Uppgifterna är avsändarens officiella siffror och publiceras
direkt, utan granskningsflödet, med källhänvisning. Plattformen gör inga egna bedömningar av vad en placering
betyder (kravspec avsnitt 18): texterna beskriver bara vad avsändaren mäter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import psycopg

HARNOSAND = "Härnösand"
# Grannkommunerna enligt kravspecens avsnitt 18, i den ordningen.
GRANNKOMMUNER = ("Sundsvall", "Kramfors", "Timrå", "Sollefteå", "Örnsköldsvik")
KOMMUNER = (HARNOSAND, *GRANNKOMMUNER)


class Ogiltig(ValueError):
    pass


@dataclass(frozen=True)
class Rankning:
    id: str
    titel: str
    avsandare: str
    avsandartyp: str
    beskrivning: str
    url: str
    metod_url: str
    villkor: str


@dataclass(frozen=True)
class Placering:
    kommun: str
    ar: int
    placering: int
    kalla_url: str
    antal: int | None = None
    poang: Decimal | None = None
    max_poang: Decimal | None = None


@dataclass(frozen=True)
class Delmatt:
    kommun: str
    ar: int
    delmatt: str
    namn: str
    grupp: str | None  # None = okänd i den här hämtningen, det sparade behålls
    enhet: str | None
    kalla_url: str
    varde: Decimal | None = None
    svar: str | None = None
    riksvarde: Decimal | None = None
    placering: int | None = None


@dataclass
class Rankningsdata:
    rankning: Rankning
    placeringar: list[Placering] = field(default_factory=list)
    delmatt: list[Delmatt] = field(default_factory=list)


# Fälten som jämförs för att avgöra om en uppgift är ny, ändrad eller oförändrad. Källadressen räknas inte:
# den kan ändras (t.ex. id:t i företagsklimatets filadresser) utan att uppgiften gör det.
_PLACERINGSFALT = ("placering", "antal", "poang", "max_poang")
_DELMATTSFALT = ("namn", "grupp", "enhet", "varde", "svar", "riksvarde", "placering")
_TEXTFALT = ("namn", "grupp", "enhet")


def _sla_ihop(nytt: dict, forra: dict | None, falt: tuple[str, ...]) -> dict:
    """Ett värde som saknas i den nya hämtningen (t.ex. därför att en av källans filer inte gick att hämta)
    behåller det sparade värdet, så att ett tillfälligt fel aldrig blir en reviderad uppgift."""
    if forra is None:
        # Texter som inte får saknas i databasen blir tomma när de är okända från början.
        return {f: ("" if v is None and f in _TEXTFALT else v) for f, v in nytt.items()}
    return {f: (forra[f] if nytt[f] is None else nytt[f]) for f in falt}


def _lagra_versioner(conn: psycopg.Connection, tabell: str, nyckelfalt: tuple[str, ...], falt: tuple[str, ...],
                     rankning_id: str, rader: list, korning_id: int, hamtad: datetime) -> dict[str, int]:
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0}
    senaste = {
        tuple(r[k] for k in nyckelfalt): r
        for r in conn.execute(
            f"SELECT DISTINCT ON ({', '.join(nyckelfalt)}) * FROM {tabell} WHERE rankning_id = %s "
            f"ORDER BY {', '.join(nyckelfalt)}, version DESC",
            (rankning_id,),
        )
    }
    for rad in rader:
        nyckel = tuple(getattr(rad, k) for k in nyckelfalt)
        forra = senaste.get(nyckel)
        varden = _sla_ihop({f: getattr(rad, f) for f in falt}, forra, falt)
        if forra is not None and all(_lika(varden[f], forra[f]) for f in falt):
            antal["oforandrade"] += 1
            continue
        version = 1 if forra is None else forra["version"] + 1
        kolumner = ("rankning_id", *nyckelfalt, *falt, "kalla_url", "hamtad", "version", "korning_id")
        conn.execute(
            f"INSERT INTO {tabell} ({', '.join(kolumner)}) VALUES ({', '.join(['%s'] * len(kolumner))})",
            (rankning_id, *nyckel, *(varden[f] for f in falt), rad.kalla_url, hamtad, version, korning_id),
        )
        senaste[nyckel] = {**varden, "version": version}
        antal["nya" if forra is None else "andrade"] += 1
    return antal


def _lika(a, b) -> bool:
    if isinstance(a, (int, Decimal)) and isinstance(b, (int, Decimal)):
        return Decimal(a) == Decimal(b)
    return a == b


def lagra(conn: psycopg.Connection, data: Rankningsdata, datakalla_id: str, korning_id: int,
          hamtad: datetime) -> dict[str, int]:
    r = data.rankning
    conn.execute(
        """
        INSERT INTO rankning (id, titel, avsandare, avsandartyp, beskrivning, url, metod_url, villkor, datakalla_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET titel = EXCLUDED.titel, avsandare = EXCLUDED.avsandare,
            avsandartyp = EXCLUDED.avsandartyp, beskrivning = EXCLUDED.beskrivning, url = EXCLUDED.url,
            metod_url = EXCLUDED.metod_url, villkor = EXCLUDED.villkor, datakalla_id = EXCLUDED.datakalla_id
        """,
        (r.id, r.titel, r.avsandare, r.avsandartyp, r.beskrivning, r.url, r.metod_url, r.villkor, datakalla_id),
    )
    a = _lagra_versioner(conn, "rankning_placering", ("kommun", "ar"), _PLACERINGSFALT, r.id,
                         data.placeringar, korning_id, hamtad)
    b = _lagra_versioner(conn, "rankning_delmatt", ("kommun", "ar", "delmatt"), _DELMATTSFALT, r.id,
                         data.delmatt, korning_id, hamtad)
    return {k: a[k] + b[k] for k in a}


# --- Läsning -------------------------------------------------------------------------------------------------

def _tal(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def _rankningsinfo(rad: dict) -> dict:
    return {k: rad[k] for k in ("id", "titel", "avsandare", "avsandartyp", "beskrivning", "url", "metod_url",
                                "villkor")}


def _placeringar(conn: psycopg.Connection, rankning_id: str) -> list[dict]:
    return list(conn.execute(
        """
        SELECT DISTINCT ON (kommun, ar) kommun, ar, placering, antal, poang, max_poang, kalla_url, hamtad
        FROM rankning_placering WHERE rankning_id = %s ORDER BY kommun, ar, version DESC
        """,
        (rankning_id,),
    ))


def _sammanfattning(placeringar: list[dict]) -> dict | None:
    egna = sorted((p for p in placeringar if p["kommun"] == HARNOSAND), key=lambda p: p["ar"])
    if not egna:
        return None
    senaste = egna[-1]
    foregaende = egna[-2] if len(egna) > 1 else None
    return {
        "ar": senaste["ar"],
        "placering": senaste["placering"],
        "antal": senaste["antal"],
        "poang": _tal(senaste["poang"]),
        "max_poang": _tal(senaste["max_poang"]),
        "foregaende": {"ar": foregaende["ar"], "placering": foregaende["placering"]} if foregaende else None,
        # Skillnaden i placeringens nummer (negativ = närmare plats 1). Ingen värdering.
        "andring": senaste["placering"] - foregaende["placering"] if foregaende else None,
    }


def lista(conn: psycopg.Connection) -> list[dict]:
    ut = []
    for r in conn.execute("SELECT * FROM rankning ORDER BY titel"):
        ut.append({**_rankningsinfo(r), "senaste": _sammanfattning(_placeringar(conn, r["id"]))})
    return ut


def _delmattstabell(conn: psycopg.Connection, rankning_id: str, senaste_ar: int) -> list[dict]:
    """Delmåtten för Härnösand det senaste året, med riksvärdet och förändringen mot året innan.

    Ett delmått som källan redovisar med en eftersläpning (t.ex. statistik som avser ett tidigare år) visas med
    sitt senaste år, om det är högst två år före rankningens senaste år.
    """
    rader = list(conn.execute(
        """
        SELECT DISTINCT ON (delmatt, ar) delmatt, ar, namn, grupp, enhet, varde, svar, riksvarde, placering
        FROM rankning_delmatt WHERE rankning_id = %s AND kommun = %s AND ar <= %s
        ORDER BY delmatt, ar, version DESC
        """,
        (rankning_id, HARNOSAND, senaste_ar),
    ))
    per_delmatt: dict[str, list[dict]] = {}
    for r in rader:
        per_delmatt.setdefault(r["delmatt"], []).append(r)
    ut = []
    for d, serie in per_delmatt.items():
        serie.sort(key=lambda r: r["ar"])
        sista = serie[-1]
        if sista["ar"] < senaste_ar - 2:
            continue
        forra = serie[-2] if len(serie) > 1 else None
        ut.append({
            "id": d,
            "namn": sista["namn"],
            "grupp": sista["grupp"],
            "enhet": sista["enhet"],
            "ar": sista["ar"],
            "varde": _tal(sista["varde"]),
            "svar": sista["svar"],
            "riksvarde": _tal(sista["riksvarde"]),
            "placering": sista["placering"],
            "foregaende": None if forra is None else {
                "ar": forra["ar"], "varde": _tal(forra["varde"]), "svar": forra["svar"],
                "placering": forra["placering"],
            },
        })
    return ut


def rankning(conn: psycopg.Connection, rankning_id: str) -> dict:
    r = conn.execute("SELECT * FROM rankning WHERE id = %s", (rankning_id,)).fetchone()
    if r is None:
        raise LookupError(f"Rankningen {rankning_id} finns inte")
    placeringar = _placeringar(conn, rankning_id)
    sammanfattning = _sammanfattning(placeringar)
    kommuner = []
    for kommun in KOMMUNER:
        punkter = sorted((p for p in placeringar if p["kommun"] == kommun), key=lambda p: p["ar"])
        if punkter:
            kommuner.append({
                "kommun": kommun,
                "punkter": [{"ar": p["ar"], "placering": p["placering"], "antal": p["antal"],
                             "poang": _tal(p["poang"])} for p in punkter],
            })
    hamtad = max((p["hamtad"] for p in placeringar), default=None)
    egna = [p for p in placeringar if p["kommun"] == HARNOSAND]
    kallor = sorted({p["kalla_url"] for p in egna if sammanfattning and p["ar"] == sammanfattning["ar"]})
    return {
        **_rankningsinfo(r),
        "datakalla": dict(conn.execute("SELECT id, titel, url FROM datakalla WHERE id = %s",
                                       (r["datakalla_id"],)).fetchone()),
        "senaste": sammanfattning,
        "metodbyten": metodbyten(conn, rankning_id),
        "kommuner": kommuner,
        "delmatt": _delmattstabell(conn, rankning_id, sammanfattning["ar"]) if sammanfattning else [],
        "hamtad": hamtad.isoformat() if hamtad else None,
        "kallor": kallor,
    }


# --- Metodbyten ----------------------------------------------------------------------------------------------

def metodbyten(conn: psycopg.Connection, rankning_id: str) -> list[dict]:
    return [
        {"ar": m["ar"], "beskrivning": m["beskrivning"]}
        for m in conn.execute(
            "SELECT ar, beskrivning FROM rankning_metodbyte WHERE rankning_id = %s ORDER BY ar", (rankning_id,))
    ]


def registrera_metodbyte(conn: psycopg.Connection, rankning_id: str, data: dict, epost: str) -> list[dict]:
    if conn.execute("SELECT 1 FROM rankning WHERE id = %s", (rankning_id,)).fetchone() is None:
        raise LookupError(f"Rankningen {rankning_id} finns inte")
    ar = data.get("ar")
    beskrivning = (data.get("beskrivning") or "").strip()
    if not isinstance(ar, int) or not 1900 <= ar <= 2200:
        raise Ogiltig("Ange metodbytets år")
    if not beskrivning:
        raise Ogiltig("Beskriv vad som ändrades i metoden")
    conn.execute(
        """
        INSERT INTO rankning_metodbyte (rankning_id, ar, beskrivning, registrerad_av) VALUES (%s, %s, %s, %s)
        ON CONFLICT (rankning_id, ar) DO UPDATE SET beskrivning = EXCLUDED.beskrivning,
            registrerad_av = EXCLUDED.registrerad_av, registrerad = now()
        """,
        (rankning_id, ar, beskrivning, epost),
    )
    conn.commit()
    return metodbyten(conn, rankning_id)


def ta_bort_metodbyte(conn: psycopg.Connection, rankning_id: str, ar: int) -> list[dict]:
    if conn.execute("DELETE FROM rankning_metodbyte WHERE rankning_id = %s AND ar = %s",
                    (rankning_id, ar)).rowcount == 0:
        raise LookupError(f"Inget metodbyte {ar} för {rankning_id}")
    conn.commit()
    return metodbyten(conn, rankning_id)


