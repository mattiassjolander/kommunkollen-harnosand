"""Topplistor per år och mandatperiod (#163).

Kommunfullmäktiges protokoll för 2026 och Valmyndighetens filer är inspelade. 2026 räknas med mandaten från
mandatperioden 2022–2026 (den som gäller den 1 juli): S 17, M 7, SD 6, C 4, V 3, MP 3, KD 2 och L 1. Där
protokollen inte har exemplet som en lista behöver (en lång beredning, en besvarad motion) kopplas behandlingar
ihop till ett ärende i testet.
"""

from __future__ import annotations

from datetime import date

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll import kf
from test_rattelser import logga_in, publicerad

from app import db
from app.arenden import SAMLING
from app.sources.valmyndigheten import Valmyndigheten

MANDAT_2022 = {"S": 17, "V": 3, "MP": 3, "C": 4, "L": 1, "M": 7, "KD": 2, "SD": 6}


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[*kf(), Valmyndigheten(anrop_per_sekund=None)],
                             anonym_lasning=True))
    logga_in(a, "redaktor")
    svar = a.post("/api/insamlingar")
    assert svar.status_code == 200 and svar.json()["status"] == "lyckad", svar.text
    logga_in(a, None)
    return a


def listor(api: TestClient, **q) -> dict:
    svar = api.get("/api/topplistor", params=q)
    assert svar.status_code == 200, svar.text
    return svar.json()


def kf_sammantraden(api: TestClient) -> list[dict]:
    return sorted(api.get("/api/sammantraden?organ=KF").json(), key=lambda s: s["datum"])


def behandlingar(api: TestClient, s: dict) -> list[dict]:
    return api.get(f"/api/sammantraden/{s['id']}").json()["behandlingar"]


def med_arende(api: TestClient, database_url: str, s: dict) -> list[dict]:
    """Sammanträdets behandlingar utan märkningar som hör till ett ärende (inte samlingspunkter), med `arende_id`."""
    with db.connect(database_url) as conn:
        arende = {r["paragraf"]: r["arende_id"] for r in conn.execute(
            "SELECT paragraf, arende_id FROM arende_behandling WHERE sammantrade_id = %s", (s["id"],))}
    return [b | {"arende_id": arende[b["paragraf"]]} for b in behandlingar(api, s)
            if b["paragraf"] in arende and not b["markningar"] and not SAMLING.search(b["rubrik"])]


def nycklar(rad: dict) -> set[tuple[int, int]]:
    return {(b["sammantrade"]["id"], b["paragraf"]) for b in rad["behandlingar"]}


def flytta_till_arende(database_url: str, arende_id: int, sammantrade_id: int, paragraf: int, beslut: str) -> None:
    with db.connect(database_url) as conn:
        conn.execute("UPDATE arende_behandling SET arende_id = %s WHERE sammantrade_id = %s AND paragraf = %s",
                     (arende_id, sammantrade_id, paragraf))
        conn.execute("UPDATE behandling SET beslut = %s WHERE sammantrade_id = %s AND paragraf = %s",
                     (beslut, sammantrade_id, paragraf))


# Urvalet

def test_standard_ar_mandatperiod_och_ogiltiga_urval(api):
    t = listor(api)
    assert t["urval"] == {"ar": 2026, "period": None, "namn": "2026", "fran": "2026-01-01", "till": "2026-12-31"}
    assert t["val"]["ar"] == [2026]
    assert [p["namn"] for p in t["val"]["perioder"]] == ["2026–2030", "2022–2026"]
    # Utan angiven period väljs den senaste som har börjat.
    assert listor(api, ar="mandatperiod")["urval"]["period"] == 2026
    p = listor(api, ar="mandatperiod", period=2022)
    assert p["urval"] | {} == {"ar": None, "period": 2022, "namn": "Mandatperioden 2022–2026",
                               "fran": "2022-10-15", "till": "2026-10-14"}
    for q in ({"ar": "1999"}, {"ar": "tjugo"}, {"period": "2022"}, {"ar": "mandatperiod", "period": "2010"}):
        assert api.get("/api/topplistor", params=q).status_code == 422, q


