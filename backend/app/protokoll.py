"""Protokoll: lagring av hämtade protokoll och läsning av det som tolkats ur dem.

Ett protokoll sparas som plattformens egen kopia med SHA-256. Nytt innehåll under samma
adress blir en ny version. Varje ny version tolkas (se `protokolltolkning`), och sammanträdets
automatiskt tolkade uppgifter ersätts med den nya tolkningen. Sammanträdet behåller sitt id,
så länkar till det fortsätter att fungera.

Hela protokollet är det primära. Ett paragrafprotokoll (omedelbart justerade paragrafer) visas
som sammanträdet tills hela protokollet finns, och ersätts då av det. Paragrafprotokollet sparas
kvar som dokument.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

import psycopg
from psycopg.types.json import Jsonb

from . import arenden, ledamoter, partier
from .rattelser import Publicerade
from .protokolltolkning import Behandling, Narvaro, Tolkning, beslutande_vid, tolka
from .sources.base import Dokument
from .sources.harnosand import ORGAN


def _datum_ur_filnamn(filnamn: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", filnamn)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


def lagra_dokument(
    conn: psycopg.Connection, datakalla_id: str, d: Dokument, korning_id: int, hamtad: datetime
) -> tuple[str, str | None]:
    """Sparar dokumentet och tolkar det. Returnerar ('ny' | 'andrad' | 'oforandrad', fel eller None)."""
    sha = hashlib.sha256(d.innehall).hexdigest()
    senaste = conn.execute(
        "SELECT sha256, version FROM dokument WHERE url = %s ORDER BY version DESC LIMIT 1", (d.url,)
    ).fetchone()
    if senaste is not None and senaste["sha256"] == sha:
        return "oforandrad", None
    if senaste is None and conn.execute("SELECT 1 FROM dokument WHERE sha256 = %s", (sha,)).fetchone():
        return "oforandrad", None  # samma innehåll har publicerats under en annan adress
    version = 1 if senaste is None else senaste["version"] + 1
    dokument_id = conn.execute(
        """
        INSERT INTO dokument (datakalla_id, url, version, filnamn, typ, organ, sha256, storlek, innehall, hamtad, korning_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (datakalla_id, d.url, version, d.filnamn, d.typ, d.organ, sha, len(d.innehall), d.innehall, hamtad, korning_id),
    ).fetchone()["id"]

    t = tolka(d.innehall)
    _lagra_tolkning(conn, d, dokument_id, t, hamtad)
    fel = None
    if not t.tolkad:
        fel = f"{d.filnamn}: kunde inte tolkas automatiskt ({'; '.join(t.avvikelser)})"
    return ("ny" if version == 1 else "andrad"), fel


def _nyckel(d: Dokument, t: Tolkning) -> tuple[str, date | None]:
    if t.tolkad:
        return (f"{t.datum.isoformat()} {t.starttid}" if t.starttid else t.datum.isoformat()), t.datum
    # Utan tolkning identifieras sammanträdet av filen. Datumet tas ur filnamnet om det går.
    return f"fil:{d.filnamn}", t.datum or _datum_ur_filnamn(d.filnamn)


def tolka_om(conn: psycopg.Connection, tolkad: datetime) -> dict[str, int]:
    """Tolkar om de lagrade protokollen med den nuvarande tolkningen, t.ex. efter att den förbättrats.

    Sammanträdena behåller sina id, så att länkar till dem fortsätter att fungera. Hela protokoll
    tolkas före paragrafprotokoll, som bara gäller tills protokollet finns.
    """
    rader = conn.execute(
        """
        SELECT s.id, s.organ, s.nyckel, s.tolkning, d.id AS dokument_id, d.url, d.filnamn, d.typ, d.innehall
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        ORDER BY d.typ = 'paragrafprotokoll', s.id
        """
    ).fetchall()
    antal = {"sammantraden": len(rader), "nu_tolkade": 0, "nu_ej_tolkade": 0}
    for r in rader:
        d = Dokument(url=r["url"], filnamn=r["filnamn"], typ=r["typ"], organ=r["organ"], innehall=bytes(r["innehall"]))
        t = tolka(d.innehall)
        nyckel, _ = _nyckel(d, t)
        if nyckel != r["nyckel"]:
            if conn.execute(
                "SELECT 1 FROM sammantrade WHERE organ = %s AND nyckel = %s", (d.organ, nyckel)
            ).fetchone():
                # Sammanträdet finns redan, ur ett annat dokument. Det avgör _lagra_tolkning.
                conn.execute("DELETE FROM sammantrade WHERE id = %s", (r["id"],))
            else:
                conn.execute("UPDATE sammantrade SET nyckel = %s WHERE id = %s", (nyckel, r["id"]))
        _lagra_tolkning(conn, d, r["dokument_id"], t, tolkad)
        if t.tolkad and r["tolkning"] == "ej_tolkad":
            antal["nu_tolkade"] += 1
        elif not t.tolkad and r["tolkning"] == "tolkad":
            antal["nu_ej_tolkade"] += 1
    return antal


