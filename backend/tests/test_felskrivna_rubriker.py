"""Felskrivna paragrafrubriker i protokollen, t.ex. "Ko§ 168" (#87).

Fixturen är ett urval av kommunstyrelsens protokoll 2026-11-03: försättsbladet, ärendelistan och sidorna 35–36
med § 167 och § 168. På sidan 36 står rubriken "Ko§ 168", ett skrivfel i protokollet.
"""

from pathlib import Path

from app import avvikelser
from app.protokolltolkning import Tolkning, _behandlingar, tolka

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def test_felskriven_rubrik_blir_en_egen_paragraf():
    t = tolka((FIXTURER / "ks-2026-11-03-urval.pdf").read_bytes())
    per_nr = {b.paragraf: b for b in t.behandlingar}
    assert per_nr[168].rubrik == "Ärenden för kännedom till kommunstyrelsen 2026"
    assert per_nr[168].beslut.startswith("Kommunstyrelsen beslutar")
    # § 167 slutar där § 168 börjar.
    assert "kännedom" not in per_nr[167].beslut
    assert 'Paragrafrubriken är felskriven i protokollet: "Ko§ 168" (s. 36)' in t.avvikelser
    assert not any("saknas:" in a and "168" in a.split("saknas:")[1].split(";")[0] for a in t.avvikelser)


def test_felskriven_rubrik_raknas_som_fel_i_protokollet():
    k = avvikelser.kategori('Paragrafrubriken är felskriven i protokollet: "Ko§ 168" (s. 36)')
    assert k == "felskrivet" and k in avvikelser.I_PROTOKOLLET


def sida(nr: int, *rader: str) -> str:
    return "\n".join(["Kommunstyrelsen", "SAMMANTRÄDESPROTOKOLL", f"{nr}(4)", *rader])


FORSTA = "Plats och tid Rådhuset\nBeslutande\nParagrafer 1-3"
ARENDELISTA = sida(2, "Ärendelista", "Nummer Rubrik Sida", "§ 1 Ett 3", "§ 2 Två 3", "§ 3 Tre 4")


def paragrafer(*sidor: str, lista: bool = True, forsta: str = FORSTA) -> tuple[list[int], list[str]]:
    lop = [sida(1, forsta), *([ARENDELISTA] if lista else []), *sidor]
    t = Tolkning()
    _behandlingar(t, lop, [forsta])
    return [b.paragraf for b in t.behandlingar], t.avvikelser


BESLUT = ("Kommunstyrelsens beslut", "att godkänna.")


def test_felskriven_rubrik_med_motkontroll():
    nr, avv = paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT), sida(4, "Ko§ 3", "Tre", *BESLUT))
    assert nr == [1, 2, 3]
    assert avv == ['Paragrafrubriken är felskriven i protokollet: "Ko§ 3" (s. 4)']
    # Utan ärendelista räcker följden och intervallet.
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT), sida(4, "Ko§ 3", "Tre", *BESLUT),
                      lista=False)[0] == [1, 2, 3]


def test_felskriven_rubrik_godtas_inte_utan_motkontroll():
    # Inte nästa paragraf i följden.
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT), sida(4, "Ko§ 3", "Tre", *BESLUT))[0] == [1]
    # Utanför försättsbladets intervall (och utan intervall).
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT), sida(4, "Ko§ 3", "Tre", *BESLUT),
                      forsta="Plats och tid Rådhuset\nParagrafer 1-2")[0] == [1, 2]
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT), sida(4, "Ko§ 3", "Tre", *BESLUT),
                      lista=False, forsta="Plats och tid Rådhuset")[0] == [1, 2]
    # Ärendelistan anger en annan sida.
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT, "Ko§ 3", "Tre", *BESLUT))[0] == [1, 2]
    # Text efter numret: vanlig löptext, ingen rubrik.
    assert paragrafer(sida(3, "§ 1", "Ett", *BESLUT, "§ 2", "Två", *BESLUT), sida(4, "jf§ 3 i lagen", *BESLUT))[0] == [1, 2]