def test_underlag_som_statistiken(api):
    t = listor(api)
    stat = api.get("/api/statistik/behandlingar", params={"fran": 2026, "till": 2026}).json()
    assert t["underlag"]["sammantraden"] == stat["summa"]["sammantraden"] == len(kf_sammantraden(api))
    assert t["underlag"]["ej_tolkade"] == stat["underlag"]["ej_tolkade"]
    assert t["underlag"]["paragrafprotokoll"] == stat["underlag"]["paragrafprotokoll"]
    # Mandatperioden 2022–2026 slutar den 14 oktober och har färre sammanträden än året.
    efter = [s for s in kf_sammantraden(api) if s["datum"] > "2026-10-14"]
    assert efter
    assert listor(api, ar="mandatperiod", period=2022)["underlag"]["sammantraden"] == t["underlag"]["sammantraden"] - len(efter)


def test_ingen_lista_over_narvaro_eller_aterremisser(api):
    # Ingen närvaro per person (frånvaro kan bero på sjukdom), och inga återremisser per ärende (ett ärende
    # återremitteras sällan mer än en gång, så listan säger inget).
    assert list(listor(api)["listor"]) == [
        "langsta_beredning", "langst_pagaende", "reservationer_per_parti", "reservationer_per_ledamot",
        "motioner_per_parti", "langsta_ledtid_motioner", "jamnaste_voteringar", "yrkanden_per_ledamot"]


# Per parti och per mandat

def test_reservationer_per_parti_visar_alla_partier_med_antal_per_mandat(api):
    t = listor(api)
    assert t["mandat"] == {"valar": 2022, "period": "2022–2026", "totalt": 43,
                           "per_parti": {"C": 4, "KD": 2, "L": 1, "M": 7, "MP": 3, "S": 17, "SD": 6, "V": 3}}
    rader = {r["parti"]: r for r in t["listor"]["reservationer_per_parti"]["rader"]}
    # Alla partier i fullmäktige, också de utan reservationer.
    assert set(MANDAT_2022) <= set(rader)
    assert rader["S"]["antal"] == 0 and rader["S"]["per_mandat"] == 0 and rader["S"]["mandat"] == 17
    sd = rader["SD"]
    assert (sd["antal"], sd["mandat"], sd["per_mandat"]) == (7, 6, 1.17)
    # Varje rad länkar till behandlingarna som räknats, och de har märkningen reservation med partiet.
    for r in rader.values():
        assert len(r["behandlingar"]) == r["antal"]
    for b in sd["behandlingar"]:
        x = api.get(f"/api/sammantraden/{b['sammantrade']['id']}/behandlingar/{b['paragraf']}").json()
        assert x["reservationer"], b
    # Störst antal först.
    # Störst antal först, och lika antal i bokstavsordning efter förkortning.
    ordning = [(-r["antal"], r["parti"]) for r in t["listor"]["reservationer_per_parti"]["rader"] if r["parti"]]
    assert ordning == sorted(ordning)
    assert list(t["mandat"]["per_parti"]) == sorted(t["mandat"]["per_parti"])


def test_motioner_per_parti_med_okant_parti_sist(api):
    rader = listor(api)["listor"]["motioner_per_parti"]["rader"]
    assert set(MANDAT_2022) <= {r["parti"] for r in rader}
    assert rader[-1]["parti"] is None and rader[-1]["per_mandat"] is None
    l = next(r for r in rader if r["parti"] == "L")
    assert (l["antal"], l["mandat"], l["per_mandat"]) == (3, 1, 3.0)
    assert all(len(r["behandlingar"]) == r["antal"] for r in rader)


def test_per_mandat_saknas_utan_valdata(database_url, google):
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    logga_in(a, "redaktor")
    assert a.post("/api/insamlingar").json()["status"] == "lyckad"
    t = listor(a)
    assert t["mandat"] is None
    assert all(r["per_mandat"] is None for r in t["listor"]["reservationer_per_parti"]["rader"])


# Per ledamot

def test_partigrupp_raknas_for_partiet_men_inte_for_ledamoterna(api, database_url):
    with db.connect(database_url) as conn:
        grupp = conn.execute(
            """
            SELECT b.sammantrade_id, b.paragraf FROM reservation r JOIN behandling b ON b.id = r.behandling_id
            WHERE r.partier = ARRAY['SD'] AND r.personer = '[]'
              AND NOT EXISTS (SELECT 1 FROM reservation r2 WHERE r2.behandling_id = b.id AND r2.personer <> '[]')
            LIMIT 1
            """).fetchone()
    assert grupp, "protokollen ska ha en reservation från hela SD-gruppen"
    nyckel = (grupp["sammantrade_id"], grupp["paragraf"])
    t = listor(api)["listor"]
    sd = next(r for r in t["reservationer_per_parti"]["rader"] if r["parti"] == "SD")
    assert nyckel in nycklar(sd)
    assert not [p for p in t["reservationer_per_ledamot"]["rader"] if nyckel in nycklar(p)]


