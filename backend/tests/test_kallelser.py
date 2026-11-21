"""Kallelser, plats och webbsändningar till sammanträdena (#68, del 3).

Data: organens sidor och sidan för webb-tv på harnosand.se, och de små kallelserna (fullmäktiges kungörelser
och två kallelser från skolnämnden) ur inspelningarna. Dagens datum låses till 2026-11-20.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient
from icalendar import Calendar
from test_sammantradesplaner import kor

from app.recorded import InspeladTransport
from app.sources import kallelser as km
from app.sources.harnosand import Protokollkalla
from app.sources.sammantradesplaner import Sammantradesplaner

SIDA = str(INSPELNINGAR / "harnosand" / "kommun_styrning_politik_och_demokrati_{}.html")


@pytest.fixture(autouse=True)
def lasta_datum(monkeypatch):
    monkeypatch.setenv("KOMMUNKOLLEN_IDAG", "2026-11-20")


def test_kallelser_och_handlingar_pa_organens_sidor():
    kf = km.kallelser_pa_sidan("KF", Path(SIDA.format("kommunfullmaktige")).read_text(encoding="utf-8"))
    assert len([k for k in kf if k.typ == "kungorelse"]) == 8
    assert len([k for k in kf if k.typ == "handlingar"]) == 7
    [elva] = [k for k in kf if k.typ == "kungorelse" and k.tid == "11:00"]
    assert (elva.datum, elva.titel, elva.storlek) == (
        date(2026, 10, 26), "Kungörelse kommunfullmäktige 2026-10-26 kl. 11.00", 172_100)
    [h] = [k for k in kf if k.typ == "handlingar" and k.tid == "11:00"]
    assert h.titel == "Handlingar kommunfullmäktige 2026-10-26, 11 00"

    ks = km.kallelser_pa_sidan("KS", Path(SIDA.format("kommunstyrelse")).read_text(encoding="utf-8"))
    assert {k.typ for k in ks} == {"handlingar"}  # kommunstyrelsen publicerar handlingarna som kallelse
    skol = km.kallelser_pa_sidan("SKOL", Path(SIDA.format("namnder_skolnamnden")).read_text(encoding="utf-8"))
    assert date(2026, 3, 30) in {k.datum for k in skol}  # extrainsatt sammanträde


def test_platsen_lases_ur_kallelsen():
    klient = httpx.Client(transport=InspeladTransport(INSPELNINGAR))
    kf = km.kallelser_pa_sidan("KF", Path(SIDA.format("kommunfullmaktige")).read_text(encoding="utf-8"))
    [elva] = [k for k in kf if k.typ == "kungorelse" and k.tid == "11:00"]
    last = km.las_kallelse(elva, klient.get(elva.url).content)
    assert (last.plats, last.tid, last.pdf_last) == ("Rådhuset - KF-salen", "11:00", True)
    # En fil som inte är en kallelse ger ingen plats, men räknas som läst.
    assert km.las_kallelse(elva, b"inte en pdf") == elva.__class__(**{**elva.__dict__, "pdf_last": True})


def test_webbsandningarna_pa_sidan_for_webb_tv():
    w = km.webbsandningar((INSPELNINGAR / "harnosand" /
                          "kommun_styrning_politik_och_demokrati_kommunfullmaktige_webb_tv.html").read_text(encoding="utf-8"))
    per_datum = {x.datum: x for x in w}
    assert per_datum[date(2026, 10, 26)].url.startswith("https://qcnl.tv/p/")
    assert per_datum[date(2025, 10, 27)].url.startswith("https://play.quickchannel.com/play/")
    assert per_datum[date(2026, 10, 26)].titel == "Sammanträde 2026-10-26"


class Raknande(httpx.BaseTransport):
    def __init__(self) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.adresser: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.adresser.append(str(request.url))
        return self.inspelad.handle_request(request)


@pytest.fixture
def api(database_url, google) -> TestClient:
    kallor = [Protokollkalla("KF", arkiv_fran=None, anrop_per_sekund=None), Sammantradesplaner(anrop_per_sekund=None)]
    klient = TestClient(skapa_app(database_url, google, kallor=kallor))
    kor(klient)
    assert klient.post("/api/auth/test/lasare").status_code == 200
    return klient


def handelse(api: TestClient, organ: str, datum: str, starttid: str | None = None) -> dict:
    k = api.get("/api/kalender", params={"organ": organ}).json()
    [h] = [h for h in k["handelser"] if h["datum"] == datum and (starttid is None or h["starttid"] == starttid)]
    return h


def test_kallelserna_kopplas_till_sina_sammantraden(api):
    # Två sammanträden samma dag: var och en får sin kungörelse och sina handlingar.
    elva = handelse(api, "KF", "2026-10-26", "11:10")
    assert elva["kallelse"]["titel"] == "Kungörelse kommunfullmäktige 2026-10-26 kl. 11.00"
    assert elva["kallelse"]["typ"] == "kungorelse"
    assert [h["titel"] for h in elva["handlingar"]] == ["Handlingar kommunfullmäktige 2026-10-26, 11 00"]
    kvart = handelse(api, "KF", "2026-10-26", "13:15")
    assert kvart["kallelse"]["titel"] == "Kungörelse kommunfullmäktige 2026-10-26 kl. 13.15"

    # En nämnd: kallelse med handlingar, för stor för att läsa platsen ur.
    sam = handelse(api, "SAM", "2026-10-29")
    assert sam["kallelse"]["titel"] == "Kallelse med handlingar 2026-10-29"

    # Kommande sammanträde utan publicerad kallelse.
    assert handelse(api, "KF", "2026-12-14")["kallelse"] is None


def test_platsen_kommer_fran_kallelsen_annars_senaste_protokollet(api):
    # Skolnämndens kallelse är liten nog att läsa, och dess protokoll ingår inte här.
    skol = handelse(api, "SKOL", "2026-06-04")
    assert (skol["plats"], skol["plats_kalla"], skol["plats_antagen"]) == ("Rådhuset - KS-salen", "kallelse", False)
    # Ett hållet sammanträde har protokollets plats.
    assert handelse(api, "KF", "2026-10-26", "11:10")["plats_kalla"] == "protokoll"
    # Utan kallelse: organets senaste protokoll, markerad som antagen.
    dec = handelse(api, "KF", "2026-12-14")
    assert (dec["plats_kalla"], dec["plats_antagen"]) == ("antagen", True)


def test_webbsandning_fore_och_efter_sammantradet(api):
    sep = handelse(api, "KF", "2026-09-28")
    assert sep["webbsandning"]["inspelning"] is True
    assert sep["webbsandning"]["url"].startswith("https://qcnl.tv/p/")
    # Båda sammanträdena 2026-10-26 finns i samma inspelning.
    assert handelse(api, "KF", "2026-10-26", "13:15")["webbsandning"]["inspelning"] is True
    # Före sammanträdet: sidan för webb-tv.
    dec = handelse(api, "KF", "2026-12-14")
    assert dec["webbsandning"] == {"url": km.WEBB_TV, "inspelning": False}
    # Inställt sammanträde och andra organ: ingen webbsändning.
    assert handelse(api, "KF", "2026-10-15")["webbsandning"] is None
    assert handelse(api, "KS", "2026-11-24")["webbsandning"] is None


def test_ics_beskrivningen_har_kallelse_och_webb_tv(api):
    cal = Calendar.from_ical(api.get("/kalender/kommunfullmaktige.ics").content)
    per_start = {e.decoded("DTSTART").isoformat()[:16]: str(e["DESCRIPTION"]) for e in cal.walk("VEVENT")}
    okt = per_start["2026-10-26T11:10"]
    assert "Kungörelse: https://harnosand.se/download/" in okt
    assert "Inspelning: https://qcnl.tv/p/" in okt
    assert "Webbsänds, webb-tv: https://harnosand.se/" in per_start["2026-12-14T13:15"]
    skol = Calendar.from_ical(api.get("/kalender/skolnamnden.ics").content)
    [juni] = [e for e in skol.walk("VEVENT") if e.decoded("DTSTART").isoformat().startswith("2026-06-04")]
    assert str(juni["LOCATION"]) == "Rådhuset - KS-salen"
    assert "Platsen är antagen" not in str(juni["DESCRIPTION"])


def test_lasta_kallelser_hamtas_inte_igen(database_url, google):
    transport = Raknande()
    app = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)],
                               transport=transport))
    [forsta] = kor(app)["kallor"]
    assert forsta["status"] == "lyckad", forsta["fel"]
    pdf_forsta = [a for a in transport.adresser if a.endswith(".pdf")]
    assert len(pdf_forsta) == 10  # åtta kungörelser och två små kallelser från skolnämnden

    transport.adresser.clear()
    [andra] = kor(app)["kallor"]
    assert andra["status"] == "inga_nya"
    assert [a for a in transport.adresser if a.endswith(".pdf")] == []
