"""SKR:s skatteunderlagsprognoser (#61).

Söm 1: datakällan läser SKR:s sida (inspelad 2026-11-21) och de fem prognosfilerna för kommuner från
2026, räknar om dem för Härnösand med LibreOffice och sparar varje cirkulär som en egen prognos.
Facit för cirkulär 26:28 kommer från Excel efter omräkning med kommunkoden 2280 (tkr, avrundat).
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest
from conftest import INSPELNINGAR, skapa_app
from fastapi.testclient import TestClient

from app import skatteunderlag
from app.skatteunderlag import Prognosfil, Prognosfel
from app.sources.base import Hamtning
from app.sources.skr import SIDA, SkrSkatteunderlag, prognoslankar

MANIFEST = json.loads((INSPELNINGAR / "manifest.json").read_text(encoding="utf-8"))


def inspelning(nyckel: str) -> bytes:
    return (INSPELNINGAR / MANIFEST[nyckel]).read_bytes()


SIDNYCKEL = "skr.se/ekonomiochbudgetplanering/skatteunderlagsprognoser.8271.html"
FIL_26_28 = next(k for k in MANIFEST if k.endswith("26028.xlsm"))

try:
    skatteunderlag.soffice()
    LIBREOFFICE = True
except Prognosfel:
    # I CI ska omräkningen alltid testas, inte hoppas över.
    if os.environ.get("KRAV_LIBREOFFICE"):
        raise
    LIBREOFFICE = False
kraver_libreoffice = pytest.mark.skipif(not LIBREOFFICE, reason="LibreOffice saknas")

# Facit för 26:28 (tkr): 2026, 2027 och 2033.
FACIT = {
    "skatteintakter": (1_431_194, 1_483_067, 1_867_519),
    "inkomstutjamning": (438_335, 461_719, 581_318),
    "kostnadsutjamning": (52_413, 66_722, 67_168),
    "regleringsbidrag": (68_098, 61_925, 8_357),
    "lss_utjamning": (76_984, 78_805, 79_332),
    "summa_intakter": (2_067_024, 2_152_238, 2_603_695),
    "slutavrakning_2026": (-16_327, 0, 0),
    "slutavrakning_2027": (0, -3_483, 0),
    "fastighetsavgift": (72_511, 73_314, 73_314),
    "summa_inkl": (2_123_232, 2_222_069, 2_677_009),
}


def test_lankarna_pa_sidan_tolkas():
    lankar = prognoslankar(inspelning(SIDNYCKEL).decode("utf-8"), SIDA)
    # Bara kommunernas filer, inte regionernas, i sidans ordning.
    assert [c for c, _, _ in lankar] == ["26:28", "26:27", "26:24", "26:18", "26:12"]
    cirk, url, filnamn = lankar[0]
    # Länktexten säger "(xlsx)" fast filen är .xlsm.
    assert url == "https://skr.se/download/18.22a5529f1a0fb7804e67d572/1791283712510/Prognosunderlag-K-2026-2033-26028.xlsm"
    assert filnamn == "Prognosunderlag-K-2026-2033-26028.xlsm"
    assert all(f.endswith(".xlsm") and "-K-" in f for _, _, f in lankar)


@pytest.fixture(scope="module")
def prognos_26_28() -> dict:
    if not LIBREOFFICE:
        pytest.skip("LibreOffice saknas")
    return skatteunderlag.prognos(inspelning(FIL_26_28))


@kraver_libreoffice
def test_omrakningen_ger_facit_for_26_28(prognos_26_28):
    p = prognos_26_28
    assert p["publicerad"].isoformat() == "2026-10-06"
    assert p["ar"] == list(range(2026, 2034))
    assert p["skattesats"] == 23.34
    rader = {r["id"]: r for r in p["rader"]}
    for rad, (a26, a27, a33) in FACIT.items():
        t = rader[rad]["tkr"]
        assert (t["2026"], t["2027"], t["2033"]) == (pytest.approx(a26, abs=1), pytest.approx(a27, abs=1),
                                                     pytest.approx(a33, abs=1)), rad
    summa = rader["summa_intakter"]["tkr"]
    for ar, v in zip(range(2028, 2033), (2_224_531, 2_296_499, 2_369_596, 2_444_400, 2_522_249)):
        assert summa[str(ar)] == pytest.approx(v, abs=1)
    assert (p["invanare"]["2026"], p["invanare"]["2027"], p["invanare"]["2033"]) == (24_333, 24_360, 24_523)
    # Raderna i ordning, med en slutavräkning per år mellan Summa intäkter och Fastighetsavgift.
    ids = [r["id"] for r in p["rader"]]
    assert ids.index("summa_intakter") < ids.index("slutavrakning_2026") < ids.index("fastighetsavgift")
    assert rader["slutavrakning_2026"]["etikett"].startswith("Slutavräkning")


def andrad(innehall: bytes, gor) -> bytes:
    """Filen med en ändring (openpyxl), sparad utan makron."""
    wb = openpyxl.load_workbook(io.BytesIO(innehall), keep_vba=False)
    gor(wb)
    ut = io.BytesIO()
    wb.save(ut)
    return ut.getvalue()


class Fast:
    """En datakälla som lämnar givna prognosfiler."""

    id = "skr-skatteunderlagsprognos"
    titel = "SKR skatteunderlagsprognos"
    url = SIDA
    anrop_per_sekund = None

    def __init__(self, filer: list[Prognosfil]) -> None:
        self.filer = filer

    def hamta(self, client, sedan: datetime | None) -> Hamtning:
        return Hamtning(prognosfiler=list(self.filer))


def kor(api: TestClient) -> dict:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    svar = api.post("/api/insamlingar")
    assert svar.status_code == 200, svar.text
    [k] = [k for k in svar.json()["kallor"] if k["datakalla_id"] == "skr-skatteunderlagsprognos"]
    return k


@kraver_libreoffice
def test_insamlingen_sparar_varje_cirkular(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[SkrSkatteunderlag(anrop_per_sekund=None)],
                               anonym_lasning=True))
    k = kor(api)
    assert (k["status"], k["antal_nya"]) == ("lyckad", 5), k.get("fel")

    api.post("/api/auth/logga-ut")
    svar = api.get("/api/skatteunderlagsprognoser").json()
    assert [p["cirkular"] for p in svar["prognoser"]] == ["26:12", "26:18", "26:24", "26:27", "26:28"]
    s = svar["senaste"]
    assert (s["cirkular"], s["publicerad"], s["version"], s["skattesats"]) == ("26:28", "2026-10-06", 1, 23.34)
    assert s["url"].endswith("/Prognosunderlag-K-2026-2033-26028.xlsm")
    summa = next(r for r in s["rader"] if r["id"] == "summa_inkl")
    assert summa["etikett"] == "Summa intäkter (inkl avräkning och fastighetsavgift)"
    assert summa["tkr"]["2027"] == pytest.approx(2_222_069, abs=1)
    # Varje cirkulär har sin egen prognos för samma år.
    assert len({p["rader"][0]["tkr"]["2027"] for p in svar["prognoser"]}) > 1

    # Samma filer igen: inga nya uppgifter, och inget räknas om.
    assert kor(api)["status"] == "inga_nya"
    [d] = [d for d in api.get("/api/datakallor").json() if d["id"] == "skr-skatteunderlagsprognos"]
    assert d["titel"] == "SKR skatteunderlagsprognos"


@kraver_libreoffice
def test_samma_cirkular_med_andra_varden_blir_ny_version(database_url, google):
    original = inspelning(FIL_26_28)
    url = "https://skr.se/download/x/1/Prognosunderlag-K-2026-2033-26028.xlsm"
    fil = Prognosfil("26:28", url, "Prognosunderlag-K-2026-2033-26028.xlsm", original)
    kallor: list = [Fast([fil])]
    api = TestClient(skapa_app(database_url, google, kallor=kallor, anonym_lasning=True))
    assert kor(api)["status"] == "lyckad"

    def hojd_skattesats(wb):
        ws = wb["Data"]
        kol = next(c.column for c in ws[2] if c.value == "Utdeb 26")
        rad = next(r[0].row for r in ws.iter_rows(min_row=3) if r[0].value == 2280)
        ws.cell(rad, kol).value = 23.84

    kallor[0].filer = [Prognosfil("26:28", url, fil.filnamn, andrad(original, hojd_skattesats))]
    k = kor(api)
    assert (k["status"], k["antal_andrade"]) == ("lyckad", 1)
    svar = api.get("/api/skatteunderlagsprognoser").json()
    assert (svar["senaste"]["version"], svar["senaste"]["skattesats"]) == (2, 23.84)
    assert svar["senaste"]["rader"][0]["tkr"]["2027"] > 1_483_067  # högre skattesats, högre skatteintäkter
    # Den tidigare versionen finns kvar.
    from app import db
    with db.connect(database_url) as conn:
        assert [r["version"] for r in conn.execute(
            "SELECT version FROM skatteunderlagsprognos WHERE cirkular = '26:28' ORDER BY version")] == [1, 2]


@kraver_libreoffice
def test_fil_utan_forvantad_rad_ger_delvis_fel(database_url, google):
    def utan_skatteintakter(wb):
        ws = wb["Prognosunderlag"]
        ws["A4"] = "Skatter"

    trasig = Prognosfil("26:27", "https://skr.se/download/y/1/Prognosunderlag-K-2026-2033-26027.xlsm",
                        "Prognosunderlag-K-2026-2033-26027.xlsm",
                        andrad(inspelning(next(k for k in MANIFEST if k.endswith("26027.xlsm"))), utan_skatteintakter))
    api = TestClient(skapa_app(database_url, google, kallor=[Fast([trasig])], anonym_lasning=True))
    k = kor(api)
    assert k["status"] == "delvis_fel"
    assert k["fel"] == ('Prognosunderlag-K-2026-2033-26027.xlsm (cirkulär 26:27): raden "Skatteintäkter" saknas i '
                        "Prognosunderlag")
    assert api.get("/api/skatteunderlagsprognoser").json()["prognoser"] == []


def test_fil_som_inte_ar_excel_ger_begripligt_fel():
    with pytest.raises(Prognosfel, match="filen kan inte läsas"):
        skatteunderlag.rakna_om(b"inte en arbetsbok")


def test_utan_prognoser_ar_listan_tom(database_url, google):
    api = TestClient(skapa_app(database_url, google, kallor=[], anonym_lasning=True))
    assert api.get("/api/skatteunderlagsprognoser").json() == {"kommun": "2280", "senaste": None, "prognoser": []}
