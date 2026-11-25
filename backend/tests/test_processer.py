"""Processer ur reglementen och delegationsordningar (#152).

Söm 1: samma egna sida av styrande dokument som för motstridigheterna (`RUBRIKER` i test_motstridigheter), med det
gemensamma reglementet och samhällsnämndens delegationsordning. Stegen citerar kallelsen (§ 13) och justeringen
(§ 26) i det gemensamma reglementet, som issuen kräver.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from test_motstridigheter import (
    GEMENSAMT_ID, LANDSBYGD_ID, RUBRIKER, SAMHALLSNAMNDEN_ID, logga_in, publicera as publicera_motstridighet,
)
from test_motstridigheter import las_in as las_in_motstridigheter
from test_styrande_dokument import ATTEST, GEMENSAMT, REGLEMENTEN, Sida, app_med, inspelad, kor

from app import db, processer

REDAKTOR = "test-redaktor@kommunkollen.test"

KALLELSE = {
    "process": "Kallelse till sammanträde",
    "steg": [
        {"vem": "Ordföranden", "vad": "Ansvarar för att kallelsen utfärdas digitalt, med tid och plats.",
         "kalla": {"dokument": GEMENSAMT_ID, "sida": 4, "paragraf": "§ 12",
                   "text": "Ordförande ansvarar för att kallelse i digital form utfärdas till sammanträdena."}},
        {"vem": "Ordföranden", "vad": "Kallelsen skickas digitalt till varje ledamot och ersättare.",
         "nar": "Senast fem dagar före sammanträdesdagen",
         "kalla": {"dokument": GEMENSAMT_ID, "sida": 4, "paragraf": "§ 13",
                   "text": "Kallelsen ska digitalt tillsändas varje ledamot och ersättare senast fem dagar före "
                           "sammanträdesdagen."}},
    ],
}
JUSTERING = {
    "process": "Justering av protokoll",
    "steg": [
        {"vem": "Ordföranden och en ledamot", "vad": "Justerar protokollet.",
         "nar": "Senast 14 dagar efter sammanträdet",
         "kalla": {"dokument": GEMENSAMT_ID, "sida": 5, "paragraf": "§ 26",
                   "text": "Protokoll justeras senast 14 dagar efter sammanträdet av ordförande och en ledamot."}},
    ],
}
DELEGATION = {
    "process": "Anmälan av delegationsbeslut",
    "steg": [
        {"vem": "Ordföranden", "vad": "Anmäler beslut i brådskande ärenden till nämnden.",
         "nar": "Vid nämndens nästkommande sammanträde",
         "kalla": {"dokument": SAMHALLSNAMNDEN_ID, "sida": 5, "paragraf": "Registrering och anmälan av delegationsbeslut",
                   "text": "beslut anmälas till nämnden vid dess nästkommande sammanträde"}},
    ],
}


@pytest.fixture
def api(database_url: str, google) -> TestClient:
    a = app_med(database_url, google, transport=Sida(RUBRIKER))
    assert kor(a)["status"] == "lyckad"
    return a


def las_in(database_url: str, *processlista: dict, redaktor: str = REDAKTOR) -> dict:
    with db.connect(database_url) as conn:
        res = processer.las_in(conn, {"processer": list(processlista)}, redaktor, datetime.now(timezone.utc))
        conn.commit()
    return res


def redaktionen(api: TestClient) -> dict[str, dict]:
    logga_in(api, "redaktor")
    svar = api.get("/api/processer/redaktion")
    assert svar.status_code == 200, svar.text
    return {p["namn"]: p for p in svar.json()["processer"]}


def publicera(api: TestClient, pid: int) -> dict:
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{pid}/granskning").status_code == 200
    svar = api.post(f"/api/processer/{pid}/publicering")
    assert svar.status_code == 200, svar.text
    return svar.json()


# Listan

def test_de_forsta_processerna_finns_och_en_redaktor_lagger_till_en_ny(api):
    lista = redaktionen(api)
    assert list(lista) == ["Kallelse till sammanträde", "Justering av protokoll", "Motion", "Medborgarförslag",
                           "Anmälan av delegationsbeslut", "Budgetprocessen", "E-förslag"]
    assert all(p["granskning"] == "utkast" and p["steg"] == [] for p in lista.values())

    svar = api.post("/api/processer", json={"namn": "  Interpellation ", "beskrivning": "Fråga till ett kommunalråd."})
    assert svar.status_code == 200, svar.text
    ny = svar.json()
    assert (ny["namn"], ny["ordning"], ny["granskning"], ny["redaktorer"]) == ("Interpellation", 8, "utkast", [REDAKTOR])
    assert api.post("/api/processer", json={"namn": "interpellation"}).status_code == 409
    assert api.post("/api/processer", json={"namn": ""}).status_code == 422
    # En utgivare lägger inte till processer, och läsaren inte heller.
    logga_in(api, "utgivare")
    assert api.post("/api/processer", json={"namn": "Ny"}).status_code == 403
    logga_in(api, None)
    assert api.post("/api/processer", json={"namn": "Ny"}).status_code in (401, 403)
    assert api.get("/api/processer").json()["processer"] == []


def test_en_process_utan_steg_kan_inte_granskas(api):
    pid = redaktionen(api)["Motion"]["id"]
    logga_in(api, "utgivare")
    svar = api.post(f"/api/processer/{pid}/granskning")
    assert svar.status_code == 409
    assert "inga steg" in svar.json()["detail"]


# Skillens inläsning

def test_skillen_laser_in_kallelsen_och_justeringen_ur_det_gemensamma_reglementet(api, database_url):
    assert las_in(database_url, KALLELSE, JUSTERING) == {"nya": 2, "oforandrade": 0}
    # Samma fil igen läses inte in två gånger.
    assert las_in(database_url, KALLELSE, JUSTERING) == {"nya": 0, "oforandrade": 2}
    lista = redaktionen(api)
    kallelse = lista["Kallelse till sammanträde"]
    assert (kallelse["granskning"], kallelse["redaktorer"]) == ("utkast", [REDAKTOR])
    assert [s["ordning"] for s in kallelse["steg"]] == [1, 2]
    fem = kallelse["steg"][1]
    assert (fem["vem"], fem["nar"]) == ("Ordföranden", "Senast fem dagar före sammanträdesdagen")
    k = fem["kalla"]
    assert k["titel"] == "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun"
    assert (k["version"], k["sida"], k["paragraf"]) == (1, 4, "§ 13")
    assert k["kopia"].endswith("/versioner/1#page=4")
    [justering] = lista["Justering av protokoll"]["steg"]
    assert (justering["nar"], justering["kalla"]["paragraf"], justering["kalla"]["sida"]) == (
        "Senast 14 dagar efter sammanträdet", "§ 26", 5)


def utan(d: dict, nyckel: str) -> dict:
    return {k: v for k, v in d.items() if k != nyckel}


STEG = JUSTERING["steg"][0]


@pytest.mark.parametrize(("steg", "fel"), [
    (utan(STEG, "kalla"), "källan saknas"),
    (STEG | {"kalla": utan(STEG["kalla"], "paragraf")}, "paragrafen saknas"),
    (STEG | {"kalla": utan(STEG["kalla"], "text")}, "citatet saknas"),
    (STEG | {"kalla": STEG["kalla"] | {"text": "justeras senast 21 dagar"}}, "står inte ordagrant på sidan 5"),
    (STEG | {"kalla": STEG["kalla"] | {"dokument": LANDSBYGD_ID}}, "ingår inte i analysen"),
    (STEG | {"kalla": STEG["kalla"] | {"dokument": "18.finnsinte"}}, "finns inte"),
    (utan(STEG, "vem"), "vem som gör något saknas"),
    (utan(STEG, "vad"), "vad som görs saknas"),
    (STEG | {"hur": "Digitalt"}, "okända fält"),
])
def test_inlasningen_avvisar_ett_steg_utan_kalla_eller_utanfor_de_25(api, database_url, steg, fel):
    with pytest.raises(processer.Ogiltig, match=fel) as e:
        las_in(database_url, KALLELSE, {"process": "Justering av protokoll", "steg": [steg]})
    assert str(e.value).startswith("Process 2 (Justering av protokoll), steg 1")
    # Ingenting läses in när något avvisas.
    assert all(p["steg"] == [] for p in redaktionen(api).values())


def test_inlasningen_avvisar_en_process_som_inte_finns_pa_listan(api, database_url):
    with pytest.raises(processer.Ogiltig, match="finns inte på redaktionens lista"):
        las_in(database_url, {"process": "Interpellation", "steg": [STEG]})
    with pytest.raises(processer.Ogiltig, match="stegen saknas"):
        las_in(database_url, {"process": "Motion", "steg": []})
    with pytest.raises(processer.Ogiltig, match="två gånger"):
        las_in(database_url, JUSTERING, JUSTERING)


def test_kommandoraden_laser_in_filen(api, database_url, monkeypatch, capsys, tmp_path):
    import json

    fil = tmp_path / "processer.json"
    fil.write_text(json.dumps({"processer": [JUSTERING]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", database_url)
    processer.main([str(fil), "--redaktor", REDAKTOR, "--prova"])
    assert "1 processer: 1 med nya steg som utkast, 0 oförändrade. Provet sparades inte." in capsys.readouterr().out
    assert redaktionen(api)["Justering av protokoll"]["steg"] == []
    processer.main([str(fil), "--redaktor", REDAKTOR])
    assert len(redaktionen(api)["Justering av protokoll"]["steg"]) == 1


# Granskning

def test_ingen_godkanner_sin_egen_process_och_lasaren_ser_bara_publicerade(api, database_url):
    las_in(database_url, JUSTERING, redaktor="test-utgivare@kommunkollen.test")
    pid = redaktionen(api)["Justering av protokoll"]["id"]
    logga_in(api, "utgivare")
    svar = api.post(f"/api/processer/{pid}/granskning")
    assert svar.status_code == 403
    assert "själv" in svar.json()["detail"]
    logga_in(api, "redaktor")
    assert api.post(f"/api/processer/{pid}/granskning").status_code == 403

    # Den som lade till processen på listan godkänner den inte heller, även om någon annan läste in stegen.
    with db.connect(database_url) as conn:
        egen = processer.lagg_till(conn, {"namn": "Interpellation"}, "test-utgivare@kommunkollen.test",
                                   datetime.now(timezone.utc))
    las_in(database_url, {"process": "Interpellation", "steg": [STEG]})
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{egen['id']}/granskning").status_code == 403
    logga_in(api, None)
    assert api.get("/api/processer").json()["processer"] == []
    assert api.get(f"/api/processer/{pid}").status_code == 404
    [d] = [d for d in api.get("/api/styrande-dokument").json()["dokument"] if d["titel"].startswith("Gemensamt")]
    assert d["processer"] == 0
    assert api.get(f"/api/styrande-dokument/{d['id']}").json()["processer"] == []


def test_en_publicerad_process_syns_pa_processidan_dokumentsidan_och_i_listan(api, database_url):
    las_in(database_url, KALLELSE, JUSTERING, DELEGATION)
    lista = redaktionen(api)
    pid = lista["Kallelse till sammanträde"]["id"]
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{pid}/publicering").status_code == 409  # inte direkt från utkast
    publicera(api, pid)
    publicera(api, lista["Justering av protokoll"]["id"])

    logga_in(api, None)
    pub = api.get("/api/processer").json()["processer"]
    assert [p["namn"] for p in pub] == ["Kallelse till sammanträde", "Justering av protokoll"]
    assert "redaktorer" not in pub[0]
    sida = api.get(f"/api/processer/{pid}").json()
    assert [s["kalla"]["paragraf"] for s in sida["steg"]] == ["§ 12", "§ 13"]
    assert [d["titel"] for d in sida["dokument"]] == [
        "Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun"]

    dokument = {d["titel"]: d for d in api.get("/api/styrande-dokument").json()["dokument"]}
    gemensamt = dokument["Gemensamt reglemente för kommunstyrelse och nämnder i Härnösands kommun"]
    assert gemensamt["processer"] == 2
    assert dokument["Delegationsordning för samhällsnämnden"]["processer"] == 0  # inte publicerad
    assert api.get(f"/api/styrande-dokument/{gemensamt['id']}").json()["processer"] == [
        {"id": pid, "namn": "Kallelse till sammanträde", "steg": 2},
        {"id": lista["Justering av protokoll"]["id"], "namn": "Justering av protokoll", "steg": 1},
    ]

    # En publicerad process läses inte in med andra steg. Den återkallas först.
    andrad = KALLELSE | {"steg": KALLELSE["steg"][1:]}
    with pytest.raises(processer.Konflikt, match="publicerad"):
        las_in(database_url, andrad)
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{pid}/aterkallelse", json={}).status_code == 422
    svar = api.post(f"/api/processer/{pid}/aterkallelse", json={"motivering": "Stegen läses in på nytt."})
    assert svar.json()["granskning"] == "aterkallad"
    assert las_in(database_url, andrad)["nya"] == 1
    assert redaktionen(api)["Kallelse till sammanträde"]["granskning"] == "utkast"
    # Samma steg i en återkallad process blir också ett nytt utkast.
    jid = redaktionen(api)["Justering av protokoll"]["id"]
    logga_in(api, "utgivare")
    api.post(f"/api/processer/{jid}/aterkallelse", json={"motivering": "Granskas igen."})
    assert las_in(database_url, JUSTERING)["nya"] == 1
    assert redaktionen(api)["Justering av protokoll"]["granskning"] == "utkast"


def test_en_process_som_inte_ska_beskrivas_avvisas(api):
    pid = redaktionen(api)["Medborgarförslag"]["id"]
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{pid}/avvisning", json={}).status_code == 422
    svar = api.post(f"/api/processer/{pid}/avvisning", json={"motivering": "Medborgarförslag finns inte längre."})
    assert (svar.json()["granskning"], svar.json()["avvisning"]) == ("avvisad", "Medborgarförslag finns inte längre.")


def test_en_publicerad_motstridighet_visas_vid_steget_den_citerar(api, database_url):
    motsagelse = {
        "typ": "motsagelse",
        "forklaring": "Det gemensamma reglementet anger fem dagar (s. 4). Testdata anger något annat (s. 5).",
        "citat": [
            {"dokument": GEMENSAMT_ID, "sida": 4, "paragraf": "13 §", "text": "senast fem dagar före sammanträdesdagen"},
            {"dokument": GEMENSAMT_ID, "sida": 5, "paragraf": "§ 26", "text": "Protokoll justeras senast 14 dagar"},
        ],
    }
    las_in_motstridigheter(database_url, {"motstridigheter": [motsagelse]})
    logga_in(api, "redaktor")
    [m] = [m for m in api.get("/api/motstridigheter/forslag").json()["forslag"] if m["kalla"] == "skill"]
    las_in(database_url, KALLELSE)
    pid = redaktionen(api)["Kallelse till sammanträde"]["id"]
    publicera(api, pid)
    logga_in(api, None)
    # Inte publicerad än: visas inte.
    assert all(s["motstridigheter"] == [] for s in api.get(f"/api/processer/{pid}").json()["steg"])
    publicera_motstridighet(api, m["id"])
    logga_in(api, None)
    tolv, tretton = api.get(f"/api/processer/{pid}").json()["steg"]
    assert tolv["motstridigheter"] == []  # samma sida, annan paragraf
    assert [x["id"] for x in tretton["motstridigheter"]] == [m["id"]]


# Ett citerat dokument ändras

def test_en_ny_version_marker_bara_stegen_som_citerar_dokumentet(database_url, google):
    sida = Sida(RUBRIKER)
    api = app_med(database_url, google, transport=sida)
    kor(api)
    las_in(database_url, KALLELSE, DELEGATION)
    lista = redaktionen(api)
    pid = lista["Kallelse till sammanträde"]["id"]
    publicera(api, pid)

    # Kommunen byter ut det gemensamma reglementet: samma id, ny tidsstämpel, annat innehåll.
    ny = GEMENSAMT.replace("1758202788908", "1790000000000")
    sida.filer[ny] = inspelad(ATTEST)
    sida.satt(RUBRIKER | {REGLEMENTEN: [ny, *RUBRIKER[REGLEMENTEN][1:]]})
    logga_in(api, "redaktor")
    assert kor(api)["status"] == "lyckad"

    lista = redaktionen(api)
    kallelse = lista["Kallelse till sammanträde"]
    assert kallelse["granskning"] == "publicerad"  # processen förblir publicerad
    assert all(s["dokument_andrat"] for s in kallelse["steg"])
    assert all(s["kalla"]["version"] == 1 for s in kallelse["steg"])
    # Delegationsordningen har inte ändrats.
    assert [s["dokument_andrat"] for s in lista["Anmälan av delegationsbeslut"]["steg"]] == [None]
    assert [p["id"] for p in api.get("/api/processer/redaktion").json()["andrade"]] == [pid]

    logga_in(api, None)
    assert api.get(f"/api/processer/{pid}").json()["dokument_andrat"] is True

    # Den nya versionen har inte citatet längre, så steget kan inte bara godkännas.
    logga_in(api, "redaktor")
    sid = kallelse["steg"][0]["id"]
    svar = api.post(f"/api/processer/{pid}/steg/{sid}/stallning")
    assert svar.status_code == 409
    assert "står inte längre" in svar.json()["detail"]


def test_en_redaktor_tar_stallning_till_ett_andrat_steg(api, database_url):
    las_in(database_url, JUSTERING)
    pid = redaktionen(api)["Justering av protokoll"]["id"]
    publicera(api, pid)
    with db.connect(database_url) as conn:
        did = conn.execute("SELECT id FROM styrande_dokument WHERE sitevision_id = %s", (GEMENSAMT_ID,)).fetchone()["id"]
        # En ny version med samma text.
        conn.execute("INSERT INTO styrande_dokument_version (dokument_id, version, url, sha256, storlek, innehall, "
                     "hamtad, sidor, ocr, dokumentinformation) SELECT dokument_id, 2, url, 'ny', storlek, innehall, "
                     "now(), sidor, ocr, dokumentinformation FROM styrande_dokument_version WHERE dokument_id = %s",
                     (did,))
        processer.markera_andrat(conn, did, datetime.now(timezone.utc).date())
        conn.commit()
    [steg] = redaktionen(api)["Justering av protokoll"]["steg"]
    assert steg["dokument_andrat"] is not None
    logga_in(api, "utgivare")
    assert api.post(f"/api/processer/{pid}/steg/{steg['id']}/stallning").status_code == 403
    logga_in(api, "redaktor")
    svar = api.post(f"/api/processer/{pid}/steg/{steg['id']}/stallning")
    assert svar.status_code == 200, svar.text
    [steg] = svar.json()["steg"]
    assert (steg["dokument_andrat"], steg["kalla"]["version"]) == (None, 2)
    assert api.post(f"/api/processer/{pid}/steg/{steg['id']}/stallning").status_code == 409
