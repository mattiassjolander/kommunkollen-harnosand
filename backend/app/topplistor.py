"""Topplistor per år eller mandatperiod (#163): beredning, återremisser, reservationer, motioner, voteringar m.fl.

Listorna räknas ur de tolkade protokollen med publicerade rättelser pålagda (behandlingar.las), med samma regler
som märkningarna (markningar.py), kommande ärenden (kommande.py) och motionerna (motioner.py). Varje rad har de
behandlingar som räknats, så att läsaren kan kontrollera siffran.

Urvalet är ett kalenderår eller en mandatperiod (15 oktober valåret till 14 oktober fyra år senare). Vad som
räknas till urvalet:

- En behandling räknas till sammanträdets datum.
- En beredning räknas till datumet för ärendets slutliga beslut.
- Ledtiden för en motion räknas till datumet då motionen besvarades, och en motion per parti till datumet då
  den väcktes.
- Ett pågående ärende räknas när någon av dess behandlingar ligger i urvalet. Tiden räknas från den första
  behandlingen fram till i dag.

Listor per parti visar alla partier i kommunfullmäktige under mandatperioden, också de med noll, med antal och
antal per mandat. Mandaten är fördelningen i kommunfullmäktige vid mandatperiodens början enligt Valmyndigheten.
För ett kalenderår gäller den mandatperiod som omfattar större delen av året (den som gäller den 1 juli).

Listor per ledamot räknar bara personer som finns i ledamotsregistret. En reservation från en hel partigrupp
("Sverigedemokraterna reserverar sig") räknas för partiet men inte för någon enskild ledamot.

Det finns ingen lista över närvaro per person: frånvaro kan bero på sjukdom eller föräldraledighet.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import psycopg

from . import kommande, markningar, motioner
from .arenden import NIVA, SAMLING, slutligt_beslut
from .partitillhorighet import Gallande
from .sammansattning import PERIODER, periodnamn
from .sources.harnosand import organ_ref
from .statistik import tillgangliga_ar

TOPP = 10
MANDATPERIOD = "mandatperiod"
OKANT = "okant"


class Ogiltigt(ValueError):
    """Urvalet finns inte."""


def _partinyckel(parti: str) -> tuple:
    """Partierna i bokstavsordning efter förkortning (design.md, Ton i text), okänt parti sist."""
    return (parti == OKANT, parti)


def _period_for(d: date) -> int | None:
    return next((ar for ar, (fran, till) in PERIODER.items() if fran <= d <= till), None)


def urval(conn: psycopg.Connection, ar: str | None, period: int | None) -> dict:
    """Urvalet: ett år (standard det senaste året med protokoll) eller en mandatperiod (standard den senaste)."""
    aren = tillgangliga_ar(conn)
    sista = aren[-1] if aren else date.today().year
    if ar == MANDATPERIOD:
        if period is None:
            period = max((p for p, (fran, _) in PERIODER.items() if fran.year <= sista), default=max(PERIODER))
        if period not in PERIODER:
            raise Ogiltigt(f"Mandatperioden {period} finns inte")
        fran, till = PERIODER[period]
        return {"ar": None, "period": period, "namn": f"Mandatperioden {periodnamn(period)}", "fran": fran,
                "till": till, "mandat_valar": period}
    if period is not None:
        raise Ogiltigt("En mandatperiod väljs med ar=mandatperiod")
    if ar in (None, ""):
        valt = sista
    elif ar.isdigit() and len(ar) == 4:
        valt = int(ar)
    else:
        raise Ogiltigt(f"Året {ar} finns inte. Ange ett år eller {MANDATPERIOD}")
    if aren and valt not in aren:
        raise Ogiltigt(f"Det finns inga protokoll från {valt}")
    return {"ar": valt, "period": None, "namn": str(valt), "fran": date(valt, 1, 1), "till": date(valt, 12, 31),
            "mandat_valar": _period_for(date(valt, 7, 1))}


def mandat(conn: psycopg.Connection, valar: int | None) -> dict | None:
    """Mandaten per parti i kommunfullmäktige vid mandatperiodens början, eller None när uppgiften saknas."""
    if valar is None:
        return None
    rader = conn.execute(
        "SELECT parti, count(*) AS n FROM valledamot WHERE valar = %s AND invald IS NULL GROUP BY parti", (valar,)
    ).fetchall()
    if not rader:
        return None
    per = {r["parti"]: r["n"] for r in rader}
    return {"valar": valar, "period": periodnamn(valar), "totalt": sum(per.values()),
            "per_parti": dict(sorted(per.items(), key=lambda x: _partinyckel(x[0])))}


def _underlag(conn: psycopg.Connection, fran: date, till: date) -> dict:
    sammantraden = conn.execute(
        """
        SELECT s.id, s.organ, s.datum, s.tolkning, d.typ AS dokument_typ
        FROM sammantrade s JOIN dokument d ON d.id = s.dokument_id
        WHERE s.datum BETWEEN %s AND %s ORDER BY s.datum, s.id
        """,
        (fran, till),
    ).fetchall()

    def kort(s: dict) -> dict:
        return {"id": s["id"], "datum": s["datum"], "organ": organ_ref(s["organ"])}

    return {
        "sammantraden": len(sammantraden),
        # Protokoll som inte gick att tolka: deras behandlingar saknas i listorna.
        "ej_tolkade": [kort(s) for s in sammantraden if s["tolkning"] == "ej_tolkad"],
        # Sammanträden som bara finns som paragrafprotokoll: bara en del av behandlingarna.
        "paragrafprotokoll": [kort(s) for s in sammantraden if s["dokument_typ"] == "paragrafprotokoll"],
        "utan_datum": conn.execute(
            "SELECT count(*) AS n FROM sammantrade WHERE datum IS NULL AND dokument_id IS NOT NULL").fetchone()["n"],
    }


def _ref(b: dict) -> dict:
    return {"sammantrade": {"id": b["sammantrade_id"], "datum": b["datum"], "organ": organ_ref(b["organ"])},
            "paragraf": b["paragraf"], "rubrik": b["rubrik"]}


def _ordna(b: dict) -> tuple:
    return (b["datum"], NIVA.get(b["organ"], 0), b["paragraf"])


def _topp(rader: list[dict], varde) -> dict:
    """De TOPP första raderna (redan sorterade) med placering. Rader med samma värde delar placering."""
    ut, plats, forra = [], 0, object()
    for i, r in enumerate(rader[:TOPP]):
        if (v := varde(r)) != forra:
            plats, forra = i + 1, v
        ut.append({"plats": plats} | r)
    return {"rader": ut, "totalt": len(rader)}


def _per_parti(antal: dict[str, list[dict]], mandatet: dict | None) -> dict:
    """En rad per parti: alla partier med mandat och alla som förekommer, med antal och antal per mandat."""
    partier = set(antal) | set((mandatet or {}).get("per_parti", {}))
    rader = []
    for p in partier:
        bs = sorted(antal.get(p, []), key=_ordna, reverse=True)
        n = (mandatet or {}).get("per_parti", {}).get(p)
        rader.append({"parti": None if p == OKANT else p, "antal": len(bs), "mandat": n,
                      "per_mandat": round(len(bs) / n, 2) if n else None, "behandlingar": [_ref(b) for b in bs]})
    # Störst antal först. Okänt parti står alltid sist, och lika antal står i bokstavsordning.
    rader.sort(key=lambda r: (r["parti"] is None, -r["antal"], _partinyckel(r["parti"] or OKANT)))
    return {"rader": rader, "totalt": sum(r["antal"] for r in rader)}


def _personer(conn: psycopg.Connection, poster: list[tuple[dict, dict]], gal: Gallande) -> dict[int, dict]:
    """Personerna i ledamotsregistret bakom (förekomst {namn, parti}, behandling): id → {namn, parti, poster}."""
    person = {r["namn"]: r["person"] for r in conn.execute(
        "SELECT namn, coalesce(huvud_id, id) AS person FROM ledamot WHERE namn = ANY(%s)",
        (sorted({p["namn"] for p, _ in poster if p.get("namn")}),))}
    namn = {r["id"]: r["namn"] for r in conn.execute(
        "SELECT id, namn FROM ledamot WHERE id = ANY(%s)", (sorted(set(person.values())),))}
    ut: dict[int, dict] = {}
    for p, b in sorted(poster, key=lambda x: _ordna(x[1])):
        if (pid := person.get(p.get("namn") or "")) is None:
            continue
        x = ut.setdefault(pid, {"person_id": pid, "namn": namn[pid], "parti": None, "poster": []})
        # Partiet vid den senaste förekomsten, med fastställd partitillhörighet.
        x["parti"] = (gal.satt(dict(p), b["datum"]) or {}).get("parti") or x["parti"]
        x["poster"].append(b)
    return ut


def berakna(conn: psycopg.Connection, valt: dict, idag: date | None = None) -> dict:
    idag = idag or date.today()
    fran, till = valt["fran"], valt["till"]
    inom = lambda d: d is not None and fran <= d <= till  # noqa: E731
    rader = markningar.satt(conn, motioner.daterade(conn))
    i_urvalet = [r for r in rader if inom(r["datum"])]
    per_arende: dict[int, list[dict]] = defaultdict(list)
    for r in rader:
        if r["arende_id"] is not None and not SAMLING.search(r["rubrik"]):
            per_arende[r["arende_id"]].append(r)
    mandatet = mandat(conn, valt["mandat_valar"])

    # Längsta beredning: avgjorda ärenden, från första behandlingen till det slutliga beslutet.
    beredning = []
    for arende_id, bs in per_arende.items():
        sista = bs[-1]
        if slutligt_beslut(sista["beslut"]) and inom(sista["datum"]) and (dagar := (sista["datum"] - bs[0]["datum"]).days):
            beredning.append({"arende_id": arende_id, "rubrik": sista["rubrik"], "dagar": dagar,
                              "fran": bs[0]["datum"], "till": sista["datum"], "behandlingar": [_ref(b) for b in bs]})
    beredning.sort(key=lambda r: (-r["dagar"], r["till"]))

    # Längst pågående: ärenden som inte är avslutade enligt Kommande, med en behandling i urvalet.
    pagaende = []
    for a in kommande.berakna(rader, kommande.MANADER, idag)["arenden"]:
        bs = per_arende.get(a["arende_id"]) or []
        if not bs or not any(inom(b["datum"]) for b in bs):
            continue
        pagaende.append({"arende_id": a["arende_id"], "rubrik": a["rubrik"], "status": kommande.STATUS[a["status"]],
                         "dagar": (idag - bs[0]["datum"]).days, "fran": bs[0]["datum"],
                         "behandlingar": [_ref(b) for b in bs]})
    pagaende.sort(key=lambda r: (-r["dagar"], r["arende_id"]))

    # Flest återremisser: behandlingar i urvalet med märkningen återremitterad, per ärende.
    remisser: dict[int, list[dict]] = defaultdict(list)
    for r in i_urvalet:
        if r["arende_id"] is not None and any(m["id"] == "aterremitterad" for m in r["markningar"]):
            remisser[r["arende_id"]].append(r)
    aterremisser = [{"arende_id": a, "rubrik": bs[-1]["rubrik"], "antal": len(bs),
                     "behandlingar": [_ref(b) for b in bs]} for a, bs in remisser.items()]
    aterremisser.sort(key=lambda r: (-r["antal"], -r["behandlingar"][-1]["sammantrade"]["datum"].toordinal()))

    ids = {r["id"]: r for r in i_urvalet}
    reservationer = conn.execute(
        "SELECT behandling_id, personer, partier FROM reservation WHERE behandling_id = ANY(%s) ORDER BY ordning",
        (list(ids),)).fetchall()
    yrkanden = conn.execute(
        "SELECT behandling_id, personer FROM yrkande WHERE behandling_id = ANY(%s) ORDER BY ordning",
        (list(ids),)).fetchall()
    gal = Gallande(conn, [p.get("namn") for r in [*reservationer, *yrkanden] for p in r["personer"]])

    # Reservationer: per parti en gång per behandling, per ledamot bara personer med namn.
    res_parti: dict[str, dict[int, dict]] = defaultdict(dict)
    res_poster: list[tuple[dict, dict]] = []
    for r in reservationer:
        b = ids[r["behandling_id"]]
        for p in r["partier"]:
            res_parti[p][b["id"]] = b
        for p in r["personer"]:
            parti = (gal.satt(dict(p), b["datum"]) or {}).get("parti") or OKANT
            res_parti[parti][b["id"]] = b
            res_poster.append((p, b))
    res_personer = []
    for x in _personer(conn, res_poster, gal).values():
        bs = sorted({b["id"]: b for b in x["poster"]}.values(), key=_ordna, reverse=True)
        res_personer.append({"person_id": x["person_id"], "namn": x["namn"], "parti": x["parti"], "antal": len(bs),
                             "behandlingar": [_ref(b) for b in bs]})
    res_personer.sort(key=lambda r: (-r["antal"], r["namn"]))

    # Yrkanden per ledamot: varje yrkande räknas för var och en som står bakom det.
    yrk_poster = [(p, ids[y["behandling_id"]]) for y in yrkanden for p in y["personer"]]
    yrk_personer = []
    for x in _personer(conn, yrk_poster, gal).values():
        bs = sorted({b["id"]: b for b in x["poster"]}.values(), key=_ordna, reverse=True)
        yrk_personer.append({"person_id": x["person_id"], "namn": x["namn"], "parti": x["parti"],
                             "antal": len(x["poster"]), "behandlingar": [_ref(b) for b in bs]})
    yrk_personer.sort(key=lambda r: (-r["antal"], r["namn"]))

    # Motioner: väckta i urvalet per parti, och ledtiden för de som besvarades i urvalet.
    m = motioner.berakna(rader, fran.year, till.year, None, idag,
                         Gallande(conn, [p["namn"] for r in rader for p in r["motionarer"] or []])) if rader else None
    lista = m["motioner"]["lista"] if m else []
    mot_parti: dict[str, list[dict]] = defaultdict(list)
    for x in lista:
        if x["vackt"] and inom(x["vackt"]["datum"]):
            v = {"sammantrade_id": x["vackt"]["sammantrade_id"], "datum": x["vackt"]["datum"], "organ": "KF",
                 "paragraf": x["vackt"]["paragraf"], "rubrik": x["rubrik"]}
            for p in {p["parti"] or OKANT for p in x["motionarer"]} or {OKANT}:
                mot_parti[p].append(v)
    ledtid = []
    for x in lista:
        if x["besvarad"] and x["ledtid_dagar"] is not None and inom(x["besvarad"]["sammantrade"]["datum"]):
            ledtid.append({"arende_id": x["arende_id"], "rubrik": x["rubrik"], "dagar": x["ledtid_dagar"],
                           "vackt": x["vackt"]["datum"], "besvarad": x["besvarad"]["sammantrade"]["datum"],
                           "utfall": x["utfall"],
                           "behandlingar": [{k: b[k] for k in ("sammantrade", "paragraf", "rubrik")}
                                            for b in x["behandlingar"]]})
    ledtid.sort(key=lambda r: (-r["dagar"], r["besvarad"]))

    # Jämnaste voteringar: minst skillnad mellan ja och nej.
    jamna = []
    resultat = markningar.voteringsresultat(conn, i_urvalet)
    for bid, vs in resultat.items():
        b = ids[bid]
        for v in vs:
            if v["ja"] is None or v["ja"] + v["nej"] == 0:
                continue
            jamna.append({"behandling": _ref(b), "votering": v["ordning"], "antal_voteringar": len(vs),
                          "ja": v["ja"], "nej": v["nej"], "marginal": abs(v["ja"] - v["nej"]),
                          "ja_forslag": v["ja_forslag"], "nej_forslag": v["nej_forslag"]})
    jamna.sort(key=lambda r: (r["marginal"], -(r["ja"] + r["nej"]),
                              -r["behandling"]["sammantrade"]["datum"].toordinal(), r["behandling"]["paragraf"]))

    return {
        "urval": {k: valt[k] for k in ("ar", "period", "namn", "fran", "till")},
        "val": {"ar": tillgangliga_ar(conn),
                "perioder": [{"valar": p, "namn": periodnamn(p)} for p in sorted(PERIODER, reverse=True)]},
        "idag": idag,
        "mandat": mandatet,
        "underlag": _underlag(conn, fran, till),
        "listor": {
            "langsta_beredning": _topp(beredning, lambda r: r["dagar"]),
            "langst_pagaende": _topp(pagaende, lambda r: r["dagar"]),
            "flest_aterremisser": _topp(aterremisser, lambda r: r["antal"]),
            "reservationer_per_parti": _per_parti({p: list(bs.values()) for p, bs in res_parti.items()}, mandatet),
            "reservationer_per_ledamot": _topp(res_personer, lambda r: r["antal"]),
            "motioner_per_parti": _per_parti(mot_parti, mandatet),
            "langsta_ledtid_motioner": _topp(ledtid, lambda r: r["dagar"]),
            "jamnaste_voteringar": _topp(jamna, lambda r: r["marginal"]),
            "yrkanden_per_ledamot": _topp(yrk_personer, lambda r: r["antal"]),
        },
    }
