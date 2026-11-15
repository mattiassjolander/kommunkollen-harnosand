"""Statistik över protokollen (#44): behandlingar per organ, år och behandlingstyp."""

from __future__ import annotations

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf, kor
from test_rattelser import behandling, publicerad, sammantrade_id

from app import db

URL = "/api/statistik/behandlingar"


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def test_behandlingar_per_ar_organ_och_typ(api):
    # Inspelningen har kommunfullmäktiges protokoll från 2026.
    s = api.get(URL).json()
    assert (s["fran"], s["till"], s["tillgangliga_ar"]) == (2026, 2026, [2026])
    [kf_] = s["rader"]
    assert (kf_["ar"], kf_["organ"]["id"], kf_["sammantraden"], kf_["behandlingar"]) == (2026, "KF", 8, 140)
    assert kf_["antal"]["motion"] == 12
    assert kf_["antal"]["interpellation"] == 30
    assert kf_["antal"]["beslut"] > 0 and kf_["antal"]["information"] > 0
    # Kommunfullmäktige lämnar inga förslag till ett annat organ.
    assert kf_["antal"]["forslag"] == 0
    assert sum(kf_["antal"].values()) == kf_["behandlingar"]
    assert s["summa"] == {k: kf_[k] for k in ("sammantraden", "behandlingar", "antal")}
    assert [t["id"] for t in s["typer"]][-1] == "okand"
    assert s["underlag"] == {"ej_tolkade": [], "paragrafprotokoll": [], "utan_datum": 0}


def test_arsintervall_och_organ(api):
    assert api.get(URL, params={"fran": 2026, "till": 2026, "organ": "KF"}).json()["rader"][0]["sammantraden"] == 8
    tomt = api.get(URL, params={"fran": 2024, "till": 2025}).json()
    assert (tomt["rader"], tomt["summa"]["behandlingar"]) == ([], 0)
    assert api.get(URL, params={"organ": "KS"}).json()["rader"] == []
    assert api.get(URL, params={"fran": 2026, "till": 2025}).status_code == 422
    assert api.get(URL, params={"organ": "XX"}).status_code == 422


def test_typen_kan_rattas_och_raknas_med(api):
    fore = api.get(URL).json()["summa"]["antal"]
    b = behandling(api, "2026-06-15", 109)
    assert b["typ"] == "beslut"
    publicerad(api, sammantrade_id=sammantrade_id(api, "2026-06-15"), objekt="behandling", paragraf=109, falt="typ",
               nytt="information", motivering="Prov.")
    b = behandling(api, "2026-06-15", 109)
    assert (b["typ"], b["rattelser"]["typ"]["ursprungligt"]) == ("information", "beslut")
    efter = api.get(URL).json()["summa"]["antal"]
    assert (efter["beslut"], efter["information"]) == (fore["beslut"] - 1, fore["information"] + 1)


def test_protokoll_som_inte_gick_att_tolka_redovisas(api, database_url):
    s = sammantrade_id(api, "2026-06-15")
    with db.connect(database_url) as conn:
        conn.execute("UPDATE sammantrade SET tolkning = 'ej_tolkad' WHERE id = %s", (s,))
        conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s", (s,))
    underlag = api.get(URL).json()["underlag"]
    assert [x["id"] for x in underlag["ej_tolkade"]] == [s]
