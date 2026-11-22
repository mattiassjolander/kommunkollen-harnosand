"""Kalendern över sammanträden: händelser för sidan Kalender och ics-flöden enligt RFC 5545 (#68).

En händelse är ett sammanträde i ett av de fem organen: planerat enligt sammanträdesplanen, eller hållet
med protokoll (även ett extra sammanträde som inte fanns i planen). Ett sammanträde utan datum (en månad
som bara anges som inställd) ingår inte.

- Starttiden kommer från planen, eller från protokollet när sammanträdet är hållet.
- Sluttiden är protokollets, eller starttiden plus medianlängden för organets sammanträden enligt
  protokollen (3 timmar för fullmäktige och 4 för övriga utan historik). Då är den ungefärlig.
- Platsen är protokollets, eller platsen i organets senaste protokoll, markerad som antagen.
- Varje sammanträde har ett stabilt UID. SEQUENCE ökar när planen ändras och när protokollet kommer.
- Ett inställt eller borttaget sammanträde finns kvar med STATUS:CANCELLED.
- Flödena innehåller de kommande sammanträdena och de senaste 12 månaderna.
"""

from __future__ import annotations

import os
import statistics
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg

from .sammantradesplan import narmast
from .sources.harnosand import ORGAN
from .sources.kallelser import WEBB_TV

TZ = ZoneInfo("Europe/Stockholm")
SLUG = {
    "KF": "kommunfullmaktige",
    "KS": "kommunstyrelsen",
    "SAM": "samhallsnamnden",
    "SOC": "socialnamnden",
    "SKOL": "skolnamnden",
}
ALLA = "alla"
STANDARDLANGD_MINUTER = {"KF": 180}  # övriga: 240
HISTORIK_DAGAR = 365
UID_DOMAN = "kommunkollen-harnosand"


def idag() -> date:
    """Dagens datum i Sverige. KOMMUNKOLLEN_IDAG (ÅÅÅÅ-MM-DD) låser datumet i e2e-tester och lokal utveckling."""
    if v := os.environ.get("KOMMUNKOLLEN_IDAG"):
        return date.fromisoformat(v)
    return datetime.now(TZ).date()


def organ_for_slug(slug: str) -> str | None:
    """'kommunfullmaktige' → 'KF', 'alla' → '' och okänt → None."""
    if slug == ALLA:
        return ""
    return next((o for o, s in SLUG.items() if s == slug), None)


def _minuter(tid: str | None) -> int | None:
    if not tid or len(tid) != 5 or tid[2] != ":":
        return None
    return int(tid[:2]) * 60 + int(tid[3:])


def langder(conn: psycopg.Connection) -> dict[str, int]:
    """Medianlängden i minuter för varje organs sammanträden enligt protokollen."""
    per_organ: dict[str, list[int]] = {}
    for r in conn.execute(
        "SELECT organ, starttid, sluttid FROM sammantrade WHERE dokument_id IS NOT NULL AND sluttid IS NOT NULL"
    ):
        start, slut = _minuter(r["starttid"]), _minuter(r["sluttid"])
        if start is not None and slut is not None and slut > start:
            per_organ.setdefault(r["organ"], []).append(slut - start)
    return {o: round(statistics.median(v)) for o, v in per_organ.items()}


def _senaste_platser(conn: psycopg.Connection) -> dict[str, str]:
    return {r["organ"]: r["plats"] for r in conn.execute(
        """
        SELECT DISTINCT ON (organ) organ, plats FROM sammantrade
        WHERE dokument_id IS NOT NULL AND plats IS NOT NULL AND datum IS NOT NULL
        ORDER BY organ, datum DESC, starttid DESC NULLS LAST
        """
    )}


