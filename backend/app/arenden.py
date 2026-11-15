"""Ärendespårning (ADR-0003): behandlingar i olika organ kopplas till samma ärende.

Kopplingsreglerna, framtagna ur hela protokollarkivet:

- **Diarienummer.** Behandlingar med samma diarienummer i samma diarieserie kopplas automatiskt.
  Serien är prefixet (`KS/2026-386`), och utan prefix organets egen serie. Kommunfullmäktige
  använder kommunstyrelsens serie. Ett stående diarienummer, som återkommer vid sex eller fler
  sammanträden i ett organ (t.ex. "Ärenden för kännedom"), kopplar ingenting.
- **Hänvisning uppåt.** Ett beslutsunderlag som hänvisar till ett protokollsutdrag från ett
  beredande organ (nämnd → KS, KS → KF) kopplas automatiskt när rubrikerna liknar varandra,
  annars blir kopplingen ett förslag.
- **Övriga hänvisningar** (till samma nivå eller nedåt, eller utan organ) blir förslag som en
  redaktör bekräftar eller avvisar (ADR-0002).
- Samlingspunkter (delegationsbeslut, meddelanden, ärenden för kännedom …) kopplas aldrig.

Ett ärende är en sammanhängande grupp behandlingar via automatiska och bekräftade kopplingar.
Varje behandling hör till ett ärende, ensam om inget kopplar den. Ärendena räknas om efter varje
tolkning och behåller sina id så långt det går.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import psycopg

from .rattelser import Publicerade
from .sources.harnosand import ORGAN

# Beslutsnivå: nämnderna bereder åt kommunstyrelsen, som bereder åt kommunfullmäktige.
NIVA = {"SAM": 0, "SOC": 0, "SKOL": 0, "KS": 1, "KF": 2}
STAENDE_GRANS = 6
LIKHETSGRANS = 0.5

# Samlingspunkter och fasta punkter på dagordningen. De återkommer vid varje sammanträde eller år
# med samma rubrik och ofta samma diarienummer, men är inte ett ärende som går mellan organ.
SAMLING = re.compile(
    r"kännedom|^anmälan|informationsärenden|^information\b|tillkommande (motioner|ärende)|delegationsbeslut"
    r"|delegeringsbeslut|delgivning|meddelanden|^skrivelser|justerare|dagordning|föredragningslista"
    r"|frågestund|korta frågor|inkomna frågor|frågor och svar|^avsägelser|^valärenden|^parentation"
    r"|uppdragsbeslut|uppdragsuppföljning|attestant",
    re.I,
)

_ORD = re.compile(r"[a-zåäöé]{4,}")
_STOPP = {"för", "samt", "till", "från", "inom", "över", "under", "kommun", "härnösands", "härnösand",
          "kommunens", "svar", "motion", "angående", "gällande"}


def _ord(text: str) -> set[str]:
    return {w[:7] for w in _ORD.findall(text.lower()) if w not in _STOPP}


def likhet(a: str, b: str) -> float:
    """Andelen gemensamma ord (förkortade till sju tecken) i den kortare rubriken."""
    x, y = _ord(a), _ord(b)
    return len(x & y) / max(1, min(len(x), len(y)))


def serie(organ: str, dnr: str) -> str:
    if "/" in dnr:
        return dnr.split("/", 1)[0].strip().upper()
    return "KS" if organ in ("KS", "KF") else organ


Nyckel = tuple[int, int]  # (sammantrade_id, paragraf)


@dataclass
class _Beh:
    nyckel: Nyckel
    organ: str
    datum: date | None
    rubrik: str
    diarienummer: list[str]
    hanvisningar: list[dict] = field(default_factory=list)

    @property
    def ordning(self) -> tuple:
        return (self.datum or date.max, NIVA.get(self.organ, 0), self.nyckel)

    @property
    def samling(self) -> bool:
        return bool(SAMLING.search(self.rubrik))


def _las(conn: psycopg.Connection) -> dict[Nyckel, _Beh]:
    rader = conn.execute(
        """
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.id, b.sammantrade_id, b.paragraf, b.rubrik,
               b.diarienummer, s.organ, s.datum
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """
    ).fetchall()
    beh = {}
    per_id = {}
    for r in rader:
        b = _Beh((r["sammantrade_id"], r["paragraf"]), r["organ"], r["datum"], r["rubrik"], r["diarienummer"])
        beh[b.nyckel] = b
        per_id[r["id"]] = b
    for h in conn.execute("SELECT behandling_id, organ, datum, paragraf, text FROM hanvisning ORDER BY behandling_id, ordning"):
        if h["behandling_id"] in per_id:
            per_id[h["behandling_id"]].hanvisningar.append(h)
    return beh


def _forslag_till_kopplingar(beh: dict[Nyckel, _Beh]) -> dict[tuple[Nyckel, Nyckel], tuple[str, str, str]]:
    """Kopplingarna som reglerna ger: (fran, till) -> (grund, underlag, status)."""
    ut: dict[tuple[Nyckel, Nyckel], tuple[str, str, str]] = {}

    def lagg_till(a: _Beh, b: _Beh, grund: str, underlag: str, status: str) -> None:
        fran, till = sorted((a, b), key=lambda x: x.ordning)
        par = (fran.nyckel, till.nyckel)
        tidigare = ut.get(par)
        if tidigare is None or (tidigare[2] == "forslag" and status == "automatisk"):
            ut[par] = (grund, underlag, status)

    # Diarienummer
    grupper: dict[tuple[str, str], list[_Beh]] = defaultdict(list)
    for b in beh.values():
        if b.samling:
            continue
        for d in b.diarienummer:
            grupper[(serie(b.organ, d), d)].append(b)
    for (_, dnr), medlemmar in grupper.items():
        per_organ = Counter(b.organ for b in medlemmar)
        if max(per_organ.values()) >= STAENDE_GRANS:
            continue
        medlemmar.sort(key=lambda x: x.ordning)
        for a, b in zip(medlemmar, medlemmar[1:]):
            lagg_till(a, b, "diarienummer", dnr, "automatisk")

    # Hänvisningar i beslutsunderlaget
    per_dag: dict[tuple[date, int], list[_Beh]] = defaultdict(list)
    for b in beh.values():
        if b.datum:
            per_dag[(b.datum, b.nyckel[1])].append(b)
    for b in beh.values():
        if b.samling:
            continue
        for h in b.hanvisningar:
            kandidater = [k for k in per_dag.get((h["datum"], h["paragraf"]), [])
                          if k is not b and (h["organ"] is None or k.organ == h["organ"])]
            for k in kandidater:
                if k.samling or (b.datum and k.datum and k.datum > b.datum):
                    continue
                uppat = h["organ"] is not None and NIVA.get(k.organ, 0) < NIVA.get(b.organ, 0)
                status = "automatisk" if uppat and likhet(b.rubrik, k.rubrik) > LIKHETSGRANS else "forslag"
                lagg_till(k, b, "hanvisning", h["text"], status)
    return ut


def koppla(conn: psycopg.Connection) -> dict[str, int]:
    """Räknar om kopplingarna och ärendena. Redaktörens beslut står kvar."""
    beh = _las(conn)
    regler = _forslag_till_kopplingar(beh)
    befintliga = {
        ((r["fran_sammantrade_id"], r["fran_paragraf"]), (r["till_sammantrade_id"], r["till_paragraf"])): r
        for r in conn.execute("SELECT * FROM koppling")
    }
    for par, r in befintliga.items():
        if r["status"] in ("bekraftad", "avvisad"):
            continue
        if par not in regler:
            conn.execute("DELETE FROM koppling WHERE id = %s", (r["id"],))
        elif (r["grund"], r["underlag"], r["status"]) != regler[par]:
            grund, underlag, status = regler[par]
            conn.execute("UPDATE koppling SET grund = %s, underlag = %s, status = %s WHERE id = %s",
                         (grund, underlag, status, r["id"]))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO koppling (fran_sammantrade_id, fran_paragraf, till_sammantrade_id, till_paragraf,
                                  grund, underlag, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(*fran, *till, *v) for (fran, till), v in regler.items() if (fran, till) not in befintliga],
        )
    return _bilda_arenden(conn, beh)


def _bilda_arenden(conn: psycopg.Connection, beh: dict[Nyckel, _Beh]) -> dict[str, int]:
    foralder = {n: n for n in beh}

    def rot(n: Nyckel) -> Nyckel:
        while foralder[n] != n:
            foralder[n] = foralder[foralder[n]]
            n = foralder[n]
        return n

    for r in conn.execute("SELECT * FROM koppling WHERE status IN ('automatisk', 'bekraftad')"):
        a, b = (r["fran_sammantrade_id"], r["fran_paragraf"]), (r["till_sammantrade_id"], r["till_paragraf"])
        if a in beh and b in beh:
            foralder[rot(a)] = rot(b)
    grupper: dict[Nyckel, list[Nyckel]] = defaultdict(list)
    for n in beh:
        grupper[rot(n)].append(n)

    tidigare = {(r["sammantrade_id"], r["paragraf"]): r["arende_id"]
                for r in conn.execute("SELECT * FROM arende_behandling")}
    # Störst grupp först, så att ett ärende som delas behåller sitt id i den största delen.
    upptagna: set[int] = set()
    tilldelning: list[tuple[int, int, int]] = []
    nya = 0
    for medlemmar in sorted(grupper.values(), key=len, reverse=True):
        kandidater = Counter(tidigare[n] for n in medlemmar if n in tidigare)
        arende_id = next((a for a, _ in kandidater.most_common() if a not in upptagna), None)
        if arende_id is None:
            arende_id = conn.execute("INSERT INTO arende DEFAULT VALUES RETURNING id").fetchone()["id"]
            nya += 1
        upptagna.add(arende_id)
        tilldelning += [(n[0], n[1], arende_id) for n in medlemmar]
    conn.execute("DELETE FROM arende_behandling")
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO arende_behandling (sammantrade_id, paragraf, arende_id) VALUES (%s, %s, %s)",
                        tilldelning)
    conn.execute("DELETE FROM arende a WHERE NOT EXISTS (SELECT 1 FROM arende_behandling x WHERE x.arende_id = a.id)")
    return {"arenden": len(grupper), "nya_arenden": nya,
            "kopplade": sum(1 for g in grupper.values() if len(g) > 1)}


# Läsning

def _organ(organ_id: str) -> dict:
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}


_BEHANDLING = """
    SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.sammantrade_id, b.paragraf, b.rubrik, b.diarienummer,
           b.beslut, s.organ, s.datum, s.tolkning
    FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
