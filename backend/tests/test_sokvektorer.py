"""Sökning på betydelse (#69): vektorer i pgvector och hybridsök med reciprocal rank fusion.

Söm 1 mot Postgres med pgvector. De flesta testerna använder den deterministiska testmodellen, som hashar
orden (fem första bokstäverna). Ett test använder den riktiga modellen.
"""

from __future__ import annotations

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_diarienummer_ur_kallelsen import Kalla
from test_sammantradesplaner import kor

from app import db, sokindex, sokvektorer
from app.sokindex import Enhet, Grupp, Kalla as Sokkalla


def enheter(monkeypatch, *lista: Enhet) -> None:
    """Behandlingarna i indexet är bara de här."""
    monkeypatch.setitem(sokindex.KALLOR, "behandling", Sokkalla(lambda c, o: [Grupp("", list(lista))]))


def behandling(nyckel: str, rubrik: str, text: str = "", **kw) -> Enhet:
    return Enhet(typ="behandling", nyckel=nyckel, rubrik=rubrik, lank=f"/b/{nyckel}", text_a=rubrik, text_c=text,
                 **kw)


@pytest.fixture
def conn(database_url):
    db.migrate(database_url)
    with db.connect(database_url) as c:
        yield c


def stycken_i_databasen(conn) -> dict[str, list[str]]:
    ut: dict[str, list[str]] = {}
    for r in conn.execute("SELECT e.nyckel, s.text FROM sokstycke s JOIN sokenhet e ON e.id = s.enhet_id "
                          "ORDER BY e.nyckel, s.ordning"):
        ut.setdefault(r["nyckel"], []).append(r["text"])
    return ut


def test_pgvector_ar_aktiverat(conn):
    assert sokvektorer.tillganglig(conn)
    assert conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone()
    # Indexet är HNSW med cosinusavstånd.
    [index] = conn.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'sokstycke_vektor'").fetchall()
    assert "hnsw" in index["indexdef"] and "vector_cosine_ops" in index["indexdef"]
    # Förberedelsen kan köras igen (varje start).
    assert sokvektorer.forbered(conn)


def test_en_traff_i_bada_listorna_rankas_over_en_som_bara_finns_i_en(conn, monkeypatch):
    fyllnad = " ".join(f"ord{i:02d}x" for i in range(40))
    enheter(
        monkeypatch,
        # I fulltexten (sökordet) och nära frågan.
        behandling("bada", "Skolnedläggning i Säbrå"),
        # Bäst i fulltexten (sökordet tre gånger), men långt från frågan bland många andra ord.
        behandling("fulltext", f"Skolnedläggning {fyllnad[:34]}", f"skolnedläggning skolnedläggning {fyllnad}"),
        # Inte sökordet, men närmast frågan för testmodellen ("skoln").
        behandling("vektor", "Skolnämnden", "Skolnämnden sammanträdde i dag. Ett beslut om lokaler fattades."),
        behandling("ingen", "Partistöd 2026", "Kommunfullmäktige beslutar om partistöd."),
    )
    sokindex.indexera(conn, typer=["behandling"])

    svar = sokindex.sok(conn, "skolnedläggning")
    traffar = {t["lank"]: t for t in svar["traffar"]}
    assert [t["lank"] for t in svar["traffar"]][0] == "/b/bada"
    assert set(traffar) == {"/b/bada", "/b/fulltext", "/b/vektor"}
    assert svar["antal"] == 3

    # Bara vektorträffen saknar sökordet. Utdraget är den mening som ligger närmast frågan, utan markering.
    assert {k: t["betydelse"] for k, t in traffar.items()} == {"/b/bada": False, "/b/fulltext": False,
                                                                "/b/vektor": True}
    assert traffar["/b/vektor"]["utdrag"] == [{"text": "Skolnämnden sammanträdde i dag.", "markerad": False}]
    assert any(d["markerad"] for d in traffar["/b/fulltext"]["utdrag"])

    # Utan vektorsökning är fulltextträffen med flest sökord först.
    sokvektorer.satt_modell(None)
    assert [t["lank"] for t in sokindex.sok(conn, "skolnedläggning")["traffar"]] == ["/b/fulltext", "/b/bada"]


