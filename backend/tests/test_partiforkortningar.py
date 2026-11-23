"""Norrlandspartiet skriver sig "NorrP" i protokollen. Plattformen förkortar det NP."""

from app.protokolltolkning import (
    Behandling, Narvaro, Reservation, Rost, Tolkning, Votering, Yrkande, _forkortningar, _namn_parti,
    _reservationer, motionarer,
)


def test_namn_med_norrp_tolkas():
    assert _namn_parti("Isedora Timander Skogström (NorrP)") == ("Isedora Timander Skogström", "NorrP")
    assert _namn_parti("Monica Fahlén (S)") == ("Monica Fahlén", "S")


def test_reservation_med_partinamnet_ger_np():
    r = _reservationer("Norrlandspartiet reserverar sig mot beslutet.")
    assert r[0].partier == ["NP"]


def test_reservation_med_namn_och_norrp():
    r = _reservationer("Isedora Timander Skogström (NorrP) reserverar sig mot beslutet.")
    assert r[0].personer == [("Isedora Timander Skogström", "NorrP")]


def test_motionar_med_norrp_och_partinamn():
    assert motionarer("Isedora Timander Skogström (NorrP) har lämnat in en motion om vägar.") == [
        ("Isedora Timander Skogström", "NP")]
    assert motionarer("Norrlandspartiet har lämnat in en motion om vägar.") == [(None, "NP")]


def test_tolkningen_sparar_np():
    t = Tolkning(
        narvaro=[Narvaro("A B", "NorrP", None, "beslutande", tjanstgor_for="C D", tjanstgor_for_parti="NorrP"),
                 Narvaro("E F", "S", None, "beslutande")],
        behandlingar=[Behandling(
            paragraf=1, rubrik="R", diarienummer=[], beslut=None,
            yrkanden=[Yrkande("y", [("A B", "NorrP")])],
            reservationer=[Reservation("r", [("A B", "NorrP")], ["NorrP"])],
            voteringar=[Votering(None, None, None, None, None, None,
                                 roster=[Rost("A B", "NorrP", "ja", ersatt="C D", ersatt_parti="NorrP")])],
            motionarer=[("A B", "NorrP")],
        )],
    )
    _forkortningar(t)
    assert [(n.parti, n.tjanstgor_for_parti) for n in t.narvaro] == [("NP", "NP"), ("S", None)]
    b = t.behandlingar[0]
    assert b.yrkanden[0].personer == [("A B", "NP")]
    assert (b.reservationer[0].personer, b.reservationer[0].partier) == ([("A B", "NP")], ["NP"])
    assert (b.voteringar[0].roster[0].parti, b.voteringar[0].roster[0].ersatt_parti) == ("NP", "NP")
    assert b.motionarer == [("A B", "NP")]
