"""Kommande: ärenden som inte är avslutade, i en enkel lista.

Ett ärende kommer från ärendespårningen (ADR-0003). Det räknas som pågående när protokollen visar
att något återstår:

- **Obesvarad motion** eller **obesvarat medborgarförslag**: väckt men utan beslut i sak (motioner.py).
- **Återremitterat** eller **bordlagt**: den senaste behandlingen sköt upp ärendet.
- **Väntar på beslut**: den senaste behandlingen är ett förslag till ett annat organ, och det organet
  har inte behandlat ärendet än.
- **Pågående uppdrag**: den senaste behandlingen ger någon i uppdrag att utreda, återrapportera
  eller redovisa något. Står det en tidpunkt i beslutet visas den.

Uppskjutna ärenden, förslag och uppdrag tas bara med när den senaste behandlingen är från de
senaste `manader` månaderna. Äldre ärenden har oftast avgjorts i en behandling som plattformen inte
kunnat koppla. Obesvarade motioner och medborgarförslag tas alltid med, eftersom de ska besvaras
inom ett år.

Allt är automatiskt tolkat ur protokollen och kan vara fel. Samlingspunkter är inga ärenden.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

import psycopg

from . import motioner
from .arenden import NIVA, SAMLING, las_arende
from .aterkommande import handelse
from .protokoll import protokoll_for
from .sources.harnosand import organ_ref

STATUS = {
    "motion": "Obesvarad motion",
    "medborgarforslag": "Obesvarat medborgarförslag",
    "aterremiss": "Återremitterat",
    "bordlaggning": "Bordlagt",
    "forslag": "Väntar på beslut",
    "uppdrag": "Pågående uppdrag",
}
MANADER = 12

_UTAN_ARENDE = {"formalia", "information", "interpellation"}
_FORESLAR = re.compile(r"föreslår\s+(kommunfullmäktige|kommunstyrelsen|\S*nämnden)\b"
                       r"|förslag till (kommunfullmäktige|kommunstyrelsen)", re.I)
_TILL_ORGAN = {"kommunfullmäktige": "KF", "kommunstyrelsen": "KS", "samhällsnämnden": "SAM",
               "socialnämnden": "SOC", "skolnämnden": "SKOL"}
_UPPDRAG = re.compile(r"\bi uppdrag\b|\buppdra[rs]?\b", re.I)
_MANAD = r"(?:januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)"
# "senast 2027-03-31", "senast den 30 juni 2027", "återrapportera ... i mars 2027", "under hösten 2027".
_FRIST = re.compile(
    rf"(?:senast(?:\s+den)?|återrapport\w*|redovisa\w*|rapportera\w*)[^.]{{0,80}}?"
    rf"(?P<tid>\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}\s+{_MANAD}\s+\d{{4}}|{_MANAD}\s+\d{{4}}"
    rf"|(?:våren|hösten|sommaren|vintern|årsskiftet)\s+\d{{4}}|kvartal\s+\d\s+\d{{4}}|\d{{4}})",
    re.I,
)


def frist(beslut: str | None) -> str | None:
    """Tidpunkten som beslutet anger för återrapportering eller redovisning, som det står."""
    m = _FRIST.search(" ".join((beslut or "").split()))
    return m["tid"] if m else None


def mottagare(beslut: str | None) -> str | None:
    """Organet som ett förslag riktar sig till: 'KF', 'KS' eller en nämnd."""
    m = _FORESLAR.search(beslut or "")
    if not m:
        return None
    return _TILL_ORGAN.get((m[1] or m[2]).lower())


def status_for(senaste: dict) -> str | None:
    """Vad som återstår efter ärendets senaste behandling, eller None när ärendet är avgjort."""
    beslut = senaste["beslut"]
    if h := handelse(beslut):
        return h
    till = mottagare(beslut)
    if till and NIVA.get(till, 0) > NIVA.get(senaste["organ"], 0):
        return "forslag"
    if _UPPDRAG.search(beslut or "") and senaste["typ"] == "beslut":
        return "uppdrag"
    return None


def _ref(b: dict) -> dict:
    return {"sammantrade": {"id": b["sammantrade_id"], "datum": b["datum"], "organ": organ_ref(b["organ"])},
            "paragraf": b["paragraf"], "rubrik": b["rubrik"], "beslut": b["beslut"]}


def kommande(conn: psycopg.Connection, manader: int = MANADER, idag: date | None = None) -> dict:
    idag = idag or date.today()
    rader = motioner.daterade(conn)
    return berakna(rader, manader, idag)


def berakna(rader: list[dict], manader: int, idag: date) -> dict:
    grans = idag - timedelta(days=round(manader * 30.44))
    per: dict[int, list[dict]] = defaultdict(list)
    for r in rader:
        if r["arende_id"] is not None:
            per[r["arende_id"]].append(r)

    poster: dict[int, dict] = {}

    # Obesvarade motioner och medborgarförslag, oavsett ålder.
    if rader:
        forsta, sista = rader[0]["datum"].year, rader[-1]["datum"].year
        m = motioner.berakna(rader, forsta, sista, None, idag)
        for typ, lista in (("motion", m["motioner"]["lista"]), ("medborgarforslag", m["medborgarforslag"]["lista"])):
            for f in lista:
                if f["besvarad"] or f["arende_id"] in poster:
                    continue
                bs = per[f["arende_id"]]
                senaste = bs[-1]
                start = f["vackt"]["datum"] if f["vackt"] else bs[0]["datum"]
                poster[f["arende_id"]] = {
                    "arende_id": f["arende_id"],
                    "rubrik": f["rubrik"],
                    "status": typ,
                    "vantar_pa": organ_ref("KF") if typ == "motion" else None,
                    "sedan": start,
                    "vackt": f["vackt"] is not None,
                    "dagar": (idag - start).days,
                    "over_ett_ar": f["over_ett_ar"],
                    "frist": None,
                    "motionarer": f.get("motionarer", []),
                }

    for arende_id, bs in per.items():
        if arende_id in poster:
            continue
        bs = [b for b in bs if not SAMLING.search(b["rubrik"]) and b["typ"] not in _UTAN_ARENDE]
        if not bs:
            continue
        senaste = bs[-1]
        if senaste["datum"] < grans:
            continue
        status = status_for(senaste)
        if status is None:
            continue
        till = mottagare(senaste["beslut"]) if status == "forslag" else None
        poster[arende_id] = {
            "arende_id": arende_id,
            "rubrik": senaste["rubrik"],
            "status": status,
            "vantar_pa": organ_ref(till) if till else None,
            "sedan": senaste["datum"],
            "vackt": False,
            "dagar": (idag - senaste["datum"]).days,
            "over_ett_ar": False,
            "frist": frist(senaste["beslut"]) if status == "uppdrag" else None,
            "motionarer": [],
        }

    ut = []
    for arende_id, p in poster.items():
        bs = per[arende_id]
        senaste = bs[-1]
        ut.append(p | {
            "diarienummer": list(dict.fromkeys(d for b in bs for d in b["diarienummer"])),
            "antal_behandlingar": len(bs),
            "senaste": _ref(senaste),
        })
    ut.sort(key=lambda p: p["senaste"]["sammantrade"]["datum"], reverse=True)
    antal = {s: 0 for s in STATUS}
    for p in ut:
        antal[p["status"]] += 1
    return {
        "idag": idag,
        "manader": manader,
        "statusar": [{"id": s, "namn": n, "antal": antal[s]} for s, n in STATUS.items()],
        "arenden": ut,
    }


def underlag(conn: psycopg.Connection, arende_id: int) -> dict | None:
    """Ärendet med handlingarna bakom varje behandling: protokollet och hänvisningarna i
    beslutsunderlaget, med länk till den behandling som hänvisningen pekar på när den finns."""
    arende = las_arende(conn, arende_id)
    if arende is None:
        return None
    ids = list({b["sammantrade"]["id"] for b in arende["behandlingar"]})
    protokoll = protokoll_for(conn, ids)
    hanvisningar: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for h in conn.execute(
        """
        SELECT b.sammantrade_id, b.paragraf, h.text, h.organ, h.datum, h.paragraf AS h_paragraf,
               (SELECT s2.id FROM sammantrade s2 JOIN behandling b2 ON b2.sammantrade_id = s2.id
                WHERE s2.datum = h.datum AND b2.paragraf = h.paragraf AND (h.organ IS NULL OR s2.organ = h.organ)
                ORDER BY s2.id LIMIT 1) AS mal_sammantrade_id
        FROM hanvisning h JOIN behandling b ON b.id = h.behandling_id
        WHERE b.sammantrade_id = ANY(%s)
        ORDER BY b.sammantrade_id, b.paragraf, h.ordning
        """,
        (ids,),
    ):
        mal = ({"sammantrade_id": h["mal_sammantrade_id"], "paragraf": h["h_paragraf"]}
               if h["mal_sammantrade_id"] else None)
        hanvisningar[(h["sammantrade_id"], h["paragraf"])].append({"text": h["text"], "behandling": mal})

    behandlingar = []
    for b in arende["behandlingar"]:
        nyckel = (b["sammantrade"]["id"], b["paragraf"])
        behandlingar.append(b | {"protokoll": protokoll.get(b["sammantrade"]["id"]),
                                 "hanvisningar": hanvisningar.get(nyckel, [])})
    return arende | {"behandlingar": behandlingar}