def _lagra_tolkning(conn: psycopg.Connection, d: Dokument, dokument_id: int, t: Tolkning, tolkad: datetime) -> None:
    nyckel, datum = _nyckel(d, t)
    if d.typ == "paragrafprotokoll":
        # Ett paragrafprotokoll gäller bara tills hela protokollet finns, och ersätter inte ett annat
        # paragrafprotokoll från samma sammanträde. Dokumentet sparas ändå.
        befintlig = conn.execute(
            """
            SELECT d.typ, d.url FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
            WHERE s.organ = %s AND s.nyckel = %s
            """,
            (d.organ, nyckel),
        ).fetchone()
        if befintlig is not None and (befintlig["typ"] == "protokoll" or befintlig["url"] != d.url):
            return
    sammantrade_id = conn.execute(
        """
        INSERT INTO sammantrade (organ, nyckel, datum, starttid, sluttid, plats, dokument_id, tolkning, avvikelser, tolkad)
        VALUES (%(organ)s, %(nyckel)s, %(datum)s, %(starttid)s, %(sluttid)s, %(plats)s, %(dokument_id)s,
                %(tolkning)s, %(avvikelser)s, %(tolkad)s)
        ON CONFLICT (organ, nyckel) DO UPDATE SET
            datum = EXCLUDED.datum, starttid = EXCLUDED.starttid, sluttid = EXCLUDED.sluttid, plats = EXCLUDED.plats,
            dokument_id = EXCLUDED.dokument_id, tolkning = EXCLUDED.tolkning, avvikelser = EXCLUDED.avvikelser,
            tolkad = EXCLUDED.tolkad
        RETURNING id
        """,
        {"organ": d.organ, "nyckel": nyckel, "datum": datum, "starttid": t.starttid, "sluttid": t.sluttid,
         "plats": t.plats, "dokument_id": dokument_id, "tolkning": "tolkad" if t.tolkad else "ej_tolkad",
         "avvikelser": Jsonb(t.avvikelser), "tolkad": tolkad},
    ).fetchone()["id"]
    conn.execute("DELETE FROM narvaro WHERE sammantrade_id = %s", (sammantrade_id,))
    conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s", (sammantrade_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori, tjanstgor_for,
                                 tjanstgor_for_parti, paragrafer, jav)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(sammantrade_id, i, n.namn, n.parti, n.roll, n.kategori, n.tjanstgor_for, n.tjanstgor_for_parti,
              n.paragrafer, n.jav) for i, n in enumerate(t.narvaro)],
        )
    for i, b in enumerate(t.behandlingar):
        _lagra_behandling(conn, sammantrade_id, i, b)
    ledamoter.registrera(conn, (n.namn for n in t.narvaro if n.kategori != "ovrig"))


def _lagra_behandling(conn: psycopg.Connection, sammantrade_id: int, ordning: int, b: Behandling) -> None:
    behandling_id = conn.execute(
        """
        INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, diarienummer, beslut, propositionsordning,
                                motionarer)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (sammantrade_id, ordning, b.paragraf, b.rubrik, b.diarienummer, b.beslut, b.propositionsordning,
         Jsonb([{"namn": n, "parti": p} for n, p in b.motionarer])),
    ).fetchone()["id"]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO yrkande (behandling_id, ordning, text, personer) VALUES (%s, %s, %s, %s)",
            [(behandling_id, i, y.text, Jsonb([{"namn": n, "parti": p} for n, p in y.personer]))
             for i, y in enumerate(b.yrkanden)],
        )
        cur.executemany(
            "INSERT INTO reservation (behandling_id, ordning, text, personer, partier) VALUES (%s, %s, %s, %s, %s)",
            [(behandling_id, i, r.text, Jsonb([{"namn": n, "parti": p} for n, p in r.personer]), r.partier)
             for i, r in enumerate(b.reservationer)],
        )
        cur.executemany(
            "INSERT INTO hanvisning (behandling_id, ordning, organ, datum, paragraf, text) VALUES (%s, %s, %s, %s, %s, %s)",
            [(behandling_id, i, h.organ, h.datum, h.paragraf, h.text) for i, h in enumerate(b.hanvisningar)],
        )
    for i, v in enumerate(b.voteringar):
        votering_id = conn.execute(
            """
            INSERT INTO votering (behandling_id, ordning, ja_forslag, nej_forslag, ja, nej, avstar, franvarande,
                                  resultat, vinnare)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (behandling_id, i, v.ja_forslag, v.nej_forslag, v.ja, v.nej, v.avstar, v.franvarande, v.resultat,
             v.vinnare),
        ).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO rost (votering_id, ordning, namn, parti, rost, ersatt, ersatt_parti)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [(votering_id, k, r.namn, r.parti, r.rost, r.ersatt, r.ersatt_parti) for k, r in enumerate(v.roster)],
            )


