"""Rubriker som fått med paragraftext eller inte hela rubriken, avgränsade med ärendelistan (#124).

Fixturerna är verkliga protokoll:
- `skol-2026-09-03-urval.pdf`: försättsbladet, ärendelistan, § 75 och § 77 ur skolnämndens protokoll 2026-09-03.
  Paragraferna har underrubriken "Beslut", som tidigare lades till rubriken.
- `skol-2025-12-18-urval.pdf`: § 128 "Delgivningar" har ingen underrubrik och inget beslut, bara texten
  "Inga inkomna delgivningar till denna nämnd. ______".
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app import db
from app.protokolltolkning import tolka
from test_lasordning_och_arendelista import BESLUT, sida, tolkning
from test_rattelser import api, behandling, sammantrade_id  # noqa: F401

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def test_rubriken_beslut_avslutar_paragrafens_rubrik():
    t = tolka((FIXTURER / "skol-2026-09-03-urval.pdf").read_bytes())
    per_nr = {b.paragraf: b for b in t.behandlingar}
    assert per_nr[75].rubrik == "Budgetuppföljning juli 2026"
    assert per_nr[75].beslut.startswith("Skolnämnden beslutar\natt godkänna budgetuppföljningen för juli 2026.")
    assert per_nr[77].rubrik == "Eventuellt tillkommande ärende"
    assert per_nr[77].beslut == "Skolnämnden beslutar\natt lägga ärendet till handlingarna."
    assert per_nr[77].paragraftext is None
    # § 75 heter något annat i ärendelistan. Det står så i protokollet, och avvikelsen står kvar.
    assert [a for a in t.avvikelser if a.startswith("§")] == [
        '§ 75: rubriken skiljer sig från ärendelistan i protokollet: "Budgetuppföljning juli 2026" i paragrafen, '
        '"Budgetuppföljning skolnämnden 2026" i ärendelistan']


def test_paragraf_utan_beslut_far_arendelistans_rubrik_och_behaller_texten():
    t = tolka((FIXTURER / "skol-2025-12-18-urval.pdf").read_bytes())
    b = next(b for b in t.behandlingar if b.paragraf == 128)
    assert (b.rubrik, b.beslut, b.rubrik_ur_arendelistan) == ("Delgivningar", None, False)
    assert b.paragraftext == "Inga inkomna delgivningar till denna nämnd."
    assert not any(a.startswith("§ 128") for a in t.avvikelser)


LISTA = ["§ 1 Allmänhetens frågestund i kommunfullmäktige 2022 3"]


def test_paragraftext_avgransas_pa_radgrans():
    t = tolkning((sida(3, "§ 1", "Allmänhetens frågestund i", "kommunfullmäktige 2022",
                       "Inga frågor har inkommit till dagens", "frågestund.", "______"), None), lista=LISTA)
    [b] = t.behandlingar
    assert b.rubrik == "Allmänhetens frågestund i kommunfullmäktige 2022"
    assert b.paragraftext == "Inga frågor har inkommit till dagens frågestund."
    assert b.beslut is None
    assert t.avvikelser == []


def test_rubrik_som_inte_stammer_pa_en_radgrans_andras_inte():
    # Ärendelistans rubrik slutar mitt på en rad i paragrafen.
    rader = ("§ 1", "Allmänhetens frågestund i kommunfullmäktige 2022 Inga frågor", "har inkommit.")
    t = tolkning((sida(3, *rader), None), lista=LISTA)
    [b] = t.behandlingar
    assert b.rubrik == "Allmänhetens frågestund i kommunfullmäktige 2022 Inga frågor har inkommit."
    assert b.paragraftext is None
    assert "rubriken är längre än i ärendelistan" in t.avvikelser[0]


def test_rubrik_foljd_av_underrubrik_andras_inte():
    # Paragrafens rubrik har ett ord mer än ärendelistans, och beslutet följer: protokollets egen rubrik.
    t = tolkning((sida(3, "§ 1", "Fastställande av föredragningslista", "2026", *BESLUT), None),
                 lista=["§ 1 Fastställande av föredragningslista 3"])
    [b] = t.behandlingar
    assert (b.rubrik, b.paragraftext) == ("Fastställande av föredragningslista 2026", None)
    assert b.beslut == "att godkänna."
    assert "rubriken är längre än i ärendelistan" in t.avvikelser[0]


def test_kortare_rubrik_fullbordas_med_nasta_rad():
    # Fyra rader utan underrubrik: tidigare blev bara första raden rubrik.
    rader = ("§ 1", "Permutering av Mellersta Norrlands", "Pensionsstiftelse", "Stiftelsen har ansökt",
             "om permutation.", "Ärendet", *BESLUT)
    t = tolkning((sida(3, *rader), None), lista=["§ 1 Permutering av Mellersta Norrlands Pensionsstiftelse 3"])
    [b] = t.behandlingar
    assert b.rubrik == "Permutering av Mellersta Norrlands Pensionsstiftelse"
    assert b.beslut == "att godkänna."
    assert b.paragraftext is None  # paragrafen har en underrubrik och ett beslut
    assert t.avvikelser == []
    # Nästa rad fullbordar den inte: rubriken ändras inte.
    t = tolkning((sida(3, *rader), None), lista=["§ 1 Permutering av Mellersta Norrlands pensionsstiftelser 3"])
    assert t.behandlingar[0].rubrik == "Permutering av Mellersta Norrlands"
    assert "kortare än i ärendelistan" in t.avvikelser[0]


def test_utan_arendelista_andras_inget():
    t = tolkning((sida(3, "§ 1", "Delgivningar", "Inga delgivningar.", "______"), None))
    [b] = t.behandlingar
    assert (b.rubrik, b.paragraftext) == ("Delgivningar Inga delgivningar. ______", None)


def test_paragraftexten_sparas_och_visas(api, database_url, monkeypatch):  # noqa: F811
    from app import protokoll
    from app.protokoll import tolka_om

    s = sammantrade_id(api, "2026-06-15")
    paragraf = behandling(api, "2026-06-15", 109)["paragraf"]
    riktig = protokoll.tolka

    def med_text(pdf: bytes):
        t = riktig(pdf)
        for b in t.behandlingar:
            if b.paragraf == paragraf:
                b.beslut, b.paragraftext = None, "Inga frågor har inkommit."
        return t

    monkeypatch.setattr(protokoll, "tolka", med_text)
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))

    [rad] = [b for b in api.get(f"/api/sammantraden/{s}").json()["behandlingar"] if b["paragraf"] == paragraf]
    assert rad["paragraftext"] == "Inga frågor har inkommit."
    assert behandling(api, "2026-06-15", paragraf)["paragraftext"] == "Inga frågor har inkommit."
    assert "paragraftext" not in behandling(api, "2026-06-15", paragraf + 1)


def test_beslutet_under_rubriken_beslut():
    # Som KS 2026-09-29 § 141: ett förslag till fullmäktige och styrelsens eget beslut under samma rubrik.
    t = tolkning((sida(3, "§ 1", "Delårsrapport 2026", "Beslut",
                       "Kommunstyrelsen föreslå kommunfullmäktige besluta", "att godkänna delårsrapporten.",
                       "Kommunstyrelsen beslutar", "att överlämna delårsrapporten till revisionen.",
                       "Sammanfattning", "Delårsrapporten visar ett underskott."), None))
    [b] = t.behandlingar
    assert b.rubrik == "Delårsrapport 2026"
    assert b.beslut == ("Kommunstyrelsen föreslå kommunfullmäktige besluta\natt godkänna delårsrapporten.\n"
                        "Kommunstyrelsen beslutar\natt överlämna delårsrapporten till revisionen.")
    # Bara ett förslag, som SKOL 2026-09-03 § 95: förut hittades inget beslut.
    t = tolkning((sida(3, "§ 1", "Anpassning av Brännaskolan", "Beslut",
                       "Skolnämnden föreslår kommunstyrelsen föreslå kommunfullmäktige besluta",
                       "att ärendet remitteras åter till förvaltningen.", "Yrkanden", "Ingen yrkar."), None))
    assert t.behandlingar[0].beslut == ("Skolnämnden föreslår kommunstyrelsen föreslå kommunfullmäktige besluta\n"
                                        "att ärendet remitteras åter till förvaltningen.")
