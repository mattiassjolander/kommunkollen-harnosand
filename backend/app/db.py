"""Databasanslutning och schemamigrering."""

from __future__ import annotations

from importlib import resources

import psycopg
from psycopg.rows import dict_row


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row, autocommit=False)


def migrate(url: str) -> None:
    """Kör alla migreringar som inte redan körts, i filnamnsordning."""
    with connect(url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrering (namn text PRIMARY KEY, kord timestamptz NOT NULL DEFAULT now())"
        )
        korda = {r["namn"] for r in conn.execute("SELECT namn FROM schema_migrering")}
        filer = sorted(
            (f for f in resources.files("app.migrations").iterdir() if f.name.endswith(".sql")),
            key=lambda f: f.name,
        )
        for fil in filer:
            if fil.name in korda:
                continue
            conn.execute(fil.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrering (namn) VALUES (%s)", (fil.name,))
        conn.commit()