# Läsning

_SAMMANTRADE = """
    SELECT s.id, s.organ, s.datum, s.starttid, s.sluttid, s.plats, s.tolkning, s.avvikelser, s.tolkad,
           d.id AS dokument_id, d.url AS dokument_url, d.filnamn, d.typ AS dokument_typ,
           d.version AS dokument_version,
           d.sha256, d.storlek, d.hamtad, d.datakalla_id, k.titel AS datakalla_titel,
           (SELECT count(*) FROM behandling b WHERE b.sammantrade_id = s.id) AS antal_behandlingar,
           (SELECT min(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS forsta_paragraf,
           (SELECT max(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS sista_paragraf
    FROM sammantrade s
    JOIN dokument d ON d.id = s.dokument_id
    JOIN datakalla k ON k.id = d.datakalla_id
"""


def _sammantrade(rad: dict) -> dict:
    organ = ORGAN.get(rad["organ"])
    return {
        "id": rad["id"],
        "organ": {"id": rad["organ"], "namn": organ.namn if organ else rad["organ"]},
        "datum": rad["datum"],
        "starttid": rad["starttid"],
        "sluttid": rad["sluttid"],
        "plats": rad["plats"],
        "tolkning": rad["tolkning"],
        "avvikelser": rad["avvikelser"],
        "antal_behandlingar": rad["antal_behandlingar"],
        "paragrafer": [rad["forsta_paragraf"], rad["sista_paragraf"]] if rad["forsta_paragraf"] is not None else None,
        "protokoll": {
            "dokument_id": rad["dokument_id"],
            "url": rad["dokument_url"],
            "kopia": f"/api/dokument/{rad['dokument_id']}",
            "filnamn": rad["filnamn"],
            "typ": rad["dokument_typ"],
            "version": rad["dokument_version"],
            "sha256": rad["sha256"],
            "storlek": rad["storlek"],
            "hamtad": rad["hamtad"],
            "tolkad": rad["tolkad"],
            "datakalla": {"id": rad["datakalla_id"], "titel": rad["datakalla_titel"]},
        },
    }


def lista_sammantraden(conn: psycopg.Connection, organ: str | None = None, ar: int | None = None) -> list[dict]:
    rader = conn.execute(
        f"{_SAMMANTRADE} WHERE (%(organ)s::text IS NULL OR s.organ = %(organ)s) "
        "AND (%(ar)s::int IS NULL OR extract(year FROM s.datum) = %(ar)s) "
        "ORDER BY s.datum DESC NULLS LAST, s.starttid DESC NULLS LAST, s.id DESC",
        {"organ": organ, "ar": ar},
    ).fetchall()
    return [_sammantrade(r) for r in rader]


SOKTRAFFAR = 200


def sok_behandlingar(
    conn: psycopg.Connection, q: str, organ: str | None = None, ar: int | None = None
) -> dict:
    """Behandlingar vars rubrik eller diarienummer innehåller söktexten, senaste först."""
    monster = "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    rader = conn.execute(
        """
        SELECT b.paragraf, b.rubrik, b.diarienummer, s.id AS sammantrade_id, s.organ, s.datum, s.tolkning,
               count(*) OVER () AS antal
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        WHERE (b.rubrik ILIKE %(m)s OR EXISTS (SELECT 1 FROM unnest(b.diarienummer) dnr WHERE dnr ILIKE %(m)s))
          AND (%(organ)s::text IS NULL OR s.organ = %(organ)s)
          AND (%(ar)s::int IS NULL OR extract(year FROM s.datum) = %(ar)s)
        ORDER BY s.datum DESC NULLS LAST, s.id DESC, b.ordning
        LIMIT %(grans)s
        """,
        {"m": monster, "organ": organ, "ar": ar, "grans": SOKTRAFFAR},
    ).fetchall()
    return {
        "antal": rader[0]["antal"] if rader else 0,
        "traffar": [
            {
                "paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"],
                "sammantrade": {
                    "id": r["sammantrade_id"], "datum": r["datum"], "tolkning": r["tolkning"],
                    "organ": {"id": r["organ"], "namn": ORGAN[r["organ"]].namn if r["organ"] in ORGAN else r["organ"]},
                },
            }
            for r in rader
        ],
    }


