"""Protokollsammanställning (#195): paragrafer, ärenden, beslut och förslag vidare, oenighet, beslutsgång och närvaro.

Reglerna prövas en och en på påhittade behandlingar, och sedan mot kommunfullmäktiges protokoll för 2026
(inspelade), med en publicerad rättelse.
"""

from __future__ import annotations

import pytest
from test_rattelser import api, publicerad, sammantrade_id  # noqa: F401

from app import db, protokollsammanstallning
from app.protokollsammanstallning import ar_arende, langd, sammanstall


def beh(paragraf: int, rubrik: str, beslut: str | None, typ: str | None, markningar=(), voteringar=0,
        reservationer=0) -> dict:
    return {"paragraf": paragraf, "rubrik": rubrik, "beslut": beslut, "typ": typ, "markningar": list(markningar),
            "antal_voteringar": voteringar, "antal_reservationer": reservationer}


# Skolnämnden 2026-11-05: 12 paragrafer, 5 informationsärenden, 3 formalia, 2 beslut och 2 utan beslut.
SKOL = [
    beh(108, "Val av justerare", "Skolnämnden utser Anna Andersson att justera protokollet.", "formalia"),
    beh(109, "Godkännande av dagordning", "Skolnämnden godkänner dagordningen.", "formalia"),
    beh(110, "Information om skolskjutsar", "Skolnämnden beslutar att lägga informationen till handlingarna.",
        "information"),
    beh(111, "Lokalförsörjningsplan för skolan", None, None),
    beh(112, "Delegationsbeslut", "Skolnämnden beslutar att lägga delegationsbesluten till handlingarna.",
        "information"),
    beh(113, "Meddelanden", "Skolnämnden beslutar att lägga meddelandena till handlingarna.", "information"),
    beh(114, "Ekonomisk prognos", "", None),
    beh(115, "Information från förvaltningschefen", None, "information"),
    beh(116, "Ny läsårstider", "Skolnämnden beslutar att fastställa läsårstiderna.", "beslut"),
    beh(117, "Taxa för fritidshem", "Skolnämnden föreslår kommunfullmäktige besluta att anta taxan.", "forslag"),
    beh(118, "Rapporter", "Skolnämnden beslutar att lägga rapporterna till handlingarna.", "information"),
    beh(119, "Övrigt", None, "formalia"),
]


def test_arenden_utan_formalia_information_och_samlingspunkter():
    s = sammanstall(SKOL)
    assert (s["paragrafer"], s["arenden"]) == (12, 4)
    assert s["filter"]["arenden"] == [111, 114, 116, 117]
    assert s["sammantradet"]["informationsarenden"] == 5
    # En samlingspunkt är inget ärende, också när den saknar typ (#195, beslut 1).
    assert not ar_arende({"rubrik": "Anmälan av delegationsbeslut", "typ": None})
    assert not ar_arende({"rubrik": "Ärenden för kännedom", "typ": "beslut"})
    assert ar_arende({"rubrik": "Svar på interpellation om vägarna", "typ": "interpellation"})


def test_beslut_och_forslag_vidare_enligt_forslag_till():
    s = sammanstall(SKOL)
    assert (s["beslut"], s["forslag_vidare"]) == (1, 1)
    assert s["filter"]["beslut"] == [116]
    assert s["skickas_vidare"] == [{"paragraf": 117, "rubrik": "Taxa för fritidshem", "till": "Kommunfullmäktige"}]
    # "Som förvaltningen föreslår" är ett eget beslut, inget förslag vidare (#182).
    s = sammanstall([beh(1, "Bidrag", "Nämnden beslutar som förvaltningen föreslår.", "beslut"),
                     beh(2, "Detaljplan", "Samhällsnämnden föreslår att kommunstyrelsen antar planen.", "forslag"),
                     beh(3, "Utan beslut", None, None)])
    assert (s["arenden"], s["beslut"], s["forslag_vidare"]) == (3, 1, 1)
    assert s["skickas_vidare"][0]["till"] == "Kommunstyrelsen"


