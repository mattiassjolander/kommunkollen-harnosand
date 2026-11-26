"""Märkningar (#162): regelbaserade uppgifter om en behandling eller ett ärende, utlästa ur protokollet.

En märkning sitter på behandlingen, eftersom det är där voteringar och reservationer står. Reglerna gissar
aldrig (ADR-0002):

- **Votering**: behandlingen har minst en votering. Texten har resultatet ja–nej, "Votering 26–24", med
  siffrorna som protokollets text anger dem, annars räknade ur voteringslistan med publicerade rättelser av
  rösterna. Saknas båda står det bara "Votering".
- **Reservation**: minst en reservation. Texten har partierna (alfabetiskt efter förkortning), annars antalet
  ledamöter som reserverar sig med namn.
- **Oenighet**: votering eller reservation, protokollets propositionsordning anger två eller fler förslag till
  beslut, eller minst två yrkanden går isär: ett yrkar avslag, återremiss, bordläggning eller ändring och ett
  annat bifall.
- **Återremitterad** och **Bordlagd**: beslutet skjuter upp ärendet (`aterkommande.handelse`).
- **Jäv**: någon anmälde jäv vid paragrafen (närvarolistan).
- **Motion**, **Medborgarförslag** och **Interpellation eller fråga**: behandlingstypen.

Det finns ingen märkning "Enig": att protokollet inte nämner yrkanden eller reservationer bevisar inte enighet.

Ett ärende har summan av behandlingarnas märkningar, plus **Lång beredning** (mer än 12 månader från första
behandlingen till det slutliga beslutet) och **Återkommande** (behandlat vid minst två sammanträden).

Märkningarna räknas när behandlingarna läses, med publicerade rättelser pålagda (beslut och typ kan vara
rättade). `las` ger behandlingarna med märkningar och kan filtrera på en märkning, t.ex. alla behandlingar
med votering ett visst år. Sökindexet sparar märkningarna per sökenhet (`sokenhet.markningar`).

En märkning är en dict {id, text}. Reservationen har också `partier`, och ett ärendes märkning `antal`
(antalet behandlingar med märkningen).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Iterable

import psycopg

from . import behandlingar
from .aterkommande import handelse
from .behandlingstyper import TYPER
from .rattelser import Publicerade

# id → visningsnamn, i den ordning de visas.
BEHANDLING: dict[str, str] = {
    "votering": "Votering",
    "reservation": "Reservation",
    "oenighet": "Oenighet",
    "aterremitterad": "Återremitterad",
    "bordlagd": "Bordlagd",
    "jav": "Jäv",
    "motion": TYPER["motion"],
    "medborgarforslag": TYPER["medborgarforslag"],
    "interpellation": TYPER["interpellation"],
}
ARENDE: dict[str, str] = {
    "lang_beredning": "Lång beredning",
    "aterkommande": "Återkommande",
}
MARKNINGAR: dict[str, str] = BEHANDLING | ARENDE
# Märkningar som beskriver vad behandlingen är. De räknas inte i ett ärende.
_TYPMARKNINGAR = ("motion", "medborgarforslag", "interpellation")
LANG_BEREDNING_MANADER = 12

_HANDELSE = {"aterremiss": "aterremitterad", "bordlaggning": "bordlagd"}

# "Ordföranden finner att det föreligger två förslag till beslut", "… tre förslag till beslut samt …".
_FLERA_FORSLAG = re.compile(
    r"föreligger\s+(?:(?:två|tre|fyra|fem|sex|sju|åtta|nio|tio|flera)|(?P<antal>\d+))\s+(?:olika\s+)?förslag", re.I)
# Ett yrkande mot förslaget: "yrkar avslag", "yrkar på återremiss", "yrkar på att avslå", "yrkar på ändring".
_MOTYRKANDE = re.compile(
    r"\byrkar\b[^.]{0,40}?\b(?:avslag|avslå|återremiss|återremittera|bordläggning|bordlägga|ändring)", re.I)
_BIFALL = re.compile(r"\byrkar\b[^.]{0,20}?\bbifall", re.I)


def flera_forslag(propositionsordning: str | None) -> bool:
    """Propositionsordningen anger två eller fler förslag till beslut."""
    for m in _FLERA_FORSLAG.finditer(" ".join((propositionsordning or "").split())):
        if m["antal"] is None or int(m["antal"]) >= 2:
            return True
    return False


def yrkanden_gar_isar(yrkanden: list[str]) -> bool:
    """Minst två yrkanden, där ett yrkar avslag, återremiss, bordläggning eller ändring och ett annat bifall."""
    mot = {i for i, y in enumerate(yrkanden) if _MOTYRKANDE.search(y)}
    bifall = {i for i, y in enumerate(yrkanden) if _BIFALL.search(y)}
    return any(i != j for i in mot for j in bifall)


def _partiordning(parti: str) -> tuple:
    return (parti == "-", parti)


def _votering_text(resultat: list[tuple[int, int] | None]) -> str:
    kanda = [r for r in resultat if r is not None]
    if not kanda:
        return "Votering"
    return "Votering " + ", ".join(f"{ja}–{nej}" for ja, nej in kanda)


def _reservation(reservationer: list[dict]) -> dict:
    partier: set[str] = set()
    utan_parti = 0
    for r in reservationer:
        partier.update(p for p in r["partier"] if p)
        for p in r["personer"]:
            if p.get("parti"):
                partier.add(p["parti"])
            else:
                utan_parti += 1
    ordnade = sorted(partier, key=_partiordning)
    if ordnade:
        text = "Reservation " + ", ".join(ordnade)
    elif utan_parti:
        text = f"Reservation, {utan_parti} {'ledamot' if utan_parti == 1 else 'ledamöter'}"
    else:
        text = "Reservation"
    return {"id": "reservation", "text": text, "partier": ordnade}


def berakna(conn: psycopg.Connection, rader: list[dict]) -> dict[int, list[dict]]:
    """Märkningarna per behandlings-id.

    rader är behandlingar med `id`, `sammantrade_id`, `paragraf`, `beslut` och `typ`, med publicerade rättelser
    pålagda (som `behandlingar.las` ger dem).
    """
    ids = [r["id"] for r in rader]
    if not ids:
        return {}
    sammantraden = list({r["sammantrade_id"] for r in rader})
    proposition = {r["id"]: r["propositionsordning"] for r in conn.execute(
        "SELECT id, propositionsordning FROM behandling WHERE id = ANY(%s)", (ids,))}
    yrkanden: dict[int, list[str]] = defaultdict(list)
    for y in conn.execute("SELECT behandling_id, text FROM yrkande WHERE behandling_id = ANY(%s) ORDER BY ordning",
                          (ids,)):
        yrkanden[y["behandling_id"]].append(y["text"])
    reservationer: dict[int, list[dict]] = defaultdict(list)
    for r in conn.execute(
            "SELECT behandling_id, personer, partier FROM reservation WHERE behandling_id = ANY(%s) ORDER BY ordning",
            (ids,)):
        reservationer[r["behandling_id"]].append(r)
    voteringar = voteringsresultat(conn, rader)
    jav: set[tuple[int, int]] = {
        (n["sammantrade_id"], p) for n in conn.execute(
            "SELECT sammantrade_id, jav FROM narvaro WHERE sammantrade_id = ANY(%s) AND cardinality(jav) > 0",
            (sammantraden,))
        for p in n["jav"]}

    ut: dict[int, list[dict]] = {}
    for b in rader:
        m: list[dict] = []
        vs = voteringar.get(b["id"], [])
        if vs:
            m.append({"id": "votering", "text": _votering_text(
                [(v["ja"], v["nej"]) if v["ja"] is not None else None for v in vs])})
        rs = reservationer.get(b["id"], [])
        if rs:
            m.append(_reservation(rs))
        if vs or rs or flera_forslag(proposition.get(b["id"])) or yrkanden_gar_isar(yrkanden.get(b["id"], [])):
            m.append({"id": "oenighet", "text": BEHANDLING["oenighet"]})
        if (h := _HANDELSE.get(handelse(b["beslut"]))) is not None:
            m.append({"id": h, "text": BEHANDLING[h]})
        if (b["sammantrade_id"], b["paragraf"]) in jav:
            m.append({"id": "jav", "text": BEHANDLING["jav"]})
        if b.get("typ") in _TYPMARKNINGAR:
            m.append({"id": b["typ"], "text": BEHANDLING[b["typ"]]})
        ut[b["id"]] = m
    return ut


def voteringsresultat(conn: psycopg.Connection, rader: list[dict]) -> dict[int, list[dict]]:
    """Voteringarna per behandlings-id, i ordning, med antal ja och nej.

    Siffrorna tas ur protokollets text. Anger texten dem inte räknas de ur voteringslistan, med publicerade
    rättelser av rösterna. Saknas båda är ja och nej None. Varje votering är en dict med `ordning` (från 1),
    `ja`, `nej`, `ja_forslag` och `nej_forslag`.
    """
    ids = [r["id"] for r in rader]
    if not ids:
        return {}
    voteringar: dict[int, list[dict]] = defaultdict(list)
    for v in conn.execute(
            "SELECT id, behandling_id, ordning, ja, nej, ja_forslag, nej_forslag FROM votering "
            "WHERE behandling_id = ANY(%s) ORDER BY ordning", (ids,)):
        voteringar[v["behandling_id"]].append(dict(v))
    utan_siffror = [v["id"] for vs in voteringar.values() for v in vs if v["ja"] is None or v["nej"] is None]
    roster: dict[int, list[dict]] = defaultdict(list)
    if utan_siffror:
        for r in conn.execute("SELECT votering_id, namn, rost FROM rost WHERE votering_id = ANY(%s) ORDER BY ordning",
                              (utan_siffror,)):
            roster[r["votering_id"]].append(dict(r))
    pub = Publicerade(conn, list({r["sammantrade_id"] for r in rader})) if utan_siffror else None
    ut: dict[int, list[dict]] = {}
    for b in rader:
        resultat = []
        for v in voteringar.get(b["id"], []):
            ja, nej = v["ja"], v["nej"]
            if (ja is None or nej is None) and roster.get(v["id"]):
                lista = [pub.rost(b["sammantrade_id"], b["paragraf"], v["ordning"] + 1, dict(r))["rost"]
                         for r in roster[v["id"]]]
                ja, nej = lista.count("ja"), lista.count("nej")
            elif ja is None or nej is None:
                ja = nej = None
            resultat.append({"ordning": v["ordning"] + 1, "ja": ja, "nej": nej,
                             "ja_forslag": v["ja_forslag"], "nej_forslag": v["nej_forslag"]})
        if resultat:
            ut[b["id"]] = resultat
    return ut


def satt(conn: psycopg.Connection, rader: list[dict]) -> list[dict]:
    """Lägger märkningarna på raderna (nyckeln `markningar`) och ger tillbaka dem."""
    per = berakna(conn, rader)
    for r in rader:
        r["markningar"] = per.get(r["id"], [])
    return rader


def las(conn: psycopg.Connection, *, markning: str | None = None, **villkor) -> list[dict]:
    """Behandlingarna (`behandlingar.las` med samma villkor) med märkningar, bara de med `markning` om den anges.

    Till exempel alla behandlingar med votering 2026: `las(conn, fran=2026, till=2026, markning="votering")`.
    """
    rader = satt(conn, behandlingar.las(conn, **villkor))
    if markning is None:
        return rader
    return [r for r in rader if any(m["id"] == markning for m in r["markningar"])]


def for_paragrafer(conn: psycopg.Connection, nycklar: Iterable[tuple[int, int]]) -> dict[tuple[int, int], list[dict]]:
    """Märkningarna per (sammanträde, paragraf), för listor som inte läser behandlingarna själva."""
    nycklar = set(nycklar)
    if not nycklar:
        return {}
    rader = las(conn, sammantraden=list({s for s, _ in nycklar}))
    return {(r["sammantrade_id"], r["paragraf"]): r["markningar"] for r in rader
            if (r["sammantrade_id"], r["paragraf"]) in nycklar}


def satt_pa_paragrafer(conn: psycopg.Connection, poster: list[dict]) -> list[dict]:
    """Lägger märkningarna på poster med `sammantrade` {id} och `paragraf`, t.ex. en ledamots röster."""
    per = for_paragrafer(conn, ((p["sammantrade"]["id"], p["paragraf"]) for p in poster))
    for p in poster:
        p["markningar"] = per.get((p["sammantrade"]["id"], p["paragraf"]), [])
    return poster


def _plus_manader(d: date, manader: int) -> date:
    ar, manad = divmod(d.month - 1 + manader, 12)
    ar, manad = d.year + ar, manad + 1
    for dag in (d.day, 30, 29, 28):
        try:
            return date(ar, manad, dag)
        except ValueError:
            continue
    raise ValueError(d)


def lang_beredning(forsta: date | None, slutligt: date | None) -> bool:
    """Mer än 12 månader från första behandlingen till det slutliga beslutet."""
    return forsta is not None and slutligt is not None and slutligt > _plus_manader(forsta, LANG_BEREDNING_MANADER)


def for_arende(bs: list[dict]) -> list[dict]:
    """Ärendets märkningar ur dess behandlingar i ärendeordning (rader som `las` ger dem).

    Behandlingarnas märkningar summeras: en märkning som finns vid en behandling har den behandlingens text,
    annars namnet och antalet behandlingar, "Votering (2)". Typen (motion …) står en gång.
    """
    from .arenden import SAMLING, slutligt_beslut  # arenden läser ärendets märkningar härifrån

    per: dict[str, list[dict]] = defaultdict(list)
    for b in bs:
        for m in b.get("markningar") or []:
            per[m["id"]].append(m)
    ut = []
    for id_, namn in BEHANDLING.items():
        if not (ms := per.get(id_)):
            continue
        if id_ in _TYPMARKNINGAR:
            ut.append({"id": id_, "text": namn, "antal": len(ms)})
        elif len(ms) == 1:
            ut.append(ms[0] | {"antal": 1})
        else:
            m = {"id": id_, "text": f"{namn} ({len(ms)})", "antal": len(ms)}
            if id_ == "reservation":
                m["partier"] = sorted({p for x in ms for p in x["partier"]}, key=_partiordning)
            ut.append(m)
    daterade = [b for b in bs if b.get("datum") is not None]
    if daterade and slutligt_beslut(bs[-1].get("beslut")) and bs[-1].get("datum") is not None:
        if lang_beredning(min(b["datum"] for b in daterade), bs[-1]["datum"]):
            ut.append({"id": "lang_beredning", "text": ARENDE["lang_beredning"], "antal": 1})
    if len({b["sammantrade_id"] for b in bs if not SAMLING.search(b.get("rubrik") or "")}) >= 2:
        ut.append({"id": "aterkommande", "text": ARENDE["aterkommande"], "antal": 1})
    return ut
