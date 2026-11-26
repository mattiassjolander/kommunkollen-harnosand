"""Raden "Skolnämnden föreslås besluta" avslutar paragrafens rubrik (#164).

Fixturen `skol-2026-11-05-urval.pdf` är ett verkligt protokoll: försättsbladet, ärendelistan, § 111 och § 114 ur
skolnämndens protokoll 2026-11-05. § 111 har bara förslaget "Skolnämnden föreslås besluta att godkänna …" och
inget "Skolnämnden beslutar". Förslaget hamnade tidigare i rubriken. I § 114 följs förslaget av förvaltningens
förslag ("Skolförvaltningen föreslår skolnämnden besluta").
"""

from __future__ import annotations

from pathlib import Path

from app.protokolltolkning import tolka
from test_lasordning_och_arendelista import sida, tolkning

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def test_forslaget_hor_inte_till_rubriken():
    t = tolka((FIXTURER / "skol-2026-11-05-urval.pdf").read_bytes())
    per_nr = {b.paragraf: b for b in t.behandlingar}
    assert per_nr[111].rubrik == "Budgetuppföljning Skolnämnden september 2026"
    assert per_nr[114].rubrik == "Sökbart programutbud Härnösands gymnasium och anpassad gymnasium 2027-2028"
    # Ett förslag är inget beslut. Paragraferna saknar "Skolnämnden beslutar", och plattformen gissar inte.
    assert per_nr[111].beslut is None and per_nr[114].beslut is None
    assert [a for a in t.avvikelser if a.startswith("§")] == [
        '§ 111: paragrafen har ett förslag till beslut ("Skolnämnden föreslås besluta") men inget beslut',
        '§ 114: paragrafen har ett förslag till beslut ("Skolnämnden föreslås besluta") men inget beslut',
    ]


def test_forslaget_avslutar_rubriken_utan_arendelista():
    t = tolkning((sida(3, "§ 1", "Budgetuppföljning september", "2026", "Skolnämnden föreslås besluta",
                       "att godkänna budgetuppföljningen.", "Beslutsunderlag", "Tjänsteskrivelse"), None))
    [b] = t.behandlingar
    assert (b.rubrik, b.beslut) == ("Budgetuppföljning september 2026", None)


def test_beslut_efter_forslaget_las_som_vanligt():
    t = tolkning((sida(3, "§ 1", "Budgetuppföljning september 2026", "Skolnämnden föreslås besluta",
                       "att godkänna budgetuppföljningen.", "Skolnämnden beslutar",
                       "att godkänna budgetuppföljningen.", "Beslutsunderlag", "Tjänsteskrivelse"), None))
    [b] = t.behandlingar
    assert b.rubrik == "Budgetuppföljning september 2026"
    assert b.beslut == "Skolnämnden beslutar\natt godkänna budgetuppföljningen."
    assert t.avvikelser == []
