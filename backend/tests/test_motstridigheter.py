"""Motstridigheter i styrande dokument (#151).

Söm 1: en egen sida av styrande dokument med länkar till inspelade filer (`Sida` i test_styrande_dokument), bland
dem de fyra fallen i issuen: det gemensamma reglementet, de två reglementena för partistöd, riktlinjerna för
landsbygdsmedel som ligger ute två gånger och samhällsnämndens konsoliderade delegationsordning.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_styrande_dokument import ATTEST, GEMENSAMT, REGLEMENTEN, SAMHALLSNAMNDEN, Sida, app_med, inspelad, kor

from app import db, motstridigheter

PARTISTOD = ("https://harnosand.se/download/18.7678e457188f04167047f857/1687853606631/"
             "Reglemente%20f%C3%B6r%20kommunalt%20partist%C3%B6d%202023-2026.pdf")
PARTISTOD_UTKAST = ("https://harnosand.se/download/18.580e43d7163221b2781b7407/1663078199525/"
                    "Reglemente%20kommunalt%20partist%C3%B6d.pdf")
LANDSBYGD = ("https://harnosand.se/download/18.5d78c790194f4b101e358e28/1739370577903/"
             "Riktlinjer%20f%C3%B6r%20landsbygdsmedel%202025-2027.pdf")
LANDSBYGD_TANKSTRECK = ("https://harnosand.se/download/18.5d78c790194f4b101e359266/1739370617728/"
                        "Riktlinjer%20f%C3%B6r%20landsbygdsmedel%202025%E2%80%932027.pdf")
KONSOLIDERAD = ("https://harnosand.se/download/18.32ef4911832d26bbc62e0bd/1662993134811/"
                "2021-06-17,%20Delegationsordning%20(konsoliderad%20version).pdf")

GEMENSAMT_ID = "18.580e43d7163221b2781b73fe"
SAMHALLSNAMNDEN_ID = "18.4b6c551c1679dec5d0a4a691"
KONSOLIDERAD_ID = "18.32ef4911832d26bbc62e0bd"
LANDSBYGD_ID = "18.5d78c790194f4b101e358e28"

RUBRIKER = {
    REGLEMENTEN: [GEMENSAMT, PARTISTOD, PARTISTOD_UTKAST, ATTEST],
    "Riktlinjer - rutiner": [LANDSBYGD, LANDSBYGD_TANKSTRECK],
    "Delegationer": [SAMHALLSNAMNDEN, KONSOLIDERAD],
}

KAPITEL = {
    "typ": "felaktig_hanvisning",
    "forklaring": "Reglementet anger att verksamheten tydliggörs i kapitel 2 till 9 (s. 3). "
                  "Innehållsförteckningen har kapitel 1–8 (s. 2).",
    "citat": [{"dokument": GEMENSAMT_ID, "sida": 3, "text": "verksamhet och uppgifter i kapitel 2 till 9"}],
    "uppgift": {"text": "Reglementet har kapitel 1–8.", "dokument": GEMENSAMT_ID, "sida": 2},
}
DELEGATIONSORDNINGAR = {
    "typ": "flera_versioner",
    "forklaring": "Samhällsnämndens delegationsordning ligger ute både som ”Delegationsordning för samhällsnämnden” "
                  "och som en konsoliderad version från 2021-06-17.",
    "dokument": [SAMHALLSNAMNDEN_ID, KONSOLIDERAD_ID],
}


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = app_med(database_url, google, transport=Sida(RUBRIKER))
    res = kor(a)
    assert res["status"] == "lyckad", res
    return a


def logga_in(api: TestClient, roll: str | None) -> None:
    api.post("/api/auth/logga-ut")
    if roll:
        assert api.post(f"/api/auth/test/{roll}").status_code == 200


def las_in(database_url: str, data: dict, redaktor: str = "test-redaktor@kommunkollen.test") -> dict:
    with db.connect(database_url) as conn:
        res = motstridigheter.las_in(conn, data, redaktor, datetime.now(timezone.utc))
        conn.commit()
    return res


def forslag(api: TestClient, **params) -> list[dict]:
    logga_in(api, "redaktor")
    svar = api.get("/api/motstridigheter/forslag", params=params)
    assert svar.status_code == 200, svar.text
    return svar.json()["forslag"]


def titlar(m: dict) -> set[str]:
    return {d["titel"] for d in m["dokument"]}


# Maskinella kandidater

def test_insamlingen_foreslar_flera_gallande_versioner_ur_diarienummer_och_titel(api):
    kandidater = forslag(api)
    assert {frozenset(titlar(m)) for m in kandidater} == {
        frozenset({"Reglemente för kommunalt partistöd 2023-2026", "Reglemente kommunalt partistöd"}),
        frozenset({"Riktlinjer för landsbygdsmedel 2025-2027", "Riktlinjer för landsbygdsmedel 2025–2027"}),
    }
    parti = next(m for m in kandidater if "Reglemente kommunalt partistöd" in titlar(m))
    assert (parti["typ"], parti["kalla"], parti["grund"], parti["granskning"]) == (
        "flera_versioner", "insamling", "samma diarienummer", "utkast")
    assert parti["forklaring"] == ("”Reglemente för kommunalt partistöd 2023-2026” och ”Reglemente kommunalt partistöd” "
                                   "har samma diarienummer i dokumentinformationen, 2022-000209.")
    land = next(m for m in kandidater if m is not parti)
    assert land["grund"] == "titlar som bara skiljer sig i skiljetecken eller årtal"
    # Förslagen syns inte för läsaren.
    logga_in(api, None)
    assert api.get("/api/motstridigheter").json()["motstridigheter"] == []
    # En ny kontroll föreslår inte samma sak igen.
    logga_in(api, "redaktor")
    kor(api)
    assert len(forslag(api)) == 2


def lagg_in(conn, titel: str, info: dict, n: int) -> int:
    did = conn.execute(
        "INSERT INTO styrande_dokument (sitevision_id, url, filnamn, titel, kategorier, forst_sedd, senast_sedd) "
        "VALUES (%s, %s, %s, %s, %s, now(), now()) RETURNING id",
        (f"18.test{n}", f"https://harnosand.se/download/18.test{n}/1/x.pdf", "x.pdf", titel, [REGLEMENTEN]),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO styrande_dokument_version (dokument_id, version, url, sha256, storlek, innehall, hamtad, sidor, "
        "ocr, dokumentinformation) VALUES (%s, 1, 'u', %s, 1, '', now(), %s, false, %s)",
        (did, f"sha{n}", ["text"], Jsonb({"ruta": True} | info)),
    )
    return did


def test_kandidaterna_kanner_igen_diarienummer_i_olika_skrivsatt_och_titlar_med_olika_streck(database_url):
    db.migrate(database_url)
    with db.connect(database_url) as conn:
        kf = {"faststalld_av": "Kommunfullmäktige"}
        a = lagg_in(conn, "Reglemente för A", kf | {"diarienummer": "KS/2022-000209"}, 1)
        b = lagg_in(conn, "Reglemente B", kf | {"diarienummer": "2022-000209"}, 2)
        c = lagg_in(conn, "Riktlinjer för C 2025-2027", {}, 3)
        d = lagg_in(conn, "Riktlinjer för C 2025 – 2027", {}, 4)
        # Två olika dokument: olika diarienummer och titlar som skiljer sig i mer än skiljetecken och årtal.
        lagg_in(conn, "Delegationsordning för skolnämnden", kf | {"diarienummer": "KS/2022-000210"}, 5)
        lagg_in(conn, "Delegationsordning för socialnämnden", kf | {"diarienummer": "KS/2023-000209"}, 6)
        # Ett utgånget dokument är ingen gällande version.
        lagg_in(conn, "Riktlinjer för C 2019-2022", {}, 7)
        assert motstridigheter.foresla_kandidater(conn, date(2026, 11, 20), datetime.now(timezone.utc)) == 2
        grupper = {tuple(r["dokument_ids"]) for r in conn.execute("SELECT dokument_ids FROM motstridighet")}
        assert grupper == {(a, b), (c, d)}


def test_titelnyckeln_tar_bort_artal_datum_och_skiljetecken():
    t = motstridigheter.titelnyckel
    assert t("Riktlinjer för landsbygdsmedel 2025-2027") == t("Riktlinjer för landsbygdsmedel 2025–2027")
    assert t("Reglemente - Ungdomsrådet") == t("Reglemente Ungdomsrådet")
    assert t("Delegationsordning för skolnämnden") != t("Delegationsordning för socialnämnden")


# Skillens inläsning

def test_skillen_laser_in_en_felaktig_hanvisning_och_flera_versioner_med_kalla(api, database_url):
    assert las_in(database_url, {"motstridigheter": [KAPITEL, DELEGATIONSORDNINGAR]}) == {"nya": 2, "oforandrade": 0}
    # Samma fil igen läses inte in två gånger.
    assert las_in(database_url, {"motstridigheter": [KAPITEL, DELEGATIONSORDNINGAR]}) == {"nya": 0, "oforandrade": 2}
    alla = forslag(api)
    kapitel = next(m for m in alla if m["typ"] == "felaktig_hanvisning")
    assert kapitel["kalla"] == "skill"
    assert kapitel["redaktorer"] == ["test-redaktor@kommunkollen.test"]
    [citat] = kapitel["citat"]
    assert citat["titel"] == "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun"
    assert (citat["version"], citat["sida"], citat["text"]) == (1, 3, "verksamhet och uppgifter i kapitel 2 till 9")
    assert citat["kopia"].endswith("/versioner/1#page=3")
    assert (kapitel["uppgift"]["text"], kapitel["uppgift"]["sida"]) == ("Reglementet har kapitel 1–8.", 2)
    deleg = next(m for m in alla if m["typ"] == "flera_versioner" and m["kalla"] == "skill")
    assert titlar(deleg) == {"Delegationsordning för samhällsnämnden",
                             "2021-06-17, Delegationsordning (konsoliderad version)"}


def test_skillen_och_insamlingen_foreslar_inte_samma_sak_tva_ganger(api, database_url):
    samma = {"typ": "flera_versioner", "forklaring": "Reglementet för partistöd ligger ute två gånger.",
             "dokument": ["18.580e43d7163221b2781b7407", "18.7678e457188f04167047f857"]}
    assert las_in(database_url, {"motstridigheter": [samma]}) == {"nya": 0, "oforandrade": 1}


MOTSAGELSE = {
    "typ": "motsagelse",
    "forklaring": "Dokument A anger X (s. 3). Dokument B anger Y (s. 2).",
    "citat": [
        {"dokument": GEMENSAMT_ID, "sida": 3, "paragraf": "Inledning", "text": "verksamhet och uppgifter i kapitel 2 till 9"},
        {"dokument": GEMENSAMT_ID, "sida": 2, "paragraf": "Innehåll", "text": "Innehåll"},
    ],
}


@pytest.mark.parametrize(("andring", "fel"), [
    ({"citat": MOTSAGELSE["citat"][:1]}, "citerar båda ställena"),
    ({"citat": [MOTSAGELSE["citat"][0] | {"sida": None}, MOTSAGELSE["citat"][1]]}, "sidan saknas"),
    ({"citat": [MOTSAGELSE["citat"][0] | {"sida": 99}, MOTSAGELSE["citat"][1]]}, "har 19 sidor"),
    ({"citat": [{k: v for k, v in MOTSAGELSE["citat"][0].items() if k != "paragraf"}, MOTSAGELSE["citat"][1]]},
     "paragrafen saknas"),
    ({"citat": [MOTSAGELSE["citat"][0] | {"text": "kapitel 2 till 10"}, MOTSAGELSE["citat"][1]]},
     "står inte ordagrant på sidan 3"),
    ({"typ": "dubblett"}, "okänd typ"),
    ({"forklaring": "Det är ett fel i reglementet."}, "ordet \"fel\""),
    ({"forklaring": "Reglementet har en brist."}, "ordet \"brist\""),
    ({"forklaring": "Reglementet motsäger sig själv."}, "motsäger sig själv"),
    ({"forklaring": "A anger X. B anger Y. C anger Z."}, "längre än två meningar"),
    ({"citat": [MOTSAGELSE["citat"][0] | {"dokument": LANDSBYGD_ID}, MOTSAGELSE["citat"][1]]},
     "ingår inte i analysen"),
    ({"citat": [MOTSAGELSE["citat"][0] | {"dokument": "18.finnsinte"}, MOTSAGELSE["citat"][1]]}, "finns inte"),
])
def test_inlasningen_avvisar_ofullstandiga_forslag(api, database_url, andring, fel):
    with pytest.raises(motstridigheter.Ogiltig, match=fel) as e:
        las_in(database_url, {"motstridigheter": [KAPITEL, MOTSAGELSE | andring]})
    assert str(e.value).startswith("Motstridighet 2")
    # Ingenting läses in när något avvisas.
    assert all(m["kalla"] == "insamling" for m in forslag(api))


def test_en_giltig_motsagelse_och_en_hanvisning_utan_uppgift(api, database_url):
    assert las_in(database_url, {"motstridigheter": [MOTSAGELSE]})["nya"] == 1
    utan = KAPITEL | {"uppgift": None}
    with pytest.raises(motstridigheter.Ogiltig, match="uppgiften om det som finns saknas"):
        las_in(database_url, {"motstridigheter": [utan]})


def test_kommandoraden_laser_in_filen(api, database_url, monkeypatch, capsys, tmp_path):
    import json

    fil = tmp_path / "motstridigheter.json"
    fil.write_text(json.dumps({"motstridigheter": [KAPITEL]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", database_url)
    motstridigheter.main([str(fil), "--redaktor", "test-redaktor@kommunkollen.test"])
    assert "1 motstridigheter: 1 nya utkast, 0 fanns redan." in capsys.readouterr().out


# Granskning, publicering och status

def publicera(api: TestClient, mid: int) -> dict:
    logga_in(api, "utgivare")
    assert api.post(f"/api/motstridigheter/{mid}/granskning").status_code == 200
    svar = api.post(f"/api/motstridigheter/{mid}/publicering")
    assert svar.status_code == 200, svar.text
    return svar.json()


def test_ingen_godkanner_sitt_eget_forslag_och_lasaren_ser_bara_publicerade(api, database_url):
    las_in(database_url, {"motstridigheter": [KAPITEL]}, redaktor="test-utgivare@kommunkollen.test")
    [m] = [m for m in forslag(api) if m["kalla"] == "skill"]
    logga_in(api, "utgivare")
    svar = api.post(f"/api/motstridigheter/{m['id']}/granskning")
    assert svar.status_code == 403
    assert "själv" in svar.json()["detail"]
    # En redaktör kan inte granska.
    logga_in(api, "redaktor")
    assert api.post(f"/api/motstridigheter/{m['id']}/granskning").status_code == 403
    # Inte publicerat än: dokumentsidan och listan visar inget.
    logga_in(api, None)
    [d] = [d for d in api.get("/api/styrande-dokument").json()["dokument"] if d["titel"].startswith("Gemensamt")]
    assert d["motstridigheter"] == 0
    assert api.get(f"/api/styrande-dokument/{d['id']}").json()["motstridigheter"] == []


def test_en_publicerad_motstridighet_far_status_och_kan_aterkallas(api, database_url):
    las_in(database_url, {"motstridigheter": [KAPITEL]})
    [m] = [m for m in forslag(api) if m["kalla"] == "skill"]
    # Publicera direkt från utkast går inte.
    logga_in(api, "utgivare")
    assert api.post(f"/api/motstridigheter/{m['id']}/publicering").status_code == 409
    publicera(api, m["id"])

    logga_in(api, None)
    lista = api.get("/api/motstridigheter").json()
    [pub] = lista["motstridigheter"]
    assert (pub["typnamn"], pub["statusnamn"], pub["statusdatum"]) == ("Felaktig hänvisning", "Ny", None)
    assert "redaktorer" not in pub
    assert next(t for t in lista["typer"] if t["id"] == "felaktig_hanvisning")["antal"] == 1
    [d] = [d for d in api.get("/api/styrande-dokument").json()["dokument"] if d["titel"].startswith("Gemensamt")]
    assert d["motstridigheter"] == 1
    assert [x["id"] for x in api.get(f"/api/styrande-dokument/{d['id']}").json()["motstridigheter"]] == [m["id"]]

    # Status sätts av en redaktör.
    assert api.post(f"/api/motstridigheter/{m['id']}/status", json={"status": "anmald"}).status_code in (401, 403)
    logga_in(api, "redaktor")
    svar = api.post(f"/api/motstridigheter/{m['id']}/status", json={"status": "anmald", "datum": "2026-11-21"})
    assert (svar.json()["statusnamn"], svar.json()["statusdatum"]) == ("Anmäld till kommunen", "2026-11-21")
    svar = api.post(f"/api/motstridigheter/{m['id']}/status", json={"status": "atgardad", "datum": "2026-12-01"})
    assert svar.status_code == 422  # åtgärdad kräver en anteckning
    svar = api.post(f"/api/motstridigheter/{m['id']}/status",
                    json={"status": "atgardad", "datum": "2026-12-01", "anteckning": "Kapitelhänvisningen rättad."})
    assert (svar.json()["statusnamn"], svar.json()["anteckning"]) == ("Åtgärdad av kommunen", "Kapitelhänvisningen rättad.")
    assert api.get("/api/motstridigheter", params={"status": "anmald"}).json()["motstridigheter"] == []
    with db.connect(database_url) as conn:
        assert [r["status"] for r in conn.execute(
            "SELECT status FROM motstridighet_status WHERE motstridighet_id = %s ORDER BY id", (m["id"],))] == [
            "anmald", "atgardad"]

    # Återkallas av en utgivare, med motivering.
    logga_in(api, "utgivare")
    assert api.post(f"/api/motstridigheter/{m['id']}/aterkallelse", json={}).status_code == 422
    svar = api.post(f"/api/motstridigheter/{m['id']}/aterkallelse", json={"motivering": "Kapitel 9 finns i bilagan."})
    assert svar.json()["granskning"] == "aterkallad"
    logga_in(api, None)
    assert api.get("/api/motstridigheter").json()["motstridigheter"] == []


def test_ett_forslag_som_inte_haller_avvisas(api):
    [m, *_] = forslag(api)
    logga_in(api, "utgivare")
    svar = api.post(f"/api/motstridigheter/{m['id']}/avvisning", json={"motivering": "Olika dokument."})
    assert svar.json()["granskning"] == "avvisad"
    assert m["id"] not in {x["id"] for x in forslag(api)}
    assert m["id"] in {x["id"] for x in forslag(api, granskning="avvisad")}


def test_granskningsvyn_filtreras_pa_typ_och_dokument(api, database_url):
    las_in(database_url, {"motstridigheter": [KAPITEL, DELEGATIONSORDNINGAR]})
    assert {m["typ"] for m in forslag(api, typ="felaktig_hanvisning")} == {"felaktig_hanvisning"}
    logga_in(api, "redaktor")
    vy = api.get("/api/motstridigheter/forslag").json()
    gemensamt = next(d for d in vy["dokument"] if d["titel"].startswith("Gemensamt"))
    assert [m["typ"] for m in forslag(api, dokument=gemensamt["id"])] == ["felaktig_hanvisning"]


# Ett berört dokument ändras

def test_en_ny_version_av_ett_berort_dokument_marker_motstridigheten(database_url, google):
    sida = Sida(RUBRIKER)
    api = app_med(database_url, google, transport=sida)
    kor(api)
    las_in(database_url, {"motstridigheter": [KAPITEL]})
    [m] = [m for m in forslag(api) if m["kalla"] == "skill"]
    publicera(api, m["id"])

    # Kommunen byter ut filen: samma id, ny tidsstämpel, annat innehåll.
    ny = GEMENSAMT.replace("1758202788908", "1790000000000")
    sida.filer[ny] = inspelad(ATTEST)
    sida.satt(RUBRIKER | {REGLEMENTEN: [ny, PARTISTOD, PARTISTOD_UTKAST, ATTEST]})
    logga_in(api, "redaktor")
    assert kor(api)["status"] == "lyckad"

    logga_in(api, None)
    [pub] = api.get("/api/motstridigheter").json()["motstridigheter"]
    assert pub["dokument_andrat"] is not None
    # Analysen körs inte om: citatet pekar fortfarande på versionen det kommer från.
    assert pub["citat"][0]["version"] == 1

    logga_in(api, "redaktor")
    vy = api.get("/api/motstridigheter/forslag").json()
    assert [x["id"] for x in vy["andrade"]] == [m["id"]]
    svar = api.post(f"/api/motstridigheter/{m['id']}/stallning")
    assert svar.json()["dokument_andrat"] is None
    assert next(d for d in svar.json()["dokument"] if d["titel"].startswith("Gemensamt"))["version"] == 2
    assert api.post(f"/api/motstridigheter/{m['id']}/stallning").status_code == 409
