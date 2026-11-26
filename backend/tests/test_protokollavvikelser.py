"""Protokollavvikelser att anmäla till kommunen (#47).

Söm 1: varje kontroll mot ett verkligt protokoll med felet (inspelade protokoll, bekräftade mot PDF:en).
Söm 2: redaktören sätter status via API:t och utgivaren ser den, också efter omtolkning. Listan är redaktionens
verktyg och visas inte för läsare (#160). Insamlingen körs mot
kommunfullmäktiges protokoll för 2026, som i test_rattelser.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from pypdf import PdfReader, PdfWriter
from test_rattelser import api, logga_in, sammantrade_id  # noqa: F401

from app import db
from app.protokoll import tolka_om
from app.protokolltolkning import tolka

INSPELADE = Path(__file__).parent / "recordings" / "harnosand"


def inspelat(slut: str) -> bytes:
    [fil] = INSPELADE.glob(f"*{slut}")
    return fil.read_bytes()


def fynd(pdf: bytes, typ: str) -> list[tuple]:
    return [(f.paragraf, f.sida, f.text) for f in tolka(pdf).kontroller if f.typ == typ]


# Söm 1: kontrollerna mot verkliga protokoll


def test_parti_saknas_for_alla_i_kf_2026_10_26():
    # Närvarolistan i protokollet kl. 11.00 anger inget parti för någon. Det är ett fel i källan: PDF:en har
    # inga partier i närvarolistan, varken i textlagret eller i bilden av sidan.
    assert fynd(inspelat("2026_10_26_Protokoll_1100.pdf"), "parti_saknas") == [
        (None, 1, "Närvarolistan anger inget parti för någon av de 59 beslutande och ersättarna.")]


def test_parti_saknas_for_en_person():
    [(paragraf, sida, text)] = fynd(inspelat("Protokoll_kommunfullm_ktige_2026_04_27.pdf"), "parti_saknas")
    assert (paragraf, sida, text) == (None, 1, "Närvarolistan anger inget parti för Lotta Visén.")


def test_ersattare_for_en_beslutande_ledamot():
    # Kl. 13.15: Ingemar Ljunggren står som ledamot utan begränsning, och Ted Sundin "ersätter Ingemar
    # Ljunggren §152".
    assert (152, 11, "Ted Sundin tjänstgör för Ingemar Ljunggren, som själv står som beslutande vid § 152.") in \
        fynd(inspelat("2026_10_26_Protokoll_1315.pdf"), "ersattare")


def test_ersattare_nar_ledamoten_bara_var_med_en_del_av_motet_raknas_inte():
    # "Agneta Jonsson (S) kl. 09.15 – 14.25": ersättaren kan ha tjänstgjort före kl. 09.15.
    assert fynd(inspelat("Socialn_mnden_2023_02_23.pdf"), "ersattare") == []
    # Tabellen "Johan Nilsson | Anne-Cathrine Genberg §§ 19-23 | §§ 24-47" läses inte rätt av tolkningen.
    assert fynd(inspelat("Protokoll_kommunfullm_ktige_2023_03_27.pdf"), "ersattare") == []


def test_olika_parti_i_narvarolistan_och_voteringslistan():
    # Nikolaus Blomqvist (SD) på sidan 1 och (M) i voteringslistan på sidan 7.
    assert fynd(inspelat("Protokoll_skoln_mnd_2025_02_06.pdf"), "parti_olika") == [
        (4, 7, "Nikolaus Blomqvist står som (SD) i närvarolistan och som (M) i voteringslistan vid § 4.")]


def test_rosterna_stammer_inte_med_antalet_beslutande():
    assert fynd(inspelat("Protokoll_kommunfullm_ktige_2024_03_25.pdf"), "rostsumma") == [
        (25, 14, "§ 25, votering 1: rösterna är 28 ja, 12 nej och 1 avstår, sammanlagt 41. "
                 "Närvarolistan anger 42 beslutande vid paragrafen.")]


def test_samma_person_stavas_olika():
    assert fynd(inspelat("Protokoll_kommunfullm_ktige_2023_02_27.pdf"), "stavning") == [
        (6, 2, 'Namnet står som "Monika Israelsson" i närvarolistan och som "Monica Israelsson" vid § 6.')]


def test_paragrafnummer_som_saknas():
    # Inget av de 253 protokollen på plattformen (november 2026) har en paragraf som saknas eller förekommer två
    # gånger. Kontrollen prövas därför mot ett verkligt protokoll där en paragrafs sida har tagits bort.
    pdf = inspelat("Protokoll_kommunfullm_ktige_2026_03_23.pdf")
    t = tolka(pdf)
    assert fynd(pdf, "paragrafnummer") == []
    # En paragraf på en egen sida, med en paragraf före och efter.
    b = next(b for f, b, e in zip(t.behandlingar, t.behandlingar[1:], t.behandlingar[2:])
             if b.sida == f.sida + 1 and e.sida == b.sida + 1)
    lasare, skrivare = PdfReader(io.BytesIO(pdf)), PdfWriter()
    for i, sida in enumerate(lasare.pages):
        if i != b.sida - 1:
            skrivare.add_page(sida)
    ut = io.BytesIO()
    skrivare.write(ut)
    [(paragraf, _, text)] = fynd(ut.getvalue(), "paragrafnummer")
    assert paragraf == b.paragraf
    assert text == (f"§ {b.paragraf} finns inte i protokollet. Paragraferna går från § {b.paragraf - 1} till "
                    f"§ {b.paragraf + 1}, fast försättsbladet anger att protokollet omfattar paragrafen.")


def test_paragraf_som_protokollet_sjalvt_utesluter_raknas_inte():
    # Samhällsnämnden 2026-06-17: "Paragrafer 78 – 88, 90-93". § 89 justerades omedelbart i ett eget protokoll.
    pdf = (Path(__file__).parent / "fixtures" / "protokoll" / "sam-2026-06-17-urval.pdf").read_bytes()
    assert 89 not in [p for p, _, _ in fynd(pdf, "paragrafnummer")]


# Söm 2: status sätts av redaktören och läsaren ser den


def protokoll(api, s: int, **filter) -> dict | None:
    if api.get("/api/auth/jag").status_code == 401:  # Listan är bara för redaktionen.
        logga_in(api, "utgivare")
    svar = api.get("/api/protokollavvikelser", params={"fran": 2026, "till": 2026} | filter)
    assert svar.status_code == 200, svar.text
    return next((x for x in svar.json()["sammantraden"] if x["sammantrade"]["id"] == s), None)


def test_redaktoren_markerar_en_avvikelse_som_anmald_och_utgivaren_ser_statusen(api, database_url):
    [s] = [x["id"] for x in api.get("/api/sammantraden?organ=KF").json()
           if x["datum"] == "2026-10-26" and x["starttid"] == "11:10"]
    p = protokoll(api, s)
    [a] = p["avvikelser"]
    assert (a["typ"], a["status"], a["sida"], a["hittas"]) == ("parti_saknas", "ny", 1, True)
    assert a["lank"].endswith("#page=1")
    assert p["sammantrade"]["organ"]["namn"] == "Kommunfullmäktige"

    # Sammanställningen att skicka till nämndsekreteraren.
    assert p["sammanstallning"].startswith("Protokoll: Kommunfullmäktige 2026-10-26\nhttps://")
    assert "1. sidan 1: Närvarolistan anger inget parti för någon av de 59 beslutande och ersättarna." in \
        p["sammanstallning"]

    # Bara en redaktör sätter status.
    status = {"status": "anmald", "datum": "2026-11-20", "anteckning": "Skickat till nämndsekreteraren."}
    logga_in(api, None)
    assert api.post(f"/api/protokollavvikelser/{a['id']}/status", json=status).status_code == 401
    logga_in(api, "utgivare")
    assert api.post(f"/api/protokollavvikelser/{a['id']}/status", json=status).status_code == 403
    logga_in(api, "redaktor")
    assert api.post(f"/api/protokollavvikelser/{a['id']}/status", json={"status": "okand"}).status_code == 422
    svar = api.post(f"/api/protokollavvikelser/{a['id']}/status", json=status)
    assert svar.status_code == 200, svar.text
    assert svar.json()["statusnamn"] == "Anmäld till kommunen"

    # Utgivaren ser statusen med datum och anteckning.
    logga_in(api, "utgivare")
    [a] = protokoll(api, s)["avvikelser"]
    assert (a["status"], a["statusdatum"], a["anteckning"]) == ("anmald", "2026-11-20", "Skickat till nämndsekreteraren.")
    assert protokoll(api, s, status="anmald") is not None
    assert protokoll(api, s, status="ny") is None
    assert protokoll(api, s, typ="stavning") is None

    # Statusen bevaras vid omtolkning.
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
        conn.commit()
    [a] = protokoll(api, s)["avvikelser"]
    assert (a["status"], a["hittas"]) == ("anmald", True)
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM protokollavvikelse_status").fetchone()[0] == 1


def test_listan_visas_bara_for_redaktionen(api):
    # Läsning är öppen utan inloggning, men inte Att anmäla.
    assert api.get("/api/sammantraden?organ=KF").status_code == 200
    assert api.get("/api/protokollavvikelser").status_code == 401
    logga_in(api, "lasare")
    assert api.get("/api/protokollavvikelser").status_code == 403
    for roll in ("redaktor", "utgivare"):
        logga_in(api, roll)
        assert api.get("/api/protokollavvikelser").status_code == 200


def test_inte_ett_fel_tas_inte_med_i_sammanstallningen(api):
    [s] = [x["id"] for x in api.get("/api/sammantraden?organ=KF").json()
           if x["datum"] == "2026-10-26" and x["starttid"] == "13:15"]
    p = protokoll(api, s)
    ersattare = [a for a in p["avvikelser"] if a["typ"] == "ersattare"]
    assert ersattare and all(f"sidan {a['sida']}: {a['text']}" in p["sammanstallning"] for a in ersattare)
    logga_in(api, "redaktor")
    assert api.post(f"/api/protokollavvikelser/{ersattare[0]['id']}/status",
                    json={"status": "inte_fel", "anteckning": "Ledamoten lämnade före § 152."}).status_code == 200
    p = protokoll(api, s)
    assert ersattare[0]["text"] not in p["sammanstallning"]


def test_avvikelse_som_kommunen_rattat_i_ny_version_markeras_reviderad(api, database_url):
    [s] = [x["id"] for x in api.get("/api/sammantraden?organ=KF").json()
           if x["datum"] == "2026-10-26" and x["starttid"] == "11:10"]
    [a] = protokoll(api, s)["avvikelser"]
    with psycopg.connect(database_url) as conn:
        # Kommunen publicerar protokollet på nytt under samma adress, och där anges partierna.
        conn.execute(
            """
            INSERT INTO dokument (datakalla_id, url, version, filnamn, typ, organ, sha256, storlek, innehall, hamtad,
                                  korning_id)
            SELECT datakalla_id, url, version + 1, filnamn, typ, organ, 'ny', storlek, innehall, now(), korning_id
            FROM dokument WHERE id = (SELECT dokument_id FROM sammantrade WHERE id = %s)
            """,
            (s,),
        )
    from app import protokollavvikelser

    with db.connect(database_url) as conn:
        ny = conn.execute("SELECT max(id) AS id FROM dokument").fetchone()["id"]
        conn.execute("UPDATE sammantrade SET dokument_id = %s WHERE id = %s", (ny, s))
        protokollavvikelser.lagra(conn, s, ny, "protokoll", [], datetime.now(timezone.utc))
        conn.commit()
    [a] = protokoll(api, s)["avvikelser"]
    assert a["hittas"] is False and a["reviderad"] is not None
    assert protokoll(api, s)["sammanstallning"] == ""
