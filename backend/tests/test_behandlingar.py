"""Behandlingar med publicerade rättelser (#101), mot en databas som fylls direkt utan inspelad insamling."""

from __future__ import annotations

from datetime import date

import pytest

from app import arenden, behandlingar, db, rattelser, sammantradesplan


@pytest.fixture
def conn(database_url: str):
    db.migrate(database_url)
    with db.connect(database_url) as c:
        yield c


def sammantrade(conn, organ: str, datum: date | None, nyckel: str | None = None) -> int:
    return conn.execute(
        "INSERT INTO sammantrade (organ, nyckel, datum) VALUES (%s, %s, %s) RETURNING id",
        (organ, nyckel or str(datum), datum),
    ).fetchone()["id"]


def behandling(conn, sid: int, paragraf: int, rubrik: str, beslut: str | None = None,
               diarienummer: list[str] | None = None, ordning: int | None = None) -> None:
    conn.execute(
        "INSERT INTO behandling (sammantrade_id, ordning, paragraf, rubrik, beslut, diarienummer) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (sid, paragraf if ordning is None else ordning, paragraf, rubrik, beslut, diarienummer or []),
    )


def ratta(conn, sid: int, paragraf: int, falt: str, nytt, publicera: bool = True) -> None:
    r = rattelser.skapa(conn, {"objekt": "behandling", "sammantrade_id": sid, "paragraf": paragraf, "falt": falt,
                               "nytt": nytt, "motivering": "Så står det i protokollet", "felet_i": "inlasningen"},
                              "redaktor@test")
    rattelser.granska(conn, r["id"], "utgivare@test")
    if publicera:
        rattelser.publicera(conn, r["id"], "utgivare@test")


def test_en_rad_per_behandling_med_rattelser_och_typ(conn):
    ks = sammantrade(conn, "KS", date(2026, 3, 3))
    kf = sammantrade(conn, "KF", date(2026, 3, 30))
    behandling(conn, ks, 10, "Taxa för bygglov", "Kommunstyrelsen föreslår kommunfullmäktige att anta taxan.",
               ["KS/2026-1"])
    # Samma paragraf två gånger i tolkningen (t.ex. en fortsättning): den första raden gäller.
    behandling(conn, ks, 10, "Taxa för bygglov (forts.)", None, [], ordning=99)
    behandling(conn, kf, 5, "Taxa för byglov", "Kommunfullmäktige beslutar att anta taxan.", ["KS/2026-1"])
    behandling(conn, kf, 6, "Motion om cykelvägar", "Kommunfullmäktige beslutar att avslå motionen.")
    ratta(conn, kf, 5, "rubrik", "Taxa för bygglov")
    ratta(conn, kf, 6, "beslut", "Kommunfullmäktige beslutar att bifalla motionen.", publicera=False)

    rader = behandlingar.las(conn)
    assert [(r["organ"], r["paragraf"]) for r in rader] == [("KS", 10), ("KF", 5), ("KF", 6)]
    ks10, kf5, kf6 = rader
    assert ks10["rubrik"] == "Taxa för bygglov" and "rattelser" not in ks10
    assert kf5["rubrik"] == "Taxa för bygglov"
    assert kf5["rattelser"]["rubrik"]["ursprungligt"] == "Taxa för byglov"
    # En rättelse som inte är publicerad syns inte.
    assert kf6["beslut"] == "Kommunfullmäktige beslutar att avslå motionen." and "rattelser" not in kf6
    assert kf6["typ"] is not None and kf6["motionarer_rattelse"] is None
    assert {k for k in kf5} >= {"id", "sammantrade_id", "datum", "organ", "tolkning", "paragraf", "rubrik", "beslut",
                                 "diarienummer", "typ", "motionarer", "motionarer_rattelse", "arende_id"}


