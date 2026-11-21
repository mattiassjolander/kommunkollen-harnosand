"""Kontrollerar planförutsättningarna och budgetförslagen i en mapp, utan databas.

    uv run --directory backend python ../.claude/skills/harnosandskollen-budgetforslag/kontroll.py ../data/budgetforslag --ar 2027

Läser mappen på samma sätt som inläsningen (`app.budgetforslag.las_mapp`), så ett fel som stoppar
inläsningen stoppar också kontrollen. Skriver per budgetår:

- kontrollsummorna i planförutsättningarna,
- per förslag: skattesats, budgeterat och beräknat resultat med differens, ram och förändring per nämnd,
  åtgärdernas täckning, och vilken version av planförutsättningarna förslaget räknat från.

Rader som behöver en anmärkning eller en rättelse märks AVVIKER.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import budgetforslag as bf
from app import planforutsattningar as pf

# Förslagen redovisar oftast hela mnkr, så avrundningen ger skillnader under de här gränserna.
SKILLNAD_MNKR = 2.0  # budgeterat − beräknat resultat
VERSION_MNKR = 1.0  # förslagets egen planförutsättning (mnkr − förändring, två avrundade tal) mot den gemensamma
PROCENT_PE = 0.1  # förslagets resultat i procent mot dess mnkr räknat på basen
KONTROLL_MNKR = 0.3  # kontrollsumma i planförutsättningarna: beloppen har en decimal, så avrundningen ger några tiondelar


def _flagga(avviker: bool) -> str:
    return "  AVVIKER" if avviker else ""


def _tal(v: float | None, dec: int = 1) -> str:
    return "–" if v is None else f"{v:.{dec}f}"


def _budgetarets(post: dict | list | None, ar: int) -> dict | None:
    """Posten för budgetåret i det tidigare formatet med planår, annars posten själv."""
    if isinstance(post, list):
        return next((p for p in post if p.get("ar") in (None, ar)), None)
    return post


def version(ra: dict, ar: int, nt: dict) -> list[str]:
    """Det som visar vilken version av planförutsättningarna förslaget räknat från."""
    ut = []
    for r in ra.get("ramar") or []:
        if r.get("ar") not in (None, ar) or r.get("mnkr") is None or r.get("forandring") is None:
            continue
        egen, gemensam = r["mnkr"] - r["forandring"], nt["ramar"].get(r["organ"])
        if gemensam is None:
            ut.append(f"    {r['organ']}: finns inte i planförutsättningarna{_flagga(True)}")
            continue
        ut.append(f"    {r['organ']}: förslagets plan {_tal(egen)}, gemensam {_tal(gemensam)}"
                  f"{_flagga(abs(egen - gemensam) > VERSION_MNKR)}")
    skatt = ra.get("skattesats") or {}
    if skatt.get("procent") is not None and skatt.get("ore") is None and skatt.get("forandring") is None:
        ut.append(f"    skattesats {skatt['procent']} %, gemensam {nt['skattesats']} % (läses som förändring "
                  f"{round((skatt['procent'] - nt['skattesats']) * 100)} öre)")
    return ut


def resultatet(ra: dict, ar: int, nt: dict, ore: int) -> list[str]:
    """Förslagets resultat i procent mot dess eget belopp i mnkr, när det anger båda."""
    r = _budgetarets(ra.get("resultat"), ar) or {}
    if r.get("procent") is None or r.get("mnkr") is None:
        return []
    procent = r["mnkr"] / bf.bas(nt, ore) * 100
    return [(f"    förslagets {r['mnkr']} mnkr är {procent:.2f} % av basen, förslaget anger {r['procent']} %"
            f"{_flagga(abs(procent - r['procent']) > PROCENT_PE)}")]


def forslaget(f: bf.Forslag, ra: dict, nt: dict | None) -> None:
    b = bf.berakning(f.uppgifter, nt)
    print(f"\n-- {f.filnamn}: {'+'.join(f.partier)}, {f.titel}{' (antagen)' if f.antagen else ''}")
    if f.anmarkning:
        print(f"  anmärkning: {f.anmarkning}")
    skatt = b["skattesats"]
    print(f"  skattesats: {_tal(skatt['procent'], 2)} % ({skatt['ore'] if skatt['ore'] is not None else '–'} öre), "
          f"skatteintäkternas förändring {_tal(b['skattejustering'])} mnkr")
    res = b["resultat"]
    if res is None:
        print(f"  budgeterat resultat: saknas{_flagga(True)}")
    else:
        print(f"  budgeterat resultat: {res['procent']} % = {_tal(res['mnkr'])} mnkr")
    if nt is not None:
        print(f"  beräknat resultat: {_tal(b['plan_resultat'])} − {_tal(b['forandring'])} + "
              f"{_tal(b['skattejustering'])} = {_tal(b['beraknat'])} mnkr")
        d = b["differens"]
        print(f"  skillnad budgeterat − beräknat: {_tal(d)} mnkr"
              f"{_flagga(d is None or abs(d) >= SKILLNAD_MNKR)}")
    print("  ramar (mnkr, plan, förändring, åtgärder):")
    for r in b["ramar"]:
        t = r["atgarder"]
        tackning = "inga åtgärder anges" if t["saknas"] else (
            f"{t['antal']} {'åtgärd' if t['antal'] == 1 else 'åtgärder'} för {_tal(t['mnkr'])}" if t["antal"] else "")
        print(f"    {r['organ']}: {_tal(r['mnkr'])}, {_tal(r['plan'])}, {_tal(r['forandring'])}"
              f"{', ' + tackning if tackning else ''}{_flagga(nt is not None and r['plan'] is None)}")
    if nt is not None:
        tas_inte_upp = [o for o in nt["ramar"] if o not in {r["organ"] for r in b["ramar"]}]
        if tas_inte_upp:
            print(f"    tas inte upp (räknas som oförändrade): {', '.join(tas_inte_upp)}")
        rader = version(ra, f.budgetar, nt) + resultatet(ra, f.budgetar, nt, skatt["ore"] or 0)
        if rader:
            print("  version av planförutsättningarna:")
            print("\n".join(rader))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Kontrollerar planförutsättningarna och budgetförslagen i en mapp.")
    p.add_argument("mapp", type=Path, help=f"mappen med {pf.FILNAMN} och <budgetår>/")
    p.add_argument("--ar", type=int, help="bara det här budgetåret")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        fil = a.mapp / pf.FILNAMN
        planer = {x.budgetar: x.uppgifter for x in pf.las_excel(fil)} if fil.exists() else {}
        nyckeltal = {ar: pf.nyckeltal(u) for ar, u in planer.items()}
        forslag = bf.las_mapp(a.mapp, nyckeltal)
    except pf.Ogiltig as e:
        sys.exit(f"Inläsningen skulle avbrytas: {e}")
    for ar in sorted({f.budgetar for f in forslag} | set(planer)):
        if a.ar and ar != a.ar:
            continue
        print(f"\n===== Budgetår {ar}")
        nt = nyckeltal.get(ar)
        if nt is None:
            print("Inga planförutsättningar: förslagen visas utan förändring och beräknat resultat.")
        else:
            print(f"Planförutsättningar: skattesats {nt['skattesats']} %, skatteintäkter {_tal(nt['skatteintakter'])}, "
                  f"bidrag {_tal(nt['bidrag'])}, resultat {_tal(nt['resultat'])}, nämnderna "
                  f"{_tal(sum(nt['ramar'].values()))} mnkr")
            for k in pf.kontroller(planer[ar]):
                if "procent" in k:
                    print(f"  {k['post']}: {k['procent']} %")
                else:
                    print(f"  kontroll {k['tabell']} {k['post']}: angivet {_tal(k['angivet'])}, summa {_tal(k['summa'])}, "
                          f"differens {_tal(k['differens'])}{_flagga(abs(k['differens']) > KONTROLL_MNKR)}")
        beskrivning = a.mapp / str(ar) / bf.BESKRIVNING
        poster = json.loads(beskrivning.read_text(encoding="utf-8")).get("forslag", {}) if beskrivning.exists() else {}
        for f in (x for x in forslag if x.budgetar == ar):
            forslaget(f, poster.get(f.filnamn, {}), nt)


if __name__ == "__main__":
    main()