def test_oenighet_voteringar_och_reservationer_med_partier():
    res = lambda *p: {"id": "reservation", "text": "Reservation " + ", ".join(p), "partier": list(p)}  # noqa: E731
    oen, vot = {"id": "oenighet", "text": "Oenighet"}, {"id": "votering", "text": "Votering 26–24"}
    s = sammanstall([
        beh(1, "Budget", "Kommunfullmäktige beslutar att anta budgeten.", "beslut", [vot, res("SD", "M"), oen],
            voteringar=2, reservationer=2),
        beh(2, "Taxa", "Kommunfullmäktige beslutar att anta taxan.", "beslut", [res("C"), oen], reservationer=1),
        beh(3, "Plan", "Kommunfullmäktige beslutar att anta planen.", "beslut", [oen]),
        beh(4, "Policy", "Kommunfullmäktige beslutar att anta policyn.", "beslut"),
    ])
    assert s["oenighet"] == {"paragrafer": 3, "voteringar": 2, "reservationer": 3, "partier": ["C", "M", "SD"],
                             "enigt": False}
    assert (s["filter"]["votering"], s["filter"]["reservation"], s["filter"]["oenighet"]) == ([1], [1, 2], [1, 2, 3])
    # Utan oenighet är det enigt i alla ärenden. Det är ingen märkning (#162).
    enigt = sammanstall(SKOL)["oenighet"]
    assert enigt == {"paragrafer": 0, "voteringar": 0, "reservationer": 0, "partier": [], "enigt": True}


def test_beslutsgang_aterremiss_bordlaggning_jav_och_nya_motioner():
    m = lambda i: {"id": i, "text": i}  # noqa: E731
    s = sammanstall([
        beh(1, "Detaljplan", "Kommunfullmäktige beslutar att återremittera ärendet.", "beslut", [m("aterremitterad")]),
        beh(2, "Lokaler", "Kommunfullmäktige beslutar att bordlägga ärendet.", "beslut", [m("bordlagd"), m("jav")]),
        beh(3, "Motion om fler bänkar", "Motionen överlämnas till kommunstyrelsen för beredning.", "motion"),
        beh(4, "Svar på motion om cykelvägar", "Kommunfullmäktige beslutar att avslå motionen.", "motion"),
        beh(5, "Tillkommande motioner, interpellationer och frågor",
            "Följande motioner har inkommit: • Motion – Inför skolhund (KS2026-12) • Motion – Snabbladdare för "
            "elfordon (KS2026-13) Motionerna överlämnas till kommunstyrelsen för beredning.", "formalia"),
        beh(6, "E-förslag om hundrastgård", "E-förslaget överlämnas till samhällsnämnden för beredning.",
            "medborgarforslag"),
        beh(7, "Interpellation om vägunderhållet", "Interpellationen får ställas.", "interpellation"),
        beh(8, "Svar på interpellation om skolan", None, "interpellation"),
    ])
    assert s["beslutsgang"] == {"aterremitterade": 1, "bordlagda": 1, "jav": 1, "motioner": 3, "medborgarforslag": 1,
                                "interpellationer": 1}
    assert s["filter"]["motioner"] == [3, 5]


@pytest.mark.parametrize(
    ("start", "slut", "vantat"),
    [("08:15", "11:48", 213), ("13:15", "13:55", 40), ("08:15", None, None), (None, "11:48", None),
     (None, None, None), ("11:00", "10:00", None)],
)
def test_langd_bara_med_bade_start_och_sluttid(start, slut, vantat):
    assert langd(start, slut) == vantat
    assert sammanstall([], starttid=start, sluttid=slut)["sammantradet"]["langd_minuter"] == vantat


def test_narvaro_och_kallelsens_punkter_som_inte_behandlades():
    s = sammanstall([], narvaro=[
        {"kategori": "beslutande", "roll": "Ordförande", "tjanstgor_for": None, "tom_plats": False},
        {"kategori": "beslutande", "roll": "Ledamot", "tjanstgor_for": None, "tom_plats": False},
        {"kategori": "beslutande", "roll": "Ersättare", "tjanstgor_for": "Anna Andersson", "tom_plats": False},
        {"kategori": "beslutande", "roll": "Ledamot", "tjanstgor_for": None, "tom_plats": True},
        {"kategori": "ej_tjanstgorande", "roll": "Ersättare", "tjanstgor_for": None, "tom_plats": False},
    ], kallelse_avvikelser=[
        {"text": 'Kallelse, sidan 3: punkten "Bidrag till föreningen X" (KS2026-1) behandlas inte i protokollet. Den '
                 "kan ha strukits från dagordningen eller flyttats till ett annat sammanträde.",
         "lank": {"titel": "Kallelse", "url": "https://x/k.pdf#page=3", "sida": 3}},
        {"text": "Kallelsen kunde bara delvis läsas.", "lank": None},
    ])
    assert (s["sammantradet"]["beslutande"], s["sammantradet"]["tjanstgorande_ersattare"]) == (3, 1)
    [punkt] = s["kallelsen"]["ej_behandlade"]
    assert punkt["rubrik"] == "Bidrag till föreningen X" and punkt["lank"]["sida"] == 3


