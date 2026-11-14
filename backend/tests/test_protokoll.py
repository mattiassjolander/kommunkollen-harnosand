"""Protokoll från kommunfullmäktige: insamling, tolkning och API (#28).

Insamlingen körs mot inspelade svar från harnosand.se: KF:s sida och protokollen för 2026.
De förväntade värdena är kontrollerade för hand mot protokollen.
"""

from __future__ import annotations

import hashlib
import io

import httpx
import psycopg
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.recorded import InspeladTransport

KALLA = "harnosand-protokoll-kf"


def kor(api: TestClient, kalla: str | None = KALLA) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar", params={"kalla": kalla} if kalla else None)
    assert svar.status_code == 200, svar.text
    return svar.json()


def sammantrade(api: TestClient, datum: str, starttid: str | None = None) -> dict:
    lista = api.get("/api/sammantraden", params={"organ": "KF"}).json()
    [s] = [s for s in lista if s["datum"] == datum and (starttid is None or s["starttid"] == starttid)]
    return api.get(f"/api/sammantraden/{s['id']}").json()


def person(s: dict, namn: str) -> dict:
    [p] = [p for p in s["narvaro"] if p["namn"] == namn]
    return p


class MedUtbytta(httpx.BaseTransport):
    """Inspelade svar, men vissa adresser ger annat innehåll."""

    def __init__(self, byten: dict[str, bytes]) -> None:
        self.inspelad = InspeladTransport(INSPELNINGAR)
        self.byten = byten

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for del_av_adress, innehall in self.byten.items():
            if del_av_adress in request.url.path:
                return httpx.Response(200, content=innehall, headers={"content-type": "application/pdf"}, request=request)
        return self.inspelad.handle_request(request)


def tom_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(595, 842)
    ut = io.BytesIO()
    w.write(ut)
    return ut.getvalue()


def test_insamlingen_hamtar_kf_protokollen_som_versionerade_kopior(api):
    korning = kor(api)
    [res] = korning["kallor"]
    assert res["datakalla_id"] == KALLA
    assert res["status"] == "lyckad"
    assert res["antal_nya"] == 8  # paragrafprotokollet "§ 129" på sidan tas inte med här

    lista = api.get("/api/sammantraden", params={"organ": "KF"}).json()
    assert [(s["datum"], s["starttid"]) for s in lista] == [
        ("2026-10-26", "13:15"), ("2026-10-26", "11:10"), ("2026-09-28", "13:15"), ("2026-06-15", "13:15"),
        ("2026-05-25", "13:15"), ("2026-04-27", "13:15"), ("2026-03-23", "13:15"), ("2026-02-23", "13:15"),
    ]
    assert all(s["tolkning"] == "tolkad" for s in lista)
    assert lista[0]["organ"] == {"id": "KF", "namn": "Kommunfullmäktige"}

    # Källan: originalets adress och plattformens kopia, med samma innehåll som originalet.
    p = lista[2]["protokoll"]
    assert p["url"].startswith("https://harnosand.se/download/")
    assert p["filnamn"] == "Protokoll kommunfullmäktige 2026-09-28.pdf"
    assert p["version"] == 1
    assert p["datakalla"]["id"] == KALLA
    kopia = api.get(p["kopia"])
    assert kopia.status_code == 200
    assert kopia.headers["content-type"] == "application/pdf"
    assert hashlib.sha256(kopia.content).hexdigest() == p["sha256"]
    original = httpx.Client(transport=InspeladTransport(INSPELNINGAR)).get(p["url"]).content
    assert kopia.content == original

    # Datakällor visar KF:s protokoll som en egen källa.
    [kf] = [k for k in api.get("/api/datakallor").json() if k["id"] == KALLA]
    assert kf["titel"] == "Härnösands kommun – protokoll, kommunfullmäktige"
    assert kf["status"] == "lyckad"


