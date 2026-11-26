"""Granskade protokoll (#176).

En redaktör eller utgivare markerar ett helt protokoll som granskat, och läsaren ser datumet. Granskningen
upphör om en omtolkning ändrar någon uppgift, och kan tas tillbaka med en motivering. Rättelser som inte är
publicerade spärrar granskningen. Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade).
"""

from __future__ import annotations

from datetime import datetime, timezone

from test_rattelser import api, logga_in, sammantrade_id, skapa  # noqa: F401 (fixturen api)

from app import db, kalender, protokollgranskning
from app.protokoll import tolka_om

DATUM = "2026-06-15"


def granskad_for_lasaren(api, s: int):
    logga_in(api, None)
    lista = next(x for x in api.get("/api/sammantraden?organ=KF").json() if x["id"] == s)
    sidan = api.get(f"/api/sammantraden/{s}").json()
    paragraf = sidan["behandlingar"][0]["paragraf"]
    behandling = api.get(f"/api/sammantraden/{s}/behandlingar/{paragraf}").json()
    assert lista["granskad"] == sidan["granskad"] == behandling["sammantrade"]["granskad"]
    return sidan["granskad"]


def test_redaktionen_granskar_och_lasaren_ser_datumet(api):
    s = sammantrade_id(api, DATUM)
    assert granskad_for_lasaren(api, s) is None

    # Bara redaktörer och utgivare granskar.
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 401
    assert api.get(f"/api/sammantraden/{s}/granskning").status_code == 401
    logga_in(api, "lasare")
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 403
    assert api.get(f"/api/sammantraden/{s}/granskning").status_code == 403
    assert api.post(f"/api/sammantraden/{s}/granskning/aterkallelse", json={"motivering": "x"}).status_code == 403

    # En person räcker, också en utgivare.
    logga_in(api, "utgivare")
    fore = api.get(f"/api/sammantraden/{s}/granskning").json()
    assert (fore["gallande"], fore["kan_granskas"], fore["logg"]) == (None, True, [])
    svar = api.post(f"/api/sammantraden/{s}/granskning")
    assert svar.status_code == 200, svar.text
    g = svar.json()
    assert (g["gallande"]["status"], g["gallande"]["granskad_av"]) == ("gallande", "test-utgivare@kommunkollen.test")
    assert g["kan_granskas"] is False
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 409

    # Läsaren ser datumet men inte vem som granskade.
    datum = granskad_for_lasaren(api, s)
    assert datum == datetime.fromisoformat(g["gallande"]["granskad"]).astimezone(kalender.TZ).date().isoformat()
    assert "granskad_av" not in str(api.get(f"/api/sammantraden/{s}").json())


def test_oppna_rattelser_sparrar_och_avvikelser_varnar(api):
    s = sammantrade_id(api, DATUM)
    logga_in(api, "redaktor")
    r = skapa(api, sammantrade_id=s, objekt="behandling", paragraf=109, falt="beslut", nytt="Antas.",
              motivering="Sidan 12.")
    g = api.get(f"/api/sammantraden/{s}/granskning").json()
    assert g["kan_granskas"] is False
    assert [x["id"] for x in g["oppna_rattelser"]] == [r["id"]]
    svar = api.post(f"/api/sammantraden/{s}/granskning")
    assert svar.status_code == 409
    assert "rättelser som inte är publicerade" in svar.json()["detail"]

    # En granskad rättelse väntar på publicering och spärrar också.
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/granskning").status_code == 200
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 409
    assert api.post(f"/api/rattelser/{r['id']}/publicering").status_code == 200

    # Avvikelserna stoppar inte granskningen.
    logga_in(api, "redaktor")
    g = api.get(f"/api/sammantraden/{s}/granskning").json()
    assert isinstance(g["avvikelser"], list)
    assert g["kan_granskas"] is True
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 200


def test_en_omtolkning_utan_andringar_behaller_granskningen(api, database_url):
    s = sammantrade_id(api, DATUM)
    logga_in(api, "redaktor")
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 200
    with db.connect(database_url) as conn:
        fore = protokollgranskning.fingeravtryck(conn, s)
        tolka_om(conn, datetime.now(timezone.utc))
        assert protokollgranskning.fingeravtryck(conn, s) == fore
    g = api.get(f"/api/sammantraden/{s}/granskning").json()
    assert g["gallande"] is not None
    assert g["andrad_efter_granskning"] is False
    assert granskad_for_lasaren(api, s) is not None


def test_en_omtolkning_som_andrar_en_uppgift_tar_bort_granskningen(api, database_url):
    s = sammantrade_id(api, DATUM)
    # Tolkningen vid granskningen hade en annan rubrik för § 109 än den nuvarande tolkningen ger.
    with db.connect(database_url) as conn:
        conn.execute("UPDATE behandling SET rubrik = 'En äldre tolkning' WHERE sammantrade_id = %s AND paragraf = 109",
                     (s,))
    logga_in(api, "redaktor")
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 200
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))

    g = api.get(f"/api/sammantraden/{s}/granskning").json()
    assert g["gallande"] is None
    assert g["andrad_efter_granskning"] is True
    assert [x["status"] for x in g["logg"]] == ["andrad"]
    assert g["logg"][0]["andrad"] is not None
    assert granskad_for_lasaren(api, s) is None

    # Protokollet kan granskas igen, och då gäller den nya tolkningen.
    logga_in(api, "redaktor")
    g = api.post(f"/api/sammantraden/{s}/granskning").json()
    assert g["andrad_efter_granskning"] is False
    assert [x["status"] for x in g["logg"]] == ["gallande", "andrad"]


def test_granskningen_tas_tillbaka_med_motivering_och_loggas(api):
    s = sammantrade_id(api, DATUM)
    logga_in(api, "redaktor")
    assert api.post(f"/api/sammantraden/{s}/granskning/aterkallelse", json={"motivering": "x"}).status_code == 409
    assert api.post(f"/api/sammantraden/{s}/granskning").status_code == 200

    # En annan person kan ta tillbaka granskningen, men bara med en motivering.
    logga_in(api, "utgivare")
    utan = api.post(f"/api/sammantraden/{s}/granskning/aterkallelse", json={"motivering": "  "})
    assert utan.status_code == 422
    g = api.post(f"/api/sammantraden/{s}/granskning/aterkallelse",
                 json={"motivering": "Närvarolistan stämmer inte med sidan 2."}).json()
    assert g["gallande"] is None
    assert g["andrad_efter_granskning"] is False
    [rad] = g["logg"]
    assert (rad["status"], rad["granskad_av"], rad["aterkallad_av"], rad["aterkallelse"]) == (
        "aterkallad", "test-redaktor@kommunkollen.test", "test-utgivare@kommunkollen.test",
        "Närvarolistan stämmer inte med sidan 2.")
    assert rad["granskad"] is not None and rad["aterkallad"] is not None
    assert granskad_for_lasaren(api, s) is None
    logga_in(api, "utgivare")
    assert api.get(f"/api/sammantraden/{s}/granskning").json()["kan_granskas"] is True


def test_okant_sammantrade(api):
    logga_in(api, "redaktor")
    assert api.get("/api/sammantraden/999999/granskning").status_code == 404
    assert api.post("/api/sammantraden/999999/granskning").status_code == 404
