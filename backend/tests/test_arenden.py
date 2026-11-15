"""Ärendespårning (#32): behandlingar i olika organ kopplas till samma ärende (ADR-0003).

Insamlingen körs mot inspelade protokoll från alla organ (se test_protokoll_organ). De förväntade
kopplingarna är kontrollerade för hand mot protokollen.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_protokoll_organ import kor, protokollkallor

from app import db
from app.arenden import _Beh, _forslag_till_kopplingar, koppla
from app.protokoll import tolka_om


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=protokollkallor(), anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def sammantrade_id(api: TestClient, organ: str, datum: str) -> int:
    [s] = [s for s in api.get("/api/sammantraden", params={"organ": organ}).json() if s["datum"] == datum]
    return s["id"]


def arende(api: TestClient, organ: str, datum: str, paragraf: int) -> dict:
    b = api.get(f"/api/sammantraden/{sammantrade_id(api, organ, datum)}/behandlingar/{paragraf}").json()
    svar = api.get(f"/api/arenden/{b['arende']['id']}")
    assert svar.status_code == 200, svar.text
    return svar.json()


def vag(a: dict) -> list[tuple[str, str, int]]:
    return [(b["sammantrade"]["organ"]["id"], b["sammantrade"]["datum"], b["paragraf"]) for b in a["behandlingar"]]


def test_ett_arende_fran_ks_till_kf_ar_ett_arende_med_behandlingarna_i_ordning(api):
    # KF 2026-03-23 §38 "Borgenstak från 2026" bereddes av KS 2026-02-24 §31. Samma diarienummer i
    # kommunstyrelsens serie, och KF:s beslutsunderlag hänvisar till KS-paragrafen.
    a = arende(api, "KF", "2026-03-23", 38)
    assert vag(a) == [("KS", "2026-02-24", 31), ("KF", "2026-03-23", 38)]
    assert a["rubrik"] == "Borgenstak från 2026"
    assert a["diarienummer"] == ["KS/2026-113"]
    [k] = a["kopplingar"]
    assert (k["grund"], k["status"], k["underlag"]) == ("diarienummer", "automatisk", "KS/2026-113")
    assert a["slutligt_beslut"]["organ"]["id"] == "KF"

    # Behandlingen visar sitt ärende, och KS-behandlingen hör till samma ärende.
    ks = api.get(f"/api/sammantraden/{sammantrade_id(api, 'KS', '2026-02-24')}/behandlingar/31").json()
    assert ks["arende"] == {"id": a["id"], "antal_behandlingar": 2}


def test_diarienummer_kopplar_men_inte_samlingspunkter(api):
    # KS 2025-03-04 §33 och 2025-01-21 §10 "Dialog utifrån uppsiktsplikt 2025" har samma diarienummer.
    assert vag(arende(api, "KS", "2025-03-04", 33)) == [("KS", "2025-01-21", 10), ("KS", "2025-03-04", 33)]

    # KF 2024-02-26 §7 har samma diarienummer som KS 2024-02-13 §17 och hänvisar dessutom till den.
    # Det blir en koppling mellan behandlingarna, inte två.
    a = arende(api, "KF", "2024-02-26", 7)
    assert vag(a) == [("KS", "2024-02-13", 17), ("KF", "2024-02-26", 7)]
    assert len(a["kopplingar"]) == 1

    # Fasta punkter som "Val av justerare" och "Valärenden 2024" kopplas inte år för år.
    assert len(arende(api, "KS", "2025-03-04", 21)["behandlingar"]) == 1
    assert len(arende(api, "KF", "2024-03-25", 30)["behandlingar"]) == 1


def test_osakra_kopplingar_hamnar_i_kon_och_redaktoren_bekraftar_eller_avvisar(api, database_url):
    # Kön kräver redaktörsroll.
    assert api.get("/api/kopplingar").status_code == 401
    assert api.post("/api/auth/test/lasare").status_code == 200
    assert api.get("/api/kopplingar").status_code == 403
    assert api.post("/api/kopplingar/1/bekraftelse").status_code == 403
    assert api.post("/api/auth/test/redaktor").status_code == 200

    ko = api.get("/api/kopplingar").json()
    par = {((k["fran"]["sammantrade"]["organ"]["id"], k["fran"]["paragraf"]),
            (k["till"]["sammantrade"]["organ"]["id"], k["till"]["paragraf"])): k for k in ko}
    # KS 2025-03-04 §34 hänvisar till en tidigare KS-paragraf (samma nivå), och §38 till ett
    # KF-beslut (nedåt). Båda blir förslag.
    samma_niva = par[(("KS", 16), ("KS", 34))]
    nedat = par[(("KF", 13), ("KS", 38))]
    assert samma_niva["grund"] == "hanvisning"
    assert samma_niva["underlag"] == "Protokollsutdrag KS 2023-01-18 § 16"
    assert samma_niva["fran"]["sammantrade"]["datum"] == "2023-01-18"
    assert len(arende(api, "KS", "2025-03-04", 34)["behandlingar"]) == 1

    fore = arende(api, "KS", "2025-03-04", 34)["id"]
    svar = api.post(f"/api/kopplingar/{samma_niva['id']}/bekraftelse")
    assert svar.status_code == 200, svar.text
    assert (svar.json()["status"], svar.json()["redaktor"]) == ("bekraftad", "test-redaktor@kommunkollen.test")
    a = arende(api, "KS", "2025-03-04", 34)
    assert vag(a) == [("KS", "2023-01-18", 16), ("KS", "2025-03-04", 34)]
    [k] = a["kopplingar"]
    assert k["status"] == "bekraftad"
    assert a["id"] == fore

    assert api.post(f"/api/kopplingar/{nedat['id']}/avvisning").json()["status"] == "avvisad"
    assert len(arende(api, "KS", "2025-03-04", 38)["behandlingar"]) == 2  # KF 2025-03-24 §23
    assert ("KF", "2023-02-27", 13) not in vag(arende(api, "KS", "2025-03-04", 38))
    assert {k["id"] for k in api.get("/api/kopplingar").json()} == {k["id"] for k in ko} - {samma_niva["id"], nedat["id"]}

    # En omtolkning tar bort och skapar om behandlingarna och räknar om kopplingarna. Redaktörens
    # beslut och ärendets id står kvar.
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))
        koppla(conn)
    a = arende(api, "KS", "2025-03-04", 34)
    assert (a["id"], [k["status"] for k in a["kopplingar"]]) == (fore, ["bekraftad"])
    assert api.get("/api/kopplingar", params={"status": "avvisad"}).json()[0]["id"] == nedat["id"]

    assert api.post("/api/kopplingar/999999/bekraftelse").status_code == 404
    assert api.get("/api/arenden/999999").status_code == 404


def beh(nyckel, organ, datum, rubrik, dnr=(), hanv=()):
    b = _Beh(nyckel, organ, date.fromisoformat(datum), rubrik, list(dnr))
    b.hanvisningar = [{"organ": o, "datum": date.fromisoformat(d), "paragraf": p, "text": f"Protokollsutdrag {o} {d} § {p}"}
                      for o, d, p in hanv]
    return b


def test_kopplingsreglerna_for_hanvisningar():
    # Nämndens och kommunstyrelsens diarienummer skiljer sig (ADR-0003). Hänvisningen avgör.
    sam = beh((1, 61), "SAM", "2026-05-21", "Detaljplan för Västanå 2:14", ["2026-000131"])
    ks = beh((2, 90), "KS", "2026-06-02", "Antagande av detaljplan för Västanå 2:14", ["2026-000386"],
             [("SAM", "2026-05-21", 61)])
    annan = beh((3, 61), "SOC", "2026-05-21", "Verksamhetsplan")
    ks2 = beh((2, 91), "KS", "2026-06-02", "Yttrande över remiss", [], [("SAM", "2026-05-21", 61)])
    utan_organ = beh((4, 5), "KF", "2026-06-15", "Något annat", [], [(None, "2026-05-21", 61)])
    kannedom = beh((2, 92), "KS", "2026-06-02", "Ärenden för kännedom", [], [("SOC", "2026-05-21", 61)])
    regler = _forslag_till_kopplingar({b.nyckel: b for b in (sam, ks, annan, ks2, utan_organ, kannedom)})
    assert {par: status for par, (_, _, status) in regler.items()} == {
        ((1, 61), (2, 90)): "automatisk",  # uppåt, liknande rubrik
        ((1, 61), (2, 91)): "forslag",  # uppåt, olika rubrik
        ((1, 61), (4, 5)): "forslag",  # utan organ: alla behandlingar den dagen med den paragrafen
        ((3, 61), (4, 5)): "forslag",
    }