def _narvaro(rader: list[dict]) -> list[Narvaro]:
    return [Narvaro(namn=r["namn"], parti=r["parti"], roll=r["roll"], kategori=r["kategori"],
                    tjanstgor_for=r["tjanstgor_for"], tjanstgor_for_parti=r["tjanstgor_for_parti"],
                    paragrafer=r["paragrafer"], jav=r["jav"]) for r in rader]


def _person(n: Narvaro, personer: dict[str, int]) -> dict:
    return {
        "ledamot_id": personer.get(n.namn) if n.kategori != "ovrig" else None,
        "namn": n.namn, "parti": n.parti, "roll": n.roll, "kategori": n.kategori,
        "tjanstgor_for": {"namn": n.tjanstgor_for, "parti": n.tjanstgor_for_parti} if n.tjanstgor_for else None,
        "paragrafer": n.paragrafer, "jav": n.jav,
    }


def _las_narvaro(conn: psycopg.Connection, sammantrade_id: int) -> list[Narvaro]:
    return _narvaro(conn.execute(
        "SELECT * FROM narvaro WHERE sammantrade_id = %s ORDER BY ordning", (sammantrade_id,)).fetchall())


def _behandling(r: dict) -> dict:
    ut = {"paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"], "beslut": r["beslut"]}
    for k in ("antal_voteringar", "antal_reservationer"):
        if k in r:
            ut[k] = r[k]
    return ut


def las_sammantrade(conn: psycopg.Connection, sammantrade_id: int) -> dict | None:
    rad = conn.execute(f"{_SAMMANTRADE} WHERE s.id = %s", (sammantrade_id,)).fetchone()
    if rad is None:
        return None
    behandlingar = conn.execute(
        """
        SELECT b.*, (SELECT count(*) FROM votering v WHERE v.behandling_id = b.id) AS antal_voteringar,
               (SELECT count(*) FROM reservation r WHERE r.behandling_id = b.id) AS antal_reservationer
        FROM behandling b WHERE b.sammantrade_id = %s ORDER BY b.ordning
        """,
        (sammantrade_id,),
    ).fetchall()
    narvaro = _las_narvaro(conn, sammantrade_id)
    personer = ledamoter.personer_for(conn, (n.namn for n in narvaro))
    pub = Publicerade(conn, [sammantrade_id])
    return _sammantrade(rad) | {
        "narvaro": partier.fyll_i(conn, sammantrade_id, [pub.person(sammantrade_id, _person(n, personer)) for n in narvaro]),
        "behandlingar": [pub.behandling(sammantrade_id, _behandling(b)) for b in behandlingar],
    }


def las_behandling(conn: psycopg.Connection, sammantrade_id: int, paragraf: int) -> dict | None:
    rad = conn.execute(f"{_SAMMANTRADE} WHERE s.id = %s", (sammantrade_id,)).fetchone()
    if rad is None:
        return None
    b = conn.execute(
        "SELECT * FROM behandling WHERE sammantrade_id = %s AND paragraf = %s ORDER BY ordning LIMIT 1",
        (sammantrade_id, paragraf),
    ).fetchone()
    if b is None:
        return None
    grannar = conn.execute(
        """
        SELECT (SELECT max(paragraf) FROM behandling WHERE sammantrade_id = %(s)s AND paragraf < %(p)s) AS foregaende,
               (SELECT min(paragraf) FROM behandling WHERE sammantrade_id = %(s)s AND paragraf > %(p)s) AS nasta
        """,
        {"s": sammantrade_id, "p": paragraf},
    ).fetchone()
    narvaro = _las_narvaro(conn, sammantrade_id)
    personer = ledamoter.personer_for(conn, (n.namn for n in narvaro))
    # Publicerade rättelser läggs på tolkningen (rattelser.py).
    pub = Publicerade(conn, [sammantrade_id])
    return pub.behandling(sammantrade_id, _behandling(b)) | _yrkanden_och_voteringar(conn, b, pub) | {
        "sammantrade": _sammantrade(rad),
        "beslutande": partier.fyll_i(conn, sammantrade_id, [pub.person(sammantrade_id, _person(n, personer))
                                                            for n in beslutande_vid(narvaro, paragraf)]),
        "jav": partier.fyll_i(conn, sammantrade_id, [pub.person(sammantrade_id, _person(n, personer))
                                                     for n in narvaro if paragraf in n.jav]),
        "arende": arenden.arende_for(conn, sammantrade_id, paragraf),
        "foregaende": grannar["foregaende"],
        "nasta": grannar["nasta"],
    }


