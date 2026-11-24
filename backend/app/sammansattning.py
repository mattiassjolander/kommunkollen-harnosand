"""Sammansättning: kön och ålder bland kandidater, valda och tjänstgörande (#65).

Valmyndighetens uppgifter om valen till kommunfullmäktige sparas per valår och kandidatnummer. Källan gallrar
kandidaternas personuppgifter i efterhand, och ett sparat värde skrivs då inte över. Ändrade uppgifter, som en
ny efterträdare, blir reviderade uppgifter med det tidigare värdet kvar i `valandring`.

Personerna i valet kopplas till ledamotsregistret. Stämmer namn och parti (partiet som gäller enligt
protokollen, ADR-0004 och ADR-0006) exakt och bara en person matchar kopplas de automatiskt. Andra fall blir
kopplingsförslag som en redaktör bekräftar eller avvisar.

En redaktör kan ange kön och födelseår med källa för en person som saknar uppgift. Uppgiften går genom
granskningsflödet (ADR-0002), och ingen godkänner sin egen registrering. Att gissa kön utifrån namn eller bild
är inte tillåtet.

Bara sammanställd statistik är öppen. Kön och ålder per person syns bara för redaktionen.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

import psycopg

from .sources.harnosand import ORGAN, organ_ref
from .sources.valmyndigheten import VALDAG, Valdata

# Kommunfullmäktiges mandatperiod börjar den 15 oktober valåret.
PERIODER = {ar: (date(ar, 10, 15), date(ar + 4, 10, 14)) for ar in VALDAG}
ALDERSGRUPPER = (("18–29", 18, 29), ("30–49", 30, 49), ("50–64", 50, 64), ("65+", 65, 200))
TOPP = 10  # de högst placerade per parti
KONSTEXT = "Kön enligt folkbokföringen (Valmyndigheten)"
_ERSATTARE = re.compile(r"ersättare", re.IGNORECASE)


class Ogiltig(ValueError):
    """Uppgiften är inte giltig."""


class EjTillatet(PermissionError):
    """Användaren får inte göra det här."""


class Konflikt(Exception):
    """Uppgiften har inte den status som steget kräver."""


def periodnamn(ar: int) -> str:
    return f"{ar}–{ar + 4}"


# Lagring

_KANDIDATFALT = ("parti", "listnummer", "ordning", "namn", "alder", "kon", "folkbokforingskommun", "giltig")
_LEDAMOTFALT = ("parti", "mandat", "namn", "invald", "avgang", "personvald", "alder", "kon")
_ERSATTARFALT = ("parti", "ersattargrupp", "kandidatnummer", "namn")


def _str(v) -> str | None:
    return None if v is None else str(v)


def _upsert(conn: psycopg.Connection, tabell: str, nyckel: dict, varden: dict, gallrade: set[str],
            korning_id: int | None, hamtad: datetime, antal: Counter) -> None:
    """Sparar en rad. Ett gallrat fält behåller sitt sparade värde. Ändrade fält loggas som reviderade uppgifter."""
    villkor = " AND ".join(f"{k} = %({k})s" for k in nyckel)
    gammal = conn.execute(f"SELECT * FROM {tabell} WHERE {villkor}", nyckel).fetchone()
    nyckeltext = "/".join(str(v) for v in nyckel.values())
    if gammal is None:
        kolumner = [*nyckel, *varden, "hamtad"] + (["gallrad"] if tabell == "valkandidat" else [])
        rad = nyckel | varden | {"hamtad": hamtad, "gallrad": hamtad if gallrade else None}
        conn.execute(f"INSERT INTO {tabell} ({', '.join(kolumner)}) VALUES ({', '.join(f'%({k})s' for k in kolumner)})",
                     rad)
        antal["nya"] += 1
        return
    andrade = {}
    for k, v in varden.items():
        if k in gallrade and v is None:
            continue  # källan har gallrat uppgiften, det sparade värdet står kvar
        if gammal[k] != v:
            andrade[k] = v
    satt = dict(andrade)
    if tabell == "valkandidat" and gallrade and gammal["gallrad"] is None:
        satt["gallrad"] = hamtad
    if satt:
        conn.execute(f"UPDATE {tabell} SET {', '.join(f'{k} = %(_{k})s' for k in satt)} WHERE {villkor}",
                     nyckel | {f"_{k}": v for k, v in satt.items()})
    if andrade:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO valandring (tabell, nyckel, falt, tidigare, nytt, korning_id, hamtad) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [(tabell, nyckeltext, k, _str(gammal[k]), _str(v), korning_id, hamtad) for k, v in andrade.items()],
            )
        antal["andrade"] += 1
    else:
        antal["oforandrade"] += 1


def _ta_bort_saknade(conn: psycopg.Connection, tabell: str, valar: int, nycklar: list[str], kvar: set[tuple],
                     korning_id: int | None, hamtad: datetime, antal: Counter) -> None:
    """Rader som källan inte längre har tas bort, och borttagningen loggas."""
    for r in conn.execute(f"SELECT {', '.join(nycklar)} FROM {tabell} WHERE valar = %s", (valar,)).fetchall():
        nyckel = tuple(r[k] for k in nycklar)
        if nyckel in kvar:
            continue
        conn.execute(f"DELETE FROM {tabell} WHERE valar = %s AND " + " AND ".join(f"{k} = %s" for k in nycklar),
                     (valar, *nyckel))
        conn.execute("INSERT INTO valandring (tabell, nyckel, falt, tidigare, nytt, korning_id, hamtad) "
                     "VALUES (%s, %s, 'rad', 'finns', NULL, %s, %s)",
                     (tabell, "/".join(str(v) for v in (valar, *nyckel)), korning_id, hamtad))
        antal["andrade"] += 1


def lagra(conn: psycopg.Connection, data: Valdata, korning_id: int | None, hamtad: datetime) -> dict:
    antal: Counter = Counter()
    ar = data.valar
    for f in data.filer:
        conn.execute(
            """INSERT INTO valfil (valar, fil, url, stampel, hamtad) VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (valar, fil) DO UPDATE SET url = EXCLUDED.url, stampel = EXCLUDED.stampel,
                                                       hamtad = EXCLUDED.hamtad""",
            (ar, f["fil"], f["url"], f["stampel"], hamtad),
        )
    if data.kandidater is not None:
        # Kandidaturerna ändras inte efter valet. En kandidat som försvinner ur filen behålls.
        for k in data.kandidater:
            _upsert(conn, "valkandidat", {"valar": ar, "kandidatnummer": k["kandidatnummer"]},
                    {f: k[f] for f in _KANDIDATFALT}, k["gallrade"], korning_id, hamtad, antal)
    if data.ledamoter is not None:
        for m in data.ledamoter:
            _upsert(conn, "valledamot", {"valar": ar, "kandidatnummer": m["kandidatnummer"]},
                    {f: m[f] for f in _LEDAMOTFALT}, m["gallrade"], korning_id, hamtad, antal)
        _ta_bort_saknade(conn, "valledamot", ar, ["kandidatnummer"],
                         {(m["kandidatnummer"],) for m in data.ledamoter}, korning_id, hamtad, antal)
    if data.ersattare is not None:
        for e in data.ersattare:
            _upsert(conn, "valersattare",
                    {"valar": ar, "ledamot_kandidatnummer": e["ledamot_kandidatnummer"],
                     "ersattarordning": e["ersattarordning"]},
                    {f: e[f] for f in _ERSATTARFALT}, set(), korning_id, hamtad, antal)
        _ta_bort_saknade(conn, "valersattare", ar, ["ledamot_kandidatnummer", "ersattarordning"],
                         {(e["ledamot_kandidatnummer"], e["ersattarordning"]) for e in data.ersattare},
                         korning_id, hamtad, antal)
    if data.rostberattigade is not None:
        r = data.rostberattigade
        gammal = conn.execute("SELECT * FROM rostberattigade WHERE valar = %s", (ar,)).fetchone()
        if gammal is None or any(gammal[k] != v for k, v in r.items()):
            conn.execute(
                f"""INSERT INTO rostberattigade (valar, {', '.join(r)}, hamtad)
                    VALUES (%(valar)s, {', '.join(f'%({k})s' for k in r)}, %(hamtad)s)
                    ON CONFLICT (valar) DO UPDATE SET {', '.join(f'{k} = EXCLUDED.{k}' for k in r)},
                                                      hamtad = EXCLUDED.hamtad""",
                r | {"valar": ar, "hamtad": hamtad},
            )
            antal["nya" if gammal is None else "andrade"] += 1
        else:
            antal["oforandrade"] += 1
    return {"nya": antal["nya"], "andrade": antal["andrade"], "oforandrade": antal["oforandrade"]}


# Koppling till ledamotsregistret

def normalisera(namn: str) -> str:
    """"Sandin, Rosmarie" → "rosmarie sandin". Versaler och blanksteg spelar ingen roll."""
    n = namn.strip()
    if "," in n:
        efter, _, fore = n.partition(",")
        n = f"{fore.strip()} {efter.strip()}"
    return " ".join(n.casefold().split())


def _delar(normaliserat: str) -> frozenset[str]:
    return frozenset(d for d in re.split(r"[\s\-]+", normaliserat) if d)


def _liknar(a: str, b: str) -> bool:
    """Mellannamn eller dubbelnamn: det kortare namnets delar (minst två) finns alla i det längre."""
    da, db = _delar(a), _delar(b)
    kort, lang = (da, db) if len(da) <= len(db) else (db, da)
    return len(kort) >= 2 and kort <= lang


_PARTIER_I_REGISTRET = """
    SELECT coalesce(l.huvud_id, l.id) AS person,
           array_remove(array_agg(DISTINCT coalesce(
               (SELECT t.parti FROM partitillhorighet t JOIN ledamot lp ON lp.id = t.ledamot_id
                WHERE t.status = 'publicerad' AND coalesce(lp.huvud_id, lp.id) = coalesce(l.huvud_id, l.id)
                  AND s.datum >= t.fran AND (t.till IS NULL OR s.datum <= t.till) LIMIT 1),
               n.parti)), NULL) AS partier
    FROM narvaro n JOIN ledamot l ON l.namn = n.namn JOIN sammantrade s ON s.id = n.sammantrade_id
    WHERE n.kategori <> 'ovrig'
    GROUP BY 1
