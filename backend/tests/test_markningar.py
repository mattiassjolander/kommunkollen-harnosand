"""Märkningar på behandlingar och ärenden (#162): votering, reservation, oenighet m.fl.

Reglerna prövas en och en, och mot kommunfullmäktiges protokoll för 2026 (inspelade). KF 2026-02-23 § 5 har en
votering med 37 ja och 6 nej och en reservation från SD, kontrollerat för hand mot protokollet.
"""

from __future__ import annotations

from datetime import date

import pytest
from test_rattelser import api, logga_in, publicerad, sammantrade_id  # noqa: F401

from app import db, markningar
from app.markningar import flera_forslag, for_arende, lang_beredning, yrkanden_gar_isar


def ids(ms: list[dict]) -> list[str]:
    return [m["id"] for m in ms]


# Reglerna

@pytest.mark.parametrize(
    ("text", "vantat"),
    [
        ("Ordföranden finner att det föreligger två förslag till beslut, kommunstyrelsens förslag och Olle Löfgrens (L) "
         "förslag.", True),
        ("Ordföranden finner att det föreligger tre förslag till beslut samt ett förslag om en tilläggsattsats.", True),
        ("Ordföranden finner att det föreligger 2 förslag till beslut.", True),
        ("Ordföranden finner att det föreligger endast ett förslag till beslut, kommunstyrelsens förslag.", False),
        ("Ordföranden finner att det föreligger 1 förslag till beslut.", False),
        (None, False),
    ],
)
def test_flera_forslag_i_propositionsordningen(text, vantat):
    assert flera_forslag(text) is vantat


@pytest.mark.parametrize(
    ("yrkanden", "vantat"),
    [
        (["Andreas Sjölander (S) yrkar bifall till kommunstyrelsens förslag.",
          "Glenn Sehlin (SD) yrkar avslag på kommunstyrelsens förslag."], True),
        (["Helena Elfvendal (MP) yrkar på bifall till kommunstyrelsens förslag.",
          "Christina Lindberg (C) yrkar på återremiss."], True),
        (["Andreas Sjölander (S) och Helena Elfvendal (MP) yrkar bifall till kommunstyrelsens förslag.",
          "Eva-Clara Viklund (M) yrkar på ändring i attsats nr.1 enligt följande: att godkänna taxan."], True),
        # Samma förslag från flera går inte isär.
        (["Andreas Sjölander (S) yrkar bifall till kommunstyrelsens förslag.",
          "Christina Lindberg (C) yrkar bifall till kommunstyrelsens förslag."], False),
        # Ett ensamt yrkande, även om avslag, är inte två yrkanden.
        (["Eva-Clara Viklund (M) yrkar på återremiss i första hand och på avslag i andra hand."], False),
        # Alla yrkar återremiss: ingen yrkar bifall.
        (["Göran Sjögren (SD) yrkar på återremiss.", "Christina Lindberg (C) yrkar på återremiss."], False),
        # Ett medskick är inget yrkande mot förslaget.
        (["Andreas Sjölander (S) yrkar bifall på kommunstyrelsens förslag.",
          "Carl-Fredrik Edgren (V) lämnar in ett medskick till kommande delårsrapport."], False),
        ([], False),
    ],
)
def test_yrkanden_som_gar_isar(yrkanden, vantat):
    assert yrkanden_gar_isar(yrkanden) is vantat


@pytest.mark.parametrize(
    ("forsta", "slutligt", "vantat"),
    [
        (date(2025, 3, 1), date(2026, 3, 2), True),
        (date(2025, 3, 1), date(2026, 3, 1), False),  # exakt 12 månader är inte mer än 12
        (date(2025, 3, 1), date(2025, 11, 30), False),
        (date(2024, 2, 29), date(2025, 3, 1), True),
        (date(2025, 3, 1), None, False),
    ],
)
def test_lang_beredning(forsta, slutligt, vantat):
    assert lang_beredning(forsta, slutligt) is vantat


def _beh(sammantrade_id: int, datum: date, beslut: str, ms: list[dict], rubrik: str = "Ny taxa") -> dict:
    return {"sammantrade_id": sammantrade_id, "datum": datum, "beslut": beslut, "rubrik": rubrik, "markningar": ms}


