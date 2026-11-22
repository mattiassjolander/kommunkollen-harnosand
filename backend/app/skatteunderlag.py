"""SKR:s skatteunderlagsprognoser för Härnösand (#61).

SKR publicerar fem gånger per år ett prognosunderlag för alla kommuner, en Excelfil med makron
(`Prognosunderlag-K-2026-2033-26028.xlsm`). Fliken `Prognosunderlag` räknas fram med formler utifrån
kommunkoden i `Prognosunderlag!B1`, och de sparade värdena gäller kod 0. Filen räknas därför om:

1. Kommunkoden skrivs in med openpyxl, och arbetsboken sparas som `.xlsx`. Då följer inga makron med.
2. LibreOffice headless öppnar filen med omräkning vid inläsning och makron avstängda, och sparar den.
3. Värdena läses av med radetiketterna i kolumn A och årtalen i raden "Belopp i tkr", inte med fasta
   cellnummer, så att små ändringar i uppläggningen mellan cirkulären klaras.

Varje cirkulär är en egen skatteunderlagsprognos. Publicerar SKR samma cirkulär igen med andra värden
blir det en ny version, och den tidigare finns kvar. Värdena är SKR:s officiella siffror och publiceras
direkt, som Kolada-data.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import openpyxl
import psycopg
from psycopg.types.json import Jsonb

KOMMUN = "2280"

# Raderna i fliken Prognosunderlag, i ordning: (id, etikett i kolumn A). Slutavräkningarna har en rad
# per avräkningsår ("Slutavräkning 2026") och läses separat.
RADER: list[tuple[str, str]] = [
    ("skatteintakter", "Skatteintäkter"),
    ("inkomstutjamning", "Inkomstutjämningsbidrag/-avgift"),
    ("kostnadsutjamning", "Kostnadsutjämning"),
    ("regleringsbidrag", "Regleringsbidrag/-avgift"),
    ("strukturbidrag", "Strukturbidrag"),
    ("inforandebidrag", "Införandebidrag"),
    ("lss_utjamning", "LSS-utjämning"),
    ("summa_intakter", "Summa intäkter"),
    ("fastighetsavgift", "Fastighetsavgift"),
    ("summa_inkl", "Summa intäkter (inkl avräkning och fastighetsavgift)"),
]
INVANARE = "Antal invånare i kommunen enligt riksprognos"
BELOPP = "Belopp i tkr"
BASUPPGIFTER = "Basuppgifter"


class Prognosfel(Exception):
    """Filen gick inte att räkna om eller läsa av. Ger delvis fel för datakällan."""


@dataclass(frozen=True)
class Prognosfil:
    """En fil med prognosunderlag för kommuner, som den står på SKR:s sida."""

    cirkular: str  # t.ex. '26:28'
    url: str
    filnamn: str
    innehall: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.innehall).hexdigest()


# Omräkning


_PROFIL = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
</oor:items>
"""


def soffice() -> str:
    """Sökvägen till LibreOffice: `SOFFICE` i miljön, `soffice` i PATH eller standardplatsen i Windows."""
    for kandidat in (os.environ.get("SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice"),
                     r"C:\Program Files\LibreOffice\program\soffice.exe"):
        if kandidat and Path(kandidat).exists():
            return kandidat
    raise Prognosfel("LibreOffice saknas (soffice), filen kan inte räknas om")


