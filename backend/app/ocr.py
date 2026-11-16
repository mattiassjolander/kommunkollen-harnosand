"""Textigenkänning (OCR) för protokoll som bara innehåller bilder (#52).

Vissa protokoll publiceras som en PDF där varje sida är en bild, utan text. Sidorna renderas och
läses med Tesseract på svenska. Tesseract ger varje ord med dess placering på sidan, och ur
placeringen byggs samma två texter som tolkningen läser ur en vanlig PDF:

- **löptext**: raderna uppifrån och ned, orden åtskilda med ett mellanslag,
- **layouttext**: raderna med orden på sin kolumn, så att kolumner i närvaro- och voteringslistor
  står kvar (som pypdf:s layoutläge).

Ett ord hör till en rad när det överlappar radens höjd. OCR kan läsa fel, och det som tolkas ur
OCR-text märks därför (`Tolkning.ocr`).
"""

from __future__ import annotations

import io
import re
import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from statistics import median

SPRAK = "swe"
DPI = 400
_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class OcrSaknas(RuntimeError):
    """Tesseract eller den svenska språkdatan finns inte."""


def _tesseract() -> str:
    t = os.environ.get("TESSERACT") or shutil.which("tesseract") or (_WINDOWS if os.path.exists(_WINDOWS) else None)
    if not t:
        raise OcrSaknas("Tesseract finns inte")
    return t


@lru_cache(maxsize=1)
def tillganglig() -> bool:
    try:
        sprak = subprocess.run([_tesseract(), "--list-langs"], capture_output=True, text=True, timeout=30).stdout
    except (OcrSaknas, OSError, subprocess.SubprocessError):
        return False
    return SPRAK in sprak.split()


@dataclass
class Ord:
    text: str
    x: int
    y: int
    b: int
    h: int


def _sidbilder(pdf: bytes, dpi: int):
    import pypdfium2 as pdfium

    dok = pdfium.PdfDocument(pdf)
    try:
        for sida in dok:
            yield sida.render(scale=dpi / 72, grayscale=True).to_pil()
    finally:
        dok.close()


def _ord(bild) -> list[Ord]:
    buf = io.BytesIO()
    bild.save(buf, format="PNG")
    # psm 4: en kolumn med text av olika storlek, raderna i läsordning. Ordens placering används ändå.
    res = subprocess.run(
        [_tesseract(), "stdin", "stdout", "-l", SPRAK, "--psm", "4", "-c", "preserve_interword_spaces=1",
         "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0"],
        input=buf.getvalue(), capture_output=True, timeout=300,
    )
    if res.returncode != 0:
        raise OcrSaknas(res.stderr.decode("utf-8", "replace").strip()[:200])
    ut = []
    for rad in res.stdout.decode("utf-8").splitlines()[1:]:
        f = rad.split("\t")
        if len(f) < 12 or f[0] != "5" or not f[11].strip():
            continue
        ut.append(Ord(f[11].strip(), int(f[6]), int(f[7]), int(f[8]), int(f[9])))
    return ut


def _rader(ord_: list[Ord]) -> list[list[Ord]]:
    """Ord med överlappande höjd blir en rad, sorterade från vänster."""
    rader: list[list[Ord]] = []
    for o in sorted(ord_, key=lambda o: (o.y + o.h / 2, o.x)):
        mitt = o.y + o.h / 2
        if rader:
            r = rader[-1]
            topp = min(x.y for x in r)
            botten = max(x.y + x.h for x in r)
            if topp <= mitt <= botten:
                r.append(o)
                continue
        rader.append([o])
    return [sorted(r, key=lambda o: o.x) for r in rader]


def _texter(ord_: list[Ord]) -> tuple[str, str]:
    if not ord_:
        return "", ""
    # Teckenbredd: medianen av ordens bredd per tecken.
    langa = [o.b / len(o.text) for o in ord_ if len(o.text) >= 3]
    tecken = median(langa) if langa else 10
    marginal = min(o.x for o in ord_)
    lop: list[str] = []
    layout: list[str] = []
    for r in _rader(ord_):
        lop.append(" ".join(o.text for o in r))
        rad = ""
        slut = 0
        for o in r:
            if not rad:
                rad = " " * round((o.x - marginal) / tecken)
            elif o.x - slut <= 1.5 * tecken:
                rad += " "  # samma fras: ett mellanslag, som i en PDF med text
            else:
                # Ett tydligt mellanrum: ordet står på sin kolumn, minst två mellanslag efter föregående.
                rad = rad.ljust(max(round((o.x - marginal) / tecken), len(rad) + 2))
            rad += o.text
            slut = o.x + o.b
        layout.append(rad)
    return "\n".join(lop), "\n".join(layout)


