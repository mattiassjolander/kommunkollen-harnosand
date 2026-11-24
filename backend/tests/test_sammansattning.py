"""Sammansättning: kön och ålder bland kandidater, valda och tjänstgörande (#65).

Valmyndighetens filer är inspelade med bara Härnösands rader (kommunfullmäktige). 2022 års filer har CR som
radslut och en stämpelrad först, och 2022 års kandidaturer är gallrade. Kommunfullmäktiges protokoll ger
ledamotsregistret som valet kopplas till.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf
from test_rattelser import logga_in

from app import db, sammansattning
from app.sources.valmyndigheten import (Valdata, Valmyndigheten, las_csv, tolka_ersattare, tolka_kandidaturer,
                                        tolka_ledamoter, tolka_rostberattigade)

VAL = INSPELNINGAR / "valmyndigheten"


def fil(namn: str) -> bytes:
    return (VAL / namn).read_bytes()


# Tolkning av filerna

def test_csv_med_cr_stampelrad_och_bom():
    stampel, rader = las_csv("﻿;Valmyndigheten 2026-10-30 15:51:49\rA;B\r1;2\r\r3;4\r".encode())
    assert stampel == "Valmyndigheten 2026-10-30 15:51:49"
    assert rader == [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}]
    # Utan stämpel och med CRLF, som kandidaturerna 2026.
    assert las_csv("﻿A;B\r\n1;2\r\n".encode()) == (None, [{"A": "1", "B": "2"}])


def test_valda_2026_enligt_facit():
    stampel, rader = tolka_ledamoter(fil("ledamoter_med_historik_2026.csv"))
    assert stampel.startswith("Valmyndigheten 2026-")
    assert len(rader) == 43
    assert sum(r["kon"] == "K" for r in rader) == 22 and sum(r["kon"] == "M" for r in rader) == 21
    assert round(sum(r["alder"] for r in rader) / len(rader), 1) == 49.3
    per_parti = {}
    for r in rader:
        k, m = per_parti.get(r["parti"], (0, 0))
        per_parti[r["parti"]] = (k + (r["kon"] == "K"), m + (r["kon"] == "M"))
    # Norrlandspartiet heter NorrP hos Valmyndigheten och NP på plattformen.
    assert per_parti == {"C": (2, 2), "KD": (0, 1), "L": (0, 1), "M": (5, 4), "MP": (3, 2), "NP": (2, 1),
                         "S": (6, 7), "SD": (2, 2), "V": (2, 1)}


def test_valda_2022_har_eftertradare_med_datum():
    _, rader = tolka_ledamoter(fil("ledamoter_med_historik_2022.csv"))
    assert len(rader) == 57
    gafvert = next(r for r in rader if r["namn"] == "Anders Gäfvert")
    bolander = next(r for r in rader if r["namn"] == "Frans Lennart Bolander")
    assert (gafvert["avgang"], gafvert["mandat"], gafvert["personvald"]) == (date(2022, 11, 25), 1, True)
    assert (bolander["invald"], bolander["mandat"], bolander["avgang"]) == (date(2022, 11, 25), 1, None)


def test_kandidaturer_2026_enligt_facit():
    rader = tolka_kandidaturer(fil("kandidaturer_2026.zip"))
    assert len(rader) == 182
    assert sum(r["kon"] == "K" for r in rader) == 76 and sum(r["kon"] == "M" for r in rader) == 105
    [utan] = [r for r in rader if r["kon"] is None]
    assert utan["parti"] == "NP" and not utan["giltig"]
    # En kandidat som skrivits till med efternamnet först.
    assert any(r["namn"] == "Sandin, Rosmarie" and r["ordning"] is None for r in rader)


def test_kandidaturer_2022_ar_gallrade():
    rader = tolka_kandidaturer(fil("kandidaturer_2022.zip"))
    assert len(rader) == 179
    assert all(r["namn"] is None and r["kon"] is None and r["alder"] is None for r in rader)
    assert rader[0]["gallrade"] == {"namn", "alder", "kon", "folkbokforingskommun"}


def test_filtrerar_pa_kolumner_och_inte_pa_hela_raden():
    rubrik = ("VALTYP;VALOMRÅDESKOD;PARTIFÖRKORTNING;ORDNING;KANDIDATNUMMER;NAMN;ÅLDER_PÅ_VALDAGEN;KÖN;"
              "FOLKBOKFÖRINGSKOMMUN;GILTIG")
    csv = "\r\n".join([
        rubrik,
        "RD;00;S;1;2280;Annan Person;50;K;Härnösand;J",   # kandidatnummer 2280 i riksdagsvalet
        "KF;2281;S;1;12;Grannkommun;40;M;Sundsvall;J",
        "KF;2280;S;1;13;Rätt Person;30;K;Härnösand;J",
    ]).encode()
    assert [r["namn"] for r in tolka_kandidaturer(csv)] == ["Rätt Person"]


def test_ersattare_och_rostberattigade():
    stampel, ersattare = tolka_ersattare(fil("ledamoter_och_ersattare_utokad_2026.csv"))
    assert stampel and len(ersattare) == 183
    assert {(e["ersattargrupp"], e["ersattarordning"]) for e in ersattare if e["namn"] == "Ted Sundin"} >= {(1, 1)}
    stampel, rb = tolka_rostberattigade(fil("rostberattigade_2026.xlsx"))
    assert stampel == "Valmyndigheten 2026-09-18"
    assert rb == {"kvinnor": 9773, "man": 9707, "a18_29": 2631, "a30_49": 5615, "a50_64": 4474, "a65": 6760,
                  "totalt": 19480}


# Insamling, lagring och statistik

@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[*kf(), Valmyndigheten(anrop_per_sekund=None)],
                             anonym_lasning=True))
    logga_in(a, "redaktor")
    svar = a.post("/api/insamlingar")
    assert svar.status_code == 200 and svar.json()["status"] == "lyckad", svar.text
    logga_in(a, None)
    return a


def statistik(api, period=2026, organ="KF") -> dict:
    svar = api.get("/api/sammansattning", params={"period": period, "organ": organ})
    assert svar.status_code == 200, svar.text
    return svar.json()


def kopplingar(database_url) -> dict[tuple[int, str], tuple[str, str, str]]:
    """(valår, namn i valet) → (status, skäl, namn i registret)."""
    with db.connect(database_url) as conn:
        return {(k["val"]["valar"], k["val"]["namn"]): (k["status"], k["skal"], k["ledamot"]["namn"])
                for k in sammansattning.kopplingar(conn)}


def test_valda_och_kandidater_enligt_facit(api):
    s = statistik(api)
    assert (s["period"]["namn"], s["organ"]["id"]) == ("2026–2030", "KF")
    valda = s["valda"]["med_eftertradare"]["totalt"]
    assert (valda["antal"], valda["kvinnor"], valda["man"], valda["kon_saknas"], valda["medelalder"]) == (
        43, 22, 21, 0, 49.3)
    per_parti = {p["parti"]: (p["kvinnor"], p["man"]) for p in s["valda"]["vid_start"]["per_parti"]}
    assert per_parti["NP"] == (2, 1) and per_parti["S"] == (6, 7) and per_parti["KD"] == (0, 1)
    assert sum(s["valda"]["vid_start"]["totalt"]["aldersgrupper"].values()) == 43

    kand = s["kandidater"]["alla"]["totalt"]
    assert (kand["antal"], kand["kvinnor"], kand["man"], kand["kon_saknas"]) == (182, 76, 105, 1)
    assert all(p["antal"] <= 10 for p in s["kandidater"]["topp"]["per_parti"])
    assert s["kandidater"]["alla"]["kallor"][0]["url"].endswith("/val2026/parti/kandidaturer.zip")
    assert s["valda"]["vid_start"]["kallor"][0]["stampel"].startswith("Valmyndigheten")
    assert s["konstext"] == "Kön enligt folkbokföringen (Valmyndigheten)"

    # De röstberättigade är referens.
    assert s["referens"]["antal"] == 19480 and s["referens"]["andel_kvinnor"] == round(9773 / 19480, 4)


def test_2022_har_gallrade_kandidater_och_valda_med_eftertradare(api):
    s = statistik(api, 2022)
    assert s["valda"]["med_eftertradare"]["totalt"]["antal"] == 57
    assert s["valda"]["vid_start"]["totalt"]["antal"] == 57 - sum(
        1 for r in tolka_ledamoter(fil("ledamoter_med_historik_2022.csv"))[1] if r["invald"])
    # Kandidaternas uppgifter är gallrade. De valda har kön genom kandidatnumret, resten saknar uppgift.
    kand = s["kandidater"]["alla"]["totalt"]
    assert kand["antal"] == 179 and kand["kon_saknas"] > 100 and kand["kvinnor"] + kand["man"] >= 50
    assert s["kandidater"]["topp"] is None
    # Tjänstgörande enligt närvarolistorna, viktat med sammanträdena.
    t = s["tjanstgorande"]
    assert t["totalt"]["antal"] > t["personer"] > 0 and t["sammantraden"] > 0
    assert t["kallor"][0]["titel"] == "Protokollens närvarolistor"


def test_nämnder_saknas_i_valets_filer(api):
    s = statistik(api, 2022, "SOC")
    assert s["kandidater"] is None and s["valda"]["vid_start"] is None
    assert api.get("/api/sammansattning", params={"period": 2018}).status_code == 422
    assert api.get("/api/sammansattning", params={"organ": "XX"}).status_code == 422


def test_koppling_exakt_mellannamn_och_samma_namn_i_tva_partier(api, database_url):
    k = kopplingar(database_url)
    # Exakt namn och parti, och bara en person: automatisk.
    assert k[(2026, "Ted Sundin")] == ("automatisk", "Samma namn och parti", "Ted Sundin")
    # Mellannamn: ett förslag.
    assert k[(2026, "Margareta Tjernlund")] == (
        "forslag", "Liknande namn (mellannamn eller dubbelnamn)", "Sigrid Margareta Tjernlund")
    # Protokollen anger två partier för personen: ett förslag.
    assert k[(2026, "Natalia Sjöberg")][0] == "forslag"

    # Samma namn i två partier i valet: båda blir förslag.
    with db.connect(database_url) as conn:
        kandidat = {"kandidatnummer": 999001, "parti": "KD", "listnummer": "1", "ordning": 30, "namn": "Ted Sundin",
                    "alder": 40, "kon": "M", "folkbokforingskommun": "Härnösand", "giltig": True, "gallrade": set()}
        sammansattning.lagra(conn, Valdata(2026, kandidater=[kandidat]), None, datetime.now(timezone.utc))
        sammansattning.koppla(conn)
        conn.commit()
        ted = [x for x in sammansattning.kopplingar(conn) if x["val"]["namn"] == "Ted Sundin" and x["val"]["valar"] == 2026]
    assert {(x["val"]["parti"], x["status"], x["skal"]) for x in ted} == {
        ("M", "forslag", "Samma namn för flera kandidater 2026"),
        ("KD", "forslag", "Samma namn för flera kandidater 2026")}


def test_redaktoren_bekraftar_och_avvisar_forslag(api, database_url):
    forslag = [x for x in api_som(api, "redaktor").get(
        "/api/sammansattning/kopplingar", params={"status": "forslag"}).json() if x["val"]["valar"] == 2026]
    fore = {p["id"]: p for p in api.get("/api/sammansattning/personer").json()}
    # Ett förslag ger inget kön till personen förrän det är bekräftat.
    utan = next(x for x in forslag if fore[x["ledamot"]["id"]]["kalla"] is None and x["val"]["kon"])
    natalia = next(x for x in forslag if x["val"]["namn"] == "Natalia Sjöberg")

    svar = api.post(f"/api/sammansattning/kopplingar/{utan['id']}/bekraftelse")
    assert svar.status_code == 200 and svar.json()["beslutad_av"] == "test-redaktor@kommunkollen.test"
    assert api.post(f"/api/sammansattning/kopplingar/{natalia['id']}/avvisning").status_code == 200
    assert api.post(f"/api/sammansattning/kopplingar/{natalia['id']}/bekraftelse").status_code == 409
    efter = {p["id"]: p for p in api.get("/api/sammansattning/personer").json()}
    assert (efter[utan["ledamot"]["id"]]["kon"], efter[utan["ledamot"]["id"]]["kalla"]) == (
        utan["val"]["kon"], "valmyndigheten")
    # En utgivare utan rollen redaktör beslutar inte om kopplingar.
    logga_in(api, "utgivare")
    assert api.post(f"/api/sammansattning/kopplingar/{natalia['id']}/avvisning").status_code == 403

    # Besluten står kvar när kopplingarna räknas om vid nästa insamling.
    with db.connect(database_url) as conn:
        sammansattning.koppla(conn)
        conn.commit()
    k = kopplingar(database_url)
    assert k[(2026, utan["val"]["namn"])][0] == "bekraftad"
    assert k[(2026, "Natalia Sjöberg")][0] == "avvisad"


def api_som(api, roll):
    logga_in(api, roll)
    return api


def test_gallrad_uppgift_skriver_inte_over_det_sparade(api, database_url):
    fore = statistik(api)["kandidater"]["alla"]["totalt"]
    gallrade = copy.deepcopy(tolka_kandidaturer(fil("kandidaturer_2026.zip")))
    for k in gallrade:
        k.update(namn=None, alder=None, kon=None, folkbokforingskommun=None,
                 gallrade={"namn", "alder", "kon", "folkbokforingskommun"})
    with db.connect(database_url) as conn:
        antal = sammansattning.lagra(conn, Valdata(2026, kandidater=gallrade), None, datetime.now(timezone.utc))
        conn.commit()
        assert antal == {"nya": 0, "andrade": 0, "oforandrade": 182}
        rad = conn.execute("SELECT namn, kon, alder, gallrad FROM valkandidat WHERE valar = 2026 "
                           "AND namn = 'Jonas Bergström'").fetchone()
        assert (rad["kon"], rad["alder"]) == ("M", 36) and rad["gallrad"] is not None
        assert conn.execute("SELECT count(*) AS n FROM valandring").fetchone()["n"] == 0
    assert statistik(api)["kandidater"]["alla"]["totalt"] == fore


def test_en_ny_eftertradare_blir_en_reviderad_uppgift(api, database_url):
    _, ledamoter = tolka_ledamoter(fil("ledamoter_med_historik_2026.csv"))
    avgar = next(r for r in ledamoter if r["namn"] == "Jonas Bergström")
    avgar["avgang"] = date(2027, 3, 1)
    ny = avgar | {"kandidatnummer": 999002, "namn": "Ny Eftertradare", "invald": date(2027, 3, 1), "avgang": None,
                  "kon": "K", "alder": 30}
    with db.connect(database_url) as conn:
        antal = sammansattning.lagra(conn, Valdata(2026, ledamoter=[*ledamoter, ny]), None, datetime.now(timezone.utc))
        conn.commit()
        assert (antal["nya"], antal["andrade"]) == (1, 1)
        [andring] = conn.execute("SELECT tabell, falt, tidigare, nytt FROM valandring").fetchall()
    assert andring == {"tabell": "valledamot", "falt": "avgang", "tidigare": None, "nytt": "2027-03-01"}
    s = statistik(api)["valda"]
    assert (s["vid_start"]["totalt"]["antal"], s["med_eftertradare"]["totalt"]["antal"]) == (43, 44)


def test_en_andra_insamling_ger_inga_nya_uppgifter(api):
    logga_in(api, "redaktor")
    svar = api.post("/api/insamlingar", params={"kalla": "valmyndigheten"}).json()
    [kalla] = svar["kallor"]
    assert kalla["status"] == "inga_nya" and kalla["antal_oforandrade"] > 0


def _nycklar(v) -> set[str]:
    if isinstance(v, dict):
        return set(v) | set().union(*(_nycklar(x) for x in v.values()))
    if isinstance(v, list):
        return set().union(*(_nycklar(x) for x in v)) if v else set()
    return set()


def test_det_publika_api_t_lamnar_inte_ut_kon_och_alder_per_person(api):
    logga_in(api, None)
    ted = next(p for p in api.get("/api/ledamoter", params={"q": "Ted Sundin"}).json() if p["namn"] == "Ted Sundin")
    person = api.get(f"/api/ledamoter/{ted['id']}").json()
    assert not _nycklar(person) & {"kon", "alder", "fodelsear", "sammansattning"}
    assert not _nycklar(api.get("/api/ledamoter").json()) & {"kon", "alder", "fodelsear"}
    # Statistiken innehåller inga namn.
    assert "Ted Sundin" not in api.get("/api/sammansattning").text
    for url in ("/api/sammansattning/personer", "/api/sammansattning/kopplingar", "/api/sammansattning/uppgifter"):
        assert api.get(url).status_code == 401, url
    logga_in(api, "lasare")
    assert api.get("/api/sammansattning/personer").status_code == 403


def test_redaktionens_uppgift_med_kalla_och_granskning(api):
    logga_in(api, "redaktor+utgivare")
    personer = api.get("/api/sammansattning/personer").json()
    utan = next(p for p in personer if p["kalla"] is None and not p["kopplingar"])
    med = next(p for p in personer if p["kalla"] == "valmyndigheten")
    fore = statistik(api, 2022)["tjanstgorande"]["totalt"]

    ny = {"ledamot_id": utan["id"], "kon": "K", "fodelsear": 1970,
          "kalla": "https://example.se/kandidatlista.pdf, sida 3"}
    assert api.post("/api/sammansattning/uppgifter", json=ny | {"kalla": ""}).status_code == 422
    assert api.post("/api/sammansattning/uppgifter", json=ny | {"kon": "X"}).status_code == 422
    assert api.post("/api/sammansattning/uppgifter", json=ny | {"ledamot_id": med["id"]}).status_code == 409
    svar = api.post("/api/sammansattning/uppgifter", json=ny)
    assert svar.status_code == 201, svar.text
    u = svar.json()
    assert (u["status"], u["ledamot"]["id"]) == ("utkast", utan["id"])

    # Ingen godkänner sin egen registrering.
    egen = api.post(f"/api/sammansattning/uppgifter/{u['id']}/granskning")
    assert (egen.status_code, egen.json()["detail"]) == (403, "Ingen godkänner sin egen registrering")
    # Ett utkast räknas inte.
    assert statistik(api, 2022)["tjanstgorande"]["totalt"] == fore

    logga_in(api, "utgivare")
    assert api.post(f"/api/sammansattning/uppgifter/{u['id']}/publicering").status_code == 409
    assert api.post(f"/api/sammansattning/uppgifter/{u['id']}/granskning").status_code == 200
    pub = api.post(f"/api/sammansattning/uppgifter/{u['id']}/publicering").json()
    assert (pub["status"], pub["publicerad_av"]) == ("publicerad", "test-utgivare@kommunkollen.test")

    p = next(p for p in api.get("/api/sammansattning/personer").json() if p["id"] == utan["id"])
    assert (p["kon"], p["kalla"]) == ("K", "redaktionen")
    efter = statistik(api, 2022)["tjanstgorande"]["totalt"]
    if fore["kon_saknas"]:
        assert efter["kvinnor"] >= fore["kvinnor"] and efter["kon_saknas"] <= fore["kon_saknas"]

    # En utgivare kan återkalla uppgiften med motivering.
    assert api.post(f"/api/sammansattning/uppgifter/{u['id']}/aterkallelse", json={}).status_code == 422
    assert api.post(f"/api/sammansattning/uppgifter/{u['id']}/aterkallelse",
                    json={"motivering": "Fel person"}).json()["status"] == "aterkallad"
    assert statistik(api, 2022)["tjanstgorande"]["totalt"] == fore

