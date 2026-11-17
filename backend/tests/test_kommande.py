"""Kommande: ärenden som inte är avslutade."""

from __future__ import annotations

import pytest
from test_arenden import api, sammantrade_id  # noqa: F401

from app.kommande import frist, mottagare, status_for

URL = "/api/kommande"


@pytest.mark.parametrize(
    ("beslut", "vantat"),
    [
        ("Kommunstyrelsen ger kommundirektören i uppdrag att utreda frågan och återrapportera senast 2027-03-31.",
         "2027-03-31"),
        ("Samhällsnämnden ger förvaltningen i uppdrag att redovisa resultatet i mars 2027.", "mars 2027"),
        ("Skolnämnden ger förvaltningen i uppdrag att utreda frågan.", None),
        (None, None),
    ],
)
def test_frist(beslut, vantat):
    assert frist(beslut) == vantat


@pytest.mark.parametrize(
    ("beslut", "organ", "typ", "vantat"),
    [
        ("Kommunstyrelsen föreslår kommunfullmäktige besluta att anta planen.", "KS", "forslag", "forslag"),
        ("Kommunfullmäktige beslutar att återremittera ärendet.", "KF", "beslut", "aterremiss"),
        ("Kommunfullmäktige beslutar att bordlägga ärendet.", "KF", "beslut", "bordlaggning"),
        ("Kommunstyrelsen beslutar att ge kommundirektören i uppdrag att utreda frågan.", "KS", "beslut", "uppdrag"),
        ("Kommunfullmäktige beslutar att anta taxan.", "KF", "beslut", None),
    ],
)
def test_status(beslut, organ, typ, vantat):
    assert status_for({"beslut": beslut, "organ": organ, "typ": typ}) == vantat


def test_mottagare():
    assert mottagare("Samhällsnämnden föreslår kommunstyrelsen att besluta") == "KS"
    assert mottagare("Kommunstyrelsen föreslår kommunfullmäktige besluta") == "KF"
    assert mottagare("Kommunstyrelsen beslutar") is None


def test_kommande_arenden(api):  # noqa: F811
    s = api.get(URL, params={"manader": 120}).json()
    assert s["arenden"], "inspelningarna har pågående ärenden"
    assert sum(x["antal"] for x in s["statusar"]) == len(s["arenden"])
    statusar = {x["id"] for x in s["statusar"]}
    for a in s["arenden"]:
        assert a["status"] in statusar
        assert "justerare" not in a["rubrik"].lower()
    # Senaste behandlingen först.
    datum = [a["senaste"]["sammantrade"]["datum"] for a in s["arenden"]]
    assert datum == sorted(datum, reverse=True)

    # Underlaget: protokollet bakom varje behandling, med länk till originalet och kopian.
    u = api.get(f"{URL}/{s['arenden'][0]['arende_id']}").json()
    assert u["behandlingar"]
    for b in u["behandlingar"]:
        assert b["protokoll"]["url"].startswith("http")
        assert b["protokoll"]["kopia"].startswith("/api/dokument/")
        assert isinstance(b["hanvisningar"], list)
    assert api.get(f"{URL}/999999").status_code == 404
    assert api.get(URL, params={"manader": 0}).status_code == 422
