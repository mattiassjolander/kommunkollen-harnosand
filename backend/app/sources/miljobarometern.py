"""Aktuell Hållbarhets kommunrankning "Sveriges miljöbästa kommun" (#66), https://kommunrankning.miljobarometern.se.

Rankningen presenteras med Miljöbarometern. Två sidor per kommun:

- `/resultat/placering/<kommun>/table`: placeringen år för år, som en tabell (samma uppgifter som Excelexporten).
- `/resultat/<kommun>/`: det senaste årets resultat, med placering av antal kommuner, totalpoäng, poäng per
  område och poäng per indikator (enkätfrågor, extern data och klimatdata).

Poängen per indikator finns bara för det senaste året. Den sparas vid varje insamling, så att historiken byggs
upp framåt. Inga användarvillkor har hittats. Källan anges alltid.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import quote

import httpx

from ..rankningar import KOMMUNER, Delmatt, Placering, Rankning, Rankningsdata
from .base import Hamtning

BAS = "https://kommunrankning.miljobarometern.se"

RANKNING = Rankning(
    id="miljobasta-kommun",
    titel="Sveriges miljöbästa kommun",
    avsandare="Aktuell Hållbarhet",
    avsandartyp="Tidning om miljö och hållbarhet",
    beskrivning=(
        "Aktuell Hållbarhet rankar kommunerna efter poäng i tre områden: en enkät till kommunerna om deras "
        "miljö- och klimatarbete, extern data från bland annat SCB, Naturvårdsverket och Avfall Sverige, och "
        "klimatdata om utsläpp. Rankningen presenteras i samarbete med Miljöbarometern. Poängen per indikator "
        "publiceras bara för det senaste året, så plattformen sparar den varje år."
    ),
    url=BAS,
    metod_url=f"{BAS}/om-webbplatsen/",
    villkor=(
        "Uppgifterna hämtas från kommunrankning.miljobarometern.se. Inga användarvillkor har hittats på "
        "webbplatsen. Källan anges alltid."
    ),
)


class Formatfel(ValueError):
    pass


def slug(kommun: str) -> str:
    """Kommunens namn i adressen, t.ex. "Östra Göinge" → "östra-göinge"."""
    return kommun.lower().replace(" ", "-")


def placeringssida(kommun: str) -> str:
    return f"{BAS}/resultat/placering/{quote(slug(kommun))}/table"


def resultatsida(kommun: str) -> str:
    return f"{BAS}/resultat/{quote(slug(kommun))}/"


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _tal(s: str) -> Decimal | None:
    s = s.strip().replace("−", "-").replace(",", ".").replace("\xa0", "").replace(" ", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def tolka_placeringar(html: str, kommun: str) -> dict[int, int]:
    """Placeringen per år ur tabellen "Placering" (kolumnerna Datum och Värde)."""
    kolumner = re.findall(r'<th id="mbDataTable-(\w+)"', html)
    tbody = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if "date" not in kolumner or "value" not in kolumner or tbody is None:
        raise Formatfel(f"Placeringssidan för {kommun} har ändrat format: tabellen med Datum och Värde saknas")
    i_ar, i_varde = kolumner.index("date"), kolumner.index("value")
    ut = {}
    for rad in re.findall(r"<tr>(.*?)</tr>", tbody.group(1), re.S):
        celler = re.findall(r'<td data-mb-value="([^"]*)"', rad)
        if len(celler) != len(kolumner):
            continue
        ar, varde = unescape(celler[i_ar]).strip(), unescape(celler[i_varde]).strip()
        if re.fullmatch(r"\d{4}", ar) and re.fullmatch(r"\d+", varde):
            ut[int(ar)] = int(varde)
    if not ut:
        raise Formatfel(f"Placeringssidan för {kommun} har ändrat format: inga placeringar i tabellen")
    return ut


def _poang(varde: str) -> tuple[Decimal | None, str | None]:
    """"Jaᆞ1 poäng" → (1, "Ja"), "0,42 poäng" → (0.42, None), "Delvisᆞ0,2 p" → (0.2, "Delvis")."""
    svar = None
    if "ᆞ" in varde:
        svar, varde = (d.strip() for d in varde.split("ᆞ", 1))
    m = re.match(r"\s*(-?[\d\s.,−]+?)\s*(poäng|p)?\s*$", varde)
    return (_tal(m.group(1)) if m else None), svar


def tolka_resultat(html: str, kommun: str, url: str) -> tuple[Placering, list[Delmatt]]:
    """Det senaste årets placering, totalpoäng och delmått ur kommunens resultatsida."""
    text = _text(html)
    m = re.search(r"plats (\d+) av (\d+)", text)
    total = re.search(r"Totalpoäng (\d{4}): ([\d,.]+) \(max ([\d,.]+)\)", text)
    if not m or not total:
        raise Formatfel(f"Resultatsidan för {kommun} har ändrat format: placeringen eller totalpoängen saknas")
    ar = int(total.group(1))
    placering = Placering(kommun, ar, int(m.group(1)), url, antal=int(m.group(2)), poang=_tal(total.group(2)),
                          max_poang=_tal(total.group(3)))
    delmatt = []
    for namn, varde, maxv in re.findall(r"varav ([^:]+?): (-?[\d,.]+) \(max ([\d,.]+)\)", text):
        namn = namn.strip()
        delmatt.append(Delmatt(kommun, ar, f"omrade:{namn}", f"{namn[:1].upper()}{namn[1:]} (max {maxv} poäng)",
                               "Poäng per område", "poäng", url, varde=_tal(varde)))
    for grupp_html in re.split(r'<div class="ItemGroup', html)[1:]:
        titel = re.search(r'<h2 class="Title">(.*?)</h2>', grupp_html, re.S)
        grupp = _text(titel.group(1)) if titel else ""
        for item in re.split(r'<div id="mbItem\d+" class="Item Indicator', grupp_html)[1:]:
            namn = re.search(r'<h3 class="Caption">(.*?)</h3>', item, re.S)
            nr = re.search(r'<span class="mb-sgn-nr">(.*?)</span>', item, re.S)
            varde = re.search(r'<span class="Value">(.*?)</span>', item, re.S)
            info = re.search(r'<span class="Info">\s*(\d{4})\s*</span>', item)
            if not (namn and nr and varde) or grupp == "Placering":
                continue
            if info and int(info.group(1)) != ar:
                continue  # en indikator som inte har något värde för året
            poang, svar = _poang(_text(varde.group(1)))
            delmatt.append(Delmatt(kommun, ar, _text(nr.group(1)), _text(namn.group(1)), grupp, "poäng", url,
                                   varde=poang, svar=svar))
    if len(delmatt) <= 3:
        raise Formatfel(f"Resultatsidan för {kommun} har ändrat format: indikatorerna saknas")
    return placering, delmatt


class Miljobarometern:
    id = "miljobasta-kommun"
    titel = "Sveriges miljöbästa kommun"
    url = BAS

    def __init__(self, kommuner=KOMMUNER, anrop_per_sekund: float | None = 1.0) -> None:
        self.kommuner = kommuner
        self.anrop_per_sekund = anrop_per_sekund

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        resultat = Hamtning()
        data = Rankningsdata(RANKNING)
        lyckade = 0
        for kommun in self.kommuner:
            try:
                s = client.get(placeringssida(kommun))
                s.raise_for_status()
                placeringar = tolka_placeringar(s.text, kommun)
                lyckade += 1
            except (httpx.HTTPError, Formatfel) as e:
                resultat.fel.append(f"Placeringar för {kommun}: {e}")
                placeringar = {}
            senaste = None
            try:
                s = client.get(resultatsida(kommun))
                s.raise_for_status()
                senaste, delmatt = tolka_resultat(s.text, kommun, resultatsida(kommun))
                data.delmatt += delmatt
                lyckade += 1
            except (httpx.HTTPError, Formatfel) as e:
                resultat.fel.append(f"Resultat för {kommun}: {e}")
            for ar, p in sorted(placeringar.items()):
                if senaste is not None and senaste.ar == ar:
                    continue
                data.placeringar.append(Placering(kommun, ar, p, placeringssida(kommun)))
            if senaste is not None:
                data.placeringar.append(senaste)
        if not lyckade:
            raise Formatfel("; ".join(resultat.fel))
        resultat.rankningar.append(data)
        return resultat