"""

_VALPERSONER = """
    SELECT valar, kandidatnummer, namn, parti FROM valledamot
    UNION ALL SELECT valar, kandidatnummer, namn, parti FROM valersattare
    UNION ALL SELECT valar, kandidatnummer, namn, parti FROM valkandidat WHERE namn IS NOT NULL AND giltig
"""


def _valpersoner(conn: psycopg.Connection) -> dict[tuple[int, int], dict]:
    ut: dict[tuple[int, int], dict] = {}
    for r in conn.execute(_VALPERSONER):
        p = ut.setdefault((r["valar"], r["kandidatnummer"]), {"namn": r["namn"], "parti": r["parti"], "former": set()})
        p["former"].add(normalisera(r["namn"]))
    return ut


def forslag_och_automatiska(conn: psycopg.Connection) -> dict[tuple[int, int, int], tuple[str, str]]:
    """(valår, kandidatnummer, person) → (status, skäl) för alla matchningar mellan valet och registret."""
    partier = {r["person"]: {p for p in r["partier"] if p != "-"} for r in conn.execute(_PARTIER_I_REGISTRET)}
    if not partier:
        return {}
    namn_till_personer: dict[str, set[int]] = defaultdict(set)
    per_del: dict[str, set[str]] = defaultdict(set)
    for r in conn.execute("SELECT namn, coalesce(huvud_id, id) AS person FROM ledamot"):
        if r["person"] not in partier:
            continue
        n = normalisera(r["namn"])
        namn_till_personer[n].add(r["person"])
        for d in _delar(n):
            per_del[d].add(n)

    valpersoner = _valpersoner(conn)
    namn_per_valar: Counter = Counter((ar, n) for (ar, _), v in valpersoner.items() for n in v["former"])

    ut: dict[tuple[int, int, int], tuple[str, str]] = {}
    for (ar, knr), v in valpersoner.items():
        exakta: set[int] = set().union(*(namn_till_personer.get(n, set()) for n in v["former"]))
        if exakta:
            dubbel = any(namn_per_valar[(ar, n)] > 1 for n in v["former"])
            for person in exakta:
                pp = partier[person]
                if len(exakta) == 1 and pp == {v["parti"]} and not dubbel:
                    ut[(ar, knr, person)] = ("automatisk", "Samma namn och parti")
                elif dubbel:
                    ut[(ar, knr, person)] = ("forslag", f"Samma namn för flera kandidater {ar}")
                elif len(exakta) > 1:
                    ut[(ar, knr, person)] = ("forslag", "Samma namn för flera personer i registret")
                elif not pp:
                    ut[(ar, knr, person)] = ("forslag", "Samma namn, men protokollen anger inget parti")
                else:
                    ut[(ar, knr, person)] = ("forslag", f"Samma namn, men protokollen anger "
                                                        f"{', '.join(sorted(pp))} och valet {v['parti']}")
            continue
        # Mellannamn och dubbelnamn: bara personer med samma parti (eller utan parti i protokollen).
        kandidatnamn = set()
        for n in v["former"]:
            for d in _delar(n):
                kandidatnamn |= per_del.get(d, set())
        for rn in kandidatnamn:
            if not any(_liknar(n, rn) for n in v["former"]):
                continue
            for person in namn_till_personer[rn]:
                if not partier[person] or v["parti"] in partier[person]:
                    ut[(ar, knr, person)] = ("forslag", "Liknande namn (mellannamn eller dubbelnamn)")
    return ut


def koppla(conn: psycopg.Connection) -> None:
    """Räknar om automatiska kopplingar och förslag. En redaktörs beslut står kvar."""
    nya = forslag_och_automatiska(conn)
    befintliga = conn.execute(
        "SELECT k.id, k.valar, k.kandidatnummer, coalesce(l.huvud_id, l.id) AS person, k.status, k.skal "
        "FROM valkoppling k JOIN ledamot l ON l.id = k.ledamot_id").fetchall()
    beslutade = {(r["valar"], r["kandidatnummer"], r["person"]) for r in befintliga
                 if r["status"] in ("bekraftad", "avvisad")}
    bekraftade_val = {(r["valar"], r["kandidatnummer"]) for r in befintliga if r["status"] == "bekraftad"}
    kvar = set()
    for r in befintliga:
        nyckel = (r["valar"], r["kandidatnummer"], r["person"])
        if nyckel in beslutade:
            continue
        ny = nya.get(nyckel)
        if ny is None or (nyckel[:2] in bekraftade_val):
            conn.execute("DELETE FROM valkoppling WHERE id = %s", (r["id"],))
            continue
        kvar.add(nyckel)
        if (r["status"], r["skal"]) != ny:
            conn.execute("UPDATE valkoppling SET status = %s, skal = %s WHERE id = %s", (*ny, r["id"]))
    rader = [(ar, knr, person, *ny) for (ar, knr, person), ny in nya.items()
             if (ar, knr, person) not in kvar and (ar, knr, person) not in beslutade
             and (ar, knr) not in bekraftade_val]
    if rader:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO valkoppling (valar, kandidatnummer, ledamot_id, status, skal) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rader)


_VALFAKTA = """
    SELECT v.valar, v.kandidatnummer,
           coalesce(m.namn, k.namn, e.namn) AS namn, coalesce(m.parti, k.parti, e.parti) AS parti,
           coalesce(k.kon, m.kon) AS kon, coalesce(k.alder, m.alder) AS alder,
           k.ordning, k.listnummer, k.gallrad, m.mandat IS NOT NULL AS vald, e.namn IS NOT NULL AS ersattare
    FROM (SELECT valar, kandidatnummer FROM valkandidat UNION SELECT valar, kandidatnummer FROM valledamot
          UNION SELECT valar, kandidatnummer FROM valersattare) v
    LEFT JOIN valkandidat k USING (valar, kandidatnummer)
    LEFT JOIN valledamot m USING (valar, kandidatnummer)
    LEFT JOIN LATERAL (SELECT namn, parti FROM valersattare e
                       WHERE e.valar = v.valar AND e.kandidatnummer = v.kandidatnummer LIMIT 1) e ON true
