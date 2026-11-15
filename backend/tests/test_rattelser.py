"""Redaktionella rättelser av tolkade uppgifter (#33).

En redaktör skriver en rättelse som utkast, och en utgivare som inte är samma person granskar
och publicerar den. Läsaren ser den rättade uppgiften med markering och vad tolkningen sa.
Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf, kor

from app import db
from app.protokoll import tolka_om


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def logga_in(api: TestClient, roll: str | None) -> None:
    api.post("/api/auth/logga-ut")
    if roll:
        assert api.post(f"/api/auth/test/{roll}").status_code == 200


def sammantrade_id(api: TestClient, datum: str) -> int:
    [s] = [s for s in api.get("/api/sammantraden?organ=KF").json() if s["datum"] == datum]
    return s["id"]


def behandling(api: TestClient, datum: str, paragraf: int) -> dict:
    return api.get(f"/api/sammantraden/{sammantrade_id(api, datum)}/behandlingar/{paragraf}").json()


def skapa(api: TestClient, **data) -> dict:
    svar = api.post("/api/rattelser", json=data)
    assert svar.status_code == 201, svar.text
    return svar.json()


def test_fran_utkast_till_publicerad_och_ingen_godkanner_sin_egen(api):
    s = sammantrade_id(api, "2026-06-15")
    tolkat = behandling(api, "2026-06-15", 109)["beslut"]

    # Bara redaktörer skriver rättelser.
    utkast = {"sammantrade_id": s, "objekt": "behandling", "paragraf": 109, "falt": "beslut",
              "nytt": "Kommunfullmäktige antar planprogrammet.", "motivering": "Beslutet står på sidan 12."}
    assert api.post("/api/rattelser", json=utkast).status_code == 401
    logga_in(api, "utgivare")
    assert api.post("/api/rattelser", json=utkast).status_code == 403

    # En person med båda rollerna skriver en rättelse men kan inte godkänna den själv.
    logga_in(api, "redaktor+utgivare")
    r = skapa(api, **utkast)
    assert (r["status"], r["redaktor"], r["ursprungligt"], r["nytt"]) == (
        "utkast", "test-redaktor+utgivare@kommunkollen.test", tolkat, "Kommunfullmäktige antar planprogrammet.")
    egen = api.post(f"/api/rattelser/{r['id']}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner sin egen rättelse")

    # Ett utkast syns inte för läsaren.
    logga_in(api, None)
    assert behandling(api, "2026-06-15", 109)["beslut"] == tolkat
    assert api.get("/api/rattelser").status_code == 401

    # En annan utgivare granskar och publicerar. Publicering kräver att rättelsen är granskad.
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/publicering").status_code == 409
    g = api.post(f"/api/rattelser/{r['id']}/granskning").json()
    assert (g["status"], g["granskad_av"]) == ("granskad", "test-utgivare@kommunkollen.test")
    assert api.post(f"/api/rattelser/{r['id']}/granskning").status_code == 409
    p = api.post(f"/api/rattelser/{r['id']}/publicering").json()
    assert (p["status"], p["publicerad_av"]) == ("publicerad", "test-utgivare@kommunkollen.test")
    assert [x["id"] for x in api.get("/api/rattelser", params={"status": "publicerad"}).json()] == [r["id"]]

    # Läsaren ser rättelsen med vad tolkningen sa.
    logga_in(api, None)
    b = behandling(api, "2026-06-15", 109)
    assert b["beslut"] == "Kommunfullmäktige antar planprogrammet."
    assert b["rattelser"]["beslut"]["ursprungligt"] == tolkat
    assert b["rattelser"]["beslut"]["motivering"] == "Beslutet står på sidan 12."
    rad = next(x for x in api.get(f"/api/sammantraden/{s}").json()["behandlingar"] if x["paragraf"] == 109)
    assert rad["beslut"] == "Kommunfullmäktige antar planprogrammet."


def test_bara_redaktoren_andrar_sitt_utkast(api):
    s = sammantrade_id(api, "2026-06-15")
    logga_in(api, "redaktor")
    r = skapa(api, sammantrade_id=s, objekt="behandling", paragraf=109, falt="diarienummer",
              nytt=["KS/2026-200"], motivering="Fel nummer")
    andrad = api.patch(f"/api/rattelser/{r['id']}", json={"nytt": ["KS/2026-201"]})
    assert andrad.json()["nytt"] == ["KS/2026-201"]

    logga_in(api, "redaktor+utgivare")
    assert api.patch(f"/api/rattelser/{r['id']}", json={"nytt": ["X"]}).status_code == 403
    assert api.delete(f"/api/rattelser/{r['id']}").status_code == 403
    assert api.post(f"/api/rattelser/{r['id']}/granskning").status_code == 200

    logga_in(api, "redaktor")
    assert api.patch(f"/api/rattelser/{r['id']}", json={"nytt": ["X"]}).status_code == 409
    assert api.delete(f"/api/rattelser/{r['id']}").status_code == 409

    # Ogiltiga rättelser
    for data, kod in [
        ({"objekt": "behandling", "paragraf": 109, "falt": "plats", "nytt": "x"}, 422),
        ({"objekt": "behandling", "paragraf": 999, "falt": "beslut", "nytt": "x"}, 404),
        ({"objekt": "rost", "paragraf": 109, "votering": 2, "namn": "Glenn Sehlin", "falt": "rost", "nytt": "kanske"}, 422),
        ({"objekt": "rost", "paragraf": 109, "votering": 2, "namn": "Glenn Sehlin", "falt": "rost", "nytt": "nej"}, 422),
        ({"objekt": "narvaro", "namn": "Glenn Sehlin", "falt": "parti", "nytt": "Sverigedemokraterna"}, 422),
        ({"objekt": "behandling", "paragraf": 109, "falt": "beslut", "nytt": "x", "motivering": " "}, 422),
    ]:
        svar = api.post("/api/rattelser", json={"sammantrade_id": s, "motivering": "m"} | data)
        assert svar.status_code == kod, (data, svar.text)


def publicerad(api: TestClient, **data) -> dict:
    logga_in(api, "redaktor")
    r = skapa(api, **data)
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/granskning").status_code == 200
    assert api.post(f"/api/rattelser/{r['id']}/publicering").status_code == 200
    logga_in(api, None)
    return r


def test_rost_och_parti_ratts_och_bevaras_vid_ny_tolkning(api, database_url):
    s = sammantrade_id(api, "2026-06-15")
    publicerad(api, sammantrade_id=s, objekt="rost", paragraf=109, votering=2, namn="Glenn Sehlin", falt="rost",
               nytt="ja", motivering="Voteringslistan på sidan 14.")
    publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
               motivering="Närvarolistan anger inget parti. SD enligt voteringslistan.")

    def kontrollera():
        b = behandling(api, "2026-06-15", 109)
        forsta, andra = b["voteringar"]
        assert forsta["lista"] == {"ja": 27, "nej": 13, "avstar": 0, "franvarande": 0}
        assert andra["lista"] == {"ja": 28, "nej": 12, "avstar": 0, "franvarande": 0}
        [glenn] = [r for r in andra["roster"] if r["namn"] == "Glenn Sehlin"]
        assert (glenn["rost"], glenn["rattelser"]["rost"]["ursprungligt"]) == ("ja", "nej")
        [person] = [p for p in b["beslutande"] if p["namn"] == "Glenn Sehlin"]
        assert (person["parti"], person["rattelser"]["parti"]["ursprungligt"]) == ("SD", None)
        narvaro = api.get(f"/api/sammantraden/{s}").json()["narvaro"]
        assert next(p for p in narvaro if p["namn"] == "Glenn Sehlin")["parti"] == "SD"

    kontrollera()
    # En ny insamling ändrar inget, och en omtolkning skapar om behandlingarna. Rättelserna står kvar.
    logga_in(api, "redaktor")
    kor(api)
    logga_in(api, None)
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
    kontrollera()

    # En ny publicerad rättelse av samma uppgift ersätter den tidigare.
    publicerad(api, sammantrade_id=s, objekt="rost", paragraf=109, votering=2, namn="Glenn Sehlin", falt="rost",
               nytt="avstar", motivering="Rättat igen.")
    b = behandling(api, "2026-06-15", 109)
    assert b["voteringar"][1]["lista"]["avstar"] == 1
    logga_in(api, "utgivare")
    assert len(api.get("/api/rattelser", params={"status": "ersatt"}).json()) == 1