def rakna_om(innehall: bytes, kommun: str = KOMMUN, timeout: int = 300) -> openpyxl.Workbook:
    """Arbetsboken omräknad för kommunen, med värden i stället för formler."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(innehall), keep_vba=False)
    except Exception as e:  # noqa: BLE001 – vilket fel som helst i filen ska ge ett begripligt meddelande
        raise Prognosfel(f"filen kan inte läsas: {e}") from e
    if "Prognosunderlag" not in wb.sheetnames:
        raise Prognosfel("fliken Prognosunderlag saknas")
    wb["Prognosunderlag"]["B1"] = int(kommun)
    if "Blad 2 Indata" in wb.sheetnames and not str(wb["Blad 2 Indata"]["B1"].value or "").startswith("="):
        wb["Blad 2 Indata"]["B1"] = int(kommun)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_ = Path(tmp)
        (tmp_ / "in").mkdir()
        (tmp_ / "ut").mkdir()
        wb.save(tmp_ / "in" / "prognos.xlsx")
        profil = tmp_ / "profil" / "user"
        profil.mkdir(parents=True)
        (profil / "registrymodifications.xcu").write_text(_PROFIL, encoding="utf-8")
        try:
            svar = subprocess.run(
                [soffice(), "--headless", "--norestore", "--nolockcheck", "--nodefault",
                 f"-env:UserInstallation={(tmp_ / 'profil').as_uri()}",
                 "--convert-to", "xlsx", "--outdir", str(tmp_ / "ut"), str(tmp_ / "in" / "prognos.xlsx")],
                capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise Prognosfel(f"omräkningen med LibreOffice tog mer än {timeout} s") from e
        ut = tmp_ / "ut" / "prognos.xlsx"
        if not ut.exists():
            fel = (svar.stderr or svar.stdout).decode(errors="replace").strip()
            raise Prognosfel(f"LibreOffice räknade inte om filen: {fel or f'kod {svar.returncode}'}")
        return openpyxl.load_workbook(ut, data_only=True)


# Avläsning


def _etikett(v: object) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _ar(v: object) -> int | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 2000 <= v <= 2100 and v == int(v):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit() and 2000 <= int(v) <= 2100:
        return int(v)
    return None


def _tal(v: object, var: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Prognosfel(f"{var}: väntade ett tal, fick {v!r}")
    return float(v)


def las_av(wb: openpyxl.Workbook, kommun: str = KOMMUN) -> dict:
    """Prognosen ur en omräknad arbetsbok: publiceringsdatum, år, rader i tkr, invånare och skattesats."""
    ws = wb["Prognosunderlag"]
    if _etikett(ws["B1"].value) != str(int(kommun)):
        raise Prognosfel(f"kommunkoden i B1 är {ws['B1'].value!r}, inte {kommun}")
    publicerad = ws["J1"].value
    if not isinstance(publicerad, datetime | date):
        raise Prognosfel(f"publiceringsdatumet i J1 saknas (fick {publicerad!r})")
    publicerad = publicerad.date() if isinstance(publicerad, datetime) else publicerad

    rader: dict[str, int] = {}
    for rad in ws.iter_rows(min_col=1, max_col=1):
        e = _etikett(rad[0].value)
        if e and e not in rader:
            rader[e] = rad[0].row
    if BELOPP not in rader:
        raise Prognosfel(f"raden \"{BELOPP}\" med årtalen saknas i Prognosunderlag")
    rubrik = rader[BELOPP]
    ar = {c.column: a for c in ws[rubrik] if (a := _ar(c.value)) is not None}
    if not ar:
        raise Prognosfel(f"raden \"{BELOPP}\" har inga årtal")
    # Bara beloppen i tkr, inte raderna med kronor per invånare längre ner, som har samma etiketter.
    slut = next((r for e, r in rader.items() if e == "Kronor per invånare"), ws.max_row + 1)

    def rad_for(etikett: str) -> int:
        # Äldre cirkulär har ibland ett tillägg i parentes, t.ex. "LSS-utjämning (inkl införanderegler)".
        # Exakt etikett går först, så att "Summa intäkter" inte blir raden "Summa intäkter (inkl …)".
        etiketter = [(r, _etikett(ws.cell(r, 1).value)) for r in range(rubrik + 1, slut)]
        r = next((r for r, e in etiketter if e == etikett), None)
        if r is None:
            r = next((r for r, e in etiketter if e.startswith(f"{etikett} (")), None)
        if r is None:
            raise Prognosfel(f"raden \"{etikett}\" saknas i Prognosunderlag")
        return r

    def varden(r: int, etikett: str) -> dict[str, float]:
        return {str(a): round(_tal(ws.cell(r, k).value or 0, f"{etikett} {a}"), 3) for k, a in ar.items()}

    ut_rader = [{"id": i, "etikett": e, "tkr": varden(rad_for(e), e)} for i, e in RADER]
    # Slutavräkningarna står mellan Summa intäkter och Fastighetsavgift, en rad per år.
    fran, till = rad_for("Summa intäkter"), rad_for("Fastighetsavgift")
    avrakningar = []
    for r in range(fran + 1, till):
        e = _etikett(ws.cell(r, 1).value)
        if not e:
            continue
        if not e.lower().startswith("slutavräkning"):
            raise Prognosfel(f"oväntad rad \"{e}\" mellan Summa intäkter och Fastighetsavgift")
        avrakningar.append({"id": f"slutavrakning_{e.split()[-1]}", "etikett": e, "tkr": varden(r, e)})
    i = next(n for n, x in enumerate(ut_rader) if x["id"] == "summa_intakter") + 1
    ut_rader[i:i] = avrakningar

    # Invånarna: årtalen står i raden Basuppgifter, som kan börja ett år tidigare än beloppen.
    if BASUPPGIFTER not in rader or INVANARE not in rader:
        raise Prognosfel(f"raden \"{INVANARE}\" eller \"{BASUPPGIFTER}\" saknas i Prognosunderlag")
    bas_ar = {c.column: a for c in ws[rader[BASUPPGIFTER]] if (a := _ar(c.value)) is not None}
    invanare = {str(a): int(round(_tal(ws.cell(rader[INVANARE], k).value, f"{INVANARE} {a}")))
                for k, a in bas_ar.items() if a in ar.values()}
    if set(invanare) != {str(a) for a in ar.values()}:
        raise Prognosfel(f"\"{INVANARE}\" saknar år")

    return {"publicerad": publicerad, "ar": sorted(ar.values()), "rader": ut_rader, "invanare": invanare,
            "skattesats": skattesats(wb, kommun, min(ar.values()))}


def skattesats(wb: openpyxl.Workbook, kommun: str, forsta_ar: int) -> float:
    """Skattesatsen som prognosen räknar med: kolumnen `Utdeb <år>` på fliken Data för kommunen."""
    if "Data" not in wb.sheetnames:
        raise Prognosfel("fliken Data saknas")
    ws = wb["Data"]
    rubrik = f"Utdeb {forsta_ar % 100:02d}"
    for rad in ws.iter_rows(min_row=1, max_row=5):
        kolumner = {_etikett(c.value): c.column for c in rad}
        if "Kommunkod" in kolumner and rubrik in kolumner:
            for r in ws.iter_rows(min_row=rad[0].row + 1):
                if _etikett(r[kolumner["Kommunkod"] - 1].value) == str(int(kommun)):
                    return round(_tal(r[kolumner[rubrik] - 1].value, rubrik), 2)
            raise Prognosfel(f"kommunen {kommun} saknas på fliken Data")
    raise Prognosfel(f"kolumnen \"{rubrik}\" saknas på fliken Data")


def prognos(innehall: bytes, kommun: str = KOMMUN) -> dict:
    return las_av(rakna_om(innehall, kommun), kommun)


# Lagring


def lagra(conn: psycopg.Connection, fil: Prognosfil, korning_id: int, hamtad: datetime,
          kommun: str = KOMMUN) -> tuple[str, str | None, date | None]:
    """Sparar cirkulärets prognos. (utfall, fel, publicerad) där utfall är 'ny', 'andrad' eller 'oforandrad'.

    En fil som redan är sparad (samma cirkulär och innehåll) räknas inte om. En ny fil för samma
    cirkulär med andra värden blir en ny version; med samma värden ändras inget."""
    senaste = conn.execute(
        "SELECT version, sha256, publicerad, skattesats, ar, rader, invanare FROM skatteunderlagsprognos "
        "WHERE cirkular = %s AND kommun = %s ORDER BY version DESC LIMIT 1", (fil.cirkular, kommun),
    ).fetchone()
    if senaste and senaste["sha256"] == fil.sha256:
        return "oforandrad", None, senaste["publicerad"]
    try:
        p = prognos(fil.innehall, kommun)
    except Prognosfel as e:
        return "oforandrad", f"{fil.filnamn} (cirkulär {fil.cirkular}): {e}", None
    if senaste and (senaste["publicerad"], float(senaste["skattesats"]), senaste["ar"], senaste["rader"],
                    senaste["invanare"]) == (p["publicerad"], p["skattesats"], p["ar"], p["rader"], p["invanare"]):
        conn.execute("UPDATE skatteunderlagsprognos SET sha256 = %s, url = %s WHERE cirkular = %s AND kommun = %s "
                     "AND version = %s", (fil.sha256, fil.url, fil.cirkular, kommun, senaste["version"]))
        return "oforandrad", None, p["publicerad"]
    conn.execute(
        """
        INSERT INTO skatteunderlagsprognos (cirkular, kommun, version, publicerad, url, filnamn, sha256, skattesats,
          ar, rader, invanare, hamtad, korning_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (fil.cirkular, kommun, senaste["version"] + 1 if senaste else 1, p["publicerad"], fil.url, fil.filnamn,
         fil.sha256, p["skattesats"], Jsonb(p["ar"]), Jsonb(p["rader"]), Jsonb(p["invanare"]), hamtad, korning_id),
    )
    return ("andrad" if senaste else "ny"), None, p["publicerad"]