"""


def _kopplingar(conn: psycopg.Connection, status: str | None = None, ledamot_id: int | None = None) -> list[dict]:
    rader = conn.execute(
        f"""
        WITH f AS ({_VALFAKTA})
        SELECT k.id, k.status, k.skal, k.skapad, k.beslutad_av, k.beslutad, k.valar, k.kandidatnummer,
               p.id AS person, p.namn AS person_namn, f.namn, f.parti, f.kon, f.alder, f.vald, f.ersattare, f.ordning
        FROM valkoppling k JOIN ledamot l ON l.id = k.ledamot_id JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id)
        LEFT JOIN f ON f.valar = k.valar AND f.kandidatnummer = k.kandidatnummer
        WHERE (%(s)s::text IS NULL OR k.status = %(s)s) AND (%(p)s::bigint IS NULL OR p.id = %(p)s)
        ORDER BY k.valar DESC, f.namn, p.namn
        """,
        {"s": status, "p": ledamot_id},
    ).fetchall()
    return [
        {"id": r["id"], "status": r["status"], "skal": r["skal"], "skapad": r["skapad"],
         "beslutad_av": r["beslutad_av"], "beslutad": r["beslutad"],
         "ledamot": {"id": r["person"], "namn": r["person_namn"]},
         "val": {"valar": r["valar"], "kandidatnummer": r["kandidatnummer"], "namn": r["namn"], "parti": r["parti"],
                 "kon": r["kon"], "alder": r["alder"], "vald": r["vald"], "ersattare": r["ersattare"],
                 "ordning": r["ordning"]}}
        for r in rader
    ]


def kopplingar(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    return _kopplingar(conn, status)


def besluta(conn: psycopg.Connection, koppling_id: int, status: str, redaktor: str) -> dict:
    rad = conn.execute("SELECT status FROM valkoppling WHERE id = %s FOR UPDATE", (koppling_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Kopplingen {koppling_id} finns inte")
    if status == "bekraftad" and rad["status"] != "forslag":
        raise Konflikt(f"Bara ett förslag kan bekräftas, kopplingen är {rad['status']}")
    if status == "avvisad" and rad["status"] not in ("forslag", "automatisk"):
        raise Konflikt(f"Kopplingen är {rad['status']} och kan inte avvisas")
    conn.execute("UPDATE valkoppling SET status = %s, beslutad_av = %s, beslutad = %s WHERE id = %s",
                 (status, redaktor, datetime.now(timezone.utc), koppling_id))
    if status == "bekraftad":
        # Andra förslag för samma person i valet tas bort.
        conn.execute(
            "DELETE FROM valkoppling WHERE id <> %(id)s AND status IN ('forslag', 'automatisk') AND (valar, kandidatnummer) "
            "= (SELECT valar, kandidatnummer FROM valkoppling WHERE id = %(id)s)", {"id": koppling_id})
    return next(k for k in _kopplingar(conn) if k["id"] == koppling_id)


# Kön och ålder per person

def _alder_vid(valdag: date, alder: int, datum: date) -> int:
    """Åldern vid ett datum, räknat från åldern på valdagen (födelsedagen är okänd, så fel med högst ett år)."""
    return alder + datum.year - valdag.year - ((datum.month, datum.day) < (valdag.month, valdag.day))


class Fakta:
    """Kön och ålder per person i registret: Valmyndighetens uppgifter genom kopplingarna, annars publicerade
    uppgifter från redaktionen."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.kon: dict[int, str] = {}
        self.kalla: dict[int, str] = {}
        self._aldrar: dict[int, list[tuple[date, int]]] = defaultdict(list)
        self._fodelsear: dict[int, int] = {}
        self.val: dict[tuple[int, int], dict] = {
            (r["valar"], r["kandidatnummer"]): r for r in conn.execute(_VALFAKTA)}
        self.person_for_val: dict[tuple[int, int], int] = {}
        for r in conn.execute(
            "SELECT k.valar, k.kandidatnummer, coalesce(l.huvud_id, l.id) AS person FROM valkoppling k "
            "JOIN ledamot l ON l.id = k.ledamot_id WHERE k.status IN ('automatisk', 'bekraftad') "
            "ORDER BY k.valar DESC"):
            self.person_for_val.setdefault((r["valar"], r["kandidatnummer"]), r["person"])
            v = self.val.get((r["valar"], r["kandidatnummer"]))
            if v is None:
                continue
            if v["kon"] and r["person"] not in self.kon:
                self.kon[r["person"]] = v["kon"]
                self.kalla[r["person"]] = "valmyndigheten"
            if v["alder"] is not None:
                self._aldrar[r["person"]].append((VALDAG[r["valar"]], v["alder"]))
                self.kalla.setdefault(r["person"], "valmyndigheten")
        for r in conn.execute(
            "SELECT coalesce(l.huvud_id, l.id) AS person, u.kon, u.fodelsear FROM personuppgift u "
            "JOIN ledamot l ON l.id = u.ledamot_id WHERE u.status = 'publicerad' ORDER BY u.publicerad"):
            if r["kon"] and r["person"] not in self.kon:
                self.kon[r["person"]] = r["kon"]
                self.kalla.setdefault(r["person"], "redaktionen")
            if r["fodelsear"] and r["person"] not in self._aldrar:
                self._fodelsear[r["person"]] = r["fodelsear"]
                self.kalla.setdefault(r["person"], "redaktionen")

    def alder(self, person: int | None, datum: date) -> int | None:
        if person is None:
            return None
        if aldrar := self._aldrar.get(person):
            valdag, a = min(aldrar, key=lambda x: abs((x[0] - datum).days))
            return _alder_vid(valdag, a, datum)
        if (ar := self._fodelsear.get(person)) is not None:
            return datum.year - ar
        return None

    def valperson(self, valar: int, kandidatnummer: int, datum: date) -> tuple[str | None, int | None]:
        """Kön och ålder vid `datum` för en person i valet: egna uppgifter, annars genom kopplingen."""
        v = self.val.get((valar, kandidatnummer)) or {}
        person = self.person_for_val.get((valar, kandidatnummer))
        kon = v.get("kon") or self.kon.get(person)
        alder = (_alder_vid(VALDAG[valar], v["alder"], datum) if v.get("alder") is not None
                 else self.alder(person, datum))
        return kon, alder


