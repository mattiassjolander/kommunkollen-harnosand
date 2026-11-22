"""Paragrafrad i fel läsordning, och motkontroll av rubrikerna mot ärendelistan (#88).

Fixturen är sidorna 1–4 ur samhällsnämndens protokoll 2026-06-17: försättsbladet, ärendelistan och § 78–79.
På sidan 3 lagrar PDF:en raden "§ 78" sist i textflödet, efter rubriken och beslutet. I layouttexten står
den först, som på den tryckta sidan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app import avvikelser, db
from app.protokolltolkning import Tolkning, _behandlingar, arendelista, sidtexter, tolka
from test_rattelser import api, behandling, publicerad, sammantrade_id  # noqa: F401

FIXTURER = Path(__file__).parent / "fixtures" / "protokoll"


def test_paragrafraden_sist_i_textflodet_flyttas_till_sidans_borjan():
    pdf = (FIXTURER / "sam-2026-06-17-urval.pdf").read_bytes()
    lop, layout = sidtexter(pdf)
    assert lop[2].rstrip().endswith("§ 78")  # felet i PDF:en
    t = tolka(pdf)
    per_nr = {b.paragraf: b for b in t.behandlingar}
    assert per_nr[78].rubrik == "Val av justerare"
    assert per_nr[78].beslut == ("Samhällsnämnden beslutar\n"
                                 "att utse Anders Bergqvist (V) till justerare för dagens protokoll.")
    assert not per_nr[78].rubrik_ur_arendelistan
    assert per_nr[79].rubrik == "Fastställande av dagordning"
    assert not any(a.startswith("§ 78") or "ärendelistan" in a for a in t.avvikelser)


def test_arendelistan_i_protokollet():
    lop, _ = sidtexter((FIXTURER / "sam-2026-06-17-urval.pdf").read_bytes())
    lista = arendelista(lop)
    assert lista[78] == "Val av justerare"
    # Rubriken fortsätter på nästa rad, och sidnumret står ensamt.
    assert lista[82] == "Detaljplan för del av Fastlandet 2:66 och Gådeå 4:32 m.fl. E4 södra infarten- Beslut om antagande"
    assert lista[88] == "Revisionsrapport – Grundläggande granskning Samhällsnämnden 2025"
    assert lista[93] == "Eventuellt tillkommande ärende"


def sida(nr: int, *rader: str) -> str:
    return "\n".join(["Samhällsnämnden", "SAMMANTRÄDESPROTOKOLL", f"{nr}(4)", *rader])


def layoutsida(*rader: str) -> str:
    return "\n".join(["   SAMMANTRÄDESPROTOKOLL      Sida", "Samhällsnämnden", *(f"      {r}" for r in rader)])


FORSTA = "Plats och tid Rådhuset\nBeslutande\nParagrafer 1-3"
BESLUT = ("Samhällsnämndens beslut", "att godkänna.")


def tolkning(*sidor: tuple[str, str | None], lista: list[str] | None = None) -> Tolkning:
    """Protokoll ur (löptext, layouttext) per sida, med en ärendelista om `lista` anges."""
    lop = [sida(1, FORSTA)]
    layout = [FORSTA]
    if lista is not None:
        lop.append(sida(2, "Ärendelista", "Nummer Rubrik Sida", *lista))
        layout.append("")
    lop += [s for s, _ in sidor]
    layout += [lay or "" for _, lay in sidor]
    t = Tolkning()
    _behandlingar(t, lop, layout)
    return t


def test_paragrafraden_flyttas_bara_nar_layouten_har_den_forst():
    lop = sida(3, "Ett", *BESLUT, "§ 1")
    # Layouten har paragrafraden direkt före rubriken: raden flyttas.
    t = tolkning((lop, layoutsida("§   1", "Ett", *BESLUT)))
    assert [(b.paragraf, b.rubrik) for b in t.behandlingar] == [(1, "Ett")]
    # Layouten har den också sist: ingenting flyttas, och raden blir början på nästa paragraf.
    t = tolkning((lop, layoutsida("Ett", *BESLUT, "§ 1")))
    assert [(b.paragraf, b.rubrik) for b in t.behandlingar] == [(1, "")]
    # Ingen layouttext för sidan.
    assert [b.rubrik for b in tolkning((lop, None)).behandlingar] == [""]
    # Raden är inte ensam ("§ 1 Ett"), eller sidan har redan en paragrafrad.
    t = tolkning((sida(3, "Ett", *BESLUT, "§ 1 Ett"), layoutsida("§ 1 Ett", "Ett", *BESLUT)))
    assert t.behandlingar == []
    t = tolkning((sida(3, "§ 1", "Ett", *BESLUT, "§ 2"), layoutsida("§ 2", "§ 1", "Ett", *BESLUT)))
    assert [(b.paragraf, b.rubrik) for b in t.behandlingar] == [(1, "Ett"), (2, "")]


def test_saknad_rubrik_tas_ur_arendelistan_med_markering():
    t = tolkning((sida(3, "§ 1", *BESLUT, "§ 2", "Två", *BESLUT), None),
                 lista=["§ 1 Val av justerare 3", "§ 2 Två 3"])
    b1, b2 = t.behandlingar
    assert (b1.rubrik, b1.rubrik_ur_arendelistan) == ("Val av justerare", True)
    assert (b2.rubrik, b2.rubrik_ur_arendelistan) == ("Två", False)
    assert t.avvikelser == ["§ 1: rubriken hittades inte i paragrafen och är hämtad ur ärendelistan"]
    assert avvikelser.kategori(t.avvikelser[0]) == "tolkning"
    # Utan ärendelista är rubriken tom, som tidigare.
    t = tolkning((sida(3, "§ 1", *BESLUT), None))
    assert (t.behandlingar[0].rubrik, t.avvikelser) == ("", ["§ 1: rubriken hittades inte"])


def test_arendelistan_i_aldre_form():
    lop = [sida(2, "Ärendelista", "§ 1 Dnr 34746 4", "Val av justerare ................................ 4",
                "§ 2 Dnr 2024-000129 1.1.1.1", "Motion - Främja självhushållning i",
                "Härnösand ........................ 5", "§ 3 Dnr 42566 6", "Godkännande av dagordning .... .... 6")]
    assert arendelista(lop) == {1: "Val av justerare", 2: "Motion - Främja självhushållning i Härnösand",
                                3: "Godkännande av dagordning"}


def motkontroll(rubrik: str, i_listan: str) -> list[str]:
    return tolkning((sida(3, "§ 1", rubrik, *BESLUT), None), lista=[f"§ 1 {i_listan} 3"]).avvikelser


def test_rubriker_som_skiljer_sig_fran_arendelistan():
    # Mellanslag, skiljetecken, tankstreck och versaler räknas inte.
    assert motkontroll("Bygglov – Särskilt boende,  Jensenvägen", "Bygglov- särskilt boende Jensenvägen") == []

    [a] = motkontroll("Beslut om avtal och budget för Nybron", "Beslut om avtal och budget Nybron")
    assert a == ('§ 1: rubriken skiljer sig från ärendelistan i protokollet: "Beslut om avtal och budget för Nybron" '
                 'i paragrafen, "Beslut om avtal och budget Nybron" i ärendelistan')
    assert avvikelser.kategori(a) == "motsagelse" and "motsagelse" in avvikelser.I_PROTOKOLLET

    [a] = motkontroll("Korta frågor Inga frågor ställdes.", "Korta frågor")
    assert a == ('§ 1: rubriken är längre än i ärendelistan ("Korta frågor"). '
                 "Inläsningen har troligen tagit med text ur paragrafen")
    assert avvikelser.kategori(a) == "tolkning"

    [a] = motkontroll("Granskning av bokslut per", "Granskning av bokslut per 2025-12-31")
    assert "kortare än i ärendelistan" in a and avvikelser.kategori(a) == "tolkning"

    [a] = motkontroll("S X X X X", "Ansvarsfrihet 2023 skolnämnden")
    assert a == ('§ 1: rubriken stämmer inte med ärendelistan ("Ansvarsfrihet 2023 skolnämnden"). '
                 "Inläsningen har troligen läst fel text som rubrik")
    assert avvikelser.kategori(a) == "tolkning"


def test_rubriken_ur_arendelistan_sparas_och_visas(api, database_url, monkeypatch):  # noqa: F811
    from app import protokoll
    from app.protokoll import tolka_om

    s = sammantrade_id(api, "2026-06-15")
    paragraf = behandling(api, "2026-06-15", 109)["paragraf"]
    riktig = protokoll.tolka

    def med_markering(pdf: bytes):
        t = riktig(pdf)
        for b in t.behandlingar:
            if b.paragraf == paragraf:
                b.rubrik, b.rubrik_ur_arendelistan = "Rubrik ur listan", True
        return t

    monkeypatch.setattr(protokoll, "tolka", med_markering)
    with db.connect(database_url) as conn:
        tolka_om(conn, datetime.now(timezone.utc))

    [rad] = [b for b in api.get(f"/api/sammantraden/{s}").json()["behandlingar"] if b["paragraf"] == paragraf]
    assert (rad["rubrik"], rad["rubrik_ur_arendelistan"]) == ("Rubrik ur listan", True)
    assert behandling(api, "2026-06-15", paragraf)["rubrik_ur_arendelistan"] is True
    assert "rubrik_ur_arendelistan" not in behandling(api, "2026-06-15", paragraf + 1)

    # En publicerad rättelse av rubriken går före ärendelistan.
    publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=paragraf, falt="rubrik",
               nytt="Rättad rubrik", motivering="Rubriken i paragrafen")
    b = behandling(api, "2026-06-15", paragraf)
    assert (b["rubrik"], b["rubrik_ur_arendelistan"]) == ("Rättad rubrik", False)
