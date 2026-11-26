"""Sökindex och fulltextsökning (#142): `python -m app.sokindex`.

Indexet består av sökenheter (tabellen `sokenhet`), en per sak som en träff visar. Varje typ har en
källa: en funktion som ger enheterna med deras text. En ny typ läggs till med en post i `KALLOR`.

- **behandling:** rubrik och diarienummer (A), beslut och yrkanden (B), paragraftexten (D).
- **protokollsida:** protokollets text sida för sida (D), läst ur PDF:en i `dokument.innehall` med samma
  sidtextfunktion som tolkningen (`protokolltolkning.las_sidtexter`) och sparad i `dokumenttext`.
- **budgetforslag:** de publicerade förslagens text sida för sida (D), titeln (A) och rubrikerna i ett
  Word-dokument (B).
- **arende:** ärendets rubrik och diarienummer (A).
- **ledamot:** registrerade ledamöter med sina namn (A). Privatpersoner som nämns i protokollen får ingen
  egen enhet, deras namn finns bara i protokollets text.
- **kallelsepunkt:** punkterna i kallelsernas föredragningslistor, med rubrik och diarienummer (A).
- **styrande_dokument:** sidorna i den gällande versionen av kommunens styrande dokument (D), med titeln (A) på första
  sidan (#63). Texten lästes när versionen lagrades. Ett borttaget dokument har inga sidor i indexet.

Enheterna innehåller den gällande versionen: behandlingar och ärenden läses med de publicerade rättelserna
pålagda (`behandlingar.las`). Varje enhet har markeringarna som sidan den länkar till visar. Behandlingar och
ärenden har också sina märkningar (#162, `markningar`), som sökningen kan filtrera på.

En enhet skrivs bara om när dess text eller visning ändrats (`sha256` på texten). Indexet uppdateras i
insamlingen, efter omtolkning och när rättelser publiceras eller återkallas. Kommandot bygger ut indexet
med det som saknas, och `--bygg-om` bygger om allt. En ombyggnad kan avbrytas och återupptas: det som
redan gjorts efter att ombyggnaden startade görs inte om.

Sökningen (`sok`) svarar aldrig med något annat än träffar i källorna (ADR-0002).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import time
import zipfile
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from threading import Lock
from typing import Callable, Iterable, Iterator
from xml.etree import ElementTree

import psycopg
from psycopg.types.json import Jsonb

from . import markningar as markningsregler, protokolltolkning, sokvektorer
from .sources.harnosand import ORGAN

logger = logging.getLogger(__name__)

TYPER = ("behandling", "protokollsida", "budgetforslag", "arende", "ledamot", "kallelsepunkt", "styrande_dokument")
# Protokollsidorna först: behandlingarna hittar sin sida i protokollets text.
_INDEXERINGSORDNING = ("protokollsida", "behandling", "budgetforslag", "arende", "ledamot", "kallelsepunkt",
                       "styrande_dokument")


# Enheter

@dataclass
class Enhet:
    typ: str
    nyckel: str
    rubrik: str
    lank: str
    text_a: str = ""
    text_b: str = ""
    text_c: str = ""
    undertitel: str | None = None
    sammantrade_id: int | None = None
    organ: str | None = None
    datum: date | None = None
    ar: int | None = None
    dokument: str | None = None
    sida: int | None = None
    markeringar: list[str] = field(default_factory=list)
    exakt: list[str] = field(default_factory=list)
    markningar: list[dict] = field(default_factory=list)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps([self.text_a, self.text_b, self.text_c]).encode()).hexdigest()

    def visning(self) -> tuple:
        return (self.sammantrade_id, self.rubrik, self.undertitel, self.organ, self.datum, self.ar, self.lank,
                self.dokument, self.sida, list(self.markeringar), list(self.exakt), list(self.markningar))


@dataclass
class Grupp:
    """Enheterna vars nyckel börjar med `prefix`. `enheter` None betyder att de som finns behålls."""
    prefix: str
    enheter: list[Enhet] | None


def normalisera(text: str) -> str:
    """Form för exakta jämförelser: gemener, ett mellanslag, inga mellanslag kring / och -."""
    return re.sub(r"\s*([/-])\s*", r"\1", " ".join(text.split())).lower()


def _ar(d: date | None) -> int | None:
    return d.year if d else None


@dataclass
class Omfang:
    """Vad en indexering omfattar och får göra.

    `sammantraden`: bara de här sammanträdena, för källor som kan avgränsas så.
    `extrahera`: om dokumentens text får läsas (True), inte (False) eller bara för dokument från en
    viss insamlingskörning (dess id). Text som redan lästs används alltid.
    `ombyggnad`: när en pågående ombyggnad startade. Text som lästs före den läses om.
    """
    sammantraden: list[int] | None = None
    extrahera: bool | int = True
    ombyggnad: datetime | None = None
    commit: bool = False


# Dokumentens text

def _dokumenttext(conn: psycopg.Connection, dokument_id: int, korning_id: int, omf: Omfang) -> dict | None:
    """Dokumentets sidor ({sidor, ocr}), lästa nu om det behövs och får göras, annars None."""
    rad = conn.execute("SELECT sidor, ocr, last FROM dokumenttext WHERE dokument_id = %s", (dokument_id,)).fetchone()
    if rad is not None and (omf.ombyggnad is None or rad["last"] >= omf.ombyggnad):
        return rad
    if omf.extrahera is False or (omf.extrahera is not True and omf.extrahera != korning_id):
        return rad
    pdf = conn.execute("SELECT innehall FROM dokument WHERE id = %s", (dokument_id,)).fetchone()["innehall"]
    sidor, ocr, fel = _las_pdf(bytes(pdf))
    conn.execute(
        """
        INSERT INTO dokumenttext (dokument_id, sidor, ocr, fel, last) VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (dokument_id) DO UPDATE SET sidor = EXCLUDED.sidor, ocr = EXCLUDED.ocr, fel = EXCLUDED.fel,
            last = EXCLUDED.last
        """,
        (dokument_id, sidor, ocr, fel),
    )
    return {"sidor": sidor, "ocr": ocr}


def _las_pdf(pdf: bytes) -> tuple[list[str], bool, str | None]:
    try:
        lop, _, ocr = protokolltolkning.las_sidtexter(pdf, layout=False)
    except protokolltolkning.EjLasbar as e:
        return [], False, str(e)
    return [_rensa(s) for s in lop], ocr, None


def _rensa(text: str) -> str:
    # NUL kan inte lagras i en textkolumn.
    return text.replace("\x00", "")


def _word_stycken(docx: bytes) -> list[tuple[str, bool]]:
    """Styckena i ett Word-dokument som (text, rubrik)."""
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        rot = ElementTree.fromstring(z.read("word/document.xml"))
    ut = []
    for p in rot.iter(f"{w}p"):
        text = "".join(t.text or "" for t in p.iter(f"{w}t")).strip()
        if not text:
            continue
        stil = p.find(f"{w}pPr/{w}pStyle")
        namn = (stil.get(f"{w}val") or "") if stil is not None else ""
        ut.append((text, bool(re.match(r"(heading|rubrik|title|titel)", namn, re.I))))
    return ut


_PARAGRAFRAD = r"(?m)^[ \t]*§[ \t]*{p}(?!\d).*$"
_INNEHALLSFORTECKNING = re.compile(r"\.{5,}|…{2,}")
_PARAGRAFSTART = re.compile(r"(?m)^[ \t]*§[ \t]*(\d+)")


def paragrafsida(sidor: list[str], paragraf: int) -> int | None:
    """Sidan (från 1) där paragrafen börjar i protokollet, när den går att hitta.

    Innehållsförteckningen räknas inte: där har raderna punktlinjer fram till sidnumret, eller så
    börjar många paragrafer på samma sida.
    """
    monster = re.compile(_PARAGRAFRAD.format(p=paragraf))
    for i, s in enumerate(sidor):
        if len(_INNEHALLSFORTECKNING.findall(s)) >= 2 or len(set(_PARAGRAFSTART.findall(s))) >= 4:
            continue
        if any(not _INNEHALLSFORTECKNING.search(m[0]) for m in monster.finditer(s)):
            return i + 1
    return None


# Källorna

def _organnamn(organ: str | None) -> str | None:
    return ORGAN[organ].namn if organ in ORGAN else organ


def _sammantraden(conn: psycopg.Connection, omf: Omfang) -> dict[int, dict]:
    """Sammanträden med protokoll: dokument, OCR och om protokollet innehåller felaktigheter."""
    return {r["id"]: r for r in conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.ocr, s.tolkning, s.dokument_id, d.typ AS dokument_typ, d.korning_id,
               EXISTS (SELECT 1 FROM rattelse r WHERE r.sammantrade_id = s.id AND r.status = 'publicerad'
                       AND r.felet_i = 'protokollet') AS felaktigheter
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        WHERE %(s)s::bigint[] IS NULL OR s.id = ANY(%(s)s)
        ORDER BY s.id
        """,
        {"s": omf.sammantraden},
    )}


