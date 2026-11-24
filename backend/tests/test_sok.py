"""Fulltextsökning och sökindex (#142).

Söm 1: indexering och sökning mot riktig Postgres. Testprotokollet är skolnämndens protokoll 2026-10-01
med kallelsens föredragningslista (se test_diarienummer_ur_kallelsen), kommunfullmäktiges protokoll används
där fler sammanträden behövs.
"""

from __future__ import annotations

import logging

import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_diarienummer_ur_kallelsen import Kalla
from test_protokoll import kf
from test_rattelser import logga_in, publicerad
from test_sammantradesplaner import kor

from app import db, sokindex


@pytest.fixture
def api(database_url, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[Kalla()], anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def sok(api: TestClient, q: str, **param) -> dict:
    svar = api.get("/api/sok", params={"q": q, **param})
    assert svar.status_code == 200, svar.text
    return svar.json()


def per_typ(svar: dict) -> dict[str, int]:
    return {p["typ"]: p["antal"] for p in svar["per_typ"] if p["antal"]}


def utdrag(t: dict) -> str:
    return "".join(f"[{d['text']}]" if d["markerad"] else d["text"] for d in t["utdrag"])


def skol(api: TestClient) -> int:
    [s] = [s for s in api.get("/api/sammantraden?organ=SKOL").json() if s["datum"] == "2026-10-01"]
    return s["id"]


def test_insamlingen_indexerar_protokollet_kallelsen_arendena_och_ledamoterna(api):
    s = skol(api)
    svar = sok(api, "förskola")
    assert per_typ(svar) == {"behandling": 2, "protokollsida": 6, "arende": 1, "kallelsepunkt": 1}
    assert [p["namn"] for p in svar["per_typ"]] == [
        "Behandling", "Protokollsida", "Budgetförslag", "Ärende", "Ledamot", "Kallelsepunkt"]

    traffar = {(t["typ"], t["rubrik"]): t for t in svar["traffar"]}
    b = traffar[("behandling", "Svar på motion om kontinuitet i allmän förskola")]
    assert (b["undertitel"], b["organ"], b["datum"], b["lank"]) == (
        "§ 105", {"id": "SKOL", "namn": "Skolnämnden"}, "2026-10-01", f"/politik/sammantraden/{s}/paragraf/105")
    # Länken går till sidan i protokollet där paragrafen börjar, inte till innehållsförteckningen.
    assert b["dokument"].startswith("/api/dokument/") and b["dokument"].endswith("#page=14")
    assert b["markeringar"] == ["automatiskt_tolkad", "diarienummer_ur_kallelsen"]

    sidor = [t for t in svar["traffar"] if t["typ"] == "protokollsida"]
    assert all(t["lank"] == f"/politik/sammantraden/{s}" and t["dokument"].endswith(f"#page={t['sida']}") for t in sidor)
    assert all("[förskola]" in utdrag(t).lower() or "[förskolan]" in utdrag(t).lower() for t in sidor)

    k = traffar[("kallelsepunkt", "Svar på motion om kontinuitet i allmän förskola")]
    assert (k["undertitel"], k["lank"], k["markeringar"]) == ("Kallelse, § 105", f"/politik/sammantraden/{s}",
                                                              ["automatiskt_tolkad"])
    assert k["dokument"].startswith("https://harnosand.se/download/") and k["dokument"].endswith("#page=13")

    a = traffar[("arende", "Svar på motion om kontinuitet i allmän förskola")]
    assert a["lank"].startswith("/politik/arenden/")
    assert api.get(f"/api{a['lank'].removeprefix('/politik')}").json()["rubrik"] == a["rubrik"]

    # Ledamöterna i registret har en enhet med länk till personsidan.
    [led] = sok(api, "Mattias Sjölander", typ="ledamot")["traffar"]
    assert api.get(f"/api{led['lank'].removeprefix('/politik')}").json()["namn"] == "Mattias Sjölander"


def test_bojningar(api):
    # "förskola", "förskolan" och "förskolor" hittar samma enheter, och utdraget markerar alla former.
    svar = [sok(api, q) for q in ("förskola", "förskolan", "förskolor", "Förskolorna")]
    assert all(per_typ(s) == per_typ(svar[0]) for s in svar)
    assert any("[förskolan]" in utdrag(t) for t in svar[1]["traffar"])


@pytest.mark.parametrize(("ord_", "text"), [
    ("skolan", "Nya skolor i Härnösand"), ("skolor", "Skolan i Härnösand"), ("beslut", "Beslutet överklagas"),
    ("beslutet", "Två beslut"), ("huset", "Husen på Norra Sundet"), ("frågan", "Inga frågor har inkommit"),
])
def test_bestamd_form_som_stemmern_inte_tar(database_url, ord_, text, monkeypatch):
    db.migrate(database_url)
    with db.connect(database_url) as conn:
        # En ny källa är en typ och en funktion som ger texten.
        monkeypatch.setitem(sokindex.KALLOR, "ledamot", sokindex.Kalla(lambda c, o: [sokindex.Grupp("", [
            sokindex.Enhet(typ="ledamot", nyckel="1", rubrik="Test", lank="/", text_c=text)])]))
        sokindex.indexera(conn, typer=["ledamot"])
        assert sokindex.sok(conn, ord_)["antal"] == 1
        assert sokindex.sok(conn, "skolgård")["antal"] == 0


def test_diarienummer_ger_arendet_och_behandlingarna_forst(api):
    svar = sok(api, "SKN/2026-717")
    assert [t["typ"] for t in svar["traffar"]] == ["arende", "behandling", "kallelsepunkt"]
    # Mellanslag och gemener spelar ingen roll. Frågan leder inte direkt till ärendet.
    assert [t["typ"] for t in sok(api, "skn / 2026-717")["traffar"]][:2] == ["arende", "behandling"]
    # Också med sorteringen på datum kommer de med.
    assert len(sok(api, "SKN/2026-717", sortering="datum")["traffar"]) == 3


def test_ledamotsnamn_ger_personen_overst(api):
    svar = sok(api, "Mattias Sjölander")
    assert svar["traffar"][0]["typ"] == "ledamot"
    assert svar["traffar"][0]["rubrik"] == "Mattias Sjölander"
    assert per_typ(svar)["protokollsida"] >= 1  # namnet står också i protokollets närvarolista


def test_rubrik_vager_tyngre_an_lopande_text(api):
    # "Brännaskolan" står i behandlingens rubrik och på protokollets sidor.
    svar = sok(api, "Brännaskolan")
    typer = [t["typ"] for t in svar["traffar"]]
    assert typer.index("behandling") < typer.index("protokollsida")
    # Beslutet väger tyngre än paragraftexten och löptexten: "handlingsplan" står i beslutet i § 99.
    forsta = sok(api, "handlingsplan")["traffar"][0]
    assert (forsta["typ"], forsta["undertitel"]) == ("behandling", "§ 99")


def test_filter_sortering_och_sidor(api):
    alla = sok(api, "skolnämnden")
    assert alla["antal"] == sum(per_typ(alla).values()) > 20
    bara = sok(api, "skolnämnden", typ="protokollsida")
    assert bara["antal"] == per_typ(alla)["protokollsida"]
    assert {t["typ"] for t in bara["traffar"]} == {"protokollsida"}
    # Antalet per typ räknas utan typfiltret, så att läsaren ser de andra typerna.
    assert per_typ(bara) == per_typ(alla)

    assert sok(api, "skolnämnden", organ="SKOL")["antal"] == alla["antal"] - per_typ(alla).get("ledamot", 0)
    assert sok(api, "skolnämnden", organ="KF")["antal"] == 0
    assert sok(api, "skolnämnden", ar=2026)["antal"] > 0
    assert sok(api, "skolnämnden", ar=2025)["antal"] == 0

    forsta = sok(api, "skolnämnden")
    andra = sok(api, "skolnämnden", sida=2)
    assert len(forsta["traffar"]) == forsta["sidstorlek"] == 20
    assert len(andra["traffar"]) == alla["antal"] - 20
    assert not {(t["typ"], t["rubrik"], t["sida"]) for t in forsta["traffar"]} & {
        (t["typ"], t["rubrik"], t["sida"]) for t in andra["traffar"]}

    for fel in ({"q": "a"}, {"q": "skola", "organ": "XX"}, {"q": "skola", "typ": "nagot"},
                {"q": "skola", "sortering": "basta"}, {"q": "skola", "sida": 0}):
        assert api.get("/api/sok", params=fel).status_code == 422, fel


def test_senaste_forst(database_url, google):
    a = TestClient(skapa_app(database_url, google, kallor=kf(), anonym_lasning=True))
    kor(a)
    datum = [t["datum"] for t in sok(a, "fråga", sortering="datum", typ="behandling")["traffar"]]
    assert datum == sorted(datum, reverse=True) and len(set(datum)) > 3
    # Relevansen lyfter inte nyare träffar: ordningen är en annan.
    relevans = [t["datum"] for t in sok(a, "fråga", typ="behandling")["traffar"]]
    assert len(relevans) == len(datum) and relevans != datum


def test_publicerad_rattelse_syns_i_traffen_och_aterkallad_forsvinner(api):
    s = skol(api)
    assert sok(api, "Kvarnbackaskolan")["antal"] == 0
    r = publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=103, falt="rubrik",
                   nytt="Anpassning och utbyggnation av Kvarnbackaskolan", motivering="Fel skola i rubriken",
                   felet_i="protokollet")
    [t] = sok(api, "Kvarnbackaskolan", typ="behandling")["traffar"]
    assert (t["typ"], t["rubrik"], t["markeringar"]) == (
        "behandling", "Anpassning och utbyggnation av Kvarnbackaskolan",
        ["automatiskt_tolkad", "rattad", "felaktigheter"])
    assert t["felaktigheter"] == 1
    # Protokollets sidor märks också "Innehåller felaktigheter", och ärendet har den rättade rubriken.
    assert all("felaktigheter" in x["markeringar"] for x in sok(api, "skolnämnden", typ="protokollsida")["traffar"])
    [a] = sok(api, "Anpassning utbyggnation", typ="arende")["traffar"]
    assert a["rubrik"] == "Anpassning och utbyggnation av Kvarnbackaskolan"

    logga_in(api, "utgivare")
    assert api.post(f"/api/rattelser/{r['id']}/aterkallelse", json={"motivering": "Rubriken stämde"}).status_code == 200
    logga_in(api, None)
    assert sok(api, "Kvarnbackaskolan")["antal"] == 0
    [t] = sok(api, "Brännaskolan", typ="behandling")["traffar"]
    assert t["markeringar"] == ["automatiskt_tolkad"]


