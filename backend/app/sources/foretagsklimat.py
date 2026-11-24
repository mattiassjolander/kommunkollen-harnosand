"""Svenskt Näringslivs ranking av det lokala företagsklimatet (#66), https://www.foretagsklimat.se.

Tre Excelfiler med alla kommuner och alla år länkas från sidan "Ladda ner data":

- `Rankingresultat.xlsx`: placeringen per kommun, faktor och år. Faktorn "Totalranking" är rankningen,
  de övriga är delmåtten (frågorna i enkäten och statistikfaktorerna).
- `Enkätresultat.xlsx`: enkätsvaren per kommun, fråga, delserie (företagare eller politiker) och alternativ.
  Delmåttets värde är företagarnas medelbetyg (alternativet tomt), riket står som "Sverige".
- `Statistikfaktorer.xlsx`: värdena för statistikfaktorerna, också med "Sverige".

Adresserna innehåller ett id som kan ändras, så länkarna hittas via länktexten på sidan.

Användarvillkor: källan ska alltid anges, och enkätsvaren för ett år får inte användas till en egen rankning
innan Svenskt Näringsliv har publicerat sin. Plattformen räknar ingen egen rankning, och sparar dessutom bara
enkätsvar för år där Svenskt Näringslivs totalranking finns i filen.
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from html import unescape
from urllib.parse import urljoin

import httpx
import openpyxl

from ..rankningar import KOMMUNER, Delmatt, Placering, Rankning, Rankningsdata
from .base import Hamtning

SIDA = "https://www.foretagsklimat.se/ladda-ner/"
FILER = {"ranking": "Rankingresultat.xlsx", "enkat": "Enkätresultat.xlsx", "statistik": "Statistikfaktorer.xlsx"}
TOTAL = "Totalranking"
RIKET = "Sverige"

RANKNING = Rankning(
    id="foretagsklimat",
    titel="Lokalt företagsklimat",
    avsandare="Svenskt Näringsliv",
    avsandartyp="Arbetsgivar- och näringslivsorganisation",
    beskrivning=(
        "Svenskt Näringsliv rankar kommunerna efter företagsklimatet, så som det beskrivs i en enkät till "
        "företagare och politiker i varje kommun och i statistik om bland annat företagande, arbetsmarknad och "
        "kommunalskatt. Delmåtten är enkätens frågor, med företagarnas medelbetyg, och statistikfaktorerna. "
        "Varje delmått har en egen placering."
    ),
    url="https://www.foretagsklimat.se",
    metod_url="https://www.foretagsklimat.se/om-foretagsklimat/metod-for-rankingen/",
    villkor=(
        "Uppgifterna laddas ner från foretagsklimat.se. Enligt Svenskt Näringslivs användarvillkor får de användas "
        "för analys av enskilda kommuner och jämförelse med andra kommuner, och källan ska alltid anges. "
        "Enkätsvaren för ett år får inte användas till en egen rankning innan Svenskt Näringsliv har publicerat "
        "sin. Plattformen räknar ingen egen rankning och visar bara enkätsvar för år som Svenskt Näringsliv redan "
        "har rankat."
    ),
)


class Formatfel(ValueError):
    pass


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def hitta_lankar(html: str, bas: str = SIDA) -> dict[str, str]:
    """Filernas adresser, hittade via länktexten (t.ex. "Rankingresultat.xlsx")."""
    lankar = {}
    for m in re.finditer(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        text = _nfc(unescape(re.sub(r"<[^>]+>", " ", m.group(2))))
        for nyckel, namn in FILER.items():
            if text.lower() == namn.lower() and nyckel not in lankar:
                lankar[nyckel] = urljoin(bas, unescape(m.group(1)))
    return lankar


def _ar(v) -> int | None:
    s = str(v).strip() if v is not None else ""
    return int(s) if re.fullmatch(r"(19|20)\d\d", s) else None


def _las(innehall: bytes, fil: str, kolumner: tuple[str, ...]):
    """Läser Excelfilens första blad. Returnerar kolumnernas index, årens index och raderna."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(innehall), read_only=True, data_only=True)
    except Exception as e:  # zipfile.BadZipFile, KeyError m.fl. när filen inte är en Excelfil
        raise Formatfel(f"{fil} gick inte att läsa som Excelfil ({type(e).__name__})") from e
    rader = wb.worksheets[0].iter_rows(values_only=True)
    rubrik = [_nfc(str(c)) if c is not None else "" for c in next(rader, ())]
    saknas = [k for k in kolumner if k not in rubrik]
    ar = {i: a for i, c in enumerate(rubrik) if (a := _ar(c))}
    if saknas or not ar:
        raise Formatfel(f"{fil} har ändrat format: " + (
            f"kolumnen {', '.join(saknas)} saknas" if saknas else "inga årskolumner"))
    return {k: rubrik.index(k) for k in kolumner}, ar, rader


