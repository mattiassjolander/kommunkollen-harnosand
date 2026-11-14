"""Reviderade uppgifter: ett ändrat värde blir en ny version och historiken bevaras (kravspec 11.5, 12.3)."""

import json
import shutil

from fastapi.testclient import TestClient

from conftest import INSPELNINGAR, skapa_app

MATT = "kolada:N03007"
NYCKEL = "api.kolada.se/v3/data/kpi/N03007/municipality/2280"


def revidera(katalog, period: int, nytt: float) -> float:
    """Ändrar ett värde i den inspelade filen, som när Kolada publicerar en revidering."""
    manifest = json.loads((katalog / "manifest.json").read_text(encoding="utf-8"))
    fil = katalog / manifest[NYCKEL]
    data = json.loads(fil.read_text(encoding="utf-8-sig"))
    for rad in data["values"]:
        if rad["period"] == period:
            for v in rad["values"]:
                if v["gender"] == "T":
                    gammalt, v["value"] = v["value"], nytt
    fil.write_text(json.dumps(data), encoding="utf-8")
    return gammalt


def kolada(korning: dict) -> dict:
    return next(k for k in korning["kallor"] if k["datakalla_id"] == "kolada")


def punkt(api: TestClient, period: str) -> dict:
    return next(p for p in api.get(f"/api/matt/{MATT}/serie").json()["punkter"] if p["period"] == period)


def test_reviderat_varde_blir_ny_version_och_tidigare_finns_kvar(database_url, google, tmp_path):
    katalog = tmp_path / "rec"
    shutil.copytree(INSPELNINGAR, katalog)
    api = TestClient(skapa_app(database_url, google, inspelningar=katalog, anonym_lasning=True))
    assert api.post("/api/auth/test/redaktor").status_code == 200

    api.post("/api/insamlingar")
    fore = punkt(api, "2024")
    orort = punkt(api, "2023")
    assert fore["version"] == 1 and fore["reviderad"] is False and fore["historik"] == []

    gammalt = revidera(katalog, 2024, 1234.5)
    korning = api.post("/api/insamlingar").json()
    assert kolada(korning)["status"] == "lyckad"
    assert kolada(korning)["antal_andrade"] == 1
    assert kolada(korning)["antal_nya"] == 0

    efter = punkt(api, "2024")
    assert efter["varde"] == 1234.5
    assert efter["version"] == 2
    assert efter["reviderad"] is True
    [tidigare] = efter["historik"]
    assert tidigare["varde"] == gammalt
    assert tidigare["version"] == 1
    assert tidigare["hamtad"] == fore["hamtad"]

    # Alla fyra tidpunkterna finns: källans publicering, period, senast hämtad och senast ändrad.
    assert efter["kallans_publicering"]
    assert efter["period"] == "2024"
    assert efter["senast_andrad"] > fore["senast_andrad"]
    assert efter["senast_hamtad"] >= efter["senast_andrad"]

    # Ett oförändrat värde får ingen ny version.
    assert punkt(api, "2023") | {"senast_hamtad": None} == orort | {"senast_hamtad": None}

    # En tredje insamling utan ändringar rör inte historiken.
    korning = api.post("/api/insamlingar").json()
    assert kolada(korning)["status"] == "inga_nya"
    assert punkt(api, "2024")["historik"] == efter["historik"]
    assert punkt(api, "2024")["version"] == 2


def test_revidering_till_saknat_varde_bevarar_det_tidigare(database_url, google, tmp_path):
    katalog = tmp_path / "rec"
    shutil.copytree(INSPELNINGAR, katalog)
    api = TestClient(skapa_app(database_url, google, inspelningar=katalog, anonym_lasning=True))
    api.post("/api/auth/test/redaktor")
    api.post("/api/insamlingar")
    gammalt = revidera(katalog, 2024, None)
    api.post("/api/insamlingar")
    p = punkt(api, "2024")
    assert p["varde"] is None  # saknat, aldrig noll
    assert p["historik"][0]["varde"] == gammalt