def test_arendets_markningar_ar_summan_med_lang_beredning_och_aterkommande():
    votering = {"id": "votering", "text": "Votering 26–24"}
    bs = [
        _beh(1, date(2025, 1, 10), "Samhällsnämnden föreslår kommunstyrelsen att besluta att anta taxan.",
             [{"id": "reservation", "text": "Reservation M", "partier": ["M"]}, {"id": "oenighet", "text": "Oenighet"}]),
        _beh(2, date(2025, 6, 10), "Kommunstyrelsen föreslår kommunfullmäktige besluta att anta taxan.",
             [{"id": "reservation", "text": "Reservation C, M", "partier": ["C", "M"]},
              {"id": "oenighet", "text": "Oenighet"}]),
        _beh(3, date(2026, 2, 23), "Kommunfullmäktige beslutar att anta taxan.",
             [votering, {"id": "oenighet", "text": "Oenighet"}]),
    ]
    a = for_arende(bs)
    assert ids(a) == ["votering", "reservation", "oenighet", "lang_beredning", "aterkommande"]
    assert a[0] == votering | {"antal": 1}  # en behandling: dess text
    assert a[1] == {"id": "reservation", "text": "Reservation (2)", "antal": 2, "partier": ["C", "M"]}
    assert a[2]["text"] == "Oenighet (3)"

    # Utan slutligt beslut finns ingen lång beredning, och med ett sammanträde är ärendet inte återkommande.
    assert "lang_beredning" not in ids(for_arende(bs[:2]))
    assert ids(for_arende(bs[:1])) == ["reservation", "oenighet"]
    # Samlingspunkter räknas inte som återkommande.
    samling = [_beh(i, date(2026, i, 1), "Kommunfullmäktige beslutar att lägga informationen till handlingarna.", [],
                    rubrik="Meddelanden") for i in (1, 2)]
    assert for_arende(samling) == []


def test_enig_satts_aldrig():
    # Att protokollet inte nämner yrkanden eller reservationer bevisar inte enighet (#162, beslut 3).
    assert "enig" not in markningar.MARKNINGAR
    assert not any("enig" == n.lower() for n in markningar.MARKNINGAR.values())


# Mot protokollen

def _paragraf(api, datum: str, paragraf: int) -> dict:  # noqa: F811
    s = api.get(f"/api/sammantraden/{sammantrade_id(api, datum)}").json()
    [b] = [b for b in s["behandlingar"] if b["paragraf"] == paragraf]
    return b


def test_votering_reservation_och_oenighet_pa_sammantradet_och_behandlingen(api):  # noqa: F811
    b = _paragraf(api, "2026-02-23", 5)
    assert b["markningar"][:3] == [
        {"id": "votering", "text": "Votering 37–6"},
        {"id": "reservation", "text": "Reservation SD", "partier": ["SD"]},
        {"id": "oenighet", "text": "Oenighet"},
    ]
    detalj = api.get(f"/api/sammantraden/{sammantrade_id(api, '2026-02-23')}/behandlingar/5").json()
    assert detalj["markningar"] == b["markningar"]


def test_ingen_enig_och_ingen_oenighet_utan_underlag(api, database_url):  # noqa: F811
    with db.connect(database_url) as conn:
        rader = markningar.las(conn)
        isar = {r["id"] for r in conn.execute(
            "SELECT b.id FROM behandling b WHERE EXISTS (SELECT 1 FROM votering v WHERE v.behandling_id = b.id) "
            "OR EXISTS (SELECT 1 FROM reservation r WHERE r.behandling_id = b.id) "
            "OR (SELECT count(*) FROM yrkande y WHERE y.behandling_id = b.id) >= 2 "
            "OR b.propositionsordning IS NOT NULL")}
    assert rader
    alla = {m["id"] for r in rader for m in r["markningar"]}
    assert alla <= set(markningar.BEHANDLING)
    assert "enig" not in alla
    # Oenighet bara där protokollet har votering, reservation, flera yrkanden eller en propositionsordning.
    assert all(r["id"] in isar for r in rader if "oenighet" in ids(r["markningar"]))
    # En behandling utan något av det får aldrig märkningen.
    assert any("oenighet" not in ids(r["markningar"]) for r in rader)


