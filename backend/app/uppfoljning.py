"""Budget jämfört med utfall per budgetår (#83, kravspec 3.2).

Kolada och SCB redovisar kommunen som helhet och har ingen budget, så budget, prognos och utfall per nämnd finns
bara i kommunens PDF:er (`docs/budget-mot-utfall.md`). Siffrorna tas fram genom att läsa årsredovisningen och
delårsrapporten och skrivs i `uppfoljning.json` i budgetårets mapp, bredvid budgetförslagen
(`data/budgetforslag/<budgetår>/`). Varje siffra har sidan i dokumentet den står på:

    {
      "arsredovisning": {"titel": "Årsredovisning 2025", "url": "https://…"},
      "delarsrapport": {"titel": "Delårsrapport augusti 2025", "url": "https://…"},
      "resultat": {"budget": {"mnkr": 10.0, "sida": 48}, "utfall": {"mnkr": 23.7, "sida": 46},
                   "avvikelse": {"mnkr": 13.7, "sida": 48},
                   "prognos_budget": {"mnkr": 13.4, "sida": 25}, "prognos": {"mnkr": -84.2, "sida": 25}},
      "namnder": [{"organ": "Socialnämnden", "budget": {"mnkr": 838.6, "sida": 81},
                   "utfall": {"mnkr": 823.7, "sida": 81}, "avvikelse": {"mnkr": 15.0, "sida": 81},
                   "prognosavvikelse": {"mnkr": -65.2, "sida": 25}}]
    }

- `budget`, `utfall` och `avvikelse` står i årsredovisningen. Budgeten är den reviderade, alltså budgeten vid
  årets slut efter fullmäktiges ändringar under året. Nämndernas belopp är nettokostnader, som positiva tal.
- `prognos`, `prognos_budget` och `prognosavvikelse` står i delårsrapporten. Prognosavvikelsen är helårsprognosen
  mot budgeten, som delårsrapporten anger den.
- `avvikelse` och `prognosavvikelse` följer dokumentets tecken: budget minus nettokostnad, så att plus betyder att
  nettokostnaden är eller väntas bli lägre än budgeten. För resultatet är avvikelsen resultat minus budget.
- Ett år utan årsredovisning (innevarande år) har bara delårsrapporten, och ett år utan delårsrapport bara
  årsredovisningen.

Den antagna budgeten läses inte in här. Den hämtas ur det antagna budgetförslaget (årsplanen) för året, som redan
finns med sida och behandling i fullmäktige. Avvikelserna räknas fram i mnkr och procent, och avvikelsen som
dokumentet anger kontrolleras mot den räknade, på samma sätt som brodiagrammet kontrolleras mot SCB.

Uppföljningen går utkast → granskad → publicerad (kravspec 18, ADR-0002) och läses in tillsammans med
budgetförslagen (`python -m app.budgetforslag MAPP`). Ingen godkänner det hen själv läst in. En rättelse görs i
filen, och en ny inläsning ger ett nytt utkast, eller en ny version av den publicerade.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import planforutsattningar as pf
from .planforutsattningar import EjTillatet, Konflikt, Ogiltig

FILNAMN = "uppfoljning.json"
DOKUMENT = {"arsredovisning": "årsredovisningen", "delarsrapport": "delårsrapporten"}
# Vilket dokument varje uppgift står i.
RESULTATFALT = {"budget": "arsredovisning", "utfall": "arsredovisning", "avvikelse": "arsredovisning",
                "prognos_budget": "delarsrapport", "prognos": "delarsrapport"}
NAMNDFALT = {"budget": "arsredovisning", "utfall": "arsredovisning", "avvikelse": "arsredovisning",
             "prognosavvikelse": "delarsrapport"}
# Avvikelsen i dokumentet är avrundad till en decimal, liksom beloppen den räknas ur.
TOLERANS_MNKR = 0.15


@dataclass
class Uppfoljning:
    budgetar: int
    filnamn: str
    uppgifter: dict


# Filen


def _belopp(v: Any, falt: str) -> dict:
    if not isinstance(v, dict) or set(v) - {"mnkr", "sida"}:
        raise Ogiltig(f"{falt} ska vara {{mnkr, sida}}")
    mnkr, sida = v.get("mnkr"), v.get("sida")
    if isinstance(mnkr, bool) or not isinstance(mnkr, (int, float)):
        raise Ogiltig(f"{falt}: mnkr ska vara ett tal")
    if isinstance(sida, bool) or not isinstance(sida, int) or sida < 1:
        raise Ogiltig(f"{falt}: sida ska vara sidnumret i dokumentet")
    return {"mnkr": round(float(mnkr), 3), "sida": sida}


def _dokument(v: Any, falt: str) -> dict:
    if not isinstance(v, dict) or set(v) - {"titel", "url"}:
        raise Ogiltig(f"{falt} ska vara {{titel, url}}")
    titel, url = str(v.get("titel") or "").strip(), str(v.get("url") or "").strip()
    if not titel:
        raise Ogiltig(f"{falt}: titel saknas")
    if not re.match(r"https://", url):
        raise Ogiltig(f"{falt}: url ska vara en https-adress till dokumentet")
    return {"titel": titel, "url": url}


def _falt(post: dict, tillatna: dict[str, str], falt: str, dokument: dict) -> dict:
    okanda = set(post) - set(tillatna)
    if okanda:
        raise Ogiltig(f"{falt}: okända fält: {', '.join(sorted(okanda))}")
    ut = {}
    for namn, dok in tillatna.items():
        if post.get(namn) is None:
            continue
        if dok not in dokument:
            raise Ogiltig(f"{falt}, {namn}: står i {DOKUMENT[dok]}, ange den under {dok}")
        ut[namn] = _belopp(post[namn], f"{falt}, {namn}")
    return ut


def uppgifter(data: Any) -> dict:
    """Validerar filens innehåll. Ogiltig vid fel."""
    if not isinstance(data, dict):
        raise Ogiltig("Uppgifterna ska vara ett objekt")
    okanda = set(data) - {*DOKUMENT, "resultat", "namnder"}
    if okanda:
        raise Ogiltig(f"Okända fält: {', '.join(sorted(okanda))}")
    dokument = {k: _dokument(data[k], k) for k in DOKUMENT if data.get(k) is not None}
    if not dokument:
        raise Ogiltig("Ange årsredovisningen, delårsrapporten eller båda")
    resultat = data.get("resultat") or {}
    if not isinstance(resultat, dict):
        raise Ogiltig("resultat ska vara ett objekt")
    namnder = data.get("namnder") or []
    if not isinstance(namnder, list):
        raise Ogiltig("namnder ska vara en lista")
    rader = []
    for i, n in enumerate(namnder):
        f = f"nämnd {i + 1}"
        if not isinstance(n, dict):
            raise Ogiltig(f"{f} ska vara ett objekt")
        organ = str(n.get("organ") or "").strip()
        if not organ:
            raise Ogiltig(f"{f}: organ saknas")
        rader.append({"organ": organ, **_falt({k: v for k, v in n.items() if k != "organ"}, NAMNDFALT,
                                               f"{f} ({organ})", dokument)})
    if len({r["organ"] for r in rader}) != len(rader):
        raise Ogiltig("Samma nämnd står flera gånger")
    return {**dokument, "resultat": _falt(resultat, RESULTATFALT, "resultat", dokument), "namnder": rader}


def las_mapp(rot: Path) -> list[Uppfoljning]:
    """`uppfoljning.json` i `rot/<budgetår>/`. Ogiltig med fil och fel när något inte stämmer."""
    ut = []
    for katalog in sorted(p for p in rot.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        fil = katalog / FILNAMN
        if not fil.exists():
            continue
        try:
            ut.append(Uppfoljning(int(katalog.name), FILNAMN, uppgifter(json.loads(fil.read_text(encoding="utf-8")))))
        except (Ogiltig, json.JSONDecodeError) as e:
            raise Ogiltig(f"{katalog.name}/{FILNAMN}: {e}") from e
    return ut


def las_in(conn: psycopg.Connection, lista_: list[Uppfoljning], redaktor: str, nu: datetime) -> dict:
    """Skapar eller uppdaterar utkast. En publicerad uppföljning ändras aldrig, utan får ett nytt utkast.

    Skriver i transaktionen men committar inte, så att inläsningen hör till samma transaktion som förslagens."""
    antal = {"nya": 0, "uppdaterade": 0, "oforandrade": 0}
    for u in lista_:
        senaste = conn.execute(
            "SELECT id, status, uppgifter FROM uppfoljning WHERE budgetar = %s AND status <> 'ersatt' "
            "ORDER BY id DESC LIMIT 1", (u.budgetar,),
        ).fetchone()
        ersatter = senaste["id"] if senaste and senaste["status"] in ("publicerad", "aterkallad") else None
        if senaste and senaste["uppgifter"] == u.uppgifter:
            antal["oforandrade"] += 1
            continue
        varden = {"b": u.budgetar, "fil": u.filnamn, "u": Jsonb(u.uppgifter), "r": [redaktor], "nu": nu, "e": ersatter,
                  "a": pf.INLASNING if ersatter else None}
        if senaste and senaste["status"] in ("utkast", "granskad"):
            conn.execute(
                "UPDATE uppfoljning SET filnamn = %(fil)s, uppgifter = %(u)s, status = 'utkast', redaktorer = %(r)s, "
                "andrad = %(nu)s, granskad_av = NULL, granskad = NULL WHERE id = %(id)s", {**varden, "id": senaste["id"]},
            )
            antal["uppdaterade"] += 1
        else:
            conn.execute(
                "INSERT INTO uppfoljning (budgetar, filnamn, uppgifter, status, redaktorer, skapad, andrad, ersatter_id, "
                "andring) VALUES (%(b)s, %(fil)s, %(u)s, 'utkast', %(r)s, %(nu)s, %(nu)s, %(e)s, %(a)s)", varden,
            )
            antal["nya"] += 1
    return antal


# Beräkningen


def avvikelse(varde: float | None, mot: float | None) -> dict | None:
    """Skillnaden i mnkr och i procent av det den jämförs med."""
    if varde is None or mot is None:
        return None
    return {"mnkr": round(varde - mot, 1), "procent": round((varde - mot) / abs(mot) * 100, 1) if mot else None}


def kostnadsavvikelse(budget: float | None, nettokostnad: float | None) -> dict | None:
    """Budget minus nettokostnad i mnkr och i procent av budgeten, som i årsredovisningen."""
    if budget is None or nettokostnad is None:
        return None
    d = budget - nettokostnad
    return {"mnkr": round(d, 1), "procent": round(d / abs(budget) * 100, 1) if budget else None}


def _kontroll(raknad: dict | None, angiven: dict | None) -> dict | None:
    """Den räknade avvikelsen mot den som dokumentet anger."""
    if raknad is None or angiven is None:
        return None
    differens = round(angiven["mnkr"] - raknad["mnkr"], 1)
    return {"angiven": angiven["mnkr"], "sida": angiven["sida"], "raknad": raknad["mnkr"], "differens": differens,
            "stammer": abs(differens) <= TOLERANS_MNKR}


def _mnkr(v: dict | None) -> float | None:
    return v["mnkr"] if v else None


def berakning(u: dict, antagen: dict | None) -> dict:
    """Tabellen per nämnd och för resultatet: antagen och reviderad budget, prognos och utfall, med avvikelser.

    `antagen` är {ramar: {organ: {mnkr, sida}}, resultat: {mnkr, sida} | None} ur det antagna budgetförslaget.
    För nämnderna är avvikelsen budget minus nettokostnad, för resultatet resultat minus budget, som i dokumenten.
    Prognosavvikelsen i procent räknas av den reviderade budgeten, eller av den antagna när den reviderade saknas."""
    ramar = (antagen or {}).get("ramar", {})
    namnder = []
    for n in u["namnder"]:
        ram = ramar.get(n["organ"])
        budget, utfall = _mnkr(n.get("budget")), _mnkr(n.get("utfall"))
        mot_reviderad = kostnadsavvikelse(budget, utfall)
        prognosavv = n.get("prognosavvikelse")
        bas = budget if budget is not None else _mnkr(ram)
        namnder.append({
            "organ": n["organ"],
            "antagen": ram,
            "reviderad": n.get("budget"),
            "andring": avvikelse(budget, _mnkr(ram)),
            "prognosavvikelse": {**prognosavv, "procent": round(prognosavv["mnkr"] / abs(bas) * 100, 1) if bas else None}
            if prognosavv else None,
            "utfall": n.get("utfall"),
            "avvikelse_reviderad": mot_reviderad,
            "avvikelse_antagen": kostnadsavvikelse(_mnkr(ram), utfall),
            "kontroll": _kontroll(mot_reviderad, n.get("avvikelse")),
        })
    # Antagna ramar för nämnder som inte finns i uppföljningen, till exempel en nämnd som lagts ned.
    finns = {n["organ"] for n in namnder}
    utan = [{"organ": o, "antagen": r} for o, r in ramar.items() if o not in finns]
    r = u["resultat"]
    res_antagen = (antagen or {}).get("resultat")
    utfall = _mnkr(r.get("utfall"))
    resultat = {
        "antagen": res_antagen,
        "reviderad": r.get("budget"),
        "prognos_budget": r.get("prognos_budget"),
        "prognos": r.get("prognos"),
        "utfall": r.get("utfall"),
        "avvikelse_reviderad": (resultat_avv := avvikelse(utfall, _mnkr(r.get("budget")))),
        "kontroll": _kontroll(resultat_avv, r.get("avvikelse")),
        "avvikelse_antagen": avvikelse(utfall, _mnkr(res_antagen)),
        "prognosavvikelse": avvikelse(_mnkr(r.get("prognos")), _mnkr(r.get("prognos_budget"))),
    }
    return {"namnder": namnder, "utan_uppfoljning": utan, "resultat": resultat}


def _antagen(conn: psycopg.Connection, budgetar: int, publicerade: bool) -> dict | None:
    """Det antagna budgetförslaget för året: ramarna, resultatet i mnkr och länkarna till förslaget och behandlingen."""
    from . import budgetforslag

    r = conn.execute(
        "SELECT id, titel, uppgifter, partier FROM budgetforslag WHERE budgetar = %s AND antagen AND typ = 'budget' "
        "AND (status = 'publicerad' OR (NOT %s AND status IN ('utkast', 'granskad'))) "
        "ORDER BY (status = 'publicerad') DESC, id DESC LIMIT 1", (budgetar, publicerade),
    ).fetchone()
    if r is None:
        return None
    u = r["uppgifter"]
    if budgetforslag.tidigare_format(u):
        return None
    plan = pf.aktuella(conn, publicerade).get(budgetar)
    nt = pf.nyckeltal(plan) if plan else None
    b = budgetforslag.berakning(u, nt)
    res = u.get("resultat")
    mnkr = (b["resultat"] or {}).get("mnkr")
    behandling = budgetforslag.koppling(conn, u.get("behandling"), r["partier"])
    return {
        "id": r["id"], "titel": r["titel"], "original": f"/api/budgetforslag/{r['id']}/original",
        "ramar": {x["organ"]: {"mnkr": x["mnkr"], "sida": x.get("sida")} for x in u["ramar"]},
        # Förslaget anger resultatet i procent av skatter och bidrag. Beloppet räknas ur planförutsättningarna.
        "resultat": {"mnkr": mnkr, "procent": res["procent"], "sida": res.get("sida"), "beraknat": True}
        if res and mnkr is not None else None,
        "behandling": {k: behandling[k] for k in ("organ", "datum", "paragraf", "hittad", "sammantrade_id")}
        if behandling else None,
    }


# Granskning och publicering

_KOLUMNER = ("id, budgetar, filnamn, uppgifter, status, redaktorer, andrad, granskad_av, granskad, publicerad_av, "
             "publicerad, aterkallad_av, aterkallad, aterkallelse, ersatter_id, andring")


def _ut(conn: psycopg.Connection, r: dict, redaktion: bool) -> dict:
    antagen = _antagen(conn, r["budgetar"], publicerade=not redaktion)
    u = r["uppgifter"]
    ut = {"id": r["id"], "budgetar": r["budgetar"], "status": r["status"], "filnamn": r["filnamn"],
          "dokument": {k: u[k] for k in DOKUMENT if k in u},
          "antagen": {k: antagen[k] for k in ("id", "titel", "original", "behandling")} if antagen else None,
          "berakning": berakning(u, antagen),
          "publicerad": r["publicerad"].isoformat() if r["publicerad"] else None,
          "andring": pf.andring(conn, "uppfoljning", r)}
    if redaktion:
        ut |= {"redaktorer": r["redaktorer"], "granskad_av": r["granskad_av"], "publicerad_av": r["publicerad_av"],
               "andrad": r["andrad"].isoformat(), "granskad": r["granskad"].isoformat() if r["granskad"] else None,
               "aterkallad_av": r["aterkallad_av"], "aterkallelse": r["aterkallelse"],
               "aterkallad": r["aterkallad"].isoformat() if r["aterkallad"] else None}
    return ut


def _hamta(conn: psycopg.Connection, id_: int) -> dict:
    r = conn.execute(f"SELECT {_KOLUMNER} FROM uppfoljning WHERE id = %s", (id_,)).fetchone()
    if r is None:
        raise LookupError(f"Uppföljningen {id_} finns inte")
    return r


def lista(conn: psycopg.Connection, status: str | None = None) -> list[dict]:
    rader = conn.execute(
        f"SELECT {_KOLUMNER} FROM uppfoljning WHERE (%(s)s::text IS NULL OR status = %(s)s) "
        "ORDER BY budgetar DESC, id DESC", {"s": status},
    ).fetchall()
    return [_ut(conn, r, redaktion=True) for r in rader]


def las(conn: psycopg.Connection, id_: int) -> dict:
    return _ut(conn, _hamta(conn, id_), redaktion=True)


def _godkann(conn: psycopg.Connection, id_: int, utgivare: str, fran: str) -> dict:
    r = _hamta(conn, id_)
    if utgivare in r["redaktorer"]:
        raise EjTillatet("Ingen godkänner en uppföljning som hen själv läst in")
    if r["status"] != fran:
        raise Konflikt(f"Uppföljningen är {r['status']}, inte {fran}")
    return r


def granska(conn: psycopg.Connection, id_: int, utgivare: str, nu: datetime) -> dict:
    _godkann(conn, id_, utgivare, "utkast")
    conn.execute("UPDATE uppfoljning SET status = 'granskad', granskad_av = %s, granskad = %s WHERE id = %s",
                 (utgivare, nu, id_))
    conn.commit()
    return las(conn, id_)


def publicera(conn: psycopg.Connection, id_: int, utgivare: str, nu: datetime) -> dict:
    r = _godkann(conn, id_, utgivare, "granskad")
    conn.execute("UPDATE uppfoljning SET status = 'ersatt' WHERE status = 'publicerad' AND budgetar = %s",
                 (r["budgetar"],))
    conn.execute("UPDATE uppfoljning SET status = 'publicerad', publicerad_av = %s, publicerad = %s WHERE id = %s",
                 (utgivare, nu, id_))
    if r["ersatter_id"] is not None:
        conn.execute("UPDATE uppfoljning SET status = 'ersatt' WHERE id = %s AND status IN ('utkast', 'granskad')",
                     (r["ersatter_id"],))
    conn.commit()
    return las(conn, id_)


def aterkalla(conn: psycopg.Connection, id_: int, data: dict, utgivare: str, nu: datetime) -> dict:
    """En utgivare återkallar en publicerad uppföljning direkt, med motivering."""
    r = _hamta(conn, id_)
    if r["status"] != "publicerad":
        raise Konflikt(f"Bara en publicerad uppföljning kan återkallas, den här är {r['status']}")
    motivering = (data.get("motivering") or "").strip()
    if not motivering:
        raise Ogiltig("Ange varför uppföljningen återkallas, till exempel vem som påpekade felet och när")
    conn.execute(
        "UPDATE uppfoljning SET status = 'aterkallad', aterkallad_av = %s, aterkallad = %s, aterkallelse = %s "
        "WHERE id = %s", (utgivare, nu, motivering, id_),
    )
    conn.commit()
    return las(conn, id_)


# Läsaren


def ar(conn: psycopg.Connection) -> list[dict]:
    """Budgetåren med publicerad eller återkallad uppföljning, senaste först."""
    return conn.execute(
        "SELECT budgetar, bool_or(status = 'publicerad') AS publicerad FROM uppfoljning "
        "WHERE status IN ('publicerad', 'aterkallad') GROUP BY budgetar ORDER BY budgetar DESC"
    ).fetchall()


def publicerad(conn: psycopg.Connection, budgetar: int) -> dict:
    """Den publicerade uppföljningen för året, eller en notis om att den är återkallad. LookupError om ingen finns."""
    r = conn.execute(f"SELECT {_KOLUMNER} FROM uppfoljning WHERE budgetar = %s AND status = 'publicerad'",
                     (budgetar,)).fetchone()
    if r is not None:
        return _ut(conn, r, redaktion=False) | {"aterkallad": False}
    if conn.execute("SELECT 1 FROM uppfoljning WHERE budgetar = %s AND status = 'aterkallad'", (budgetar,)).fetchone():
        return {"budgetar": budgetar, "aterkallad": True}
    raise LookupError(f"Ingen publicerad uppföljning för {budgetar}")