def _decimal(v) -> Decimal | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        # Filerna har binära flyttal med 15–17 siffror. Tolv decimaler räcker och ger stabila jämförelser.
        return Decimal(repr(v)).quantize(Decimal("1e-12")).normalize() if isinstance(v, float) else Decimal(v)
    try:
        return Decimal(str(v).replace(",", ".").strip())
    except Exception:
        return None


def _placering(v) -> int | None:
    d = _decimal(v)
    return int(d) if d is not None and d == d.to_integral_value() and d > 0 else None


def tolka_ranking(innehall: bytes, kommuner=KOMMUNER):
    """Placeringarna per (kommun, faktor, år) för de valda kommunerna, och antalet rankade kommuner per år.

    En faktor där alla kommuner har plats 1 ett år (flervalsfrågor som inte rankas) räknas inte som delmått.
    """
    k, ar, rader = _las(innehall, FILER["ranking"], ("Kommun", "Faktor"))
    placeringar: dict[tuple[str, str, int], int] = {}
    antal: dict[int, int] = {}
    alla_ettor: dict[tuple[str, int], bool] = {}
    for rad in rader:
        kommun, faktor = rad[k["Kommun"]], rad[k["Faktor"]]
        if not kommun or not faktor:
            continue
        kommun, faktor = _nfc(str(kommun)), _nfc(str(faktor))
        for i, a in ar.items():
            p = _placering(rad[i]) if i < len(rad) else None
            if p is None:
                continue
            if faktor == TOTAL:
                antal[a] = antal.get(a, 0) + 1
            alla_ettor[(faktor, a)] = alla_ettor.get((faktor, a), True) and p == 1
            if kommun in kommuner:
                placeringar[(kommun, faktor, a)] = p
    if not antal:
        raise Formatfel(f"{FILER['ranking']} har ändrat format: faktorn {TOTAL} saknas")
    placeringar = {n: p for n, p in placeringar.items() if n[1] == TOTAL or not alla_ettor[(n[1], n[2])]}
    return placeringar, antal


def tolka_varden(innehall: bytes, fil: str, kommuner=KOMMUNER) -> dict[tuple[str, str, int], Decimal]:
    """Värdena per (kommun eller "Sverige", faktor, år).

    Enkäten: företagarnas medelbetyg (delserie "Företagare", alternativet tomt).
    Statistiken: värdet när faktorn bara har en delserie. Har den flera går det inte att säga vilken som ligger
    till grund för placeringen, och då sparas bara placeringen.
    """
    enkat = fil == FILER["enkat"]
    kolumner = ("Kommun", "Faktor", "Delserie", "Alternativ") if enkat else ("Kommun", "Faktor", "Delserie")
    k, ar, rader = _las(innehall, fil, kolumner)
    varden: dict[tuple[str, str, int], Decimal] = {}
    delserier: dict[tuple[str, str], set[str]] = {}
    for rad in rader:
        kommun, faktor = rad[k["Kommun"]], rad[k["Faktor"]]
        if not kommun or not faktor:
            continue
        kommun, faktor = _nfc(str(kommun)), _nfc(str(faktor))
        if kommun != RIKET and kommun not in kommuner:
            continue
        delserie = _nfc(str(rad[k["Delserie"]] or ""))
        if enkat:
            if delserie != "Företagare" or _nfc(str(rad[k["Alternativ"]] or "")):
                continue
        else:
            delserier.setdefault((kommun, faktor), set()).add(delserie)
        for i, a in ar.items():
            v = _decimal(rad[i]) if i < len(rad) else None
            if v is not None:
                varden[(kommun, faktor, a)] = v
    if not enkat:
        varden = {n: v for n, v in varden.items() if len(delserier[(n[0], n[1])]) == 1}
    return varden


