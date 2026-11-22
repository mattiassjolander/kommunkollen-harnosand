"""Krockar och filtren i fliken Partitillhörighet (#100, del 3).

Körs mot kommunfullmäktiges protokoll för 2026 (inspelade), som i test_partitillhorighet.
"""

from __future__ import annotations

from test_partitillhorighet import narvaro, period, publicera
from test_rattelser import api, logga_in  # noqa: F401


def angiven(api) -> tuple[str, dict]:
    """Ett sammanträde och en beslutande med parti i närvarolistan."""
    return next(
        (s["datum"], p) for s in api.get("/api/sammantraden?organ=KF").json()
        for p in api.get(f"/api/sammantraden/{s['id']}").json()["narvaro"]
        if p["parti"] and p["parti"] != "-" and p["ledamot_id"] and p["kategori"] == "beslutande"
        and not p.get("parti_harlett"))


def krockar_for(api, ledamot_id: int) -> list[dict]:
    logga_in(api, "redaktor")
    return next((k["krockar"] for k in api.get("/api/partitillhorighet/krockar").json()
                 if k["ledamot"]["id"] == ledamot_id), [])


def personen(api, ledamot_id: int) -> dict:
    logga_in(api, "utgivare")
    return next(p for p in api.get("/api/partitillhorighet/personer").json() if p["ledamot"]["id"] == ledamot_id)


def test_en_krock_listas_bekraftas_som_felaktighet_och_visas_igen_vid_aterkallelse(api):
    datum, person = angiven(api)
    pid = person["ledamot_id"]
    logga_in(api, None)
    assert api.get("/api/partitillhorighet/krockar").status_code == 401
    assert krockar_for(api, pid) == []
    p0 = personen(api, pid)
    assert (p0["publicerade"], p0["vantande"], p0["krockar"]) == ([], 0, 0) and p0["antal_sammantraden"] >= 1

    # Ett utkast till period ger också krockar, och personen väntar på granskning.
    p = period(api, ledamot_id=pid, parti="-", fran=datum, till=datum, motivering="Partilös enligt prov.")
    k = krockar_for(api, pid)
    assert [(x["sammantrade"]["datum"], x["protokollet"], x["period"]["parti"], x["period"]["status"]) for x in k] \
        == [(datum, person["parti"], "-", "utkast")]
    assert (personen(api, pid)["vantande"], personen(api, pid)["krockar"]) == (1, 1)
    publicera(api, p["id"])
    assert krockar_for(api, pid)[0]["period"]["status"] == "publicerad"
    assert [t["parti"] for t in personen(api, pid)["publicerade"]] == ["-"]

    # Redaktören bekräftar krocken som fel i protokollet. Den blir en rättelse och försvinner ur listan.
    logga_in(api, "redaktor")
    s = k[0]["sammantrade"]["id"]
    for data, kod in [({"krockar": []}, 422), ({"krockar": [{"sammantrade_id": s, "namn": person["namn"]}]}, 422),
                      ({"krockar": [{"sammantrade_id": s, "namn": "Ingen Alls"}], "felet_i": "protokollet",
                        "motivering": "m"}, 409)]:
        assert api.post("/api/partitillhorighet/krockar/bekraftelser", json=data).status_code == kod, data
    svar = api.post("/api/partitillhorighet/krockar/bekraftelser", json={
        "felet_i": "protokollet", "motivering": "Personen är partilös sedan dess.",
        "krockar": [{"sammantrade_id": s, "namn": person["namn"]}]})
    assert svar.status_code == 201, svar.text
    r = svar.json()[0]
    assert (r["status"], r["nytt"], r["ursprungligt"], r["felet_i"]) == ("utkast", "-", person["parti"], "protokollet")
    assert krockar_for(api, pid) == []

    # Publicerad räknas den som en felaktighet i protokollet.
    logga_in(api, "utgivare")
    api.post(f"/api/rattelser/{r['id']}/granskning")
    api.post(f"/api/rattelser/{r['id']}/publicering")
    logga_in(api, None)
    assert api.get(f"/api/sammantraden/{s}").json()["felaktigheter"] == 1
    n = narvaro(api, datum, person["namn"])
    assert n["parti"] == "-" and n.get("partitillhorighet") is None

    # Återkallas rättelsen visas krocken igen.
    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": "Fel."}).status_code == 200
    assert len(krockar_for(api, pid)) == 1


def test_samma_parti_och_saknat_parti_ar_ingen_krock(api):
    datum, person = angiven(api)
    p = period(api, ledamot_id=person["ledamot_id"], parti=person["parti"], fran="2026-01-01", till=None,
               motivering="Enligt närvarolistorna.")
    publicera(api, p["id"])
    assert krockar_for(api, person["ledamot_id"]) == []
