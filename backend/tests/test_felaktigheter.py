"""Fel i protokollet eller i inläsningen, och protokoll märkta med felaktigheter (#74, del 2 och 4).

Insamlingen körs mot kommunfullmäktiges protokoll för 2026 (inspelade), som i test_rattelser.
"""

from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from app import db
from app.protokoll import tolka_om
from test_rattelser import api, logga_in, publicerad, sammantrade_id, skapa  # noqa: F401


def sammantrade(api, s: int) -> dict:
    return api.get(f"/api/sammantraden/{s}").json()


def i_listan(api, s: int) -> dict:
    return next(x for x in api.get("/api/sammantraden?organ=KF").json() if x["id"] == s)


def avvikelser(api, s: int) -> dict | None:
    return next((x for x in api.get("/api/avvikelser", params={"fran": 2026, "till": 2026}).json()["sammantraden"]
                 if x["sammantrade"]["id"] == s), None)


def test_partiet_ratts_som_fel_i_protokollet_och_protokollet_marks(api, database_url):
    s = sammantrade_id(api, "2026-06-15")
    assert sammantrade(api, s)["felaktigheter"] == 0

    # Söm 1: redaktören rättar partiet för en enskild förekomst och anger att felet finns i protokollet.
    r = publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
                   felet_i="protokollet", motivering="Närvarolistan anger inget parti. SD enligt voteringslistan.")
    assert r["felet_i"] == "protokollet"

    # Läsaren ser partiet med rättelsemarkering, och var felet fanns.
    glenn = next(p for p in sammantrade(api, s)["narvaro"] if p["namn"] == "Glenn Sehlin")
    assert glenn["parti"] == "SD"
    assert (glenn["rattelser"]["parti"]["ursprungligt"], glenn["rattelser"]["parti"]["felet_i"]) == (None, "protokollet")

    # Protokollet innehåller felaktigheter, på sammanträdessidan och i listan.
    assert sammantrade(api, s)["felaktigheter"] == 1
    assert i_listan(api, s)["felaktigheter"] == 1

    # Listan över felaktigheter: varje rättelse med före och efter.
    a = avvikelser(api, s)
    assert a["i_protokollet"] and a["felaktigheter"] == 1
    [x] = a["rattelser"]
    assert {k: x[k] for k in ("objekt", "namn", "falt", "ursprungligt", "nytt", "felet_i")} == {
        "objekt": "narvaro", "namn": "Glenn Sehlin", "falt": "parti", "ursprungligt": None, "nytt": "SD",
        "felet_i": "protokollet"}
    assert x["motivering"].startswith("Närvarolistan anger inget parti")

    # Valet bevaras vid omtolkning.
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
        conn.commit()
    assert sammantrade(api, s)["felaktigheter"] == 1


def test_fel_i_inlasningen_och_inte_angivet_ger_ingen_markering(api, database_url):
    s = sammantrade_id(api, "2026-06-15")
    publicerad(api, sammantrade_id=s, objekt="rost", paragraf=109, votering=2, namn="Glenn Sehlin", falt="rost",
               nytt="ja", felet_i="inlasningen", motivering="Voteringslistan på sidan 14.")
    publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
               felet_i="protokollet", motivering="SD enligt voteringslistan.")
    # En rättelse från före #74 saknar valet.
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE rattelse SET felet_i = NULL WHERE objekt = 'narvaro'")

    assert sammantrade(api, s)["felaktigheter"] == 0
    a = avvikelser(api, s)
    assert a["felaktigheter"] == 0
    assert sorted((x["falt"], x["felet_i"] or "") for x in a["rattelser"]) == [("parti", ""), ("rost", "inlasningen")]
    antal = {f["id"]: f["antal"] for f in api.get("/api/avvikelser", params={"fran": 2026, "till": 2026}).json()["felet_i"]}
    assert antal == {"protokollet": 0, "inlasningen": 1, None: 1}


def test_valet_ses_av_utgivaren_och_kan_andras_i_utkastet(api):
    s = sammantrade_id(api, "2026-06-15")
    logga_in(api, "redaktor")
    r = skapa(api, sammantrade_id=s, objekt="behandling", paragraf=109, falt="diarienummer", nytt=["KS/2026-200"],
              felet_i="protokollet", motivering="Fel nummer i protokollet")
    assert api.patch(f"/api/rattelser/{r['id']}", json={"felet_i": "inlasningen"}).json()["felet_i"] == "inlasningen"
    assert api.patch(f"/api/rattelser/{r['id']}", json={"felet_i": "annat"}).status_code == 422
    logga_in(api, "utgivare")
    [utkast] = [x for x in api.get("/api/rattelser", params={"status": "utkast"}).json() if x["id"] == r["id"]]
    assert utkast["felet_i"] == "inlasningen"


# Del 3: ändra befintliga rättelser


def granska_och_publicera(api, rid: int) -> None:
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{rid}/granskning").status_code == 200, rid
    assert api.post(f"/api/rattelser/{rid}/publicering").status_code == 200, rid
    logga_in(api, None)


