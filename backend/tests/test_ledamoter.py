"""Ledamotsregistret ur protokollens närvarolistor (#30).

Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade). De förväntade värdena
är kontrollerade för hand mot protokollen.
"""

from __future__ import annotations

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf, kor


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def ledamot(api: TestClient, namn: str) -> dict:
    [p] = [p for p in api.get("/api/ledamoter").json() if p["namn"] == namn]
    return p


def test_registret_listar_alla_i_narvarolistorna_med_parti_enligt_protokollen(api):
    lista = api.get("/api/ledamoter").json()
    namn = [p["namn"] for p in lista]
    assert len(namn) == len(set(namn)) == 112
    assert namn == sorted(namn, key=lambda n: n.casefold().translate(str.maketrans("åäö", "{|}")))
    assert "Jonas Bergström" in namn  # kommunalråd under Övriga i våras, ledamot i oktober
    assert "Olof Bäckman" not in namn  # sekreterare, inte i närvaron

    edgren = ledamot(api, "Carl-Fredrik Edgren")
    assert edgren["parti"] == "-"  # senast: partilös
    assert edgren["partier"] == ["-", "V"]
    assert edgren["organ"] == [{"id": "KF", "namn": "Kommunfullmäktige"}]
    assert (edgren["antal_sammantraden"], edgren["senast"]) == (5, "2026-09-28")

    assert [p["namn"] for p in api.get("/api/ledamoter", params={"q": "thyr"}).json()] == [
        "Britta Thyr", "Knapp Britta Thyr",
    ]
    assert {p["namn"] for p in api.get("/api/ledamoter", params={"parti": "-"}).json()} >= {"Carl-Fredrik Edgren"}
    assert api.get("/api/ledamoter", params={"organ": "KS"}).json() == []


def test_ledamotssidan_visar_partibyte_roller_och_narvaro(api):
    s = api.get(f"/api/ledamoter/{ledamot(api, 'Carl-Fredrik Edgren')['id']}").json()
    assert s["namn"] == "Carl-Fredrik Edgren"
    # Partiet som protokollet anger, sammanträde för sammanträde. I juni anges inget parti.
    assert s["partier_over_tid"] == [
        {"parti": "V", "fran": "2026-02-23", "till": "2026-02-23", "antal": 1},
        {"parti": "-", "fran": "2026-03-23", "till": "2026-05-25", "antal": 2},
        {"parti": None, "fran": "2026-06-15", "till": "2026-06-15", "antal": 1},
        {"parti": "-", "fran": "2026-09-28", "till": "2026-09-28", "antal": 1},
    ]
    [kf_] = s["organ"]
    assert kf_["roller"] == ["Ledamot"]
    assert (kf_["antal"], kf_["beslutande"], kf_["franvarande"]) == (5, 5, 0)
    senaste = s["sammantraden"][0]
    assert senaste["sammantrade"]["datum"] == "2026-09-28"
    assert (senaste["parti"], senaste["roll"], senaste["kategori"]) == ("-", "Ledamot", "beslutande")
    feb = s["sammantraden"][-1]
    assert feb["sammantrade"]["datum"] == "2026-02-23"
    assert 7 not in feb["paragrafer"]

    # Frånvaro syns när protokollet redovisar den (tabellerna i februari och mars).
    skyttberg = api.get(f"/api/ledamoter/{ledamot(api, 'Nina Skyttberg')['id']}").json()
    assert skyttberg["organ"][0]["franvarande"] >= 1

    # Ersättare med tjänstgöring.
    rune = api.get(f"/api/ledamoter/{ledamot(api, 'Rune Danielsson')['id']}").json()
    assert {"namn": "Magnus Oskarsson", "parti": "S"} in [x["tjanstgor_for"] for x in rune["sammantraden"]]

    assert api.get("/api/ledamoter/999999").status_code == 404


def test_behandlingen_lankar_till_ledamoten(api):
    [s] = [s for s in api.get("/api/sammantraden").json() if s["datum"] == "2026-09-28"]
    b = api.get(f"/api/sammantraden/{s['id']}/behandlingar/129").json()
    [mohamed] = [p for p in b["beslutande"] if p["namn"] == "Mohamed Abdulwahab Mohamed"]
    assert mohamed["ledamot_id"] == ledamot(api, "Mohamed Abdulwahab Mohamed")["id"]
    [jav] = [p for p in b["jav"] if p["namn"] == "Knapp Britta Thyr"]
    assert jav["ledamot_id"] == ledamot(api, "Knapp Britta Thyr")["id"]
    sammantrade = api.get(f"/api/sammantraden/{s['id']}").json()
    [ovrig] = [p for p in sammantrade["narvaro"] if p["kategori"] == "ovrig"]
    assert ovrig["ledamot_id"] is None