# Mot protokollen

def _sammanstallning(api, datum: str) -> dict:  # noqa: F811
    return api.get(f"/api/sammantraden/{sammantrade_id(api, datum)}").json()["sammanstallning"]


def test_sammantradet_och_listan_har_samma_tal(api):  # noqa: F811
    s = _sammanstallning(api, "2026-02-23")
    assert s["paragrafer"] >= s["arenden"] >= s["beslut"] + s["forslag_vidare"] > 0
    # KF 2026-02-23 § 5: votering 37–6 och reservation från SD (test_markningar).
    assert 5 in s["filter"]["votering"] and 5 in s["filter"]["reservation"]
    assert "SD" in s["oenighet"]["partier"] and not s["oenighet"]["enigt"]
    rad = next(r for r in api.get("/api/sammantraden?organ=KF").json() if r["datum"] == "2026-02-23")
    k = rad["sammanstallning"]
    assert (k["paragrafer"], k["arenden"], k["beslut"], k["forslag_vidare"]) == (
        s["paragrafer"], s["arenden"], s["beslut"], s["forslag_vidare"])
    assert {"id": "votering", "antal": s["oenighet"]["voteringar"]} in k["chips"]
    assert k["markningar"]["votering"] == len(s["filter"]["votering"])


def test_listan_raknas_utan_en_fraga_per_sammantrade(api, monkeypatch):  # noqa: F811
    anrop = []
    las = protokollsammanstallning.markningar.las
    monkeypatch.setattr(protokollsammanstallning.markningar, "las", lambda conn, **kw: anrop.append(kw) or las(conn, **kw))
    lista = api.get("/api/sammantraden?organ=KF").json()
    assert len([s for s in lista if s["sammanstallning"]]) > 5
    assert len(anrop) == 1


def test_publicerad_rattelse_andrar_talen(api):  # noqa: F811
    s = sammantrade_id(api, "2026-02-23")
    fore = _sammanstallning(api, "2026-02-23")
    p = fore["filter"]["beslut"][0]
    publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=p, falt="beslut",
               nytt="Kommunfullmäktige beslutar att återremittera ärendet.", motivering="Beslutet lästes fel.")
    efter = _sammanstallning(api, "2026-02-23")
    assert efter["beslutsgang"]["aterremitterade"] == fore["beslutsgang"]["aterremitterade"] + 1
    assert p in efter["filter"]["aterremitterad"]
    # Ett beslut som rättas till ett förslag vidare flyttas från beslut till förslag vidare.
    q = efter["filter"]["beslut"][1]
    publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=q, falt="beslut",
               nytt="Kommunfullmäktige föreslår kommunstyrelsen att besluta att anta planen.",
               motivering="Beslutet lästes fel.")
    sist = _sammanstallning(api, "2026-02-23")
    assert (sist["beslut"], sist["forslag_vidare"]) == (efter["beslut"] - 1, efter["forslag_vidare"] + 1)
    rad = next(r for r in api.get("/api/sammantraden?organ=KF").json() if r["id"] == s)
    assert rad["sammanstallning"]["beslut"] == sist["beslut"]


def test_otolkat_protokoll_har_ingen_sammanstallning(api, database_url):  # noqa: F811
    s = sammantrade_id(api, "2026-02-23")
    with db.connect(database_url) as conn:
        conn.execute("UPDATE sammantrade SET tolkning = 'ej_tolkad' WHERE id = %s", (s,))
    assert api.get(f"/api/sammantraden/{s}").json()["sammanstallning"] is None
    rad = next(r for r in api.get("/api/sammantraden?organ=KF").json() if r["id"] == s)
    assert rad["sammanstallning"] is None
    # Ett planerat sammanträde utan protokoll får ingen sammanställning.
    assert protokollsammanstallning.for_sammantraden(None, [{"id": 1, "dokument_id": None, "tolkning": None}]) == {
        1: None}