# Läsning


def _ut(r: dict) -> dict:
    return {"cirkular": r["cirkular"], "version": r["version"], "publicerad": r["publicerad"].isoformat(),
            "url": r["url"], "filnamn": r["filnamn"], "skattesats": float(r["skattesats"]), "ar": r["ar"],
            "rader": r["rader"], "invanare": r["invanare"], "hamtad": r["hamtad"].isoformat()}


def lista(conn: psycopg.Connection, kommun: str = KOMMUN) -> dict:
    """Den senaste versionen av varje cirkulär, sorterade efter publiceringsdatum, och den senaste prognosen."""
    rader = conn.execute(
        """
        SELECT DISTINCT ON (cirkular) * FROM skatteunderlagsprognos WHERE kommun = %s
        ORDER BY cirkular, version DESC
        """, (kommun,),
    ).fetchall()
    prognoser = sorted((_ut(r) for r in rader), key=lambda p: (p["publicerad"], p["cirkular"]))
    return {"kommun": kommun, "senaste": prognoser[-1] if prognoser else None, "prognoser": prognoser}


# Raden som jämförs med planförutsättningarnas skatteintäkter och generella bidrag och utjämning (#62).
JAMFORD_RAD = "summa_inkl"
FORSTA_AR = 2026  # SKR har inga äldre prognosfiler att hämta.


