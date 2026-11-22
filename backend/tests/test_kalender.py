"""Kalendern och ics-flödena över sammanträden (#68, del 2).

Data: fullmäktiges protokoll för 2026 och de fem organens sammanträdesplaner, ur inspelningarna.
Dagens datum låses till 2026-11-20, så att kommande och tidigare sammanträden är desamma varje gång.
ics-utdatan kontrolleras med parserbiblioteket icalendar.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from icalendar import Calendar
from test_sammantradesplaner import MedAndradSida, kor

from app import kalender
from app.sources.harnosand import Protokollkalla
from app.sources.sammantradesplaner import Sammantradesplaner

STOCKHOLM = "Europe/Stockholm"


@pytest.fixture(autouse=True)
def lasta_datum(monkeypatch):
    monkeypatch.setenv("KOMMUNKOLLEN_IDAG", "2026-11-20")


def kallor():
    return [Protokollkalla("KF", arkiv_fran=None, anrop_per_sekund=None), Sammantradesplaner(anrop_per_sekund=None)]


@pytest.fixture
def api(database_url, google) -> TestClient:
    klient = TestClient(skapa_app(database_url, google, kallor=kallor()))
    kor(klient)
    assert klient.post("/api/auth/logga-ut").status_code in (200, 204)
    return klient


def kalenderfil(api: TestClient, adress: str) -> Calendar:
    svar = api.get(adress)
    assert svar.status_code == 200, svar.text
    assert svar.headers["content-type"].startswith("text/calendar")
    return Calendar.from_ical(svar.content)


def handelse(cal: Calendar, datum: str, tid: str | None = None):
    traffar = [e for e in cal.walk("VEVENT") if e.decoded("DTSTART").isoformat().startswith(
        datum + (f"T{tid}" if tid else ""))]
    assert len(traffar) == 1, [e.decoded("DTSTART") for e in cal.walk("VEVENT")]
    return traffar[0]


def test_floden_per_organ_och_gemensamt_ar_oppna_och_giltiga(api):
    # Ingen inloggning: kalenderappar kan inte logga in.
    kf = kalenderfil(api, "/kalender/kommunfullmaktige.ics")
    assert str(kf["VERSION"]) == "2.0" and kf["PRODID"]
    assert str(kf["X-WR-CALNAME"]) == "Kommunfullmäktige – sammanträden"
    [tz] = kf.walk("VTIMEZONE")
    assert str(tz["TZID"]) == STOCKHOLM
    assert {str(e["SUMMARY"]) for e in kf.walk("VEVENT")} >= {"Kommunfullmäktige – sammanträde"}
    assert {str(e["SUMMARY"]).split(": ")[-1] for e in kf.walk("VEVENT")} == {"Kommunfullmäktige – sammanträde"}

    alla = kalenderfil(api, "/kalender/alla.ics")
    organ = {str(e["SUMMARY"]).split(": ")[-1].split(" – ")[0] for e in alla.walk("VEVENT")}
    assert organ == {"Kommunfullmäktige", "Kommunstyrelsen", "Samhällsnämnden", "Socialnämnden", "Skolnämnden"}
    assert api.get("/kalender/okant.ics").status_code == 404


def test_handelsen_har_tidszon_uid_och_ungefarlig_sluttid(api):
    kf = kalenderfil(api, "/kalender/kommunfullmaktige.ics")
    dec = handelse(kf, "2026-12-14")
    start, slut = dec.decoded("DTSTART"), dec.decoded("DTEND")
    assert str(start.tzinfo) == STOCKHOLM and start.isoformat() == "2026-12-14T13:15:00+01:00"
    # Sluttiden: medianlängden för fullmäktiges sammanträden enligt protokollen.
    assert slut > start and slut.date() == start.date()
    assert str(dec["UID"]).startswith("sammantrade-") and str(dec["UID"]).endswith("@kommunkollen-harnosand")
    assert str(dec["STATUS"]) == "CONFIRMED"
    beskrivning = str(dec["DESCRIPTION"])
    assert "Sluttiden är ungefärlig" in beskrivning
    assert "Platsen är antagen" in beskrivning
    assert str(dec["LOCATION"]) == "Rådhuset - KF-salen"
    assert "/kalender?sammantrade=" in beskrivning
    assert "kommunfullmaktige.html" in beskrivning

    # Ett hållet sammanträde har protokollets tider och plats, och länk till protokollet.
    okt = handelse(kf, "2026-10-26", "11:")
    assert okt.decoded("DTSTART").isoformat() == "2026-10-26T11:10:00+01:00"
    assert "Sluttiden är ungefärlig" not in str(okt["DESCRIPTION"])
    assert "/politik/sammantraden/" in str(okt["DESCRIPTION"])
    # Sommartid i september.
    assert handelse(kf, "2026-09-28").decoded("DTSTART").utcoffset().total_seconds() == 7200


def test_installt_sammantrade_ar_kvar_som_cancelled(api):
    kf = kalenderfil(api, "/kalender/kommunfullmaktige.ics")
    okt = handelse(kf, "2026-10-15")
    assert str(okt["STATUS"]) == "CANCELLED"
    assert str(okt["SUMMARY"]) == "Inställt: Kommunfullmäktige – sammanträde"
    # Utan tid i planen: heldag.
    assert okt.decoded("DTSTART") == date(2026, 10, 15)
    ks = kalenderfil(api, "/kalender/kommunstyrelsen.ics")
    assert str(handelse(ks, "2026-09-08")["STATUS"]) == "CANCELLED"


def test_flodet_har_kommande_och_senaste_tolv_manaderna(api):
    ks = kalenderfil(api, "/kalender/kommunstyrelsen.ics")
    datum = sorted(e.decoded("DTSTART").date() if isinstance(e.decoded("DTSTART"), datetime)
                   else e.decoded("DTSTART") for e in ks.walk("VEVENT"))
    assert datum[0] >= date(2025, 11, 20)
    assert datum[-1] == date(2027, 11, 23)


def test_andrad_tid_behaller_uid_och_ger_ny_dtstart_och_sequence(database_url, google, api):
    fore = handelse(kalenderfil(api, "/kalender/kommunfullmaktige.ics"), "2026-12-14")
    andrad = MedAndradSida("KF", [("<p>December</p></td><td>14</td><td>13.15</td>",
                                   "<p>December</p></td><td>14</td><td>OBS tiden: 09.00</td>")])
    api2 = TestClient(skapa_app(database_url, google, kallor=[Sammantradesplaner(anrop_per_sekund=None)],
                                transport=andrad))
    kor(api2)
    efter = handelse(kalenderfil(api2, "/kalender/kommunfullmaktige.ics"), "2026-12-14")
    assert str(efter["UID"]) == str(fore["UID"])
    assert efter.decoded("DTSTART").isoformat() == "2026-12-14T09:00:00+01:00"
    assert int(efter["SEQUENCE"]) == int(fore["SEQUENCE"]) + 1


def test_ett_sammantrade_som_ics_fil(api):
    assert api.post("/api/auth/test/lasare").status_code == 200
    lista = api.get("/api/kalender", params={"organ": "KF"}).json()
    [dec] = [h for h in lista["handelser"] if h["datum"] == "2026-12-14"]
    svar = api.get(f"/kalender/sammantraden/{dec['id']}.ics")
    assert svar.status_code == 200
    assert svar.headers["content-disposition"] == 'attachment; filename="kommunfullmaktige-2026-12-14.ics"'
    cal = Calendar.from_ical(svar.content)
    [e] = cal.walk("VEVENT")
    assert str(e["UID"]) == dec["uid"]
    assert api.get("/kalender/sammantraden/999999.ics").status_code == 404


def test_kalender_api_for_sidan(api):
    assert api.post("/api/auth/test/lasare").status_code == 200
    k = api.get("/api/kalender").json()
    assert k["idag"] == "2026-11-20"
    assert [f["flode"] for f in k["floden"]] == list(kalender.SLUG.values())
    [okt] = [h for h in k["handelser"] if h["organ"]["id"] == "KF" and h["datum"] == "2026-10-26"
             and h["starttid"] == "11:10"]
    assert (okt["status"], okt["protokoll"], okt["sluttid_ungefarlig"]) == ("hallet", True, False)
    [inst] = [h for h in k["handelser"] if h["organ"]["id"] == "KF" and h["datum"] == "2026-10-15"]
    assert inst["status"] == "installt"
    # Ett extra sammanträde som inte fanns i planen ingår också (fullmäktige 13.15 samma dag).
    assert [h["starttid"] for h in k["handelser"] if h["organ"]["id"] == "KF" and h["datum"] == "2026-10-26"] == \
        ["11:10", "13:15"]
    assert api.get("/api/kalender", params={"organ": "XX"}).status_code == 422


def test_textvarden_escapas_och_langa_rader_viks():
    assert kalender.text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    rad = "DESCRIPTION:" + "å" * 80
    vikt = kalender.vik(rad)
    for del_ in vikt.split("\r\n"):
        assert len(del_.encode("utf-8")) <= 75
    assert vikt.replace("\r\n ", "") == rad