def test_votering_utan_siffror_raknas_ur_listan_med_rattelser(api, database_url):  # noqa: F811
    s = sammantrade_id(api, "2026-02-23")
    with db.connect(database_url) as conn:
        conn.execute(
            "UPDATE votering SET ja = NULL, nej = NULL WHERE behandling_id = "
            "(SELECT id FROM behandling WHERE sammantrade_id = %s AND paragraf = 5)", (s,))
    assert _paragraf(api, "2026-02-23", 5)["markningar"][0]["text"] == "Votering 37–6"
    # En publicerad rättelse av en röst räknas (beslut 6).
    publicerad(api, sammantrade_id=s, objekt="rost", paragraf=5, votering=1, namn="Lennart Molin", falt="rost",
               nytt="nej", motivering="Rösten står fel i listan.")
    assert _paragraf(api, "2026-02-23", 5)["markningar"][0]["text"] == "Votering 36–7"
    with db.connect(database_url) as conn:
        conn.execute("DELETE FROM rost WHERE votering_id IN (SELECT v.id FROM votering v JOIN behandling b "
                     "ON b.id = v.behandling_id WHERE b.sammantrade_id = %s AND b.paragraf = 5)", (s,))
    assert _paragraf(api, "2026-02-23", 5)["markningar"][0]["text"] == "Votering"


def test_aterremitterad_efter_publicerad_rattelse_och_bordlagd(api, database_url):  # noqa: F811
    s = sammantrade_id(api, "2026-02-23")
    utan = [b for b in api.get(f"/api/sammantraden/{s}").json()["behandlingar"]
            if not {"aterremitterad", "bordlagd"} & set(ids(b["markningar"]))]
    p, q = utan[0]["paragraf"], utan[1]["paragraf"]
    # En rättelse som utkast räknas inte, en publicerad gör det.
    logga_in(api, "redaktor")
    api.post("/api/rattelser", json={"sammantrade_id": s, "objekt": "behandling", "paragraf": p, "falt": "beslut",
                                     "nytt": "Kommunfullmäktige beslutar att återremittera ärendet.",
                                     "motivering": "Beslutet lästes fel.", "felet_i": "inlasningen"})
    logga_in(api, None)
    assert "aterremitterad" not in ids(_paragraf(api, "2026-02-23", p)["markningar"])
    publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=p, falt="beslut",
               nytt="Kommunfullmäktige beslutar att återremittera ärendet.", motivering="Beslutet lästes fel.")
    assert {"id": "aterremitterad", "text": "Återremitterad"} in _paragraf(api, "2026-02-23", p)["markningar"]

    with db.connect(database_url) as conn:
        conn.execute("UPDATE behandling SET beslut = 'Kommunfullmäktige beslutar att bordlägga ärendet.' "
                     "WHERE sammantrade_id = %s AND paragraf = %s", (s, q))
    assert {"id": "bordlagd", "text": "Bordlagd"} in _paragraf(api, "2026-02-23", q)["markningar"]


def test_jav_och_oenighet_ur_yrkanden(api, database_url):  # noqa: F811
    s = sammantrade_id(api, "2026-02-23")
    utan = [b for b in api.get(f"/api/sammantraden/{s}").json()["behandlingar"] if not b["markningar"]]
    p = utan[0]["paragraf"]
    with db.connect(database_url) as conn:
        conn.execute("UPDATE narvaro SET jav = ARRAY[%s] WHERE id = (SELECT min(id) FROM narvaro WHERE sammantrade_id = %s)",
                     (p, s))
        behandling_id = conn.execute("SELECT id FROM behandling WHERE sammantrade_id = %s AND paragraf = %s",
                                     (s, p)).fetchone()["id"]
        conn.execute("DELETE FROM yrkande WHERE behandling_id = %s", (behandling_id,))
        conn.execute("INSERT INTO yrkande (behandling_id, ordning, text) VALUES (%s, 0, %s), (%s, 1, %s)",
                     (behandling_id, "Anna Ek (S) yrkar bifall till kommunstyrelsens förslag.",
                      behandling_id, "Bo Al (M) yrkar avslag."))
    assert ids(_paragraf(api, "2026-02-23", p)["markningar"]) == ["oenighet", "jav"]


