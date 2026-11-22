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
- **Motionstitel.** Ett svar på en motion, eller en beredning av den, kopplas till kommunfullmäktiges
  beslut att väcka motionen när titlarna är lika (#108). Från augusti 2026 saknar protokollen oftast
  diarienummer, och våren 2026 fick pågående ärenden nya nummer, så titeln är det som återstår.
  Exakt samma titel och en enda väckt motion ger en automatisk koppling. En titel som är början på
  den andra eller liknar den, eller flera väckta motioner som passar, ger förslag. Motionen ska vara
  väckt före behandlingen.
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

from . import behandlingar
from .sources.harnosand import NIVA, organ_ref
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


_MOTIONSPREFIX = re.compile(
    r"^(?:(?:svar\s+på|yttrande\s+över)\s+)?(?:remiss\s+(?:angående|gällande)\s+)?motion(?:en)?\b"
    r"(?:\s*[-–—:]\s*|\s+)(?:om\s+)?",
    re.I,
)
_DNR_PARENTES = re.compile(r"\s*\([^)]*\d[^)]*\)")


def motionstitel(text: str | None) -> str | None:
    """Motionens titel ur en rubrik, normaliserad för jämförelse, eller None om rubriken inte gäller en
    motion. "Motion - Kontinuitet i allmän förskola" och "Svar på motion om kontinuitet i allmän
    förskola" ger båda "kontinuitet i allmän förskola"."""
    text = (text or "").strip()
    m = _MOTIONSPREFIX.match(text)
    if not m:
        return None
    titel = _DNR_PARENTES.sub("", text[m.end():])
    titel = " ".join(titel.lower().split()).strip(" .,:;–—-")
    return titel or None


def _titlar_lika(a: str, b: str) -> int:
    """Hur väl två motionstitlar stämmer: 3 exakt, 2 när den ena är början på den andra (vid ord- eller
    skiljeteckengräns), 1 när de liknar varandra (likhet) och 0 annars."""
    if a == b:
        return 3
    kort, lang = sorted((a, b), key=len)
    if lang.startswith(kort) and not lang[len(kort)].isalnum():
        return 2
    return 1 if likhet(a, b) > LIKHETSGRANS else 0


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
    beslut: str | None = None

    @property
    def ordning(self) -> tuple:
        return (self.datum or date.max, NIVA.get(self.organ, 0), self.nyckel)

    @property
    def samling(self) -> bool:
        return bool(SAMLING.search(self.rubrik))


def _las(conn: psycopg.Connection) -> dict[Nyckel, _Beh]:
    """Alla behandlingar med publicerade rättelser (ADR-0003), i ordningen sammanträde, paragraf."""
    beh = {}
    per_id = {}
    for r in sorted(behandlingar.las(conn), key=lambda r: (r["sammantrade_id"], r["paragraf"])):
        b = _Beh((r["sammantrade_id"], r["paragraf"]), r["organ"], r["datum"], r["rubrik"], r["diarienummer"],
                 beslut=r["beslut"])
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

    _motionstitlar(beh, ut, lagg_till)
    return ut


def _motionstitlar(beh: dict[Nyckel, _Beh], ut: dict, lagg_till) -> None:
    """Kopplingsregeln motionstitel (#108). Körs sist, så att den bara kopplar det som diarienummer och
    automatiska hänvisningar inte redan har kopplat till en väckt motion."""
    from .motioner import tillkommande_motioner, utfall  # motioner importerar den här modulen

    # Väckta motioner: (titel, behandling, kan kopplas). Motioner som väcks under samlingspunkten
    # "Tillkommande motioner" är kandidater, men samlingspunkten kopplas aldrig.
    vackta: list[tuple[str, _Beh, bool]] = []
    for b in beh.values():
        if b.organ != "KF" or utfall(b.beslut) != "vackt":
            continue
        if b.samling:
            vackta += [(t, b, False) for titel, _ in tillkommande_motioner(b.beslut or "")
                       if (t := motionstitel(f"Motion - {titel}"))]
        elif t := motionstitel(b.rubrik):
            vackta.append((t, b, True))
    if not vackta:
        return
    vackt_id = {v.nyckel for _, v, _ in vackta}

    # Grupperna som de automatiska kopplingarna hittills ger.
    foralder: dict[Nyckel, Nyckel] = {}

    def rot(n: Nyckel) -> Nyckel:
        while foralder.get(n, n) != n:
            n = foralder[n]
        return n

    for (a, b), (_, _, status) in list(ut.items()):
        if status == "automatisk" and rot(a) != rot(b):
            foralder[rot(a)] = rot(b)
    med_vackt = {rot(n) for n in vackt_id}

    # Svar och beredning: den tidigaste behandlingen med en motionstitel i varje grupp som inte redan
    # har en väckt motion. De övriga i gruppen är redan kopplade till den.
    svar: dict[Nyckel, tuple[_Beh, str]] = {}
    for b in sorted(beh.values(), key=lambda x: x.ordning):
        if b.samling or b.nyckel in vackt_id or rot(b.nyckel) in med_vackt or rot(b.nyckel) in svar:
            continue
        if t := motionstitel(b.rubrik):
            svar[rot(b.nyckel)] = (b, t)

    for b, titel in svar.values():
        traffar = [(_titlar_lika(titel, t), likhet(titel, t), t, v, kan) for t, v, kan in vackta
                   if v.ordning < b.ordning]
        traffar = [x for x in traffar if x[0]]
        if not traffar:
            continue
        # Bara den bästa nivån: exakt före början före liknande, och bland liknande den högsta likheten.
        niva, hogst = max(x[:2] for x in traffar)
        traffar = [x for x in traffar if x[0] == niva and (niva > 1 or x[1] == hogst)]
        status = "automatisk" if niva == 3 and len(traffar) == 1 else "forslag"
        for _, _, t, v, kan in traffar:
            if kan:
                lagg_till(v, b, "motionstitel", t, status)


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

def _beh(r: dict) -> dict:
    b = {
        "sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": organ_ref(r["organ"]),
                        "tolkning": r["tolkning"]},
        "paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"], "beslut": r["beslut"],
        "typ": r["typ"],
    }
    if "rattelser" in r:
        b["rattelser"] = r["rattelser"]
    return b


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
    behandlingslista = [_beh(r) for r in behandlingar.las(conn, arende=arende_id)]
    # Alla kopplingar som rör ärendets behandlingar, också förslag och avvisade kopplingar till andra ärenden.
    medlem = "IN (SELECT sammantrade_id, paragraf FROM arende_behandling WHERE arende_id = %(a)s)"
    kopplingar = _kopplingar(
        conn, f"WHERE (k.fran_sammantrade_id, k.fran_paragraf) {medlem} OR (k.till_sammantrade_id, k.till_paragraf) {medlem}",
        {"a": arende_id})
    diarienummer = list(dict.fromkeys(d for b in behandlingslista for d in b["diarienummer"]))
    # Slutligt beslut: det senaste beslutet, om det inte är ett förslag till ett annat organ.
    sista = behandlingslista[-1] if behandlingslista else None
    slutligt = sista if sista and sista["beslut"] and not _FORESLAR.search(sista["beslut"]) else None
    return {
        "id": arende_id,
        "rubrik": sista["rubrik"] if sista else None,
        "diarienummer": diarienummer,
        "behandlingar": behandlingslista,
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
    ut = [_koppling(r) for r in rader if r["fran_rubrik"] is not None and r["till_rubrik"] is not None]
    # Historiken över besluten, äldst först (#77).
    historik: dict[int, list[dict]] = defaultdict(list)
    if ut:
        for h in conn.execute(
            "SELECT koppling_id, status, redaktor, tid, motivering FROM kopplingsbeslut "
            "WHERE koppling_id = ANY(%s) ORDER BY tid, id", ([k["id"] for k in ut],),
        ):
            historik[h["koppling_id"]].append({"status": h["status"], "redaktor": h["redaktor"], "tid": h["tid"],
                                                "motivering": h["motivering"]})
    for k in ut:
        k["historik"] = historik[k["id"]]
    return ut


def _koppling(r: dict) -> dict:
    def sida(s: str) -> dict:
        return {"sammantrade": {"id": r[f"{s}_sammantrade_id"], "datum": r[f"{s}_datum"],
                                "organ": organ_ref(r[f"{s}_organ"])},
                "paragraf": r[f"{s}_paragraf"], "rubrik": r[f"{s}_rubrik"]}

    return {"id": r["id"], "fran": sida("fran"), "till": sida("till"), "grund": r["grund"],
            "underlag": r["underlag"], "status": r["status"], "redaktor": r["redaktor"], "beslutad": r["beslutad"]}


def lista_kopplingar(conn: psycopg.Connection, status: str, redaktor: str | None = None) -> list[dict]:
    """Kopplingarna med en status. Med `redaktor` bara de som den redaktören beslutade senast."""
    if redaktor is None:
        return _kopplingar(conn, "WHERE k.status = %(s)s", {"s": status})
    return _kopplingar(conn, "WHERE k.status = %(s)s AND k.redaktor = %(r)s", {"s": status, "r": redaktor})


class OgiltigtBeslut(ValueError):
    """Beslutet går inte att fatta, t.ex. utan motivering eller för en automatisk koppling."""


def besluta(conn: psycopg.Connection, koppling_id: int, status: str, redaktor: str,
            motivering: str | None = None) -> dict:
    """En redaktör bekräftar eller avvisar en koppling, eller ändrar ett tidigare beslut (#77).

    Att ändra ett beslut (från bekräftad eller avvisad) kräver motivering och kan också lägga tillbaka
    kopplingen som förslag. Varje beslut sparas i historiken. Ärendena räknas om."""
    rad = conn.execute("SELECT status FROM koppling WHERE id = %s FOR UPDATE", (koppling_id,)).fetchone()
    if rad is None:
        raise LookupError(f"Kopplingen {koppling_id} finns inte")
    fore = rad["status"]
    motivering = (motivering or "").strip() or None
    if fore == "automatisk":
        raise OgiltigtBeslut("En automatisk koppling bygger på diarienumret och beslutas inte av en redaktör")
    if status not in ("forslag", "bekraftad", "avvisad"):
        raise OgiltigtBeslut(f"Okänt beslut: {status}")
    if status == fore:
        raise OgiltigtBeslut("Kopplingen har redan det beslutet")
    if fore != "forslag" and motivering is None:
        raise OgiltigtBeslut("Att ändra ett beslut kräver en motivering")
    nu = datetime.now(timezone.utc)
    if status == "forslag":
        conn.execute("UPDATE koppling SET status = 'forslag', redaktor = NULL, beslutad = NULL WHERE id = %s",
                     (koppling_id,))
    else:
        conn.execute("UPDATE koppling SET status = %s, redaktor = %s, beslutad = %s WHERE id = %s",
                     (status, redaktor, nu, koppling_id))
    conn.execute("INSERT INTO kopplingsbeslut (koppling_id, status, redaktor, tid, motivering) "
                 "VALUES (%s, %s, %s, %s, %s)", (koppling_id, status, redaktor, nu, motivering))
    koppla(conn)
    [k] = _kopplingar(conn, "WHERE k.id = %(id)s", {"id": koppling_id})
    return k
