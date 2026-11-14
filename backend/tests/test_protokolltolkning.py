"""Tolkning av protokoll som inte gick att tolka vid den första insamlingen i november 2026.

PDF:erna i tests/fixtures/protokoll är kommunens egna. Skolnämndens protokoll är ett urval av
sidorna (kallelsen, protokollets början och slut, och början på protokollsutdraget efter det),
så att filen hålls liten.
"""

from pathlib import Path

from app.protokolltolkning import tolka

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def tolkning(namn: str):
    return tolka((FIXTURER / namn).read_bytes())


def test_diarienummer_som_textlagret_delat():
    # Textlagret skriver "§ 61 S AM/2026-131".
    t = tolkning("sam-2026-05-21.pdf")
    assert t.avvikelser == []
    assert [(b.paragraf, b.diarienummer) for b in t.behandlingar] == [(61, ["SAM/2026-131"])]
    assert t.behandlingar[0].rubrik == "Detaljplan för del av Fastlandet 2:64, beslut om godkännande"
    assert t.behandlingar[0].beslut.startswith("Samhällsnämnden beslutar")

    t = tolkning("sam-2026-06-17-par-89.pdf")
    assert [(b.paragraf, b.diarienummer) for b in t.behandlingar] == [(89, ["SAM/2026-146"])]


def test_kallelse_fore_och_protokollsutdrag_efter_protokollet_tolkas_inte():
    t = tolkning("skol-2025-12-18-urval.pdf")
    assert str(t.datum) == "2025-12-18"
    assert any(n.namn == "Nina Skyttberg" and n.parti == "S" for n in t.narvaro)
    # Utdraget efter protokollet (§ 104 och § 118 en gång till) räknas inte.
    assert [b.paragraf for b in t.behandlingar] == [115, 116, 128]
    assert "Samma paragraf förekommer flera gånger" not in t.avvikelser


def test_ofullstandig_pdf_sags_i_avvikelserna():
    # Kommunens fil har bara första sidan av protokollets 58.
    t = tolkning("sam-2022-06-16-forsta-sidan.pdf")
    assert str(t.datum) == "2022-06-16"
    assert "Inga behandlingar hittades" in t.avvikelser
    assert "PDF:en har 1 av protokollets 58 sidor" in t.avvikelser


def test_omtolkning_av_lagrade_protokoll_behaller_sammantradenas_id(database_url, google):
    # Som ett protokoll som inte gick att tolka med en tidigare tolkning.
    from datetime import datetime, timezone

    from conftest import skapa_app
    from fastapi.testclient import TestClient
    from test_protokoll import kf, kor

    from app import db
    from app.protokoll import tolka_om

    api = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(api)
    [s] = [s for s in api.get("/api/sammantraden?organ=KF").json() if s["datum"] == "2026-02-23"]
    fore = api.get(f"/api/sammantraden/{s['id']}").json()
    with db.connect(database_url) as conn:
        conn.execute(
            "UPDATE sammantrade SET nyckel = 'fil:x.pdf', tolkning = 'ej_tolkad', avvikelser = '[\"Inga behandlingar hittades\"]' WHERE id = %s",
            (s["id"],),
        )
        conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s", (s["id"],))
    assert api.get(f"/api/sammantraden/{s['id']}").json()["tolkning"] == "ej_tolkad"
    antal_sammantraden = len(api.get("/api/sammantraden").json())

    with db.connect(database_url) as conn:
        antal = tolka_om(conn, datetime.now(timezone.utc))
    assert (antal["nu_tolkade"], antal["nu_ej_tolkade"]) == (1, 0)

    efter = api.get(f"/api/sammantraden/{s['id']}").json()
    assert efter["tolkning"] == "tolkad"
    assert efter["behandlingar"] == fore["behandlingar"]
    assert efter["narvaro"] == fore["narvaro"]
    assert len(api.get("/api/sammantraden").json()) == antal_sammantraden