class Foretagsklimat:
    id = "foretagsklimat"
    titel = "Lokalt företagsklimat"
    url = SIDA

    def __init__(self, kommuner=KOMMUNER, anrop_per_sekund: float | None = 1.0) -> None:
        self.kommuner = kommuner
        self.anrop_per_sekund = anrop_per_sekund

    def hamta(self, client: httpx.Client, sedan: datetime | None) -> Hamtning:
        svar = client.get(SIDA)
        svar.raise_for_status()
        lankar = hitta_lankar(svar.text, str(svar.url))
        resultat = Hamtning()
        saknade = [namn for nyckel, namn in FILER.items() if nyckel not in lankar]
        if len(saknade) == len(FILER):
            raise Formatfel(f"Sidan {SIDA} har ändrat format: länkarna till Excelfilerna saknas")
        resultat.fel += [f"Länken till {namn} saknas på sidan {SIDA}" for namn in saknade]

        def las(nyckel, tolka):
            if nyckel not in lankar:
                return None
            try:
                s = client.get(lankar[nyckel])
                s.raise_for_status()
                return tolka(s.content)
            except (httpx.HTTPError, Formatfel) as e:
                resultat.fel.append(f"{FILER[nyckel]}: {e}")
                return None

        ranking = las("ranking", lambda b: tolka_ranking(b, self.kommuner))
        enkat = las("enkat", lambda b: tolka_varden(b, FILER["enkat"], self.kommuner))
        statistik = las("statistik", lambda b: tolka_varden(b, FILER["statistik"], self.kommuner))
        bada = enkat is not None and statistik is not None
        enkat, statistik = enkat or {}, statistik or {}
        enkatfaktorer = {n[1] for n in enkat}
        statistikfaktorer = {n[1] for n in statistik}
        if ranking is None:
            if len(resultat.fel) >= len(FILER):
                raise Formatfel("; ".join(resultat.fel))
            # Utan rankingfilen går det inte att veta vilka år Svenskt Näringsliv har publicerat, så inga
            # enkätsvar sparas (användarvillkoren). Statistiken saknar placering och sparas inte heller.
            resultat.rankningar.append(Rankningsdata(RANKNING))
            return resultat
        placeringar, antal = ranking
        publicerade = max(antal)

        data = Rankningsdata(RANKNING)
        for (kommun, faktor, ar), p in sorted(placeringar.items()):
            if faktor == TOTAL:
                data.placeringar.append(Placering(kommun, ar, p, lankar["ranking"], antal=antal.get(ar)))
                continue
            if faktor in enkatfaktorer:
                if ar > publicerade:
                    continue
                kalla, grupp, enhet, varden = "enkat", "Enkät", "medelbetyg", enkat
            elif faktor in statistikfaktorer:
                kalla, grupp, enhet, varden = "statistik", "Statistik", "", statistik
            elif bada:
                # Faktorn finns bara i rankingfilen. Enkätfrågor känns igen på frågetecknet.
                kalla, grupp, enhet, varden = ("enkat", "Enkät", "medelbetyg", {}) if faktor.endswith("?") \
                    else ("ranking", "Statistik", "", {})
            else:
                # En av filerna gick inte att hämta, så det går inte att säga vilken sorts faktor det är.
                # Det sparade lämnas orört (None).
                kalla, grupp, enhet, varden = "ranking", None, None, {}
            data.delmatt.append(Delmatt(
                kommun, ar, faktor, faktor, grupp, enhet, lankar.get(kalla, lankar["ranking"]),
                varde=varden.get((kommun, faktor, ar)), riksvarde=varden.get((RIKET, faktor, ar)), placering=p,
            ))
        resultat.rankningar.append(data)
        return resultat