def jamforelse(conn: psycopg.Connection, ar: int, plan_mnkr: float | None, kommun: str = KOMMUN) -> dict:
    """Planförutsättningarnas summa bredvid varje skatteunderlagsprognos som har en siffra för budgetåret.

    Differensen är SKR − planförutsättningar, i mnkr och procent. Ingen prognos pekas ut som den rätta.
    Saknas planförutsättningar eller prognos är `prognoser` tom och `saknas` säger varför."""
    prognoser = []
    for p in lista(conn, kommun)["prognoser"]:
        rad = next((r for r in p["rader"] if r["id"] == JAMFORD_RAD), None)
        tkr = rad["tkr"].get(str(ar)) if rad else None
        if tkr is None:
            continue
        mnkr = round(tkr / 1000, 3)
        d = None
        if plan_mnkr is not None:
            d = {"mnkr": round(mnkr - plan_mnkr, 1),
                 "procent": round((mnkr - plan_mnkr) / plan_mnkr * 100, 2) if plan_mnkr else None}
        prognoser.append({"cirkular": p["cirkular"], "publicerad": p["publicerad"], "url": p["url"],
                          "filnamn": p["filnamn"], "mnkr": mnkr, "differens": d})
    saknas = None
    if plan_mnkr is None:
        saknas = f"Planförutsättningarna för {ar} är inte publicerade."
    elif not prognoser:
        saknas = (f"SKR:s prognoser finns från {FORSTA_AR}." if ar < FORSTA_AR
                  else f"Ingen av SKR:s skatteunderlagsprognoser har en siffra för {ar}.")
    return {"planforutsattningar_mnkr": plan_mnkr, "prognoser": prognoser if plan_mnkr is not None else [],
            "saknas": saknas}
