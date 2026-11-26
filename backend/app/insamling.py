"""Insamlingsmotorn: kör datakällor och lagrar deras uppgifter som observationer.

Observationer är append-only. En uppgift som redan finns med samma värde räknas som
oförändrad. En uppgift med ändrat värde blir en ny version, och den tidigare versionen
finns kvar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
import psycopg

from . import kalender, kallelsepunkter, motstridigheter, namnvarianter, rankningar, sammansattning, sammantradesplan, skatteunderlag, sokindex, styrande_dokument
from .arenden import koppla
from .protokoll import lagra_dokument
from .robust import Robusthet, kallklient
from .sources.base import Datakalla, Hamtning


@dataclass
class Kallresultat:
    datakalla_id: str
    status: str  # 'lyckad' | 'inga_nya' | 'delvis_fel' | 'misslyckad'
    antal_nya: int = 0
    antal_andrade: int = 0
    antal_oforandrade: int = 0
    fel: str | None = None
    senaste_publicering: date | None = None


@dataclass
class Korningsresultat:
    korning_id: int
    status: str  # 'lyckad' | 'delvis_fel' | 'misslyckad'
    kallor: list[Kallresultat]


UTAN_FEL = ("lyckad", "inga_nya")


def korningsstatus(kallstatusar: list[str]) -> str:
    """En körning är lyckad om alla källor kontrollerades utan fel, även om inget var nytt."""
    if all(s in UTAN_FEL for s in kallstatusar):
        return "lyckad"
    if all(s == "misslyckad" for s in kallstatusar):
        return "misslyckad"
    return "delvis_fel"


def _senast_lyckad(conn: psycopg.Connection, datakalla_id: str) -> datetime | None:
    rad = conn.execute(
        "SELECT max(startad) AS t FROM kallkorning WHERE datakalla_id = %s AND status IN ('lyckad', 'inga_nya')",
        (datakalla_id,),
    ).fetchone()
    return rad["t"] if rad else None


def _lagra(conn: psycopg.Connection, kalla: Datakalla, hamtning: Hamtning, korning_id: int, hamtad: datetime) -> Kallresultat:
    res = Kallresultat(datakalla_id=kalla.id, status="inga_nya")
    for m in hamtning.matt:
        conn.execute(
            """
            INSERT INTO matt (id, datakalla_id, titel, beskrivning, enhet, kallans_publicering, uppdaterad)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET titel = EXCLUDED.titel, beskrivning = EXCLUDED.beskrivning,
                enhet = EXCLUDED.enhet, kallans_publicering = EXCLUDED.kallans_publicering,
                uppdaterad = EXCLUDED.uppdaterad
            """,
            (m.id, kalla.id, m.titel, m.beskrivning, m.enhet, m.kallans_publicering, hamtad),
        )
    for u in hamtning.uppgifter:
        senaste = conn.execute(
            """
            SELECT varde, version FROM observation
            WHERE matt_id = %s AND omrade = %s AND period = %s
            ORDER BY version DESC LIMIT 1
            """,
            (u.matt_id, u.omrade, u.period),
        ).fetchone()
        if senaste is not None and senaste["varde"] == u.varde:
            res.antal_oforandrade += 1
            continue
        version = 1 if senaste is None else senaste["version"] + 1
        conn.execute(
            """
            INSERT INTO observation (matt_id, omrade, period, varde, kallans_publicering, hamtad, version, korning_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (u.matt_id, u.omrade, u.period, u.varde, u.kallans_publicering, hamtad, version, korning_id),
        )
        if senaste is None:
            res.antal_nya += 1
        else:
            res.antal_andrade += 1
    fel = list(hamtning.fel)
    dokument_andrade = False
    for d in hamtning.dokument:
        utfall, dokumentfel = lagra_dokument(conn, kalla.id, d, korning_id, hamtad)
        dokument_andrade |= utfall != "oforandrad"
        if utfall == "ny":
            res.antal_nya += 1
        elif utfall == "andrad":
            res.antal_andrade += 1
        else:
            res.antal_oforandrade += 1
        if dokumentfel:
            fel.append(dokumentfel)
    if dokument_andrade:
        # Behandlingar utan diarienummer kompletteras ur kallelsen före kopplingarna (#109).
        kallelsepunkter.komplettera(conn)
        koppla(conn)
        # Ett nytt protokoll kan innehålla ett beslut om sammanträdestiderna (#99).
        sammantradesplan.lagra_beslut(conn, kalender.idag(), korning_id, hamtad)
    prognosdatum = []
    for p in hamtning.prognosfiler:
        utfall, prognosfel, publicerad = skatteunderlag.lagra(conn, p, korning_id, hamtad)
        if utfall == "ny":
            res.antal_nya += 1
        elif utfall == "andrad":
            res.antal_andrade += 1
        elif not prognosfel:
            res.antal_oforandrade += 1
        if prognosfel:
            fel.append(prognosfel)
        if publicerad:
            prognosdatum.append(publicerad)
    for plan in hamtning.sammantradesplaner:
        antal = sammantradesplan.lagra(conn, plan, korning_id, hamtad)
        res.antal_nya += antal["nya"]
        res.antal_andrade += antal["andrade"]
        res.antal_oforandrade += antal["oforandrade"]
    if hamtning.sammantradesplaner:
        # År utan plan på webbsidan får sina sammanträden ur organens beslut (#99).
        sammantradesplan.lagra_beslut(conn, kalender.idag(), korning_id, hamtad)
    if hamtning.kallelser or hamtning.webbsandningar:
        antal = sammantradesplan.lagra_kallelser(conn, hamtning.kallelser, hamtning.webbsandningar, korning_id, hamtad)
        if antal.pop("lasta_listor") and kallelsepunkter.komplettera(conn):
            koppla(conn)
        res.antal_nya += antal["nya"]
        res.antal_andrade += antal["andrade"]
        res.antal_oforandrade += antal["oforandrade"]
    for v in hamtning.val:
        antal = sammansattning.lagra(conn, v, korning_id, hamtad)
        res.antal_nya += antal["nya"]
        res.antal_andrade += antal["andrade"]
        res.antal_oforandrade += antal["oforandrade"]
    for r in hamtning.rankningar:
        antal = rankningar.lagra(conn, r, kalla.id, korning_id, hamtad)
        res.antal_nya += antal["nya"]
        res.antal_andrade += antal["andrade"]
        res.antal_oforandrade += antal["oforandrade"]
    for lista in hamtning.styrande_dokument:
        antal = styrande_dokument.lagra(conn, lista, korning_id, hamtad, kalender.idag())
        # Kandidater till flera gällande versioner (#151), som utkast för redaktionen.
        motstridigheter.foresla_kandidater(conn, kalender.idag(), hamtad)
        res.antal_nya += antal["nya"]
        res.antal_andrade += antal["andrade"]
        res.antal_oforandrade += antal["oforandrade"]
    if dokument_andrade:
        # Namnvarianter slås ihop, felaktiga namn tas bort och nya förslag tas fram (#165).
        namnvarianter.underhall(conn)
    if hamtning.val or dokument_andrade:
        # Nya val- eller protokolluppgifter kan ge nya kopplingar till ledamotsregistret (#65).
        sammansattning.koppla(conn)
    publiceringar = [d for d in (*(m.kallans_publicering for m in hamtning.matt),
                                 *(u.kallans_publicering for u in hamtning.uppgifter), *prognosdatum) if d]
    res.senaste_publicering = max(publiceringar, default=None)
    if fel:
        res.status = "delvis_fel"
        res.fel = "; ".join(fel)
    elif res.antal_nya or res.antal_andrade:
        res.status = "lyckad"
    return res