def test_bara_personer_i_ledamotsregistret_raknas(api, database_url):
    s = kf_sammantraden(api)[0]
    b = next(b for b in behandlingar(api, s) if not b["markningar"])
    with db.connect(database_url) as conn:
        bid = conn.execute("SELECT id FROM behandling WHERE sammantrade_id = %s AND paragraf = %s",
                           (s["id"], b["paragraf"])).fetchone()["id"]
        conn.execute("""INSERT INTO reservation (behandling_id, ordning, text, personer)
                        VALUES (%s, 0, 'Ingen Registrerad (S) reserverar sig.', '[{"namn": "Ingen Registrerad", "parti": "S"}]')""",
                     (bid,))
    t = listor(api)["listor"]
    s_rad = next(r for r in t["reservationer_per_parti"]["rader"] if r["parti"] == "S")
    assert s_rad["antal"] == 1 and nycklar(s_rad) == {(s["id"], b["paragraf"])}
    assert "Ingen Registrerad" not in {p["namn"] for p in t["reservationer_per_ledamot"]["rader"]}


def test_reservationer_och_yrkanden_per_ledamot(api, database_url):
    t = listor(api)["listor"]
    res = t["reservationer_per_ledamot"]
    assert len(res["rader"]) == 10 and res["totalt"] == 18
    forsta = res["rader"][0]
    assert (forsta["plats"], forsta["namn"], forsta["parti"], forsta["antal"]) == (1, "Charlotte Höglund Bystedt", "SD", 4)
    assert api.get(f"/api/ledamoter/{forsta['person_id']}").status_code == 200
    # Lika antal delar placering.
    assert [r["plats"] for r in res["rader"][:4]] == [1, 2, 2, 2]

    yrk = t["yrkanden_per_ledamot"]["rader"]
    sehlin = yrk[0]
    assert (sehlin["plats"], sehlin["namn"], sehlin["antal"]) == (1, "Glenn Sehlin", 9)
    with db.connect(database_url) as conn:
        n = conn.execute(
            """SELECT count(*) AS n FROM yrkande y JOIN behandling b ON b.id = y.behandling_id
               JOIN sammantrade s ON s.id = b.sammantrade_id
               WHERE y.personer @> '[{"namn": "Glenn Sehlin"}]' AND extract(year FROM s.datum) = 2026""").fetchone()["n"]
    assert n == 9
    assert all(len(r["behandlingar"]) <= r["antal"] for r in yrk)


# Voteringar

def test_jamnaste_voteringar_med_rattelse_av_rosterna(api, database_url):
    t = listor(api)["listor"]["jamnaste_voteringar"]
    # Skillnaden i procent av ja- och nejrösterna, minst först.
    procent = [r["skillnad_procent"] for r in t["rader"]]
    assert procent == sorted(procent) and t["totalt"] == len(t["rader"])
    for r in t["rader"]:
        assert r["skillnad"] == abs(r["ja"] - r["nej"])
        assert r["skillnad_procent"] == round(100 * r["skillnad"] / (r["ja"] + r["nej"]), 1)
    # KF 2026-02-23 § 5: 37–6. Utan siffror i texten räknas listan, med publicerade rättelser (36–7).
    s = next(x for x in kf_sammantraden(api) if x["datum"] == "2026-02-23")
    rad = lambda lista: next(r for r in lista["rader"] if r["behandling"]["sammantrade"]["id"] == s["id"]  # noqa: E731
                             and r["behandling"]["paragraf"] == 5)
    assert (rad(t)["ja"], rad(t)["nej"], rad(t)["skillnad_procent"]) == (37, 6, 72.1)
    with db.connect(database_url) as conn:
        conn.execute("UPDATE votering SET ja = NULL, nej = NULL WHERE behandling_id = "
                     "(SELECT id FROM behandling WHERE sammantrade_id = %s AND paragraf = 5)", (s["id"],))
    publicerad(api, sammantrade_id=s["id"], objekt="rost", paragraf=5, votering=1, namn="Lennart Molin", falt="rost",
               nytt="nej", motivering="Rösten står fel i listan.")
    t = listor(api)["listor"]["jamnaste_voteringar"]
    assert (rad(t)["ja"], rad(t)["nej"], rad(t)["skillnad_procent"]) == (36, 7, 67.4)


