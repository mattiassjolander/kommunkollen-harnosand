"""Diarienummer ur kallelsen, när protokollet saknar dem (#109).

Fixturerna i tests/fixtures/kallelser är kommunens egna kallelser, utan bilder:

- skolnämnden 2026-10-01: föredragningslistans 15 sidor (med sidhuvud "Sida N(15)")
- kommunstyrelsen 2026-09-29: handlingarnas 16 första sidor (paragrafnumren 116–131, protokollets 131–143)
- fullmäktige 2026-10-26 kl. 13.15: kungörelsen (bara tabellen) och handlingarnas 16 första sidor
- samhällsnämnden 2026-10-29: sidorna 1–7, 15 och 18 (paragrafsidor utan sidhuvud, med bilagor emellan)
- socialnämnden 2026-10-29: sidorna 1–3 och 38
- skolnämnden 2026-09-03: sidorna 1–6 (tabellen saknar kolumnen Sida)
- socialnämnden 2026-09-24: sidorna 1, 2, 53 och 56 (bara tjänsteskrivelser, och en tabell vars ord
  textutvinningen bryter: "Val av justera" / "re 2")
- samhällsnämnden 2026-09-24: sidorna 1–4 och 53 (bara tjänsteskrivelser, med serien "SAM-2026-2266")

tests/fixtures/protokoll/skol-2026-10-01.pdf är skolnämndens protokoll, som saknar diarienummer.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest
from conftest import skapa_app
from fastapi.testclient import TestClient
from test_rattelser import logga_in, publicerad
from test_sammantradesplaner import kor

from app import avvikelser, db, kallelsepunkter
from app.arenden import koppla
from app.sources import foredragningslista as fl
from app.sources.base import Dokument, Hamtning
from app.sources.kallelser import Kallelse

KALLELSER = Path(__file__).parent / "fixtures" / "kallelser"
PROTOKOLL = Path(__file__).parent / "fixtures" / "protokoll"
SKOL_URL = "https://harnosand.se/download/18.5559ceaa1a0f4ef04c4eb3ed/1791440984328/Kallelse%20skoln%C3%A4mnden%202026-10-01,%20med%20bilagor.pdf"


def dnr(f: fl.Foredragningslista) -> dict[int, list[str]]:
    return {p.paragraf: list(p.diarienummer) for p in f.punkter if p.diarienummer}


def test_skolnamnden_med_sidhuvud_och_utan_paragrafnummer_pa_sidan():
    f = fl.las(KALLELSER / "skol-2026-10-01-foredragningslista.pdf", "SKOL")
    assert f.status == "last", f.fel
    assert dnr(f) == {99: ["SKN/2026-738"], 100: ["SKN/2026-737"], 101: ["SKN/2026-736"], 102: ["SKN/2026-294"],
                      104: ["SKN/2026-734"], 105: ["SKN/2026-717"], 106: ["SKN/2026-202"]}
    per_nr = {p.paragraf: p for p in f.punkter}
    assert [p.paragraf for p in f.punkter] == list(range(96, 108))
    # § 99 och § 105 saknar paragrafnummer på sidan: tabellens sida avgör, och sidans rubrik gäller.
    assert (per_nr[105].sida, per_nr[105].rubrik) == (13, "Svar på motion om kontinuitet i allmän förskola")
    assert per_nr[105].tabellrubrik == "Motion- Kontinuitet i allmän förskola"
    assert per_nr[99].sida == 5


def test_kommunstyrelsens_handlingar():
    f = fl.las(KALLELSER / "ks-2026-09-29-foredragningslista.pdf", "KS")
    assert f.status == "last", f.fel
    # Tabellen fortsätter på sidan 2, efter ordförandens namn.
    assert [p.paragraf for p in f.punkter] == [116, 117, 118, 119, 121, 122, 123, 125, 126, 127, 128, 129, 130, 131]
    assert dnr(f) == {119: ["KS/2026-504"], 121: ["KS/2026-454"], 122: ["KS/2026-489"], 123: ["MNP/2026-5"],
                      125: ["KS/2026-270"], 126: ["KS/2026-340"], 127: ["KS/2026-452"], 128: ["KS/2026-451"],
                      129: ["KS/2026-102"], 131: ["KS/2026-104"]}


def test_fullmaktiges_kungorelse_och_handlingar():
    kungorelse = fl.las(KALLELSER / "kf-2026-10-26-1315-kungorelse.pdf", "KF")
    assert kungorelse.status == "last"
    assert len(kungorelse.punkter) == 15 and dnr(kungorelse) == {}  # bara tabellen
    handlingar = fl.las(KALLELSER / "kf-2026-10-26-1315-handlingar-foredragningslista.pdf", "KF")
    assert handlingar.status == "last", handlingar.fel
    assert dnr(handlingar) == {150: ["KS/2026-451"], 151: ["KS/2026-270"], 152: ["KS/2026-340"],
                               153: ["MNP/2026-5"], 154: ["KS/2026-504"]}


def test_namnderna_utan_sidhuvud_med_bilagor_emellan():
    sam = fl.las(KALLELSER / "sam-2026-10-29-urval.pdf", "SAM")
    assert sam.status == "last", sam.fel
    # Tabellens rader 128–135 har rubrikerna för sig i textutvinningen.
    per_nr = {p.paragraf: p for p in sam.punkter}
    assert per_nr[129].tabellrubrik == "Tillsyn- olovlig åtgärd, startat utan starbesked"
    assert per_nr[135].tabellrubrik == "Indexuppräkning av taxor 2027"
    assert dnr(sam) == {124: ["SAM/2026-111"], 125: ["SAM/2026-180"], 126: ["SAM/2026-182"]}
    assert (per_nr[125].sida, per_nr[126].sida) == (8, 9)
    soc = fl.las(KALLELSER / "soc-2026-10-29-urval.pdf", "SOC")
    assert dnr(soc) == {105: ["SOC/2026-113"], 106: ["SOC/2026-136"]}


def test_tabell_utan_kolumnen_sida():
    f = fl.las(KALLELSER / "skol-2026-09-03-urval.pdf", "SKOL")
    assert f.status == "last", f.fel
    per_nr = {p.paragraf: p for p in f.punkter}
    assert list(per_nr) == list(range(69, 95))
    assert per_nr[72].tabellrubrik == "Information om skolinspektionens beslut gällande introduktionsprogrammen"
    assert per_nr[94].tabellrubrik == "Ärenden för kännedom"
    assert dnr(f) == {72: ["SKN/2026-474"]}  # sidorna 2–6 finns i fixturen


def test_bara_tjansteskrivelser():
    soc = fl.las(KALLELSER / "soc-2026-09-24-urval.pdf", "SOC")
    assert soc.status == "last", soc.fel
    per_nr = {p.paragraf: p for p in soc.punkter}
    # Layoutläget håller ihop orden som standardläget bryter.
    assert per_nr[92].tabellrubrik == "Val av justerare"
    assert per_nr[97].tabellrubrik == "Svar på remiss angående motion - Införande av elektronisk körjournal"
    assert dnr(soc) == {95: ["SOC/2026-189"], 96: ["SOC/2026-190"], 97: ["SOC/2026-191"]}
    assert (per_nr[95].sida, per_nr[95].rubrik) == (2, "Delårsrapport 2026")
    sam = fl.las(KALLELSER / "sam-2026-09-24-urval.pdf", "SAM")
    assert dnr(sam) == {97: ["SAM/2026-146"], 100: ["SAM-2026-2266"]}
    # Tabellen fortsätter på sidan 3, och hålltiderna efter den hör inte dit.
    per_nr = {p.paragraf: p for p in sam.punkter}
    assert per_nr[121].tabellrubrik == "Eventuellt tillkommande ärende"
    assert per_nr[120].tabellrubrik == "Ärenden för kännedom samhällsnämnden 2026"


def test_diarienummer_i_andra_former():
    assert fl.diarienummer("KS", "KS", " ", "2025", "000475") == "2025-000475"  # som i protokollen
    assert fl.diarienummer("SOC", "KS", " ", "2025", "000475") == "KS/2025-000475"
    assert fl.diarienummer("SKOL", "SKN", " ", "2026", "717") == "2026-717"
    assert fl.diarienummer("SAM", "SAM", "-", "2026", "2266") == "SAM-2026-2266"
    assert fl.las(b"inte en pdf", "KS").status == "fel"


# Komplettering och visning (söm 1)


class Kalla:
    """Skolnämndens protokoll 2026-10-01 och kallelsen, med föredragningslistan ur fixturen."""

    id = "test-skolnamnden"
    titel = "Skolnämnden (test)"
    url = "https://harnosand.se"
    anrop_per_sekund = None

    def __init__(self, kallelse: Path = KALLELSER / "skol-2026-10-01-foredragningslista.pdf") -> None:
        self.kallelse = kallelse

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        h = Hamtning()
        h.dokument.append(Dokument("https://harnosand.se/download/x/Protokoll Skolnämnden 2026-10-01.pdf",
                                   "Protokoll Skolnämnden 2026-10-01.pdf", "protokoll", "SKOL",
                                   (PROTOKOLL / "skol-2026-10-01.pdf").read_bytes()))
        h.kallelser.append(Kallelse("SKOL", date(2026, 10, 1), None, "kallelse",
                                    "Kallelse skolnämnden 2026-10-01, med bilagor", SKOL_URL, 17_400_000,
                                    foredragningslista=fl.las(self.kallelse, "SKOL")))
        return h


@pytest.fixture
def api(database_url, google) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[Kalla()], anonym_lasning=True))
    kor(a)
    a.post("/api/auth/logga-ut")
    return a


def skol(api: TestClient) -> int:
    [s] = [s for s in api.get("/api/sammantraden?organ=SKOL").json() if s["datum"] == "2026-10-01"]
    return s["id"]


def test_behandlingen_far_diarienumret_ur_kallelsen(api):
    s = skol(api)
    b = api.get(f"/api/sammantraden/{s}/behandlingar/105").json()
    assert b["rubrik"] == "Svar på motion om kontinuitet i allmän förskola"
    assert b["diarienummer"] == ["SKN/2026-717"]
    assert b["diarienummer_kallelse"] == {
        "titel": "Kallelse skolnämnden 2026-10-01, med bilagor", "typ": "kallelse", "sida": 13,
        "url": f"{SKOL_URL}#page=13"}
    sammantrade = api.get(f"/api/sammantraden/{s}").json()
    per_nr = {x["paragraf"]: x for x in sammantrade["behandlingar"]}
    assert {p: x["diarienummer"] for p, x in per_nr.items() if x["diarienummer"]} == {
        99: ["SKN/2026-738"], 100: ["SKN/2026-737"], 101: ["SKN/2026-736"], 102: ["SKN/2026-294"],
        104: ["SKN/2026-734"], 105: ["SKN/2026-717"], 106: ["SKN/2026-202"]}
    assert per_nr[96]["diarienummer_kallelse"] is None
    # Alla punkter i föredragningslistan paras ihop med protokollets paragrafer.
    assert [a for a in sammantrade["avvikelser"] if a["lank"]] == []
    # Sökningen hittar kallelsens diarienummer.
    [t] = api.get("/api/behandlingar", params={"q": "SKN/2026-717"}).json()["traffar"]
    assert (t["paragraf"], t["diarienummer_ur_kallelsen"]) == (105, True)


def test_protokollet_och_rattelsen_gar_fore_kallelsen(api, database_url):
    s = skol(api)
    with db.connect(database_url) as conn:
        conn.execute("UPDATE behandling SET diarienummer = '{SKN/2026-999}' WHERE sammantrade_id = %s AND paragraf = 104",
                     (s,))
        kallelsepunkter.komplettera(conn)
        conn.commit()
    b = api.get(f"/api/sammantraden/{s}/behandlingar/104").json()
    assert (b["diarienummer"], b["diarienummer_kallelse"]) == (["SKN/2026-999"], None)

    publicerad(api, sammantrade_id=s, objekt="behandling", paragraf=105, falt="diarienummer",
               nytt=["SKN/2026-718"], motivering="Fel nummer i kallelsen")
    b = api.get(f"/api/sammantraden/{s}/behandlingar/105").json()
    assert b["diarienummer"] == ["SKN/2026-718"]
    assert b["diarienummer_kallelse"] is None
    # Rättelsen visar kallelsens nummer som det ursprungliga.
    assert b["rattelser"]["diarienummer"]["ursprungligt"] == ["SKN/2026-717"]


def test_kopplingarna_anvander_kallelsens_diarienummer(api, database_url):
    s = skol(api)
    with db.connect(database_url) as conn:
        # Ett senare sammanträde i kommunstyrelsen med samma nummer, också det bara i kallelsen.
        dokument_id = conn.execute("SELECT dokument_id FROM sammantrade WHERE id = %s", (s,)).fetchone()["dokument_id"]
        ks = conn.execute(
            "INSERT INTO sammantrade (organ, nyckel, datum, dokument_id, tolkning, tolkad) "
            "VALUES ('KS', '2026-10-20', '2026-10-20', %s, 'tolkad', now()) RETURNING id", (dokument_id,)
        ).fetchone()["id"]
        conn.execute("INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik) VALUES "
                     "(%s, 0, 150, 'Svar på motion om kontinuitet i allmän förskola')", (ks,))
        kallelse_id = conn.execute(
            "INSERT INTO kallelse (organ, datum, typ, titel, url, forst_sedd, senast_sedd) VALUES "
            "('KS', '2026-10-20', 'handlingar', 'Handlingar kommunstyrelsen 2026-10-20', 'https://x/ks.pdf', now(), now()) "
            "RETURNING id").fetchone()["id"]
        kallelsepunkter.lagra_punkter(conn, kallelse_id, fl.Foredragningslista("last", (
            fl.Punkt(140, "Motion om kontinuitet i allmän förskola", ("SKN/2026-717",), 5),)), datetime.now(timezone.utc))
        assert kallelsepunkter.komplettera(conn) == 1
        koppla(conn)
        conn.commit()
    arende = api.get(f"/api/sammantraden/{s}/behandlingar/105").json()["arende"]
    a = api.get(f"/api/arenden/{arende['id']}").json()
    assert [(b["sammantrade"]["organ"]["id"], b["paragraf"]) for b in a["behandlingar"]] == [("SKOL", 105), ("KS", 150)]
    assert [(k["grund"], k["underlag"]) for k in a["kopplingar"]] == [("diarienummer", "SKN/2026-717")]
    assert all(b["diarienummer_kallelse"] for b in a["behandlingar"])


def med_andrade_punkter(database_url, andra) -> None:
    """Skolnämndens föredragningslista med punkterna ändrade av `andra(punkt) -> punkt | None`."""
    with db.connect(database_url) as conn:
        [kallelse_id] = [r["id"] for r in conn.execute("SELECT id FROM kallelse")]
        f = fl.las(KALLELSER / "skol-2026-10-01-foredragningslista.pdf", "SKOL")
        punkter = tuple(x for x in map(andra, f.punkter) if x is not None)
        kallelsepunkter.lagra_punkter(conn, kallelse_id, fl.Foredragningslista("last", punkter), datetime.now(timezone.utc))
        kallelsepunkter.komplettera(conn)
        conn.commit()


def kallelsens_avvikelser(api, s: int) -> list[dict]:
    return [a for a in api.get(f"/api/sammantraden/{s}").json()["avvikelser"] if a["lank"]]


def test_en_punkt_som_inte_behandlas_ger_en_avvikelse_med_lank_till_kallelsen(api, database_url):
    s = skol(api)
    med_andrade_punkter(database_url, lambda p: p if p.paragraf != 105 else fl.Punkt(
        105, "Uppföljning av kostverksamheten", p.diarienummer, p.sida, "Uppföljning av kostverksamheten"))
    b = api.get(f"/api/sammantraden/{s}/behandlingar/105").json()
    assert (b["diarienummer"], b["diarienummer_kallelse"]) == ([], None)
    # Kallelsens paragrafnummer är preliminärt och anges inte. Sidan anges i stället (#121).
    [a] = kallelsens_avvikelser(api, s)
    assert a == {
        "text": 'Kallelse skolnämnden 2026-10-01, med bilagor, sidan 13: punkten "Uppföljning av kostverksamheten" '
                "(SKN/2026-717) behandlas inte i protokollet. Den kan ha strukits från dagordningen eller "
                "flyttats till ett annat sammanträde.",
        "lank": {"titel": "Kallelse skolnämnden 2026-10-01, med bilagor", "url": f"{SKOL_URL}#page=13", "sida": 13},
    }
    assert "§" not in a["text"]
    assert avvikelser.kategori(a) == avvikelser.kategori(a["text"]) == "kallelsen"
    assert "kallelsen" not in avvikelser.I_PROTOKOLLET
    logga_in(api, "lasare")
    lista = api.get("/api/avvikelser", params={"fran": 2026, "till": 2026}).json()
    [rad] = [x for x in lista["sammantraden"] if x["sammantrade"]["id"] == s]
    assert a | {"kategori": "kallelsen"} in rad["avvikelser"]


def test_en_punkt_utan_diarienummer_som_inte_behandlas_ger_ocksa_en_avvikelse(api, database_url):
    s = skol(api)
    med_andrade_punkter(database_url, lambda p: p if p.paragraf != 96 else fl.Punkt(
        96, "Information om lokalförsörjningen", (), None, "Information om lokalförsörjningen"))
    # Utan sida länkas kallelsen som helhet.
    assert kallelsens_avvikelser(api, s) == [{
        "text": 'Kallelse skolnämnden 2026-10-01, med bilagor: punkten "Information om lokalförsörjningen" '
                "behandlas inte i protokollet. Den kan ha strukits från dagordningen eller flyttats till ett "
                "annat sammanträde.",
        "lank": {"titel": "Kallelse skolnämnden 2026-10-01, med bilagor", "url": SKOL_URL, "sida": None},
    }]


def test_formalia_och_punkter_utan_rubrik_ger_ingen_avvikelse(api, database_url):
    s = skol(api)
    extra = (fl.Punkt(108, "", (), None), fl.Punkt(109, "Eventuellt tillkommande ärende", (), 16, "Eventuellt tillkommande ärende"),
             fl.Punkt(110, "Ärenden för kännedom", (), None, "Extra ärenden"))
    with db.connect(database_url) as conn:
        [kallelse_id] = [r["id"] for r in conn.execute("SELECT id FROM kallelse")]
        f = fl.las(KALLELSER / "skol-2026-10-01-foredragningslista.pdf", "SKOL")
        kallelsepunkter.lagra_punkter(conn, kallelse_id, fl.Foredragningslista("last", f.punkter + extra),
                                      datetime.now(timezone.utc))
        kallelsepunkter.komplettera(conn)
        conn.commit()
    assert kallelsens_avvikelser(api, s) == []


def test_en_kallelse_som_bara_delvis_kunde_lasas_ger_en_avvikelse(api, database_url):
    s = skol(api)
    with db.connect(database_url) as conn:
        [kallelse_id] = [r["id"] for r in conn.execute("SELECT id FROM kallelse")]
        f = fl.las(KALLELSER / "skol-2026-10-01-foredragningslista.pdf", "SKOL")
        kallelsepunkter.lagra_punkter(conn, kallelse_id, fl.Foredragningslista(
            "delvis_fel", f.punkter, ("Sidan 14 i föredragningslistan hittades inte",)), datetime.now(timezone.utc))
        kallelsepunkter.komplettera(conn)
        conn.commit()
    avv = api.get(f"/api/sammantraden/{s}").json()["avvikelser"]
    assert {"text": "Kallelse skolnämnden 2026-10-01, med bilagor: kunde bara delvis läsas "
                    "(Sidan 14 i föredragningslistan hittades inte)",
            "lank": {"titel": "Kallelse skolnämnden 2026-10-01, med bilagor", "url": SKOL_URL, "sida": None}} in avv
    # Det som kunde läsas används ändå.
    assert api.get(f"/api/sammantraden/{s}/behandlingar/105").json()["diarienummer"] == ["SKN/2026-717"]


def test_avvikelser_sparade_som_strangar_far_formen_text_och_lank():
    assert avvikelser.objekt("Inga behandlingar hittades") == {"text": "Inga behandlingar hittades", "lank": None}
    # Kallelsens avvikelser före #121 kategoriseras som förut.
    assert avvikelser.kategori("Handlingar kommunstyrelsen 2026-09-29: diarienumret KS/2026-102 "
                               "(§ 129 Kommunstyrelsens uppdragsbeslut 2026) liknar ingen paragraf i protokollet") == "kallelsen"


def test_sidor_som_saknas_i_foredragningslistan_ger_delvis_fel(tmp_path):
    from pypdf import PdfReader, PdfWriter

    w = PdfWriter()
    for i, sida in enumerate(PdfReader(KALLELSER / "skol-2026-10-01-foredragningslista.pdf").pages):
        if i + 1 != 13:
            w.add_page(sida)
    fil = tmp_path / "utan-sidan-13.pdf"
    with fil.open("wb") as f:
        w.write(f)
    f = fl.las(fil, "SKOL")
    assert f.status == "delvis_fel"
    assert f.fel == ("Sidan 13 i föredragningslistan hittades inte",)
    assert 105 not in dnr(f) and dnr(f)[104] == ["SKN/2026-734"]


def test_olasbar_text_ger_fel_och_en_avvikelse(api, database_url):
    # Kommunstyrelsen 2026-02-24: typsnittet saknar teckentabell, så texten är bara glyfkoder.
    f = fl.las(KALLELSER / "ks-2026-02-24-olasbar.pdf", "KS")
    assert f.status == "fel"
    assert f.fel == ("texten går inte att läsa, typsnittet saknar teckentabell",)
    s = skol(api)
    with db.connect(database_url) as conn:
        [kallelse_id] = [r["id"] for r in conn.execute("SELECT id FROM kallelse")]
        kallelsepunkter.lagra_punkter(conn, kallelse_id, f, datetime.now(timezone.utc))
        kallelsepunkter.komplettera(conn)
        conn.commit()
    avv = api.get(f"/api/sammantraden/{s}").json()["avvikelser"]
    assert {"text": "Kallelse skolnämnden 2026-10-01, med bilagor: kunde inte läsas "
                    "(texten går inte att läsa, typsnittet saknar teckentabell)",
            "lank": {"titel": "Kallelse skolnämnden 2026-10-01, med bilagor", "url": SKOL_URL, "sida": None}} in avv


def test_migreringen_slar_in_sparade_strangar(api, database_url):
    s = skol(api)
    sql = (Path(kallelsepunkter.__file__).parent / "migrations" / "0031_kallelseavvikelser_med_lank.sql").read_text("utf-8")
    with db.connect(database_url) as conn:
        conn.execute("UPDATE sammantrade SET kallelse_avvikelser = '[\"a\", \"b\"]' WHERE id = %s", (s,))
        conn.execute(sql)
        assert conn.execute("SELECT kallelse_avvikelser FROM sammantrade WHERE id = %s", (s,)).fetchone()[
            "kallelse_avvikelser"] == [{"text": "a", "lank": None}, {"text": "b", "lank": None}]
