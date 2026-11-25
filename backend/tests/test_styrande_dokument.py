"""Kommunens styrande dokument (#63): insamling, versioner, dokumentinformation, giltighet, beslut och sök.

Söm 1: sidan Kommunens styrande dokument och en PDF per rubrik är inspelade 2026-11-25 (STYRANDE_URVAL=1), och det
gemensamma reglementet för kommunstyrelse och nämnder med. Testerna som behöver andra länkar serverar en egen sida
med länkar till de inspelade filerna (`Sida`).

Fallen för igenkänningen kommer från en jämförelse med en arkiverad kopia av sidan från 2024: samhällsnämndens
delegationsordning behöll sitt id och fick en ny tidsstämpel, och det gemensamma reglementet fick ett nytt id med samma
filnamn.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient

from app import db, styrande_dokument
from app.recorded import InspeladTransport
from app.sources.styrande_dokument import SIDA, StyrandeDokument, lankar_pa_sidan

KALLA = "harnosand-styrande-dokument"
SIDNYCKEL = "harnosand.se/kommun--styrning/forvaltning-och-organisation/kommunens-styrande-dokument.html"
GEMENSAMT = ("https://harnosand.se/download/18.580e43d7163221b2781b73fe/1758202788908/"
             "Gemensamt%20reglemente%20f%C3%B6r%20kommunstyrelse%20och%20n%C3%A4mnder%20i%20H%C3%A4rn%C3%B6sands%20kommun.pdf")
# Samma fil 2024, med ett annat id (Wayback Machine).
GEMENSAMT_2024 = ("https://harnosand.se/download/18.433ad436192ebf697ee972cf/1730713223569/"
                  "Gemensamt%20reglemente%20f%C3%B6r%20kommunstyrelse%20och%20n%C3%A4mnder%20i%20H%C3%A4rn%C3%B6sands%20kommun.pdf")
SAMHALLSNAMNDEN = ("https://harnosand.se/download/18.4b6c551c1679dec5d0a4a691/1775042169645/"
                   "Delegationsordning%20f%C3%B6r%20samh%C3%A4llsn%C3%A4mnden.pdf")
# Samma id 2024, med en äldre tidsstämpel.
SAMHALLSNAMNDEN_2024 = ("https://harnosand.se/download/18.4b6c551c1679dec5d0a4a691/1730125211592/"
                        "Delegationsordning%20f%C3%B6r%20samh%C3%A4llsn%C3%A4mnden.pdf")
ATTEST = "https://harnosand.se/download/18.580e43d7163221b2781b73fc/1711620649711/Attestreglemente.pdf"
REGLEMENTEN = "Reglementen, ägardirektiv och bolagsordning"


def inspelad(url: str) -> bytes:
    t = InspeladTransport(INSPELNINGAR)
    return t.handle_request(httpx.Request("GET", url)).content


class Sida(httpx.BaseTransport):
    """Inspelningarna, med en egen sida av styrande dokument och egna filer för vissa adresser."""

    def __init__(self, rubriker: dict[str, list[str]], filer: dict[str, bytes] | None = None) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.filer = filer or {}
        self.satt(rubriker)
        self.hamtade: list[str] = []

    def satt(self, rubriker: dict[str, list[str]]) -> None:
        delar = []
        for rubrik, urler in rubriker.items():
            delar.append(f"<h2>{rubrik}</h2><ul>")
            delar += [f'<li><a href="{u.removeprefix("https://harnosand.se")}">fil</a></li>' for u in urler]
            delar.append("</ul>")
        self.html = f"<html><body>{''.join(delar)}<h2>Kontakt och service</h2></body></html>"

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        nyckel = f"{request.url.host}{request.url.path}"
        if nyckel == SIDNYCKEL:
            return httpx.Response(200, text=self.html, request=request)
        self.hamtade.append(str(request.url))
        for url, innehall in self.filer.items():
            if httpx.URL(url) == request.url:
                return httpx.Response(200, content=innehall, request=request)
        return self.inspelad.handle_request(request)


def app_med(database_url: str, google, transport: httpx.BaseTransport | None = None,
            urval: int | None = None) -> TestClient:
    a = TestClient(skapa_app(database_url, google, kallor=[StyrandeDokument(urval=urval, anrop_per_sekund=None)],
                             transport=transport, anonym_lasning=True))
    assert a.post("/api/auth/test/redaktor").status_code == 200
    return a


def kor(api: TestClient) -> dict:
    svar = api.post("/api/insamlingar", params={"kalla": KALLA})
    assert svar.status_code == 200, svar.text
    return svar.json()["kallor"][0]


def dokument(api: TestClient, titel: str) -> dict:
    [d] = [d for d in api.get("/api/styrande-dokument").json()["dokument"] if d["titel"] == titel]
    return api.get(f"/api/styrande-dokument/{d['id']}").json()


# Sidan

def test_sidan_har_tio_rubriker_och_138_dokument_och_en_fil_under_tva_rubriker():
    sida = (INSPELNINGAR / InspeladTransport(INSPELNINGAR).manifest[SIDNYCKEL]).read_text(encoding="utf-8")
    lankar, rubriker = lankar_pa_sidan(sida)
    assert rubriker == ["Övergripande visioner och mål", "Föreskrifter", REGLEMENTEN, "Bolagsordning / Ägardirektiv",
                        "Policy", "Plan", "Program", "Riktlinjer - rutiner", "Delegationer", "Dokumenthanteringsplaner"]
    assert len(lankar) == 138
    [renhallning] = [l for l in lankar if l.titel.startswith("Renhållningsordning")]
    assert renhallning.kategorier == ("Föreskrifter", "Plan")
    assert renhallning.sitevision_id == "18.580e43d7163221b2781b71a3"
    assert renhallning.tidsstampel == 1663679757842
    # Filnamnen är i NFC, som de visas.
    assert any(l.titel == "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun" for l in lankar)
    # Urvalet för inspelningarna: den första länken under varje rubrik.
    assert len(lankar_pa_sidan(sida, urval=1)[0]) == 10


def test_insamlingen_lagrar_dokumenten_med_kategori_och_kalla(database_url, google):
    api = app_med(database_url, google, urval=1)
    res = kor(api)
    assert (res["status"], res["antal_nya"]) == ("lyckad", 10)
    lista = api.get("/api/styrande-dokument").json()
    assert len(lista["dokument"]) == 10
    assert lista["kategorier"][0] == "Övergripande visioner och mål"
    assert lista["kalla"]["url"] == SIDA and lista["kalla"]["kontrollerad"]
    attest = next(d for d in lista["dokument"] if d["titel"] == "Attestreglemente")
    assert attest["kategorier"] == [REGLEMENTEN]
    assert attest["faststallt"] == {"text": "Kommunfullmäktige", "organ": {"id": "KF", "namn": "Kommunfullmäktige"},
                                    "datum": "2019-01-31"}
    # Datakällan står på statussidan.
    assert any(k["id"] == KALLA for k in api.get("/api/datakallor").json())
    # En andra kontroll hämtar inga filer igen och ändrar inget.
    res = kor(api)
    assert (res["status"], res["antal_oforandrade"]) == ("inga_nya", 10)


# Dokumentinformation

def test_dokumentinformationen_i_det_gemensamma_reglementet(database_url, google):
    api = app_med(database_url, google, Sida({REGLEMENTEN: [ATTEST, GEMENSAMT]}))
    kor(api)
    d = dokument(api, "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun")
    info = d["dokumentinformation"]
    assert info["ruta"] is True
    assert info["dokumenttyp"] == "Reglemente"
    assert info["faststalld_av"] == "Kommunfullmäktige"
    assert info["datum"] == "2024-04-03"
    assert info["diarienummer"] == "KS 2022/415"
    assert info["version"] == "1.2"
    assert info["senast_reviderad"] == "2025-05-26"
    assert info["giltig_tom"] == "Tillsvidare"
    assert info["galler_for"] == "Alla kommunens nämnder samt kommunstyrelsen"
    assert d["galler_fran"] == "2025-07-01"
    assert d["giltighet"]["status"] == "gallande"
    assert d["giltighet"]["kalla"] == "dokumentinformationen"
    assert d["versioner"][0]["kommunens_url"] == GEMENSAMT
    assert d["versioner"][0]["sidor"] > 10


def test_ett_dokument_utan_ruta_har_alla_falt_saknade():
    info = styrande_dokument.las_dokumentinformation(
        "Granskningsgrupper 2023-2026 Områdesbevakning av de olika nämndernas verksamhetsområden")
    assert info["ruta"] is False
    assert all(info[n] is None for n, _ in styrande_dokument.FALT)


def test_falt_som_saknas_i_rutan_och_etiketter_over_flera_rader():
    # Ur skolnämndens delegationsordning (ingen version) och attestreglementet ("Senast" och "reviderad" på två rader).
    info = styrande_dokument.las_dokumentinformation(
        "Dokumentnamn Skolnämndens delegationsordning 2026\nDokumenttyp\nStyrande\nFastställd/upprättad av Skolnämnden\n"
        "Datum\n2026-02-05\nDiarienummer\n2026–000042\nDokumentansvarig/processägare Skolförvaltningen\nSenast\n"
        "reviderad\n2026-01-20\nGiltig t o m\n2027-12-31\n")
    assert info["version"] is None
    assert info["senast_reviderad"] == "2026-01-20"
    assert info["giltig_tom"] == "2027-12-31"
    assert info["dokumentinformation"] is None
    assert styrande_dokument.normalisera_diarienummer(info["diarienummer"], "SKOL") == ("SKOL", 2026, 42)


def test_den_aldre_mallen_for_rutan():
    # Ur Allmänna ordningsföreskrifter (1999): "Fastställd av", "Dokumentansvarig" och "Övrig Information".
    info = styrande_dokument.las_dokumentinformation(
        "Dokumentnamn Allmänna lokala ordningsföreskrifter Dokumenttyp \nFöreskrift \nFastställd av Kommunfullmäktige "
        "Datum \n1999-04-12 \nDiarienummer \nKS15-63-003 \nDokumentansvarig Samhällsnämnden Version \n1:6 \n"
        "Senast reviderad \n2020-09-28 § 58 \nGiltig t o m \ntills vidare \nDokumentinformation Fastställd av "
        "kommunfullmäktige 1999-04-12, § 71 \nDokumentet gäller för Härnösands kommun. Övrig Information")
    assert info["dokumenttyp"] == "Föreskrift"
    assert info["faststalld_av"] == "Kommunfullmäktige"
    assert info["diarienummer"] == "KS15-63-003"
    assert info["dokumentansvarig"] == "Samhällsnämnden"
    assert info["dokumentinformation"] == "Fastställd av kommunfullmäktige 1999-04-12, § 71"
    assert info["galler_for"] == "Härnösands kommun."
    assert info["annan_information"] is None
    assert styrande_dokument.giltighet("Allmänna ordningsföreskrifter", info, None, IDAG)["status"] == "gallande"


# Giltighet

IDAG = date(2026, 11, 25)


@pytest.mark.parametrize("titel, tom, idag, status, kalla", [
    ("Reglemente", "2024-12-31", IDAG, "utganget", "dokumentinformationen"),
    ("Reglemente", "20241231", IDAG, "utganget", "dokumentinformationen"),
    ("Reglemente", "2027-03-31", IDAG, "gallande", "dokumentinformationen"),
    ("Reglemente", "Tillsvidare", IDAG, "gallande", "dokumentinformationen"),
    ("Reglemente", "Tills vidare", IDAG, "gallande", "dokumentinformationen"),
    ("Klimat-energiplan-2017-2020-antagen", None, IDAG, "utganget", "titeln"),
    ("Granskningsgrupper 2023-2026", None, IDAG, "gallande", "titeln"),
    ("Granskningsgrupper 2023-2026", None, date(2027, 1, 1), "utganget", "titeln"),
    ("Biblioteksplan 2023 – 2027 Härnösands kommun", None, IDAG, "gallande", "titeln"),
    # "Giltig t o m" går före perioden i titeln.
    ("Bostadsförsörjningsprogram 2017-2022", "2030-12-31", IDAG, "gallande", "dokumentinformationen"),
    # Ett datum i titeln är ingen period.
    ("2021-06-17, Delegationsordning (konsoliderad version)", None, IDAG, "gallande", None),
    ("Attestreglemente", None, IDAG, "gallande", None),
])
def test_giltighet(titel, tom, idag, status, kalla):
    g = styrande_dokument.giltighet(titel, {"giltig_tom": tom}, None, idag)
    assert (g["status"], g["kalla"]) == (status, kalla)
    if status == "utganget":
        assert g["text"].endswith("Dokumentet ligger kvar på kommunens sida.")


def test_borttaget_gar_fore_allt_annat():
    g = styrande_dokument.giltighet("Plan 2030-2040", {"giltig_tom": "2099-01-01"}, date(2026, 11, 1), IDAG)
    assert (g["status"], g["borttagen"]) == ("borttaget", "2026-11-01")


@pytest.mark.parametrize("dnr, organ, vantat", [
    ("KS 2022/415", "KF", ("KS", 2022, 415)),
    ("KS/2022-415", "KF", ("KS", 2022, 415)),
    ("KS2023-470", "KF", ("KS", 2023, 470)),
    ("2022-000209", "KF", ("KS", 2022, 209)),
    ("SAM 2025-000041", "SAM", ("SAM", 2025, 41)),
    ("KS 15-182-001", "KF", None),
    (None, "KF", None),
])
def test_diarienummer_normaliseras(dnr, organ, vantat):
    assert styrande_dokument.normalisera_diarienummer(dnr, organ) == vantat


# Igenkänning och versioner

def test_samma_id_med_ny_tidsstampel_ar_en_ny_version(database_url, google):
    sida = Sida({"Delegationer": [SAMHALLSNAMNDEN_2024]}, {SAMHALLSNAMNDEN_2024: inspelad(ATTEST)})
    api = app_med(database_url, google, sida)
    kor(api)
    [forsta] = api.get("/api/styrande-dokument").json()["dokument"]
    sida.satt({"Delegationer": [SAMHALLSNAMNDEN]})
    res = kor(api)
    assert (res["antal_nya"], res["antal_andrade"]) == (0, 1)
    [d] = api.get("/api/styrande-dokument").json()["dokument"]
    assert d["id"] == forsta["id"]
    sidan = api.get(f"/api/styrande-dokument/{d['id']}").json()
    nu, tidigare = sidan["versioner"]
    assert (nu["version"], nu["ersatt"], nu["kommunens_url"]) == (2, None, SAMHALLSNAMNDEN)
    assert tidigare["version"] == 1 and tidigare["ersatt"] and tidigare["kommunens_url"] == SAMHALLSNAMNDEN_2024
    # Den tidigare versionen finns kvar som plattformens kopia.
    kopia = api.get(tidigare["kopia"])
    assert kopia.status_code == 200 and kopia.content == inspelad(ATTEST)
    assert sidan["dokumentinformation"]["faststalld_av"] == "Samhällsnämnden"


def test_nytt_id_med_samma_filnamn_i_samma_kategori_ar_en_ny_version(database_url, google):
    sida = Sida({REGLEMENTEN: [GEMENSAMT_2024]}, {GEMENSAMT_2024: inspelad(ATTEST)})
    api = app_med(database_url, google, sida)
    kor(api)
    [forsta] = api.get("/api/styrande-dokument").json()["dokument"]
    sida.satt({REGLEMENTEN: [GEMENSAMT]})
    res = kor(api)
    assert (res["antal_nya"], res["antal_andrade"]) == (0, 1)
    [d] = api.get("/api/styrande-dokument").json()["dokument"]
    assert d["id"] == forsta["id"] and d["giltighet"]["status"] == "gallande"
    assert [v["kommunens_url"] for v in api.get(f"/api/styrande-dokument/{d['id']}").json()["versioner"]] == [
        GEMENSAMT, GEMENSAMT_2024]


def test_nytt_id_i_en_annan_kategori_ar_ett_nytt_dokument(database_url, google):
    sida = Sida({REGLEMENTEN: [GEMENSAMT_2024]}, {GEMENSAMT_2024: inspelad(ATTEST)})
    api = app_med(database_url, google, sida)
    kor(api)
    sida.satt({"Policy": [GEMENSAMT]})
    res = kor(api)
    assert (res["antal_nya"], res["antal_andrade"]) == (1, 1)  # ett nytt, ett borttaget
    statusar = sorted(d["giltighet"]["status"] for d in api.get("/api/styrande-dokument").json()["dokument"])
    assert statusar == ["borttaget", "gallande"]


def test_en_oforandrad_fil_hamtas_inte_igen(database_url, google):
    sida = Sida({REGLEMENTEN: [ATTEST]})
    api = app_med(database_url, google, sida)
    kor(api)
    sida.hamtade.clear()
    assert kor(api)["status"] == "inga_nya"
    assert sida.hamtade == []


def test_ett_borttaget_dokument_marks_med_datum_och_finns_kvar(database_url, google, monkeypatch):
    monkeypatch.setenv("KOMMUNKOLLEN_IDAG", "2026-11-25")
    sida = Sida({REGLEMENTEN: [ATTEST, GEMENSAMT]})
    api = app_med(database_url, google, sida)
    kor(api)
    assert api.get("/api/sok", params={"q": "attestreglemente", "typ": "styrande_dokument"}).json()["antal"] > 0
    sida.satt({REGLEMENTEN: [GEMENSAMT]})
    assert kor(api)["antal_andrade"] == 1
    d = dokument(api, "Attestreglemente")
    assert d["borttagen"] == "2026-11-25"
    assert d["giltighet"] == {"status": "borttaget", "kalla": None, "till": None, "borttagen": "2026-11-25",
                              "text": "Borttaget från kommunens sida 2026-11-25."}
    assert api.get(d["versioner"][0]["kopia"]).status_code == 200
    # Ett borttaget dokument försvinner ur sökningen.
    traffar = api.get("/api/sok", params={"q": "attestreglemente", "typ": "styrande_dokument"}).json()["traffar"]
    assert all("Attestreglemente" not in t["rubrik"] for t in traffar)
    # Kommer det tillbaka är det inte längre borttaget.
    sida.satt({REGLEMENTEN: [ATTEST, GEMENSAMT]})
    kor(api)
    assert dokument(api, "Attestreglemente")["borttagen"] is None


def test_manga_borttagna_pa_en_gang_ar_en_andrad_sida_och_inget_lagras(database_url, google):
    urler = [f"https://harnosand.se/download/18.{i:024x}/1700000000000/Dokument%20{i}.pdf" for i in range(12)]
    sida = Sida({"Policy": urler}, {u: inspelad(ATTEST) for u in urler})
    api = app_med(database_url, google, sida)
    kor(api)
    sida.satt({"Policy": urler[:1]})
    assert kor(api)["status"] == "misslyckad"
    assert all(d["giltighet"]["status"] != "borttaget" for d in api.get("/api/styrande-dokument").json()["dokument"])


def test_en_sida_utan_lankar_ger_en_misslyckad_kontroll(database_url, google):
    api = app_med(database_url, google, Sida({}))
    assert kor(api)["status"] == "misslyckad"


def test_en_fil_som_inte_gar_att_hamta_ger_delvis_fel_och_forsoks_igen(database_url, google):
    class Trasig(Sida):
        def handle_request(self, request):
            if "Attestreglemente" in str(request.url) and self.trasig:
                return httpx.Response(503, request=request)
            return super().handle_request(request)

    sida = Trasig({REGLEMENTEN: [ATTEST, GEMENSAMT]})
    sida.trasig = True
    api = app_med(database_url, google, sida)
    res = kor(api)
    assert (res["status"], res["antal_nya"]) == ("delvis_fel", 1)
    sida.trasig = False
    res = kor(api)
    assert (res["status"], res["antal_nya"]) == ("lyckad", 1)


# Koppling till beslutet och sök

def test_dokumentet_kopplas_till_behandlingen_med_samma_organ_datum_och_diarienummer(database_url, google):
    api = app_med(database_url, google, Sida({REGLEMENTEN: [GEMENSAMT]}))
    kor(api)
    with db.connect(database_url) as conn:
        sid = conn.execute("INSERT INTO sammantrade (organ, nyckel, datum) VALUES ('KF', '2024-04-03', '2024-04-03') "
                           "RETURNING id").fetchone()["id"]
        annan = conn.execute("INSERT INTO sammantrade (organ, nyckel, datum) VALUES ('KS', '2024-04-03', '2024-04-03') "
                             "RETURNING id").fetchone()["id"]
        for s, p, dnr in ((sid, 31, ["KS/2022-414"]), (sid, 32, ["KS/2022-415"]), (annan, 32, ["KS/2022-415"])):
            conn.execute("INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, diarienummer) "
                         "VALUES (%s, %s, %s, 'Gemensamt reglemente', %s)", (s, p, p, dnr))
        conn.commit()
        assert styrande_dokument.for_behandling(conn, sid, 32) == [
            {"id": api.get("/api/styrande-dokument").json()["dokument"][0]["id"],
             "titel": "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun"}]
        assert styrande_dokument.for_behandling(conn, sid, 31) == []
        assert styrande_dokument.for_behandling(conn, annan, 32) == []
    d = dokument(api, "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun")
    assert d["beslut"] == [{"sammantrade_id": sid, "paragraf": 32, "rubrik": "Gemensamt reglemente",
                            "organ": {"id": "KF", "namn": "Kommunfullmäktige"}, "datum": "2024-04-03",
                            "grund": "samma diarienummer"}]


def test_sidorna_i_den_gallande_versionen_gar_att_soka_fram(database_url, google):
    api = app_med(database_url, google, Sida({REGLEMENTEN: [GEMENSAMT]}))
    kor(api)
    svar = api.get("/api/sok", params={"q": "justering protokoll", "typ": "styrande_dokument"}).json()
    assert svar["antal"] > 0
    t = svar["traffar"][0]
    assert t["typ"] == "styrande_dokument"
    assert t["lank"].startswith("/politik/styrande-dokument/")
    assert t["dokument"].startswith("/api/styrande-dokument/") and "#page=" in t["dokument"]
    assert t["organ"] == {"id": "KF", "namn": "Kommunfullmäktige"}