# Nyckel för Postgres advisory lock som hindrar att två insamlingar körs samtidigt,
# oavsett om de startas av schemaläggaren eller manuellt (också från olika processer).
LASNYCKEL = 0x6B6B_0001


class InsamlingPagar(Exception):
    """En annan insamling pågår redan."""


def kor_insamling(
    conn: psycopg.Connection,
    kallor: list[Datakalla],
    client: httpx.Client,
    utlosare: str = "manuell",
    planerad_tid: datetime | None = None,
    robusthet: Robusthet | None = None,
) -> Korningsresultat:
    """Kör källorna i tur och ordning. Var och en sparas i en egen transaktion.

    Har en tidigare körning avbrutits (status 'pagar' utan att någon insamling pågår) återupptas
    den: källor som redan är klara i den hoppas över. Eftersom en källas uppgifter sparas
    tillsammans med dess resultat, och oförändrade värden inte sparas igen, blir det inga dubbletter.
    """
    if not conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (LASNYCKEL,)).fetchone()["ok"]:
        conn.rollback()
        raise InsamlingPagar("En insamling pågår redan. Försök igen när den är klar.")
    try:
        return _kor(conn, kallor, client, utlosare, planerad_tid, robusthet or Robusthet())
    finally:
        conn.rollback()
        conn.execute("SELECT pg_advisory_unlock(%s)", (LASNYCKEL,))
        conn.commit()