def test_sammantradet_med_narvaro_tjanstgoring_och_jav(api):
    kor(api)
    s = sammantrade(api, "2026-09-28")
    assert s["plats"] == "Rådhuset - KF-salen"
    assert (s["starttid"], s["sluttid"]) == ("13:15", "16:30")
    assert s["paragrafer"] == [121, 136]
    assert s["avvikelser"] == []

    ordf = person(s, "Monica Fahlén")
    assert (ordf["parti"], ordf["roll"], ordf["kategori"]) == ("S", "Ordförande", "beslutande")
    assert person(s, "Thomas Andersson")["roll"] == "1:e vice ordförande"

    # Partitillhörigheten är den protokollet anger: "(-)" är partilös, utan parentes anges inget parti.
    assert person(s, "Carl-Fredrik Edgren")["parti"] == "-"
    assert person(s, "Hans Rosengren")["parti"] is None

    assert person(s, "Knapp Britta Thyr")["jav"] == [129]
    ersattare = person(s, "Mohamed Abdulwahab Mohamed")
    assert ersattare["roll"] == "Ersättare"
    assert ersattare["tjanstgor_for"] == {"namn": "Knapp Britta Thyr", "parti": "MP"}
    assert ersattare["paragrafer"] == [129]
    assert person(s, "Rune Danielsson")["tjanstgor_for"] == {"namn": "Magnus Oskarsson", "parti": "S"}
    assert person(s, "Rune Danielsson")["paragrafer"] is None
    assert person(s, "Lars Zetterlund")["kategori"] == "ej_tjanstgorande"
    assert person(s, "Jonas Bergström")["kategori"] == "ovrig"


def test_behandlingar_med_rubrik_diarienummer_och_beslut(api):
    kor(api)
    s = sammantrade(api, "2026-09-28")
    assert [b["paragraf"] for b in s["behandlingar"]] == list(range(121, 137))
    b = {b["paragraf"]: b for b in s["behandlingar"]}
    assert b[121]["rubrik"] == "Val av justerare"
    assert b[129]["rubrik"] == "Svar på Hemställan om lånefinansiering för inköp av ombordutrustning"
    assert b[136]["diarienummer"] == ["KS/2026-584"]
    assert b[129]["beslut"].splitlines() == [
        "Kommunfullmäktige beslutar",
        "att godkänna att Kommunalförbundet Kollektivtrafikmyndigheten i Västernorrlands län upptar lån om högst "
        "22 mkr för finansiering av investering i ombordutrustning för biljett- och betalsystem samt realtids- och "
        "trafikledningssystem,",
        "att beslutet gäller under förutsättning att övriga medlemmar beslutar likalydande, samt",
        "att ärendet justeras omedelbart.",
    ]
    assert b[127]["beslut"] == "Ärendet utgår i enlighet med fastställd dagordning."
    # En informationspunkt utan beslut har inget beslut, och det är ingen avvikelse.
    assert b[124]["beslut"] is None

    # Ett protokoll med diarienummer i formen "Dnr 2026-000025".
    feb = {b["paragraf"]: b for b in sammantrade(api, "2026-02-23")["behandlingar"]}
    assert list(feb) == list(range(1, 15))
    assert feb[3]["diarienummer"] == ["2026-000025"]
    assert feb[3]["rubrik"] == "Allmänhetens frågestund i kommunfullmäktige 2026"


def test_beslutande_vid_en_behandling_med_hansyn_till_jav_och_tjanstgoring(api):
    kor(api)
    s = sammantrade(api, "2026-09-28")

    p129 = api.get(f"/api/sammantraden/{s['id']}/behandlingar/129").json()
    beslutande = {p["namn"] for p in p129["beslutande"]}
    assert "Knapp Britta Thyr" not in beslutande  # jäv
    assert "Per-Eric Norberg" not in beslutande  # jäv
    assert {"Mohamed Abdulwahab Mohamed", "Catharina Rosén"} <= beslutande  # tjänstgör vid § 129
    assert {p["namn"] for p in p129["jav"]} == {"Knapp Britta Thyr", "Per-Eric Norberg"}
    assert (p129["foregaende"], p129["nasta"]) == (128, 130)
    assert p129["sammantrade"]["id"] == s["id"]

    p128 = api.get(f"/api/sammantraden/{s['id']}/behandlingar/128").json()
    beslutande = {p["namn"] for p in p128["beslutande"]}
    assert "Knapp Britta Thyr" in beslutande
    assert "Mohamed Abdulwahab Mohamed" not in beslutande
    assert len(p128["beslutande"]) == len(p129["beslutande"])

    assert api.get(f"/api/sammantraden/{s['id']}/behandlingar/999").status_code == 404


