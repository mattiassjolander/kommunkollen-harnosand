"""Förslag på fastställda partitillhörigheter i en batch (#100, del 2).

Algoritmen testas med påhittade förekomster. Flödet testas mot kommunfullmäktiges protokoll för 2026
(inspelade), som i test_partitillhorighet.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.partiforslag import Forekomst, perioder
from test_partitillhorighet import GLENN, ledamot, narvaro
from test_rattelser import api, logga_in  # noqa: F401


def forekomster(*partier: str | None, start: date = date(2023, 1, 16)) -> list[Forekomst]:
    return [Forekomst(start + timedelta(weeks=4 * i), 1000 + i, "KF", p) for i, p in enumerate(partier)]


def kort(ut: list[dict]) -> list[tuple]:
    return [(p["parti"], p["fran"], p["till"], [k.parti for k in p["krockar"]]) for p in ut]


def test_samma_parti_med_luckor_blir_en_period_fran_forsta_sammantradet():
    f = forekomster(None, *["S"] * 5, None, *["S"] * 5)
    assert kort(perioder(f)) == [("S", f[0].datum, None, [])]
    assert len(perioder(f)[0]["forekomster"]) == 12


def test_ett_partibyte_som_bestar_blir_tva_perioder():
    f = forekomster(*["C"] * 6, *["-"] * 4)
    assert kort(perioder(f)) == [("C", f[0].datum, f[6].datum - timedelta(days=1), []), ("-", f[6].datum, None, [])]
    # Två i följd räcker vid personens sista sammanträden.
    f = forekomster(*["C"] * 6, "-", "-")
    assert [p["parti"] for p in perioder(f)] == ["C", "-"]


def test_en_enstaka_avvikelse_blir_en_krock():
    f = forekomster(*["S"] * 4, "M", *["S"] * 4)
    assert kort(perioder(f)) == [("S", f[0].datum, None, ["M"])]
    # Två i följd mitt i en period är också en krock.
    f = forekomster(*["S"] * 4, "M", "M", *["S"] * 4)
    assert kort(perioder(f)) == [("S", f[0].datum, None, ["M", "M"])]
    # En avvikelse vid det första sammanträdet hör till den första perioden.
    f = forekomster("M", *["S"] * 4)
    assert kort(perioder(f)) == [("S", f[0].datum, None, ["M"])]


def test_utan_angivet_parti_inget_forslag_och_utan_stabilt_parti_det_vanligaste():
    assert perioder(forekomster(None, None)) == []
    assert [p["parti"] for p in perioder(forekomster("S"))] == ["S"]
    assert kort(perioder(forekomster("S", "M", "S", "M", "S")))[0][:1] == ("S",)


def forslag_for(api, namn: str) -> dict | None:
    logga_in(api, "redaktor")
    return next((f for f in api.get("/api/partitillhorighet/forslag").json() if f["ledamot"]["namn"] == namn), None)


def test_forslagen_bekraftas_i_en_batch_och_publiceras_tillsammans(api):
    logga_in(api, None)
    assert api.get("/api/partitillhorighet/forslag").status_code == 401
    alla = (logga_in(api, "redaktor"), api.get("/api/partitillhorighet/forslag").json())[1]
    # Två personer med angivet parti, med belägg.
    valda = [f for f in alla if f["perioder"][0]["antal_per_parti"]][:2]
    assert len(valda) == 2
    p = valda[0]["perioder"][0]
    assert p["antal_per_parti"][p["parti"]] >= 1 and p["exempel"]["id"] and p["forsta"] <= p["sista"]

    rader = [{"ledamot_id": f["ledamot"]["id"], "parti": f["perioder"][0]["parti"], "fran": f["perioder"][0]["fran"],
              "till": f["perioder"][0]["till"]} for f in valda]
    rader[1]["motivering"] = "Egen motivering."
    svar = api.post("/api/partitillhorighet/batcher", json={"motivering": "Enligt närvarolistorna.", "perioder": rader})
    assert svar.status_code == 201, svar.text
    skapade = svar.json()
    batch = skapade[0]["batch"]
    assert [t["batch"] for t in skapade] == [batch, batch] and batch is not None
    assert [t["motivering"] for t in skapade] == ["Enligt närvarolistorna.", "Egen motivering."]
    # Personerna har nu perioder och föreslås inte längre.
    namn = {f["ledamot"]["namn"] for f in api.get("/api/partitillhorighet/forslag").json()}
    assert not namn & {f["ledamot"]["namn"] for f in valda}

    # Ingen godkänner sin egen batch.
    logga_in(api, "redaktor+utgivare")
    egen = api.post("/api/partitillhorighet/batcher", json={"motivering": "x", "perioder": [
        {"ledamot_id": ledamot(api, GLENN)["id"], "parti": "SD", "fran": "2020-01-01", "till": "2020-12-31"}]}).json()
    assert api.post(f"/api/partitillhorighet/batcher/{egen[0]['batch']}/granskning").status_code == 403

    logga_in(api, "utgivare")
    assert api.post(f"/api/partitillhorighet/batcher/{batch}/publicering").status_code == 409
    assert len(api.post(f"/api/partitillhorighet/batcher/{batch}/granskning").json()) == 2
    publicerade = api.post(f"/api/partitillhorighet/batcher/{batch}/publicering").json()
    assert [t["status"] for t in publicerade] == ["publicerad", "publicerad"]
    assert api.post("/api/partitillhorighet/batcher/999999/granskning").status_code == 404


def test_en_batch_ar_allt_eller_inget(api):
    glenn = ledamot(api, GLENN)
    logga_in(api, "redaktor")
    rad = {"ledamot_id": glenn["id"], "parti": "SD", "fran": "2026-01-01", "till": None}
    for perioder_, kod in [([], 422), ([rad, rad | {"fran": "2026-06-01"}], 409),
                           ([rad, rad | {"parti": "Sverigedemokraterna", "fran": "2020-01-01", "till": "2020-12-31"}], 422)]:
        svar = api.post("/api/partitillhorighet/batcher", json={"motivering": "m", "perioder": perioder_})
        assert svar.status_code == kod, (perioder_, svar.text)
    # Inget sparades.
    logga_in(api, "utgivare")
    assert api.get("/api/partitillhorighet").json() == []
    # En rad utan egen eller gemensam motivering avvisas.
    logga_in(api, "redaktor")
    assert api.post("/api/partitillhorighet/batcher", json={"perioder": [rad]}).status_code == 422


def test_en_publicerad_batch_galler_i_protokollen(api):
    # Glenn Sehlin saknar parti i närvarolistan 2026-06-15 men har det vid andra sammanträden.
    f = forslag_for(api, GLENN)
    assert f is not None and f["perioder"][-1]["utan_parti"] >= 1
    t = f["perioder"][-1]
    svar = api.post("/api/partitillhorighet/batcher", json={"motivering": "Enligt närvarolistorna.", "perioder": [
        {"ledamot_id": f["ledamot"]["id"], "parti": t["parti"], "fran": t["fran"], "till": t["till"]}]}).json()
    logga_in(api, "utgivare")
    api.post(f"/api/partitillhorighet/batcher/{svar[0]['batch']}/granskning")
    api.post(f"/api/partitillhorighet/batcher/{svar[0]['batch']}/publicering")
    logga_in(api, None)
    n = narvaro(api, "2026-06-15")
    assert n["parti"] == t["parti"] and n["partitillhorighet"]["protokollet"] is None
