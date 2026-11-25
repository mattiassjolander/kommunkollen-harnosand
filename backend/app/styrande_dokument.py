"""Kommunens styrande dokument (#63): lagring, dokumentinformation, giltighet och koppling till beslutet.

Begreppen finns i GLOSSARY.md, avsnitt Styrande dokument.

**Så känns ett dokument igen** när listan på kommunens sida lagras:

(a) Samma Sitevision-id (`18.<id>`) är samma dokument. En ny tidsstämpel i länken ger en ny version, om filen har
    ändrats.
(b) Ett nytt id med samma filnamn i samma kategori som ett dokument som försvann i samma kontroll är en ny version av
    det dokumentet. Båda fallen finns: samhällsnämndens delegationsordning har behållit id:t, och det gemensamma
    reglementet har fått ett nytt.

Allt annat är ett nytt dokument. Ett dokument som inte längre står på sidan märks borttaget med datum och sparas.

**Dokumentinformationen** läses ur rutan på första sidan och återges som den står. Fält som saknas är None.

**Giltigheten** räknas när dokumentet läses: utgånget när "Giltig t o m" har passerats, annars när perioden i titeln
(t.ex. 2017–2020) har passerats, till och med 31 december det sista året. "Giltig t o m" går före titeln.

**Kopplingen till beslutet** görs när organet, datumet och diarienumret i dokumentinformationen stämmer exakt med en
behandling i protokollen, efter att diarienumret har normaliserats (`KS 2022/415` = `KS/2022-415`).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

import psycopg
from psycopg.types.json import Jsonb

from . import protokolltolkning
from .sources.harnosand import ORGAN, organ_ref
from .sources.styrande_dokument import SIDA, Dokumentlista, Lank

DATAKALLA = "harnosand-styrande-dokument"

# Fälten i rutan med dokumentinformation, i rutans ordning: (nyckel, etikett som reguljärt uttryck). Äldre dokument
# har en mall med "Fastställd av", "Dokumentansvarig" och "Övrig information".
FALT = (
    ("dokumentnamn", r"Dokumentnamn"),
    ("dokumenttyp", r"Dokumenttyp"),
    ("faststalld_av", r"Fastställd(?:\s*/\s*upprättad)?\s+av"),
    ("datum", r"Datum"),
    ("diarienummer", r"Diarienummer"),
    ("dokumentansvarig", r"Dokumentansvarig(?:\s*/\s*processägare)?"),
    ("version", r"Version"),
    ("senast_reviderad", r"Senast\s+reviderad"),
    ("giltig_tom", r"Giltig\s+t\s*\.?\s*o\s*\.?\s*m\.?"),
    ("dokumentinformation", r"Dokumentinformation"),
    ("galler_for", r"Dokumentet\s+gäller\s+för"),
    ("annan_information", r"(?:Annan|Övrig)\s+[Ii]nformation"),
)
_ETIKETT = re.compile("|".join(f"(?P<{n}>\\b{e}(?![a-zåäö]))" for n, e in FALT))


# Dokumentinformation

def las_dokumentinformation(forsta_sidan: str) -> dict:
    """Rutan på första sidan: {ruta: bool, <fält>: text eller None}.

    Rutan börjar med "Dokumentnamn" och står sist på sidan. Varje fält är texten mellan dess etikett och nästa.
    En etikett som står i fel ordning (t.ex. ordet "Version" i ett värde) räknas inte.
    """
    ut: dict = {"ruta": False, **{n: None for n, _ in FALT}}
    text = " ".join(forsta_sidan.split())
    start = re.search(r"\bDokumentnamn\b", text)
    if not start:
        return ut
    ut["ruta"] = True
    ruta = text[start.start():]
    traffar: list[tuple[str, int, int]] = []
    nasta_index = 0
    for m in _ETIKETT.finditer(ruta):
        namn = m.lastgroup
        index = next(i for i, (n, _) in enumerate(FALT) if n == namn)
        if index < nasta_index:
            continue
        traffar.append((namn, m.start(), m.end()))
        nasta_index = index + 1
    for i, (namn, _, slut) in enumerate(traffar):
        till = traffar[i + 1][1] if i + 1 < len(traffar) else len(ruta)
        varde = ruta[slut:till].strip(" :|")
        ut[namn] = varde or None
    return ut


_DATUM = re.compile(r"(?<!\d)((?:19|20)\d{2})-?(\d{2})-?(\d{2})(?!\d)")


def tolka_datum(text: str | None) -> date | None:
    """Ett datum som 2024-04-03 eller 20240403. Ett ofullständigt datum som "2023-" ger None."""
    if not text:
        return None
    m = _DATUM.search(text)
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


_TILLSVIDARE = re.compile(r"^\s*tills?\s*vidare\b", re.IGNORECASE)
_GALLER_FRAN = re.compile(r"Gäller\s+(?:från\s+och\s+med|fr\.?\s*o\.?\s*m\.?)\s+(\S+)", re.IGNORECASE)


def galler_fran(info: dict) -> date | None:
    m = _GALLER_FRAN.search(info.get("dokumentinformation") or "")
    return tolka_datum(m[1]) if m else None


def faststallt_organ(text: str | None) -> str | None:
    """Organets id när "Fastställd/upprättad av" börjar med ett av plattformens organ, t.ex. "Kommunfullmäktige § 8"."""
    if not text:
        return None
    t = text.lower()
    for o in ORGAN.values():
        if t.startswith(o.namn.lower()):
            return o.id
    return None


# Diarienummer

_DNR = re.compile(r"^\s*([A-ZÅÄÖ]{2,5})?\s*/?\s*((?:19|20)\d{2})\s*[-–/]\s*(\d{1,7})\s*$", re.IGNORECASE)


def normalisera_diarienummer(dnr: str | None, organ: str | None) -> tuple[str, int, int] | None:
    """(serie, år, nummer): `KS 2022/415`, `KS/2022-415` och `KS2022-000415` blir ('KS', 2022, 415).

    Ett nummer utan serie får organets serie, som i kopplingen av ärenden (KF och KS använder kommunstyrelsens).
    """
    if not dnr:
        return None
    m = _DNR.match(dnr)
    if not m:
        return None
    serie = (m[1] or "").upper() or ("KS" if organ in ("KS", "KF") else (organ or ""))
    return serie, int(m[2]), int(m[3])


# Giltighet

_PERIOD = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})(?!\d)")


def giltighet(titel: str, info: dict, borttagen: date | None, idag: date) -> dict:
    """{status: gallande | utganget | borttaget, kalla: dokumentinformationen | titeln | None, till: datum, text}."""
    if borttagen is not None:
        return {"status": "borttaget", "kalla": None, "till": None, "borttagen": borttagen.isoformat(),
                "text": f"Borttaget från kommunens sida {borttagen.isoformat()}."}
    tom = info.get("giltig_tom")
    till = tolka_datum(tom)
    if till is not None:
        status = "utganget" if till < idag else "gallande"
        text = f"Giltig t o m {till.isoformat()} enligt dokumentinformationen."
        if status == "utganget":
            text += " Dokumentet ligger kvar på kommunens sida."
        return {"status": status, "kalla": "dokumentinformationen", "till": till.isoformat(), "text": text}
    if tom and _TILLSVIDARE.match(tom):
        return {"status": "gallande", "kalla": "dokumentinformationen", "till": None,
                "text": "Giltig tills vidare enligt dokumentinformationen."}
    perioder = _PERIOD.findall(titel)
    if perioder:
        fran, sista = perioder[-1]
        till = date(int(sista), 12, 31)
        status = "utganget" if till < idag else "gallande"
        text = f"Perioden i titeln är {fran}–{sista}, giltig t o m {till.isoformat()}."
        if status == "utganget":
            text += " Dokumentet ligger kvar på kommunens sida."
        return {"status": status, "kalla": "titeln", "till": till.isoformat(), "text": text}
    return {"status": "gallande", "kalla": None, "till": None, "text": "Dokumentet anger ingen giltighetstid."}


# Lagring

def kanda_filer(conn: psycopg.Connection) -> set[str]:
    """Adresserna som redan är hämtade: varje versions adress och dokumentens senaste adress."""
    return {r["url"] for r in conn.execute(
        "SELECT url FROM styrande_dokument_version UNION SELECT url FROM styrande_dokument")}


def _las_text(pdf: bytes) -> tuple[list[str], bool, str | None]:
    try:
        lop, _, ocr = protokolltolkning.las_sidtexter(pdf, layout=False)
    except protokolltolkning.EjLasbar as e:
        return [], False, str(e)
    return [s.replace("\x00", "") for s in lop], ocr, None


def _ny_version(conn: psycopg.Connection, dokument_id: int, lank: Lank, innehall: bytes, korning_id: int,
                hamtad: datetime) -> bool:
    """Sparar filen som en ny version, om den skiljer sig från den senaste. True om en version sparades."""
    sha = hashlib.sha256(innehall).hexdigest()
    senaste = conn.execute(
        "SELECT id, version, sha256 FROM styrande_dokument_version WHERE dokument_id = %s ORDER BY version DESC LIMIT 1",
        (dokument_id,),
    ).fetchone()
    if senaste is not None and senaste["sha256"] == sha:
        return False
    sidor, ocr, textfel = _las_text(innehall)
    info = las_dokumentinformation(sidor[0] if sidor else "")
    if senaste is not None:
        conn.execute("UPDATE styrande_dokument_version SET ersatt = %s WHERE id = %s", (hamtad, senaste["id"]))
    conn.execute(
        """
        INSERT INTO styrande_dokument_version (dokument_id, version, url, sha256, storlek, innehall, hamtad, korning_id,
                                               sidor, ocr, textfel, dokumentinformation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (dokument_id, 1 if senaste is None else senaste["version"] + 1, lank.url, sha, len(innehall), innehall, hamtad,
         korning_id, sidor, ocr, textfel, Jsonb(info)),
    )
    return True


