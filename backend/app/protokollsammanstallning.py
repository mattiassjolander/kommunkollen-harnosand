"""Protokollsammanställning (#195): vad som hände på ett sammanträde, räknat ur protokollets tolkning.

Sammanställningen räknas här och ingen annanstans, med publicerade rättelser pålagda (behandlingarna läses med
`markningar.las`, som bygger på `behandlingar.las`). Reglerna gissar aldrig (ADR-0002):

- **Paragrafer**: alla behandlingar i protokollet.
- **Ärenden**: behandlingar som hör till ett ärende, alltså utan formalia, informationsärenden och samlingspunkter
  som delegationsbeslut och meddelanden (`arenden.SAMLING`).
- **Beslut**: ärenden där organet beslutade själv. **Förslag vidare**: ärenden där organet föreslår ett annat organ
  något, med den gemensamma regeln `arenden.forslag_till` (#182). En paragraf utan beslutstext räknas inte.
- **Oenighet**: paragrafer med märkningen Oenighet (#162), antalet voteringar och antalet reservationer, med de
  reserverande partierna som förkortningar i alfabetisk ordning. Utan oenighet är det "Enigt i alla ärenden".
- **Beslutsgång**: paragrafer som återremitterades, bordlades eller där någon anmälde jäv (märkningarna), och nya
  motioner, medborgarförslag och interpellationer. En motion eller ett medborgarförslag är nytt när beslutet
  överlämnar det för beredning (`motioner.utfall`), och motionerna under samlingspunkten "Tillkommande motioner"
  räknas en och en. En interpellation är ny när rubriken börjar med "Interpellation".
- **Sammanträdet**: längden i minuter (bara när både start- och sluttid finns och sluttiden är senare), antal
  beslutande och tjänstgörande ersättare ur närvarolistan, och antal informationsärenden.
- **Skickas vidare**: förslagen vidare, med organet de går till.
- **Kallelsen mot protokollet**: punkterna i kallelsen som inte behandlades, ur kallelsens avvikelser (#121).

Ett protokoll som inte kunde tolkas, och ett planerat sammanträde utan protokoll, har ingen sammanställning (None).

`filter` anger paragraferna bakom varje tal, så att sammanträdessidan kan visa bara dem.
"""

from __future__ import annotations

import re
from collections import defaultdict

import psycopg

from . import markningar
from .arenden import SAMLING, forslag_till
from .avvikelser import kategori, objekt
from .motioner import tillkommande_motioner, utfall

_UTAN_ARENDE = {"formalia", "information"}
_INTERPELLATION = re.compile(r"^interpellation", re.I)
_TILLKOMMANDE = re.compile(r"^tillkommande motioner", re.I)
_TID = re.compile(r"^(\d{1,2}):(\d{2})$")
_PUNKT = re.compile(r'punkten "(?P<rubrik>[^"]+)"')
# Märkningarna som visas i listan över sammanträden, i den ordningen (#174).
CHIPS = ("votering", "reservation", "oenighet")


def ar_arende(b: dict) -> bool:
    """Behandlingen hör till ett ärende: inte formalia, informationsärende eller samlingspunkt."""
    return b.get("typ") not in _UTAN_ARENDE and not SAMLING.search(b.get("rubrik") or "")


def langd(starttid: str | None, sluttid: str | None) -> int | None:
    """Sammanträdets längd i minuter, bara när både start- och sluttid finns och sluttiden är senare."""
    a, b = _TID.match(starttid or ""), _TID.match(sluttid or "")
    if not a or not b:
        return None
    minuter = (int(b[1]) * 60 + int(b[2])) - (int(a[1]) * 60 + int(a[2]))
    return minuter if minuter > 0 else None


def _partiordning(parti: str) -> tuple:
    return (parti == "-", parti)


def _organnamn(organ: str) -> str:
    return organ[:1].upper() + organ[1:]


