"""Rätta motionärer (#78): peka på person och parti.

Söm 1: kommunfullmäktiges inspelade protokoll från 2026 (som test_statistik). Motionen "Odlingslotter"
väcktes vid KF 2026-04-27 § 58, och tolkningen hittar ingen motionär i bakgrunden. En redaktör rättar
motionärerna, och en utgivare som inte skrev rättelsen granskar och publicerar den (ADR-0002).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from test_statistik import api  # noqa: F401

from app import db
from app.protokoll import tolka_om


def logga_in(api: TestClient, roll: str | None) -> None:
    api.post("/api/auth/logga-ut")
    if roll:
        assert api.post(f"/api/auth/test/{roll}").status_code == 200


def odlingslotter(api: TestClient) -> dict:
    s = api.get("/api/statistik/motioner").json()
    return next(m for m in s["motioner"]["lista"] if "Odlingslotter" in m["rubrik"])


def vackta(api: TestClient, parti: str) -> int:
    per_parti = api.get("/api/statistik/motioner").json()["motioner"]["per_parti"]
    return next((p["vackta"] for p in per_parti if p["parti"] == parti), 0)


def person(api: TestClient, namn: str) -> dict:
    [p] = [p for p in api.get("/api/ledamoter", params={"q": namn}).json() if p["namn"] == namn]
    return p


def test_motionar_som_saknas_rattas_med_person_och_parti_ur_narvaron(api, database_url):  # noqa: F811
    m = odlingslotter(api)
    assert (m["motionarer"], m["vackt"]["datum"]) == ([], "2026-04-27")
    # Rättelsen hör till behandlingen där motionen väcktes.
    mal = m["rattelsemal"]
    assert (mal["sammantrade_id"], mal["paragraf"]) == (m["vackt"]["sammantrade_id"], m["vackt"]["paragraf"]) \
        and mal["paragraf"] == 58
    fore_s = vackta(api, "S")

    logga_in(api, "redaktor")
    fahlen, visen = person(api, "Monica Fahlén"), person(api, "Lotta Visén")
    # Partiet förifylls ur närvaron vid sammanträdet där motionen väcktes.
    forslag = api.get("/api/motionarer/parti", params={"person_id": fahlen["id"], "sammantrade_id": mal["sammantrade_id"]})
    assert forslag.json() == {"parti": "S", "kalla": {"grund": "narvaro", "sammantrade": None}}
    # Saknas partiet i närvarolistan härleds det, och källan visas.
    visen_parti = api.get("/api/motionarer/parti", params={"person_id": visen["id"], "sammantrade_id": mal["sammantrade_id"]}).json()
    assert visen_parti["kalla"]["grund"] in ("samma_protokoll", "annat_protokoll")
    assert api.get("/api/motionarer/parti", params={"person_id": 999999, "sammantrade_id": 1}).status_code == 404

    def rattelse(nytt, **extra) -> dict:
        return {"sammantrade_id": mal["sammantrade_id"], "objekt": "behandling", "paragraf": mal["paragraf"],
                "falt": "motionarer", "nytt": nytt, "motivering": "Motionen är undertecknad av Monica Fahlén (S).", "felet_i": "inlasningen"} | extra

    # Bara personer i registret, och en partigrupp ska ha ett parti.
    assert api.post("/api/rattelser", json=rattelse([{"person_id": 999999, "parti": "S"}])).status_code == 422
    assert api.post("/api/rattelser", json=rattelse([{"parti": None}])).status_code == 422
    assert api.post("/api/rattelser", json=rattelse([])).status_code == 422
    dubbel = [{"person_id": fahlen["id"], "parti": "S"}, {"person_id": fahlen["id"], "parti": "S"}]
    assert api.post("/api/rattelser", json=rattelse(dubbel)).status_code == 422

    svar = api.post("/api/rattelser", json=rattelse([{"person_id": fahlen["id"], "parti": "S"}, {"parti": "V"}]))
    assert svar.status_code == 201, svar.text
    r = svar.json()
    assert (r["falt"], r["status"], r["ursprungligt"]) == ("motionarer", "utkast", [])
    assert r["nytt"] == [{"person_id": fahlen["id"], "namn": "Monica Fahlén", "parti": "S"},
                         {"person_id": None, "namn": None, "parti": "V"}]
    # Utkastet kan ändras: byta, ta bort och lägga till.
    r = api.patch(f"/api/rattelser/{r['id']}", json={"nytt": [{"person_id": fahlen["id"], "parti": "S"}]}).json()
    assert [p["namn"] for p in r["nytt"]] == ["Monica Fahlén"]
    # Opublicerad syns inte för läsaren.
    logga_in(api, None)
    assert odlingslotter(api)["motionarer"] == []

    # Ingen publicerar sin egen rättelse.
    logga_in(api, "redaktor+utgivare")
    egen = api.post("/api/rattelser", json=rattelse([{"person_id": visen["id"], "parti": "MP"}])).json()
    assert api.post(f"/api/rattelser/{egen['id']}/granskning").status_code == 403

    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/granskning").json()["status"] == "granskad"
    assert api.post(f"/api/rattelser/{r['id']}/publicering").json()["status"] == "publicerad"

    logga_in(api, None)
    m = odlingslotter(api)
    assert m["motionarer"] == [{"person_id": fahlen["id"], "namn": "Monica Fahlén", "parti": "S"}]
    rattad = m["rattelser"]["motionarer"]
    assert (rattad["ursprungligt"], rattad["motivering"]) == ([], "Motionen är undertecknad av Monica Fahlén (S).")
    # Statistiken per parti räknas med rättelsen.
    assert vackta(api, "S") == fore_s + 1

    # En omtolkning ändrar inte tolkningen men bevarar rättelsen.
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
    assert odlingslotter(api)["motionarer"][0]["namn"] == "Monica Fahlén"


def test_utgivare_kan_skriva_rattelse_av_motionarer_men_inte_andra_uppgifter(api):  # noqa: F811
    mal = odlingslotter(api)["rattelsemal"]
    logga_in(api, "utgivare")
    fahlen = person(api, "Monica Fahlén")
    bas = {"sammantrade_id": mal["sammantrade_id"], "objekt": "behandling", "paragraf": mal["paragraf"],
           "motivering": "Enligt motionen.", "felet_i": "inlasningen"}
    assert api.post("/api/rattelser", json=bas | {"falt": "rubrik", "nytt": "Ny rubrik"}).status_code == 403
    svar = api.post("/api/rattelser", json=bas | {"falt": "motionarer", "nytt": [{"person_id": fahlen["id"], "parti": "S"}]})
    assert svar.status_code == 201, svar.text
    # En redaktör (inte den som skrev) publicerar inte; det gör en annan utgivare.
    logga_in(api, "redaktor+utgivare")
    assert api.post(f"/api/rattelser/{svar.json()['id']}/granskning").json()["status"] == "granskad"


def test_tolkade_motionarer_lankar_till_personsidan(api):  # noqa: F811
    s = api.get("/api/statistik/motioner").json()
    friskvard = next(m for m in s["motioner"]["lista"] if "friskvårdsbidraget" in m["rubrik"])
    [olle] = friskvard["motionarer"]
    assert (olle["namn"], olle["parti"]) == ("Olle Löfgren", "L")
    assert api.get(f"/api/ledamoter/{olle['person_id']}").json()["namn"] == "Olle Löfgren"