"""


def _beh(r: dict) -> dict:
    return {
        "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": _organ(r["organ"]),
                        "tolkning": r["tolkning"]},
        "paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"], "beslut": r["beslut"],
    }


def arende_for(conn: psycopg.Connection, sammantrade_id: int, paragraf: int) -> dict | None:
    rad = conn.execute(
        """
        SELECT a.arende_id, (SELECT count(*) FROM arende_behandling x WHERE x.arende_id = a.arende_id) AS antal
        FROM arende_behandling a WHERE a.sammantrade_id = %s AND a.paragraf = %s
        """,
        (sammantrade_id, paragraf),
    ).fetchone()
    return {"id": rad["arende_id"], "antal_behandlingar": rad["antal"]} if rad else None


_FORESLAR = re.compile(r"föreslår\s+(kommunfullmäktige|kommunstyrelsen)|förslag till (kommunfullmäktige|kommunstyrelsen)", re.I)


def las_arende(conn: psycopg.Connection, arende_id: int) -> dict | None:
    if not conn.execute("SELECT 1 FROM arende WHERE id = %s", (arende_id,)).fetchone():
        return None
    rader = conn.execute(
        f"""{_BEHANDLING}
        JOIN arende_behandling a ON a.sammantrade_id = b.sammantrade_id AND a.paragraf = b.paragraf
        WHERE a.arende_id = %s
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """,
        (arende_id,),
    ).fetchall()
    rader.sort(key=lambda r: (r["datum"] or date.max, NIVA.get(r["organ"], 0), r["paragraf"]))
    pub = Publicerade(conn, list({r["sammantrade_id"] for r in rader}))
    behandlingar = [pub.behandling(r["sammantrade_id"], _beh(r)) for r in rader]
    # Alla kopplingar som rör ärendets behandlingar, också förslag och avvisade kopplingar till andra ärenden.
    medlem = "IN (SELECT sammantrade_id, paragraf FROM arende_behandling WHERE arende_id = %(a)s)"
    kopplingar = _kopplingar(
        conn, f"WHERE (k.fran_sammantrade_id, k.fran_paragraf) {medlem} OR (k.till_sammantrade_id, k.till_paragraf) {medlem}",
        {"a": arende_id})
    diarienummer = list(dict.fromkeys(d for b in behandlingar for d in b["diarienummer"]))
    # Slutligt beslut: det senaste beslutet, om det inte är ett förslag till ett annat organ.
    sista = behandlingar[-1] if behandlingar else None
    slutligt = sista if sista and sista["beslut"] and not _FORESLAR.search(sista["beslut"]) else None
    return {
        "id": arende_id,
        "rubrik": sista["rubrik"] if sista else None,
        "diarienummer": diarienummer,
        "behandlingar": behandlingar,
        "kopplingar": kopplingar,
        "slutligt_beslut": {"sammantrade_id": slutligt["sammantrade"]["id"], "paragraf": slutligt["paragraf"],
                            "organ": slutligt["sammantrade"]["organ"], "datum": slutligt["sammantrade"]["datum"],
                            "beslut": slutligt["beslut"]} if slutligt else None,
    }


def _kopplingar(conn: psycopg.Connection, villkor: str, parametrar: dict) -> list[dict]:
    rader = conn.execute(
        f"""
        SELECT k.*,
               fb.rubrik AS fran_rubrik, fs.organ AS fran_organ, fs.datum AS fran_datum,
               tb.rubrik AS till_rubrik, ts.organ AS till_organ, ts.datum AS till_datum
        FROM koppling k
        JOIN sammantrade fs ON fs.id = k.fran_sammantrade_id
        JOIN sammantrade ts ON ts.id = k.till_sammantrade_id
        LEFT JOIN LATERAL (SELECT rubrik FROM behandling WHERE sammantrade_id = k.fran_sammantrade_id
                           AND paragraf = k.fran_paragraf ORDER BY ordning LIMIT 1) fb ON true
        LEFT JOIN LATERAL (SELECT rubrik FROM behandling WHERE sammantrade_id = k.till_sammantrade_id
                           AND paragraf = k.till_paragraf ORDER BY ordning LIMIT 1) tb ON true
        {villkor}
        ORDER BY ts.datum DESC NULLS LAST, k.id
        """,
        parametrar,
    ).fetchall()
    return [_koppling(r) for r in rader if r["fran_rubrik"] is not None and r["till_rubrik"] is not None]


def _koppling(r: dict) -> dict:
    def sida(s: str) -> dict:
        return {"sammantrade": {"id": r[f"{s}_sammantrade_id"], "datum": r[f"{s}_datum"],
                                "organ": _organ(r[f"{s}_organ"])},
                "paragraf": r[f"{s}_paragraf"], "rubrik": r[f"{s}_rubrik"]}

    return {"id": r["id"], "fran": sida("fran"), "till": sida("till"), "grund": r["grund"],
            "underlag": r["underlag"], "status": r["status"], "redaktor": r["redaktor"], "beslutad": r["beslutad"]}


def lista_kopplingar(conn: psycopg.Connection, status: str) -> list[dict]:
    return _kopplingar(conn, "WHERE k.status = %(s)s", {"s": status})


def besluta(conn: psycopg.Connection, koppling_id: int, status: str, redaktor: str) -> dict:
    """En redaktör bekräftar eller avvisar en koppling. Ärendena räknas om."""
    rad = conn.execute(
        "UPDATE koppling SET status = %s, redaktor = %s, beslutad = %s WHERE id = %s RETURNING id",
        (status, redaktor, datetime.now(timezone.utc), koppling_id),
    ).fetchone()
    if rad is None:
        raise LookupError(f"Kopplingen {koppling_id} finns inte")
    koppla(conn)
    [k] = _kopplingar(conn, "WHERE k.id = %(id)s", {"id": koppling_id})
    return k