# Vanliga läsfel i protokollen. Paragraftecknet läses som 8, 5, 3, & eller $, ibland ihop med numret.
_RATTELSER = [
    (re.compile(r"\$\s?8\s(?=\d)"), "§§ "),            # "$8 43 — 60" -> "§§ 43 – 60"
    (re.compile(r"(Paragrafer\s+)\S{1,2}\s(?=\d{1,3}\s*[—–-]\s*\d)"), r"\g<1>§§ "),  # "Paragrafer 88 43 – 60"
    (re.compile(r"\$\$?"), "§"),                       # dollartecken förekommer inte i protokollen
    (re.compile(r"&\s?(?=\d{1,3}\b)"), "§ "),          # "(S) & 45"
    (re.compile(r"(?<=\)\s)8\s(?=\d{1,3}\b)"), "§ "),  # "(SD) 8 45"
    (re.compile(r"^(\s*)8\s(?=\d{1,3}\b)"), r"\1§ "),  # "8 43-44, 46-60" i radbörjan
    (re.compile(r"—"), "–"),
]
# Paragrafintervallet på första sidan. Bindestrecket kan läsas dubbelt ("62 –- 77") och siffrorna
# i slutnumret som bokstäver ("TT" för 77).
_INTERVALL = re.compile(r"Paragrafer\s+§*\s*(\d{1,3})\s*[–-]+\s*([\dTIlOoSBZ|]{1,3})(?!\w)")
_SIFFERLIKA = str.maketrans("TIl|OoSBZ", "711100582")
# En rad med bara ett nummer, eventuellt följt av diarienumret: paragrafrubriken.
_NUMMERRAD = re.compile(r"^(\s*)§?\s?(\d{1,5})((?:\s+\S*\d\S*)?)$")


def ratta(rad: str, intervall: tuple[int, int] | None = None) -> str:
    """Rättar vanliga OCR-fel i en rad.

    En paragrafrubrik ("843", "5849", "8 50", "845 SAM/2026-103") rättas bara när protokollets
    paragrafintervall är känt: numret blir den del av siffrorna som ligger inom intervallet."""
    for monster, ersattning in _RATTELSER:
        rad = monster.sub(ersattning, rad)
    m = _NUMMERRAD.match(rad)
    if m and intervall:
        siffror = m[2]
        for k in range(len(siffror)):
            nr = int(siffror[k:])
            if intervall[0] <= nr <= intervall[1] and (k > 0 or rad.lstrip().startswith("§")):
                return f"{m[1]}§ {nr}{m[3]}"
    return rad


def paragrafintervall(text: str) -> tuple[int, int] | None:
    """Protokollets paragrafintervall ur OCR-text, med vanliga läsfel i siffrorna rättade."""
    m = _INTERVALL.search(" ".join(ratta(r) for r in text.splitlines()))
    if not m:
        return None
    start, slut = int(m[1]), int(m[2].translate(_SIFFERLIKA))
    return (start, slut) if start <= slut else None


def sidtexter(pdf: bytes, dpi: int = DPI) -> tuple[list[str], list[str]]:
    """(löptext, layouttext) per sida, lästa med OCR och med vanliga läsfel rättade."""
    sidor = [_texter(_ord(bild)) for bild in _sidbilder(pdf, dpi)]
    intervall = next((i for lop, _ in sidor[:2] if (i := paragrafintervall(lop))), None)

    def rattad(text: str) -> str:
        text = "\n".join(ratta(r, intervall) for r in text.splitlines())
        if intervall:
            # Intervallet skrivs som i protokollet, så att tolkningen kan jämföra paragraferna mot det.
            text = _INTERVALL.sub(f"Paragrafer §§ {intervall[0]}–{intervall[1]}", text)
        return text

    return [rattad(l) for l, _ in sidor], [rattad(y) for _, y in sidor]
