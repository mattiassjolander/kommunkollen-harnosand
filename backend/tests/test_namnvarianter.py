"""Namnen i protokollen (#165): tom plats, tjänstgöring och roller i namnet, och namnvarianter.

Raderna är de som gav felaktiga namn i registret på servern 2026-11-26. Registret prövas mot kommunfullmäktiges
protokoll för 2026 (inspelade), med namnvarianter som läggs in i närvaron.
"""

from __future__ import annotations

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_ledamoter import ledamot
from test_protokoll import kf, kor

from app import db, namnvarianter
from app.protokolltolkning import (
    Narvaro, Tolkning, _narvaro_forsta_sidan, _rensa_narvaro, beslutande_vid, rensat_namn,
)

# Närvarolistan på första sidan, som i kommunstyrelsens protokoll: namnfältet i kolumn 44, rollen i kolumn 96.
SIDA = "\n".join(f"{etikett:<44}{namn:<52}{roll}".rstrip() for etikett, namn, roll in [
    ("Beslutande", "Jonas Bergström, ordförande", "Ordförande"),
    ("", "Britta Thyr, 1:e vice ordförande", "1:e vice ordförande"),
    ("", "Glenn Sehlin, §§ 131-138, 140-143", "Ledamot"),
    ("", "Tom plats för Ester Sundin Hemström", "Ledamot"),
    ("", "Ro Blomkvist tjänstgörande ersättare för Axel Bodo", "Ersättare"),
    ("", "Monica Fällström (S) för vakant plats efter Johan", "Ersättare"),
    ("", "Christian Wasell (M) för Charlotte Höglund Bystedt", "Ersättare"),
    ("", "(SD) § 50", ""),
    ("", "Christina Ögrim, ersätter Ingemar", "Ersättare"),
    ("", "Ljunggren §§ 131-137", ""),
    ("", "Olle Löfgren, ersätter Ingemar Ljunggren", "Ersättare"),
    ("", "§ 138", ""),
    ("Ej tjänstgörande", "Tobias Gillberg", "Ersättare"),
    ("Justerare", "Britta Thyr", ""),
])


def narvaro(sida: str) -> Tolkning:
    t = Tolkning()
    assert _narvaro_forsta_sidan(t, sida)
    _rensa_narvaro(t)
    return t


def test_bara_namnet_blir_namnet():
    t = narvaro(SIDA)
    poster = {(n.namn, n.tjanstgor_for): n for n in t.narvaro}
    assert {n.namn for n in t.narvaro} == {
        "Jonas Bergström", "Britta Thyr", "Glenn Sehlin", "Ester Sundin Hemström", "Ro Blomkvist",
        "Monica Fällström", "Christian Wasell", "Christina Ögrim", "Olle Löfgren", "Tobias Gillberg",
    }
    assert poster[("Jonas Bergström", None)].roll == "Ordförande"
    assert poster[("Britta Thyr", None)].roll == "1:e vice ordförande"
    assert poster[("Glenn Sehlin", None)].paragrafer == [*range(131, 139), *range(140, 144)]
    assert t.avvikelser == []


def test_en_tom_plats_ar_ingen_person():
    # "Tom plats för X": stolen var tom, och X räknas som frånvarande.
    [ester] = [n for n in narvaro(SIDA).narvaro if n.namn == "Ester Sundin Hemström"]
    assert (ester.kategori, ester.tom_plats, ester.tjanstgor_for) == ("franvarande", True, None)
    # Den som tjänstgör på en vakant plats tjänstgör inte för någon.
    [monica] = [n for n in narvaro(SIDA).narvaro if n.namn == "Monica Fällström"]
    assert (monica.parti, monica.kategori, monica.tjanstgor_for) == ("S", "beslutande", None)


# Kommunstyrelsen 2025-04-02 (#203): Christina Lindberg var jävig i § 50 och § 61, och hennes stol var tom.
TOM_STOL = "\n".join(f"{etikett:<44}{namn:<52}{roll}".rstrip() for etikett, namn, roll in [
    ("Beslutande", "Jonas Bergström (S), ordförande", "Ordförande"),
    ("", "Christina Lindberg (C) §§ 43-49, 51-60, 62-68", "Ledamot"),
    ("", "Tom stol Christina Lindberg (C) §§ 50, 61", ""),
    ("", "Britta Thyr (MP)", "Ledamot"),
    ("Justerare", "Britta Thyr", ""),
])