def _nya(b: dict) -> tuple[int, int, int]:
    """(nya motioner, nya medborgarförslag, nya interpellationer) vid behandlingen."""
    if _TILLKOMMANDE.search(b.get("rubrik") or ""):
        return len(tillkommande_motioner(b.get("beslut") or "")), 0, 0
    vackt = utfall(b.get("beslut")) == "vackt"
    return (int(b.get("typ") == "motion" and vackt), int(b.get("typ") == "medborgarforslag" and vackt),
            int(b.get("typ") == "interpellation" and bool(_INTERPELLATION.search(b.get("rubrik") or ""))))


def sammanstall(behandlingar: list[dict], *, starttid: str | None = None, sluttid: str | None = None,
                narvaro: list[dict] = (), kallelse_avvikelser: list = ()) -> dict:
    """Sammanställningen för ett tolkat protokoll.

    behandlingar har `paragraf`, `rubrik`, `beslut`, `typ` och `markningar` med publicerade rättelser pålagda, och
    `antal_voteringar` och `antal_reservationer`. narvaro har `kategori`, `roll`, `tjanstgor_for` och `tom_plats`.
    """
    filter_: dict[str, list[int]] = defaultdict(list)
    skickas_vidare = []
    voteringar = reservationer = motioner = medborgarforslag = interpellationer = 0
    partier: set[str] = set()
    for b in behandlingar:
        p = b["paragraf"]
        ms = {m["id"]: m for m in b.get("markningar") or []}
        if ar_arende(b):
            filter_["arenden"].append(p)
            if till := forslag_till(b.get("beslut")):
                filter_["forslag_vidare"].append(p)
                skickas_vidare.append({"paragraf": p, "rubrik": b.get("rubrik"), "till": _organnamn(till)})
            elif (b.get("beslut") or "").strip():
                filter_["beslut"].append(p)
        if b.get("typ") == "information":
            filter_["information"].append(p)
        for id_ in ("oenighet", "votering", "reservation", "aterremitterad", "bordlagd", "jav"):
            if id_ in ms:
                filter_[id_].append(p)
        if "reservation" in ms:
            partier.update(ms["reservation"].get("partier") or [])
        voteringar += b.get("antal_voteringar") or 0
        reservationer += b.get("antal_reservationer") or 0
        nm, nf, ni = _nya(b)
        motioner, medborgarforslag, interpellationer = motioner + nm, medborgarforslag + nf, interpellationer + ni
        for nyckel, n in (("motioner", nm), ("medborgarforslag", nf), ("interpellationer", ni)):
            if n:
                filter_[nyckel].append(p)

    beslutande = [n for n in narvaro if n.get("kategori") == "beslutande" and not n.get("tom_plats")]
    ej_behandlade = []
    for a in kallelse_avvikelser:
        a = objekt(a)
        if kategori(a) == "kallelsen" and "behandlas inte i protokollet" in a["text"]:
            m = _PUNKT.search(a["text"])
            ej_behandlade.append({"rubrik": m["rubrik"] if m else None, "text": a["text"], "lank": a.get("lank")})
    antal = {k: len(v) for k, v in filter_.items()}
    return {
        "paragrafer": len(behandlingar),
        "arenden": antal.get("arenden", 0),
        "beslut": antal.get("beslut", 0),
        "forslag_vidare": antal.get("forslag_vidare", 0),
        "oenighet": {
            "paragrafer": antal.get("oenighet", 0),
            "voteringar": voteringar,
            "reservationer": reservationer,
            "partier": sorted(partier, key=_partiordning),
            "enigt": not antal.get("oenighet") and not voteringar and not reservationer,
        },
        "beslutsgang": {
            "aterremitterade": antal.get("aterremitterad", 0),
            "bordlagda": antal.get("bordlagd", 0),
            "jav": antal.get("jav", 0),
            "motioner": motioner,
            "medborgarforslag": medborgarforslag,
            "interpellationer": interpellationer,
        },
        "sammantradet": {
            "langd_minuter": langd(starttid, sluttid),
            "beslutande": len(beslutande),
            "tjanstgorande_ersattare": sum(
                1 for n in beslutande if n.get("tjanstgor_for") or (n.get("roll") or "").lower().startswith("ersättare")),
            "informationsarenden": antal.get("information", 0),
        },
        "skickas_vidare": skickas_vidare,
        "kallelsen": {"ej_behandlade": ej_behandlade},
        "filter": dict(filter_),
    }


