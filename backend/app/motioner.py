"""Motioner och medborgarförslag (#45): när de väcktes, när de besvarades, utfall och ledtid.

En motion följs genom ärendespårningen (ADR-0003). Ett ärende är en motion när någon av dess
behandlingar har behandlingstypen motion, och ett medborgarförslag när någon har typen
medborgarförslag (e-förslag). Typen räknas med publicerade rättelser pålagda.

- **Väckt** är kommunfullmäktiges beslut att överlämna motionen till kommunstyrelsen för beredning.
  Motioner som väcks under samlingspunkten "Tillkommande motioner, interpellationer och frågor"
  kopplas till ärendet med diarienumret i beslutet, och annars med rubriken. En koppling på rubriken
  är osäker och visas som ett förslag (ADR-0002).
- **Besvarad** är kommunfullmäktiges beslut i sak (bifall, avslag, besvarad, delvis eller annat).
  Återremiss och bordläggning besvarar inte motionen. Ett medborgarförslag besvaras av den nämnd
  eller styrelse som fattar beslutet i sak.
- **Ledtid** är dagarna från väckt till besvarad. En motion ska beredas inom ett år (kommunallagen
  5 kap. 35 §). Motioner och medborgarförslag som varit obesvarade längre än ett år, eller besvarades
  efter mer än ett år, markeras.

När ett medborgarförslag väcktes står inte i protokollen. Då räknas tiden från den första behandlingen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

import psycopg

from .arenden import LIKHETSGRANS, NIVA, likhet
from .behandlingstyper import klassa
from .rattelser import Publicerade
from .sources.harnosand import ORGAN

ETT_AR = 365
UTFALL = {"bifall": "Bifall", "avslag": "Avslag", "besvarad": "Besvarad", "delvis": "Delvis bifall",
          "annat": "Annat beslut"}

_VACKT = re.compile(r"\böverlämna[s]?\b.*\bberedning", re.I | re.S)
_ATERREMISS = re.compile(r"återremitter", re.I)
_BORDLAGG = re.compile(r"bordlägg", re.I)
_DELVIS = re.compile(r"\bdelvis\b|att-?sats|\bpunkt(?:er(?:na)?)?\s+(?:\d|ett|två|tre)", re.I)
_AVSLAG = re.compile(r"\bavslå[sr]?\b|\binte\s+genomför|\bgenomförs\s+inte\b|\binte\s+bifall", re.I)
_BIFALL = re.compile(r"\bbifall(?:a|es|s)?\b|\bgenomförs\b|\bgenomföra\b", re.I)
_BESVARAD = re.compile(r"\bbesvarad", re.I)
_SAMLINGSPUNKT = re.compile(r"^tillkommande motioner", re.I)


def utfall(beslut: str | None) -> str | None:
    """Vad ett beslut gör med motionen eller förslaget: 'vackt', 'aterremiss', 'bordlaggning', ett av
    UTFALL, eller None när beslutstexten saknas."""
    if not beslut or not beslut.strip():
        return None
    if _VACKT.search(beslut):
        return "vackt"
    if _ATERREMISS.search(beslut):
        return "aterremiss"
    if _BORDLAGG.search(beslut):
        return "bordlaggning"
    if _DELVIS.search(beslut):
        return "delvis"
    if _AVSLAG.search(beslut):
        return "avslag"
    if _BIFALL.search(beslut):
        return "bifall"
    if _BESVARAD.search(beslut):
        return "besvarad"
    return "annat"


# "Motion – Jämställdhetsstrategi (KS2022-206)", "inkomna motionen: Snabbladdare för elfordon, till …",
# "motion: Motion – Inför skolhund i Härnösands kommun, överlämnas …", "motion – om principbeslut om …".
_TILLKOMMANDE = re.compile(
    r"\bmotion(?:en)?\s*[–:-]\s*(?:motion\s*[–:-]\s*)?(?:om\s+)?(?P<titel>[^•]+?)\s*(?:\((?P<dnr>[^)]*)\))?\s*"
    r"(?=,(?!\s*\()|\bsamt\b|\btill kommunstyrelsen\b|\böverlämnas\b|•|\.?\s*$|\bfår ställas\b|,\s*att\b)",
    re.I,
)
_KS_DNR = re.compile(r"(?:KS\s*)?(\d{4})\s*[-–]?\s*(\d{1,6})")


def tillkommande_motioner(beslut: str) -> list[tuple[str, str | None]]:
    """Motionerna som överlämnas till beredning i samlingspunkten: (titel, diarienummer)."""
    ut = []
    for m in _TILLKOMMANDE.finditer(beslut or ""):
        titel = m["titel"].strip(" ,.:–-")
        if not titel or titel.lower().startswith(("till ", "följande")):
            continue
        d = _KS_DNR.fullmatch(m["dnr"].strip()) if m["dnr"] else None
        ut.append((titel, f"{d[1]}-{int(d[2]):06d}" if d else None))
    return ut


def _organ(organ_id: str) -> dict:
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}


def _las(conn: psycopg.Connection) -> list[dict]:
    rader = conn.execute(
        """
        SELECT DISTINCT ON (b.sammantrade_id, b.paragraf) b.sammantrade_id, b.paragraf, b.rubrik, b.beslut,
               b.diarienummer, b.motionarer, s.organ, s.datum, a.arende_id
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        LEFT JOIN arende_behandling a ON a.sammantrade_id = b.sammantrade_id AND a.paragraf = b.paragraf
        WHERE s.datum IS NOT NULL
        ORDER BY b.sammantrade_id, b.paragraf, b.ordning
        """
    ).fetchall()
    pub = Publicerade(conn, list({r["sammantrade_id"] for r in rader}))
    ut = []
    for r in rader:
        b = pub.behandling(r["sammantrade_id"], {k: r[k] for k in ("paragraf", "rubrik", "beslut", "diarienummer")})
        ut.append(r | {"rubrik": b["rubrik"], "beslut": b["beslut"], "diarienummer": b["diarienummer"],
                       "typ": b["typ"]})
    ut.sort(key=lambda r: (r["datum"], NIVA.get(r["organ"], 0), r["paragraf"]))
    return ut


def _hanvisning(r: dict) -> dict:
    return {"sammantrade": {"id": r["sammantrade_id"], "datum": r["datum"], "organ": _organ(r["organ"])},
            "paragraf": r["paragraf"], "rubrik": r["rubrik"]}


def _motionarer(behandlingar: list[dict]) -> list[dict]:
    """Motionärerna ur ärendets behandlingar. Samma person med olika stavning ("Höglund-Bystedt",
    "Höglund Bystedt") räknas en gång."""
    sett: dict[tuple, dict] = {}
    for b in behandlingar:
        for p in b["motionarer"] or []:
            nyckel = ((p["namn"] or "").replace("-", " ").lower(), p["parti"])
            if p["namn"] is None and any(k[1] == p["parti"] for k in sett):
                continue
            sett.setdefault(nyckel, p)
    namngivna = {k[1] for k in sett if k[0]}
    return [p for k, p in sett.items() if k[0] or k[1] not in namngivna]


def _forlopp(behandlingar: list[dict], idag: date, vackt: dict | None, besvarande_organ: set[str] | None) -> dict:
    besvarad = None
    for b in behandlingar:
        if besvarande_organ is not None and b["organ"] not in besvarande_organ:
            continue
        u = utfall(b["beslut"])
        if u in UTFALL and not (besvarande_organ is None and re.search(r"\bföreslår\b", b["beslut"] or "")):
            besvarad = b | {"utfall": u}
    start = vackt["datum"] if vackt else behandlingar[0]["datum"]
    slut = besvarad["datum"] if besvarad else idag
    return {
        "vackt": vackt,
        "forsta_behandling": _hanvisning(behandlingar[0]),
        "besvarad": _hanvisning(besvarad) | {"beslut": besvarad["beslut"]} if besvarad else None,
        "utfall": besvarad["utfall"] if besvarad else None,
        "ledtid_dagar": (besvarad["datum"] - vackt["datum"]).days if besvarad and vackt else None,
        "over_ett_ar": (slut - start).days > ETT_AR,
        "aterremisser": sum(1 for b in behandlingar if utfall(b["beslut"]) == "aterremiss"),
        "bordlaggningar": sum(1 for b in behandlingar if utfall(b["beslut"]) == "bordlaggning"),
        "behandlingar": [_hanvisning(b) | {"beslut": b["beslut"], "osaker": b.get("osaker", False)}
                         for b in behandlingar],
    }


_TITELPREFIX = re.compile(
    r"^(?:svar på\s+)?(?:remiss\s+(?:angående|gällande)\s+)?(?:motion(?:en)?|e-förslag(?:et)?)\s*(?:\d+\s*)?"
    r"(?:om\s+)?[–:-]?\s*", re.I)
_TITELSUFFIX = re.compile(r"\s*(?:\(anmälan\)|-\s*ny|,\s*återremiss|-\s*svar.*)\s*$", re.I)


def _titel(rubrik: str) -> str:
    """Motionens titel ur behandlingens rubrik: "Svar på remiss angående motion- X (anmälan)" -> "X"."""
    return _TITELSUFFIX.sub("", _TITELPREFIX.sub("", rubrik)).strip()


def _arenden(rader: list[dict], typ: str) -> dict[int, list[dict]]:
    per: dict[int, list[dict]] = defaultdict(list)
    for r in rader:
        if r["arende_id"] is not None:
            per[r["arende_id"]].append(r)
    return {a: bs for a, bs in per.items() if any(b["typ"] == typ for b in bs)}


def _i_urvalet(f: dict, fran: int, till: int, organ: str | None) -> bool:
    datum = [b["sammantrade"]["datum"] for b in f["behandlingar"]] + ([f["vackt"]["datum"]] if f["vackt"] else [])
    if not any(fran <= d.year <= till for d in datum):
        return False
    return organ is None or any(b["sammantrade"]["organ"]["id"] == organ for b in f["behandlingar"])


def motioner_och_forslag(conn: psycopg.Connection, fran: int, till: int, organ: str | None = None,
                         idag: date | None = None) -> dict:
    return berakna(_las(conn), fran, till, organ, idag or date.today())


def berakna(rader: list[dict], fran: int, till: int, organ: str | None, idag: date) -> dict:
    """Motioner och medborgarförslag ur behandlingarna, sorterade i tidsordning."""

    # Motioner väckta under samlingspunkten: (titel, dnr, behandling).
    tillkommande = [(titel, dnr, r) for r in rader if r["organ"] == "KF" and _SAMLINGSPUNKT.search(r["rubrik"])
                    for titel, dnr in tillkommande_motioner(r["beslut"])]

    # Remissvar och beredning i nämnderna har ofta nämndens eget diarienummer och hamnar då i ett eget
    # ärende. Ett sådant ärende utan behandling i kommunfullmäktige kopplas till den motion i
    # fullmäktige som har mest lik rubrik och väcktes före. Kopplingen är osäker och markeras.
    arenden = _arenden(rader, "motion")
    i_kf = {a: bs for a, bs in arenden.items() if any(b["organ"] == "KF" for b in bs)}
    for a, bs in [(a, bs) for a, bs in arenden.items() if a not in i_kf]:
        titel = _titel(bs[-1]["rubrik"])
        kandidater = [(likhet(titel, _titel(k[0]["rubrik"])), k[0]["datum"], ka) for ka, k in i_kf.items()
                      if k[0]["datum"] <= bs[0]["datum"]]
        kandidater = [k for k in kandidater if k[0] > LIKHETSGRANS]
        if kandidater:
            mal = max(kandidater)[2]
            i_kf[mal] = sorted(i_kf[mal] + [b | {"osaker": True} for b in bs],
                               key=lambda r: (r["datum"], NIVA.get(r["organ"], 0), r["paragraf"]))
            del arenden[a]
    arenden.update(i_kf)

    motioner = []
    for arende_id, bs in arenden.items():
        vackt = None
        if v := next((b for b in bs if b["organ"] == "KF" and utfall(b["beslut"]) == "vackt"), None):
            vackt = {"datum": v["datum"], "sammantrade_id": v["sammantrade_id"], "paragraf": v["paragraf"],
                     "organ": _organ("KF"), "grund": "beslut", "osaker": False}
        else:
            dnr = {d for b in bs for d in b["diarienummer"]}
            rubrik = bs[0]["rubrik"]
            fore = [t for t in tillkommande if t[2]["datum"] <= bs[0]["datum"]]
            traff = next(((t, False) for t in reversed(fore) if t[1] and t[1] in dnr), None) or next(
                ((t, True) for t in reversed(fore) if likhet(t[0], _titel(rubrik)) > LIKHETSGRANS), None)
            if traff:
                (titel, _, r), osaker = traff
                vackt = {"datum": r["datum"], "sammantrade_id": r["sammantrade_id"], "paragraf": r["paragraf"],
                         "organ": _organ("KF"), "grund": "samlingspunkt", "osaker": osaker, "titel": titel}
        f = _forlopp(bs, idag, vackt, {"KF"})
        if not _i_urvalet(f, fran, till, organ):
            continue
        motioner.append({"arende_id": arende_id, "rubrik": next(b["rubrik"] for b in bs if b["organ"] == "KF" or b is bs[-1]), "motionarer": _motionarer(bs)} | f)

    forslag = []
    for arende_id, bs in _arenden(rader, "medborgarforslag").items():
        f = _forlopp(bs, idag, None, None)
        if not _i_urvalet(f, fran, till, organ):
            continue
        forslag.append({"arende_id": arende_id, "rubrik": bs[-1]["rubrik"]} | f)

    def tomt() -> dict:
        return {"vackta": 0, "besvarade": 0, "utfall": {u: 0 for u in UTFALL}}

    per_ar = {ar: tomt() for ar in range(fran, till + 1)}
    per_parti: dict[str, dict] = defaultdict(tomt)
    for m in motioner:
        partier = {p["parti"] or "okant" for p in m["motionarer"]} or {"okant"}
        if m["vackt"] and fran <= m["vackt"]["datum"].year <= till:
            per_ar[m["vackt"]["datum"].year]["vackta"] += 1
            for p in partier:
                per_parti[p]["vackta"] += 1
        if m["besvarad"] and fran <= m["besvarad"]["sammantrade"]["datum"].year <= till:
            r = per_ar[m["besvarad"]["sammantrade"]["datum"].year]
            r["besvarade"] += 1
            r["utfall"][m["utfall"]] += 1
            for p in partier:
                per_parti[p]["besvarade"] += 1
                per_parti[p]["utfall"][m["utfall"]] += 1

    nyckel = lambda m: m["vackt"]["datum"] if m["vackt"] else m["forsta_behandling"]["sammantrade"]["datum"]  # noqa: E731
    motioner.sort(key=nyckel, reverse=True)
    forslag.sort(key=lambda f: f["forsta_behandling"]["sammantrade"]["datum"], reverse=True)
    return {
        "fran": fran,
        "till": till,
        "organ": _organ(organ) if organ else None,
        "idag": idag,
        "utfall": [{"id": u, "namn": n} for u, n in UTFALL.items()],
        "motioner": {
            "per_ar": [{"ar": ar} | r for ar, r in per_ar.items()],
            "per_parti": [{"parti": p} | r for p, r in sorted(per_parti.items(), key=lambda x: (x[0] == "okant", x[0]))],
            "lista": motioner,
            "utan_vackt": sum(1 for m in motioner if not m["vackt"]),
        },
        "medborgarforslag": {"lista": forslag},
    }