def test_bara_andrade_enheter_raknas_om(api, database_url):
    s = skol(api)
    with db.connect(database_url) as conn:
        fore = {(r["typ"], r["nyckel"]): r for r in conn.execute("SELECT typ, nyckel, text_andrad FROM sokenhet")}
        antal = sokindex.indexera(conn, extrahera=False)
        assert (antal["nya"], antal["andrade"], antal["borttagna"]) == (0, 0, 0)
        assert antal["oforandrade"] == len(fore)

        conn.execute("UPDATE behandling SET beslut = 'Skolnämnden beslutar att bygga en ny förskola.' "
                     "WHERE sammantrade_id = %s AND paragraf = 107", (s,))
        assert sokindex.indexera(conn, typer=["behandling"], extrahera=False)["andrade"] == 1
        efter = {(r["typ"], r["nyckel"]): r for r in conn.execute("SELECT typ, nyckel, text_andrad FROM sokenhet")}
        andrade = {n for n in fore if efter[n]["text_andrad"] != fore[n]["text_andrad"]}
        assert andrade == {("behandling", f"{s}:107")}

        # En behandling som försvinner ur protokollet tas bort ur indexet.
        conn.execute("DELETE FROM behandling WHERE sammantrade_id = %s AND paragraf = 107", (s,))
        assert sokindex.indexera(conn, typer=["behandling"], extrahera=False)["borttagna"] == 1
        conn.commit()