# Ärenden och årsavgränsningen

def test_beredning_raknas_till_aret_for_det_slutliga_beslutet(api, database_url):
    alla = kf_sammantraden(api)
    forsta, sista = alla[0], alla[-1]
    assert sista["datum"] > "2026-10-14"
    a = med_arende(api, database_url, forsta)[0]
    b = med_arende(api, database_url, sista)[0]
    flytta_till_arende(database_url, a["arende_id"], sista["id"], b["paragraf"], "Kommunfullmäktige beslutar att anta planen.")
    dagar = (date.fromisoformat(sista["datum"]) - date.fromisoformat(forsta["datum"])).days

    [r] = [r for r in listor(api)["listor"]["langsta_beredning"]["rader"] if r["arende_id"] == a["arende_id"]]
    assert (r["dagar"], r["fran"], r["till"]) == (dagar, forsta["datum"], sista["datum"])
    assert nycklar(r) >= {(forsta["id"], a["paragraf"]), (sista["id"], b["paragraf"])}
    # Det slutliga beslutet kom efter mandatperiodens slut: inte med i 2022–2026.
    period = listor(api, ar="mandatperiod", period=2022)["listor"]["langsta_beredning"]["rader"]
    assert a["arende_id"] not in {r["arende_id"] for r in period}
    # Ett förslag till ett annat organ är inget slutligt beslut.
    with db.connect(database_url) as conn:
        conn.execute("UPDATE behandling SET beslut = 'Kommunstyrelsen föreslår kommunfullmäktige att anta planen.' "
                     "WHERE sammantrade_id = %s AND paragraf = %s", (sista["id"], b["paragraf"]))
    assert a["arende_id"] not in {r["arende_id"] for r in listor(api)["listor"]["langsta_beredning"]["rader"]}


def test_langst_pagaende_raknas_fran_forsta_behandlingen_till_i_dag(api):
    rader = listor(api)["listor"]["langst_pagaende"]["rader"]
    assert rader
    for r in rader:
        assert r["dagar"] == (date.today() - date.fromisoformat(r["fran"])).days
        assert r["fran"] == min(b["sammantrade"]["datum"] for b in r["behandlingar"])
    assert [r["dagar"] for r in rader] == sorted((r["dagar"] for r in rader), reverse=True)
    motion = next(r for r in rader if r["rubrik"] == "Motion - Översyn av taxor och avgifter")
    assert (motion["plats"], motion["status"], motion["fran"]) == (1, "Obesvarad motion", "2026-02-23")


def test_ledtid_for_motion_raknas_till_aret_den_besvarades(api, database_url):
    pagaende = listor(api)["listor"]["langst_pagaende"]["rader"]
    motion = next(r for r in pagaende if r["rubrik"] == "Motion - Översyn av taxor och avgifter")
    sista = kf_sammantraden(api)[-1]
    b = med_arende(api, database_url, sista)[0]
    flytta_till_arende(database_url, motion["arende_id"], sista["id"], b["paragraf"], "Motionen avslås.")

    [r] = listor(api)["listor"]["langsta_ledtid_motioner"]["rader"]
    assert (r["arende_id"], r["vackt"], r["besvarad"], r["utfall"]) == (motion["arende_id"], "2026-02-23",
                                                                          sista["datum"], "avslag")
    assert r["dagar"] == (date.fromisoformat(sista["datum"]) - date(2026, 2, 23)).days
    assert (sista["id"], b["paragraf"]) in nycklar(r)
    # Besvarad efter den 14 oktober 2026: inte med i mandatperioden 2022–2026, och inte längre pågående.
    assert listor(api, ar="mandatperiod", period=2022)["listor"]["langsta_ledtid_motioner"]["rader"] == []
    assert motion["arende_id"] not in {x["arende_id"] for x in listor(api)["listor"]["langst_pagaende"]["rader"]}