# Redaktionens uppgifter (kön och födelseår med källa)

def _uppgift_varden(data: dict) -> dict:
    kon = data.get("kon") or None
    if kon not in (None, "K", "M"):
        raise Ogiltig("Kön anges som K eller M")
    fodelsear = data.get("fodelsear")
    if fodelsear in ("", None):
        fodelsear = None
    else:
        try:
            fodelsear = int(fodelsear)
        except (TypeError, ValueError) as e:
            raise Ogiltig("Ange födelseåret med fyra siffror") from e
        if not 1900 <= fodelsear <= date.today().year - 18:
            raise Ogiltig("Födelseåret är inte rimligt för en förtroendevald")
    if kon is None and fodelsear is None:
        raise Ogiltig("Ange kön, födelseår eller båda")
    kalla = (data.get("kalla") or "").strip()
    if len(kalla) < 5:
        raise Ogiltig("Ange källan: en länk, eller dokument och sida")
    return {"kon": kon, "fodelsear": fodelsear, "kalla": kalla}


def _uppgift(conn: psycopg.Connection, uppgift_id: int) -> dict:
    rad = conn.execute("SELECT * FROM personuppgift WHERE id = %s FOR UPDATE", (uppgift_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Uppgiften {uppgift_id} finns inte")
    return rad


def _uppgift_ut(conn: psycopg.Connection, uppgift_id: int) -> dict:
    r = conn.execute(
        "SELECT u.*, p.id AS person, p.namn AS person_namn FROM personuppgift u JOIN ledamot l ON l.id = u.ledamot_id "
        "JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id) WHERE u.id = %s", (uppgift_id,)).fetchone()
    return _uppgiftsrad(r)


def _uppgiftsrad(r: dict) -> dict:
    return {"id": r["id"], "ledamot": {"id": r["person"], "namn": r["person_namn"]}, "kon": r["kon"],
            "fodelsear": r["fodelsear"], "kalla": r["kalla"], "status": r["status"], "redaktor": r["redaktor"],
            "skapad": r["skapad"], "granskad_av": r["granskad_av"], "publicerad_av": r["publicerad_av"],
            "publicerad": r["publicerad"], "aterkallelse": r["aterkallelse"]}


def uppgifter(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    rader = conn.execute(
        "SELECT u.*, p.id AS person, p.namn AS person_namn FROM personuppgift u JOIN ledamot l ON l.id = u.ledamot_id "
        "JOIN ledamot p ON p.id = coalesce(l.huvud_id, l.id) WHERE (%(s)s::text IS NULL OR u.status = %(s)s) "
        "ORDER BY u.skapad DESC", {"s": status}).fetchall()
    return [_uppgiftsrad(r) for r in rader]


def skapa_uppgift(conn: psycopg.Connection, data: dict, redaktor: str) -> dict:
    ledamot_id = data.get("ledamot_id")
    if not isinstance(ledamot_id, int):
        raise Ogiltig("ledamot_id saknas")
    rad = conn.execute("SELECT coalesce(huvud_id, id) AS person FROM ledamot WHERE id = %s", (ledamot_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Ledamoten {ledamot_id} finns inte")
    v = _uppgift_varden(data)
    fakta = Fakta(conn)
    if fakta.kalla.get(rad["person"]) == "valmyndigheten":
        raise Konflikt("Personen har redan uppgifter från Valmyndigheten")
    uid = conn.execute(
        "INSERT INTO personuppgift (ledamot_id, kon, fodelsear, kalla, status, redaktor) "
        "VALUES (%(l)s, %(kon)s, %(fodelsear)s, %(kalla)s, 'utkast', %(red)s) RETURNING id",
        v | {"l": rad["person"], "red": redaktor}).fetchone()["id"]
    return _uppgift_ut(conn, uid)


def ta_bort_uppgift(conn: psycopg.Connection, uppgift_id: int, redaktor: str) -> None:
    u = _uppgift(conn, uppgift_id)
    if u["redaktor"] != redaktor:
        raise EjTillatet("Bara redaktören som skrev uppgiften kan ta bort den")
    if u["status"] != "utkast":
        raise Konflikt("Bara ett utkast kan tas bort")
    conn.execute("DELETE FROM personuppgift WHERE id = %s", (uppgift_id,))


def _godkann(conn: psycopg.Connection, uppgift_id: int, utgivare: str, fran: str) -> dict:
    u = _uppgift(conn, uppgift_id)
    if u["redaktor"] == utgivare:
        raise EjTillatet("Ingen godkänner sin egen registrering")
    if u["status"] != fran:
        raise Konflikt(f"Uppgiften är {u['status']}, inte {fran}")
    return u


def granska_uppgift(conn: psycopg.Connection, uppgift_id: int, utgivare: str) -> dict:
    _godkann(conn, uppgift_id, utgivare, "utkast")
    conn.execute("UPDATE personuppgift SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), uppgift_id))
    return _uppgift_ut(conn, uppgift_id)


def publicera_uppgift(conn: psycopg.Connection, uppgift_id: int, utgivare: str) -> dict:
    _godkann(conn, uppgift_id, utgivare, "granskad")
    conn.execute("UPDATE personuppgift SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, datetime.now(timezone.utc), uppgift_id))
    return _uppgift_ut(conn, uppgift_id)


def aterkalla_uppgift(conn: psycopg.Connection, uppgift_id: int, data: dict, utgivare: str) -> dict:
    u = _uppgift(conn, uppgift_id)
    if u["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad uppgift kan återkallas, den här är {u['status']}")
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför uppgiften återkallas")
    conn.execute("UPDATE personuppgift SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, "
                 "aterkallelse = %s WHERE id = %s", (utgivare, datetime.now(timezone.utc), motivering, uppgift_id))
    return _uppgift_ut(conn, uppgift_id)


def personer(conn: psycopg.Connection) -> list[dict]:
    """Redaktionens vy: personerna i registret med kön, ålder, källa, kopplingar och väntande uppgifter."""
    fakta = Fakta(conn)
    kopp: dict[int, list[dict]] = defaultdict(list)
    for k in _kopplingar(conn):
        if k["status"] != "avvisad":
            kopp[k["ledamot"]["id"]].append(k)
    vantande: dict[int, list[dict]] = defaultdict(list)
    for u in uppgifter(conn):
        if u["status"] in ("utkast", "granskad"):
            vantande[u["ledamot"]["id"]].append(u)
    rader = conn.execute(
        "SELECT p.id, p.namn FROM ledamot p WHERE p.huvud_id IS NULL AND EXISTS ("
        " SELECT 1 FROM narvaro n JOIN ledamot l ON l.namn = n.namn WHERE coalesce(l.huvud_id, l.id) = p.id "
        " AND n.kategori <> 'ovrig') ORDER BY p.namn").fetchall()
    idag = date.today()
    return [
        {"id": r["id"], "namn": r["namn"], "kon": fakta.kon.get(r["id"]), "alder": fakta.alder(r["id"], idag),
         "kalla": fakta.kalla.get(r["id"]), "kopplingar": kopp.get(r["id"], []),
         "vantande_uppgifter": vantande.get(r["id"], [])}
        for r in rader
    ]


# Statistik

def _grupp(alder: int | None) -> str:
    if alder is None:
        return "saknas"
    return next((namn for namn, fran, till in ALDERSGRUPPER if fran <= alder <= till), "saknas")


def matt(poster: list[tuple[str | None, int | None]]) -> dict:
    """Kön och ålder för en grupp. Varje post är (kön, ålder). Saknade uppgifter är en egen grupp."""
    antal = len(poster)
    kon = Counter(k if k in ("K", "M") else "saknas" for k, _ in poster)
    aldrar = [a for _, a in poster if a is not None]
    grupper = Counter(_grupp(a) for _, a in poster)

    def andel(n: int) -> float | None:
        return round(n / antal, 4) if antal else None

    return {
        "antal": antal,
        "kvinnor": kon["K"], "man": kon["M"], "kon_saknas": kon["saknas"],
        "andel_kvinnor": andel(kon["K"]), "andel_man": andel(kon["M"]), "andel_kon_saknas": andel(kon["saknas"]),
        "medelalder": round(sum(aldrar) / len(aldrar), 1) if aldrar else None,
        "aldersgrupper": {namn: grupper[namn] for namn, _, _ in ALDERSGRUPPER} | {"saknas": grupper["saknas"]},
    }


def _sortera_partier(partier: list[str]) -> list[str]:
    ordning = ("S", "V", "MP", "C", "L", "M", "KD", "SD", "NP")
    return sorted(partier, key=lambda p: (ordning.index(p) if p in ordning else 99, p))


def _led(poster: list[tuple[str | None, str | None, int | None]], **extra) -> dict:
    """Ett led: totalt och per parti. Varje post är (parti, kön, ålder)."""
    per_parti: dict[str, list] = defaultdict(list)
    for parti, kon, alder in poster:
        per_parti[parti or "?"].append((kon, alder))
    return {
        "totalt": matt([(k, a) for _, k, a in poster]),
        "per_parti": [{"parti": p, **matt(per_parti[p])} for p in _sortera_partier(list(per_parti))],
        **extra,
    }


def _kalla(conn: psycopg.Connection, valar: int, fil: str) -> dict | None:
    r = conn.execute("SELECT url, stampel, hamtad FROM valfil WHERE valar = %s AND fil = %s", (valar, fil)).fetchone()
    return dict(r) | {"titel": "Valmyndigheten"} if r else None


def _kandidater(conn: psycopg.Connection, fakta: Fakta, ar: int) -> dict | None:
    rader = conn.execute("SELECT kandidatnummer, parti, ordning FROM valkandidat WHERE valar = %s", (ar,)).fetchall()
    if not rader:
        return None
    valdag = VALDAG[ar]
    alla, topp = [], []
    for r in rader:
        kon, alder = fakta.valperson(ar, r["kandidatnummer"], valdag)
        alla.append((r["parti"], kon, alder))
        if r["ordning"] is not None and r["ordning"] <= TOPP:
            topp.append((r["parti"], kon, alder))
    kallor = [_kalla(conn, ar, "kandidaturer")]
    return {
        "alla": _led(alla, kallor=kallor),
        # De högst placerade per parti visas bara när kandidaternas uppgifter inte är gallrade.
        "topp": _led(topp, kallor=kallor) if ar == max(VALDAG) else None,
    }


def _valda_kf(conn: psycopg.Connection, fakta: Fakta, ar: int) -> dict | None:
    rader = conn.execute("SELECT kandidatnummer, parti, invald FROM valledamot WHERE valar = %s", (ar,)).fetchall()
    if not rader:
        return None
    valdag = VALDAG[ar]
    poster = [(r, *fakta.valperson(ar, r["kandidatnummer"], valdag)) for r in rader]
    kallor = [_kalla(conn, ar, "ledamoter_med_historik")]
    return {
        "vid_start": _led([(r["parti"], k, a) for r, k, a in poster if r["invald"] is None], kallor=kallor),
        "med_eftertradare": _led([(r["parti"], k, a) for r, k, a in poster], kallor=kallor),
    }


_NARVARO = """
    SELECT DISTINCT ON (s.id, coalesce(l.huvud_id, l.id))
           s.id AS sammantrade_id, s.datum, coalesce(l.huvud_id, l.id) AS person, n.roll, n.kategori,
           coalesce((SELECT t.parti FROM partitillhorighet t JOIN ledamot lp ON lp.id = t.ledamot_id
                     WHERE t.status = 'publicerad' AND coalesce(lp.huvud_id, lp.id) = coalesce(l.huvud_id, l.id)
                       AND s.datum >= t.fran AND (t.till IS NULL OR s.datum <= t.till) LIMIT 1), n.parti) AS parti
    FROM narvaro n JOIN ledamot l ON l.namn = n.namn JOIN sammantrade s ON s.id = n.sammantrade_id
    WHERE n.kategori <> 'ovrig' AND s.organ = %(organ)s AND s.datum BETWEEN %(fran)s AND %(till)s
    ORDER BY s.id, coalesce(l.huvud_id, l.id), n.kategori = 'beslutande' DESC
"""


def _ur_protokollen(conn: psycopg.Connection, fakta: Fakta, organ: str, ar: int) -> tuple[dict | None, dict | None]:
    """Valda (ordinarie ledamöter enligt närvarolistorna) och tjänstgörande, för andra organ än fullmäktige och
    för tjänstgörande i fullmäktige."""
    fran, till = PERIODER[ar]
    rader = conn.execute(_NARVARO, {"organ": organ, "fran": fran, "till": till}).fetchall()
    if not rader:
        return None, None
    tjanst = [(r["parti"], fakta.kon.get(r["person"]), fakta.alder(r["person"], r["datum"]))
              for r in rader if r["kategori"] == "beslutande"]
    ordinarie: dict[int, Counter] = defaultdict(Counter)
    for r in rader:
        if r["roll"] and not _ERSATTARE.search(r["roll"]):
            ordinarie[r["person"]][r["parti"]] += 1
    valdag = VALDAG[ar]
    valda = [(c.most_common(1)[0][0], fakta.kon.get(p), fakta.alder(p, valdag)) for p, c in ordinarie.items()]
    kalla = {"titel": "Protokollens närvarolistor", "url": None, "stampel": None,
             "hamtad": max((r["datum"] for r in rader), default=None)}
    personer = len({r["person"] for r in rader if r["kategori"] == "beslutande"})
    sammantraden = len({r["sammantrade_id"] for r in rader})
    return (
        _led(valda, kallor=[kalla]) if valda else None,
        _led(tjanst, kallor=[kalla], personer=personer, sammantraden=sammantraden) if tjanst else None,
    )


def _referens(conn: psycopg.Connection) -> dict | None:
    r = conn.execute("SELECT * FROM rostberattigade ORDER BY valar DESC LIMIT 1").fetchone()
    if r is None:
        return None
    t = r["totalt"]
    return {
        "valar": r["valar"], "antal": t,
        "andel_kvinnor": round(r["kvinnor"] / t, 4), "andel_man": round(r["man"] / t, 4),
        "aldersgrupper": {"18–29": r["a18_29"], "30–49": r["a30_49"], "50–64": r["a50_64"], "65+": r["a65"]},
        "kallor": [_kalla(conn, r["valar"], "rostberattigade")],
    }


def statistik(conn: psycopg.Connection, period: int, organ: str) -> dict:
    if period not in PERIODER:
        raise Ogiltig(f"Mandatperioden {period} finns inte")
    if organ not in ORGAN:
        raise Ogiltig(f"Organet {organ} finns inte")
    fakta = Fakta(conn)
    valda_protokoll, tjanst = _ur_protokollen(conn, fakta, organ, period)
    fran, till = PERIODER[period]
    if organ == "KF":
        kandidater = _kandidater(conn, fakta, period)
        valda = _valda_kf(conn, fakta, period)
    else:
        kandidater = None
        valda = {"vid_start": None, "med_eftertradare": None, "enligt_protokollen": valda_protokoll}
    return {
        "period": {"ar": period, "namn": periodnamn(period), "fran": fran, "till": till, "valdag": VALDAG[period]},
        "organ": organ_ref(organ),
        "perioder": [{"ar": a, "namn": periodnamn(a)} for a in sorted(PERIODER)],
        "organlista": [organ_ref(o) for o in ORGAN],
        "kandidater": kandidater,
        "valda": valda,
        "tjanstgorande": tjanst,
        "referens": _referens(conn),
        "aldersgrupper": [namn for namn, _, _ in ALDERSGRUPPER],
        "konstext": KONSTEXT,
    }
