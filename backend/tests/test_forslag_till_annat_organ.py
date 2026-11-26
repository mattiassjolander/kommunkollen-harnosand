"""Förslag till ett annat organ är bara när ett organ föreslår ett organ (#182).

Samhällsnämnden 2022-06-16 § 113, "E-förslag - Ökad säkerhet vid lämning och hämtning vid Brännaskolan",
visades som obesvarat medborgarförslag eftersom beslutet innehöll "som samhällsförvaltningen föreslår".
"""

from __future__ import annotations

from datetime import date

import pytest

from app import kommande, motioner
from app.arenden import forslag_till, slutligt_beslut
from app.kommande import mottagare, status_for

BRANNASKOLAN = ("Samhällsnämnden beslutar\natt e-förslaget genomförs på det sätt som samhällsförvaltningen föreslår "
                "och att skicka ärendet till kommunfullmäktiges presidium för kännedom och till "
                "kommunstyrelseförvaltningen för avslut.")
IDAG = date(2026, 11, 26)


def _b(arende, organ, datum, par, rubrik, beslut, typ="medborgarforslag"):
    return {"arende_id": arende, "organ": organ, "datum": date.fromisoformat(datum),
            "sammantrade_id": hash((organ, datum)), "paragraf": par, "rubrik": rubrik, "beslut": beslut,
            "diarienummer": [], "typ": typ, "motionarer": [], "markningar": []}


@pytest.mark.parametrize(
    ("beslut", "vantat"),
    [
        ("Kommunstyrelsen föreslår kommunfullmäktige besluta att anta planen.", "kommunfullmäktige"),
        ("Samhällsnämnden föreslår kommunstyrelsen föreslå kommunfullmäktige besluta att avslå e-förslaget.",
         "kommunstyrelsen"),
        ("Skolnämnden föreslår kommunstyrelsen att föreslå kommunfullmäktige besluta att avslå motionen.",
         "kommunstyrelsen"),
        ("Kommunstyrelsen föreslå kommunfullmäktige besluta att godkänna delårsrapporten.", "kommunfullmäktige"),
        ("Kommunstyrelsen föreslår att fullmäktige beslutar att anta taxan.", "kommunfullmäktige"),
        ("Skolförvaltningen föreslår skolnämnden besluta att godkänna", "skolnämnden"),
        ("Kommunstyrelsen beslutar att lämna förslag till kommunfullmäktige.", "kommunfullmäktige"),
        (BRANNASKOLAN, None),
        ("Samhällsnämnden beslutar att göra som förvaltningen föreslår.", None),
        ("Skolnämnden föreslås besluta att godkänna rapporten.", None),
        ("Kommunfullmäktige beslutar att anta taxan.", None),
        (None, None),
    ],
)
def test_forslag_till(beslut, vantat):
    assert forslag_till(beslut) == vantat
    assert slutligt_beslut(beslut) == (beslut is not None and vantat is None)


def test_som_forvaltningen_foreslar_ar_bifall_och_besvarar_medborgarforslaget():
    rubrik = "E-förslag - Ökad säkerhet vid lämning och hämtning vid Brännaskolan"
    rader = [_b(2270, "SAM", "2022-06-16", 113, rubrik, BRANNASKOLAN)]
    assert motioner.utfall(BRANNASKOLAN) == "bifall"

    [f] = motioner.berakna(rader, 2022, 2026, None, IDAG)["medborgarforslag"]["lista"]
    assert (f["utfall"], f["besvarad"]["paragraf"], f["over_ett_ar"]) == ("bifall", 113, False)
    assert kommande.berakna(rader, 120, IDAG)["arenden"] == []


def test_forslag_till_ett_annat_organ_besvarar_inte_medborgarforslaget():
    rader = [_b(7, "SAM", "2026-03-10", 20, "E-förslag - Fler bänkar",
                "Samhällsnämnden föreslår kommunstyrelsen föreslå kommunfullmäktige besluta att bifalla e-förslaget.")]
    [f] = motioner.berakna(rader, 2026, 2026, None, IDAG)["medborgarforslag"]["lista"]
    assert (f["besvarad"], f["utfall"]) == (None, None)
    [p] = kommande.berakna(rader, 120, IDAG)["arenden"]
    assert p["status"] == "medborgarforslag"


@pytest.mark.parametrize(
    "beslut",
    [
        "Kommunstyrelsen beslutar att skicka ärendet till kommunfullmäktiges presidium för kännedom.",
        "Samhällsnämnden beslutar att skicka ärendet till kommunstyrelseförvaltningen för avslut.",
        BRANNASKOLAN,
    ],
)
def test_for_kannedom_och_for_avslut_ar_inget_nytt_steg(beslut):
    assert mottagare(beslut) is None
    assert status_for({"beslut": beslut, "organ": "SAM", "typ": "beslut"}) is None
    rader = [_b(9, "SAM", "2026-10-01", 50, "Ändrad skyltning", beslut, typ="beslut")]
    assert kommande.berakna(rader, 12, IDAG)["arenden"] == []