def test_narvarolista_pa_egna_sidor(api):
    """Februariprotokollet har närvaron i tabeller: ledamöter med närvaro, ersättare med tjänstgöring."""
    kor(api)
    s = sammantrade(api, "2026-02-23")
    assert person(s, "Nina Skyttberg")["kategori"] == "franvarande"
    molin = person(s, "Lennart Molin")
    assert (molin["kategori"], molin["parti"]) == ("beslutande", "S")
    assert molin["tjanstgor_for"] == {"namn": "Nina Skyttberg", "parti": "S"}
    assert person(s, "Mohamed Abdulwahab")["kategori"] == "ej_tjanstgorande"
    edgren = person(s, "Carl-Fredrik Edgren")
    assert edgren["parti"] == "V"
    assert 7 not in edgren["paragrafer"]

    vid7 = api.get(f"/api/sammantraden/{s['id']}/behandlingar/7").json()
    assert "Carl-Fredrik Edgren" not in {p["namn"] for p in vid7["beslutande"]}


def test_avvikelser_mot_protokollets_egna_uppgifter_redovisas(api):
    kor(api)
    # Protokollet anger §§ 35-54, men innehåller 35–52 (53 är första paragrafen i april).
    s = sammantrade(api, "2026-03-23")
    assert s["tolkning"] == "tolkad"
    assert s["avvikelser"] == ["Paragraferna stämmer inte med protokollets paragrafintervall (saknas: 53, 54)"]


def test_ett_protokoll_som_inte_gar_att_tolka_visas_anda_och_ger_delvis_fel(database_url, google):
    transport = MedUtbytta({"Protokoll kommunfullmäktige 2026-06-15.pdf": tom_pdf()})
    api = TestClient(skapa_app(database_url, google, transport=transport))
    [res] = kor(api)["kallor"]
    assert res["status"] == "delvis_fel"
    assert "Protokoll kommunfullmäktige 2026-06-15.pdf: kunde inte tolkas automatiskt" in res["fel"]
    assert res["antal_nya"] == 8

    lista = api.get("/api/sammantraden").json()
    [ej] = [s for s in lista if s["tolkning"] == "ej_tolkad"]
    assert ej["datum"] == "2026-06-15"  # ur filnamnet
    assert ej["antal_behandlingar"] == 0
    assert ej["protokoll"]["url"].endswith("2026-06-15.pdf")
    assert api.get(ej["protokoll"]["kopia"]).status_code == 200
    assert "PDF:en saknar text (inskannad?)" in api.get(f"/api/sammantraden/{ej['id']}").json()["avvikelser"]
    assert sum(s["tolkning"] == "tolkad" for s in lista) == 7

    [kf] = [k for k in api.get("/api/datakallor").json() if k["id"] == KALLA]
    assert kf["status"] == "delvis_fel"


def test_nytt_innehall_under_samma_adress_blir_en_ny_version(database_url, google):
    api = TestClient(skapa_app(database_url, google))
    kor(api)
    fore = sammantrade(api, "2026-09-28")

    # Oförändrade protokoll: inga nya uppgifter.
    [res] = kor(api)["kallor"]
    assert (res["status"], res["antal_oforandrade"]) == ("inga_nya", 8)

    # Kommunen byter innehållet i filen (här: samma protokoll med en tillagd kommentar).
    url = fore["protokoll"]["url"]
    original = httpx.Client(transport=InspeladTransport(INSPELNINGAR)).get(url).content
    api2 = TestClient(skapa_app(database_url, google,
                                transport=MedUtbytta({"2026-09-28.pdf": original + b"\n%andrad\n"})))
    [res] = kor(api2)["kallor"]
    assert (res["status"], res["antal_andrade"], res["antal_oforandrade"]) == ("lyckad", 1, 7)

    efter = sammantrade(api2, "2026-09-28")
    assert efter["id"] == fore["id"]  # samma sammanträde, så länkar fortsätter att fungera
    assert efter["protokoll"]["version"] == 2
    assert efter["protokoll"]["sha256"] != fore["protokoll"]["sha256"]
    assert efter["behandlingar"] == fore["behandlingar"]
    # Den tidigare versionen finns kvar.
    assert api2.get(fore["protokoll"]["kopia"]).content == original
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM dokument WHERE url = %s", (url,)).fetchone()[0] == 2


def test_lasning_ar_oppen_utan_inloggning(database_url, google):
    api = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    kor(api)
    api.post("/api/auth/logga-ut")
    lista = api.get("/api/sammantraden")
    assert lista.status_code == 200
    assert api.get(f"/api/sammantraden/{lista.json()[0]['id']}").status_code == 200
    assert api.get("/api/organ").json() == [{"id": "KF", "namn": "Kommunfullmäktige"}]