def _avbruten_korning(conn: psycopg.Connection) -> int | None:
    # Anropas med låset taget, så en körning som fortfarande står som pågående har avbrutits.
    rad = conn.execute("SELECT id FROM insamlingskorning WHERE status = 'pagar' ORDER BY id DESC LIMIT 1").fetchone()
    return rad["id"] if rad else None


def _kor(
    conn: psycopg.Connection,
    kallor: list[Datakalla],
    client: httpx.Client,
    utlosare: str,
    planerad_tid: datetime | None,
    robusthet: Robusthet,
) -> Korningsresultat:
    korning_id = _avbruten_korning(conn)
    klara: set[str] = set()
    if korning_id is not None:
        klara = {r["datakalla_id"] for r in conn.execute(
            "SELECT datakalla_id FROM kallkorning WHERE korning_id = %s", (korning_id,))}
        # Äldre avbrutna körningar (om flera) avslutas utan att återupptas.
        conn.execute("UPDATE insamlingskorning SET status = 'avbruten', avslutad = now() "
                     "WHERE status = 'pagar' AND id < %s", (korning_id,))
    else:
        korning_id = conn.execute(
            "INSERT INTO insamlingskorning (utlosare, planerad_tid) VALUES (%s, %s) RETURNING id",
            (utlosare, planerad_tid),
        ).fetchone()["id"]
    conn.commit()

    for kalla in kallor:
        if kalla.id in klara:
            continue
        startad = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO datakalla (id, titel, url) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET titel = EXCLUDED.titel, url = EXCLUDED.url",
            (kalla.id, kalla.titel, kalla.url),
        )
        try:
            if hasattr(kalla, "kanda_kallelser"):
                kalla.kanda_kallelser = {r["url"] for r in conn.execute("SELECT url FROM kallelse WHERE pdf_last")}
                # Föredragningslistan läses bara ur nya kallelser. Äldre läses med app.las_kallelser (#109).
                kalla.alla_kallelser = {r["url"] for r in conn.execute("SELECT url FROM kallelse")}
            if hasattr(kalla, "kanda_dokument"):
                # Källor med dokument får veta vilka adresser som redan är hämtade.
                kalla.kanda_dokument = {r["url"] for r in conn.execute(
                    "SELECT DISTINCT url FROM dokument WHERE datakalla_id = %s", (kalla.id,))}
            if hasattr(kalla, "kanda_filer"):
                # Styrande dokument (#63): filer som redan är hämtade laddas inte ner igen.
                kalla.kanda_filer = styrande_dokument.kanda_filer(conn)
            with kallklient(client, robusthet, getattr(kalla, "anrop_per_sekund", None)) as kc:
                hamtning = kalla.hamta(kc, _senast_lyckad(conn, kalla.id))
            res = _lagra(conn, kalla, hamtning, korning_id, startad)
        except Exception as e:  # ett fel i en källa får inte stoppa de andra
            conn.rollback()
            conn.execute(
                "INSERT INTO datakalla (id, titel, url) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (kalla.id, kalla.titel, kalla.url),
            )
            res = Kallresultat(datakalla_id=kalla.id, status="misslyckad", fel=f"{type(e).__name__}: {e}")
        conn.execute(
            """
            INSERT INTO kallkorning (korning_id, datakalla_id, status, antal_nya, antal_andrade, antal_oforandrade,
                                     fel, kallans_senaste_publicering, startad, avslutad)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            """,
            (korning_id, kalla.id, res.status, res.antal_nya, res.antal_andrade, res.antal_oforandrade,
             res.fel, res.senaste_publicering, startad),
        )
        conn.commit()

    # Sökindexet (#142): de nya protokollens text läses, och det som ändrats räknas om. Ett fel här
    # påverkar inte insamlingens resultat.
    sokindex.uppdatera(conn, extrahera=korning_id)
    conn.commit()

    resultat = [
        Kallresultat(datakalla_id=r["datakalla_id"], status=r["status"], antal_nya=r["antal_nya"],
                     antal_andrade=r["antal_andrade"], antal_oforandrade=r["antal_oforandrade"], fel=r["fel"],
                     senaste_publicering=r["kallans_senaste_publicering"])
        for r in conn.execute(
            "SELECT * FROM kallkorning WHERE korning_id = %s ORDER BY startad", (korning_id,))
    ]
    status = korningsstatus([r.status for r in resultat])
    conn.execute(
        "UPDATE insamlingskorning SET avslutad = now(), status = %s WHERE id = %s", (status, korning_id)
    )
    conn.commit()
    return Korningsresultat(korning_id=korning_id, status=status, kallor=resultat)
