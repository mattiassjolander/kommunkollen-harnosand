"""Planerade sammanträden: lagring av organens sammanträdesplaner och jämförelse med protokollen.

Ett planerat sammanträde är en rad i tabellen `sammantrade` med plan_*-kolumnerna ifyllda. När
protokollet läses in kopplas det till det planerade sammanträdet med samma organ och datum (se
`protokoll._lagra_tolkning`), och finns protokollet redan när planen läses kopplas planen till det.
Ett protokoll utan planerat sammanträde, t.ex. från ett extra sammanträde, är ett sammanträde som tidigare.

Varje ändring i planen blir en ny version i `planversion` (en reviderad uppgift). Ett sammanträde som
försvinner från sidan utan att vara inställt markeras som borttaget ur planen och finns kvar.

Organen fastställer sina planer genom beslut i protokollen, t.ex. "Sammanträdestider 2027".
`jamforelse` hittar besluten och visar för redaktionen var datumen skiljer sig från webbsidan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import psycopg

from . import behandlingar
from .sources.harnosand import ORGAN
from .sources.sammantradesplaner import MANADER, Planrad, Sammantradesplan

FALT = ("datum", "starttid", "status", "anmarkning")


@dataclass(frozen=True)
class Kalla:
    """Var planen kommer ifrån: organets tabell på webbsidan, eller ett beslut i ett protokoll."""

    typ: str = "webbsidan"  # 'webbsidan' | 'beslut'
    sammantrade_id: int | None = None
    paragraf: int | None = None


WEBBSIDAN = Kalla()


def _versioner(conn: psycopg.Connection, organ: str) -> dict[str, dict]:
    return {r["plan_nyckel"]: r for r in conn.execute(
        """
        SELECT id, plan_nyckel, plan_datum AS datum, plan_starttid AS starttid, plan_status AS status,
               plan_anmarkning AS anmarkning, plan_version AS version, plan_kalla AS kalla,
               plan_beslut_sammantrade_id AS beslut_sammantrade_id, plan_beslut_paragraf AS beslut_paragraf
        FROM sammantrade WHERE organ = %s AND plan_nyckel IS NOT NULL
        """,
        (organ,),
    )}


def _ny_version(conn: psycopg.Connection, sammantrade_id: int, version: int, varden: dict, kalltext: str,
                url: str | None, korning_id: int | None, hamtad: datetime, kalla: Kalla) -> None:
    k = {"kalla": kalla.typ, "beslut_s": kalla.sammantrade_id, "beslut_p": kalla.paragraf}
    conn.execute(
        """
        UPDATE sammantrade SET plan_datum = %(datum)s, plan_starttid = %(starttid)s, plan_status = %(status)s,
               plan_anmarkning = %(anmarkning)s, plan_url = %(url)s, plan_version = %(version)s,
               plan_kalla = %(kalla)s, plan_beslut_sammantrade_id = %(beslut_s)s, plan_beslut_paragraf = %(beslut_p)s
        WHERE id = %(id)s
        """,
        {**varden, **k, "url": url, "version": version, "id": sammantrade_id},
    )
    conn.execute(
        """
        INSERT INTO planversion (sammantrade_id, version, datum, starttid, status, anmarkning, kalltext, hamtad,
                                 korning_id, kalla, beslut_sammantrade_id, beslut_paragraf)
        VALUES (%(id)s, %(version)s, %(datum)s, %(starttid)s, %(status)s, %(anmarkning)s, %(kalltext)s,
                %(hamtad)s, %(korning_id)s, %(kalla)s, %(beslut_s)s, %(beslut_p)s)
        """,
        {**varden, **k, "id": sammantrade_id, "version": version, "kalltext": kalltext, "hamtad": hamtad,
         "korning_id": korning_id},
    )


def _odaterade_till_datum(rader: list[Planrad], befintliga: dict[str, dict]) -> list[Planrad]:
    """En månad som bara anges som inställd ("Juni: Inställd") gäller det sammanträde i månaden som
    försvunnit från sidan, om det är ett enda. Då behåller sammanträdet sitt datum och sin identitet."""
    nycklar = {r.nyckel for r in rader}
    ut = []
    for r in rader:
        if r.datum is None and r.status == "installt" and r.nyckel not in befintliga:
            kandidater = [b for n, b in befintliga.items()
                          if b["datum"] is not None and n not in nycklar
                          and (b["datum"].year, b["datum"].month) == (r.ar, r.manad)]
            if len(kandidater) == 1:
                k = kandidater[0]
                r = Planrad(r.organ, r.ar, r.manad, k["datum"], k["starttid"], "installt", r.anmarkning, r.kalltext)
        ut.append(r)
    return ut


def lagra(conn: psycopg.Connection, plan: Sammantradesplan, korning_id: int | None,
          hamtad: datetime, kalla: Kalla = WEBBSIDAN) -> dict[str, int]:
    """Sparar organets plan. Returnerar antal nya, ändrade och oförändrade planerade sammanträden.

    En plan från webbsidan tar över ett sammanträde som kom från ett beslut, som en ny version."""
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0}
    befintliga = _versioner(conn, plan.organ)
    sedda: set[str] = set()
    for r in _odaterade_till_datum(plan.rader, befintliga):
        if r.nyckel in sedda:
            continue  # samma datum två gånger i tabellen
        sedda.add(r.nyckel)
        varden = {"datum": r.datum, "starttid": r.starttid, "status": r.status, "anmarkning": r.anmarkning}
        b = befintliga.get(r.nyckel)
        if b is not None:
            samma_kalla = (b["kalla"], b["beslut_sammantrade_id"], b["beslut_paragraf"]) == (
                kalla.typ, kalla.sammantrade_id, kalla.paragraf)
            if samma_kalla and all(b[f] == varden[f] for f in FALT):
                antal["oforandrade"] += 1
                continue
            _ny_version(conn, b["id"], b["version"] + 1, varden, r.kalltext, plan.url, korning_id, hamtad, kalla)
            antal["andrade"] += 1
            continue
        # Ett hållet sammanträde vars protokoll redan är inläst får planens uppgifter.
        protokoll = None
        if r.datum is not None:
            protokoll = narmast(r.starttid, conn.execute(
                """
                SELECT id, starttid FROM sammantrade
                WHERE organ = %s AND datum = %s AND plan_nyckel IS NULL AND dokument_id IS NOT NULL ORDER BY id
                """,
                (plan.organ, r.datum),
            ).fetchall())
        if protokoll is not None:
            sammantrade_id = protokoll["id"]
            conn.execute("UPDATE sammantrade SET plan_nyckel = %s, plan_status = %s, plan_version = 1, plan_kalla = %s "
                         "WHERE id = %s", (r.nyckel, r.status, kalla.typ, sammantrade_id))
        else:
            sammantrade_id = conn.execute(
                """
                INSERT INTO sammantrade (organ, nyckel, datum, plan_nyckel, plan_status, plan_version, plan_kalla)
                VALUES (%s, %s, %s, %s, %s, 1, %s) RETURNING id
                """,
                (plan.organ, f"plan:{r.nyckel}", r.datum, r.nyckel, r.status, kalla.typ),
            ).fetchone()["id"]
        _ny_version(conn, sammantrade_id, 1, varden, r.kalltext, plan.url, korning_id, hamtad, kalla)
        antal["nya"] += 1
    # Sammanträden som försvunnit från sidan, för de år sidan visar.
    for nyckel, b in befintliga.items():
        if nyckel in sedda or int(nyckel[:4]) not in plan.ar or b["status"] == "borttaget":
            continue
        varden = {f: b[f] for f in FALT} | {"status": "borttaget"}
        _ny_version(conn, b["id"], b["version"] + 1, varden, "", plan.url, korning_id, hamtad, kalla)
        antal["andrade"] += 1
    return antal


# Ett sammanträde som börjar senare än planerat är samma sammanträde. Har organet bara ett sammanträde
# den dagen kopplas det oavsett tid (#107). Två sammanträden samma dag, t.ex. fullmäktige 2026-10-26
# kl. 11.00 och 13.15, skiljs åt med tiden: det närmaste inom gränsen.
MAX_AVVIKELSE_MINUTER = 60


def _minuter(tid: str | None) -> int | None:
    if not tid or not re.fullmatch(r"\d{2}:\d{2}", tid):
        return None
    return int(tid[:2]) * 60 + int(tid[3:])


def narmast(starttid: str | None, kandidater: list[dict], entydig: bool = True) -> dict | None:
    """Kandidaten (med 'starttid') som ligger närmast i tid. Saknas en av tiderna räknas den som lika.

    En enda kandidat väljs oavsett tid, om inte `entydig` är falskt (det finns fler sammanträden den
    dagen på andra sidan). Annars väljs den närmaste, och ingen om ingen ligger inom MAX_AVVIKELSE_MINUTER."""
    if entydig and len(kandidater) == 1:
        return kandidater[0]
    bast, bast_avvikelse = None, None
    for k in kandidater:
        a, b = _minuter(starttid), _minuter(k["starttid"])
        avvikelse = 0 if a is None or b is None else abs(a - b)
        if avvikelse <= MAX_AVVIKELSE_MINUTER and (bast_avvikelse is None or avvikelse < bast_avvikelse):
            bast, bast_avvikelse = k, avvikelse
    return bast


def planerat_for_protokoll(conn: psycopg.Connection, organ: str, datum: date | None,
                           starttid: str | None) -> int | None:
    """Det planerade sammanträde som ett nytt protokoll hör till: samma organ och datum, och starttiden
    när den behövs. Ett sammanträde som inte blev av kopplas bara om inget annat passar.

    Har organet redan ett protokoll den dagen är dagen inte entydig, och tiden avgör (se `narmast`)."""
    if datum is None:
        return None
    kandidater = conn.execute(
        """
        SELECT id, plan_starttid AS starttid FROM sammantrade
        WHERE organ = %s AND plan_datum = %s AND dokument_id IS NULL
        ORDER BY plan_status = 'planerat' DESC, id
        """,
        (organ, datum),
    ).fetchall()
    fler_protokoll = conn.execute(
        "SELECT 1 FROM sammantrade WHERE organ = %s AND datum = %s AND dokument_id IS NOT NULL", (organ, datum),
    ).fetchone() is not None
    rad = narmast(starttid, kandidater, entydig=not fler_protokoll)
    return rad["id"] if rad else None


def koppla_om(conn: psycopg.Connection, sammantrade_id: int) -> int | None:
    """Ett nytt protokoll som passar organets planerade sammanträde den dagen bättre än det protokoll
    planen kopplades till (när det var dagens enda) tar över planen. Returnerar planens tidigare sammanträde."""
    s = conn.execute("SELECT organ, datum, starttid, plan_nyckel FROM sammantrade WHERE id = %s",
                     (sammantrade_id,)).fetchone()
    if s is None or s["plan_nyckel"] is not None or s["datum"] is None or _minuter(s["starttid"]) is None:
        return None
    for p in conn.execute(
        """
        SELECT id, starttid, plan_starttid FROM sammantrade
        WHERE organ = %s AND plan_datum = %s AND dokument_id IS NOT NULL AND id <> %s ORDER BY id
        """,
        (s["organ"], s["datum"], sammantrade_id),
    ).fetchall():
        plan, fore = _minuter(p["plan_starttid"]), _minuter(p["starttid"])
        if plan is None or fore is None:
            continue
        ny = abs(plan - _minuter(s["starttid"]))
        if abs(plan - fore) > MAX_AVVIKELSE_MINUTER and ny <= MAX_AVVIKELSE_MINUTER:
            flytta_plan(conn, p["id"], sammantrade_id)
            return p["id"]
    return None


PLANKOLUMNER = ("plan_nyckel", "plan_datum", "plan_starttid", "plan_status", "plan_anmarkning", "plan_url",
                "plan_version", "plan_kalla", "plan_beslut_sammantrade_id", "plan_beslut_paragraf")


def flytta_plan(conn: psycopg.Connection, fran: int, till: int) -> None:
    """Flyttar planens uppgifter och versioner från ett sammanträde till ett annat utan plan."""
    varden = conn.execute(f"SELECT {', '.join(PLANKOLUMNER)} FROM sammantrade WHERE id = %s", (fran,)).fetchone()
    mal = conn.execute("SELECT plan_nyckel FROM sammantrade WHERE id = %s", (till,)).fetchone()
    if varden is None or varden["plan_nyckel"] is None or mal is None or mal["plan_nyckel"] is not None:
        raise ValueError(f"planen kan inte flyttas från sammanträde {fran} till {till}")
    conn.execute(f"UPDATE sammantrade SET {', '.join(f'{k} = NULL' for k in PLANKOLUMNER)} WHERE id = %s", (fran,))
    conn.execute(f"UPDATE sammantrade SET {', '.join(f'{k} = %({k})s' for k in PLANKOLUMNER)} WHERE id = %(id)s",
                 {**varden, "id": till})
    conn.execute("UPDATE planversion SET sammantrade_id = %s WHERE sammantrade_id = %s", (till, fran))


def sla_ihop_dubbletter(conn: psycopg.Connection) -> list[dict]:
    """Slår ihop planerade sammanträden utan protokoll med protokollet samma dag för samma organ, när
    kopplingen är entydig enligt `narmast` (#107). Planen flyttas till protokollets sammanträde och det
    tomma planerade sammanträdet tas bort. Kallelser och webbsändningar hör till organ och datum och
    följer med. Returnerar paren."""
    ut = []
    for p in conn.execute(
        """
        SELECT id, organ, plan_datum, plan_starttid FROM sammantrade
        WHERE plan_nyckel IS NOT NULL AND dokument_id IS NULL AND plan_datum IS NOT NULL ORDER BY organ, plan_datum, id
        """
    ).fetchall():
        k = narmast(p["plan_starttid"], conn.execute(
            """
            SELECT id, starttid FROM sammantrade
            WHERE organ = %s AND datum = %s AND dokument_id IS NOT NULL AND plan_nyckel IS NULL ORDER BY id
            """,
            (p["organ"], p["plan_datum"]),
        ).fetchall())
        if k is None:
            continue
        flytta_plan(conn, p["id"], k["id"])
        # Hänvisningar till det tomma sammanträdet (det finns inga, men en hänvisning ska inte försvinna).
        conn.execute("UPDATE sammantrade SET plan_beslut_sammantrade_id = %s WHERE plan_beslut_sammantrade_id = %s",
                     (k["id"], p["id"]))
        conn.execute("UPDATE planversion SET beslut_sammantrade_id = %s WHERE beslut_sammantrade_id = %s",
                     (k["id"], p["id"]))
        conn.execute("DELETE FROM sammantrade WHERE id = %s", (p["id"],))
        ut.append({"organ": p["organ"], "datum": p["plan_datum"], "planerat_id": p["id"],
                   "plan_starttid": p["plan_starttid"], "protokoll_id": k["id"], "starttid": k["starttid"]})
    return ut


# Läsning


def _plan_ut(r: dict) -> dict:
    return {
        "id": r["id"],
        "nyckel": r["plan_nyckel"],
        "datum": r["plan_datum"].isoformat() if r["plan_datum"] else None,
        "manad": r["plan_nyckel"][:7],
        "starttid": r["plan_starttid"],
        "status": r["plan_status"],
        "anmarkning": r["plan_anmarkning"],
        "version": r["plan_version"],
        "protokoll": r["dokument_id"] is not None,
        "kalla": r["plan_kalla"],
        "beslut": {"sammantrade_id": r["plan_beslut_sammantrade_id"], "paragraf": r["plan_beslut_paragraf"],
                   "datum": r["beslut_datum"].isoformat() if r["beslut_datum"] else None}
        if r["plan_kalla"] == "beslut" else None,
    }


def lista(conn: psycopg.Connection) -> list[dict]:
    """Planerna per organ och år, med versionerna och jämförelsen mot besluten i protokollen."""
    rader = conn.execute(
        """
        SELECT s.id, s.organ, s.plan_nyckel, s.plan_datum, s.plan_starttid, s.plan_status, s.plan_anmarkning,
               s.plan_version, s.plan_url, s.dokument_id, s.plan_kalla, s.plan_beslut_sammantrade_id,
               s.plan_beslut_paragraf, bs.datum AS beslut_datum
        FROM sammantrade s LEFT JOIN sammantrade bs ON bs.id = s.plan_beslut_sammantrade_id
        WHERE s.plan_nyckel IS NOT NULL
        ORDER BY s.organ, s.plan_nyckel
        """
    ).fetchall()
    versioner: dict[int, list[dict]] = {}
    for v in conn.execute(
        """
        SELECT sammantrade_id, version, datum, starttid, status, anmarkning, kalltext, hamtad, kalla
        FROM planversion ORDER BY sammantrade_id, version
        """
    ):
        versioner.setdefault(v["sammantrade_id"], []).append({
            "version": v["version"], "datum": v["datum"].isoformat() if v["datum"] else None,
            "starttid": v["starttid"], "status": v["status"], "anmarkning": v["anmarkning"],
            "kalltext": v["kalltext"], "hamtad": v["hamtad"].isoformat(), "kalla": v["kalla"],
        })
    planer: dict[tuple[str, int], dict] = {}
    for r in rader:
        ar = int(r["plan_nyckel"][:4])
        p = planer.setdefault((r["organ"], ar), {
            "organ": {"id": r["organ"], "namn": ORGAN[r["organ"]].namn}, "ar": ar, "url": r["plan_url"],
            "sammantraden": [],
        })
        p["url"] = p["url"] or r["plan_url"]  # Sammanträden ur beslut har ingen sida (#99).
        p["sammantraden"].append({**_plan_ut(r), "versioner": versioner.get(r["id"], [])})
    beslut = beslut_om_planer(conn)
    ut = []
    for (organ, ar), p in sorted(planer.items(), key=lambda x: (list(ORGAN).index(x[0][0]), x[0][1])):
        b = beslut.get((organ, ar))
        p["beslut"] = b["beslut"] if b else []
        # Året har ingen plan på webbsidan än: alla sammanträden kommer från besluten (#99).
        p["bara_beslut"] = all(x["kalla"] == "beslut" for x in p["sammantraden"])
        # Utan ett beslut som anger datumen går planen inte att jämföra.
        p["skillnader"] = skillnader(p["sammantraden"], b["datum"]) if b and b["fullstandig"] else None
        ut.append(p)
    return ut


# Besluten om sammanträdesplanerna i protokollen

_DATUM = re.compile(r"(\d{1,2})\s+(" + "|".join(MANADER) + r")(?:\s+(20\d{2}))?", re.IGNORECASE)
_TID = re.compile(r"(\d{1,2})[.:](\d{2})")
_PLANRUBRIK = r"sammanträdes(tider|dagar|plan|datum)"
_HELA_PLANEN = re.compile(
    r"^(?P<subjekt>[a-zåäö ]+?)\s+sammanträder\s+(?:kl\.?\s*)?(?P<tid>\d{1,2}[.:]\d{2})?\s*"
    r"följande\s+(?:datum|dagar)\s*:?(?P<datum>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_INSTALLS = re.compile(r"sammanträde(?:t)?\s+(?:den\s+)?(?P<fran>\d{1,2}\s+[a-zåäö]+(?:\s+20\d{2})?)\s+ställs\s+in",
                       re.IGNORECASE)
_FLYTTAS = re.compile(
    r"sammanträde(?:t)?\s+(?:den\s+)?(?P<fran>\d{1,2}\s+[a-zåäö]+(?:\s+20\d{2})?)\s+"
    r"(?:flyttas|senareläggs|tidigareläggs)\s+till\s+(?:den\s+)?(?P<till>\d{1,2}\s+[a-zåäö]+(?:\s+20\d{2})?)",
    re.IGNORECASE,
)
_ANNAT_ORGAN = re.compile(r"utskott|beredning", re.IGNORECASE)


def _datumlista(text: str, ar: int | None) -> list[date]:
    # Listan slutar vid en mening som börjar med versal, t.ex. "… 24 november Beslutet gäller …".
    text = re.split(r"\.(?!\d)|\s(?=[A-ZÅÄÖ])", text, maxsplit=1)[0]
    ut = []
    for dag, manad, ar_i_text in _DATUM.findall(text):
        a = int(ar_i_text) if ar_i_text else ar
        if a is None:
            continue
        try:
            ut.append(date(a, MANADER[manad.lower()], int(dag)))
        except ValueError:
            continue
    return ut


def tolka_beslut(beslut: str, organ: str, ar: int | None) -> list[tuple[str, object]]:
    """Beslutets att-satser om organets egna sammanträden, i ordning:
    ('plan', (starttid, [datum])), ('installt', datum) eller ('flyttat', (från, till))."""
    namn = ORGAN[organ].namn.lower()
    satser = re.split(r"(?:^|\n|\s)att\s+", beslut)
    ut: list[tuple[str, object]] = []
    for sats in satser[1:]:
        sats = " ".join(sats.split())
        if _ANNAT_ORGAN.search(sats):
            continue
        if m := _HELA_PLANEN.match(sats):
            if m["subjekt"].strip().lower() != namn:
                continue  # t.ex. kommunstyrelsens förslag om fullmäktiges sammanträden
            tid = _TID.fullmatch(m["tid"]) if m["tid"] else None
            datum = _datumlista(m["datum"], ar)
            if datum:
                ut.append(("plan", (f"{int(tid[1]):02d}:{tid[2]}" if tid else None, datum)))
            continue
        if m := _FLYTTAS.search(sats):
            fran, till = _datumlista(m["fran"], ar), _datumlista(m["till"], ar)
            if fran and till:
                ut.append(("flyttat", (fran[0], till[0])))
            continue
        if m := _INSTALLS.search(sats):
            if fran := _datumlista(m["fran"], ar):
                ut.append(("installt", fran[0]))
    return ut


def _tom() -> dict:
    # fullstandig: något beslut anger alla datum för året (inte bara "att anta förslaget").
    # installda: inställda datum, flyttade: från → till (används när planen lagras ur besluten).
    return {"beslut": [], "datum": {}, "fullstandig": False, "installda": set(), "flyttade": {}}


def beslut_om_planer(conn: psycopg.Connection) -> dict[tuple[str, int], dict]:
    """(organ, år) → besluten om organets sammanträdesplan för året och de datum som gäller enligt dem."""
    # Rättade beslut gäller (ADR-0002). Rubriken väljs på tolkningen och prövas igen efter rättelsen.
    rader = [r for r in behandlingar.las(conn, rubrik=_PLANRUBRIK)
             if r["beslut"] and r["datum"] is not None and re.search(_PLANRUBRIK, r["rubrik"] or "", re.I)]
    rader.sort(key=lambda r: (r["datum"], r["paragraf"]))
    ut: dict[tuple[str, int], dict] = {}
    for r in rader:
        if r["organ"] not in ORGAN:
            continue
        ar_i_rubrik = {int(a) for a in re.findall(r"\b(20\d{2})\b", r["rubrik"])}
        ar = ar_i_rubrik.pop() if len(ar_i_rubrik) == 1 else None
        aren: set[int] = set()
        for typ, varde in tolka_beslut(r["beslut"], r["organ"], ar):
            if typ == "plan":
                tid, datum = varde
                for a in {d.year for d in datum}:
                    # En ny plan för året ersätter den tidigare.
                    p = ut.setdefault((r["organ"], a), _tom())
                    p["datum"] = {d: tid for d in datum if d.year == a}
                    p["fullstandig"] = True
                    p["installda"], p["flyttade"] = set(), {}
                    aren.add(a)
                continue
            fran, till = varde if typ == "flyttat" else (varde, None)
            p = ut.setdefault((r["organ"], fran.year), _tom())
            tid = p["datum"].pop(fran, None)
            aren.add(fran.year)
            if till is None:
                p["installda"].add(fran)
            else:
                ut.setdefault((r["organ"], till.year), _tom())["datum"][till] = tid
                p["flyttade"][fran] = till
                aren.add(till.year)
        for a in sorted(aren):
            ut[(r["organ"], a)]["beslut"].append({
                "sammantrade_id": r["sammantrade_id"], "paragraf": r["paragraf"], "rubrik": r["rubrik"],
                "datum": r["datum"].isoformat(),
            })
    return ut


def skillnader(sammantraden: list[dict], beslutade: dict[date, str | None]) -> list[dict]:
    """Datum där webbsidans planerade sammanträden och besluten skiljer sig åt."""
    sidan = {s["datum"]: s for s in sammantraden if s["datum"] and s["status"] == "planerat"}
    beslut = {d.isoformat(): t for d, t in beslutade.items()}
    ut = []
    for d in sorted(set(sidan) | set(beslut)):
        s, b = sidan.get(d), d in beslut
        if s and not b:
            ut.append({"datum": d, "typ": "bara_sidan", "sidan": s["starttid"], "beslutet": None})
        elif b and not s:
            installt = next((x for x in sammantraden if x["datum"] == d), None)
            ut.append({"datum": d, "typ": "bara_beslutet", "sidan": installt["status"] if installt else None,
                       "beslutet": beslut[d]})
        elif s and beslut[d] and s["starttid"] and s["starttid"] != beslut[d]:
            ut.append({"datum": d, "typ": "tid", "sidan": s["starttid"], "beslutet": beslut[d]})
    return ut


# Kallelser och webbsändningar (#68, del 3)


def lagra_kallelser(conn: psycopg.Connection, kallelser: list, webbsandningar: list, korning_id: int | None,
                    hamtad: datetime) -> dict[str, int]:
    """Sparar kallelser och webbsändningar. En kallelse som lästs behåller sin plats även när den inte läses igen.

    `lasta_listor` i svaret: antalet kallelser vars föredragningslista lästes (#109), så att behandlingarna
    kan kompletteras med diarienumren (`kallelsepunkter.komplettera`)."""
    from .kallelsepunkter import lagra_punkter

    antal = {"nya": 0, "andrade": 0, "oforandrade": 0, "lasta_listor": 0}
    for k in kallelser:
        fore = conn.execute("SELECT id, tid, plats, pdf_last, punkter_status FROM kallelse WHERE url = %s",
                            (k.url,)).fetchone()
        if k.foredragningslista is not None and (fore is None or fore["punkter_status"] == "ej_last"):
            antal["lasta_listor"] += 1
        if fore is None:
            kallelse_id = conn.execute(
                """
                INSERT INTO kallelse (organ, datum, tid, typ, titel, url, storlek, plats, pdf_last, forst_sedd,
                                      senast_sedd, korning_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (k.organ, k.datum, k.tid, k.typ, k.titel, k.url, k.storlek, k.plats, k.pdf_last, hamtad, hamtad,
                 korning_id),
            ).fetchone()["id"]
            if k.foredragningslista is not None:
                lagra_punkter(conn, kallelse_id, k.foredragningslista, hamtad)
            antal["nya"] += 1
            continue
        if k.foredragningslista is not None and fore["punkter_status"] == "ej_last":
            lagra_punkter(conn, fore["id"], k.foredragningslista, hamtad)
        if k.pdf_last and not fore["pdf_last"]:
            conn.execute("UPDATE kallelse SET tid = %s, plats = %s, pdf_last = true, senast_sedd = %s WHERE url = %s",
                         (k.tid or fore["tid"], k.plats, hamtad, k.url))
            antal["andrade"] += 1
        else:
            conn.execute("UPDATE kallelse SET senast_sedd = %s WHERE url = %s", (hamtad, k.url))
            antal["oforandrade"] += 1
    for w in webbsandningar:
        rad = conn.execute(
            """
            INSERT INTO webbsandning (organ, datum, url, titel, forst_sedd, senast_sedd, korning_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET senast_sedd = EXCLUDED.senast_sedd
            RETURNING (xmax = 0) AS ny
            """,
            (w.organ, w.datum, w.url, w.titel, hamtad, hamtad, korning_id),
        ).fetchone()
        antal["nya" if rad["ny"] else "oforandrade"] += 1
    return antal


# Planer ur besluten (#99)


def _ar_med_webbplan(conn: psycopg.Connection) -> set[tuple[str, int]]:
    return {(r["organ"], r["ar"]) for r in conn.execute(
        "SELECT DISTINCT organ, left(plan_nyckel, 4)::int AS ar FROM sammantrade WHERE plan_kalla = 'webbsidan'"
    )}


def lagra_beslut(conn: psycopg.Connection, idag: date, korning_id: int | None = None,
                 hamtad: datetime | None = None) -> dict[str, int]:
    """Planerade sammanträden ur organens beslut för år som saknar plan på webbsidan, från och med i år.

    Besluten tolkas som på sidan Planer (`beslut_om_planer`). Planen gäller bara när något beslut anger
    alla datum för året. Ett flyttat sammanträde är samma sammanträde med nytt datum, och ett inställt
    finns kvar som inställt. Varje ändring blir en ny version, som för planerna på webbsidan.
    """
    hamtad = hamtad or datetime.now().astimezone()
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0}
    webb = _ar_med_webbplan(conn)
    for (organ, ar), p in sorted(beslut_om_planer(conn).items()):
        if ar < idag.year or not p["fullstandig"] or (organ, ar) in webb or not p["beslut"]:
            continue
        b = p["beslut"][-1]
        kalla = Kalla("beslut", b["sammantrade_id"], b["paragraf"])
        kalltext = f"{ORGAN[organ].namn} {b['datum']} § {b['paragraf']}: {b['rubrik']}"
        # Ett flyttat sammanträde behåller sin rad: nyckeln och datumet flyttas innan planen lagras.
        befintliga = _versioner(conn, organ)
        for fran, till in p["flyttade"].items():
            gammal, ny = befintliga.get(fran.isoformat()), till.isoformat()
            if gammal is not None and gammal["kalla"] == "beslut" and ny not in befintliga and till.year == ar:
                conn.execute("UPDATE sammantrade SET plan_nyckel = %s, datum = %s WHERE id = %s AND dokument_id IS NULL",
                             (ny, till, gammal["id"]))
        rader = [Planrad(organ, ar, d.month, d, tid, "planerat", None, kalltext) for d, tid in sorted(p["datum"].items())
                 if d.year == ar]
        rader += [Planrad(organ, ar, d.month, d, befintliga[d.isoformat()]["starttid"]
                          if d.isoformat() in befintliga else None, "installt", None, kalltext)
                  for d in sorted(p["installda"]) if d.year == ar]
        for k, v in lagra(conn, Sammantradesplan(organ, None, [ar], rader), korning_id, hamtad, kalla).items():
            antal[k] += v
    return antal