def _behandlingar(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    sammantraden = _sammantraden(conn, omf)
    rader = markningsregler.las(conn, sammantraden=omf.sammantraden)
    extra = {r["id"]: r for r in conn.execute(
        """
        SELECT b.id, b.paragraftext,
               (SELECT string_agg(y.text, E'\n' ORDER BY y.ordning) FROM yrkande y WHERE y.behandling_id = b.id)
                   AS yrkanden
        FROM behandling b WHERE b.id = ANY(%s)
        """,
        ([r["id"] for r in rader],),
    )}
    sidtexter: dict[int, list[str]] = {}
    for s in sammantraden.values():
        t = conn.execute("SELECT sidor FROM dokumenttext WHERE dokument_id = %s", (s["dokument_id"],)).fetchone()
        sidtexter[s["id"]] = t["sidor"] if t else []
    enheter = []
    for b in rader:
        s = sammantraden.get(b["sammantrade_id"])
        if s is None:
            continue
        x = extra.get(b["id"], {})
        markeringar = ["ocr" if s["ocr"] else "automatiskt_tolkad"]
        if b.get("rattelser"):
            markeringar.append("rattad")
        if b.get("diarienummer_kallelse"):
            markeringar.append("diarienummer_ur_kallelsen")
        if s["felaktigheter"]:
            markeringar.append("felaktigheter")
        sida = paragrafsida(sidtexter[s["id"]], b["paragraf"])
        enheter.append(Enhet(
            typ="behandling", nyckel=f"{b['sammantrade_id']}:{b['paragraf']}", rubrik=b["rubrik"],
            undertitel=f"§ {b['paragraf']}", lank=f"/politik/sammantraden/{b['sammantrade_id']}/paragraf/{b['paragraf']}",
            text_a=" ".join([b["rubrik"], *b["diarienummer"]]),
            text_b="\n".join(t for t in (b["beslut"], x.get("yrkanden")) if t),
            text_c=x.get("paragraftext") or "",
            sammantrade_id=b["sammantrade_id"], organ=b["organ"], datum=b["datum"], ar=_ar(b["datum"]),
            dokument=f"/api/dokument/{s['dokument_id']}" + (f"#page={sida}" if sida else ""), sida=sida,
            markeringar=markeringar, exakt=[normalisera(d) for d in b["diarienummer"]], markningar=b["markningar"],
        ))
    yield Grupp("", enheter)


def _protokollsidor(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    for s in _sammantraden(conn, omf).values():
        t = _dokumenttext(conn, s["dokument_id"], s["korning_id"], omf)
        if t is None:
            yield Grupp(f"{s['id']}:", None)
            continue
        namn = "Paragrafprotokoll" if s["dokument_typ"] == "paragrafprotokoll" else "Protokoll"
        markeringar = (["ocr"] if t["ocr"] else []) + (["felaktigheter"] if s["felaktigheter"] else [])
        yield Grupp(f"{s['id']}:", [
            Enhet(typ="protokollsida", nyckel=f"{s['id']}:{i}", rubrik=f"{namn}, sidan {i}", undertitel=f"Sidan {i}",
                  lank=f"/politik/sammantraden/{s['id']}", text_c=text, sammantrade_id=s["id"], organ=s["organ"],
                  datum=s["datum"], ar=_ar(s["datum"]), dokument=f"/api/dokument/{s['dokument_id']}#page={i}",
                  sida=i, markeringar=markeringar)
            for i, text in enumerate(t["sidor"], start=1) if text.strip()
        ])


def _budgetforslag(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    befintliga = {r["dokument"].split("#")[0]: r["andrad"] for r in conn.execute(
        "SELECT DISTINCT ON (split_part(dokument, '#', 1)) dokument, andrad FROM sokenhet "
        "WHERE typ = 'budgetforslag' ORDER BY split_part(dokument, '#', 1), andrad")}
    for f in conn.execute(
        "SELECT id, budgetar, nyckel, titel, partier, filnamn FROM budgetforslag WHERE status = 'publicerad' "
        "ORDER BY budgetar, nyckel"
    ).fetchall():
        prefix = f"{f['budgetar']}:{f['nyckel']}:"
        original = f"/api/budgetforslag/{f['id']}/original"
        andrad = befintliga.get(original)
        aktuell = andrad is not None and (omf.ombyggnad is None or andrad >= omf.ombyggnad)
        if aktuell or omf.extrahera is not True:
            # Ett förslag ändras inte efter publicering, bara genom en ny version med eget id.
            yield Grupp(prefix, None)
            continue
        innehall = bytes(conn.execute("SELECT original FROM budgetforslag WHERE id = %s", (f["id"],)).fetchone()["original"])
        titel = " ".join([f["titel"], *f["partier"]])
        bas = dict(typ="budgetforslag", organ=None, datum=None, ar=f["budgetar"],
                   lank=f"/politik/budget?ar={f['budgetar']}")
        if f["filnamn"].lower().endswith(".docx"):
            try:
                stycken = _word_stycken(innehall)
            except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
                stycken = []
            enheter = [Enhet(nyckel=f"{prefix}0", rubrik=f["titel"], text_a=titel,
                             text_b="\n".join(t for t, rubrik in stycken if rubrik),
                             text_c="\n".join(t for t, rubrik in stycken if not rubrik),
                             dokument=original, **bas)]
        else:
            sidor, _, _ = _las_pdf(innehall)
            enheter = [Enhet(nyckel=f"{prefix}{i}", rubrik=f"{f['titel']}, sidan {i}", undertitel=f"Sidan {i}",
                             text_a=titel if i == 1 else "", text_c=text, dokument=f"{original}#page={i}", sida=i,
                             **bas)
                       for i, text in enumerate(sidor, start=1) if text.strip()]
        yield Grupp(prefix, enheter)


def _arenden(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    per_arende: dict[int, list[dict]] = {}
    for b in markningsregler.las(conn):  # i ärendeordning
        if b["arende_id"] is not None:
            per_arende.setdefault(b["arende_id"], []).append(b)
    enheter = []
    for arende_id, beh in per_arende.items():
        sista = beh[-1]
        diarienummer = list(dict.fromkeys(d for b in beh for d in b["diarienummer"]))
        enheter.append(Enhet(
            typ="arende", nyckel=str(arende_id), rubrik=sista["rubrik"],
            undertitel=f"{len(beh)} {'behandling' if len(beh) == 1 else 'behandlingar'}",
            lank=f"/politik/arenden/{arende_id}", text_a=" ".join([sista["rubrik"], *diarienummer]),
            organ=sista["organ"], datum=sista["datum"], ar=_ar(sista["datum"]),
            exakt=[normalisera(d) for d in diarienummer], markningar=markningsregler.for_arende(beh),
        ))
    yield Grupp("", enheter)


def _ledamoter(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    rader = conn.execute(
        """
        SELECT p.id, p.namn, array_agg(l.namn ORDER BY l.huvud_id IS NOT NULL, l.namn) AS namn_alla
        FROM ledamot p JOIN ledamot l ON coalesce(l.huvud_id, l.id) = p.id
        WHERE p.huvud_id IS NULL
        GROUP BY p.id
        HAVING bool_or(EXISTS (SELECT 1 FROM narvaro n WHERE n.namn = l.namn AND n.kategori <> 'ovrig'))
        ORDER BY p.id
        """
    ).fetchall()
    yield Grupp("", [
        Enhet(typ="ledamot", nyckel=str(r["id"]), rubrik=r["namn"], lank=f"/politik/ledamoter/{r['id']}",
              text_a=" ".join(r["namn_alla"]), exakt=[normalisera(n) for n in r["namn_alla"]])
        for r in rader
    ])


def _kallelsepunkter(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    rader = conn.execute(
        """
        SELECT p.id, p.paragraf, p.rubrik, p.diarienummer, p.sida, k.organ, k.datum, k.typ, k.url,
               (SELECT s.id FROM sammantrade s WHERE s.organ = k.organ
                  AND coalesce(s.datum, s.plan_datum) = k.datum
                ORDER BY s.dokument_id IS NULL, s.id LIMIT 1) AS sammantrade_id,
               (SELECT s.dokument_id IS NOT NULL FROM sammantrade s WHERE s.organ = k.organ
                  AND coalesce(s.datum, s.plan_datum) = k.datum
                ORDER BY s.dokument_id IS NULL, s.id LIMIT 1) AS protokoll
        FROM kallelsepunkt p JOIN kallelse k ON k.id = p.kallelse_id
        ORDER BY p.id
        """
    ).fetchall()
    enheter = []
    for r in rader:
        if r["sammantrade_id"] is None:
            lank = "/politik/kalender"
        elif r["protokoll"]:
            lank = f"/politik/sammantraden/{r['sammantrade_id']}"
        else:
            lank = f"/politik/kalender?sammantrade={r['sammantrade_id']}"
        typnamn = {"kungorelse": "Kungörelse", "kallelse": "Kallelse", "handlingar": "Handlingar"}[r["typ"]]
        enheter.append(Enhet(
            typ="kallelsepunkt", nyckel=str(r["id"]), rubrik=r["rubrik"],
            undertitel=f"{typnamn}" + (f", § {r['paragraf']}" if r["paragraf"] is not None else ""),
            lank=lank, text_a=" ".join([r["rubrik"], *r["diarienummer"]]), organ=r["organ"], datum=r["datum"],
            ar=_ar(r["datum"]), dokument=f"{r['url']}#page={r['sida']}" if r["sida"] else r["url"], sida=r["sida"],
            markeringar=["automatiskt_tolkad"], exakt=[normalisera(d) for d in r["diarienummer"]],
        ))
    yield Grupp("", enheter)


def _styrande_dokument(conn: psycopg.Connection, omf: Omfang) -> Iterator[Grupp]:
    from . import styrande_dokument  # styrande_dokument använder insamlingens moduler

    for r in conn.execute(
        """
        SELECT DISTINCT ON (d.id) d.id, d.titel, v.version, v.sidor, v.ocr, v.dokumentinformation
        FROM styrande_dokument d JOIN styrande_dokument_version v ON v.dokument_id = d.id
        WHERE d.borttagen IS NULL ORDER BY d.id, v.version DESC
        """
    ).fetchall():
        info = r["dokumentinformation"]
        organ = styrande_dokument.faststallt_organ(info.get("faststalld_av"))
        datum = styrande_dokument.tolka_datum(info.get("datum"))
        bas = f"/api/styrande-dokument/{r['id']}/versioner/{r['version']}"
        yield Grupp(f"{r['id']}:", [
            Enhet(typ="styrande_dokument", nyckel=f"{r['id']}:{i}", rubrik=f"{r['titel']}, sidan {i}",
                  undertitel=f"Sidan {i}", lank=f"/politik/styrande-dokument/{r['id']}",
                  text_a=r["titel"] if i == 1 else "", text_c=text, organ=organ, datum=datum, ar=_ar(datum),
                  dokument=f"{bas}#page={i}", sida=i, markeringar=["ocr"] if r["ocr"] else [])
            for i, text in enumerate(r["sidor"], start=1) if text.strip()
        ])


@dataclass(frozen=True)
class Kalla:
    enheter: Callable[[psycopg.Connection, Omfang], Iterable[Grupp]]
    # Kan avgränsas till vissa sammanträden (Omfang.sammantraden).
    avgransad: bool = False


KALLOR: dict[str, Kalla] = {
    "behandling": Kalla(_behandlingar, avgransad=True),
    "protokollsida": Kalla(_protokollsidor, avgransad=True),
    "budgetforslag": Kalla(_budgetforslag),
    "arende": Kalla(_arenden),
    "ledamot": Kalla(_ledamoter),
    "kallelsepunkt": Kalla(_kallelsepunkter),
    "styrande_dokument": Kalla(_styrande_dokument),
}


# Indexering

_KOLUMNER = ("sammantrade_id", "rubrik", "undertitel", "organ", "datum", "ar", "lank", "dokument", "sida",
             "markeringar", "exakt", "markningar")


def indexera(conn: psycopg.Connection, typer: Iterable[str] | None = None, sammantraden: list[int] | None = None,
             extrahera: bool | int = True, ombyggnad: datetime | None = None, commit: bool = False,
             vektorer: bool = True) -> dict[str, int]:
    """Uppdaterar indexet för typerna (standard alla). Ger antal nya, ändrade, oförändrade och borttagna.

    Med `vektorer` räknas också vektorerna (#69) för de enheter som skrevs om.

    Med `sammantraden` uppdateras bara de sammanträdena, för typer som kan avgränsas, och övriga typer helt.
    Med `commit` sparas arbetet efter varje grupp, så att en avbruten körning inte behöver göra om det.
    """
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0, "borttagna": 0}
    valda = set(typer or TYPER)
    skrivna: list[int] = []
    for typ in (t for t in _INDEXERINGSORDNING if t in valda):
        kalla = KALLOR[typ]
        omf = Omfang(sammantraden=sammantraden if kalla.avgransad else None, extrahera=extrahera,
                     ombyggnad=ombyggnad, commit=commit)
        befintliga = {r["nyckel"]: r for r in conn.execute(
            f"SELECT nyckel, sha256, andrad, {', '.join(_KOLUMNER)} FROM sokenhet WHERE typ = %(t)s "
            "AND (%(s)s::bigint[] IS NULL OR sammantrade_id = ANY(%(s)s))",
            {"t": typ, "s": omf.sammantraden},
        )}
        sedda: set[str] = set()
        behallna: list[str] = []
        for grupp in kalla.enheter(conn, omf):
            if grupp.enheter is None:
                behallna.append(grupp.prefix)
            else:
                for e in grupp.enheter:
                    sedda.add(e.nyckel)
                    utfall, enhet_id = _skriv(conn, e, befintliga.get(e.nyckel), ombyggnad)
                    antal[utfall] += 1
                    if enhet_id is not None:
                        skrivna.append(enhet_id)
            if commit:
                conn.commit()
        borttagna = [n for n in befintliga if n not in sedda and not any(n.startswith(p) for p in behallna)]
        if borttagna:
            conn.execute("DELETE FROM sokenhet WHERE typ = %s AND nyckel = ANY(%s)", (typ, borttagna))
            antal["borttagna"] += len(borttagna)
        if commit:
            conn.commit()
    if vektorer:
        sokvektorer.vektorisera(conn, skrivna, commit=commit)
    return antal


def _skriv(conn: psycopg.Connection, e: Enhet, befintlig: dict | None,
           ombyggnad: datetime | None) -> tuple[str, int | None]:
    sha = e.sha256
    if befintlig is not None:
        gammal = tuple(befintlig[k] for k in _KOLUMNER)
        if (befintlig["sha256"] == sha and gammal == e.visning()
                and (ombyggnad is None or befintlig["andrad"] >= ombyggnad)):
            return "oforandrade", None
    rad = conn.execute(
        f"""
        INSERT INTO sokenhet (typ, nyckel, {', '.join(_KOLUMNER)}, text_a, text_b, text_c, sha256)
        VALUES (%(typ)s, %(nyckel)s, {', '.join(f'%({k})s' for k in _KOLUMNER)}, %(text_a)s, %(text_b)s, %(text_c)s,
                %(sha256)s)
        ON CONFLICT (typ, nyckel) DO UPDATE SET
            {', '.join(f'{k} = EXCLUDED.{k}' for k in _KOLUMNER)},
            text_a = EXCLUDED.text_a, text_b = EXCLUDED.text_b, text_c = EXCLUDED.text_c,
            text_andrad = CASE WHEN sokenhet.sha256 = EXCLUDED.sha256 THEN sokenhet.text_andrad ELSE now() END,
            sha256 = EXCLUDED.sha256, andrad = now()
        RETURNING id
        """,
        {"typ": e.typ, "nyckel": e.nyckel, **{k: getattr(e, k) for k in _KOLUMNER}, "markningar": Jsonb(e.markningar),
         "text_a": _rensa(e.text_a), "text_b": _rensa(e.text_b), "text_c": _rensa(e.text_c), "sha256": sha},
    ).fetchone()
    return ("nya" if befintlig is None else "andrade"), rad["id"]


def uppdatera(conn: psycopg.Connection, **kw) -> dict[str, int] | None:
    """Som `indexera`, men ett fel stoppar inte det som anropade (insamling, rättelse). Felet loggas."""
    try:
        with conn.transaction():
            return indexera(conn, **kw)
    except Exception:
        logger.exception("Sökindexet kunde inte uppdateras")
        return None


# Sökning

SORTERINGAR = ("relevans", "datum")
SIDSTORLEK = 20
_ORDTYPER = {"asciiword", "word", "hword_asciipart", "hword_part", "numword", "hword_numpart"}
# Bestämd form som den svenska stemmern inte tar bort: "skolan" och "skolans" blir "skolan", "huset" blir "huset".
_BESTAMDA = (("ans", 2), ("an", 1), ("ets", 3), ("et", 2))
_DNR = re.compile(r"[A-ZÅÄÖa-zåäö]{1,5}\s?[A-ZÅÄÖa-zåäö]{0,5}\s?/\s?\d{4}\s?[-:]\s?\d+|\d{4}-\d{3,6}")
_SKILJETECKEN = "\"'()[]{},;:!?«»”“.…"


def _lexem(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def fraga(conn: psycopg.Connection, q: str) -> str | None:
    """Sökfrågan som tsquery-text: alla ord ska finnas, med böjningar.

    Den svenska stemmern ger "skol" för "skola", "skolor" och "skolorna" men "skolan" för "skolan".
    Varje ord får därför också sin stam med bestämd form ("skol" → "skolan", "beslut" → "beslutet"),
    och ett ord i bestämd form får stammen utan den ("skolan" → "skol").
    """
    ord_ = [o.strip(_SKILJETECKEN).lower() for o in q.split()][:12]
    ord_ = [o for o in ord_ if o]
    if not ord_:
        return None
    tokens = conn.execute(
        """
        SELECT u.nr, d.alias, d.token, d.lexemes FROM unnest(%s::text[]) WITH ORDINALITY u(ord, nr),
        LATERAL ts_debug('swedish', u.ord) d
        WHERE d.lexemes IS NOT NULL AND cardinality(d.lexemes) > 0
        ORDER BY u.nr
        """,
        (ord_,),
    ).fetchall()
    kortade = sorted({t["token"].lower()[:-n] for t in tokens if t["alias"] in _ORDTYPER
                      for s, n in _BESTAMDA if t["token"].lower().endswith(s) and len(t["token"]) - len(s) >= 3})
    stammar = {r["ord"]: r["lexem"] for r in conn.execute(
        "SELECT o AS ord, (ts_lexize('swedish_stem', o))[1] AS lexem FROM unnest(%s::text[]) o", (kortade,))}
    delar = []
    for t in tokens:
        varianter = set(t["lexemes"])
        if t["alias"] in _ORDTYPER:
            tok = t["token"].lower()
            varianter |= {stammar.get(tok[:-n]) for s, n in _BESTAMDA if tok.endswith(s)} - {None}
            varianter |= {v + slut for v in list(varianter) for slut in ("an", "et")}
        delar.append("(" + " | ".join(_lexem(v) for v in sorted(varianter)) + ")")
    return " & ".join(delar) or None


def exakt_fraga(q: str) -> str:
    return normalisera(q.strip(_SKILJETECKEN + " "))


_START, _SLUT = "\x01", "\x02"


def _utdrag(text: str | None) -> list[dict]:
    """ts_headline-texten som delar, där de markerade är sökorden."""
    if not text:
        return []
    ut = []
    for i, del_ in enumerate(re.split(f"{_START}|{_SLUT}", re.sub(r"\s+", " ", text).strip())):
        if del_:
            ut.append({"text": del_, "markerad": i % 2 == 1})
    return ut


_TYPNAMN = {"behandling": "Behandling", "protokollsida": "Protokollsida", "budgetforslag": "Budgetförslag",
            "arende": "Ärende", "ledamot": "Ledamot", "kallelsepunkt": "Kallelsepunkt",
            "styrande_dokument": "Styrande dokument"}


def sok(conn: psycopg.Connection, q: str, organ: str | None = None, ar: int | None = None, typ: str | None = None,
        sortering: str = "relevans", sida: int = 1, markning: str | None = None) -> dict:
    """Träffarna för frågan, en sida i taget, och antalet per typ (utan typfiltret).

    Hybridsök (#69): fulltextlistan och vektorlistan slås ihop med reciprocal rank fusion, där en enhet får
    1 / (60 + placeringen) från varje lista den finns i. Exakta träffar på diarienummer och namn ligger först.
    En fråga som är ett diarienummer söks bara exakt och i fulltext.

    Med `markning` (#162) bara enheter med märkningen, alltså behandlingar och ärenden. En tom fråga ger då
    alla med märkningen.
    """
    utan_fraga = not q.strip()
    tsq = None if utan_fraga else fraga(conn, q)
    exakt = None if utan_fraga else exakt_fraga(q) or None
    fragevektor, vektortraffar = ((None, []) if utan_fraga or _DNR.fullmatch(q.strip())
                                  else sokvektorer.sok(conn, q, organ, ar))
    param = {"q": tsq, "exakt": exakt, "organ": organ, "ar": ar, "typ": typ,
             "markning": Jsonb([{"id": markning}]) if markning else None,
             "vid": [v["id"] for v in vektortraffar],
             "grans": SIDSTORLEK, "fran": (max(sida, 1) - 1) * SIDSTORLEK}
    textvillkor = ("TRUE" if utan_fraga else
                   "(e.sokvektor @@ %(q)s::tsquery OR e.exakt @> ARRAY[%(exakt)s::text] OR e.id = ANY(%(vid)s::bigint[]))")
    villkor = textvillkor + """
        AND (%(markning)s::jsonb IS NULL OR e.markningar @> %(markning)s::jsonb)
        AND (%(organ)s::text IS NULL OR e.organ = %(organ)s)
        AND (%(ar)s::int IS NULL OR e.ar = %(ar)s)
    """
    per_typ = {r["typ"]: r["antal"] for r in conn.execute(
        f"SELECT e.typ, count(*) AS antal FROM sokenhet e WHERE {villkor} GROUP BY e.typ", param)}
    ordning = ("niva DESC, rrf DESC, datum DESC NULLS LAST, id" if sortering == "relevans"
               else "datum DESC NULLS LAST, ar DESC NULLS LAST, niva DESC, rrf DESC, id")
    rader = conn.execute(
        f"""
        WITH kandidater AS (
            SELECT e.*,
                   CASE WHEN e.exakt @> ARRAY[%(exakt)s::text]
                        THEN CASE e.typ WHEN 'arende' THEN 3 WHEN 'ledamot' THEN 3 WHEN 'behandling' THEN 2 ELSE 1 END
                        ELSE 0 END AS niva,
                   coalesce(e.sokvektor @@ %(q)s::tsquery, false) AS i_text,
                   coalesce(ts_rank(e.sokvektor, %(q)s::tsquery), 0) AS rang,
                   v.nr AS vnr
            FROM sokenhet e
            LEFT JOIN unnest(%(vid)s::bigint[]) WITH ORDINALITY v(id, nr) ON v.id = e.id
            WHERE {villkor} AND (%(typ)s::text IS NULL OR e.typ = %(typ)s)
        ),
        rangordnade AS (
            -- Placeringen i varje lista räknas efter filtren.
            SELECT k.*,
                   CASE WHEN k.i_text THEN 1.0 / (60 + rank() OVER (PARTITION BY k.i_text ORDER BY k.rang DESC))
                        ELSE 0 END
                   + CASE WHEN k.vnr IS NOT NULL
                          THEN 1.0 / (60 + rank() OVER (PARTITION BY k.vnr IS NULL ORDER BY k.vnr)) ELSE 0 END AS rrf
            FROM kandidater k
        ),
        traffar AS (
            SELECT * FROM rangordnade ORDER BY {ordning} LIMIT %(grans)s OFFSET %(fran)s
        )
        SELECT t.id, t.typ, t.nyckel, t.rubrik, t.undertitel, t.organ, t.datum, t.ar, t.lank, t.dokument, t.sida,
               t.markeringar, t.markningar, t.sammantrade_id, t.niva = 0 AND NOT t.i_text AS bara_betydelse,
               CASE WHEN %(q)s::tsquery IS NULL THEN left(u.text, 200)
                    ELSE ts_headline('swedish', u.text, %(q)s::tsquery,
                                     'MaxFragments=2, MaxWords=24, MinWords=8, ShortWord=2, '
                                     'FragmentDelimiter=" … ", StartSel=' || chr(1) || ', StopSel=' || chr(2))
               END AS utdrag
        FROM traffar t
        -- Rubriken visas redan. Utdraget är ur beslutet, yrkandena och löptexten.
        CROSS JOIN LATERAL (SELECT nullif(concat_ws(E'\n', nullif(t.text_b, ''), nullif(t.text_c, '')), '') AS text) u
        ORDER BY {ordning}
        """,
        param,
    ).fetchall()
    # En träff som bara kommer från vektorsökningen har inga sökord att markera. Utdraget är den mening i
    # det närmaste stycket som ligger närmast frågan.
    stycken = {v["id"]: v["stycke"] for v in vektortraffar}
    meningar = sokvektorer.basta_meningar(
        fragevektor, {r["id"]: stycken[r["id"]] for r in rader if r["bara_betydelse"] and r["id"] in stycken}
    ) if fragevektor is not None else {}
    sammantraden = {r["sammantrade_id"] for r in rader if r["sammantrade_id"]}
    felaktigheter = {}
    if sammantraden:
        felaktigheter = {r["sammantrade_id"]: r["antal"] for r in conn.execute(
            "SELECT sammantrade_id, count(*) AS antal FROM rattelse WHERE status = 'publicerad' "
            "AND felet_i = 'protokollet' AND sammantrade_id = ANY(%s) GROUP BY sammantrade_id", (list(sammantraden),))}
    return {
        "antal": sum(per_typ.values()) if typ is None else per_typ.get(typ, 0),
        "per_typ": [{"typ": t, "namn": _TYPNAMN[t], "antal": per_typ.get(t, 0)} for t in TYPER],
        "sida": max(sida, 1),
        "sidstorlek": SIDSTORLEK,
        # Åren i indexet, för filtret.
        "ar_i_index": [r["ar"] for r in conn.execute(
            "SELECT DISTINCT ar FROM sokenhet WHERE ar IS NOT NULL ORDER BY ar DESC")],
        "traffar": [
            {
                "typ": r["typ"], "rubrik": r["rubrik"], "undertitel": r["undertitel"],
                "organ": {"id": r["organ"], "namn": _organnamn(r["organ"])} if r["organ"] else None,
                "datum": r["datum"], "ar": r["ar"], "lank": r["lank"], "dokument": r["dokument"], "sida": r["sida"],
                "markeringar": r["markeringar"],
                "markningar": r["markningar"],
                "utdrag": ([{"text": meningar[r["id"]], "markerad": False}] if r["id"] in meningar
                           else _utdrag(r["utdrag"])),
                "betydelse": r["bara_betydelse"],
                "sammantrade_id": r["sammantrade_id"],
                "felaktigheter": felaktigheter.get(r["sammantrade_id"], 0) if r["sammantrade_id"] else 0,
            }
            for r in rader
        ],
    }


class Fragegrans:
    """Högst `antal` frågor per `sekunder` och IP-adress, i ett glidande fönster."""

    def __init__(self, antal: int = 30, sekunder: float = 60.0, klocka: Callable[[], float] = time.monotonic) -> None:
        self.antal, self.sekunder, self.klocka = antal, sekunder, klocka
        self._fragor: dict[str, deque[float]] = {}
        self._las = Lock()

    def tillat(self, ip: str) -> float | None:
        """None om frågan är tillåten, annars antal sekunder tills nästa är det."""
        nu = self.klocka()
        with self._las:
            if len(self._fragor) > 10_000:  # glöm adresser som inte frågat på länge
                self._fragor = {k: v for k, v in self._fragor.items() if v and v[-1] > nu - self.sekunder}
            fragor = self._fragor.setdefault(ip, deque())
            while fragor and fragor[0] <= nu - self.sekunder:
                fragor.popleft()
            if len(fragor) >= self.antal:
                return fragor[0] + self.sekunder - nu
            fragor.append(nu)
            return None


class UtanSokfragor(logging.Filter):
    """Tar bort frågan ur åtkomstloggens rad för /api/sok: sökfrågorna loggas inte."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and args[2].startswith("/api/sok"):
            record.args = (*args[:2], args[2].split("?")[0], *args[3:])
        return True


# Kommandot

def bygg(conn: psycopg.Connection, bygg_om: bool = False) -> dict[str, int]:
    """Bygger ut indexet med det som saknas, eller bygger om allt. Arbetet sparas efter varje sammanträde."""
    startad = None
    if bygg_om:
        rad = conn.execute("SELECT id, startad FROM sokindex_ombyggnad WHERE klar IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if rad is None:
            rad = conn.execute("INSERT INTO sokindex_ombyggnad DEFAULT VALUES RETURNING id, startad").fetchone()
            conn.commit()
        else:
            logger.info("Återupptar ombyggnaden som startade %s", rad["startad"])
        startad = rad["startad"]
    antal = indexera(conn, extrahera=True, ombyggnad=startad, commit=True, vektorer=False)
    # Vektorerna för alla enheter som väntar: ändrade, nya, eller räknade med en annan modell.
    antal["vektorer"] = sokvektorer.vektorisera(conn, commit=True)
    if bygg_om:
        conn.execute("UPDATE sokindex_ombyggnad SET klar = now() WHERE klar IS NULL")
        conn.commit()
    return antal


def main(argv: list[str] | None = None) -> None:
    from . import db

    p = argparse.ArgumentParser(description="Bygger ut sökindexet med det som saknas eller har ändrats.")
    p.add_argument("--bygg-om", action="store_true",
                   help="bygg om hela indexet och läs om dokumentens text. Kan avbrytas och återupptas.")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn:
        antal = bygg(conn, a.bygg_om)
    print(f"Sökindexet: {antal['nya']} nya, {antal['andrade']} ändrade, {antal['oforandrade']} oförändrade och "
          f"{antal['borttagna']} borttagna enheter. Vektorer för {antal['vektorer']} enheter. {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.")


if __name__ == "__main__":
    main()