def test_filtren_galler_ocksa_vektortraffarna(conn, monkeypatch):
    from datetime import date

    enheter(
        monkeypatch,
        behandling("2025", "Skolnämnden", "Skolnämnden", organ="SKOL", datum=date(2025, 3, 1), ar=2025),
        behandling("2026", "Skolnämnden", "Skolnämnden", organ="SKOL", datum=date(2026, 3, 1), ar=2026),
        behandling("ks", "Skolnämnden", "Skolnämnden", organ="KS", datum=date(2026, 4, 1), ar=2026),
    )
    sokindex.indexera(conn, typer=["behandling"])
    lankar = lambda **kw: sorted(t["lank"] for t in sokindex.sok(conn, "skolnedläggning", **kw)["traffar"])  # noqa: E731
    assert lankar() == ["/b/2025", "/b/2026", "/b/ks"]
    assert lankar(ar=2026) == ["/b/2026", "/b/ks"]
    assert lankar(organ="SKOL", ar=2026) == ["/b/2026"]
    assert lankar(typ="arende") == []
    # Sorteringen på datum gäller också dem.
    assert [t["lank"] for t in sokindex.sok(conn, "skolnedläggning", sortering="datum")["traffar"]] == [
        "/b/ks", "/b/2026", "/b/2025"]


def test_ett_diarienummer_soks_inte_pa_betydelse(conn, monkeypatch):
    enheter(monkeypatch, behandling("1", "KS/2026-1", "KS/2026-1"), behandling("2", "KS/2026-2", "KS/2026-2"))
    sokindex.indexera(conn, typer=["behandling"])
    assert [t["lank"] for t in sokindex.sok(conn, "KS/2026-1")["traffar"]] == ["/b/1"]


def test_en_andrad_text_raknas_om_och_en_oforandrad_inte(conn, monkeypatch):
    raknade: list[str] = []
    modell = sokvektorer.Testmodell()
    passager = modell.passager
    monkeypatch.setattr(modell, "passager", lambda texter: raknade.extend(texter) or passager(texter))
    sokvektorer.satt_modell(modell)

    enheter(monkeypatch, behandling("a", "Skolan", "Första texten."), behandling("b", "Vägen", "Om vägen."))
    sokindex.indexera(conn, typer=["behandling"])
    # Rubriken är ett eget stycke.
    assert raknade == ["Skolan", "Skolan\nFörsta texten.", "Vägen", "Vägen\nOm vägen."]
    assert sokvektorer.status(conn) | {"modell": None} == {
        "aktiv": True, "modell": None, "enheter": 2, "med_vektorer": 2, "vantar": 0}

    raknade.clear()
    sokindex.indexera(conn, typer=["behandling"])
    assert raknade == []

    enheter(monkeypatch, behandling("a", "Skolan", "Andra texten."), behandling("b", "Vägen", "Om vägen."))
    sokindex.indexera(conn, typer=["behandling"])
    assert raknade == ["Skolan", "Skolan\nAndra texten."]
    assert stycken_i_databasen(conn) == {"a": ["Skolan", "Skolan\nAndra texten."], "b": ["Vägen", "Vägen\nOm vägen."]}

    # En borttagen enhet tar sina stycken med sig.
    enheter(monkeypatch, behandling("b", "Vägen", "Om vägen."))
    sokindex.indexera(conn, typer=["behandling"])
    assert stycken_i_databasen(conn) == {"b": ["Vägen", "Vägen\nOm vägen."]}


def test_modellbyte_raknar_om_allt_stegvis_och_kan_aterupptas(conn, monkeypatch):
    enheter(monkeypatch, *(behandling(str(i), f"Ärende {i}", "Skolnämnden") for i in range(5)))
    sokindex.indexera(conn, typer=["behandling"])

    class Ny(sokvektorer.Testmodell):
        namn = "ny-modell"

    ny = Ny()
    sokvektorer.satt_modell(ny)
    assert sokvektorer.status(conn) == {"aktiv": True, "modell": "ny-modell", "enheter": 5, "med_vektorer": 0,
                                        "vantar": 5}
    # Vektorsökningen använder bara vektorer från den aktuella modellen. Fulltexten fungerar under tiden.
    assert sokindex.sok(conn, "skolnedläggning")["antal"] == 0
    assert sokindex.sok(conn, "skolnämnden")["antal"] == 5

    # Avbryts efter första gruppen: det som sparats görs inte om.
    anrop = 0
    passager = ny.passager

    def avbryt(texter):
        nonlocal anrop
        anrop += 1
        if anrop == 2:
            raise KeyboardInterrupt
        return passager(texter)

    monkeypatch.setattr(ny, "passager", avbryt)
    with pytest.raises(KeyboardInterrupt):
        sokvektorer.vektorisera(conn, commit=True, grupp=2)
    conn.rollback()
    assert sokvektorer.status(conn)["vantar"] == 3

    monkeypatch.setattr(ny, "passager", passager)
    assert sokindex.bygg(conn)["vektorer"] == 3
    assert sokvektorer.status(conn)["vantar"] == 0
    assert {r["modell"] for r in conn.execute("SELECT DISTINCT modell FROM sokstycke")} == {"ny-modell"}
    assert sokindex.sok(conn, "skolnedläggning")["antal"] == 5


