"""Valmyndighetens öppna data om valen till kommunfullmäktige i Härnösand (#65).

Fem filer per val: de valda ledamöterna med efterträdare (`ledamoter_med_historik.csv`), ledamöterna med
ersättare (`ledamoter_och_ersattare_utokad.csv`) och kandidaturerna (`kandidaturer.zip`). För 2026 hämtas
också de röstberättigade per kön och ålder, som referens i statistiken.

Om formatet:

- CSV-filerna är semikolonseparerade, UTF-8 med BOM. Resultatfilerna börjar med en stämpel
  (";Valmyndigheten 2026-10-30 15:51:49") före rubrikraden. Kandidaturerna har ingen stämpel.
- 2022 års filer har bara CR som radslut, kandidaturerna 2026 har CRLF.
- Raderna filtreras på kolumnerna (Valtyp och Kommun, respektive VALTYP och VALOMRÅDESKOD), aldrig på en
  sträng i hela raden, eftersom kommunkoden kan förekomma som kandidatnummer.
- Valmyndigheten gallrar kandidaternas personuppgifter i efterhand och skriver då "Gallrad uppgift".
  Ett gallrat fält blir None och står i radens "gallrade", så att ett sparat värde inte skrivs över.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx

from .base import Hamtning

KOMMUN = "Härnösand"
KOMMUNKOD = "2280"
VALAR = (2022, 2026)
VALDAG = {2022: date(2022, 9, 11), 2026: date(2026, 9, 13)}

RESULTAT = "https://resultat.val.se/filer/val{ar}/info/{fil}.csv"
KANDIDATURER = "https://data.val.se/filer/val{ar}/parti/kandidaturer.zip"
# Antal röstberättigade per valdistrikt uppdelat på kön och ålder, valdagen, val till kommunfullmäktige
# (sidan "Rådata val 2026" på val.se).
ROSTBERATTIGADE = {
    2026: "https://www.val.se/download/18.7faaad3f1a0b0c300e4180/1789746961123/"
          "antal-rostberattigade-per-valdistrikt-uppdelat-pa-kon-och-alder-valdagen-13-september-2026-"
          "val-till-kommunfullmaktige.xlsx",
}

GALLRAD = "Gallrad uppgift"
# Valmyndighetens partiförkortningar som plattformen skriver på annat sätt.
_PARTI = {"NorrP": "NP"}


def parti(forkortning: str) -> str:
    f = (forkortning or "").strip()
    return _PARTI.get(f, f)


@dataclass
class Valdata:
    """Det som hämtats för ett val. None = filen gick inte att hämta, och det sparade lämnas orört."""

    valar: int
    filer: list[dict] = field(default_factory=list)  # {fil, url, stampel}
    kandidater: list[dict] | None = None
    ledamoter: list[dict] | None = None
    ersattare: list[dict] | None = None
    rostberattigade: dict | None = None


def las_csv(innehall: bytes) -> tuple[str | None, list[dict[str, str]]]:
    """Returnerar källans stämpel (om den finns) och raderna som dict per rubrik."""
    text = innehall.decode("utf-8-sig")
    linjer = [l for l in re.split(r"\r\n|\r|\n", text) if l.strip()]
    stampel = None
    if linjer and linjer[0].startswith(";"):
        stampel = linjer[0].strip(";").strip() or None
        linjer = linjer[1:]
    if not linjer:
        return stampel, []
    rader = list(csv.reader(linjer, delimiter=";"))
    rubriker = [r.strip() for r in rader[0]]
    return stampel, [dict(zip(rubriker, (v.strip() for v in r))) for r in rader[1:]]


def _text(v: str | None) -> str | None:
    return v.strip() if v and v.strip() else None


def _heltal(v: str | None) -> int | None:
    v = _text(v)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _datum(v: str | None) -> date | None:
    v = _text(v)
    return datetime.fromisoformat(v).date() if v else None


def _kon(v: str | None) -> str | None:
    v = _text(v)
    return v if v in ("K", "M") else None


def _gallrat(rad: dict, falt: dict[str, str]) -> tuple[dict, set[str]]:
    """Byter "Gallrad uppgift" mot None. Returnerar värdena och vilka fält som är gallrade."""
    gallrade = {namn for namn, kolumn in falt.items() if (rad.get(kolumn) or "").strip() == GALLRAD}
    return {namn: (None if namn in gallrade else rad.get(kolumn)) for namn, kolumn in falt.items()}, gallrade


def tolka_kandidaturer(innehall: bytes) -> list[dict]:
    """Kandidaturerna till kommunfullmäktige i Härnösand, ur zip-filen (eller CSV-filen direkt)."""
    if innehall[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(innehall)) as z:
            namn = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            innehall = z.read(namn)
    _, rader = las_csv(innehall)
    ut = []
    for r in rader:
        if r.get("VALTYP") != "KF" or r.get("VALOMRÅDESKOD") != KOMMUNKOD:
            continue
        v, gallrade = _gallrat(r, {"namn": "NAMN", "alder": "ÅLDER_PÅ_VALDAGEN", "kon": "KÖN",
                                    "folkbokforingskommun": "FOLKBOKFÖRINGSKOMMUN"})
        ut.append({
            "kandidatnummer": int(r["KANDIDATNUMMER"]),
            "parti": parti(r.get("PARTIFÖRKORTNING", "")),
            "listnummer": _text(r.get("LISTNUMMER")),
            "ordning": _heltal(r.get("ORDNING")),
            "namn": _text(v["namn"]),
            "alder": _heltal(v["alder"]),
            "kon": _kon(v["kon"]),
            "folkbokforingskommun": _text(v["folkbokforingskommun"]),
            "giltig": (r.get("GILTIG") or "J").strip() != "N",
            "gallrade": gallrade,
        })
    return ut


def _harnosand_kf(rader: list[dict]) -> list[dict]:
    return [r for r in rader if r.get("Valtyp") == "KF" and r.get("Kommun") == KOMMUN]


def tolka_ledamoter(innehall: bytes) -> tuple[str | None, list[dict]]:
    """De valda ledamöterna med efterträdare (ledamoter_med_historik.csv)."""
    stampel, rader = las_csv(innehall)
    ut = []
    for r in _harnosand_kf(rader):
        v, gallrade = _gallrat(r, {"alder": "Ålder valdag", "kon": "Kön"})
        ut.append({
            "kandidatnummer": int(r["Kandidatnummer ledamot"]),
            "parti": parti(r.get("Partiförkortning", "")),
            "mandat": int(r["Mandat (invalsordning)"]),
            "namn": " ".join(filter(None, (_text(r.get("Ledamot förnamn")), _text(r.get("Ledamot efternamn"))))),
            "invald": _datum(r.get("Invalsdatum")),
            "avgang": _datum(r.get("Avgångsdatum")),
            "personvald": bool(_text(r.get("Personvald"))),
            "alder": _heltal(v["alder"]),
            "kon": _kon(v["kon"]),
            "gallrade": gallrade,
        })
    return stampel, ut


def tolka_ersattare(innehall: bytes) -> tuple[str | None, list[dict]]:
    """Ersättarna per ledamot (ledamoter_och_ersattare_utokad.csv)."""
    stampel, rader = las_csv(innehall)
    ut = []
    for r in _harnosand_kf(rader):
        if not _text(r.get("Kandidatnummer ersättare")):
            continue
        ut.append({
            "parti": parti(r.get("Partiförkortning", "")),
            "ledamot_kandidatnummer": int(r["Kandidatnummer ledamot"]),
            "ersattargrupp": _heltal(r.get("Ersättargrupp")),
            "ersattarordning": int(r["Ersättarordning"]),
            "kandidatnummer": int(r["Kandidatnummer ersättare"]),
            "namn": _text(r.get("Namn ersättare")) or "",
        })
    return stampel, ut


def tolka_rostberattigade(innehall: bytes) -> tuple[str | None, dict]:
    """De röstberättigade i Härnösand per kön och åldersgrupp, ur fliken per kommun."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(innehall), read_only=True, data_only=True)
    stampel = None
    for ws in wb.worksheets:
        rader = ws.iter_rows(values_only=True)
        forsta = next(rader, None)
        if not forsta:
            continue
        if isinstance(forsta[0], str) and forsta[0].startswith("Valmyndigheten"):
            stampel = forsta[0].strip()
            continue
        rubriker = [str(c).strip() if c is not None else "" for c in forsta]
        if "Kommunkod" not in rubriker or "Valdistriktskod" in rubriker:
            continue
        for rad in rader:
            v = dict(zip(rubriker, rad))
            if str(v.get("Kommunkod") or "").strip() == KOMMUNKOD:
                return stampel, {
                    "kvinnor": int(v["Kvinnor"]), "man": int(v["Män"]),
                    "a18_29": int(v["Ålder 18-29"]), "a30_49": int(v["Ålder 30-49"]),
                    "a50_64": int(v["Ålder 50-64"]), "a65": int(v["Ålder 65-"]), "totalt": int(v["Totalt"]),
                }
    raise ValueError(f"Kommunkod {KOMMUNKOD} saknas i filen över röstberättigade")