def test_tom_stol_vid_vissa_paragrafer_ar_ingen_person():
    t = narvaro(TOM_STOL)
    assert {n.namn for n in t.narvaro} == {"Jonas Bergström", "Christina Lindberg", "Britta Thyr"}
    [beslutande, tom] = [n for n in t.narvaro if n.namn == "Christina Lindberg"]
    assert (beslutande.kategori, beslutande.tom_plats, beslutande.paragrafer) == (
        "beslutande", False, [*range(43, 50), *range(51, 61), *range(62, 69)])
    assert (tom.parti, tom.kategori, tom.tom_plats, tom.paragrafer) == ("C", "franvarande", True, [50, 61])
    assert t.avvikelser == []


@pytest.mark.parametrize("paragraf, beslutande", [(49, True), (50, False), (51, True), (61, False), (62, True)])
def test_den_med_tom_stol_ar_inte_beslutande_vid_de_paragraferna(paragraf, beslutande):
    namn = {n.namn for n in beslutande_vid(narvaro(TOM_STOL).narvaro, paragraf)}
    assert ("Christina Lindberg" in namn) == beslutande
    assert {"Jonas Bergström", "Britta Thyr"} <= namn


def test_tjanstgoring_i_alla_skrivsatt():
    poster = {n.namn: n for n in narvaro(SIDA).narvaro}
    ro = poster["Ro Blomkvist"]
    assert (ro.roll, ro.kategori, ro.tjanstgor_for, ro.paragrafer) == ("Ersättare", "beslutande", "Axel Bodo", None)
    wasell = poster["Christian Wasell"]
    assert (wasell.parti, wasell.tjanstgor_for, wasell.tjanstgor_for_parti, wasell.paragrafer) == (
        "M", "Charlotte Höglund Bystedt", "SD", [50])
    # ", ersätter Ingemar" fortsätter på nästa rad.
    assert (poster["Christina Ögrim"].tjanstgor_for, poster["Christina Ögrim"].paragrafer) == (
        "Ingemar Ljunggren", [*range(131, 138)])
    assert (poster["Olle Löfgren"].tjanstgor_for, poster["Olle Löfgren"].paragrafer) == ("Ingemar Ljunggren", [138])


def test_en_rad_per_person_med_tjanstgoring_utan_parti():
    sida = "\n".join([
        "Beslutande          Ledamöter",
        "                    Anna Andersson (S), ordförande",
        "                    Ersättare",
        "                    Ro Blomkvist tjänstgörande ersättare för Axel Bodo",
        "Justerare           Anna Andersson",
    ])
    [anna, ro] = narvaro(sida).narvaro
    assert (anna.namn, anna.tjanstgor_for) == ("Anna Andersson", None)
    assert (ro.namn, ro.roll, ro.tjanstgor_for) == ("Ro Blomkvist", "Ersättare", "Axel Bodo")


@pytest.mark.parametrize("rad, namn", [
    ("Glenn Sehlin, §§ 131-138, 140-143", "Glenn Sehlin"),
    ("Britta Thyr, 1:e vice ordförande", "Britta Thyr"),
    ("Jonas Bergström, ordförande", "Jonas Bergström"),
    ("Christian Wasell (M) för Charlotte Höglund Bystedt (SD) § 50", "Christian Wasell"),
    ("Olle Löfgren, ersätter Ingemar Ljunggren", "Olle Löfgren"),
    ("Ro Blomkvist tjänstgörande ersättare för Axel Bodo", "Ro Blomkvist"),
    ("Tom plats för Ester Sundin Hemström", "Ester Sundin Hemström"),
    ("Tom stol Christina Lindberg (C) §§ 50, 61", "Christina Lindberg"),
    ("Monica Fällström (S) för vakant plats efter Johan Nilsson", "Monica Fällström"),
    ("Christina Ögrim, ersätter Ingemar", "Christina Ögrim"),
    ("Vakant plats efter Johan Nilsson", None),
    ("Charlotte Höglund-Bystedt", "Charlotte Höglund-Bystedt"),
])
def test_namnen_i_registret_pa_servern(rad, namn):
    assert rensat_namn(rad) == namn


