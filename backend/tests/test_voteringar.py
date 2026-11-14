"""Yrkanden, voteringar och reservationer ur protokollen (#31).

Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade). De förväntade värdena
är kontrollerade för hand mot voteringslistorna i protokollen.
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


def sammantrade(api: TestClient, datum: str) -> dict:
    [s] = [s for s in api.get("/api/sammantraden?organ=KF").json() if s["datum"] == datum]
    return api.get(f"/api/sammantraden/{s['id']}").json()


def behandling(api: TestClient, datum: str, paragraf: int) -> dict:
    s = sammantrade(api, datum)
    return api.get(f"/api/sammantraden/{s['id']}/behandlingar/{paragraf}").json()


def rost(votering: dict, namn: str) -> dict:
    [r] = [r for r in votering["roster"] if r["namn"] == namn]
    return r


def test_ateremissvotering_och_huvudvotering_med_yrkanden_och_reservation(api):
    # KF 2026-06-15 § 109 Planprogram Skeppsbron: först om ärendet ska avgöras idag, sedan huvudvoteringen.
    b = behandling(api, "2026-06-15", 109)

    assert [[p["namn"] for p in y["personer"]] for y in b["yrkanden"]] == [
        ["Glenn Sehlin"], ["Eva-Clara Viklund"], ["Helena Elfvendal"], ["Hans Rosengren"],
    ]
    assert b["yrkanden"][0]["text"] == "Glenn Sehlin (SD) yrkar i första hand återremiss, i andra hand att ärendet avslås."
    assert b["yrkanden"][0]["personer"][0]["ledamot_id"] is not None

    forsta, andra = b["voteringar"]
    assert (forsta["nummer"], forsta["ja_forslag"], forsta["nej_forslag"]) == (
        1, "ärendet ska avgöras idag", "ärendet ska remitteras åter")
    assert (andra["ja_forslag"], andra["nej_forslag"]) == (
        "Helena Elfvendals (MP), med fleras, förslag", "Glenn Sehlins (SD), med fleras, förslag")
    for v in (forsta, andra):
        assert v["angivet"] == {"ja": 27, "nej": 13, "avstar": None, "franvarande": None}
        assert v["lista"] == {"ja": 27, "nej": 13, "avstar": 0, "franvarande": 0}
        assert v["vinnare"] == "ja"
        assert len(v["roster"]) == 40
    assert andra["resultat"] == "fullmäktige beslutat enligt Helena Elfvendals (MP), med fleras, förslag"

    # Voteringslistan: "Nina Skyttberg (S) ersatt av Mats Höglund (S)". Den som röstade är ersättaren.
    hoglund = rost(andra, "Mats Höglund")
    assert (hoglund["parti"], hoglund["rost"]) == ("S", "ja")
    assert (hoglund["ersatt"]["namn"], hoglund["ersatt"]["parti"]) == ("Nina Skyttberg", "S")
    assert hoglund["ledamot_id"] is not None and hoglund["ersatt"]["ledamot_id"] is not None
    assert rost(andra, "Monika Israelsson")["rost"] == "nej"
    assert rost(andra, "Kristoffer Bodin")["rost"] == "nej"
    assert rost(andra, "Carl Fredrik Edgren")["parti"] == "-"

    per_parti = {p["parti"]: p for p in andra["per_parti"]}
    assert [p["parti"] for p in andra["per_parti"]] == ["C", "KD", "L", "M", "MP", "S", "SD", "V", "-"]
    assert per_parti["M"] == {"parti": "M", "ja": 0, "nej": 7, "avstar": 0, "franvarande": 0}
    assert per_parti["SD"]["nej"] == 5
    assert per_parti["S"]["ja"] == 16

    [res] = b["reservationer"]
    assert [p["namn"] for p in res["personer"]] == [
        "Glenn Sehlin", "Ulrika Jonsson", "Charlotte Höglund Bystedt", "Kenneth Lunneborg", "Monika Israelsson",
    ]
    assert res["text"].endswith("reserverar sig mot beslutet.")


def test_voteringslista_med_kryss_i_kolumner_och_reservation_for_ett_parti(api):
    # KF 2026-02-23 § 5: kryss under Ja eller Nej, ersättaren i en egen kolumn.
    b = behandling(api, "2026-02-23", 5)
    [v] = b["voteringar"]
    assert (v["ja_forslag"], v["nej_forslag"]) == ("kommunstyrelsens förslag", "Göran Sjögrens (SD) förslag")
    assert v["angivet"]["ja"] == v["lista"]["ja"] == 37
    assert v["angivet"]["nej"] == v["lista"]["nej"] == 6
    assert v["vinnare"] == "ja"
    assert rost(v, "Lennart Molin")["ersatt"]["namn"] == "Nina Skyttberg"
    assert rost(v, "Anne-Cathrine Genberg")["rost"] == "ja"  # namnet bryts över två rader
    assert rost(v, "Göran Virén Sjögren")["rost"] == "nej"
    assert {p["parti"]: p["nej"] for p in v["per_parti"]}["SD"] == 6

    assert [(r["partier"], [p["namn"] for p in r["personer"]]) for r in b["reservationer"]] == [
        (["SD"], []), (["SD"], ["Göran Sjögren"]),
    ]
    [beh] = [x for x in sammantrade(api, "2026-02-23")["behandlingar"] if x["paragraf"] == 5]
    assert (beh["antal_voteringar"], beh["antal_reservationer"]) == (1, 2)


def test_avstar_och_tomma_stolar_enligt_listan(api):
    # KF 2026-03-23 § 39: kolumnen Avstår. KF 2026-04-27 § 61: "--- tom stol ---", "2 frånvarande".
    [v] = behandling(api, "2026-03-23", 39)["voteringar"]
    assert v["angivet"] == {"ja": 28, "nej": 6, "avstar": 8, "franvarande": None}
    assert (v["lista"]["ja"], v["lista"]["nej"], v["lista"]["avstar"]) == (28, 6, 8)
    assert rost(v, "Eva-Clara Viklund")["rost"] == "avstar"

    [v] = behandling(api, "2026-04-27", 61)["voteringar"]
    assert v["angivet"] == {"ja": 34, "nej": 7, "avstar": None, "franvarande": 2}
    assert v["lista"] == {"ja": 34, "nej": 7, "avstar": 0, "franvarande": 2}
    assert rost(v, "Kristoffer Bodin")["rost"] == "franvarande"
    assert rost(v, "May Andersson")["ersatt"] is None  # tjänstgjorde på en vakant plats


def test_listan_som_inte_stammer_med_texten_visas_som_den_ar(api):
    # KF 2026-06-15 § 112: texten säger 21 ja, listan har 20. Ärendet remitterades åter trots fler
    # ja-röster (minoritetsåterremiss), så vinnaren räknas inte fram ur siffrorna.
    s = sammantrade(api, "2026-06-15")
    assert "§ 112, votering 1: voteringslistan har 20 ja, 18 nej, 0 avstår, protokollets text 21 ja, 18 nej, 0 avstår" in s["avvikelser"]
    [v] = behandling(api, "2026-06-15", 112)["voteringar"]
    assert (v["angivet"]["ja"], v["lista"]["ja"]) == (21, 20)
    assert v["vinnare"] is None
    assert v["resultat"].endswith("att ärendet remitteras åter")


def test_ledamotens_roster_med_lank_till_behandlingen(api):
    [molin] = [p for p in api.get("/api/ledamoter?q=Lennart Molin").json() if p["namn"] == "Lennart Molin"]
    roster = api.get(f"/api/ledamoter/{molin['id']}").json()["roster"]
    feb = [r for r in roster if r["sammantrade"]["datum"] == "2026-02-23"]
    assert [(r["paragraf"], r["rost"], r["ersatt"]["namn"]) for r in feb] == [(5, "ja", "Nina Skyttberg")]
    assert feb[0]["rubrik"].startswith("Överlämning av myndighetsutövning")
    assert feb[0]["sammantrade"]["id"] == sammantrade(api, "2026-02-23")["id"]
    datum = [r["sammantrade"]["datum"] for r in roster]
    assert datum == sorted(datum, reverse=True)
