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

from . import (arenden, avvikelser, ledamoter, markningar, partier, protokollavvikelser, protokollgranskning,
               protokollsammanstallning, kalender, sammantradesplan)
from .kallelsepunkter import Kallelsenummer, efter_rattelser
from .partitillhorighet import Gallande
from .rattelser import Publicerade
from .protokolltolkning import Behandling, Narvaro, Tolkning, beslutande_i, beslutande_vid, tolka
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
    # Ett protokoll för ett planerat sammanträde kopplas till det i stället för att skapa ett nytt.
    if not conn.execute("SELECT 1 FROM sammantrade WHERE organ = %s AND nyckel = %s", (d.organ, nyckel)).fetchone():
        if (planerat := sammantradesplan.planerat_for_protokoll(conn, d.organ, datum, t.starttid)) is not None:
            conn.execute("UPDATE sammantrade SET nyckel = %s WHERE id = %s", (nyckel, planerat))
    sammantrade_id = conn.execute(
        """
        INSERT INTO sammantrade (organ, nyckel, datum, starttid, sluttid, plats, dokument_id, tolkning, avvikelser, tolkad,
                                 ocr)
        VALUES (%(organ)s, %(nyckel)s, %(datum)s, %(starttid)s, %(sluttid)s, %(plats)s, %(dokument_id)s,
                %(tolkning)s, %(avvikelser)s, %(tolkad)s, %(ocr)s)
        ON CONFLICT (organ, nyckel) DO UPDATE SET
            datum = EXCLUDED.datum, starttid = EXCLUDED.starttid, sluttid = EXCLUDED.sluttid, plats = EXCLUDED.plats,
            dokument_id = EXCLUDED.dokument_id, tolkning = EXCLUDED.tolkning, avvikelser = EXCLUDED.avvikelser,
            tolkad = EXCLUDED.tolkad, ocr = EXCLUDED.ocr
        RETURNING id
        """,
        {"organ": d.organ, "nyckel": nyckel, "datum": datum, "starttid": t.starttid, "sluttid": t.sluttid,
         "plats": t.plats, "dokument_id": dokument_id, "tolkning": "tolkad" if t.tolkad else "ej_tolkad",
         "avvikelser": Jsonb(t.avvikelser), "tolkad": tolkad, "ocr": t.ocr},
    ).fetchone()["id"]
    # Planen kopplades kanske till dagens enda protokoll, och det här passar den bättre i tid (#107).
    sammantradesplan.koppla_om(conn, sammantrade_id)
    conn.execute("DELETE FROM narvaro WHERE sammantrade_id = %s", (sammantrade_id,))
    conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s", (sammantrade_id,))
    conn.execute("DELETE FROM sittning WHERE sammantrade_id = %s", (sammantrade_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO sittning (sammantrade_id, ordning, plats, starttid, sluttid, paragrafer, delegation)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(sammantrade_id, i, x.plats, x.starttid, x.sluttid, x.paragrafer, x.delegation)
             for i, x in enumerate(t.sittningar)],
        )
        cur.executemany(
            """
            INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori, tjanstgor_for,
                                 tjanstgor_for_parti, paragrafer, jav, tom_plats)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(sammantrade_id, i, n.namn, n.parti, n.roll, n.kategori, n.tjanstgor_for, n.tjanstgor_for_parti,
              n.paragrafer, n.jav, n.tom_plats) for i, n in enumerate(t.narvaro)],
        )
    for i, b in enumerate(t.behandlingar):
        _lagra_behandling(conn, sammantrade_id, i, b)
    ledamoter.registrera(conn, (n.namn for n in t.narvaro if n.kategori != "ovrig"))
    protokollavvikelser.lagra(conn, sammantrade_id, dokument_id, d.typ, t.kontroller, tolkad)
    # En granskning upphör om tolkningen ändrade någon uppgift (#176).
    protokollgranskning.efter_tolkning(conn, sammantrade_id, tolkad)


def _lagra_behandling(conn: psycopg.Connection, sammantrade_id: int, ordning: int, b: Behandling) -> None:
    behandling_id = conn.execute(
        """
        INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, rubrik_ur_arendelistan, diarienummer, beslut,
                                paragraftext, propositionsordning, motionarer)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (sammantrade_id, ordning, b.paragraf, b.rubrik, b.rubrik_ur_arendelistan, b.diarienummer, b.beslut,
         b.paragraftext, b.propositionsordning, Jsonb([{"namn": n, "parti": p} for n, p in b.motionarer])),
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
    SELECT s.id, s.organ, s.datum, s.starttid, s.sluttid, s.plats, s.tolkning, s.avvikelser, s.kallelse_avvikelser,
           s.tolkad, s.ocr, d.id AS dokument_id, d.url AS dokument_url, d.filnamn, d.typ AS dokument_typ,
           d.version AS dokument_version,
           d.sha256, d.storlek, d.hamtad, d.datakalla_id, k.titel AS datakalla_titel,
           (SELECT count(*) FROM behandling b WHERE b.sammantrade_id = s.id) AS antal_behandlingar,
           (SELECT min(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS forsta_paragraf,
           (SELECT max(paragraf) FROM behandling b WHERE b.sammantrade_id = s.id) AS sista_paragraf,
           (SELECT count(*) FROM rattelse r WHERE r.sammantrade_id = s.id AND r.status = 'publicerad'
              AND r.felet_i = 'protokollet') AS felaktigheter,
           (SELECT g.granskad FROM protokollgranskning g
            WHERE g.sammantrade_id = s.id AND g.status = 'gallande') AS granskad
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
        # Protokollets avvikelser är strängar i databasen, kallelsens objekt med en länk (#121).
        "avvikelser": [avvikelser.objekt(a) for a in rad["avvikelser"] + rad["kallelse_avvikelser"]],
        "ocr": rad["ocr"],
        "antal_behandlingar": rad["antal_behandlingar"],
        "paragrafer": [rad["forsta_paragraf"], rad["sista_paragraf"]] if rad["forsta_paragraf"] is not None else None,
        # Publicerade rättelser av fel i själva protokollet (#74): protokollet "Innehåller felaktigheter".
        "felaktigheter": rad["felaktigheter"],
        # Datumet då redaktionen granskade protokollet (#176), eller None. Vem som granskade visas inte.
        "granskad": rad["granskad"].astimezone(kalender.TZ).date() if rad["granskad"] else None,
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
    # Den kompakta sammanställningen (#195), räknad för alla sammanträden på en gång.
    sammanstallningar = protokollsammanstallning.for_sammantraden(conn, rader, kompakta=True)
    return [_sammantrade(r) | {"sammanstallning": sammanstallningar[r["id"]]} for r in rader]


SOKTRAFFAR = 200


def sok_behandlingar(
    conn: psycopg.Connection, q: str, organ: str | None = None, ar: int | None = None
) -> dict:
    """Behandlingar vars rubrik eller diarienummer innehåller söktexten, senaste först."""
    monster = "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    rader = conn.execute(
        """
        SELECT b.paragraf, b.rubrik, d.diarienummer, d.ur_kallelsen, s.id AS sammantrade_id, s.organ, s.datum,
               s.tolkning, count(*) OVER () AS antal
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        LEFT JOIN kallelse_diarienummer kd ON kd.sammantrade_id = b.sammantrade_id AND kd.paragraf = b.paragraf
        -- Protokollets diarienummer, annars kallelsens (#109).
        CROSS JOIN LATERAL (SELECT CASE WHEN cardinality(b.diarienummer) = 0 AND kd.diarienummer IS NOT NULL
                                        THEN kd.diarienummer ELSE b.diarienummer END AS diarienummer,
                                   cardinality(b.diarienummer) = 0 AND kd.diarienummer IS NOT NULL AS ur_kallelsen) d
        WHERE (b.rubrik ILIKE %(m)s OR EXISTS (SELECT 1 FROM unnest(d.diarienummer) dnr WHERE dnr ILIKE %(m)s))
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
                "diarienummer_ur_kallelsen": r["ur_kallelsen"],
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
                    paragrafer=r["paragrafer"], jav=r["jav"], tom_plats=r["tom_plats"]) for r in rader]


def _person(n: Narvaro, personer: dict[str, int]) -> dict:
    return {
        "ledamot_id": personer.get(n.namn) if n.kategori != "ovrig" else None,
        "namn": n.namn, "parti": n.parti, "roll": n.roll, "kategori": n.kategori,
        "tjanstgor_for": {"namn": n.tjanstgor_for, "parti": n.tjanstgor_for_parti} if n.tjanstgor_for else None,
        "paragrafer": n.paragrafer, "jav": n.jav,
        **({"tom_plats": True} if n.tom_plats else {}),  # "Tom plats för Namn" (#165)
    }


def _las_narvaro(conn: psycopg.Connection, sammantrade_id: int) -> list[Narvaro]:
    return _narvaro(conn.execute(
        "SELECT * FROM narvaro WHERE sammantrade_id = %s ORDER BY ordning", (sammantrade_id,)).fetchall())


def _behandling(r: dict) -> dict:
    ut = {"paragraf": r["paragraf"], "rubrik": r["rubrik"], "diarienummer": r["diarienummer"], "beslut": r["beslut"]}
    if r.get("rubrik_ur_arendelistan"):
        ut["rubrik_ur_arendelistan"] = True
    if r.get("paragraftext"):
        ut["paragraftext"] = r["paragraftext"]
    for k in ("antal_voteringar", "antal_reservationer"):
        if k in r:
            ut[k] = r[k]
    return ut


def protokoll_for(conn: psycopg.Connection, sammantrade_ids: list[int]) -> dict[int, dict | None]:
    """Protokollet (originalet och plattformens kopia) per sammanträde, None för ett sammanträde utan protokoll."""
    return {r["id"]: _sammantrade(r)["protokoll"]
            for r in conn.execute(f"{_SAMMANTRADE} WHERE s.id = ANY(%s)", (list(sammantrade_ids),))}


def _las_sittningar(conn: psycopg.Connection, sammantrade_id: int) -> list[dict]:
    return conn.execute(
        "SELECT plats, starttid, sluttid, paragrafer, delegation FROM sittning WHERE sammantrade_id = %s ORDER BY ordning",
        (sammantrade_id,)).fetchall()


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
    kn = Kallelsenummer(conn, [sammantrade_id])
    gal = Gallande(conn, [x for n in narvaro for x in (n.namn, n.tjanstgor_for)])
    rattade = [efter_rattelser(pub.behandling(sammantrade_id, kn.satt(sammantrade_id, _behandling(b))))
               for b in behandlingar]
    _med_markningar(conn, sammantrade_id, behandlingar, rattade)
    return _sammantrade(rad) | {
        "narvaro": _med_parti(conn, sammantrade_id, rad["datum"], pub, gal, [_person(n, personer) for n in narvaro]),
        # Bara när protokollet har flera sittningar (#85): var och en med sina beslutande.
        "sittningar": [
            {"nummer": i + 1} | x | {"beslutande": _med_parti(
                conn, sammantrade_id, rad["datum"], pub, gal,
                [_person(n, personer) for n in beslutande_i(narvaro, x["paragrafer"])])}
            for i, x in enumerate(_las_sittningar(conn, sammantrade_id))
        ],
        "behandlingar": rattade,
        "sammanstallning": protokollsammanstallning.for_sammantraden(conn, [rad])[sammantrade_id],
    }


def _med_markningar(conn: psycopg.Connection, sammantrade_id: int, rader: list[dict], rattade: list[dict]) -> None:
    """Märkningarna (#162) på de rättade behandlingarna, räknade med de rättade besluten och typerna."""
    per = markningar.berakna(conn, [
        {"id": b["id"], "sammantrade_id": sammantrade_id, "paragraf": r["paragraf"], "beslut": r["beslut"],
         "typ": r.get("typ")} for b, r in zip(rader, rattade)])
    for b, r in zip(rader, rattade):
        r["markningar"] = per.get(b["id"], [])


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
    # Publicerade rättelser och fastställda partitillhörigheter läggs på tolkningen (rattelser.py,
    # partitillhorighet.py).
    pub = Publicerade(conn, [sammantrade_id])
    gal = Gallande(conn, [x for n in narvaro for x in (n.namn, n.tjanstgor_for)])
    behandling = efter_rattelser(pub.behandling(
        sammantrade_id, Kallelsenummer(conn, [sammantrade_id]).satt(sammantrade_id, _behandling(b))))
    _med_markningar(conn, sammantrade_id, [b], [behandling])
    return behandling | _yrkanden_och_voteringar(conn, b, pub, rad["datum"]) | {
        "sammantrade": _sammantrade(rad),
        "beslutande": _med_parti(conn, sammantrade_id, rad["datum"], pub, gal,
                                 [_person(n, personer) for n in beslutande_vid(narvaro, paragraf)]),
        "jav": _med_parti(conn, sammantrade_id, rad["datum"], pub, gal,
                          [_person(n, personer) for n in narvaro if paragraf in n.jav]),
        "arende": arenden.arende_for(conn, sammantrade_id, paragraf),
        # Sittningen paragrafen hör till, när protokollet har flera (#85).
        "sittning": next(({"nummer": i + 1} | x for i, x in enumerate(_las_sittningar(conn, sammantrade_id))
                          if paragraf in x["paragrafer"]), None),
        "foregaende": grannar["foregaende"],
        "nasta": grannar["nasta"],
    }


def _med_parti(conn: psycopg.Connection, sammantrade_id: int, datum, pub: Publicerade, gal: Gallande,
               personer: list[dict]) -> list[dict]:
    """Partiet för personerna i närvarolistan: rättelse, fastställd partitillhörighet, protokollet, härlett."""
    for p in personer:
        pub.person(sammantrade_id, p)
        if p["kategori"] != "ovrig":
            gal.satt(p, datum)
        gal.satt(p["tjanstgor_for"], datum)
    return partier.fyll_i(conn, sammantrade_id, personer)


def _partiordning(parti: str | None) -> tuple:
    # Alfabetiskt efter förkortning (design.md), partilös och okänt parti sist.
    return (parti is None, parti == "-", parti or "")


def _yrkanden_och_voteringar(conn: psycopg.Connection, b: dict, pub: Publicerade, datum=None) -> dict:
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
    gal = Gallande(conn, namn)

    def med_id(p: dict) -> dict:
        return gal.satt(dict(p), datum) | {"ledamot_id": personer.get(p["namn"])}

    ut_voteringar = []
    for v in voteringar:
        vr = [gal.satt(pub.rost(b["sammantrade_id"], b["paragraf"], v["ordning"] + 1, dict(r)), datum)
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
                 "partitillhorighet": r.get("partitillhorighet"),
                 "ledamot_id": personer.get(r["namn"]) if r["namn"] else None,
                 "ersatt": gal.satt({"namn": r["ersatt"], "parti": r["ersatt_parti"],
                                     "ledamot_id": personer.get(r["ersatt"])}, datum)
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