def test_ett_avhugget_namn_kopplas_bara_till_en_enda_franvarande():
    def tolkning(*franvarande: str) -> Tolkning:
        t = Tolkning(narvaro=[Narvaro(namn="Christina Ögrim, ersätter Ingemar", parti=None, roll=None,
                                      kategori="beslutande")]
                     + [Narvaro(namn=n, parti="S", roll="Ledamot", kategori="franvarande") for n in franvarande])
        _rensa_narvaro(t)
        return t

    t = tolkning("Ingemar Ljunggren", "Anna Andersson")
    assert (t.narvaro[0].tjanstgor_for, t.narvaro[0].tjanstgor_for_parti, t.avvikelser) == ("Ingemar Ljunggren", "S", [])
    for t in (tolkning(), tolkning("Ingemar Ljunggren", "Ingemar Wiklander")):
        assert t.narvaro[0].tjanstgor_for == "Ingemar"  # som protokollet skriver, ingen gissning
        assert len(t.avvikelser) == 1 and "Ingemar" in t.avvikelser[0]


def test_ks_protokollet_med_radbrutna_ersattningar():
    from test_protokolltolkning import tolkning

    poster = {(n.namn, n.tjanstgor_for): n for n in tolkning("ks-2026-09-29-forsta-sidan.pdf").narvaro}
    assert poster[("Christina Ögrim", "Ingemar Wiklander")].paragrafer == [138]
    assert poster[("Olle Löfgren", "Ingemar Ljunggren")].roll == "Ersättare"


# Registret


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def lagg_till(database_url: str, namn: str, som: str, antal: int = 1, ny_lista: bool = False) -> None:
    """Lägger `namn` i närvaron vid `antal` sammanträden där `som` var med, med samma parti. Med `ny_lista` i
    stället vid sammanträden där `som` inte var med."""
    with db.connect(database_url) as conn:
        rader = conn.execute(
            f"""SELECT s.id, (SELECT parti FROM narvaro WHERE namn = %(som)s AND parti IS NOT NULL LIMIT 1) AS parti
                FROM sammantrade s WHERE {'NOT' if ny_lista else ''} EXISTS (
                    SELECT 1 FROM narvaro n WHERE n.sammantrade_id = s.id AND n.namn = %(som)s)
                AND EXISTS (SELECT 1 FROM narvaro n WHERE n.sammantrade_id = s.id)
                ORDER BY s.id LIMIT %(antal)s""",
            {"som": som, "antal": antal},
        ).fetchall()
        assert len(rader) == antal
        for r in rader:
            conn.execute(
                """INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori)
                   VALUES (%s, 1000, %s, %s, 'Ledamot', 'beslutande')""",
                (r["id"], namn, r["parti"]),
            )
        conn.execute("INSERT INTO ledamot (namn) VALUES (%s) ON CONFLICT DO NOTHING", (namn,))
        conn.commit()


def underhall(database_url: str) -> dict:
    with db.connect(database_url) as conn:
        plan = namnvarianter.underhall(conn)
        conn.commit()
    return plan


def test_bindestreck_och_mellanslag_slas_ihop_automatiskt(api, database_url):
    assert underhall(database_url) == {"borttagna": [], "sammanslagna": [], "forslag": []}
    lagg_till(database_url, "Carl Fredrik Edgren", som="Carl-Fredrik Edgren", antal=2)
    lagg_till(database_url, "Carl- Fredrik  Edgren", som="Carl-Fredrik Edgren")

    plan = underhall(database_url)
    # Huvudnamnet är den stavning som förekommer oftast (fem sammanträden).
    assert sorted(plan["sammanslagna"], key=lambda x: x["namn"]) == [
        {"namn": "Carl Fredrik Edgren", "huvudnamn": "Carl-Fredrik Edgren"},
        {"namn": "Carl- Fredrik  Edgren", "huvudnamn": "Carl-Fredrik Edgren"},
    ]
    p = ledamot(api, "Carl-Fredrik Edgren")
    assert p["andra_namn"] == ["Carl Fredrik Edgren", "Carl- Fredrik  Edgren"]
    assert underhall(database_url)["sammanslagna"] == []


def test_automatiken_slar_inte_ihop_det_en_redaktor_delat_upp(api, database_url):
    lagg_till(database_url, "Carl Fredrik Edgren", som="Carl-Fredrik Edgren")
    underhall(database_url)
    [namn] = [n for n in api.get(f"/api/ledamoter/{ledamot(api, 'Carl-Fredrik Edgren')['id']}").json()["namn_varianter"]
              if n["namn"] == "Carl Fredrik Edgren"]
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post(f"/api/ledamoter/{namn['id']}/uppdelning").status_code == 200

    assert underhall(database_url) == {"borttagna": [], "sammanslagna": [], "forslag": []}
    assert ledamot(api, "Carl-Fredrik Edgren")["andra_namn"] == []


