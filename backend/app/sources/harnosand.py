"""Härnösands kommun (harnosand.se): protokoll från de beslutande organen.

Varje organs sida listar innevarande års protokoll som PDF-länkar. Under rubriken
"… arkiverade protokoll" finns en mapp per år (Sitevision, `?folder=…`) med äldre protokoll.
Tolkningen görs när protokollet lagras (se `app.protokoll`), inte här.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urljoin

import httpx

from .base import Dokument, Hamtning

BAS = "https://harnosand.se"
POLITIK = "/kommun--styrning/politik-och-demokrati"


@dataclass(frozen=True)
class Organ:
    id: str
    namn: str
    sida: str  # sökväg på harnosand.se
    # Organets namn som det står i protokollens filnamn, i gemener ("skolnämnd" täcker "skolnämnden").
    filnamn: str


ORGAN = {
    o.id: o
    for o in (
        Organ("KF", "Kommunfullmäktige", f"{POLITIK}/kommunfullmaktige.html", "kommunfullmäktige"),
        Organ("KS", "Kommunstyrelsen", f"{POLITIK}/kommunstyrelse.html", "kommunstyrelsen"),
        Organ("SAM", "Samhällsnämnden", f"{POLITIK}/namnder/samhallsnamnden.html", "samhällsnämnden"),
        Organ("SOC", "Socialnämnden", f"{POLITIK}/namnder/socialnamnden.html", "socialnämnden"),
        Organ("SKOL", "Skolnämnden", f"{POLITIK}/namnder/skolnamnden.html", "skolnämnd"),
    )
}

# Beslutsnivå: nämnderna bereder åt kommunstyrelsen, som bereder åt kommunfullmäktige.
NIVA = {"SAM": 0, "SOC": 0, "SKOL": 0, "KS": 1, "KF": 2}


def organ_ref(organ_id: str) -> dict:
    """Organet som det visas i API:t: {"id", "namn"}. Ett okänt organ får sitt id som namn."""
    o = ORGAN.get(organ_id)
    return {"id": organ_id, "namn": o.namn if o else organ_id}

# Utskott och beredningar är egna organ och ingår inte (kravspec avsnitt 18).
_ANNAT_ORGAN = re.compile(r"utskott|beredning", re.IGNORECASE)
_PARAGRAFPROTOKOLL = re.compile(r"§|direktjuster|omedelbar justering|utdrag", re.IGNORECASE)
_LANK = re.compile(r'href="(/download/[^"]+\.pdf)"', re.IGNORECASE)
_MAPP = re.compile(r'href="([^"]*\?folder=([0-9a-f.]+)&(?:amp;)?sv\.url=([0-9a-f.]+))"[^>]*>\s*([^<]*?)\s*</a>')


def dokumenttyp(filnamn: str, organ: Organ) -> str | None:
    """'protokoll', 'paragrafprotokoll' eller None om filen inte är ett protokoll från organet."""
    namn = " ".join(filnamn.lower().split())
    if "protokoll" not in namn or organ.filnamn not in namn or _ANNAT_ORGAN.search(namn):
        return None
    return "paragrafprotokoll" if _PARAGRAFPROTOKOLL.search(namn) else "protokoll"


def _filer(avsnitt: str, organ: Organ) -> list[tuple[str, str, str]]:
    """(url, filnamn, typ) för protokollen i ett avsnitt av en sida, i sidans ordning och utan dubbletter."""
    sett: dict[str, tuple[str, str, str]] = {}
    for href in _LANK.findall(avsnitt):
        href = html.unescape(href)
        filnamn = unquote(href.rsplit("/", 1)[-1])
        if typ := dokumenttyp(filnamn, organ):
            url = urljoin(BAS, href)
            sett.setdefault(url, (url, filnamn, typ))
    return list(sett.values())


def _portlet(sida: str, portlet_id: str) -> str:
    """Innehållet i en Sitevision-portlet (filmappens lista), fram till listans slut."""
    i = sida.find(f'id="svid{portlet_id.replace(".", "_")}"')
    if i < 0:
        return ""
    avsnitt = sida[i:]
    slut = avsnitt.find("</ul>")
    return avsnitt[: slut if slut >= 0 else None]


def arkivmappar(sida: str) -> list[tuple[int, str]]:
    """(år, adress) för årsmapparna under rubriken med arkiverade protokoll."""
    # Rubriken är ett h2 på vissa sidor och fetstil i ett stycke på andra.
    m = re.search(r"arkiverade protokoll", sida, re.IGNORECASE)
    if not m:
        return []
    efter = sida[m.end() :]
    nasta = re.search(r"arkiverade (?!protokoll)", efter, re.IGNORECASE)  # t.ex. "arkiverade handlingar"
    efter = efter[: nasta.start() if nasta else None]
    mappar: list[tuple[int, str]] = []
    for href, mapp, portlet, etikett in _MAPP.findall(efter):
        ar = re.search(r"(20\d{2})", etikett)
        if not ar:
            continue
        stig = html.unescape(href).split("?", 1)[0].split(";", 1)[0]  # utan jsessionid
        mappar.append((int(ar[1]), f"{urljoin(BAS, stig)}?folder={mapp}&sv.url={portlet}"))
    return mappar


class Protokollkalla:
    """Protokoll från ett organ. En instans per organ, så att varje organ har en egen kontroll.

    `arkiv_fran`: första året i arkivet som hämtas (None = bara innevarande år på organets sida).
    `urval`: högst så många protokoll per sida och årsmapp (för inspelningar och test, None = alla).
    `kanda_dokument`: adresser som redan är hämtade (fylls i av insamlingen). Arkivets filer hämtas
    bara en gång, eftersom Sitevision ger en fil en ny adress när den byts ut. Protokollen på
    organets sida hämtas varje gång, så att ändrat innehåll under samma adress upptäcks.
    """

    def __init__(
        self,
        organ: str,
        arkiv_fran: int | None = 2022,
        urval: int | None = None,
        anrop_per_sekund: float | None = 2.0,
    ) -> None:
        self.organ = ORGAN[organ]
        self.id = f"harnosand-protokoll-{organ.lower()}"
        self.titel = f"Härnösands kommun – protokoll, {self.organ.namn.lower()}"
        self.url = urljoin(BAS, self.organ.sida)
        self.arkiv_fran = arkiv_fran
        self.urval = urval or None
        self.anrop_per_sekund = anrop_per_sekund
        self.kanda_dokument: set[str] = set()

    def _lista(self, client: httpx.Client) -> tuple[list[tuple[str, str, str]], set[str], list[str]]:
        svar = client.get(self.url)
        svar.raise_for_status()
        sida = svar.text
        aktuella = _filer(re.split(r"arkiverade protokoll", sida, maxsplit=1, flags=re.IGNORECASE)[0],
                          self.organ)[: self.urval]
        filer = list(aktuella)
        fel: list[str] = []
        if self.arkiv_fran is not None:
            for ar, url in arkivmappar(sida):
                if ar < self.arkiv_fran:
                    continue
                try:
                    mapp = client.get(url)
                    mapp.raise_for_status()
                except httpx.HTTPError as e:
                    fel.append(f"Arkivet {ar}: {type(e).__name__}: {e}")
                    continue
                portlet = url.rsplit("sv.url=", 1)[-1]
                filer.extend(_filer(_portlet(mapp.text, portlet), self.organ)[: self.urval])
        unika = list({f[0]: f for f in filer}.values())
        return unika, {f[0] for f in aktuella}, fel

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        filer, aktuella, fel = self._lista(client)
        resultat = Hamtning(fel=fel)
        att_hamta = [f for f in filer if f[0] in aktuella or f[0] not in self.kanda_dokument]
        for url, filnamn, typ in att_hamta:
            try:
                pdf = client.get(url)
                pdf.raise_for_status()
                resultat.dokument.append(Dokument(url=url, filnamn=filnamn, typ=typ, organ=self.organ.id,
                                                  innehall=pdf.content))
            except httpx.HTTPError as e:
                resultat.fel.append(f"{filnamn}: {type(e).__name__}: {e}")
        if att_hamta and not resultat.dokument:
            raise httpx.HTTPError(f"Inget av {len(att_hamta)} protokoll kunde hämtas")
        return resultat