def handelser(conn: psycopg.Connection, organ: str | None = None, sammantrade_id: int | None = None,
              fran: date | None = None) -> list[dict]:
    """Sammanträdena från och med `fran` (standard: 12 månader bakåt), i tidsordning."""
    fran = fran if fran is not None else idag() - timedelta(days=HISTORIK_DAGAR)
    rader = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.starttid, s.sluttid, s.plats, s.dokument_id, s.plan_nyckel,
               s.plan_starttid, s.plan_status, s.plan_version, s.plan_url, d.hamtad AS protokoll_hamtad,
               (SELECT max(v.hamtad) FROM planversion v WHERE v.sammantrade_id = s.id) AS plan_andrad
        FROM sammantrade s LEFT JOIN dokument d ON d.id = s.dokument_id
        WHERE s.datum IS NOT NULL AND s.organ = ANY(%(organ)s)
          AND (%(id)s::bigint IS NULL OR s.id = %(id)s)
          AND (%(id)s::bigint IS NOT NULL OR s.datum >= %(fran)s)
        ORDER BY s.datum, coalesce(s.starttid, s.plan_starttid) NULLS FIRST, s.id
        """,
        {"organ": [organ] if organ else list(ORGAN), "id": sammantrade_id, "fran": fran},
    ).fetchall()
    langd = langder(conn)
    platser = _senaste_platser(conn)
    ut = []
    for r in rader:
        hallet = r["dokument_id"] is not None
        starttid = (r["starttid"] if hallet and r["starttid"] else None) or r["plan_starttid"] or r["starttid"]
        sluttid, ungefarlig = (r["sluttid"], False) if hallet and r["sluttid"] else (None, True)
        if sluttid is None and (start := _minuter(starttid)) is not None:
            slut = min(start + langd.get(r["organ"], STANDARDLANGD_MINUTER.get(r["organ"], 240)), 23 * 60 + 59)
            sluttid = f"{slut // 60:02d}:{slut % 60:02d}"
        # Platsen: protokollets, annars kallelsens (se _koppla_kallelser), annars organets senaste protokoll.
        plats, kalla = (r["plats"], "protokoll") if hallet and r["plats"] else (platser.get(r["organ"]), "antagen")
        status = r["plan_status"] if r["plan_status"] in ("installt", "borttaget") and not hallet else (
            "hallet" if hallet else "planerat")
        andrad = max((t for t in (r["plan_andrad"], r["protokoll_hamtad"]) if t), default=None)
        ut.append({
            "id": r["id"],
            "uid": f"sammantrade-{r['id']}@{UID_DOMAN}",
            "organ": {"id": r["organ"], "namn": ORGAN[r["organ"]].namn, "flode": SLUG[r["organ"]]},
            "datum": r["datum"].isoformat(),
            "starttid": starttid,
            "sluttid": sluttid if starttid else None,
            "sluttid_ungefarlig": bool(starttid) and ungefarlig,
            "plats": plats,
            "plats_antagen": bool(plats) and kalla == "antagen",
            "plats_kalla": kalla if plats else None,
            "status": status,
            "protokoll": hallet,
            "sekvens": max((r["plan_version"] or 1) - 1, 0) + (1 if hallet and r["plan_nyckel"] else 0),
            "andrad": andrad.isoformat() if andrad else None,
            "plan_url": r["plan_url"],
            "kallelse": None,
            "handlingar": [],
            "webbsandning": None,
        })
    _koppla_kallelser(conn, ut)
    return ut


def _koppla_kallelser(conn: psycopg.Connection, handelser_: list[dict]) -> None:
    """Kallelser, handlingar och webbsändningar till sammanträdena: samma organ och datum. Har organet flera
    sammanträden samma dag går en kallelse med klockslag till det som ligger närmast i tid."""
    if not handelser_:
        return
    per_dag: dict[tuple[str, str], list[dict]] = {}
    for h in handelser_:
        per_dag.setdefault((h["organ"]["id"], h["datum"]), []).append(h)
    datum = sorted({date.fromisoformat(h["datum"]) for h in handelser_})
    for k in conn.execute(
        """
        SELECT organ, datum, tid, typ, titel, url, storlek, plats FROM kallelse
        WHERE datum BETWEEN %s AND %s ORDER BY forst_sedd, id
        """,
        (datum[0], datum[-1]),
    ):
        dagens = per_dag.get((k["organ"], k["datum"].isoformat()), [])
        mal = [narmast(k["tid"], dagens)] if k["tid"] and len(dagens) > 1 else dagens
        for h in (x for x in mal if x is not None):
            if k["typ"] == "handlingar":
                h["handlingar"].append({"titel": k["titel"], "url": k["url"], "storlek": k["storlek"]})
                continue
            # Den senast publicerade kallelsen gäller.
            h["kallelse"] = {"titel": k["titel"], "url": k["url"], "typ": k["typ"]}
            if k["plats"] and h["plats_kalla"] != "protokoll":
                h["plats"], h["plats_kalla"], h["plats_antagen"] = k["plats"], "kallelse", False
    inspelningar = {r["datum"].isoformat(): r["url"] for r in conn.execute(
        "SELECT datum, url FROM webbsandning WHERE organ = 'KF' AND datum BETWEEN %s AND %s ORDER BY forst_sedd",
        (datum[0], datum[-1]),
    )}
    for h in handelser_:
        if h["organ"]["id"] != "KF" or h["status"] in ("installt", "borttaget"):
            continue
        # Före sammanträdet: sidan för webb-tv. Efter: inspelningen, när den finns.
        if inspelning := inspelningar.get(h["datum"]):
            h["webbsandning"] = {"url": inspelning, "inspelning": True}
        else:
            h["webbsandning"] = {"url": WEBB_TV, "inspelning": False}


# ics enligt RFC 5545

VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Stockholm",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def text(v: str) -> str:
    """Escapar ett TEXT-värde (RFC 5545 3.3.11)."""
    return v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def vik(rad: str) -> str:
    """Viker en innehållsrad till högst 75 oktetter per rad (RFC 5545 3.1), utan att dela ett UTF-8-tecken."""
    delar, aktuell, langd, grans = [], "", 0, 75
    for tecken in rad:
        n = len(tecken.encode("utf-8"))
        if langd + n > grans:
            delar.append(aktuell)
            aktuell, langd, grans = " ", 1, 75
        aktuell += tecken
        langd += n
    delar.append(aktuell)
    return "\r\n".join(delar)


def _tid(datum: str, tid: str) -> str:
    return f"{datum.replace('-', '')}T{tid.replace(':', '')}00"


def _vevent(h: dict, bas: str) -> list[str]:
    namn = h["organ"]["namn"]
    installt = h["status"] in ("installt", "borttaget")
    rubrik = f"{namn} – sammanträde"
    if h["status"] == "installt":
        rubrik = f"Inställt: {rubrik}"
    elif h["status"] == "borttaget":
        rubrik = f"Borttaget ur planen: {rubrik}"
    stampel = datetime.fromisoformat(h["andrad"]) if h["andrad"] else datetime.now(timezone.utc)
    rader = [
        "BEGIN:VEVENT",
        f"UID:{h['uid']}",
        f"DTSTAMP:{stampel.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    ]
    if h["starttid"]:
        rader += [f"DTSTART;TZID=Europe/Stockholm:{_tid(h['datum'], h['starttid'])}",
                  f"DTEND;TZID=Europe/Stockholm:{_tid(h['datum'], h['sluttid'])}"]
    else:
        d = date.fromisoformat(h["datum"])
        rader += [f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}"]
    sida = f"{bas}/politik/sammantraden/{h['id']}" if h["protokoll"] else f"{bas}/kalender?sammantrade={h['id']}"
    beskrivning = []
    if h["status"] == "installt":
        beskrivning.append("Sammanträdet är inställt.")
    elif h["status"] == "borttaget":
        beskrivning.append("Sammanträdet har tagits bort ur sammanträdesplanen på harnosand.se.")
    if h["sluttid_ungefarlig"]:
        beskrivning.append("Sluttiden är ungefärlig, beräknad utifrån hur länge organets sammanträden brukar pågå.")
    if h["plats_antagen"]:
        beskrivning.append("Platsen är antagen utifrån organets senaste protokoll.")
    if h["kallelse"]:
        namn_k = "Kungörelse" if h["kallelse"]["typ"] == "kungorelse" else "Kallelse"
        beskrivning.append(f"{namn_k}: {h['kallelse']['url']}")
    for x in h["handlingar"]:
        beskrivning.append(f"Handlingar: {x['url']}")
    if h["webbsandning"]:
        etikett = "Inspelning" if h["webbsandning"]["inspelning"] else "Webbsänds, webb-tv"
        beskrivning.append(f"{etikett}: {h['webbsandning']['url']}")
    if h["protokoll"]:
        beskrivning.append(f"Protokoll: {sida}")
    else:
        beskrivning.append(f"Sammanträdet i Kommunkollen: {sida}")
    if h["plan_url"]:
        beskrivning.append(f"Sammanträdesplanen: {h['plan_url']}")
    rader += [
        f"SEQUENCE:{h['sekvens']}",
        f"STATUS:{'CANCELLED' if installt else 'CONFIRMED'}",
        f"SUMMARY:{text(rubrik)}",
    ]
    if h["plats"]:
        rader.append(f"LOCATION:{text(h['plats'])}")
    rader += [f"DESCRIPTION:{text(chr(10).join(beskrivning))}", f"URL:{sida}", "TRANSP:OPAQUE", "END:VEVENT"]
    return rader


def ics(handelser_: list[dict], namn: str, bas: str) -> str:
    """Ett VCALENDAR med händelserna, med CRLF och vikta rader."""
    rader = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kommunkollen Härnösand//Sammanträden//SV",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{text(namn)}",
        "X-WR-TIMEZONE:Europe/Stockholm",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
        *VTIMEZONE,
    ]
    for h in handelser_:
        rader += _vevent(h, bas)
    rader.append("END:VCALENDAR")
    return "".join(vik(r) + "\r\n" for r in rader)


def flodesnamn(organ: str) -> str:
    return f"{ORGAN[organ].namn} – sammanträden" if organ else "Härnösands kommun – sammanträden"