def test_felaktiga_namn_tas_bort_och_det_rensade_namnet_foljer_med(api, database_url):
    # Som på servern före omtolkningen: felaktiga namn utan förekomster, varav ett sammanslaget som huvudnamn.
    knapp = ledamot(api, "Knapp Britta Thyr")
    with db.connect(database_url) as conn:
        fel = conn.execute("INSERT INTO ledamot (namn) VALUES ('Knapp Britta Thyr, 1:e vice ordförande'), "
                           "('Tom plats för Ester Sundin Hemström') RETURNING id").fetchall()
        conn.commit()
    assert api.post("/api/auth/test/redaktor").status_code == 200
    assert api.post(f"/api/ledamoter/{fel[0]['id']}/sammanslagningar", params={"med": knapp["id"]}).status_code == 200
    assert api.post(f"/api/ledamoter/{fel[0]['id']}/sammanslagningar",
                    params={"med": ledamot(api, "Britta Thyr")["id"]}).status_code == 200

    plan = underhall(database_url)
    assert sorted(x["namn"] for x in plan["borttagna"]) == [
        "Knapp Britta Thyr, 1:e vice ordförande", "Tom plats för Ester Sundin Hemström"]
    # Den redaktören slog ihop står kvar, med det namn som förekommer oftast som huvudnamn.
    p = ledamot(api, "Britta Thyr")
    assert p["andra_namn"] == ["Knapp Britta Thyr"]
    with db.connect(database_url) as conn:
        assert not conn.execute("SELECT 1 FROM ledamot WHERE namn LIKE 'Tom plats%' OR namn LIKE '%ordförande'").fetchall()
        # Historiken finns kvar.
        assert [r["typ"] for r in conn.execute(
            "SELECT typ FROM ledamot_handelse WHERE namn = 'Knapp Britta Thyr, 1:e vice ordförande'")] == ["borttagning"]
        assert [r["typ"] for r in conn.execute(
            "SELECT typ FROM ledamot_handelse WHERE namn = 'Knapp Britta Thyr' ORDER BY id")] == ["sammanslagning"]


def test_insamlingen_foreslar_namnvarianter_ur_protokollen(api):
    assert api.post("/api/auth/test/redaktor").status_code == 200
    forslag = {frozenset(n["namn"] for n in f["namn"]): f for f in api.get("/api/namnforslag").json()}
    assert {
        frozenset(("Runa Ödlund", "Runa Harriet Ödlund")),
        frozenset(("Elisabeth Hildén", "Elisabet Hildén")),
        frozenset(("Charlotte Bystedt", "Charlotte Höglund Bystedt")),
    } <= set(forslag)
    assert forslag[frozenset(("Elisabeth Hildén", "Elisabet Hildén"))]["skal"].startswith(
        "Samma förnamn och efternamn, med en liten skillnad i stavningen. Samma parti")


