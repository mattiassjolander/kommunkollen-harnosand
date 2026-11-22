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
from datetime import date, datetime

import psycopg

from .sources.harnosand import ORGAN
from .sources.sammantradesplaner import MANADER, Planrad, Sammantradesplan

FALT = ("datum", "starttid", "status", "anmarkning")


def _versioner(conn: psycopg.Connection, organ: str) -> dict[str, dict]:
    return {r["plan_nyckel"]: r for r in conn.execute(
        """
        SELECT id, plan_nyckel, plan_datum AS datum, plan_starttid AS starttid, plan_status AS status,
               plan_anmarkning AS anmarkning, plan_version AS version
        FROM sammantrade WHERE organ = %s AND plan_nyckel IS NOT NULL
        """,
        (organ,),
    )}


def _ny_version(conn: psycopg.Connection, sammantrade_id: int, version: int, varden: dict, kalltext: str,
                url: str, korning_id: int | None, hamtad: datetime) -> None:
    conn.execute(
        """
        UPDATE sammantrade SET plan_datum = %(datum)s, plan_starttid = %(starttid)s, plan_status = %(status)s,
               plan_anmarkning = %(anmarkning)s, plan_url = %(url)s, plan_version = %(version)s
        WHERE id = %(id)s
        """,
        {**varden, "url": url, "version": version, "id": sammantrade_id},
    )
    conn.execute(
        """
        INSERT INTO planversion (sammantrade_id, version, datum, starttid, status, anmarkning, kalltext, hamtad,
                                 korning_id)
        VALUES (%(id)s, %(version)s, %(datum)s, %(starttid)s, %(status)s, %(anmarkning)s, %(kalltext)s,
                %(hamtad)s, %(korning_id)s)
        """,
        {**varden, "id": sammantrade_id, "version": version, "kalltext": kalltext, "hamtad": hamtad,
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
          hamtad: datetime) -> dict[str, int]:
    """Sparar organets plan. Returnerar antal nya, ändrade och oförändrade planerade sammanträden."""
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
            if all(b[f] == varden[f] for f in FALT):
                antal["oforandrade"] += 1
                continue
            _ny_version(conn, b["id"], b["version"] + 1, varden, r.kalltext, plan.url, korning_id, hamtad)
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
            conn.execute("UPDATE sammantrade SET plan_nyckel = %s, plan_status = %s, plan_version = 1 WHERE id = %s",
                         (r.nyckel, r.status, sammantrade_id))
        else:
            sammantrade_id = conn.execute(
                """
                INSERT INTO sammantrade (organ, nyckel, datum, plan_nyckel, plan_status, plan_version)
                VALUES (%s, %s, %s, %s, %s, 1) RETURNING id
                """,
                (plan.organ, f"plan:{r.nyckel}", r.datum, r.nyckel, r.status),
            ).fetchone()["id"]
        _ny_version(conn, sammantrade_id, 1, varden, r.kalltext, plan.url, korning_id, hamtad)
        antal["nya"] += 1
    # Sammanträden som försvunnit från sidan, för de år sidan visar.
    for nyckel, b in befintliga.items():
        if nyckel in sedda or int(nyckel[:4]) not in plan.ar or b["status"] == "borttaget":
            continue
        varden = {f: b[f] for f in FALT} | {"status": "borttaget"}
        _ny_version(conn, b["id"], b["version"] + 1, varden, "", plan.url, korning_id, hamtad)
        antal["andrade"] += 1
    return antal


# Ett sammanträde som börjar senare än planerat är samma sammanträde. Två sammanträden samma dag,
# t.ex. fullmäktige 2026-10-26 kl. 11.00 och 13.15, är det inte.
MAX_AVVIKELSE_MINUTER = 60


def _minuter(tid: str | None) -> int | None:
    if not tid or not re.fullmatch(r"\d{2}:\d{2}", tid):
        return None
    return int(tid[:2]) * 60 + int(tid[3:])


def narmast(starttid: str | None, kandidater: list[dict]) -> dict | None:
    """Kandidaten (med 'starttid') som ligger närmast i tid. Saknas en av tiderna räknas den som lika."""
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
    när den finns. Ett sammanträde som inte blev av kopplas bara om inget annat passar."""
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
    rad = narmast(starttid, kandidater)
    return rad["id"] if rad else None


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
    }


def lista(conn: psycopg.Connection) -> list[dict]:
    """Planerna per organ och år, med versionerna och jämförelsen mot besluten i protokollen."""
    rader = conn.execute(
        """
        SELECT id, organ, plan_nyckel, plan_datum, plan_starttid, plan_status, plan_anmarkning, plan_version,
               plan_url, dokument_id
        FROM sammantrade WHERE plan_nyckel IS NOT NULL
        ORDER BY organ, plan_nyckel
        """
    ).fetchall()
    versioner: dict[int, list[dict]] = {}
    for v in conn.execute(
        """
        SELECT sammantrade_id, version, datum, starttid, status, anmarkning, kalltext, hamtad
        FROM planversion ORDER BY sammantrade_id, version
        """
    ):
        versioner.setdefault(v["sammantrade_id"], []).append({
            "version": v["version"], "datum": v["datum"].isoformat() if v["datum"] else None,
            "starttid": v["starttid"], "status": v["status"], "anmarkning": v["anmarkning"],
            "kalltext": v["kalltext"], "hamtad": v["hamtad"].isoformat(),
        })
    planer: dict[tuple[str, int], dict] = {}
    for r in rader:
        ar = int(r["plan_nyckel"][:4])
        p = planer.setdefault((r["organ"], ar), {
            "organ": {"id": r["organ"], "namn": ORGAN[r["organ"]].namn}, "ar": ar, "url": r["plan_url"],
            "sammantraden": [],
        })
        p["sammantraden"].append({**_plan_ut(r), "versioner": versioner.get(r["id"], [])})
    beslut = beslut_om_planer(conn)
    ut = []
    for (organ, ar), p in sorted(planer.items(), key=lambda x: (list(ORGAN).index(x[0][0]), x[0][1])):
        b = beslut.get((organ, ar))
        p["beslut"] = b["beslut"] if b else []
        # Utan ett beslut som anger datumen går planen inte att jämföra.
        p["skillnader"] = skillnader(p["sammantraden"], b["datum"]) if b and b["fullstandig"] else None
        ut.append(p)
    return ut


# Besluten om sammanträdesplanerna i protokollen

_DATUM = re.compile(r"(\d{1,2})\s+(" + "|".join(MANADER) + r")(?:\s+(20\d{2}))?", re.IGNORECASE)
_TID = re.compile(r"(\d{1,2})[.:](\d{2})")
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
    return {"beslut": [], "datum": {}, "fullstandig": False}


def beslut_om_planer(conn: psycopg.Connection) -> dict[tuple[str, int], dict]:
    """(organ, år) → besluten om organets sammanträdesplan för året och de datum som gäller enligt dem."""
    rader = conn.execute(
        """
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.sammantrade_id, b.paragraf, b.rubrik, b.beslut,
               s.organ, s.datum
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        WHERE b.rubrik ~* 'sammanträdes(tider|dagar|plan|datum)' AND b.beslut IS NOT NULL AND s.datum IS NOT NULL
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """
    ).fetchall()
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
                    aren.add(a)
                continue
            fran, till = varde if typ == "flyttat" else (varde, None)
            tid = ut.setdefault((r["organ"], fran.year), _tom())["datum"].pop(fran, None)
            aren.add(fran.year)
            if till is not None:
                ut.setdefault((r["organ"], till.year), _tom())["datum"][till] = tid
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
    """Sparar kallelser och webbsändningar. En kallelse som lästs behåller sin plats även när den inte läses igen."""
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0}
    for k in kallelser:
        fore = conn.execute("SELECT tid, plats, pdf_last FROM kallelse WHERE url = %s", (k.url,)).fetchone()
        if fore is None:
            conn.execute(
                """
                INSERT INTO kallelse (organ, datum, tid, typ, titel, url, storlek, plats, pdf_last, forst_sedd,
                                      senast_sedd, korning_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (k.organ, k.datum, k.tid, k.typ, k.titel, k.url, k.storlek, k.plats, k.pdf_last, hamtad, hamtad,
                 korning_id),
            )
            antal["nya"] += 1
            continue
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
