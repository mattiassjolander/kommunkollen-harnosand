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


def test_hanvisningar_till_protokollsutdrag_i_beslutsunderlaget():
    from app.protokolltolkning import hanvisningar

    text = "\n".join([
        "• Tjänsteskrivelse 2026-05-10",
        "• Protokollsutdrag samhällsnämnden 20260521 §61",
        "• Socialnämndens protokollsutdrag, 2023-01-26 § 5",
        "• Protokollsutdrag KS 2024- 06- 04 § 112",
        "• Protokollsutdrag 2023 -05-22 § 7",
        "Kommunfullmäktige Kramfors kommun protokollsutdrag 2026-03-30 § 12",
        "• Protokollsutdrag kommunstyrelsen 2026-02-30 § 3",
    ])
    assert [(h.organ, h.datum.isoformat(), h.paragraf) for h in hanvisningar(text)] == [
        ("SAM", "2026-05-21", 61),
        ("SOC", "2023-01-26", 5),
        ("KS", "2024-06-04", 112),
        (None, "2023-05-22", 7),  # utan organ, men inleder en punkt
    ]
    assert hanvisningar(text)[0].text == "Protokollsutdrag samhällsnämnden 20260521 §61"


def test_paragrafer_i_namnkolumnen_ar_paragraferna_personen_deltog_i():
    # KF 2024-05-27: "Andreas Sjölander §§ 57-61, 63-68, 70-76". Han var inte med vid § 62 och § 69.
    t = tolkning("kf-2024-05-27-urval.pdf")
    andreas = [n for n in t.narvaro if n.namn == "Andreas Sjölander"]
    assert len(andreas) == 1
    assert andreas[0].kategori == "beslutande"
    assert 62 not in andreas[0].paragrafer and 69 not in andreas[0].paragrafer
    assert andreas[0].paragrafer[:5] == [57, 58, 59, 60, 61]
    assert not any("§" in n.namn for n in t.narvaro)


def test_namnfalt_med_roll_paragrafer_och_radbrutna_ersattningar():
    # KS 2026-09-29: en kolumn utan parti, där "Namn, ersätter Annan §§ …" bryts över flera rader.
    t = tolkning("ks-2026-09-29-forsta-sidan.pdf")
    poster = {(n.namn, n.tjanstgor_for): n for n in t.narvaro}
    assert ("Britta Thyr", None) in poster and poster[("Britta Thyr", None)].roll == "1:e vice ordförande"
    assert 139 not in poster[("Glenn Sehlin", None)].paragrafer
    assert poster[("Monica Fällström", "Magnus Oskarsson")].paragrafer[-1] == 143
    assert poster[("Hans Rosengren", "Ann Kristine Elfvendal")].paragrafer == [138]
    assert poster[("Hans Rosengren", "Monica Fällström")].paragrafer == [139]
    assert poster[("Ulrika Jonsson", "Glenn Sehlin")].paragrafer == [139]
    assert not any("§" in n.namn or "," in n.namn or "ersätter" in n.namn for n in t.narvaro)