def test_mellannamn_blir_forslag_som_redaktionen_beslutar(api, database_url):
    # Samma förnamn och efternamn, samma parti, aldrig i samma närvarolista.
    lagg_till(database_url, "Carl Erik Fredrik Edgren", som="Carl-Fredrik Edgren", ny_lista=True)
    lagg_till(database_url, "Carl-Fredrik Edgrén", som="Carl-Fredrik Edgren", ny_lista=True)
    # I samma närvarolista som Britta Thyr: två personer, inget förslag.
    lagg_till(database_url, "Britta Maria Thyr", som="Britta Thyr")
    plan = underhall(database_url)
    assert plan["sammanslagna"] == []
    # De två nya namnen står i samma närvarolista och föreslås inte med varandra.
    assert {frozenset((x["namn"], x["annat_namn"])) for x in plan["forslag"]} == {
        frozenset(("Carl-Fredrik Edgren", "Carl Erik Fredrik Edgren")),
        frozenset(("Carl-Fredrik Edgren", "Carl-Fredrik Edgrén")),
    }

    assert api.get("/api/namnforslag").status_code == 401
    assert api.post("/api/auth/test/redaktor").status_code == 200
    forslag = api.get("/api/namnforslag").json()
    [mellan] = [f for f in forslag if {n["namn"] for n in f["namn"]} == {"Carl-Fredrik Edgren", "Carl Erik Fredrik Edgren"}]
    assert mellan["skal"].startswith("Samma förnamn och efternamn, olika mellannamn")
    assert mellan["namn"][0]["ledamot"]["antal_sammantraden"] in (1, 5)

    svar = api.post(f"/api/namnforslag/{mellan['id']}/bekrafta")
    assert svar.status_code == 200, svar.text
    assert svar.json()["status"] == "bekraftad"
    assert ledamot(api, "Carl-Fredrik Edgren")["andra_namn"] == ["Carl Erik Fredrik Edgren"]
    assert api.post(f"/api/namnforslag/{mellan['id']}/bekrafta").status_code == 409

    [stavning] = [f for f in api.get("/api/namnforslag").json() if "Carl-Fredrik Edgrén" in {n["namn"] for n in f["namn"]}]
    assert stavning["skal"].startswith("Samma förnamn och efternamn, med en liten skillnad i stavningen")
    assert api.post(f"/api/namnforslag/{stavning['id']}/avvisa").json()["status"] == "avvisad"
    # Ett avvisat förslag kommer inte tillbaka.
    assert underhall(database_url)["forslag"] == []
    assert stavning["id"] not in [f["id"] for f in api.get("/api/namnforslag").json()]
    assert [f["id"] for f in api.get("/api/namnforslag", params={"status": "avvisad"}).json()] == [stavning["id"]]


def test_provkorningen_sparar_ingenting(api, database_url, monkeypatch, capsys):
    from app import tolka_om

    with db.connect(database_url) as conn:
        conn.execute("INSERT INTO ledamot (namn) VALUES ('Tom plats för Ester Sundin Hemström')")
        conn.commit()
    monkeypatch.setenv("DATABASE_URL", database_url)
    tolka_om.main(["--prov"])
    ut = capsys.readouterr().out
    assert "Inget sparades" in ut
    assert "Tom plats för Ester Sundin Hemström" in ut
    assert "Namn som slås ihop automatiskt (0)" in ut
    with db.connect(database_url) as conn:
        assert conn.execute("SELECT 1 FROM ledamot WHERE namn = 'Tom plats för Ester Sundin Hemström'").fetchone()


def test_sammantradet_visar_tom_plats(api, database_url):
    with db.connect(database_url) as conn:
        s = conn.execute("SELECT sammantrade_id FROM narvaro WHERE namn = 'Carl-Fredrik Edgren' LIMIT 1").fetchone()
        conn.execute("""INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori, tom_plats)
                        VALUES (%s, 1000, 'Tora Tomplatsson', 'M', 'Ledamot', 'franvarande', true)""",
                     (s["sammantrade_id"],))
        conn.commit()
    narvaro = api.get(f"/api/sammantraden/{s['sammantrade_id']}").json()["narvaro"]
    [tora] = [p for p in narvaro if p["namn"] == "Tora Tomplatsson"]
    assert (tora["kategori"], tora["tom_plats"]) == ("franvarande", True)
    assert not any("tom_plats" in p for p in narvaro if p["namn"] != "Tora Tomplatsson")


def test_ledamotens_sida_visar_inte_tom_stol_som_beslutande(api, database_url):
    # "Tom stol Namn §§ 50, 61" (#203): på ledamotens sida är hon beslutande vid de andra paragraferna.
    with db.connect(database_url) as conn:
        s = conn.execute("SELECT sammantrade_id FROM narvaro WHERE namn = 'Carl-Fredrik Edgren' LIMIT 1").fetchone()
        conn.execute("INSERT INTO ledamot (namn) VALUES ('Tora Tomstolsson')")
        conn.execute("""INSERT INTO narvaro (sammantrade_id, ordning, namn, parti, roll, kategori, paragrafer, tom_plats)
                        VALUES (%(s)s, 1000, 'Tora Tomstolsson', 'C', 'Ledamot', 'beslutande', '{49,51}', false),
                               (%(s)s, 1001, 'Tora Tomstolsson', 'C', NULL, 'franvarande', '{50}', true)""",
                     {"s": s["sammantrade_id"]})
        conn.commit()
    [forekomst] = api.get(f"/api/ledamoter/{ledamot(api, 'Tora Tomstolsson')['id']}").json()["sammantraden"]
    assert (forekomst["kategori"], forekomst["paragrafer"]) == ("beslutande", [49, 51])
