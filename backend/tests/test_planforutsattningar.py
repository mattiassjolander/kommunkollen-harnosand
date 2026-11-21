"""Planförutsättningar per budgetår (#58): inläsningen av Excelfilen och beräkningarna mot förslagen.

Filen har en flik per budgetår med kolumnerna tabell, post, belopp i mnkr och källa. Rubriker,
formler och anteckningarna längst ner läses inte. Beräkningarna prövas med siffrorna för L, M och SD
2027 ur planförutsättningarna och förslagen.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from app import budgetforslag, planforutsattningar

FIXTUR = Path(__file__).parent / "fixtures" / "budgetforslag" / "planforutsattningar.xlsx"

# Planförutsättningarna 2027 (L s. 8).
NT_2027 = {
    "skattesats": 23.34, "skatteintakter": 1483.0, "bidrag": 734.0, "resultat": 50.0,
    "ramar": {"Kommunstyrelsen": 187.0, "Kommungemensam verksamhet": 147.0, "Kommunfullmäktige": 14.0,
              "Samhällsnämnden": 240.0, "Skolnämnden": 663.0, "Socialnämnden": 893.0},
}


def flik(tmp_path: Path, rader: list[tuple], namn: str = "2027") -> Path:
    bok = openpyxl.Workbook()
    bok.active.title = "Översikt"
    bok.active["A1"] = "Planförutsättningar per budgetår"
    blad = bok.create_sheet(namn)
    for r in rader:
        blad.append(list(r))
    fil = tmp_path / "planforutsattningar.xlsx"
    bok.save(fil)
    return fil


GRUND = [
    ("Planförutsättningar 2027 (mnkr)",),
    (),
    ("Tabell", "Post", "Planförutsättning", "Källa", "Kontroll"),
    ("Resultatbudget",),
    ("Resultatbudget", "Skatteintäkter", 1483, "L s. 8"),
    ("Resultatbudget", "Generella bidrag och utjämning", 734, "L s. 8"),
    ("Resultatbudget", "Årets resultat", 50, "L s. 8", "=C5+C6-C7"),
    ("Resultatbudget", "Resultat i % av skatter och bidrag", "=C7/(C5+C6)", "uträknat"),
    ("Resultatbudget", "Skattesats (%)", 23.34, "alla förslag"),
    ("Nämnder", "Kommunstyrelsen", 187, "L s. 8, M s. 4"),
    ("Nämnder", "Arbetslivsnämnden", None, "L s. 8"),
    ("Nämnder", "Totalt", 187, "L s. 8", "=SUM(C10:C11)-C12"),
    ("Investeringar", "Kommunstyrelsen", 25, "L s. 9"),
    ("Avvikelser och anmärkningar",),
    ("• C (s. 3) bygger på en annan version: nämnderna 1 847,8.",),
]


def test_excelfilen_lases_med_ratt_varden(tmp_path):
    [p] = planforutsattningar.las_excel(flik(tmp_path, GRUND))
    assert p.budgetar == 2027
    u = p.uppgifter
    assert u["skattesats"] == {"procent": 23.34, "kalla": "alla förslag"}
    # Formler, rubriker, tomma belopp och anteckningar läses inte.
    assert u["tabeller"]["resultatbudget"] == [
        {"post": "Skatteintäkter", "mnkr": 1483.0, "kalla": "L s. 8"},
        {"post": "Generella bidrag och utjämning", "mnkr": 734.0, "kalla": "L s. 8"},
        {"post": "Årets resultat", "mnkr": 50.0, "kalla": "L s. 8"},
    ]
    assert [p["post"] for p in u["tabeller"]["namnder"]] == ["Kommunstyrelsen", "Totalt"]
    assert u["tabeller"]["investeringar"] == [{"post": "Kommunstyrelsen", "mnkr": 25.0, "kalla": "L s. 9"}]
    assert u["tabeller"]["balansbudget"] == u["tabeller"]["kassaflode"] == []
    assert planforutsattningar.nyckeltal(u)["ramar"] == {"Kommunstyrelsen": 187.0}


def test_utkastet_till_filen_kan_lasas():
    [p] = planforutsattningar.las_excel(FIXTUR)
    assert planforutsattningar.nyckeltal(p.uppgifter) == NT_2027
    # Kontrollsummorna visar avrundningen i L:s tabell (nämnderna summerar till 2 144, L skriver 2 145).
    k = {(x["tabell"], x["post"]): x for x in planforutsattningar.kontroller(p.uppgifter)}
    assert k[("namnder", "Totalt")] == {"tabell": "namnder", "post": "Totalt", "summa": 2144.0, "angivet": 2145.0,
                                             "differens": 1.0}
    assert k[("resultatbudget", "Årets resultat")]["differens"] == 0
    assert k[("resultatbudget", "Resultat i % av skatter och bidrag")]["procent"] == 2.26


@pytest.mark.parametrize(
    ("andring", "fel"),
    [
        ({4: ("Resultatbudget", "Skatteintäkter", "1 483", "L s. 8")}, r"flik 2027, rad 5 \(Skatteintäkter\): beloppet i kolumn C ska vara ett tal"),
        ({8: ("Resultatbudget", "Skattesats", 23.34, "")}, r"raden 'Skattesats \(%\)' i Resultatbudget saknas"),
        ({8: ("Resultatbudget", "Skattesats (%)", 0.2334, "")}, "skattesatsen ska anges i procent"),
        ({12: ("Drift", "Kommunstyrelsen", 25, "")}, "rad 13: okänd tabell 'Drift'"),
        ({11: ("Nämnder", "Kommunstyrelsen", 187, "")}, "Kommunstyrelsen står flera gånger i namnder"),
        ({6: ("Resultatbudget", "Årets resultat", None, "")}, "raden 'Årets resultat' i Resultatbudget saknas"),
    ],
)
def test_fel_i_filen_ger_begripligt_felmeddelande(tmp_path, andring, fel):
    rader = [andring.get(i, r) for i, r in enumerate(GRUND)]
    with pytest.raises(planforutsattningar.Ogiltig, match=fel):
        planforutsattningar.las_excel(flik(tmp_path, rader))


def test_fil_utan_budgetar_avvisas(tmp_path):
    with pytest.raises(planforutsattningar.Ogiltig, match="ingen flik heter ett budgetår"):
        planforutsattningar.las_excel(flik(tmp_path, GRUND, namn="Budget"))
    (tmp_path / "trasig.xlsx").write_bytes(b"inte en Excelfil")
    with pytest.raises(planforutsattningar.Ogiltig, match="kan inte läsas som en Excelfil"):
        planforutsattningar.las_excel(tmp_path / "trasig.xlsx")


def test_kallan_lankar_till_sidan_i_forslaget():
    assert planforutsattningar.kallor("C s. 3, M s. 16–17, Planförutsättningar2024.xlsx", {"M": 7}) == [
        {"text": "C s. 3"}, {"text": "M s. 16–17", "forslag": 7, "sida": 16}, {"text": "Planförutsättningar2024.xlsx"}]


# Beräkningarna, med L, M och SD 2027 som fall.


def berakna(data: dict) -> dict:
    return budgetforslag.berakning(budgetforslag.uppgifter(data, 2027, True, NT_2027), NT_2027)


def test_l_2027_saknar_finansiering_for_20_mnkr():
    # L budgeterar 80 mnkr, men ramarna sparar bara 10 mnkr netto mot planförutsättningen (resultat 50).
    b = berakna({"resultat": {"mnkr": 80, "sida": 8}, "skattesats": {"procent": 23.34, "sida": 8}, "ramar": [
        {"organ": "Kommunfullmäktige", "mnkr": 13, "sida": 8}, {"organ": "Kommunstyrelsen", "mnkr": 150, "sida": 8},
        {"organ": "Kommungemensam verksamhet", "mnkr": 105, "sida": 8}, {"organ": "Samhällsnämnden", "mnkr": 235, "sida": 8},
        {"organ": "Skolnämnden", "mnkr": 703, "sida": 8}, {"organ": "Socialnämnden", "mnkr": 928, "sida": 8}]})
    assert b["skattesats"] == {"procent": 23.34, "ore": 0, "plan": 23.34}
    assert {"organ": "Kommunstyrelsen", "mnkr": 150.0, "plan": 187.0, "forandring": -37.0,
            "atgarder": {"antal": 0, "mnkr": None, "saknas": True}} in b["ramar"]
    assert (b["forandring"], b["beraknat"], b["resultat"]["mnkr"], b["differens"]) == (-10.0, 60.0, 80.0, 20.0)
    # Resultatet i mnkr räknas om till procent av skatter och bidrag (80 / 2 217).
    assert b["resultat"]["procent"] == 3.608


def test_sd_2027_utelamnar_kostnader_utanfor_namnderna():
    # SD räknar resultatet som skatter och bidrag minus ramar (2 217,2 − 2 172,8 = 44,4) och utelämnar
    # cirka 22 mnkr utanför nämnderna, så det beräknade resultatet blir cirka 21 mnkr.
    b = berakna({"resultat": {"procent": 2.0, "sida": 7}, "ramar": [
        {"organ": "Kommunfullmäktige", "mnkr": 15, "sida": 7}, {"organ": "Kommunstyrelsen", "mnkr": 184.3, "sida": 7},
        {"organ": "Kommungemensam verksamhet", "mnkr": 136.3, "sida": 7}, {"organ": "Samhällsnämnden", "mnkr": 246.3, "sida": 7},
        {"organ": "Skolnämnden", "mnkr": 703.7, "sida": 7}, {"organ": "Socialnämnden", "mnkr": 887.2, "sida": 7}]})
    assert (b["forandring"], b["beraknat"], b["resultat"]["mnkr"]) == (28.8, 21.2, 44.3)
    assert b["differens"] == pytest.approx(22, abs=1.5)


def test_m_2027_sanker_skatten_och_gar_ihop():
    # M sänker skatten med 10 öre (−6 mnkr) och anger ramarna som förändringar mot planförutsättningen.
    u = budgetforslag.uppgifter({"skattesats": {"forandring": -0.10, "sida": 4}, "resultat": {"procent": 2.5, "sida": 3},
                                 "ramar": [{"organ": "Kommunstyrelsen", "forandring": -37, "sida": 4},
                                           {"organ": "Kommungemensam verksamhet", "forandring": -4, "sida": 4},
                                           {"organ": "Samhällsnämnden", "forandring": 1, "sida": 4},
                                           {"organ": "Skolnämnden", "forandring": 15, "sida": 4},
                                           {"organ": "Socialnämnden", "forandring": 13, "sida": 4}]}, 2027, True, NT_2027)
    # Ramarna lagras i mnkr, skatten som förändring i öre.
    assert u["skattesats"] == {"ore": -10, "sida": 4}
    assert {"organ": "Kommunstyrelsen", "mnkr": 150.0, "sida": 4} in u["ramar"]
    b = budgetforslag.berakning(u, NT_2027)
    assert b["skattesats"] == {"procent": 23.24, "ore": -10, "plan": 23.34}
    assert b["skattejustering"] == -6.4
    # Basen för procenten minskar med skattesänkningen: 2,5 % av (2 217 − 6,4).
    assert (b["forandring"], b["resultat"]["mnkr"], b["beraknat"]) == (-12.0, 55.3, 55.6)
    assert abs(b["differens"]) < 1


def test_ar_utan_planforutsattningar_visas_utan_forandring():
    u = budgetforslag.uppgifter({"skattesats": {"procent": 23.34}, "resultat": [{"ar": 2022, "mnkr": 36, "procent": 2.0}],
                                 "ramar": [{"organ": "Skolnämnden", "ar": 2022, "mnkr": 616.2},
                                           {"organ": "Skolnämnden", "ar": 2023, "mnkr": 620}]}, 2022, False, None)
    assert u == {"skattesats": {"procent": 23.34}, "resultat": {"procent": 2.0},
                 "ramar": [{"organ": "Skolnämnden", "mnkr": 616.2}]}
    b = budgetforslag.berakning(u, None)
    assert b["ramar"] == [{"organ": "Skolnämnden", "mnkr": 616.2, "plan": None, "forandring": None,
                           "atgarder": {"antal": 0, "mnkr": None, "saknas": False}}]
    assert (b["planforutsattningar"], b["beraknat"], b["differens"], b["resultat"]) == (False, None, None, {"procent": 2.0, "mnkr": None})
    # En förändring kan inte räknas om utan planförutsättningar.
    with pytest.raises(budgetforslag.Ogiltig, match="förändringen räknas bara om när planförutsättningarna för 2022 finns"):
        budgetforslag.uppgifter({"ramar": [{"organ": "Skolnämnden", "forandring": 4}]}, 2022, False, None)