class Valmyndigheten:
    id = "valmyndigheten"
    titel = "Valmyndigheten"
    url = "https://www.val.se/valresultat-och-statistik/statistik-och-data.html"

    def __init__(self, valar: tuple[int, ...] = VALAR, anrop_per_sekund: float | None = 1.0) -> None:
        self.valar = valar
        self.anrop_per_sekund = anrop_per_sekund

    def _hamta(self, client: httpx.Client, url: str) -> bytes:
        svar = client.get(url)
        svar.raise_for_status()
        return svar.content

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        # Filerna är små för Härnösand men stora för riket. Allt hämtas vid varje kontroll, och lagringen
        # avgör vad som är nytt eller ändrat.
        resultat = Hamtning()
        lyckade = 0
        senaste_fel: Exception | None = None
        for ar in self.valar:
            data = Valdata(valar=ar)
            steg = [
                ("ledamoter_med_historik", RESULTAT.format(ar=ar, fil="ledamoter_med_historik"), tolka_ledamoter,
                 "ledamoter"),
                ("ledamoter_och_ersattare", RESULTAT.format(ar=ar, fil="ledamoter_och_ersattare_utokad"),
                 tolka_ersattare, "ersattare"),
                ("kandidaturer", KANDIDATURER.format(ar=ar), lambda b: (None, tolka_kandidaturer(b)), "kandidater"),
            ]
            if ar in ROSTBERATTIGADE:
                steg.append(("rostberattigade", ROSTBERATTIGADE[ar], tolka_rostberattigade, "rostberattigade"))
            for fil, url, tolka, falt in steg:
                try:
                    stampel, varden = tolka(self._hamta(client, url))
                except (httpx.HTTPError, KeyError, ValueError, zipfile.BadZipFile, StopIteration) as e:
                    senaste_fel = e
                    resultat.fel.append(f"{fil} {ar}: {type(e).__name__}: {e}")
                    continue
                setattr(data, falt, varden)
                data.filer.append({"fil": fil, "url": url, "stampel": stampel})
                lyckade += 1
            resultat.val.append(data)
        if lyckade == 0 and senaste_fel is not None:
            raise senaste_fel
        return resultat