def test_filter(conn):
    a = sammantrade(conn, "KS", date(2025, 12, 1))
    b = sammantrade(conn, "KS", date(2026, 1, 20))
    c = sammantrade(conn, "SAM", date(2026, 2, 5))
    utan = sammantrade(conn, "SAM", None, nyckel="okänt")
    for sid in (a, b, c, utan):
        behandling(conn, sid, 1, "Sammanträdestider 2027" if sid == c else "Val av justerare")
    arenden.koppla(conn)

    def nycklar(**f) -> list[int]:
        return [r["sammantrade_id"] for r in behandlingar.las(conn, **f)]

    assert nycklar() == [a, b, c, utan]  # utan datum sist
    assert nycklar(fran=2026) == [b, c]
    assert nycklar(till=2025) == [a]
    assert nycklar(organ="SAM") == [c, utan]
    assert nycklar(rubrik="sammanträdes(tider|plan)") == [c]
    arende_b = behandlingar.las(conn, fran=2026, till=2026, organ="KS")[0]["arende_id"]
    assert arende_b is not None and nycklar(arende=arende_b) == [b]


def test_publicerad_rattelse_av_diarienumret_andrar_kopplingen_direkt(conn):
    ks = sammantrade(conn, "KS", date(2026, 3, 3))
    kf = sammantrade(conn, "KF", date(2026, 3, 30))
    behandling(conn, ks, 10, "Taxa för bygglov", "Kommunstyrelsen föreslår kommunfullmäktige att anta taxan.",
               ["KS/2026-1"])
    behandling(conn, kf, 5, "Taxa för bygglov", "Kommunfullmäktige beslutar att anta taxan.", ["KS/2026-7"])
    arenden.koppla(conn)

    def arende(sid: int, paragraf: int) -> int:
        return arenden.arende_for(conn, sid, paragraf)["id"]

    assert arende(ks, 10) != arende(kf, 5)
    # Diarienumret är felläst i fullmäktiges protokoll. Ett utkast eller en granskad rättelse ändrar inget.
    ratta(conn, kf, 5, "diarienummer", ["KS/2026-1"], publicera=False)
    assert arende(ks, 10) != arende(kf, 5)
    [r] = rattelser.lista(conn, "granskad")
    rattelser.publicera(conn, r["id"], "utgivare@test")
    assert arende(ks, 10) == arende(kf, 5)
    arendet = arenden.las_arende(conn, arende(kf, 5))
    assert [b["paragraf"] for b in arendet["behandlingar"]] == [10, 5]
    assert arendet["behandlingar"][1]["rattelser"]["diarienummer"]["nytt"] == ["KS/2026-1"]


def test_publicerad_rattelse_av_beslutet_galler_i_jamforelsen_med_planen(conn):
    kf = sammantrade(conn, "KF", date(2026, 9, 28))
    behandling(conn, kf, 130, "Svar på återremiss gällande sammanträdestider 2027",
               "Kommunfullmäktige beslutar\natt kommunfullmäktige sammanträder kl. 13.15 följande datum: "
               "22 februari och 22 mars.")
    assert set(sammantradesplan.beslut_om_planer(conn)[("KF", 2027)]["datum"]) == {date(2027, 2, 22), date(2027, 3, 22)}
    ratta(conn, kf, 130, "beslut", "Kommunfullmäktige beslutar\natt kommunfullmäktige sammanträder kl. 13.15 "
                                   "följande datum: 22 februari, 22 mars och 26 april.")
    assert set(sammantradesplan.beslut_om_planer(conn)[("KF", 2027)]["datum"]) == {
        date(2027, 2, 22), date(2027, 3, 22), date(2027, 4, 26)}


def test_inga_dubbletter_av_lasningen_kvar():
    """Ingen annan modul läser behandlingar med egen DISTINCT ON eller importerar privata namn (#101)."""
    from pathlib import Path
    import re

    app = Path(arenden.__file__).parent
    for fil in app.rglob("*.py"):
        text = fil.read_text(encoding="utf-8")
        if fil.name != "behandlingar.py":
            assert "DISTINCT ON (b.sammantrade_id, b.paragraf)" not in text, fil
        assert not re.search(r"^from \.[\w.]* import .*\b_[A-Za-z]", text, re.M), fil