def test_stycken_om_300_ord_med_50_ords_overlapp():
    ord_ = [f"o{i}" for i in range(700)]
    stycken = sokvektorer.stycken("Rubrik KS/2026-1", "", " ".join(ord_))
    assert len(stycken) == 4 and stycken[0] == "Rubrik KS/2026-1"
    stycken = stycken[1:]
    assert [s.split()[:3] for s in stycken] == [["Rubrik", "KS/2026-1", "o0"], ["Rubrik", "KS/2026-1", "o250"],
                                                ["Rubrik", "KS/2026-1", "o500"]]
    assert [s.split()[-1] for s in stycken] == ["o299", "o549", "o699"]
    # En kort enhet är ett stycke, och en utan annan text än rubriken är rubriken.
    assert sokvektorer.stycken("Rubrik", "Beslutet.", "Texten.") == ["Rubrik", "Rubrik\nBeslutet. Texten."]
    assert sokvektorer.stycken("Lennart Molin", "", "") == ["Lennart Molin"]
    assert sokvektorer.stycken("", "", "") == []


def test_stycket_har_enhetens_sida(conn, monkeypatch):
    enheter(monkeypatch, behandling("a", "Skolan", "Text.", sida=14))
    sokindex.indexera(conn, typer=["behandling"])
    assert conn.execute("SELECT sida, modell FROM sokstycke").fetchall() == [
        {"sida": 14, "modell": "test-ordhash-1"}] * 2


def test_utan_pgvector_ar_sokningen_fulltext(conn, monkeypatch):
    monkeypatch.setattr(sokvektorer, "tillganglig", lambda c: False)
    enheter(monkeypatch, behandling("a", "Skolnämnden", "Skolnämnden"), behandling("b", "Skolan", "Skolan"))
    sokindex.indexera(conn, typer=["behandling"])
    assert conn.execute("SELECT count(*) AS n FROM sokstycke").fetchone()["n"] == 0
    assert sokindex.sok(conn, "skolnedläggning")["antal"] == 0
    assert sokindex.sok(conn, "skolan")["antal"] == 1
    assert sokvektorer.status(conn) == {"aktiv": False, "modell": "test-ordhash-1", "enheter": 2,
                                        "med_vektorer": 0, "vantar": 0}


def test_insamlingen_och_statussidan(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[Kalla()], anonym_lasning=True))
    kor(api)
    s = api.get("/api/status").json()["sokvektorer"]
    assert s["aktiv"] and s["modell"] == "test-ordhash-1"
    assert s["enheter"] > 50 and s["med_vektorer"] == s["enheter"] and s["vantar"] == 0
    # En rättelse som publiceras räknar om sina enheter (via sokindex.uppdatera), se test_sok.


def test_den_riktiga_modellen_hittar_en_omskriven_fraga(conn, monkeypatch):
    sokvektorer.satt_modell(sokvektorer.E5Small())
    enheter(
        monkeypatch,
        behandling("sabra", "Avveckling av Säbrå skola",
                   "Skolnämnden beslutar att avveckla verksamheten vid Säbrå skola från och med höstterminen 2027. "
                   "Eleverna erbjuds plats vid Bergsåker skola."),
        behandling("deleg", "Skolnämndens delegationsordning 2025",
                   "Skolnämnden beslutar att anta den reviderade delegationsordningen."),
        behandling("styr", "Styrdokument som är aktuella för revidering",
                   "Skolnämnden beslutar att förlänga giltighetstiden för styrdokumenten."),
        behandling("parti", "Partistöd 2026", "Kommunfullmäktige beslutar att betala ut partistöd för 2026."),
        behandling("plan", "Detaljplan för del av Fastlandet", "Kommunfullmäktige antar detaljplanen."),
    )
    sokindex.indexera(conn, typer=["behandling"])

    svar = sokindex.sok(conn, "skolnedläggning")
    traffar = {t["lank"]: t for t in svar["traffar"]}
    # Behandlingen om avvecklingen är bland de första, fast den inte innehåller sökordet. Den kommer från
    # vektorsökningen, med en mening ur källan som utdrag.
    assert "/b/sabra" in [t["lank"] for t in svar["traffar"]][:2]
    assert traffar["/b/sabra"]["betydelse"]
    assert traffar["/b/sabra"]["utdrag"][0]["text"] in (
        "Skolnämnden beslutar att avveckla verksamheten vid Säbrå skola från och med höstterminen 2027.",
        "Eleverna erbjuds plats vid Bergsåker skola.")
    # Det som inte handlar om skolor är inte träffar.
    assert "/b/parti" not in traffar and "/b/plan" not in traffar
