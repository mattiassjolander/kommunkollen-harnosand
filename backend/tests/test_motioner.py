"""Motioner och medborgarförslag (#45): väckt, besvarad, utfall, ledtid och motionärer."""

from __future__ import annotations

from datetime import date

import pytest
from test_statistik import api  # noqa: F401

from app.motioner import berakna, tillkommande_motioner, utfall
from app.protokolltolkning import motionarer


@pytest.mark.parametrize(
    ("text", "vantat"),
    [
        ("Johan Wester (C) har lämnat in en motion om att", [("Johan Wester", "C")]),
        ("Glenn Sehlin (SD) har till kommunfullmäktige inkommit med en motion", [("Glenn Sehlin", "SD")]),
        ("Lillemor Andersson (C) och Per-Erik Norberg (C) har i en motion föreslagit",
         [("Lillemor Andersson", "C"), ("Per-Erik Norberg", "C")]),
        # "X och Y (SD)": båda har partiet SD.
        ("Charlotte Höglund-Bystedt och Ulrika Jonsson (SD) har väckt en motion om",
         [("Charlotte Höglund-Bystedt", "SD"), ("Ulrika Jonsson", "SD")]),
        ("Johan Wester, Centerpartiet, har lämnat in en motion", [("Johan Wester", "C")]),
        ("Olle Löfgren (Liberalerna) har lämnat in en motion", [("Olle Löfgren", "L")]),
        ("Centerpartiet har lämnat in en motion till fullmäktige.", [(None, "C")]),
        ("Kommunfullmäktige har remitterat en motion till samhällsnämnden.", []),
    ],
)
def test_motionarer(text, vantat):
    assert motionarer(f"Förvaltningen har yttrat sig. {text}") == vantat


@pytest.mark.parametrize(
    ("beslut", "vantat"),
    [
        ("Kommunfullmäktige beslutar\natt överlämna motionen till kommunstyrelsen för beredning.", "vackt"),
        ("Kommunfullmäktige beslutar\natt avslå motionen.", "avslag"),
        ("Kommunfullmäktige beslutar\natt bifalla motionen.", "bifall"),
        ("Kommunfullmäktige beslutar\natt anse motionen vara besvarad.", "besvarad"),
        ("Kommunfullmäktige beslutar\natt bifalla motionens första att-sats, samt\natt avslå", "delvis"),
        ("Kommunfullmäktige beslutar\natt återremittera ärendet.", "aterremiss"),
        ("Kommunfullmäktige beslutar\natt bordlägga ärendet.", "bordlaggning"),
        ("Samhällsnämnden beslutar\natt e-förslaget inte genomförs", "avslag"),
        ("Samhällsnämnden beslutar\natt e-förslaget genomförs delvis.", "delvis"),
        ("Skolnämnden beslutar\natt e-förslaget tas med i framtida planering", "annat"),
        ("", None),
    ],
)
def test_utfall(beslut, vantat):
    assert utfall(beslut) == vantat


def test_motioner_i_samlingspunkten():
    assert tillkommande_motioner(
        "Kommunfullmäktige beslutar att överlämna följande motioner till kommunstyrelsen för beredning: "
        "• Motion – Jämställdhetsstrategi (KS2022-206), samt • Motion – Språkkrav inom socialförvaltningen (KS2022-210)."
    ) == [("Jämställdhetsstrategi", "2022-000206"), ("Språkkrav inom socialförvaltningen", "2022-000210")]
    assert tillkommande_motioner(
        "Kommunfullmäktige beslutar att interpellationen får ställas, samt att Motion - Sänk trösklar för att "
        "starta och driva företag i Härnösand, (KS 2022–548), till kommunstyrelsen för beredning."
    ) == [("Sänk trösklar för att starta och driva företag i Härnösand", "2022-000548")]


def _b(arende, organ, datum, par, rubrik, beslut, dnr=(), motionarer_=(), typ="motion"):
    return {"arende_id": arende, "organ": organ, "datum": date.fromisoformat(datum), "sammantrade_id": hash((organ, datum)),
            "paragraf": par, "rubrik": rubrik, "beslut": beslut, "diarienummer": list(dnr), "typ": typ,
            "motionarer": [{"namn": n, "parti": p} for n, p in motionarer_]}


