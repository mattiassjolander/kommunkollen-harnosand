"""Återkommande ärenden (#46): ärenden som behandlats vid flera sammanträden."""

from __future__ import annotations

import pytest
from test_arenden import api, sammantrade_id  # noqa: F401

from app import db
from app.aterkommande import handelse

URL = "/api/statistik/aterkommande"


@pytest.mark.parametrize(
    ("beslut", "vantat"),
    [
        ("Kommunfullmäktige beslutar\natt återremittera ärendet till kommunstyrelsen.", "aterremiss"),
        ("Kommunfullmäktige beslutar\natt bordlägga ärendet.", "bordlaggning"),
        ("Kommunfullmäktige beslutar\natt ärendet bordläggs till nästa sammanträde.", "bordlaggning"),
        ("Kommunfullmäktige beslutar\natt anta taxan.", None),
        (None, None),
    ],
)
def test_handelse(beslut, vantat):
    assert handelse(beslut) == vantat


def test_aterkommande_arenden_med_aterremisser(api, database_url):  # noqa: F811
    s = api.get(URL).json()
    # KS 2026-02-24 §31 bereder KF 2026-03-23 §38 "Borgenstak från 2026": samma ärende vid två sammanträden.
    borgen = next(a for a in s["arenden"] if a["rubrik"] == "Borgenstak från 2026")
    assert borgen["antal_behandlingar"] == 2
    assert [(b["sammantrade"]["organ"]["id"], b["paragraf"]) for b in borgen["behandlingar"]] == [("KS", 31), ("KF", 38)]
    assert (borgen["aterremisser"], borgen["bordlaggningar"]) == (0, 0)
    assert s["summa"]["arenden"] == len(s["arenden"]) > 0
    # Sorterade efter antal behandlingar, flest först.
    antal = [a["antal_behandlingar"] for a in s["arenden"]]
    assert antal == sorted(antal, reverse=True)
    # Samlingspunkter tas inte med.
    assert not any("justerare" in a["rubrik"].lower() or "kännedom" in a["rubrik"].lower() for a in s["arenden"])

    # En återremiss räknas.
    with db.connect(database_url) as conn:
        conn.execute(
            "UPDATE behandling SET beslut = 'Kommunstyrelsen beslutar\natt återremittera ärendet.' "
            "WHERE sammantrade_id = %s AND paragraf = 31",
            (sammantrade_id(api, "KS", "2026-02-24"),),
        )
    s = api.get(URL).json()
    borgen = next(a for a in s["arenden"] if a["rubrik"] == "Borgenstak från 2026")
    assert borgen["aterremisser"] == 1 and borgen["behandlingar"][0]["handelse"] == "aterremiss"
    assert s["summa"]["aterremisser"] >= 1

    # Med bara ett organ i urvalet är ärendet inte längre återkommande.
    assert not any(a["id"] == borgen["id"] for a in api.get(URL, params={"organ": "KF"}).json()["arenden"])
    assert api.get(URL, params={"fran": 2026, "till": 2025}).status_code == 422
