"""Yrkanden, voteringar och reservationer ur protokollen (#31).

Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade). De förväntade värdena
är kontrollerade för hand mot voteringslistorna i protokollen.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf, kor

from app.protokolltolkning import Rost, Votering, tolka


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
    assert "§ 112, votering 1: voteringslistan har 20 ja, 18 nej, protokollets text 21 ja, 18 nej" in s["avvikelser"]
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


# Voteringslistor i arkivet 2022–2026. PDF:erna i tests/fixtures/protokoll är ett urval av sidorna
# i kommunens protokoll: början, med närvaro- och voteringslistan, och paragraferna med voteringar.
# De förväntade värdena är kontrollerade för hand mot listorna.

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def voteringar(namn: str) -> tuple[dict[int, list[Votering]], list[str]]:
    t = tolka((FIXTURER / namn).read_bytes())
    ut: dict[int, list[Votering]] = {}
    for b in t.behandlingar:
        ut.setdefault(b.paragraf, []).extend(b.voteringar)
    return ut, [a for a in t.avvikelser if "votering" in a]


def antal(v: Votering) -> tuple[int, int, int, int]:
    c = Counter(r.rost for r in v.roster)
    return c["ja"], c["nej"], c["avstar"], c["franvarande"]


def roster_for(v: Votering, namn: str) -> Rost:
    [r] = [r for r in v.roster if r.namn == namn]
    return r


def test_flera_voteringar_bredvid_varandra_i_narvarolistan():
    # KF 2024-05-27: "Vot § 61", "Vot § 63", "Vot § 64" i närvaro- och voteringslistan. Rubrikerna
    # står inte ovanför kryssen, så kolumnerna läses ur kryssen själva.
    v, avvikelser = voteringar("kf-2024-05-27-urval.pdf")
    assert antal(v[61][0]) == (34, 8, 1, 0)
    assert antal(v[64][0]) == (30, 7, 1, 5)
    # Flera ersättare vid olika paragrafer i samma ruta: "Brendan Mc Carthy §§ 57-61, 64-65, 67-76",
    # "Anne-Cathrine Genberg § 63", "Hans Rosengren § 66".
    assert roster_for(v[61][0], "Brendan Mc Carthy").ersatt == "Monika Lindberg"
    assert roster_for(v[63][0], "Anne-Cathrine Genberg").ersatt == "Monika Lindberg"
    # Paragrafer som bryts över kolumner och rader: "§§ 57-         61, 65-68, 70-          76".
    assert roster_for(v[61][0], "Monika Israelsson").ersatt == "Björn Höglund"
    assert roster_for(v[64][0], "Björn Höglund").rost == "franvarande"  # "tom stol §§ 63- 64, 69"
    # § 63: listan har en frånvarande mer än texten. Den visas som den står.
    assert avvikelser == [
        "§ 63, votering 1: voteringslistan har 21 ja, 16 nej, 1 avstår, 5 frånvarande, "
        "protokollets text 22 ja, 16 nej, 1 avstår, 4 frånvarande"
    ]

    # KF 2023-06-19: tom stol vid §§ 91-96 och en ersättare vid §§ 97-115 på samma plats.
    v, avvikelser = voteringar("kf-2023-06-19-urval.pdf")
    assert avvikelser == []
    assert antal(v[96][0]) == (22, 18, 2, 1)
    assert antal(v[98][0]) == (31, 12, 0, 0)
    assert roster_for(v[96][0], "Elisabeth Strömquist").rost == "franvarande"
    assert roster_for(v[98][0], "Martin Brendan McCarthy").ersatt == "Elisabeth Strömquist"
    assert roster_for(v[96][0], "Martin Brendan McCarthy").ersatt == "Andreas Sjölander"


def test_rubriker_over_flera_rader_och_tva_voteringar_i_samma_paragraf():
    # KF 2024-10-21: "Vot § 123, p.4" och "Vot § 123" (p.5) med Ja/Nej på olika rader, och
    # "propositi onsordning" delat i textlagret.
    v, avvikelser = voteringar("kf-2024-10-21-urval.pdf")
    assert avvikelser == []
    assert antal(v[118][0]) == (23, 17, 2, 1)
    assert [antal(x) for x in v[123]] == [(25, 17, 0, 1), (27, 14, 1, 1)]
    assert roster_for(v[123][1], "Ulrika Sundgren").rost == "ja"
    assert roster_for(v[123][0], "Ulrika Sundgren").rost == "nej"

    # KF 2024-12-16: "Vot §" med numret på raden under, och "§§ 150-154, 156.169".
    v, avvikelser = voteringar("kf-2024-12-16-urval.pdf")
    assert avvikelser == []
    assert antal(v[153][0]) == (23, 18, 1, 1)
    assert antal(v[158][0]) == (23, 19, 0, 1)


def test_avstavade_rubriker_och_ny_indragning_pa_nasta_sida():
    # KF 2025-06-16: "Part"/"i" och "När"/"var"/"o". Sista raderna står på en ny sida med annan
    # indragning. Ett kryss på en tom stol räknas inte, som i protokollets text.
    v, avvikelser = voteringar("kf-2025-06-16-urval.pdf")
    assert avvikelser == []
    assert [antal(x) for x in v[93]] == [(4, 6, 32, 1), (25, 8, 9, 1)]
    assert antal(v[96][0]) == (25, 17, 0, 1)
    assert roster_for(v[96][0], "Kristoffer Bodin").rost == "nej"
    assert roster_for(v[93][1], "Björn Höglund").rost == "franvarande"


def test_rostord_i_listan():
    # KF 2025-05-26: "avstår" med liten bokstav. KF 2022-09-26: "Avstår" och "Ej röstat".
    v, avvikelser = voteringar("kf-2025-05-26-urval.pdf")
    assert avvikelser == []
    assert antal(v[73][0]) == (23, 18, 2, 0)
    assert roster_for(v[73][0], "Natalia Sjöberg").rost == "avstar"

    v, avvikelser = voteringar("kf-2022-09-26-urval.pdf")
    assert avvikelser == []
    assert antal(v[81][0]) == (13, 21, 3, 6)
    kranz = roster_for(v[81][0], "Lillian Kranz")
    assert (kranz.rost, kranz.ersatt) == ("franvarande", "Anders Nordström")


def test_namndernas_listor():
    # Samhällsnämnden 2024-09-26: "Med 6 stycken ja-röster mot 4 stycken nej-röster", och "§ 121 Ja Nej"
    # i tabellhuvudet som inte är ett antal. Texten nämner inte den som avstod.
    v, avvikelser = voteringar("sam-2024-09-26-urval.pdf")
    assert avvikelser == []
    [x] = v[121]
    assert (x.ja, x.nej, x.avstar) == (6, 4, None)
    assert antal(x) == (6, 4, 1, 0)

    # Samhällsnämnden 2022-10-13: Ja och Nej står långt till höger om kryssen. En ersättare från ett
    # annat parti står med sitt parti: "Keith Bryant (V)" på en plats för S.
    v, avvikelser = voteringar("sam-2022-10-13-urval.pdf")
    assert avvikelser == []
    assert antal(v[166][0]) == (7, 4, 0, 0)
    bryant = roster_for(v[166][0], "Keith Bryant")
    assert (bryant.parti, bryant.ersatt, bryant.ersatt_parti) == ("V", "Anne-Cathrine Genberg", "S")

    # Skolnämnden 2026-04-01: "Namn" och "Röst" med JA och NEJ, och "tjänstgörande ersättare för".
    v, avvikelser = voteringar("skol-2026-04-01-urval.pdf")
    assert avvikelser == []
    assert antal(v[33][0]) == (7, 4, 0, 0)
    abdi = roster_for(v[33][0], "Naima Jamal Abdi")
    assert (abdi.parti, abdi.rost, abdi.ersatt, abdi.ersatt_parti) == ("MP", "ja", "Mattias Sjölander", "MP")