def _partiordning(parti: str | None) -> tuple:
    # Alfabetiskt efter förkortning (design.md), partilös och okänt parti sist.
    return (parti is None, parti == "-", parti or "")


def _yrkanden_och_voteringar(conn: psycopg.Connection, b: dict, pub: Publicerade) -> dict:
    yrkanden = conn.execute(
        "SELECT text, personer FROM yrkande WHERE behandling_id = %s ORDER BY ordning", (b["id"],)).fetchall()
    reservationer = conn.execute(
        "SELECT text, personer, partier FROM reservation WHERE behandling_id = %s ORDER BY ordning", (b["id"],)
    ).fetchall()
    voteringar = conn.execute("SELECT * FROM votering WHERE behandling_id = %s ORDER BY ordning", (b["id"],)).fetchall()
    roster = conn.execute(
        """
        SELECT r.* FROM rost r JOIN votering v ON v.id = r.votering_id
        WHERE v.behandling_id = %s ORDER BY r.votering_id, r.ordning
        """,
        (b["id"],),
    ).fetchall()
    namn = [n for r in roster for n in (r["namn"], r["ersatt"]) if n]
    namn += [p["namn"] for y in [*yrkanden, *reservationer] for p in y["personer"]]
    personer = ledamoter.personer_for(conn, namn)

    def med_id(p: dict) -> dict:
        return p | {"ledamot_id": personer.get(p["namn"])}

    ut_voteringar = []
    for v in voteringar:
        vr = [pub.rost(b["sammantrade_id"], b["paragraf"], v["ordning"] + 1, dict(r))
              for r in roster if r["votering_id"] == v["id"]]
        per_parti: dict[str | None, dict[str, int]] = {}
        for r in vr:
            per_parti.setdefault(r["parti"], {"ja": 0, "nej": 0, "avstar": 0, "franvarande": 0})[r["rost"]] += 1
        ut_voteringar.append({
            "nummer": v["ordning"] + 1,
            "ja_forslag": v["ja_forslag"], "nej_forslag": v["nej_forslag"],
            # Siffrorna som protokollets text anger, och siffrorna i voteringslistan.
            "angivet": {"ja": v["ja"], "nej": v["nej"], "avstar": v["avstar"], "franvarande": v["franvarande"]},
            "lista": {k: sum(1 for r in vr if r["rost"] == k) for k in ("ja", "nej", "avstar", "franvarande")},
            "resultat": v["resultat"],
            "vinnare": v["vinnare"],
            "roster": [
                {"namn": r["namn"], "parti": r["parti"], "rost": r["rost"], "rattelser": r.get("rattelser"),
                 "ledamot_id": personer.get(r["namn"]) if r["namn"] else None,
                 "ersatt": {"namn": r["ersatt"], "parti": r["ersatt_parti"], "ledamot_id": personer.get(r["ersatt"])}
                 if r["ersatt"] else None}
                for r in vr
            ],
            "per_parti": [{"parti": p} | antal for p, antal in sorted(per_parti.items(), key=lambda x: _partiordning(x[0]))],
        })
    return {
        "yrkanden": [{"text": y["text"], "personer": [med_id(p) for p in y["personer"]]} for y in yrkanden],
        "propositionsordning": b["propositionsordning"],
        "voteringar": ut_voteringar,
        "reservationer": [
            {"text": r["text"], "personer": [med_id(p) for p in r["personer"]], "partier": r["partier"]}
            for r in reservationer
        ],
    }


def las_dokument(conn: psycopg.Connection, dokument_id: int) -> dict | None:
    return conn.execute(
        "SELECT filnamn, innehall, sha256 FROM dokument WHERE id = %s", (dokument_id,)).fetchone()
