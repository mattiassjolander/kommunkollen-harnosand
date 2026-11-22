"""Kopplingsregeln motionstitel (#108): svar på motioner kopplas till fullmäktiges beslut att väcka motionen."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient

from app import db
from app.arenden import _Beh, _forslag_till_kopplingar, arende_for, koppla, motionstitel

VACKT = "Kommunfullmäktige beslutar\natt överlämna motionen till kommunstyrelsen för beredning."


@pytest.mark.parametrize(
    ("rubrik", "vantat"),
    [
        ("Motion - Kontinuitet i allmän förskola", "kontinuitet i allmän förskola"),
        ("Motion- Kontinuitet i allmän förskola", "kontinuitet i allmän förskola"),
        ("Svar på motion om kontinuitet i allmän förskola", "kontinuitet i allmän förskola"),
        ("Svar på motion - Inför elektronisk körjournal", "inför elektronisk körjournal"),
        ("Svar på motion - Upphör med vegetariska substitut i skolmaten", "upphör med vegetariska substitut i skolmaten"),
        ("Svar på motion - Utökade tider för serveringstillstånd", "utökade tider för serveringstillstånd"),
        ("Svar på motion - Slopa enprocentregeln", "slopa enprocentregeln"),
        ("Motion – Jämställdhetsstrategi (KS2022-206)", "jämställdhetsstrategi"),
        ("Motion - Inför elektronisk körjournal (anmälan)", "inför elektronisk körjournal"),
        ("Motion - Slopa enprocentregeln (Anmälan)", "slopa enprocentregeln"),
        ("Motion: Snabbladdare för elfordon", "snabbladdare för elfordon"),
        ("Yttrande över motionen om  Fler   laddplatser", "fler laddplatser"),
        ("Motion - Uppföljning av bifallna e-förslag, lex belysning", "uppföljning av bifallna e-förslag, lex belysning"),
        ("Borgenstak från 2026", None),
        ("Tillkommande motioner, interpellationer och frågor", None),
        ("Motioner", None),
        ("Motion", None),
    ],
)
def test_motionstitel(rubrik, vantat):
    assert motionstitel(rubrik) == vantat


def beh(nyckel, organ, datum, rubrik, dnr=(), beslut="Beslutar att anta förslaget.", hanv=()):
    b = _Beh(nyckel, organ, date.fromisoformat(datum), rubrik, list(dnr), beslut=beslut)
    b.hanvisningar = [{"organ": o, "datum": date.fromisoformat(d), "paragraf": p, "text": f"Protokollsutdrag {o} {d} § {p}"}
                      for o, d, p in hanv]
    return b


def kopplingar(*b):
    return {par: (grund, status) for par, (grund, _, status) in _forslag_till_kopplingar({x.nyckel: x for x in b}).items()}


def test_svaret_kopplas_automatiskt_till_den_vackta_motionen_och_ovriga_via_hanvisningen():
    kf = beh((1, 133), "KF", "2025-10-27", "Motion - Kontinuitet i allmän förskola", ["2025-000475"], VACKT)
    skol = beh((2, 105), "SKOL", "2026-10-01", "Svar på motion om kontinuitet i allmän förskola")
    ks = beh((3, 162), "KS", "2026-11-03", "Svar på motion om kontinuitet i allmän förskola",
             hanv=[("SKOL", "2026-10-01", 105)])
    assert kopplingar(kf, skol, ks) == {
        ((1, 133), (2, 105)): ("motionstitel", "automatisk"),  # den tidigaste behandlingen som svarar
        ((2, 105), (3, 162)): ("hanvisning", "automatisk"),
    }
    # Utan hänvisningen kopplas KS-behandlingen på samma sätt.
    ks.hanvisningar = []
    assert kopplingar(kf, skol, ks)[((1, 133), (3, 162))] == ("motionstitel", "automatisk")


def test_anmalan_i_kf_hindrar_inte_den_automatiska_kopplingen():
    # KF 2026-06-15 § 117 och KS 2026-11-03 § 159, som blev ett förslag före rättelsen.
    kf = beh((1, 117), "KF", "2026-06-15", "Motion - Inför elektronisk körjournal (anmälan)", [], VACKT)
    ks = beh((2, 159), "KS", "2026-11-03", "Svar på motion - Inför elektronisk körjournal")
    assert kopplingar(kf, ks) == {((1, 117), (2, 159)): ("motionstitel", "automatisk")}


def test_liknande_titel_eller_flera_vackta_motioner_ger_forslag():
    lex = beh((1, 134), "KF", "2025-10-27", "Motion - Uppföljning av bifallna e-förslag, lex belysning",
              ["2025-000472"], VACKT)
    motioner = beh((4, 50), "KF", "2024-04-29", "Motion - Uppföljning av bifallna motioner", ["2024-000284"], VACKT)
    ks = beh((2, 43), "KS", "2026-03-31", "Motion - Uppföljning av bifallna e-förslag", ["KS/2026-115"],
             "Kommunstyrelsen föreslår kommunfullmäktige besluta att avslå motionen.")
    kf = beh((3, 70), "KF", "2026-04-27", "Motion - Uppföljning av bifallna e-förslag", ["KS/2026-115"],
             "Kommunfullmäktige beslutar att avslå motionen.")
    # Början på titeln ger ett förslag, och den nästan lika motionen från 2024 kopplas inte.
    assert kopplingar(lex, motioner, ks, kf) == {
        ((2, 43), (3, 70)): ("diarienummer", "automatisk"),
        ((1, 134), (2, 43)): ("motionstitel", "forslag"),
    }

    # Två väckta motioner med samma titel: förslag till båda.
    a = beh((1, 10), "KF", "2025-01-27", "Motion - Slopa enprocentregeln", [], VACKT)
    b = beh((2, 20), "KF", "2025-05-26", "Motion: Slopa enprocentregeln", [], VACKT)
    svar = beh((3, 163), "KS", "2026-11-03", "Svar på motion - Slopa enprocentregeln")
    assert kopplingar(a, b, svar) == {((1, 10), (3, 163)): ("motionstitel", "forslag"),
                                      ((2, 20), (3, 163)): ("motionstitel", "forslag")}

    # Liknande men inte samma titel.
    c = beh((1, 11), "KF", "2025-01-27", "Motion - Utökade tider för serveringstillstånd i centrum", [], VACKT)
    svar = beh((3, 161), "KS", "2026-11-03", "Svar på motion - Utökade öppettider för serveringstillstånd")
    assert kopplingar(c, svar) == {((1, 11), (3, 161)): ("motionstitel", "forslag")}


def test_motion_som_vacks_efter_behandlingen_eller_i_samlingspunkten_kopplas_inte():
    svar = beh((1, 159), "KS", "2026-11-03", "Svar på motion - Inför elektronisk körjournal")
    senare = beh((2, 5), "KF", "2026-11-23", "Motion - Inför elektronisk körjournal", [], VACKT)
    assert kopplingar(svar, senare) == {}

    samling = beh((3, 140), "KF", "2025-10-27", "Tillkommande motioner, interpellationer och frågor",
                  beslut="Kommunfullmäktige beslutar att överlämna följande motioner till kommunstyrelsen för "
                         "beredning: • Motion – Inför elektronisk körjournal (KS2025-480).")
    assert kopplingar(samling, svar) == {}
    # Ett beslut som inte väcker motionen är ingen väckt motion.
    remiss = beh((4, 9), "KF", "2025-10-27", "Motion - Inför elektronisk körjournal", [],
                 "Kommunfullmäktige beslutar att återremittera ärendet.")
    assert kopplingar(remiss, svar) == {}


def _sammantrade(conn, organ, datum, behandlingar):
    sid = conn.execute("INSERT INTO sammantrade (organ, nyckel, datum) VALUES (%s, %s, %s) RETURNING id",
                       (organ, datum, datum)).fetchone()["id"]
    for i, (paragraf, rubrik, dnr, beslut, hanv) in enumerate(behandlingar):
        bid = conn.execute(
            "INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, diarienummer, beslut)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", (sid, i, paragraf, rubrik, list(dnr), beslut)).fetchone()["id"]
        for j, (o, d, p) in enumerate(hanv):
            conn.execute("INSERT INTO hanvisning (behandling_id, ordning, organ, datum, paragraf, text)"
                         " VALUES (%s, %s, %s, %s, %s, %s)", (bid, j, o, d, p, f"{o} protokollsutdrag, {d}, § {p}"))
    return sid


def test_motionens_sida_visar_beredningen_och_motionen_ar_obesvarad_tills_kf_beslutar(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[], anonym_lasning=True))
    with db.connect(database_url) as conn:
        kf = _sammantrade(conn, "KF", "2025-10-27", [
            (133, "Motion - Kontinuitet i allmän förskola", ["2025-000475"], VACKT, []),
            (134, "Motion - Uppföljning av bifallna e-förslag, lex belysning", ["2025-000472"], VACKT, []),
        ])
        _sammantrade(conn, "KF", "2024-04-29", [
            (50, "Motion - Uppföljning av bifallna motioner", ["2024-000284"], VACKT, [])])
        skol = _sammantrade(conn, "SKOL", "2026-10-01", [
            (105, "Svar på motion om kontinuitet i allmän förskola", [], "Skolnämnden beslutar att anta yttrandet.", [])])
        ks = _sammantrade(conn, "KS", "2026-11-03", [
            (162, "Svar på motion om kontinuitet i allmän förskola", [],
             "Kommunstyrelsen föreslår kommunfullmäktige besluta att avslå motionen.", [("SKOL", "2026-10-01", 105)])])
        ks_mars = _sammantrade(conn, "KS", "2026-03-31", [
            (43, "Motion - Uppföljning av bifallna e-förslag", ["KS/2026-115"],
             "Kommunstyrelsen föreslår kommunfullmäktige besluta att avslå motionen.", [])])
        _sammantrade(conn, "KF", "2026-04-27", [
            (70, "Motion - Uppföljning av bifallna e-förslag", ["KS/2026-115"],
             "Kommunfullmäktige beslutar att avslå motionen.", [])])
        koppla(conn)
        conn.commit()

    def arende(sid, paragraf):
        with db.connect(database_url) as conn:
            arende_id = arende_for(conn, sid, paragraf)["id"]
        return api.get(f"/api/arenden/{arende_id}").json()

    a = arende(kf, 133)
    assert [(b["sammantrade"]["organ"]["id"], b["paragraf"]) for b in a["behandlingar"]] == [
        ("KF", 133), ("SKOL", 105), ("KS", 162)]
    assert {(k["grund"], k["status"], k["underlag"]) for k in a["kopplingar"]} == {
        ("motionstitel", "automatisk", "kontinuitet i allmän förskola"),
        ("hanvisning", "automatisk", "SKOL protokollsutdrag, 2026-10-01, § 105")}
    assert arende(skol, 105)["id"] == arende(ks, 162)["id"] == a["id"]

    statistik = api.get("/api/statistik/motioner", params={"fran": 2024, "till": 2026}).json()
    [m] = [m for m in statistik["motioner"]["lista"] if m["arende_id"] == a["id"]]
    assert [(b["sammantrade"]["organ"]["id"], b["paragraf"]) for b in m["behandlingar"]] == [
        ("KF", 133), ("SKOL", 105), ("KS", 162)]
    assert (m["vackt"]["paragraf"], m["besvarad"], m["utfall"]) == (133, None, None)

    # Lex belysning: ett förslag som redaktören bekräftar. Då är motionen avgjord av KF 2026-04-27 § 70.
    assert len(arende(kf, 134)["behandlingar"]) == 1
    assert api.post("/api/auth/test/redaktor").status_code == 200
    forslag = [k for k in api.get("/api/kopplingar").json() if k["grund"] == "motionstitel"]
    assert [(k["fran"]["paragraf"], k["till"]["paragraf"], k["underlag"]) for k in forslag] == [
        (134, 43, "uppföljning av bifallna e-förslag, lex belysning")]
    assert api.post(f"/api/kopplingar/{forslag[0]['id']}/bekraftelse").status_code == 200
    assert arende(kf, 134)["id"] == arende(ks_mars, 43)["id"]
    statistik = api.get("/api/statistik/motioner", params={"fran": 2024, "till": 2026}).json()
    [m] = [m for m in statistik["motioner"]["lista"] if m["vackt"] and m["vackt"]["paragraf"] == 134]
    assert (m["besvarad"]["sammantrade"]["datum"], m["besvarad"]["paragraf"], m["utfall"]) == ("2026-04-27", 70, "avslag")
