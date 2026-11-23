"""Protokoll med flera sittningar samma dag (#85).

Kommunstyrelsens protokoll 2022-01-18 (ur inspelningarna) har två försättsblad: hela styrelsen på
Zoom kl. 08.15–14.10 med §§ 1–14, och presidiet i Kommunstyrelsesalen kl. 14.10–14.30 med § 15,
ett beslut på delegation av kommunstyrelsen. De förväntade värdena är kontrollerade för hand mot
protokollet.
"""

from __future__ import annotations

import io
from datetime import datetime

import httpx
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from test_sammantradesplaner import kor

from app.protokolltolkning import beslutande_vid, paragrafintervall, sidtexter, tolka
from app.sources.base import Dokument, Hamtning

PDF = INSPELNINGAR / "harnosand" / "download_18_7abb6df217e6e0e59a326be1_1642603225421_Protokoll_kommunstyrelsen_2022_01_18.pdf"
PRESIDIET = ["Andreas Sjölander", "Carl Fredrik Edgren", "Christina Lindberg"]


def utan_sidor(pdf: bytes, *sidor: int) -> bytes:
    """PDF:en utan de angivna sidorna (räknat från 1)."""
    w = PdfWriter()
    for i, sida in enumerate(PdfReader(io.BytesIO(pdf)).pages):
        if i + 1 not in sidor:
            w.add_page(sida)
    ut = io.BytesIO()
    w.write(ut)
    return ut.getvalue()


def test_paragrafintervallet_ar_alla_sittningarnas_tillsammans():
    t = tolka(PDF.read_bytes())
    assert t.avvikelser == []
    assert [b.paragraf for b in t.behandlingar] == list(range(1, 16))
    assert paragrafintervall(sidtexter(PDF.read_bytes())[1]) == list(range(1, 16))


def test_varje_sittning_med_plats_tid_och_paragrafer():
    t = tolka(PDF.read_bytes())
    # Sammanträdets plats och tid är den första sittningens.
    assert (t.plats, t.starttid, t.sluttid) == ("Digitalt möte via Zoom", "08:15", "14:10")
    assert [(s.plats, s.starttid, s.sluttid, s.paragrafer, s.delegation) for s in t.sittningar] == [
        ("Digitalt möte via Zoom", "08:15", "14:10", list(range(1, 15)), None),
        ("Kommunstyrelsesalen", "14:10", "14:30", [15], "kommunstyrelsens presidium"),
    ]


def test_beslutande_per_sittning():
    t = tolka(PDF.read_bytes())
    assert [n.namn for n in beslutande_vid(t.narvaro, 15)] == PRESIDIET
    assert len(beslutande_vid(t.narvaro, 14)) == 15
    per_namn = {n.namn: n for n in t.narvaro}
    # Presidiet var med vid båda sittningarna, övriga ledamöter och ersättarna bara vid den första.
    assert all(per_namn[n].paragrafer is None for n in PRESIDIET)
    assert per_namn["Glenn Sehlin"].paragrafer == list(range(1, 15))
    assert (per_namn["Susanne Forsberg"].kategori, per_namn["Susanne Forsberg"].paragrafer) == (
        "ej_tjanstgorande", list(range(1, 15)))
    assert len(t.narvaro) == 22  # ingen person två gånger


def test_en_verklig_lucka_upptacks_fortfarande():
    # Utan sidan med § 15 (sida 26) saknas den andra sittningens paragraf.
    t = tolka(utan_sidor(PDF.read_bytes(), 26))
    assert t.avvikelser == ["Paragraferna stämmer inte med protokollets paragrafintervall (saknas: 15)"]
    # Utan sidan med § 2 (sida 5) saknas en paragraf i den första sittningen.
    t = tolka(utan_sidor(PDF.read_bytes(), 5))
    assert t.avvikelser == ["Paragraferna stämmer inte med protokollets paragrafintervall (saknas: 2)"]


def test_ett_protokoll_med_en_sittning_har_inga_sittningar():
    t = tolka(utan_sidor(PDF.read_bytes(), 2, 26))
    assert t.sittningar == []
    assert t.avvikelser == []
    assert all(n.paragrafer is None for n in t.narvaro)


class Kalla:
    id = "test-ks"
    titel = "Kommunstyrelsen (test)"
    url = "https://harnosand.se"
    anrop_per_sekund = None

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        h = Hamtning()
        h.dokument.append(Dokument("https://harnosand.se/download/x/Protokoll kommunstyrelsen 2022-01-18.pdf",
                                   "Protokoll kommunstyrelsen 2022-01-18.pdf", "protokoll", "KS", PDF.read_bytes()))
        return h


@pytest.fixture
def api(database_url, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[Kalla()], anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def ks(api: TestClient) -> dict:
    [s] = api.get("/api/sammantraden?organ=KS").json()
    return api.get(f"/api/sammantraden/{s['id']}").json()


def test_sammantradet_visar_sittningarna_var_for_sig(api):
    s = ks(api)
    assert s["avvikelser"] == []
    assert [(x["nummer"], x["plats"], x["starttid"], x["sluttid"], x["paragrafer"], x["delegation"])
            for x in s["sittningar"]] == [
        (1, "Digitalt möte via Zoom", "08:15", "14:10", list(range(1, 15)), None),
        (2, "Kommunstyrelsesalen", "14:10", "14:30", [15], "kommunstyrelsens presidium"),
    ]
    forsta, andra = s["sittningar"]
    assert len(forsta["beslutande"]) == 15
    assert [(p["namn"], p["parti"]) for p in andra["beslutande"]] == [
        ("Andreas Sjölander", "S"), ("Carl Fredrik Edgren", "V"), ("Christina Lindberg", "C")]


def test_behandlingen_har_sittningens_beslutande(api):
    s = ks(api)
    b15 = api.get(f"/api/sammantraden/{s['id']}/behandlingar/15").json()
    assert [p["namn"] for p in b15["beslutande"]] == PRESIDIET
    assert b15["sittning"] == {"nummer": 2, "plats": "Kommunstyrelsesalen", "starttid": "14:10", "sluttid": "14:30",
                               "paragrafer": [15], "delegation": "kommunstyrelsens presidium"}
    b14 = api.get(f"/api/sammantraden/{s['id']}/behandlingar/14").json()
    assert len(b14["beslutande"]) == 15
    assert b14["sittning"]["nummer"] == 1


def test_narvarostatistiken_raknar_per_sittning(api):
    s = ks(api)
    per_namn = {p["namn"]: p for p in s["narvaro"]}
    sehlin = api.get(f"/api/ledamoter/{per_namn['Glenn Sehlin']['ledamot_id']}").json()
    [rad] = sehlin["sammantraden"]
    assert (rad["kategori"], rad["paragrafer"]) == ("beslutande", list(range(1, 15)))
    ordforande = api.get(f"/api/ledamoter/{per_namn['Andreas Sjölander']['ledamot_id']}").json()
    [rad] = ordforande["sammantraden"]
    assert (rad["kategori"], rad["paragrafer"]) == ("beslutande", None)
    assert ordforande["organ"][0]["beslutande"] == 1  # ett sammanträde, inte två

