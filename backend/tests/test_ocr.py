"""OCR för protokoll som bara innehåller bilder (#52).

Fixturen är ett urval av samhällsnämndens protokoll 2026-04-30, där varje sida är en bild:
första sidan, §§ 43–44 och sidorna med §§ 49 och 51 (vars paragraftecken är svåra att läsa).
Testerna som kör OCR hoppas över när Tesseract med svenska saknas. CI installerar det.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import ocr
from app.protokolltolkning import _tolka, tolka

FIXTUR = Path(__file__).parent / "fixtures" / "protokoll" / "sam-2026-04-30-bilder-urval.pdf"
# I CI är OCR ett krav (KRAV_OCR=1), så att testerna inte hoppas över utan att någon märker det.
if os.environ.get("KRAV_OCR") and not ocr.tillganglig():
    raise RuntimeError("KRAV_OCR är satt men Tesseract med svensk språkdata saknas")
kraver_ocr = pytest.mark.skipif(not ocr.tillganglig(), reason="Tesseract med svensk språkdata saknas")


@pytest.mark.parametrize(
    ("rad", "vantat"),
    [
        ("Charlotte Höglund Bystedt (SD) 8 45", "Charlotte Höglund Bystedt (SD) § 45"),
        ("Therese Arebratt (S) & 45", "Therese Arebratt (S) § 45"),
        ("8 43-44, 46-60", "§ 43-44, 46-60"),
        ("som $ 60, samt", "som § 60, samt"),
        ("Sekreterare Felicia Bring Caris Paragrafer 88 43 — 60", "Sekreterare Felicia Bring Caris Paragrafer §§ 43 – 60"),
        ("Paragrafer $8 43 — 60", "Paragrafer §§ 43 – 60"),
        # Paragrafrubriken på egen rad, med paragrafintervallet känt.
        ("843", "§ 43"),
        ("5849 SAM/2026-116", "§ 49 SAM/2026-116"),
        ("349 SAM/2026-116", "§ 49 SAM/2026-116"),
        ("851 SAM/2026-109", "§ 51 SAM/2026-109"),
        ("§ 50 SAM/2026-117", "§ 50 SAM/2026-117"),
        # Andra tal lämnas: utanför intervallet, eller inget tecken att ta bort.
        ("10", "10"),
        ("2026", "2026"),
        ("50", "50"),
    ],
)
def test_vanliga_lasfel_rattas(rad, vantat):
    assert ocr.ratta(rad, (43, 60)) == vantat


@pytest.mark.parametrize(
    ("text", "vantat"),
    [
        ("Sekreterare Felicia Bring Caris Paragrafer 88 43 — 60", (43, 60)),
        # Samhällsnämnden 2026-05-28: dubbelt bindestreck och 77 läst som "TT".
        ("Sekreterare Felicia Bring Caris Paragrafer 62 –- TT", (62, 77)),
        ("Paragrafer §§ 1-1O", (1, 10)),
        ("Paragrafer 62 – 12", None),
        ("Paragrafer 62", None),
    ],
)
def test_paragrafintervallet_lases_trots_lasfel(text, vantat):
    assert ocr.paragrafintervall(text) == vantat


def test_paragrafrubriker_rattas_inte_utan_kant_intervall():
    assert ocr.ratta("843") == "843"


@kraver_ocr
def test_protokoll_med_bara_bilder_tolkas_med_ocr():
    t = tolka(FIXTUR.read_bytes())
    assert t.ocr
    assert (str(t.datum), t.starttid) == ("2026-04-30", "08:15")
    assert [b.paragraf for b in t.behandlingar] == [43, 44, 49, 51]
    assert t.behandlingar[0].rubrik == "Val av justerare"
    assert "Christian Wasell (M)" in t.behandlingar[0].beslut
    assert t.behandlingar[2].diarienummer == ["SAM/2026-116"]
    # Närvaron från första sidan, med tjänstgöring och paragrafer.
    narvaro = {(n.namn, n.kategori): n for n in t.narvaro}
    assert narvaro[("Helena Elfvendal", "beslutande")].roll == "Ordförande"
    sehlin = narvaro[("Glenn Sehlin", "beslutande")]
    assert (sehlin.parti, sehlin.tjanstgor_for) == ("SD", "Charlotte Höglund Bystedt")
    assert 45 not in sehlin.paragrafer and 46 in sehlin.paragrafer
    assert narvaro[("Charlotte Höglund Bystedt", "beslutande")].paragrafer == [45]
    # Avvikelsen om saknad text står kvar, så att kommunen kan ombes publicera en PDF med text.
    assert "PDF:en saknar text och har lästs med OCR" in t.avvikelser


def test_utan_ocr_ar_protokollet_ej_tolkat(monkeypatch):
    monkeypatch.setattr(ocr, "tillganglig", lambda: False)
    t = _tolka.__wrapped__(FIXTUR.read_bytes())
    assert (t.tolkad, t.ocr, t.avvikelser) == (False, False, ["PDF:en saknar text (inskannad?)"])


@kraver_ocr
def test_sammantradet_markeras_som_last_med_ocr(database_url, google):
    from conftest import skapa_app
    from fastapi.testclient import TestClient
    from test_protokoll import kf, kor

    from app import db
    from app.protokoll import tolka_om

    api = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(api)
    [s] = [s for s in api.get("/api/sammantraden?organ=KF").json() if s["datum"] == "2026-02-23"]
    assert api.get(f"/api/sammantraden/{s['id']}").json()["ocr"] is False
    with db.connect(database_url) as conn:
        conn.execute(
            "UPDATE dokument SET innehall = %s WHERE id = (SELECT dokument_id FROM sammantrade WHERE id = %s)",
            (FIXTUR.read_bytes(), s["id"]),
        )
        tolka_om(conn, datetime.now(timezone.utc))
    [ocr_s] = [x for x in api.get("/api/sammantraden?organ=KF").json() if x["datum"] == "2026-04-30"]
    svar = api.get(f"/api/sammantraden/{ocr_s['id']}").json()
    assert (svar["ocr"], svar["tolkning"]) == (True, "tolkad")
    assert "PDF:en saknar text och har lästs med OCR" in svar["avvikelser"]
    avvikelser = api.get("/api/avvikelser").json()
    rad = next(x for x in avvikelser["sammantraden"] if x["sammantrade"]["id"] == ocr_s["id"])
    assert any(a["kategori"] == "ofullstandigt" for a in rad["avvikelser"])
