"""Schemalagd insamling: körs automatiskt vid de konfigurerade tidpunkterna, aldrig två samtidigt."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db
from app.insamling import LASNYCKEL
from app.main import standardkallor
from app.recorded import InspeladTransport
from app.schema import Schema
from app.schemalaggare import kor_om_dags
from conftest import INSPELNINGAR, skapa_app

SVERIGE = ZoneInfo("Europe/Stockholm")
SCHEMA = Schema(dagar=(1, 15), klockan=time(3, 0))


def t(manad: int, dag: int, timme: int = 12, minut: int = 0) -> datetime:
    return datetime(2026, manad, dag, timme, minut, tzinfo=SVERIGE)


@pytest.fixture
def conn(database_url):
    db.migrate(database_url)
    with db.connect(database_url) as c:
        yield c


@pytest.fixture
def klient():
    with httpx.Client(transport=InspeladTransport(INSPELNINGAR)) as c:
        yield c


def korningar(conn) -> list[dict]:
    return conn.execute("SELECT utlosare, status FROM insamlingskorning ORDER BY id").fetchall()


# Schemat


def test_nasta_korning_ar_nasta_konfigurerade_dag_och_klockslag():
    assert SCHEMA.nasta(t(11, 13)) == t(11, 15, 3)
    assert SCHEMA.nasta(t(11, 15, 2, 59)) == t(11, 15, 3)
    assert SCHEMA.nasta(t(11, 15, 3)) == t(12, 1, 3)  # precis på tidpunkten räknas som passerad
    assert SCHEMA.nasta(t(12, 20)) == datetime(2027, 1, 1, 3, tzinfo=SVERIGE)


def test_schemat_foljer_svensk_tid_aven_over_sommartid():
    sommar = Schema(dagar=(1,), klockan=time(3, 0)).nasta(t(6, 2))
    assert sommar == t(7, 1, 3)
    assert sommar.utcoffset().total_seconds() == 2 * 3600


def test_schemat_kan_andras_via_konfiguration(monkeypatch):
    monkeypatch.setenv("INSAMLING_DAGAR", "5, 20")
    monkeypatch.setenv("INSAMLING_KLOCKAN", "04:30")
    schema = Schema.fran_miljo()
    assert schema.dagar == (5, 20)
    assert schema.nasta(t(11, 13)) == t(11, 20, 4, 30)

    monkeypatch.setenv("INSAMLING_DAGAR", "")
    assert Schema.fran_miljo() is None  # schemat avstängt


def test_ogiltigt_schema_ger_tydligt_fel(monkeypatch):
    monkeypatch.setenv("INSAMLING_DAGAR", "1,32")
    with pytest.raises(ValueError, match="INSAMLING_DAGAR"):
        Schema.fran_miljo()


# Schemaläggaren


def test_en_korning_startar_automatiskt_vid_schemalagd_tid(conn, klient):
    kallor = standardkallor()
    # 15 nov 03:00 har passerat och ingen schemalagd körning har gjorts sedan dess.
    res = kor_om_dags(conn, kallor, klient, SCHEMA, t(11, 15, 3, 1))
    assert res is not None and res.status == "lyckad"
    assert korningar(conn) == [{"utlosare": "schema", "status": "lyckad"}]

    # Samma schemalagda tidpunkt körs bara en gång.
    assert kor_om_dags(conn, kallor, klient, SCHEMA, t(11, 15, 3, 2)) is None
    assert kor_om_dags(conn, kallor, klient, SCHEMA, t(11, 30, 23, 59)) is None
    assert len(korningar(conn)) == 1

    # Nästa schemalagda tidpunkt ger en ny körning.
    assert kor_om_dags(conn, kallor, klient, SCHEMA, t(12, 1, 3, 0)) is not None
    assert [k["utlosare"] for k in korningar(conn)] == ["schema", "schema"]


def test_en_missad_korning_tas_igen_en_gang(conn, klient):
    # Servern var nere både den 1:a och den 15:e. När den startar körs en insamling, inte två.
    kallor = standardkallor()
    assert kor_om_dags(conn, kallor, klient, SCHEMA, t(11, 20)) is not None
    assert kor_om_dags(conn, kallor, klient, SCHEMA, t(11, 20, 12, 1)) is None
    assert len(korningar(conn)) == 1


def test_manuell_korning_registreras_som_manuell_och_ersatter_inte_schemat(database_url, google, conn, klient):
    api = TestClient(skapa_app(database_url, google))
    api.post("/api/auth/test/redaktor")
    assert api.post("/api/insamlingar").status_code == 200
    assert korningar(conn)[-1]["utlosare"] == "manuell"
    # Den schemalagda körningen görs ändå.
    assert kor_om_dags(conn, standardkallor(), klient, SCHEMA, datetime.now(SVERIGE)) is not None
    assert korningar(conn)[-1]["utlosare"] == "schema"


def test_tva_korningar_startar_aldrig_samtidigt(database_url, google, conn, klient):
    api = TestClient(skapa_app(database_url, google))
    api.post("/api/auth/test/redaktor")

    # En annan process håller på med en insamling.
    with psycopg.connect(database_url, autocommit=True) as annan:
        annan.execute("SELECT pg_advisory_lock(%s)", (LASNYCKEL,))
        svar = api.post("/api/insamlingar")
        assert svar.status_code == 409
        assert "pågår" in svar.json()["detail"]
        assert kor_om_dags(conn, standardkallor(), klient, SCHEMA, t(11, 15, 4)) is None
        assert korningar(conn) == []

    # När den är klar går det att köra igen.
    assert api.post("/api/insamlingar").status_code == 200


# Statusindikatorn


def test_status_visar_nasta_planerade_korning(database_url, google):
    api = TestClient(skapa_app(database_url, google, schema=SCHEMA, anonym_lasning=True))
    nasta = datetime.fromisoformat(api.get("/api/status").json()["nasta_korning"])
    assert nasta == SCHEMA.nasta(datetime.now(SVERIGE))
    assert nasta.day in (1, 15) and (nasta.hour, nasta.minute) == (3, 0)


def test_utan_schema_finns_ingen_nasta_korning(database_url, google):
    api = TestClient(skapa_app(database_url, google, schema=None, anonym_lasning=True))
    assert api.get("/api/status").json()["nasta_korning"] is None


def test_backend_och_schemalaggaren_kan_migrera_samtidigt(database_url):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: db.migrate(database_url), range(4)))
    with db.connect(database_url) as c:
        assert c.execute("SELECT count(*) AS n FROM schema_migrering WHERE namn = '0003_planerad_tid.sql'").fetchone()["n"] == 1
