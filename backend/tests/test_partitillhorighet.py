"""Fastställd partitillhörighet per period (#100, del 1): flödet, pålägget och ordningen för vad som gäller.

Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade), som i test_rattelser. Glenn Sehlin
saknar parti i närvarolistan 2026-06-15.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app import db
from app.protokoll import tolka_om
from test_rattelser import api, logga_in, publicerad, sammantrade_id  # noqa: F401

GLENN = "Glenn Sehlin"


def ledamot(api, namn: str) -> dict:
    return next(p for p in api.get("/api/ledamoter", params={"q": namn}).json() if p["namn"] == namn)


def narvaro(api, datum: str, namn: str = GLENN) -> dict:
    s = sammantrade_id(api, datum)
    return next(p for p in api.get(f"/api/sammantraden/{s}").json()["narvaro"] if p["namn"] == namn)


def period(api, **data) -> dict:
    logga_in(api, "redaktor")
    svar = api.post("/api/partitillhorighet", json={"motivering": "SD enligt voteringslistorna 2026."} | data)
    assert svar.status_code == 201, svar.text
    return svar.json()


def publicera(api, pid: int) -> None:
    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/{pid}/granskning").status_code == 200
    assert api.post(f"/api/partitillhorighet/{pid}/publicering").status_code == 200, pid
    logga_in(api, None)


def test_en_publicerad_period_galler_narvaron_med_markering(api, database_url):
    glenn = ledamot(api, GLENN)
    fore = narvaro(api, "2026-06-15")
    assert fore.get("partitillhorighet") is None

    p = period(api, ledamot_id=glenn["id"], parti="SD", fran="2026-01-01", till=None)
    assert (p["status"], p["till"], p["ledamot"]["namn"]) == ("utkast", None, GLENN)
    # Ett utkast gäller inte, och ingen godkänner sin egen registrering.
    assert narvaro(api, "2026-06-15").get("partitillhorighet") is None
    logga_in(api, "redaktor+utgivare")
    egen = api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "SD", "fran": "2020-01-01",
                                                    "till": "2020-12-31", "motivering": "Prov"}).json()
    assert api.post(f"/api/partitillhorighet/{egen['id']}/granskning").status_code == 403
    publicera(api, p["id"])

    efter = narvaro(api, "2026-06-15")
    assert efter["parti"] == "SD" and "parti_harlett" not in efter
    assert efter["partitillhorighet"]["protokollet"] is None
    assert efter["partitillhorighet"]["motivering"] == "SD enligt voteringslistorna 2026."
    # Personsidan visar perioden, och listan räknar med partiet.
    sida = api.get(f"/api/ledamoter/{glenn['id']}").json()
    assert [(t["parti"], t["fran"], t["till"]) for t in sida["partitillhorighet"]] == [("SD", "2026-01-01", None)]
    assert GLENN in [x["namn"] for x in api.get("/api/ledamoter", params={"parti": "SD"}).json()]

    # Perioden gäller också efter en omtolkning, som för ett nytt protokoll.
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
        conn.commit()
    assert narvaro(api, "2026-06-15")["parti"] == "SD"


def test_ordningen_rattelse_period_protokoll(api):
    glenn = ledamot(api, GLENN)
    p = period(api, ledamot_id=glenn["id"], parti="SD", fran="2026-01-01", till="2026-12-31")
    publicera(api, p["id"])
    # En rättelse av en enskild förekomst går före perioden.
    s = sammantrade_id(api, "2026-06-15")
    publicerad(api, sammantrade_id=s, objekt="narvaro", namn=GLENN, falt="parti", nytt="-",
               felet_i="protokollet", motivering="Partilös enligt protokollet.")
    n = narvaro(api, "2026-06-15")
    assert (n["parti"], n.get("partitillhorighet")) == ("-", None)


def test_perioden_ger_ingen_markering_nar_protokollet_anger_samma_parti(api):
    # En person med parti i närvarolistan: samma parti i perioden ändrar inget.
    datum, annan = next(
        (s["datum"], p) for s in api.get("/api/sammantraden?organ=KF").json()
        for p in api.get(f"/api/sammantraden/{s['id']}").json()["narvaro"]
        if p["parti"] and p["ledamot_id"] and p["kategori"] == "beslutande" and not p.get("parti_harlett"))
    p = period(api, ledamot_id=annan["ledamot_id"], parti=annan["parti"], fran=datum, till=datum)
    publicera(api, p["id"])
    n = narvaro(api, datum, annan["namn"])
    assert (n["parti"], n.get("partitillhorighet")) == (annan["parti"], None)


def test_overlappande_perioder_avvisas(api):
    glenn = ledamot(api, GLENN)
    p = period(api, ledamot_id=glenn["id"], parti="SD", fran="2026-01-01", till="2026-06-30")
    overlappande = {"ledamot_id": glenn["id"], "parti": "-", "fran": "2026-06-01", "motivering": "x"}
    # En period som överlappar en väntande period för samma person avvisas och nämner den (#202).
    logga_in(api, "redaktor")
    svar = api.post("/api/partitillhorighet", json=overlappande)
    assert svar.status_code == 409
    assert svar.json()["detail"] == "Det finns redan ett utkast: SD, 2026-01-01–2026-06-30"
    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/{p['id']}/granskning").status_code == 200
    logga_in(api, "redaktor")
    svar = api.post("/api/partitillhorighet", json=overlappande)
    assert (svar.status_code, svar.json()["detail"]) == (409, "Det finns redan ett granskat förslag: SD, 2026-01-01–2026-06-30")
    # Också i en batch.
    svar = api.post("/api/partitillhorighet/batcher", json={"motivering": "x", "perioder": [overlappande]})
    assert (svar.status_code, svar.json()["detail"]) == (409, "Rad 1: Det finns redan ett granskat förslag: SD, 2026-01-01–2026-06-30")
    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/{p['id']}/publicering").status_code == 200
    logga_in(api, "redaktor")
    svar = api.post("/api/partitillhorighet", json=overlappande | {"fran": "2026-03-01"})
    assert (svar.status_code, svar.json()["detail"]) == (409, "Perioden överlappar en publicerad period (SD, 2026-01-01–2026-06-30)")
    # Ett partibyte blir två perioder som inte överlappar.
    assert api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "-", "fran": "2026-07-01",
                                                    "motivering": "Partilös från juli"}).status_code == 201
    for data, kod in [({"parti": "Sverigedemokraterna"}, 422), ({"fran": "igår"}, 422),
                      ({"fran": "2026-05-01", "till": "2026-04-01"}, 422), ({"motivering": " "}, 422),
                      ({"ledamot_id": 999999}, 404)]:
        svar = api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "SD", "fran": "2027-01-01",
                                                        "motivering": "m"} | data)
        assert svar.status_code == kod, (data, svar.text)


def test_ny_version_och_aterkallelse(api):
    glenn = ledamot(api, GLENN)
    p = period(api, ledamot_id=glenn["id"], parti="S", fran="2026-01-01", till=None)
    publicera(api, p["id"])
    assert narvaro(api, "2026-06-15")["parti"] == "S"

    logga_in(api, "redaktor")
    assert api.patch(f"/api/partitillhorighet/{p['id']}", json={"parti": "SD"}).status_code == 409
    ny = api.post(f"/api/partitillhorighet/{p['id']}/versioner", json={"parti": "SD", "motivering": "Fel parti."})
    assert ny.status_code == 201, ny.text
    assert (ny.json()["fran"], ny.json()["ersatter_id"]) == ("2026-01-01", p["id"])
    # Den nya versionen får överlappa den den ersätter.
    publicera(api, ny.json()["id"])
    assert narvaro(api, "2026-06-15")["parti"] == "SD"
    logga_in(api, "utgivare")
    status = {t["id"]: t["status"] for t in api.get("/api/partitillhorighet").json()}
    assert (status[p["id"]], status[ny.json()["id"]]) == ("ersatt", "publicerad")

    # Återkallad: protokollet och härledningen gäller igen.
    assert api.post(f"/api/partitillhorighet/{ny.json()['id']}/aterkallelse", json={"motivering": ""}).status_code == 422
    assert api.post(f"/api/partitillhorighet/{ny.json()['id']}/aterkallelse",
                    json={"motivering": "Perioden var fel."}).json()["status"] == "aterkallad"
    n = narvaro(api, "2026-06-15")
    assert n.get("partitillhorighet") is None
    assert n["parti"] is None or n.get("parti_harlett")


def test_en_utgivare_kasserar_ett_utkast_eller_en_granskad_period(api):
    """#202: en dubblett som väntar på granskning går att få bort, och historiken finns kvar."""
    glenn = ledamot(api, GLENN)
    utkast = period(api, ledamot_id=glenn["id"], parti="SD", fran="2022-01-01", till="2022-12-31")
    granskad = period(api, ledamot_id=glenn["id"], parti="SD", fran="2023-01-01", till="2023-12-31")
    publicerad_ = period(api, ledamot_id=glenn["id"], parti="SD", fran="2024-01-01", till="2024-12-31")
    publicera(api, publicerad_["id"])
    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/{granskad['id']}/granskning").status_code == 200

    # Redaktören kan inte kassera, och en motivering krävs.
    logga_in(api, "redaktor")
    assert api.post(f"/api/partitillhorighet/{utkast['id']}/kassering", json={"motivering": "Dubblett."}).status_code == 403
    logga_in(api, "utgivare")
    svar = api.post(f"/api/partitillhorighet/{granskad['id']}/kassering", json={"motivering": " "})
    assert (svar.status_code, svar.json()["detail"]) == (422, "Ange varför perioden kasseras")
    # En publicerad period återkallas i stället.
    assert api.post(f"/api/partitillhorighet/{publicerad_['id']}/kassering",
                    json={"motivering": "Dubblett."}).status_code == 409

    for t in (utkast, granskad):
        svar = api.post(f"/api/partitillhorighet/{t['id']}/kassering", json={"motivering": "Registrerad två gånger."})
        assert svar.status_code == 200, svar.text
        k = svar.json()
        assert (k["status"], k["aterkallelse"], k["aterkallad_av"]) == ("aterkallad", "Registrerad två gånger.",
                                                                        "test-utgivare@kommunkollen.test")
        assert k["aterkallad"] is not None and k["publicerad"] is None
    # En kasserad period kan inte kasseras igen eller publiceras.
    assert api.post(f"/api/partitillhorighet/{granskad['id']}/kassering", json={"motivering": "x"}).status_code == 409
    assert api.post(f"/api/partitillhorighet/{granskad['id']}/publicering").status_code == 409
    # Perioderna finns kvar som historik, men inte bland de väntande.
    status = {t["id"]: t["status"] for t in api.get("/api/partitillhorighet").json()}
    assert (status[utkast["id"]], status[granskad["id"]]) == ("aterkallad", "aterkallad")
    assert not api.get("/api/partitillhorighet?status=granskad").json()
    # En kasserad period hindrar inte en ny period för samma tid.
    assert period(api, ledamot_id=glenn["id"], parti="SD", fran="2023-01-01", till="2023-12-31")["status"] == "utkast"


