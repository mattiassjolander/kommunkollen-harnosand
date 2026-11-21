"""Härnösands kommun (harnosand.se): sammanträdesplanerna på de fem organens sidor.

Varje organs sida har en tabell per år med kolumnerna Månad, Datum och Tid. Ändringar skrivs
in som fritext i tabellen, t.ex. "Inställt", "Inställd", "OBS tiden: 11.00" och "(8/9 ställs in)".
Text som inte känns igen sparas som en anmärkning på raden och ger *delvis fel*.
Lagringen görs i `app.sammantradesplan`.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urljoin

import httpx

from . import kallelser as kallelsemodul
from .base import Hamtning
from .harnosand import BAS, ORGAN

MANADER = {
    m: i for i, m in enumerate(
        ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
         "november", "december"), start=1)
}


@dataclass(frozen=True)
class Planrad:
    """Ett planerat sammanträde enligt organets tabell.

    `datum` är None för en månad som bara anges som inställd ("Juni: Inställd").
    `status`: 'planerat' eller 'installt'.
    """

    organ: str
    ar: int
    manad: int
    datum: date | None
    starttid: str | None  # "HH:MM", som i protokollen
    status: str
    anmarkning: str | None = None
    kalltext: str = ""  # tabellradens text, t.ex. "Oktober | 26 | OBS tiden: 11.00"

    @property
    def nyckel(self) -> str:
        """Identifierar raden i organets plan: datumet, eller året och månaden när datum saknas."""
        return self.datum.isoformat() if self.datum else f"{self.ar}-{self.manad:02d}"


@dataclass
class Sammantradesplan:
    """Ett organs sammanträdesplan så som sidan visar den: de år sidan har tabeller för, och raderna."""

    organ: str
    url: str
    ar: list[int]
    rader: list[Planrad] = field(default_factory=list)
    fel: list[str] = field(default_factory=list)  # rader med text som inte kändes igen


_TABELL = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
_RAD = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
_CELL = re.compile(r"<t[dh]\b.*?</t[dh]>", re.IGNORECASE | re.DOTALL)
_CAPTION = re.compile(r"<caption\b.*?</caption>", re.IGNORECASE | re.DOTALL)
_AR = re.compile(r"\b(20\d{2})\b")
_TID = re.compile(r"\b(\d{1,2})[.:](\d{2})\b")
_INSTALLT = re.compile(r"^inställ(?:t|d|da)$", re.IGNORECASE)
_STALLS_IN = re.compile(r"\(?\s*(\d{1,2})\s*/\s*(\d{1,2})\s+ställs\s+in\s*\)?", re.IGNORECASE)
_OBS_TID = re.compile(r"^obs[!:.]?\s*(?:ny\s+)?tid(?:en)?\s*[:.]?\s*(?:kl\.?\s*)?(\d{1,2})[.:](\d{2})$", re.IGNORECASE)
_TOM = {"", "-", "–", "—"}


def _text(cell: str) -> str:
    text = re.sub(r"<br\b[^>]*>", " ", cell, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return " ".join(text.replace("\xa0", " ").split())


def _ar(tabell: str, fore: str) -> int | None:
    """Tabellens år: ur rubriken i tabellen, annars ur den närmast föregående texten (t.ex. en h2)."""
    if m := _CAPTION.search(tabell):
        if ar := _AR.findall(_text(m[0])):
            return int(ar[-1])
    ar = _AR.findall(_text(fore[-800:]))
    return int(ar[-1]) if ar else None


def _tid(m: re.Match) -> str:
    return f"{int(m[1]):02d}:{m[2]}"


def _tolka_tid(text: str) -> tuple[str | None, bool, str | None]:
    """Tid-kolumnen → (starttid, inställt, okänd text)."""
    if text in _TOM:
        return None, False, None
    if _INSTALLT.match(text):
        return None, True, None
    if m := re.fullmatch(r"(?:kl\.?\s*)?(\d{1,2})[.:](\d{2})", text, re.IGNORECASE):
        return _tid(m), False, None
    if m := _OBS_TID.match(text):
        return _tid(m), False, None
    m = _TID.search(text)
    return (_tid(m) if m else None), False, text


def _tolka_datum(text: str, manad: int) -> tuple[list[int], list[tuple[int, int]], bool, str | None]:
    """Datum-kolumnen → (dagar, inställda (dag, månad), hela månaden inställd, okänd text)."""
    if text in _TOM:
        return [], [], False, None
    if _INSTALLT.match(text):
        return [], [], True, None
    installda = [(int(d), int(m)) for d, m in _STALLS_IN.findall(text)]
    rest = _STALLS_IN.sub(" ", text)
    dagar: list[int] = []
    okant: list[str] = []
    for del_ in re.split(r",|\boch\b|&", rest):
        del_ = del_.strip(" .")
        if not del_:
            continue
        if del_.isdigit():
            dagar.append(int(del_))
        else:
            okant.append(del_)
    return dagar, installda, False, (", ".join(okant) or None)


def _datum(ar: int, manad: int, dag: int) -> date | None:
    try:
        return date(ar, manad, dag)
    except ValueError:
        return None


def tolka_tabell(organ: str, ar: int, tabell: str) -> tuple[list[Planrad], list[str]]:
    """Raderna i en tabell (Månad | Datum | Tid) → planerade sammanträden och fel för okänd text."""
    rader: list[Planrad] = []
    fel: list[str] = []
    for tr in _RAD.findall(tabell):
        celler = [_text(c) for c in _CELL.findall(tr)]
        if len(celler) < 2 or (manad := MANADER.get(celler[0].lower())) is None:
            continue  # rubrikraden eller en rad utan månad
        datumtext, tidtext = celler[1], (celler[2] if len(celler) > 2 else "")
        kalltext = " | ".join(celler)
        dagar, installda, hela_installd, okant_datum = _tolka_datum(datumtext, manad)
        starttid, tid_installd, okant_tid = _tolka_tid(tidtext)
        okant = "; ".join(t for t in (okant_datum, okant_tid) if t) or None
        if okant:
            fel.append(f"{ORGAN[organ].namn} {ar}, {celler[0].lower()}: texten \"{kalltext}\" känns inte igen")
        status = "installt" if tid_installd else "planerat"
        for dag in dagar:
            if (d := _datum(ar, manad, dag)) is None:
                fel.append(f"{ORGAN[organ].namn} {ar}, {celler[0].lower()}: {dag} är inget datum")
                continue
            rader.append(Planrad(organ, ar, manad, d, starttid, status, okant, kalltext))
        for dag, m in installda:
            if (d := _datum(ar, m, dag)) is None:
                fel.append(f"{ORGAN[organ].namn} {ar}, {celler[0].lower()}: {dag}/{m} är inget datum")
                continue
            rader.append(Planrad(organ, ar, m, d, starttid, "installt", okant, kalltext))
        if hela_installd and not dagar:
            rader.append(Planrad(organ, ar, manad, None, None, "installt", okant, kalltext))
        elif okant and not dagar and not installda:
            # Text utan datum som inte känns igen: raden finns kvar som en anmärkning för månaden.
            rader.append(Planrad(organ, ar, manad, None, starttid, "planerat", okant, kalltext))
    return rader, fel


def tolka_sida(organ: str, url: str, sida: str) -> Sammantradesplan:
    """Alla tabeller med sammanträdesdagar på organets sida, med året ur rubriken."""
    plan = Sammantradesplan(organ=organ, url=url, ar=[])
    for m in _TABELL.finditer(sida):
        tabell = m[0]
        rubrik = [_text(c).lower() for c in _CELL.findall(_RAD.findall(tabell)[0])] if _RAD.search(tabell) else []
        if rubrik[:3] != ["månad", "datum", "tid"]:
            continue
        ar = _ar(tabell, sida[: m.start()])
        if ar is None:
            plan.fel.append(f"{ORGAN[organ].namn}: en tabell med sammanträdesdagar saknar år")
            continue
        rader, fel = tolka_tabell(organ, ar, tabell)
        plan.ar.append(ar)
        plan.rader.extend(rader)
        plan.fel.extend(fel)
    return plan


class Sammantradesplaner:
    """Sammanträdesplanerna för kommunfullmäktige, kommunstyrelsen och de tre nämnderna, med kallelserna
    som sidorna länkar till och fullmäktiges webbsändningar (se `kallelser`).

    `kanda_kallelser`: kallelser som redan är lästa (fylls i av insamlingen). De hämtas inte igen,
    eftersom Sitevision ger en fil en ny adress när den byts ut.
    """

    id = "harnosand-sammantradesplaner"
    titel = "Härnösands kommun – sammanträdesplaner, kallelser och webb-tv"
    url = urljoin(BAS, "/kommun--styrning/politik-och-demokrati.html")

    def __init__(self, anrop_per_sekund: float | None = 2.0) -> None:
        self.anrop_per_sekund = anrop_per_sekund
        self.kanda_kallelser: set[str] = set()

    def _kallelser(self, client: httpx.Client, organ: str, sida: str, resultat: Hamtning) -> None:
        for k in kallelsemodul.kallelser_pa_sidan(organ, sida):
            if (k.typ != "handlingar" and k.url not in self.kanda_kallelser and k.storlek is not None
                    and k.storlek <= kallelsemodul.MAX_STORLEK_FOR_PLATS):
                try:
                    pdf = client.get(k.url)
                    pdf.raise_for_status()
                    k = kallelsemodul.las_kallelse(k, pdf.content)
                except httpx.HTTPError as e:
                    resultat.fel.append(f"{k.titel}: {type(e).__name__}: {e}")
            resultat.kallelser.append(k)

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        resultat = Hamtning()
        for organ in ORGAN.values():
            url = urljoin(BAS, organ.sida)
            try:
                svar = client.get(url)
                svar.raise_for_status()
            except httpx.HTTPError as e:
                resultat.fel.append(f"{organ.namn}: {type(e).__name__}: {e}")
                continue
            plan = tolka_sida(organ.id, url, svar.text)
            if not plan.ar:
                resultat.fel.append(f"{organ.namn}: sidan har ingen tabell med sammanträdesdagar")
                continue
            resultat.fel.extend(plan.fel)
            resultat.sammantradesplaner.append(plan)
            self._kallelser(client, organ.id, svar.text, resultat)
        try:
            svar = client.get(kallelsemodul.WEBB_TV)
            svar.raise_for_status()
            resultat.webbsandningar = kallelsemodul.webbsandningar(svar.text)
            if not resultat.webbsandningar:
                resultat.fel.append("Webb-tv: sidan har inga länkar till sammanträden")
        except httpx.HTTPError as e:
            resultat.fel.append(f"Webb-tv: {type(e).__name__}: {e}")
        if not resultat.sammantradesplaner:
            raise httpx.HTTPError("Ingen sammanträdesplan kunde läsas: " + "; ".join(resultat.fel))
        return resultat