def lagra(conn: psycopg.Connection, lista: Dokumentlista, korning_id: int, hamtad: datetime, idag: date) -> dict:
    """Lagrar listan från en kontroll. Ger antal nya, ändrade och oförändrade dokument."""
    antal = {"nya": 0, "andrade": 0, "oforandrade": 0}
    for i, namn in enumerate(lista.kategorier):
        conn.execute(
            "INSERT INTO styrande_kategori (namn, ordning) VALUES (%s, %s) "
            "ON CONFLICT (namn) DO UPDATE SET ordning = EXCLUDED.ordning", (namn, i))
    alla = conn.execute("SELECT id, sitevision_id, url, filnamn, kategorier, borttagen FROM styrande_dokument").fetchall()
    per_id: dict[str, dict] = {}
    for d in sorted(alla, key=lambda d: (d["borttagen"] is not None, d["id"])):
        per_id.setdefault(d["sitevision_id"], d)
    matchade: dict[str, dict] = {}  # länkens adress -> dokumentet
    sedda: set[int] = set()
    # (a) Samma id.
    for lank in lista.lankar:
        d = per_id.get(lank.sitevision_id)
        if d is not None and d["id"] not in sedda:
            matchade[lank.url] = d
            sedda.add(d["id"])
    # (b) Nytt id, samma filnamn och kategori som ett dokument som försvann nu.
    forsvunna = [d for d in alla if d["id"] not in sedda and d["borttagen"] is None]
    for lank in lista.lankar:
        if lank.url in matchade:
            continue
        d = next((d for d in forsvunna if d["id"] not in sedda and d["filnamn"] == lank.filnamn
                  and set(d["kategorier"]) & set(lank.kategorier)), None)
        if d is not None:
            matchade[lank.url] = d
            sedda.add(d["id"])

    for lank in lista.lankar:
        d = matchade.get(lank.url)
        innehall = lista.filer.get(lank.url)
        if d is None:
            if innehall is None:
                continue  # en ny fil som inte gick att hämta försöks igen vid nästa kontroll
            dokument_id = conn.execute(
                """
                INSERT INTO styrande_dokument (sitevision_id, url, filnamn, titel, kategorier, forst_sedd, senast_sedd)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (lank.sitevision_id, lank.url, lank.filnamn, lank.titel, list(lank.kategorier), hamtad, hamtad),
            ).fetchone()["id"]
            _ny_version(conn, dokument_id, lank, innehall, korning_id, hamtad)
            antal["nya"] += 1
            continue
        andrad = d["borttagen"] is not None
        if innehall is not None:
            andrad |= _ny_version(conn, d["id"], lank, innehall, korning_id, hamtad)
        if innehall is not None or lank.url == d["url"]:
            # Adressen uppdateras bara när filen gick att hämta, så att en misslyckad hämtning görs om.
            conn.execute(
                """
                UPDATE styrande_dokument SET sitevision_id = %s, url = %s, filnamn = %s, titel = %s, kategorier = %s,
                    senast_sedd = %s, borttagen = NULL WHERE id = %s
                """,
                (lank.sitevision_id, lank.url, lank.filnamn, lank.titel, list(lank.kategorier), hamtad, d["id"]),
            )
        else:
            conn.execute("UPDATE styrande_dokument SET kategorier = %s, senast_sedd = %s, borttagen = NULL WHERE id = %s",
                         (list(lank.kategorier), hamtad, d["id"]))
        antal["andrade" if andrad else "oforandrade"] += 1

    borta = [d for d in alla if d["id"] not in sedda and d["borttagen"] is None]
    aktiva = sum(1 for d in alla if d["borttagen"] is None)
    if len(borta) > max(10, aktiva // 2):
        # Så många borttagna på en gång tyder på en ändrad sida. Kontrollen misslyckas och inget lagras.
        raise ValueError(f"{len(borta)} av {aktiva} styrande dokument saknas på sidan, sidan kan ha ändrats")
    for d in borta:
        conn.execute("UPDATE styrande_dokument SET borttagen = %s WHERE id = %s", (idag, d["id"]))
        antal["andrade"] += 1
    return antal


# Läsning

_SENASTE = """
    SELECT DISTINCT ON (dokument_id) dokument_id, id AS version_id, version, dokumentinformation, ocr
    FROM styrande_dokument_version ORDER BY dokument_id, version DESC
"""


def _faststallt(info: dict) -> dict:
    organ = faststallt_organ(info.get("faststalld_av"))
    d = tolka_datum(info.get("datum"))
    return {"text": info.get("faststalld_av"), "organ": organ_ref(organ) if organ else None,
            "datum": d.isoformat() if d else None}


def _beslut(conn: psycopg.Connection, info: dict) -> list[dict]:
    """Behandlingarna där organet, datumet och diarienumret stämmer exakt med dokumentinformationen."""
    organ = faststallt_organ(info.get("faststalld_av"))
    datum = tolka_datum(info.get("datum"))
    dnr = normalisera_diarienummer(info.get("diarienummer"), organ)
    if organ is None or datum is None or dnr is None:
        return []
    rader = conn.execute(
        """
        SELECT b.sammantrade_id, b.paragraf, b.rubrik, b.diarienummer, s.organ, s.datum
        FROM behandling b JOIN sammantrade s ON s.id = b.sammantrade_id
        WHERE s.organ = %s AND s.datum = %s ORDER BY b.paragraf
        """,
        (organ, datum),
    ).fetchall()
    return [{"sammantrade_id": r["sammantrade_id"], "paragraf": r["paragraf"], "rubrik": r["rubrik"],
             "organ": organ_ref(r["organ"]), "datum": r["datum"].isoformat(), "grund": "samma diarienummer"}
            for r in rader if any(normalisera_diarienummer(d, organ) == dnr for d in r["diarienummer"])]


def kontrollerad(conn: psycopg.Connection) -> str | None:
    """När sidan senast kontrollerades utan att kontrollen misslyckades."""
    rad = conn.execute(
        "SELECT max(avslutad) AS t FROM kallkorning WHERE datakalla_id = %s AND status <> 'misslyckad'",
        (DATAKALLA,)).fetchone()
    return rad["t"].isoformat() if rad and rad["t"] else None


def lista(conn: psycopg.Connection, idag: date) -> dict:
    rader = conn.execute(
        f"""
        SELECT d.id, d.titel, d.kategorier, d.borttagen, v.dokumentinformation
        FROM styrande_dokument d JOIN ({_SENASTE}) v ON v.dokument_id = d.id
        ORDER BY d.titel COLLATE "C", d.id
        """
    ).fetchall()
    ordning = {r["namn"]: r["ordning"] for r in conn.execute("SELECT namn, ordning FROM styrande_kategori")}
    dokument = []
    for r in rader:
        info = r["dokumentinformation"]
        dokument.append({
            "id": r["id"], "titel": r["titel"],
            "kategorier": sorted(r["kategorier"], key=lambda k: ordning.get(k, len(ordning))),
            "faststallt": _faststallt(info), "giltighet": giltighet(r["titel"], info, r["borttagen"], idag),
        })
    dokument.sort(key=lambda d: (min((ordning.get(k, len(ordning)) for k in d["kategorier"]), default=0),
                                 d["titel"].casefold()))
    kategorier = sorted({k for d in dokument for k in d["kategorier"]}, key=lambda k: ordning.get(k, len(ordning)))
    return {"dokument": dokument, "kategorier": kategorier,
            "kalla": {"titel": "Kommunens styrande dokument", "url": SIDA, "kontrollerad": kontrollerad(conn)}}


def las(conn: psycopg.Connection, dokument_id: int, idag: date) -> dict | None:
    d = conn.execute("SELECT * FROM styrande_dokument WHERE id = %s", (dokument_id,)).fetchone()
    if d is None:
        return None
    versioner = conn.execute(
        """
        SELECT version, url, storlek, hamtad, ersatt, ocr, textfel, dokumentinformation, cardinality(sidor) AS sidor
        FROM styrande_dokument_version WHERE dokument_id = %s ORDER BY version DESC
        """,
        (dokument_id,),
    ).fetchall()
    senaste = versioner[0]
    info = senaste["dokumentinformation"]
    ordning = {r["namn"]: r["ordning"] for r in conn.execute("SELECT namn, ordning FROM styrande_kategori")}
    galler = galler_fran(info)
    return {
        "id": d["id"], "titel": d["titel"], "filnamn": d["filnamn"],
        "kategorier": sorted(d["kategorier"], key=lambda k: ordning.get(k, len(ordning))),
        "url": d["url"], "borttagen": d["borttagen"].isoformat() if d["borttagen"] else None,
        "forst_sedd": d["forst_sedd"].isoformat(), "senast_sedd": d["senast_sedd"].isoformat(),
        "dokumentinformation": {k: v for k, v in info.items()},
        "galler_fran": galler.isoformat() if galler else None,
        "faststallt": _faststallt(info),
        "giltighet": giltighet(d["titel"], info, d["borttagen"], idag),
        "beslut": _beslut(conn, info),
        "versioner": [
            {"version": v["version"], "hamtad": v["hamtad"].isoformat(),
             "ersatt": v["ersatt"].isoformat() if v["ersatt"] else None,
             "kommunens_url": v["url"], "kopia": f"/api/styrande-dokument/{d['id']}/versioner/{v['version']}",
             "storlek": v["storlek"], "sidor": v["sidor"], "ocr": v["ocr"], "textfel": v["textfel"]}
            for v in versioner
        ],
        "kalla": {"titel": "Kommunens styrande dokument", "url": SIDA, "kontrollerad": kontrollerad(conn)},
    }


def fil(conn: psycopg.Connection, dokument_id: int, version: int) -> dict | None:
    return conn.execute(
        """
        SELECT v.innehall, v.sha256, d.filnamn FROM styrande_dokument_version v
        JOIN styrande_dokument d ON d.id = v.dokument_id WHERE v.dokument_id = %s AND v.version = %s
        """,
        (dokument_id, version),
    ).fetchone()


def for_behandling(conn: psycopg.Connection, sammantrade_id: int, paragraf: int) -> list[dict]:
    """De styrande dokument som behandlingen fastställde, enligt kopplingen ovan."""
    s = conn.execute("SELECT organ, datum FROM sammantrade WHERE id = %s", (sammantrade_id,)).fetchone()
    if s is None or s["datum"] is None:
        return []
    ut = []
    for r in conn.execute(
        f"""
        SELECT d.id, d.titel, v.dokumentinformation FROM styrande_dokument d
        JOIN ({_SENASTE}) v ON v.dokument_id = d.id ORDER BY d.titel
        """
    ):
        info = r["dokumentinformation"]
        if faststallt_organ(info.get("faststalld_av")) != s["organ"] or tolka_datum(info.get("datum")) != s["datum"]:
            continue
        if any(b["paragraf"] == paragraf and b["sammantrade_id"] == sammantrade_id for b in _beslut(conn, info)):
            ut.append({"id": r["id"], "titel": r["titel"]})
    return ut