def test_redaktoren_slar_ihop_och_delar_upp(api):
    britta, knapp = ledamot(api, "Britta Thyr"), ledamot(api, "Knapp Britta Thyr")

    # Kräver inloggning med rollen redaktör.
    assert api.post(f"/api/ledamoter/{knapp['id']}/sammanslagningar", params={"med": britta["id"]}).status_code == 401
    assert api.post("/api/auth/test/lasare").status_code == 200
    assert api.post(f"/api/ledamoter/{knapp['id']}/sammanslagningar", params={"med": britta["id"]}).status_code == 403
    assert api.post("/api/auth/test/redaktor").status_code == 200

    svar = api.post(f"/api/ledamoter/{knapp['id']}/sammanslagningar", params={"med": britta["id"]})
    assert svar.status_code == 200, svar.text
    s = svar.json()
    assert (s["id"], s["namn"]) == (knapp["id"], "Knapp Britta Thyr")
    assert [(n["namn"], n["huvudnamn"]) for n in s["namn_varianter"]] == [
        ("Knapp Britta Thyr", True), ("Britta Thyr", False),
    ]
    assert len(s["sammantraden"]) == 8
    assert s["organ"][0]["antal"] == 8

    # Registret visar en person, och det andra namnet leder dit.
    namn = [p["namn"] for p in api.get("/api/ledamoter").json()]
    assert "Britta Thyr" not in namn
    assert ledamot(api, "Knapp Britta Thyr")["andra_namn"] == ["Britta Thyr"]
    via = api.get(f"/api/ledamoter/{britta['id']}").json()
    assert (via["id"], via["sammanslagen_med"]) == (knapp["id"], knapp["id"])
    assert api.post(f"/api/ledamoter/{britta['id']}/sammanslagningar", params={"med": knapp["id"]}).status_code == 409

    # Behandlingen pekar på den sammanslagna personen.
    [s0928] = [s for s in api.get("/api/sammantraden").json() if s["datum"] == "2026-10-26" and s["starttid"] == "11:10"]
    [p] = [p for p in api.get(f"/api/sammantraden/{s0928['id']}").json()["narvaro"] if p["namn"] == "Britta Thyr"]
    assert p["ledamot_id"] == knapp["id"]

    # Uppdelning: namnet blir en egen person igen.
    svar = api.post(f"/api/ledamoter/{britta['id']}/uppdelning")
    assert svar.status_code == 200, svar.text
    assert (svar.json()["id"], svar.json()["namn"], len(svar.json()["sammantraden"])) == (britta["id"], "Britta Thyr", 5)
    assert ledamot(api, "Knapp Britta Thyr")["andra_namn"] == []
    assert api.post(f"/api/ledamoter/{britta['id']}/uppdelning").status_code == 409

    # En sammanslagning av en grupp flyttar alla dess namn.
    mohamed, abdul = ledamot(api, "Mohamed Abdulwahab Mohamed"), ledamot(api, "Mohamed Abdulwahab")
    api.post(f"/api/ledamoter/{knapp['id']}/sammanslagningar", params={"med": britta["id"]})
    api.post(f"/api/ledamoter/{mohamed['id']}/sammanslagningar", params={"med": abdul["id"]})
    s = api.post(f"/api/ledamoter/{mohamed['id']}/sammanslagningar", params={"med": britta["id"]}).json()
    assert {n["namn"] for n in s["namn_varianter"]} == {
        "Mohamed Abdulwahab Mohamed", "Mohamed Abdulwahab", "Knapp Britta Thyr", "Britta Thyr",
    }


def test_sammanslagningen_finns_kvar_efter_ny_tolkning(database_url, google):
    a = TestClient(skapa_app(database_url, google, kallor=kf()))
    kor(a)
    knapp, britta = ledamot(a, "Knapp Britta Thyr"), ledamot(a, "Britta Thyr")
    a.post(f"/api/ledamoter/{knapp['id']}/sammanslagningar", params={"med": britta["id"]})
    kor(a)  # protokollen hämtas och tolkas om
    assert ledamot(a, "Knapp Britta Thyr")["andra_namn"] == ["Britta Thyr"]