def test_ombyggnaden_kan_avbrytas_och_aterupptas(api, database_url, monkeypatch):
    lasta = []
    las_pdf = sokindex._las_pdf

    def raknad(pdf: bytes):
        lasta.append(len(pdf))
        if len(lasta) == 1:
            raise KeyboardInterrupt  # avbruten mitt i
        return las_pdf(pdf)

    monkeypatch.setattr(sokindex, "_las_pdf", raknad)
    with db.connect(database_url) as conn:
        sidor = conn.execute("SELECT count(*) AS n FROM sokenhet WHERE typ = 'protokollsida'").fetchone()["n"]
        with pytest.raises(KeyboardInterrupt):
            sokindex.bygg(conn, bygg_om=True)
        conn.rollback()
        [o] = conn.execute("SELECT * FROM sokindex_ombyggnad").fetchall()
        assert o["klar"] is None
        sokindex.bygg(conn, bygg_om=True)  # återupptar samma ombyggnad
        assert len(lasta) == 2
        assert [r["klar"] is not None for r in conn.execute("SELECT * FROM sokindex_ombyggnad")] == [True]
        assert conn.execute("SELECT count(*) AS n FROM sokenhet WHERE typ = 'protokollsida'").fetchone()["n"] == sidor
        # Klar: en ny körning utan ombyggnad läser ingenting.
        sokindex.bygg(conn)
        assert len(lasta) == 2


