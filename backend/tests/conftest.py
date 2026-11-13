"""Söm 1: backendens HTTP-API mot riktig Postgres, med källorna utbytta mot inspelade svar.

Postgres tas från `TEST_DATABASE_URL` om den är satt (CI), annars startas en inbäddad
Postgres via pgserver. Varje test får en egen, tom databas.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.recorded import InspeladTransport

INSPELNINGAR = Path(__file__).parent / "recordings"


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    import pgserver

    server = pgserver.get_server(tempfile.mkdtemp(prefix="kommunkollen-test-"), cleanup_mode="delete")
    return server.get_uri()


@pytest.fixture
def database_url(postgres_url: str):
    namn = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(postgres_url, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{namn}"')
    bas, _, _ = postgres_url.rpartition("/")
    yield f"{bas}/{namn}"
    with psycopg.connect(postgres_url, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{namn}" WITH (FORCE)')


@pytest.fixture
def api(database_url: str) -> TestClient:
    app = create_app(database_url=database_url, transport=InspeladTransport(INSPELNINGAR))
    return TestClient(app)