def test_utgivaren_kasserar_sin_egen_registrering(api):
    """Att kassera är inget godkännande, så ADR-0002 hindrar det inte. Redaktören kan fortfarande ta bort sitt utkast."""
    glenn = ledamot(api, GLENN)
    logga_in(api, "redaktor+utgivare")
    egen = api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "SD", "fran": "2020-01-01",
                                                    "till": "2020-12-31", "motivering": "Prov"}).json()
    svar = api.post(f"/api/partitillhorighet/{egen['id']}/kassering", json={"motivering": "Fel person."})
    assert svar.json()["status"] == "aterkallad"
    logga_in(api, "redaktor")
    utkast = api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "SD", "fran": "2020-01-01",
                                                      "till": "2020-12-31", "motivering": "Prov"}).json()
    assert api.delete(f"/api/partitillhorighet/{utkast['id']}").status_code == 204


def test_en_ny_version_raknas_inte_som_overlapp(api):
    """#202: en ny version överlappar perioden den ersätter, och ett utkast överlappar sig självt när det ändras."""
    glenn = ledamot(api, GLENN)
    p = period(api, ledamot_id=glenn["id"], parti="SD", fran="2026-01-01", till=None)
    logga_in(api, "redaktor")
    assert api.patch(f"/api/partitillhorighet/{p['id']}", json={"fran": "2025-06-01"}).status_code == 200
    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/{p['id']}/granskning").status_code == 200

    # En ny version av en granskad period, medan den väntar.
    logga_in(api, "redaktor")
    ny = api.post(f"/api/partitillhorighet/{p['id']}/versioner", json={"parti": "-", "motivering": "Partilös."})
    assert ny.status_code == 201, ny.text
    assert api.patch(f"/api/partitillhorighet/{ny.json()['id']}", json={"fran": "2025-01-01"}).status_code == 200
    # Men en annan ny period för samma tid avvisas.
    svar = api.post("/api/partitillhorighet", json={"ledamot_id": glenn["id"], "parti": "-", "fran": "2026-01-01",
                                                    "motivering": "x"})
    assert svar.status_code == 409 and svar.json()["detail"].startswith("Det finns redan ett granskat förslag: SD, 2025-06-01")
    publicera(api, ny.json()["id"])
    logga_in(api, "utgivare")
    status = {t["id"]: t["status"] for t in api.get("/api/partitillhorighet").json()}
    assert (status[p["id"]], status[ny.json()["id"]]) == ("ersatt", "publicerad")