def test_behandlingstypen_som_markning(api, database_url):  # noqa: F811
    with db.connect(database_url) as conn:
        rader = markningar.las(conn)
    motioner = [r for r in rader if r["typ"] == "motion"]
    assert motioner, "inspelningarna har motioner"
    assert all({"id": "motion", "text": "Motion"} in r["markningar"] for r in motioner)
    # Ett vanligt beslut får ingen typmärkning.
    assert not any(set(ids(r["markningar"])) & {"motion", "medborgarforslag", "interpellation"}
                   for r in rader if r["typ"] in ("beslut", "forslag", None))


def test_las_filtrerar_pa_markning(api, database_url):  # noqa: F811
    with db.connect(database_url) as conn:
        med = markningar.las(conn, fran=2026, till=2026, markning="votering")
        alla = markningar.las(conn, fran=2026, till=2026)
    assert med and len(med) < len(alla)
    assert all("votering" in ids(r["markningar"]) for r in med)
    assert {(r["sammantrade_id"], r["paragraf"]) for r in med} == {
        (r["sammantrade_id"], r["paragraf"]) for r in alla if "votering" in ids(r["markningar"])}


def test_sok_filtrerar_pa_markning_och_klarar_sig_utan_soktext(api):  # noqa: F811
    s = api.get("/api/sok", params={"markning": "votering", "ar": 2026, "sortering": "datum"}).json()
    assert s["antal"] > 0
    assert {p["typ"] for p in s["per_typ"] if p["antal"]} <= {"behandling", "arende"}
    for t in s["traffar"]:
        assert "votering" in ids(t["markningar"]), t
    paragraf5 = [t for t in s["traffar"] if t["lank"] == f"/politik/sammantraden/{sammantrade_id(api, '2026-02-23')}/paragraf/5"]
    assert paragraf5 and paragraf5[0]["markningar"][0]["text"] == "Votering 37–6"
    # Med söktext och märkning: bara träffar med märkningen.
    med_text = api.get("/api/sok", params={"q": "motion", "markning": "motion"}).json()
    assert all("motion" in ids(t["markningar"]) for t in med_text["traffar"])
    # Utan märkning behövs fortfarande en söktext, och en okänd märkning avvisas.
    assert api.get("/api/sok", params={"q": ""}).status_code == 422
    assert api.get("/api/sok", params={"markning": "enig"}).status_code == 422
    # Träffar utan märkningar har en tom lista.
    vanlig = api.get("/api/sok", params={"q": "budget"}).json()
    assert all(isinstance(t["markningar"], list) for t in vanlig["traffar"])


def test_arende_ledamot_och_kommande_har_markningar(api):  # noqa: F811
    b = api.get(f"/api/sammantraden/{sammantrade_id(api, '2026-02-23')}/behandlingar/5").json()
    a = api.get(f"/api/arenden/{b['arende']['id']}").json()
    assert "votering" in ids(a["markningar"])
    assert all("markningar" in x for x in a["behandlingar"])

    molin = next(r for v in b["voteringar"] for r in v["roster"] if r["namn"] == "Lennart Molin")
    ledamot = api.get(f"/api/ledamoter/{molin['ledamot_id']}").json()
    [rost] = [r for r in ledamot["roster"] if r["paragraf"] == 5 and r["sammantrade"]["datum"] == "2026-02-23"]
    assert rost["markningar"][0] == {"id": "votering", "text": "Votering 37–6"}

    k = api.get("/api/kommande", params={"manader": 120}).json()
    assert all(isinstance(x["markningar"], list) for x in k["arenden"])
    for m in k["markningar"]:
        assert m["antal"] == sum(1 for x in k["arenden"] if m["id"] in ids(x["markningar"]))