def test_vackt_och_besvarad_motion_kopplas_ihop_over_sammantraden():
    rader = [
        _b(1, "KF", "2024-05-27", 70, "Motion - Utred breddning av LOV",
           "Kommunfullmäktige beslutar\natt överlämna motionen till kommunstyrelsen för beredning.", ["2024-000186"]),
        # Remissvaret har nämndens diarienummer och är ett eget ärende: kopplas på rubriken, osäkert.
        _b(2, "SOC", "2024-10-24", 90, "Svar på remiss angående motion - Utred breddning av LOV",
           "Socialnämnden beslutar\natt anta yttrandet", ["2024-000099"]),
        _b(1, "KS", "2025-03-04", 30, "Motion - Utred breddning av LOV",
           "Kommunstyrelsen föreslår kommunfullmäktige besluta\natt avslå motionen.", ["2024-000186"],
           [("Johan Wester", "C")]),
        _b(1, "KF", "2025-04-28", 59, "Motion - Utred breddning av LOV",
           "Kommunfullmäktige beslutar\natt återremittera ärendet.", ["2024-000186"], [("Johan Wester", "C")]),
        _b(1, "KF", "2025-06-16", 92, "Motion - Utred breddning av LOV, återremiss",
           "Kommunfullmäktige beslutar\natt avslå motionen.", ["2024-000186"]),
        # En motion som väcks i samlingspunkten och aldrig besvaras.
        _b(None, "KF", "2023-10-23", 140, "Tillkommande motioner, interpellationer och frågor",
           "Kommunfullmäktige beslutar att överlämna följande motioner till kommunstyrelsen för beredning: "
           "• Motion – Skälig habiliteringsersättning (KS2023-487).", typ="formalia"),
        _b(3, "KS", "2024-11-26", 160, "Motion - Skälig habiliteringsersättning",
           "Kommunstyrelsen beslutar\natt ge kommundirektören i uppdrag", ["2023-000487"]),
        _b(3, "KF", "2025-02-24", 6, "Motion - Skälig habiliteringsersättning",
           "Kommunfullmäktige beslutar\natt bordlägga ärendet.", ["2023-000487"]),
        _b(5, "SAM", "2025-01-30", 12, "E-förslag - Tänd lyset", "Samhällsnämnden beslutar\natt återremittera ärendet",
           typ="medborgarforslag"),
        _b(5, "SAM", "2025-05-30", 40, "E-förslag - Tänd lyset", "Samhällsnämnden beslutar\natt e-förslaget genomförs delvis",
           typ="medborgarforslag"),
    ]
    rader.sort(key=lambda r: r["datum"])
    s = berakna(rader, 2024, 2025, None, date(2025, 11, 15))
    lov = next(m for m in s["motioner"]["lista"] if m["rubrik"] == "Motion - Utred breddning av LOV")
    assert (lov["vackt"]["datum"], lov["vackt"]["grund"]) == (date(2024, 5, 27), "beslut")
    assert (lov["besvarad"]["sammantrade"]["datum"], lov["utfall"]) == (date(2025, 6, 16), "avslag")
    assert (lov["ledtid_dagar"], lov["over_ett_ar"], lov["aterremisser"]) == (385, True, 1)
    assert lov["motionarer"] == [{"namn": "Johan Wester", "parti": "C"}]
    assert [(b["sammantrade"]["organ"]["id"], b["osaker"]) for b in lov["behandlingar"]] == [
        ("KF", False), ("SOC", True), ("KS", False), ("KF", False), ("KF", False)]

    hab = next(m for m in s["motioner"]["lista"] if "habilitering" in m["rubrik"])
    assert (hab["vackt"]["datum"], hab["vackt"]["grund"], hab["vackt"]["osaker"]) == (date(2023, 10, 23), "samlingspunkt", False)
    assert (hab["besvarad"], hab["utfall"], hab["over_ett_ar"], hab["bordlaggningar"]) == (None, None, True, 1)

    # Väckta räknas på året de väcktes, besvarade på året de besvarades.
    assert [(r["ar"], r["vackta"], r["besvarade"], r["utfall"]["avslag"]) for r in s["motioner"]["per_ar"]] == [
        (2024, 1, 0, 0), (2025, 0, 1, 1)]
    assert [(p["parti"], p["vackta"], p["besvarade"]) for p in s["motioner"]["per_parti"]] == [("C", 1, 1)]

    [lyset] = s["medborgarforslag"]["lista"]
    assert (lyset["vackt"], lyset["besvarad"]["sammantrade"]["organ"]["id"], lyset["utfall"]) == (None, "SAM", "delvis")
    assert lyset["aterremisser"] == 1


def test_motioner_ur_protokollen(api):  # noqa: F811
    s = api.get("/api/statistik/motioner").json()
    [ar] = s["motioner"]["per_ar"]
    assert (ar["ar"], ar["vackta"], ar["besvarade"], ar["utfall"]["delvis"]) == (2026, 11, 1, 1)
    friskvard = next(m for m in s["motioner"]["lista"] if "friskvårdsbidraget" in m["rubrik"])
    assert friskvard["vackt"]["datum"] == "2026-03-23"
    assert friskvard["motionarer"] == [{"namn": "Olle Löfgren", "parti": "L"}]
    assert (friskvard["besvarad"], friskvard["over_ett_ar"]) == (None, False)
    assert friskvard["behandlingar"][0]["sammantrade"]["id"] == friskvard["vackt"]["sammantrade_id"]
    assert next(p for p in s["motioner"]["per_parti"] if p["parti"] == "L")["vackta"] == 3
    assert api.get("/api/statistik/motioner", params={"fran": 2024, "till": 2025}).json()["motioner"]["lista"] == []
