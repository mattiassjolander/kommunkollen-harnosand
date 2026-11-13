"""Söm 1: backendens HTTP-API mot riktig Postgres, med källorna utbytta mot inspelade svar.

Postgres tas från `TEST_DATABASE_URL` om den är satt (CI), annars startas en inbäddad
Postgres via pgserver. Varje test får en egen, tom databas.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import uuid
from pathlib import Path

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import Inloggning, las_anvandare
from app.main import create_app
from app.recorded import InspeladTransport

INSPELNINGAR = Path(__file__).parent / "recordings"

GOOGLE_CLIENT_ID = "test-klient.apps.googleusercontent.com"
TILLATNA = "anna@example.se=redaktor+utgivare; Bo@Example.se=lasare"


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


class FalskGoogle:
    """Googles token-endpoint. `nasta_id_token` styr vad nästa inloggning returnerar."""

    def __init__(self) -> None:
        self.nasta_id_token: dict = {}
        self.anrop: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anrop.append(request)
        if request.url.host != "oauth2.googleapis.com":
            raise httpx.ConnectError(f"Oväntat anrop till {request.url}", request=request)
        def b64(d: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        token = f"{b64({'alg': 'RS256'})}.{b64(self.nasta_id_token)}.signatur"
        return httpx.Response(200, json={"id_token": token, "access_token": "x"})


@pytest.fixture
def google() -> FalskGoogle:
    return FalskGoogle()


def skapa_app(database_url: str, google: FalskGoogle, kallor=None, inspelningar: Path = INSPELNINGAR, **inloggning):
    standard = {
        "google_client_id": GOOGLE_CLIENT_ID,
        "google_client_secret": "hemligt",
        "anvandare": las_anvandare(TILLATNA),
        "testenv": True,
    }
    inst = Inloggning(**(standard | inloggning))
    return create_app(
        database_url=database_url,
        kallor=kallor,
        transport=InspeladTransport(inspelningar),
        inloggning=inst,
        auth_transport=httpx.MockTransport(google),
    )


@pytest.fixture
def api(database_url: str, google: FalskGoogle) -> TestClient:
    """Oinloggad klient. Testinloggning finns (TESTENV)."""
    return TestClient(skapa_app(database_url, google))


@pytest.fixture
def redaktor(api: TestClient) -> TestClient:
    assert api.post("/api/auth/test/redaktor").status_code == 200
    return api