def kompakt(s: dict | None, behandlingar: list[dict]) -> dict | None:
    """Raden i listan över sammanträden: talen, chipsen och märkningarna för märkningsfiltret."""
    if s is None:
        return None
    per: dict[str, int] = defaultdict(int)
    for b in behandlingar:
        for m in {m["id"] for m in b.get("markningar") or []}:
            per[m] += 1
    o = s["oenighet"]
    chips = {"votering": o["voteringar"], "reservation": o["reservationer"], "oenighet": o["paragrafer"]}
    return {
        "paragrafer": s["paragrafer"], "arenden": s["arenden"], "beslut": s["beslut"],
        "forslag_vidare": s["forslag_vidare"],
        "chips": [{"id": c, "antal": chips[c]} for c in CHIPS if chips[c]],
        "enigt": o["enigt"],
        # Antal paragrafer per märkning, för märkningsfiltret i listan.
        "markningar": dict(per),
    }


def for_sammantraden(conn: psycopg.Connection, sammantraden: list[dict], *, kompakta: bool = False
                     ) -> dict[int, dict | None]:
    """Sammanställningen per sammanträdes-id, med ett fast antal frågor oavsett hur många sammanträden.

    sammantraden har `id`, `tolkning`, `dokument_id`, `starttid`, `sluttid` och `kallelse_avvikelser`.
    Med kompakta=True blir det raden i listan (`kompakt`).
    """
    tolkade = [s for s in sammantraden if s.get("dokument_id") is not None and s.get("tolkning") == "tolkad"]
    ut: dict[int, dict | None] = {s["id"]: None for s in sammantraden}
    if not tolkade:
        return ut
    ids = [s["id"] for s in tolkade]
    rader = markningar.las(conn, sammantraden=ids)
    beh_ids = [r["id"] for r in rader]
    voteringar = {r["behandling_id"]: r["n"] for r in conn.execute(
        "SELECT behandling_id, count(*) AS n FROM votering WHERE behandling_id = ANY(%s) GROUP BY behandling_id",
        (beh_ids,))}
    reservationer = {r["behandling_id"]: r["n"] for r in conn.execute(
        "SELECT behandling_id, count(*) AS n FROM reservation WHERE behandling_id = ANY(%s) GROUP BY behandling_id",
        (beh_ids,))}
    narvaro: dict[int, list[dict]] = defaultdict(list)
    for n in conn.execute(
            "SELECT sammantrade_id, kategori, roll, tjanstgor_for, tom_plats FROM narvaro WHERE sammantrade_id = ANY(%s)",
            (ids,)):
        narvaro[n["sammantrade_id"]].append(n)
    per: dict[int, list[dict]] = defaultdict(list)
    for r in sorted(rader, key=lambda r: r["paragraf"]):
        per[r["sammantrade_id"]].append(
            r | {"antal_voteringar": voteringar.get(r["id"], 0), "antal_reservationer": reservationer.get(r["id"], 0)})
    for s in tolkade:
        bs = per.get(s["id"], [])
        full = sammanstall(bs, starttid=s.get("starttid"), sluttid=s.get("sluttid"), narvaro=narvaro.get(s["id"], []),
                           kallelse_avvikelser=s.get("kallelse_avvikelser") or [])
        ut[s["id"]] = kompakt(full, bs) if kompakta else full
    return ut