def test_kommandot(database_url, google, monkeypatch, capsys):
    a = TestClient(skapa_app(database_url, google, kallor=[Kalla()], anonym_lasning=True))
    kor(a)
    monkeypatch.setenv("DATABASE_URL", database_url)
    sokindex.main([])
    assert "0 nya, 0 ändrade" in capsys.readouterr().out
    sokindex.main(["--bygg-om"])
    ut = capsys.readouterr().out
    assert "0 nya" in ut and "0 borttagna" in ut


def test_hogst_30_fragor_per_minut_och_ip_adress(api):
    for _ in range(30):
        assert api.get("/api/sok", params={"q": "förskola"}).status_code == 200
    svar = api.get("/api/sok", params={"q": "förskola"})
    assert svar.status_code == 429
    assert int(svar.headers["Retry-After"]) > 0

    klocka = [0.0]
    grans = sokindex.Fragegrans(2, 60, klocka=lambda: klocka[0])
    assert grans.tillat("a") is None and grans.tillat("a") is None
    assert grans.tillat("a") == 60
    assert grans.tillat("b") is None  # en annan adress
    klocka[0] = 61
    assert grans.tillat("a") is None


def test_sokfragorna_loggas_inte(api, caplog):
    caplog.set_level(logging.INFO)
    sok(api, "hemligt förskola")
    # Testklientens egen logg (httpx) är inte serverns.
    assert not any("hemligt" in r.getMessage() for r in caplog.records if r.name != "httpx")
    [rad] = [r for r in caplog.records if r.name == "app.sok"]
    assert "träffar" in rad.getMessage() and " ms" in rad.getMessage()

    # Åtkomstloggens rad får adressen utan frågan.
    post = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("1.2.3.4:5", "GET", "/api/sok?q=hemligt", "1.1", 200), None)
    sokindex.UtanSokfragor().filter(post)
    assert "hemligt" not in post.getMessage() and "/api/sok" in post.getMessage()


def test_budgetforslagens_text_indexeras_nar_de_publiceras(database_url, google, monkeypatch, capsys):
    from test_budgetforslag import las_in, publicera_alla

    a = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    las_in(database_url, monkeypatch, capsys)
    assert sok(a, "skattesats")["antal"] == 0  # utkasten är inte publicerade
    publicera_alla(a)
    svar = sok(a, "skattesats", typ="budgetforslag")
    assert svar["antal"] > 0
    t = svar["traffar"][0]
    assert t["lank"] == "/politik/budget?ar=2027" and t["ar"] == 2027
    assert t["dokument"].startswith("/api/budgetforslag/") and f"/original#page={t['sida']}" in t["dokument"]
    assert sok(a, "skattesats", typ="budgetforslag", ar=2027)["antal"] == svar["antal"]

    # Ett återkallat förslag försvinner ur sökningen.
    logga_in(a, "redaktor")
    forslag = {f["nyckel"]: f for f in a.get("/api/budgetforslag?status=publicerad").json()}
    logga_in(a, "utgivare")
    [nyckel, *_] = forslag
    assert a.post(f"/api/budgetforslag/{forslag[nyckel]['id']}/aterkallelse",
                  json={"motivering": "Fel fil"}).status_code == 200
    logga_in(a, None)
    kvar = sok(a, "skattesats", typ="budgetforslag")["traffar"]
    assert all(f"/api/budgetforslag/{forslag[nyckel]['id']}/" not in t["dokument"] for t in kvar)


def test_paragrafsida_hoppar_over_innehallsforteckningen():
    sidor = ["Protokoll", "§ 1 Val av justerare\n§ 2 Dagordning 4\n§ 3 Budget 5\n§ 4 Övrigt 6",
             "§ 1 Dnr 1\nVal av justerare", "§ 2 Dagordning ..... 4", "Text\n§ 2 Dnr 9\nDagordning", "§ 30 Annat"]
    assert sokindex.paragrafsida(sidor, 1) == 3
    assert sokindex.paragrafsida(sidor, 2) == 5
    assert sokindex.paragrafsida(sidor, 3) is None
    assert sokindex.paragrafsida(sidor, 30) == 6


def test_word_dokumentets_rubriker():
    import io
    import zipfile

    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    xml = (f'<w:document {w}><w:body>'
           '<w:p><w:pPr><w:pStyle w:val="Rubrik1"/></w:pPr><w:r><w:t>Skola</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Vi satsar på </w:t></w:r><w:r><w:t>skolan.</w:t></w:r></w:p>'
           '<w:p></w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    assert sokindex._word_stycken(buf.getvalue()) == [("Skola", True), ("Vi satsar på skolan.", False)]


def test_normalisering():
    assert sokindex.normalisera("  KS / 2026 - 386 ") == "ks/2026-386"
    assert sokindex.exakt_fraga('"Anna  Karin"') == "anna karin"
