"""Vektorsökning (#69): sökenheternas text som vektorer från en lokal språkmodell, i pgvector.

Fulltextsökningen (`app.sokindex`) hittar ord och böjningar. Vektorerna hittar betydelse: "skolnedläggning"
hittar "Avveckling av Säbrå skola". Sökningen slår ihop de två listorna (reciprocal rank fusion, i
`sokindex.sok`).

- **Modell:** `intfloat/multilingual-e5-small` (384 dimensioner), med ONNX via fastembed på processorn.
  Modellfilen är inbyggd i backend-bilden och laddas första gången den behövs, bara i den processen.
  Sökfrågorna lämnar aldrig servern (ADR-0008).
- **Stycken:** en enhets text delas i stycken om cirka 300 ord som överlappar med 50 ord. Rubriken och
  diarienumret (`text_a`) står först i varje stycke, och är också ett eget stycke: rubriken säger ofta mest
  om vad enheten handlar om, och i ett långt stycke späds den ut. Ett stycke har enhetens sidnummer.
- **Uppdatering:** en enhet väntar på vektorer när texten ändrats sedan de räknades (`sha256`) eller när
  modellen bytts. `vektorisera` räknar om de väntande och kan avbrytas och återupptas.

Tabellen `sokstycke` kräver tillägget pgvector. Finns det inte i databasen skapas tabellen inte, och
sökningen är enbart fulltext som i del 1.

Modellen väljs med `SOKMODELL`: `e5-small` (standard), `test` (en deterministisk modell för testerna,
utan språkförståelse) eller `av` (ingen vektorsökning).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from threading import Lock, Thread
from typing import Protocol, Sequence

import psycopg

logger = logging.getLogger(__name__)

DIMENSIONER = 384
STYCKE_ORD = 300
OVERLAPP_ORD = 50
# Antal enheter som vektorsökningen ger, och stycken som HNSW-indexet söker bland.
VEKTORTRAFFAR = 50
_KANDIDATER = 200


class Modell(Protocol):
    namn: str
    # Stycken som ligger längre från frågan än så räknas inte som träffar. Utan gräns ger vektorsökningen
    # alltid de närmaste, också när inget handlar om frågan.
    min_likhet: float

    def passager(self, texter: Sequence[str]) -> list[list[float]]: ...

    def fraga(self, text: str) -> list[float]: ...


class E5Small:
    """`intfloat/multilingual-e5-small`. e5-modellerna vill ha prefixen "query: " och "passage: "."""

    namn = "intfloat/multilingual-e5-small"
    # e5 ger höga likheter också för texter om annat (0,75–0,83). Satt efter frågor mot protokollen 2026-11-24.
    min_likhet = 0.83

    def __init__(self, katalog: str | None = None, tradar: int | None = None) -> None:
        self.katalog = katalog or os.environ.get("MODELL_KATALOG")
        # onnxruntime räknar värdens alla kärnor, inte de som containern får använda (två på LXC 107).
        self.tradar = tradar or (len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None)
        self._modell = None
        self._las = Lock()

    def _ladda(self):
        with self._las:
            if self._modell is None:
                from fastembed import TextEmbedding
                from fastembed.common.model_description import ModelSource, PoolingType

                if not any(m["model"] == self.namn for m in TextEmbedding.list_supported_models()):
                    TextEmbedding.add_custom_model(
                        model=self.namn, pooling=PoolingType.MEAN, normalization=True,
                        sources=ModelSource(hf=self.namn), dim=DIMENSIONER, model_file="onnx/model.onnx",
                    )
                logger.info("Laddar sökmodellen %s", self.namn)
                self._modell = TextEmbedding(self.namn, cache_dir=self.katalog, threads=self.tradar)
            return self._modell

    def passager(self, texter: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._ladda().embed([f"passage: {t}" for t in texter], batch_size=16)]

    def fraga(self, text: str) -> list[float]:
        return next(iter(self._ladda().embed([f"query: {text}"]))).tolist()


class Testmodell:
    """Deterministisk modell för testerna: orden (de fem första bokstäverna) hashade till dimensioner.

    Den förstår inga synonymer, men texter med samma ord hamnar nära varandra.
    """

    namn = "test-ordhash-1"
    min_likhet = 0.5

    def _vektor(self, text: str) -> list[float]:
        v = [0.0] * DIMENSIONER
        for o in re.findall(r"\w+", text.lower()):
            h = hashlib.md5(o[:5].encode()).digest()
            v[int.from_bytes(h[:4], "little") % DIMENSIONER] += 1.0 if h[4] % 2 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def passager(self, texter: Sequence[str]) -> list[list[float]]:
        return [self._vektor(t) for t in texter]

    def fraga(self, text: str) -> list[float]:
        return self._vektor(text)


_vald: Modell | None = None
_vald_satt = False
_vald_las = Lock()


def modell() -> Modell | None:
    """Modellen enligt `SOKMODELL`, eller None om vektorsökningen är avstängd."""
    global _vald, _vald_satt
    with _vald_las:
        if not _vald_satt:
            namn = (os.environ.get("SOKMODELL") or "e5-small").strip().lower()
            _vald = {"e5-small": E5Small, "test": Testmodell}.get(namn, lambda: None)()
            _vald_satt = True
        return _vald


def satt_modell(m: Modell | None) -> None:
    """Byter modell (testerna)."""
    global _vald, _vald_satt
    with _vald_las:
        _vald, _vald_satt = m, True


def forvarm(database_url: str) -> None:
    """Laddar språkmodellen i bakgrunden när backend startar, så att den första sökningen inte får vänta.

    Bara när vektorsökningen kan användas: utan pgvector laddas modellen inte alls.
    """
    m = modell()
    if not isinstance(m, E5Small):
        return

    def ladda() -> None:
        from . import db

        try:
            with db.connect(database_url) as conn:
                if tillganglig(conn):
                    m.fraga("uppvärmning")
        except Exception:
            logger.exception("Sökmodellen kunde inte laddas i förväg")

    Thread(target=ladda, name="sokmodell", daemon=True).start()


# Databasen

def forbered(conn: psycopg.Connection) -> bool:
    """Skapar tillägget och tabellen om pgvector finns i databasen. Ger True om vektorerna kan användas."""
    if conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").fetchone() is None:
        return False
    try:
        with conn.transaction():
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS sokstycke (
                    enhet_id    bigint NOT NULL REFERENCES sokenhet(id) ON DELETE CASCADE,
                    ordning     integer NOT NULL,
                    sida        integer,
                    text        text NOT NULL,
                    modell      text NOT NULL,
                    vektor      vector({DIMENSIONER}) NOT NULL,
                    PRIMARY KEY (enhet_id, ordning)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS sokstycke_vektor ON sokstycke USING hnsw (vektor vector_cosine_ops)")
    except psycopg.Error:
        logger.exception("Vektorsökningen kunde inte förberedas, sökningen blir enbart fulltext")
        return False
    return True


def tillganglig(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('sokstycke') IS NOT NULL AS finns").fetchone()["finns"]


def stycken(text_a: str, text_b: str, text_c: str) -> list[str]:
    """Rubriken, och texten i stycken om `STYCKE_ORD` ord som överlappar med `OVERLAPP_ORD`, med rubriken först."""
    huvud = " ".join(text_a.split()[:40])
    ord_ = f"{text_b} {text_c}".split()
    ut: list[str] = [huvud] if huvud else []
    if not ord_:
        return ut
    start = 0
    while True:
        ut.append(f"{huvud}\n{' '.join(ord_[start:start + STYCKE_ORD])}".strip())
        if start + STYCKE_ORD >= len(ord_):
            return ut
        start += STYCKE_ORD - OVERLAPP_ORD


def _vektortext(v: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def vektorisera(conn: psycopg.Connection, enheter: list[int] | None = None, commit: bool = False,
                grupp: int = 32, m: Modell | None = None) -> int:
    """Räknar vektorer för de enheter som väntar (alla, eller bara `enheter`). Ger antal räknade enheter.

    Med `commit` sparas arbetet efter varje grupp, så att en avbruten körning fortsätter där den slutade.
    """
    m = m or modell()
    if m is None or not tillganglig(conn):
        return 0
    if enheter is not None and not enheter:
        return 0
    antal, efter = 0, 0
    while True:
        rader = conn.execute(
            """
            SELECT id, text_a, text_b, text_c, sida, sha256 FROM sokenhet
            WHERE (vektor_sha256 IS DISTINCT FROM sha256 OR vektor_modell IS DISTINCT FROM %(m)s)
              AND (%(e)s::bigint[] IS NULL OR id = ANY(%(e)s)) AND id > %(efter)s
            ORDER BY id LIMIT %(grupp)s
            """,
            {"m": m.namn, "e": enheter, "efter": efter, "grupp": grupp},
        ).fetchall()
        if not rader:
            return antal
        delar = [(r, i, s) for r in rader for i, s in enumerate(stycken(r["text_a"], r["text_b"], r["text_c"]))]
        vektorer = m.passager([s for _, _, s in delar]) if delar else []
        ids = [r["id"] for r in rader]
        conn.execute("DELETE FROM sokstycke WHERE enhet_id = ANY(%s)", (ids,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO sokstycke (enhet_id, ordning, sida, text, modell, vektor) "
                "VALUES (%s, %s, %s, %s, %s, %s::vector)",
                [(r["id"], i, r["sida"], s, m.namn, _vektortext(v)) for (r, i, s), v in zip(delar, vektorer)],
            )
            cur.executemany(
                "UPDATE sokenhet SET vektor_sha256 = %s, vektor_modell = %s WHERE id = %s",
                [(r["sha256"], m.namn, r["id"]) for r in rader],
            )
        antal += len(rader)
        efter = ids[-1]
        if commit:
            conn.commit()
            logger.info("Vektorer: %d enheter räknade", antal)


def status(conn: psycopg.Connection) -> dict:
    """Hur många enheter som har aktuella vektorer och hur många som väntar, för statussidan."""
    m = modell()
    aktiv = m is not None and tillganglig(conn)
    rad = conn.execute(
        "SELECT count(*) AS enheter, count(*) FILTER (WHERE vektor_sha256 = sha256 AND vektor_modell = %s) AS klara "
        "FROM sokenhet",
        (m.namn if m else None,),
    ).fetchone()
    return {
        "aktiv": aktiv,
        "modell": m.namn if m else None,
        "enheter": rad["enheter"],
        "med_vektorer": rad["klara"] if aktiv else 0,
        "vantar": rad["enheter"] - rad["klara"] if aktiv else 0,
    }


def sok(conn: psycopg.Connection, q: str, organ: str | None = None, ar: int | None = None,
        antal: int = VEKTORTRAFFAR) -> tuple[list[float] | None, list[dict]]:
    """De `antal` enheter vars stycken ligger närmast frågan, närmast först, med det närmaste stycket.

    Filtren tillämpas före rankningen. Ger också frågans vektor, för utdragen.
    """
    m = modell()
    if m is None or not tillganglig(conn):
        return None, []
    v = m.fraga(q)
    conn.execute(f"SET LOCAL hnsw.ef_search = {_KANDIDATER}")
    rader = conn.execute(
        """
        SELECT s.enhet_id, s.text, s.vektor <=> %(v)s::vector AS avstand
        FROM sokstycke s JOIN sokenhet e ON e.id = s.enhet_id
        WHERE s.modell = %(m)s
          AND (%(organ)s::text IS NULL OR e.organ = %(organ)s) AND (%(ar)s::int IS NULL OR e.ar = %(ar)s)
        ORDER BY s.vektor <=> %(v)s::vector
        LIMIT %(k)s
        """,
        {"v": _vektortext(v), "m": m.namn, "organ": organ, "ar": ar, "k": _KANDIDATER},
    ).fetchall()
    basta: dict[int, dict] = {}
    for r in (r for r in rader if 1 - r["avstand"] >= m.min_likhet):  # närmast först
        basta.setdefault(r["enhet_id"], {"id": r["enhet_id"], "stycke": r["text"], "avstand": r["avstand"]})
    traffar = list(basta.values())[:antal]
    # Utdraget tas ur brödtexten. Är rubriken det närmaste stycket används det närmaste av de andra.
    bara_rubrik = [t["id"] for t in traffar if "\n" not in t["stycke"]]
    if bara_rubrik:
        brodtext = {r["enhet_id"]: r["text"] for r in conn.execute(
            """
            SELECT DISTINCT ON (enhet_id) enhet_id, text FROM sokstycke
            WHERE enhet_id = ANY(%(e)s) AND modell = %(m)s AND strpos(text, chr(10)) > 0
            ORDER BY enhet_id, vektor <=> %(v)s::vector
            """,
            {"e": bara_rubrik, "m": m.namn, "v": _vektortext(v)},
        )}
        for t in traffar:
            t["stycke"] = brodtext.get(t["id"], t["stycke"])
    return v, traffar


_MENING = re.compile(r"(?<=[.!?:])\s+(?=[A-ZÅÄÖ0-9§•–-])")


def basta_meningar(
    fraga_vektor: Sequence[float], stycken_: dict[int, str], per_stycke: int = 12, hogst: int = 48
) -> dict[int, str]:
    """Den mening i varje stycke som ligger närmast frågan, för utdraget till en träff på betydelse.

    Varje mening kostar ett anrop till modellen när sidan visas, cirka 20 ms på serverns två kärnor. Sidan
    räknar därför högst `hogst` meningar, fördelade jämnt över träffarna. Ett stycke som bara får en mening
    behöver ingen jämförelse."""
    m = modell()
    kandidater: dict[int, list[str]] = {}
    for nyckel, text in stycken_.items():
        _, _, brodtext = text.partition("\n")
        delar = [" ".join(d.split()[:40]) for d in _MENING.split(brodtext or text) if len(d.split()) >= 3]
        kandidater[nyckel] = (delar or [" ".join((brodtext or text).split()[:40])])[:per_stycke]
    if m is None or not kandidater:
        return {}
    # Lika många meningar per stycke, så långt taket räcker.
    kvot = max(1, hogst // len(kandidater))
    ut = {k: d[0] for k, d in kandidater.items()}
    meningar = [(k, t) for k, d in kandidater.items() if len(d) > 1 for t in d[:kvot]]
    if not meningar:
        return ut
    basta: dict[int, float] = {}
    for (nyckel, t), v in zip(meningar, m.passager([t for _, t in meningar])):
        likhet = sum(a * b for a, b in zip(fraga_vektor, v))
        if nyckel not in basta or likhet > basta[nyckel]:
            basta[nyckel], ut[nyckel] = likhet, t
    return ut


if __name__ == "__main__":
    # Laddar ner modellen till MODELL_KATALOG när backend-bilden byggs (se Dockerfile).
    import sys

    if sys.argv[1:] == ["--ladda-ner"]:
        logging.basicConfig(level=logging.INFO)
        print(len(E5Small().fraga("test")), "dimensioner")