def test_en_publicerad_rattelse_andras_genom_en_ny_version(api):
    """Söm 3: från fel i protokollet till fel i inläsningen. Markeringen försvinner och historiken bevaras."""
    s = sammantrade_id(api, "2026-06-15")
    gammal = publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
                        felet_i="protokollet", motivering="Närvarolistan anger inget parti.")
    assert sammantrade(api, s)["felaktigheter"] == 1

    logga_in(api, "redaktor")
    # En publicerad rättelse ändras inte på plats.
    assert api.patch(f"/api/rattelser/{gammal['id']}", json={"felet_i": "inlasningen"}).status_code == 409
    svar = api.post(f"/api/rattelser/{gammal['id']}/versioner",
                    json={"felet_i": "inlasningen", "motivering": "Partiet står i närvarolistan, inläsningen missade det."})
    assert svar.status_code == 201, svar.text
    ny = svar.json()
    # Förifyllt från den gamla versionen.
    assert (ny["status"], ny["nytt"], ny["felet_i"], ny["ersatter_id"]) == ("utkast", "SD", "inlasningen", gammal["id"])
    assert [t["id"] for t in ny["tidigare"]] == [gammal["id"]]
    # Bara en väntande version åt gången.
    assert api.post(f"/api/rattelser/{gammal['id']}/versioner", json={"motivering": "Igen"}).status_code == 409

    # Den gamla gäller tills den nya är publicerad.
    assert sammantrade(api, s)["felaktigheter"] == 1
    granska_och_publicera(api, ny["id"])
    assert sammantrade(api, s)["felaktigheter"] == 0
    assert avvikelser(api, s)["rattelser"][0]["felet_i"] == "inlasningen"

    logga_in(api, "utgivare")
    statusar = {r["id"]: r["status"] for r in api.get("/api/rattelser").json()}
    assert (statusar[gammal["id"]], statusar[ny["id"]]) == ("ersatt", "publicerad")
    # Läsaren ser den tidigare versionen i historiken.
    logga_in(api, None)
    glenn = next(p for p in sammantrade(api, s)["narvaro"] if p["namn"] == "Glenn Sehlin")
    [tidigare] = glenn["rattelser"]["parti"]["tidigare"]
    assert (tidigare["felet_i"], tidigare["motivering"]) == ("protokollet", "Närvarolistan anger inget parti.")


def test_ett_utkast_andras_direkt_och_en_ny_version_av_ett_utkast_avvisas(api):
    s = sammantrade_id(api, "2026-06-15")
    logga_in(api, "redaktor")
    r = skapa(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
              felet_i="protokollet", motivering="Prov")
    assert api.post(f"/api/rattelser/{r['id']}/versioner", json={"motivering": "x"}).status_code == 409
    andrat = api.patch(f"/api/rattelser/{r['id']}", json={"nytt": "S", "motivering": "Prov 2", "felet_i": "inlasningen"})
    assert {k: andrat.json()[k] for k in ("nytt", "motivering", "felet_i")} == {
        "nytt": "S", "motivering": "Prov 2", "felet_i": "inlasningen"}


def test_en_rattelse_utan_valet_kompletteras_genom_en_ny_version(api, database_url):
    s = sammantrade_id(api, "2026-06-15")
    gammal = publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
                        felet_i="protokollet", motivering="Från före #74")
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE rattelse SET felet_i = NULL WHERE id = %s", (gammal["id"],))
    logga_in(api, "redaktor")
    # Valet måste anges i den nya versionen när den gamla saknar det.
    assert api.post(f"/api/rattelser/{gammal['id']}/versioner", json={"motivering": "Komplettering"}).status_code == 422
    ny = api.post(f"/api/rattelser/{gammal['id']}/versioner",
                  json={"motivering": "Komplettering", "felet_i": "protokollet"}).json()
    granska_och_publicera(api, ny["id"])
    assert sammantrade(api, s)["felaktigheter"] == 1


def test_en_utgivare_aterkallar_en_publicerad_rattelse(api):
    s = sammantrade_id(api, "2026-06-15")
    r = publicerad(api, sammantrade_id=s, objekt="narvaro", namn="Glenn Sehlin", falt="parti", nytt="SD",
                   felet_i="protokollet", motivering="Närvarolistan anger inget parti.")
    logga_in(api, "redaktor")
    assert api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": "Fel"}).status_code == 403
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": " "}).status_code == 422
    svar = api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": "Rättelsen var fel."})
    assert svar.status_code == 200, svar.text
    assert (svar.json()["status"], svar.json()["aterkallelse"]) == ("aterkallad", "Rättelsen var fel.")
    assert api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": "Igen"}).status_code == 409

    # Tolkningen gäller igen, och markeringen försvinner.
    logga_in(api, None)
    glenn = next(p for p in sammantrade(api, s)["narvaro"] if p["namn"] == "Glenn Sehlin")
    assert "parti" not in (glenn.get("rattelser") or {})
    assert sammantrade(api, s)["felaktigheter"] == 0
