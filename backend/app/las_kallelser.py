"""Diarienummer ur kallelserna bakåt (#109): `python -m app.las_kallelser [--fran ÅÅÅÅ-MM-DD] [--status saknas] [--torrt]`.

Insamlingen läser föredragningslistan bara ur nya kallelser. Det här läser den ur de lagrade kallelser,
kungörelser och handlingar som inte är lästa, för sammanträden från och med `--fran` (2026-01-01) som
har behandlingar utan diarienummer. Sedan kompletteras behandlingarna och kopplingarna och ärendena
räknas om. Filerna hämtas från harnosand.se, en i taget. `--torrt` visar bara vilka som skulle läsas.
`--status saknas` läser om de lästa där ingen föredragningslista hittades, till exempel efter att
läsningen har förbättrats.

På servern: `docker compose exec backend /app/.venv/bin/python -m app.las_kallelser`, först efter
användarens godkännande. Kräver DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from . import db, kallelsepunkter, sokindex
from .arenden import koppla
from .sources import foredragningslista


def att_lasa(conn, fran: date, status: str = "ej_last") -> list[dict]:
    return conn.execute(
        """
        SELECT k.id, k.organ, k.datum, k.titel, k.url, k.storlek FROM kallelse k
        WHERE k.punkter_status = %s AND k.datum >= %s
          AND EXISTS (SELECT 1 FROM sammantrade s JOIN behandling b ON b.sammantrade_id = s.id
                      WHERE s.organ = k.organ AND s.datum = k.datum AND cardinality(b.diarienummer) = 0)
        ORDER BY k.datum, k.id
        """,
        (status, fran),
    ).fetchall()


def las(conn, client: httpx.Client, k: dict) -> foredragningslista.Foredragningslista:
    with tempfile.TemporaryDirectory(prefix="kallelse-") as katalog:
        fil = Path(katalog) / "kallelse.pdf"
        try:
            with client.stream("GET", k["url"]) as svar:
                svar.raise_for_status()
                with fil.open("wb") as f:
                    for bit in svar.iter_bytes():
                        f.write(bit)
        except httpx.HTTPError as e:
            # Hämtningen misslyckades: kallelsen förblir oläst och kan läsas nästa gång.
            return foredragningslista.Foredragningslista("ej_last", fel=(f"{type(e).__name__}: {e}",))
        f = foredragningslista.las(fil, k["organ"])
    kallelsepunkter.lagra_punkter(conn, k["id"], f, datetime.now(timezone.utc))
    return f


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fran", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--status", choices=["ej_last", "saknas", "fel", "delvis_fel"], default="ej_last")
    parser.add_argument("--torrt", action="store_true")
    args = parser.parse_args()
    url = os.environ["DATABASE_URL"]
    db.migrate(url)
    with db.connect(url) as conn, httpx.Client(timeout=120, follow_redirects=True) as client:
        kallelser = att_lasa(conn, args.fran, args.status)
        print(f"{len(kallelser)} kallelser att läsa från {args.fran}.")
        for k in kallelser:
            if args.torrt:
                print(f"  {k['organ']} {k['datum']} {k['titel']} ({(k['storlek'] or 0) / 1e6:.0f} MB)")
                continue
            f = las(conn, client, k)
            conn.commit()
            antal = sum(1 for p in f.punkter if p.diarienummer)
            print(f"  {k['organ']} {k['datum']} {k['titel']}: {f.status}, {antal} diarienummer"
                  + (f" ({'; '.join(f.fel)})" if f.fel else ""))
        if args.torrt:
            return
        andrade = kallelsepunkter.komplettera(conn)
        arenden = koppla(conn)
        sokindex.indexera(conn, typer=("behandling", "arende", "kallelsepunkt"), extrahera=False)
        conn.commit()
    print(f"{andrade} behandlingar fick eller ändrade diarienummer ur kallelsen.")
    print(f"{arenden['arenden']} ärenden, varav {arenden['kopplade']} med flera behandlingar.")


if __name__ == "__main__":
    main()
