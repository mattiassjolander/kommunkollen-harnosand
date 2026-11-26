"""HTTP-API:t."""

from __future__ import annotations

import logging
import math
import os
import time
from datetime import date, datetime, timezone
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from starlette.middleware.sessions import SessionMiddleware

from . import arenden, aterkommande, krockar, motstridigheter, namnvarianter, partiforslag, processer, partitillhorighet, auth, avvikelser, protokollavvikelser, budgetforslag, db, planforutsattningar, rankningar, rattelser, ekonomi, floden, ledamoter, motionarer, motioner, kalender, kommande, markningar, protokoll, resultatbro, sammansattning, sammantradesplan, serier, skatteunderlag, sokindex, sokvektorer, statistik, status, styrande_dokument, undersokningar, uppfoljning
from .behandlingstyper import TYPER
from .auth import Anvandare, Inloggning, krav_roll
from .insamling import InsamlingPagar, kor_insamling
from .recorded import InspeladTransport
from .robust import Robusthet
from .schema import SVERIGE, Schema
from .sources.base import Datakalla
from .sources.foretagsklimat import Foretagsklimat
from .sources.kolada import Kolada
from .sources.miljobarometern import Miljobarometern
from .sources.harnosand import ORGAN, Protokollkalla
from .sources.sammantradesplaner import Sammantradesplaner
from .sources.scb import Scb
from .sources.skr import SkrSkatteunderlag
from .sources.styrande_dokument import StyrandeDokument, urval_fran_miljo
from .sources.valmyndigheten import Valmyndigheten

KOMMUN = "2280"  # Härnösand
FRAN_MILJO = object()  # create_app läser schemat från miljön om inget anges


def _unika(matt: list) -> list:
    return list({m.id: m for m in matt}.values())


def _anropsgrans(namn: str, standard: float) -> float | None:
    """Anrop per sekund från miljön, t.ex. SCB_ANROP_PER_SEKUND=2. 0 betyder ingen gräns."""
    varde = float(os.environ.get(f"{namn}_ANROP_PER_SEKUND") or standard)
    return varde or None


def standardkallor() -> list[Datakalla]:
    return [
        Kolada(nyckeltal=[*ekonomi.KOLADA, floden.INVANARE.split(":")[1]], kommun=KOMMUN, riket=ekonomi.KOLADA,
               samlade=undersokningar.KOLADA, anrop_per_sekund=_anropsgrans("KOLADA", 5)),
        Scb(matt=_unika([*ekonomi.SCB, *floden.SCB_MATT]), differenser=[ekonomi.RORELSEKAPITAL], kommun=KOMMUN,
            anrop_per_sekund=_anropsgrans("SCB", 2)),
        SkrSkatteunderlag(anrop_per_sekund=_anropsgrans("SKR", 1)),
        *(Protokollkalla(organ, urval=int(os.environ.get("PROTOKOLL_URVAL") or 0),
                         anrop_per_sekund=_anropsgrans("PROTOKOLL", 1)) for organ in ORGAN),
        Sammantradesplaner(anrop_per_sekund=_anropsgrans("PROTOKOLL", 1)),
        Valmyndigheten(anrop_per_sekund=_anropsgrans("VALMYNDIGHETEN", 1)),
        Foretagsklimat(anrop_per_sekund=_anropsgrans("RANKNINGAR", 1)),
        Miljobarometern(anrop_per_sekund=_anropsgrans("RANKNINGAR", 1)),
        StyrandeDokument(urval=urval_fran_miljo(), anrop_per_sekund=_anropsgrans("PROTOKOLL", 1)),
    ]


def create_app(
    database_url: str | None = None,
    kallor: list[Datakalla] | None = None,
    transport: httpx.BaseTransport | None = None,
    inloggning: Inloggning | None = None,
    auth_transport: httpx.BaseTransport | None = None,
    schema: Schema | None | object = FRAN_MILJO,
    robusthet: Robusthet | None = None,
) -> FastAPI:
    if schema is FRAN_MILJO:
        schema = Schema.fran_miljo()
    database_url = database_url or os.environ["DATABASE_URL"]
    kallor = kallor if kallor is not None else standardkallor()
    if transport is None and os.environ.get("INSPELNINGAR"):
        transport = InspeladTransport(Path(os.environ["INSPELNINGAR"]))

    db.migrate(database_url)
    sokvektorer.forvarm(database_url)
    app = FastAPI(title="Kommunkollen Härnösand")
    app.state.inloggning = inloggning or Inloggning.fran_miljo()
    app.add_middleware(
        SessionMiddleware,
        # Utan SESSION_SECRET blir alla utloggade när appen startas om.
        secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32),
        session_cookie="kommunkollen_session",
        same_site="lax",
        https_only=os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true",
        max_age=14 * 24 * 3600,
    )

    def http_klient() -> httpx.Client:
        return httpx.Client(transport=transport, timeout=30.0, headers={"User-Agent": "kommunkollen/0.1"})

    def auth_klient() -> httpx.Client:
        return httpx.Client(transport=auth_transport, timeout=15.0)

    app.include_router(auth.router(auth_klient))

    @app.get("/api/halsa")
    def halsa() -> dict:
        return {"status": "ok"}

    @app.post("/api/insamlingar", dependencies=[Depends(krav_roll("redaktor"))])
    def starta_insamling(kalla: str | None = None) -> dict:
        """Kör alla källor, eller bara `kalla` (omkörning av en enskild källa)."""
        valda = kallor if kalla is None else [k for k in kallor if k.id == kalla]
        if not valda:
            raise HTTPException(404, f"Datakällan {kalla} finns inte")
        with db.connect(database_url) as conn, http_klient() as client:
            try:
                res = kor_insamling(conn, valda, client, utlosare="manuell", robusthet=robusthet)
            except InsamlingPagar as e:
                raise HTTPException(409, str(e)) from None
        return {
            "korning_id": res.korning_id,
            "status": res.status,
            "kallor": [vars(k) for k in res.kallor],
        }

    @app.get("/api/status", dependencies=[Depends(krav_roll("lasare"))])
    def uppdateringsstatus() -> dict:
        with db.connect(database_url) as conn:
            resultat = status.global_status(conn, kallor)
            # Vektorsökningen (#69): hur många sökenheter som har vektorer och hur många som väntar.
            resultat["sokvektorer"] = sokvektorer.status(conn)
        resultat["nasta_korning"] = schema.nasta(datetime.now(SVERIGE)) if schema else None
        return resultat

    @app.get("/api/datakallor", dependencies=[Depends(krav_roll("lasare"))])
    def datakallor() -> list[dict]:
        with db.connect(database_url) as conn:
            return status.datakallor(conn, kallor)

    @app.get("/api/insamlingar", dependencies=[Depends(krav_roll("lasare"))])
    def korningslogg(antal: int = Query(50, ge=1, le=500)) -> list[dict]:
        with db.connect(database_url) as conn:
            return status.korningslogg(conn, antal)

    @app.get("/api/matt/{matt_id}/serie", dependencies=[Depends(krav_roll("lasare"))])
    def serie(matt_id: str, omrade: str = KOMMUN) -> dict:
        with db.connect(database_url) as conn:
            resultat = ekonomi.las_nyckeltal(conn, matt_id, omrade)
        if resultat is None:
            raise HTTPException(404, f"Måttet {matt_id} finns inte")
        return resultat

    @app.get("/api/ekonomi", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomiska_nyckeltal(omrade: str = KOMMUN) -> dict:
        """Alla ekonomiska nyckeltal i katalogen, grupperade som kort, och huvudtalen för översikten.
        Ett mått som inte samlats in än har serie null. Ett kort med växeln Totalt / Per invånare har
        varianten per invånare i `per_invanare`. Kolada-måtten har genomsnittet för riket i `riket`."""

        def nyckeltal(conn, matt_id: str) -> dict:
            s = ekonomi.las_nyckeltal(conn, matt_id, omrade)
            # Genomsnittet för riket finns bara för Kolada-måtten (#82). Övriga har riket null.
            riket = ekonomi.las_riket(conn, matt_id)
            return {
                "id": matt_id,
                "prisniva": ekonomi.prisniva(s["matt"]["enhet"]) if s else None,
                "serie": s,
                "riket": riket,
            }

        with db.connect(database_url) as conn:
            grupper = [
                {
                    "id": g.id,
                    "titel": g.titel,
                    "ingress": g.ingress,
                    "nyckeltal": [
                        nyckeltal(conn, k.matt)
                        | {
                            "per_invanare": nyckeltal(conn, k.per_invanare) if k.per_invanare else None,
                            "samband": [{"till": sb.till, "text": sb.text} for sb in ekonomi.SAMBAND.get(k.matt, [])],
                        }
                        for k in g.kort
                    ],
                }
                for g in ekonomi.GRUPPER
            ]
        huvudtal = [{"id": h.matt, "kort": h.kort, "titel": h.titel, "forklaring": h.forklaring} for h in ekonomi.HUVUDTAL]
        return {"omrade": omrade, "grupper": grupper, "huvudtal": huvudtal}

    @app.get("/api/undersokningar", dependencies=[Depends(krav_roll("lasare"))])
    def undersokningssidan(omrade: str = KOMMUN) -> dict:
        """Medborgarundersökningen, Insikt och anmälda brott (#67): urvalet per avsnitt med genomsnittet för
        riket, och alla frågor i medborgarundersökningen för analysverktyget."""
        with db.connect(database_url) as conn:
            return undersokningar.las(conn, omrade)

    @app.get("/api/undersokningar/nyckeltal/{matt_id}", dependencies=[Depends(krav_roll("lasare"))])
    def undersokningsnyckeltal(matt_id: str, omrade: str = KOMMUN) -> dict:
        """Ett nyckeltal ur undersökningarna, t.ex. en fråga i medborgarundersökningen som inte är i urvalet."""
        if not undersokningar.i_katalogen(matt_id):
            raise HTTPException(404, f"Nyckeltalet {matt_id} finns inte bland undersökningarna")
        with db.connect(database_url) as conn:
            return undersokningar.nyckeltal(conn, matt_id, omrade)

    @app.get("/api/rankningar", dependencies=[Depends(krav_roll("lasare"))])
    def rankningslista() -> list[dict]:
        """Rankningarna (#66) med Härnösands senaste placering och förändringen mot året innan."""
        with db.connect(database_url) as conn:
            return rankningar.lista(conn)

    @app.get("/api/rankningar/{rankning_id}", dependencies=[Depends(krav_roll("lasare"))])
    def rankningssida(rankning_id: str) -> dict:
        """En rankning: placeringen över tid för Härnösand och grannkommunerna, delmåtten och metodbytena."""
        with db.connect(database_url) as conn:
            try:
                return rankningar.rankning(conn, rankning_id)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e

    @app.post("/api/rankningar/{rankning_id}/metodbyten", status_code=201)
    def registrera_metodbyte(rankning_id: str, data: dict,
                             anv: Anvandare = Depends(krav_roll("redaktor"))) -> list[dict]:
        with db.connect(database_url) as conn:
            try:
                return rankningar.registrera_metodbyte(conn, rankning_id, data, anv.epost)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except rankningar.Ogiltig as e:
                raise HTTPException(422, str(e)) from e

    @app.delete("/api/rankningar/{rankning_id}/metodbyten/{ar}")
    def ta_bort_metodbyte(rankning_id: str, ar: int,
                          anv: Anvandare = Depends(krav_roll("redaktor"))) -> list[dict]:
        with db.connect(database_url) as conn:
            try:
                return rankningar.ta_bort_metodbyte(conn, rankning_id, ar)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e

    @app.get("/api/ekonomi/resultatbro", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomisk_resultatbro(omrade: str = KOMMUN) -> dict:
        """Brodiagrammet för årets resultat per år, med kontrollen mot SCB:s årets resultat (#81)."""
        with db.connect(database_url) as conn:
            return resultatbro.las(conn, omrade)

    @app.get("/api/skatteunderlagsprognoser", dependencies=[Depends(krav_roll("lasare"))])
    def skatteunderlagsprognoser() -> dict:
        """SKR:s skatteunderlagsprognoser för kommunen: den senaste och alla cirkulär (#61)."""
        with db.connect(database_url) as conn:
            return skatteunderlag.lista(conn)

    @app.get("/api/floden", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomiska_floden(
        ar: str | None = None, jamfor: str | None = None, verksamhet: str | None = None, omrade: str = KOMMUN
    ) -> dict:
        """Sankey-modellen för ett år. Utan år: senaste år med fullständigt underlag.

        `verksamhet` (t.ex. 490) ger fördjupningen i ett verksamhetsområdes kostnadsslag.
        `jamfor` lägger till förändringen per flöde mot ett annat år.
        """
        if verksamhet is not None and verksamhet not in floden.OMRADESNAMN:
            raise HTTPException(404, f"Verksamhetsområdet {verksamhet} finns inte")
        with db.connect(database_url) as conn:
            varden = floden.las_varden(conn, omrade)
            titlar = {r["id"]: r["titel"] for r in conn.execute("SELECT id, titel FROM matt")}

        def berakna(a: str) -> dict:
            if verksamhet is None:
                return floden.modell(varden, a, titlar)
            return floden.fordjupning(varden, a, verksamhet, titlar)

        ar_lista = [{"ar": a, "fullstandig": berakna(a)["fullstandig"]} for a in floden.tillgangliga_ar(varden)]
        if ar is None:
            fullstandiga = [a["ar"] for a in ar_lista if a["fullstandig"]]
            ar = fullstandiga[-1] if fullstandiga else (ar_lista[-1]["ar"] if ar_lista else None)
        if ar is None:
            return {"ar": None, "tillgangliga_ar": [], "fullstandig": False, "saknas": [], "noder": [], "floden": [],
                    "verksamhet": None}
        resultat = berakna(ar)
        if jamfor is not None and jamfor != ar:
            resultat = floden.jamfor(resultat, berakna(jamfor))
        return resultat | {"omrade": omrade, "tillgangliga_ar": ar_lista}

    # Politik och beslut: sammanträden och behandlingar ur protokollen (automatiskt tolkade uppgifter).

    @app.get("/api/organ", dependencies=[Depends(krav_roll("lasare"))])
    def organ() -> list[dict]:
        return [{"id": o.id, "namn": o.namn} for o in ORGAN.values()]

    @app.get("/api/sammantraden", dependencies=[Depends(krav_roll("lasare"))])
    def sammantraden(organ: str | None = None, ar: int | None = None) -> list[dict]:
        with db.connect(database_url) as conn:
            return protokoll.lista_sammantraden(conn, organ, ar)

    @app.get("/api/behandlingar", dependencies=[Depends(krav_roll("lasare"))])
    def behandlingar(q: str, organ: str | None = None, ar: int | None = None) -> dict:
        """Sök behandlingar på rubrik eller diarienummer."""
        if len(q.strip()) < 2:
            raise HTTPException(422, "Söktexten behöver vara minst två tecken")
        with db.connect(database_url) as conn:
            return protokoll.sok_behandlingar(conn, q, organ, ar)

    # Fulltextsökning (#142). Sökfrågorna loggas inte, bara antalet träffar och svarstiden.
    sokgrans = sokindex.Fragegrans(int(os.environ.get("SOK_FRAGOR_PER_MINUT") or 30), 60.0)
    soklogg = logging.getLogger("app.sok")
    atkomstlogg = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, sokindex.UtanSokfragor) for f in atkomstlogg.filters):
        atkomstlogg.addFilter(sokindex.UtanSokfragor())

    @app.get("/api/sok", dependencies=[Depends(krav_roll("lasare"))])
    def sok(
        request: Request,
        q: str = "",
        organ: str | None = None,
        ar: int | None = None,
        typ: str | None = Query(None, pattern=f"^({'|'.join(sokindex.TYPER)})$"),
        sortering: str = Query("relevans", pattern="^(relevans|datum)$"),
        sida: int = Query(1, ge=1, le=50),
        markning: str | None = Query(None, pattern=f"^({'|'.join(markningar.MARKNINGAR)})$"),
    ) -> dict:
        """Sök i behandlingar, protokollsidor, budgetförslag, ärenden, ledamöter och kallelsepunkter.

        Med `markning` bara behandlingar och ärenden med märkningen (#162). Då kan söktexten vara tom, och
        svaret är alla med märkningen, t.ex. alla behandlingar med votering ett år.

        Högst 30 frågor per minut och IP-adress. Svaret är träffar i källorna, aldrig ett genererat svar (ADR-0002).
        """
        vanta = sokgrans.tillat(request.client.host if request.client else "")
        if vanta is not None:
            raise HTTPException(429, "För många sökningar på kort tid. Vänta en stund och försök igen.",
                                headers={"Retry-After": str(max(1, math.ceil(vanta)))})
        if len(q.strip()) < 2 and not (markning and not q.strip()):
            raise HTTPException(422, "Söktexten behöver vara minst två tecken")
        if organ is not None and organ not in ORGAN:
            raise HTTPException(422, f"Organet {organ} finns inte")
        start = time.perf_counter()
        with db.connect(database_url) as conn:
            svar = sokindex.sok(conn, q, organ=organ, ar=ar, typ=typ, sortering=sortering, sida=sida,
                                markning=markning)
        soklogg.info("Sökning: %d träffar på %.0f ms", svar["antal"], (time.perf_counter() - start) * 1000)
        return svar

    def intervall(conn, fran: int | None, till: int | None, organ: str | None) -> tuple[int, int]:
        """Åren fran–till, som standard alla år med protokoll."""
        if organ is not None and organ not in ORGAN:
            raise HTTPException(422, f"Organet {organ} finns inte")
        ar = statistik.tillgangliga_ar(conn)
        fran = fran if fran is not None else (ar[0] if ar else date.today().year)
        till = till if till is not None else (ar[-1] if ar else fran)
        if fran > till:
            raise HTTPException(422, "Startåret kan inte vara efter slutåret")
        return fran, till

    @app.get("/api/statistik/behandlingar", dependencies=[Depends(krav_roll("lasare"))])
    def statistik_behandlingar(fran: int | None = None, till: int | None = None, organ: str | None = None) -> dict:
        """Behandlingar per år, organ och behandlingstyp för åren fran–till (båda inräknade)."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return statistik.behandlingar(conn, fran, till, organ)

    @app.get("/api/statistik/behandlingar/{typ}", dependencies=[Depends(krav_roll("lasare"))])
    def statistik_behandlingar_av_typ(typ: str, fran: int | None = None, till: int | None = None,
                                      organ: str | None = None) -> list[dict]:
        """Behandlingarna av en typ (eller "okand") för åren fran–till, de senaste först."""
        if typ not in (*TYPER, statistik.OKAND):
            raise HTTPException(422, f"Behandlingstypen {typ} finns inte")
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return statistik.behandlingar_av_typ(conn, fran, till, organ, typ)

    @app.get("/api/statistik/motioner", dependencies=[Depends(krav_roll("lasare"))])
    def statistik_motioner(fran: int | None = None, till: int | None = None, organ: str | None = None) -> dict:
        """Motioner och medborgarförslag: väckta, besvarade, utfall och ledtid (#45)."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return motioner.motioner_och_forslag(conn, fran, till, organ)

    @app.get("/api/statistik/aterkommande", dependencies=[Depends(krav_roll("lasare"))])
    def statistik_aterkommande(fran: int | None = None, till: int | None = None, organ: str | None = None) -> dict:
        """Ärenden som behandlats vid flera sammanträden, med återremisser och bordläggningar (#46)."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return aterkommande.aterkommande(conn, fran, till, organ)

    @app.get("/api/kommande", dependencies=[Depends(krav_roll("lasare"))])
    def kommande_arenden(manader: int = Query(kommande.MANADER, ge=1, le=120)) -> dict:
        """Ärenden som inte är avslutade: obesvarade motioner, uppskjutna ärenden, förslag och uppdrag."""
        with db.connect(database_url) as conn:
            return kommande.kommande(conn, manader)

    @app.get("/api/kommande/{arende_id}", dependencies=[Depends(krav_roll("lasare"))])
    def kommande_underlag(arende_id: int) -> dict:
        """Ärendet med protokollen och hänvisningarna i beslutsunderlaget bakom varje behandling."""
        with db.connect(database_url) as conn:
            resultat = kommande.underlag(conn, arende_id)
        if resultat is None:
            raise HTTPException(404, f"Ärendet {arende_id} finns inte")
        return resultat

    @app.get("/api/avvikelser", dependencies=[Depends(krav_roll("lasare"))])
    def protokollens_avvikelser(fran: int | None = None, till: int | None = None, organ: str | None = None) -> dict:
        """Sammanträden vars protokoll har avvikelser eller publicerade rättelser."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return avvikelser.lista(conn, fran, till, organ)

    # Att anmäla är redaktionens verktyg och inte publikt (#160).
    @app.get("/api/protokollavvikelser", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_protokollavvikelser(
        fran: int | None = None, till: int | None = None, organ: str | None = None,
        typ: str | None = Query(None, pattern="^(rostsumma|parti_olika|ersattare|paragrafnummer|parti_saknas|stavning)$"),
        status: str | None = Query(None, pattern="^(ny|anmald|rattad|inte_fel)$"),
    ) -> dict:
        """Uppgifter i protokollen som inte stämmer med varandra (#47), per protokoll och med status."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return protokollavvikelser.lista(conn, fran, till, organ, typ, status)

    @app.post("/api/protokollavvikelser/{avvikelse_id}/status")
    def satt_protokollavvikelsens_status(avvikelse_id: int, data: dict,
                                         anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Redaktören sätter status: {status: ny|anmald|rattad|inte_fel, datum, anteckning}."""
        with db.connect(database_url) as conn:
            try:
                return protokollavvikelser.satt_status(conn, avvikelse_id, data, anv.epost)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except protokollavvikelser.Ogiltig as e:
                raise HTTPException(422, str(e)) from e

    @app.get("/api/sammantraden/{sammantrade_id}", dependencies=[Depends(krav_roll("lasare"))])
    def sammantrade(sammantrade_id: int) -> dict:
        with db.connect(database_url) as conn:
            resultat = protokoll.las_sammantrade(conn, sammantrade_id)
        if resultat is None:
            raise HTTPException(404, f"Sammanträdet {sammantrade_id} finns inte")
        return resultat

    @app.get("/api/sammantraden/{sammantrade_id}/behandlingar/{paragraf}", dependencies=[Depends(krav_roll("lasare"))])
    def behandling(sammantrade_id: int, paragraf: int) -> dict:
        with db.connect(database_url) as conn:
            resultat = protokoll.las_behandling(conn, sammantrade_id, paragraf)
            if resultat is not None:
                # Styrande dokument som behandlingen fastställde (#63).
                resultat["styrande_dokument"] = styrande_dokument.for_behandling(conn, sammantrade_id, paragraf)
        if resultat is None:
            raise HTTPException(404, f"§ {paragraf} finns inte i sammanträdet {sammantrade_id}")
        return resultat

    @app.get("/api/arenden/{arende_id}", dependencies=[Depends(krav_roll("lasare"))])
    def arende(arende_id: int) -> dict:
        """Ärendets väg genom organen: behandlingarna i tidsordning och kopplingarna mellan dem."""
        with db.connect(database_url) as conn:
            resultat = arenden.las_arende(conn, arende_id)
        if resultat is None:
            raise HTTPException(404, f"Ärendet {arende_id} finns inte")
        return resultat

    def _bas(request: Request) -> str:
        return os.environ.get("PUBLIK_URL", "").rstrip("/") or str(request.base_url).rstrip("/")

    @app.get("/api/kalender", dependencies=[Depends(krav_roll("lasare"))])
    def kalender_api(organ: str | None = None) -> dict:
        """Sammanträdena för sidan Kalender: kommande och de senaste 12 månaderna, med flödenas adresser."""
        if organ is not None and organ not in ORGAN:
            raise HTTPException(422, f"Organet {organ} finns inte")
        with db.connect(database_url) as conn:
            return {
                "idag": kalender.idag().isoformat(),
                "floden": [{"organ": o, "namn": ORGAN[o].namn, "flode": s} for o, s in kalender.SLUG.items()],
                "handelser": kalender.handelser(conn, organ),
            }

    # Kalenderflödena är alltid öppna utan inloggning, eftersom kalenderappar inte kan logga in.
    @app.get("/kalender/{flode}.ics", response_class=Response)
    def kalenderflode(flode: str, request: Request) -> Response:
        organ = kalender.organ_for_slug(flode)
        if organ is None:
            raise HTTPException(404, f"Kalenderflödet {flode} finns inte")
        with db.connect(database_url) as conn:
            innehall = kalender.ics(kalender.handelser(conn, organ or None), kalender.flodesnamn(organ), _bas(request))
        return Response(innehall, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": f'inline; filename="{flode}.ics"'})

    @app.get("/kalender/sammantraden/{sammantrade_id}.ics", response_class=Response)
    def kalenderhandelse(sammantrade_id: int, request: Request) -> Response:
        with db.connect(database_url) as conn:
            handelser = kalender.handelser(conn, sammantrade_id=sammantrade_id)
        if not handelser:
            raise HTTPException(404, f"Sammanträdet {sammantrade_id} finns inte i kalendern")
        h = handelser[0]
        innehall = kalender.ics(handelser, kalender.flodesnamn(h["organ"]["id"]), _bas(request))
        return Response(innehall, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition":
                                 f'attachment; filename="{h["organ"]["flode"]}-{h["datum"]}.ics"'})

    @app.get("/api/sammantradesplaner", dependencies=[Depends(krav_roll("redaktor"))])
    def sammantradesplaner() -> list[dict]:
        """Organens sammanträdesplaner med versionerna, och skillnaderna mot besluten i protokollen.

        Bara för redaktionen, eftersom skillnaderna inte visas publikt."""
        with db.connect(database_url) as conn:
            return sammantradesplan.lista(conn)

    @app.get("/api/kopplingar")
    def kopplingar(status: str = Query("forslag", pattern="^(automatisk|forslag|bekraftad|avvisad)$"),
                   mina: bool = False, anv: Anvandare = Depends(krav_roll("redaktor"))) -> list[dict]:
        """Kön med förslag på kopplingar, eller kopplingarna med en annan status. `mina` = bara egna beslut."""
        with db.connect(database_url) as conn:
            return arenden.lista_kopplingar(conn, status, anv.epost if mina else None)

    def _besluta(koppling_id: int, status: str, anv: Anvandare, motivering: str | None = None) -> dict:
        with db.connect(database_url) as conn:
            try:
                return arenden.besluta(conn, koppling_id, status, anv.epost, motivering)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except arenden.OgiltigtBeslut as e:
                raise HTTPException(422, str(e)) from e

    @app.post("/api/kopplingar/{koppling_id}/bekraftelse")
    def bekrafta_koppling(koppling_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _besluta(koppling_id, "bekraftad", anv)

    @app.post("/api/kopplingar/{koppling_id}/avvisning")
    def avvisa_koppling(koppling_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _besluta(koppling_id, "avvisad", anv)

    @app.post("/api/kopplingar/{koppling_id}/beslut")
    def andra_kopplingsbeslut(koppling_id: int, data: dict,
                              anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Ändrar ett beslut (#77): {status: forslag|bekraftad|avvisad, motivering}."""
        return _besluta(koppling_id, str(data.get("status", "")), anv, data.get("motivering"))

    # Redaktionella rättelser (#33): redaktören skriver, en annan person med rollen utgivare granskar och publicerar.

    def _rattelse(steg, *args):
        with db.connect(database_url) as conn:
            try:
                return steg(conn, *args)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except rattelser.Ogiltig as e:
                raise HTTPException(422, str(e)) from e
            except rattelser.EjTillatet as e:
                raise HTTPException(403, str(e)) from e
            except rattelser.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.get("/api/rattelser", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_rattelser(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt|aterkallad)$"),
    ) -> list[dict]:
        return _rattelse(rattelser.lista, status)

    @app.post("/api/rattelser", status_code=201)
    def skapa_rattelse(data: dict, anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> dict:
        """En rättelse som utkast: {sammantrade_id, objekt, paragraf, votering, namn, falt, nytt, motivering}.

        Motionärer (#78) kan också skrivas av en utgivare. Övriga uppgifter rättas av en redaktör."""
        if "redaktor" not in anv.roller and data.get("falt") != "motionarer":
            raise HTTPException(403, "Kräver rollen redaktör")
        return _rattelse(rattelser.skapa, data, anv.epost)

    # Ändra och ta bort: bara den som skrev utkastet (rattelser.py kontrollerar det).
    @app.patch("/api/rattelser/{rattelse_id}")
    def andra_rattelse(rattelse_id: int, data: dict,
                       anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> dict:
        return _rattelse(rattelser.andra, rattelse_id, data, anv.epost)

    @app.delete("/api/rattelser/{rattelse_id}", status_code=204)
    def ta_bort_rattelse(rattelse_id: int, anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> Response:
        _rattelse(rattelser.ta_bort, rattelse_id, anv.epost)
        return Response(status_code=204)

    @app.post("/api/rattelser/{rattelse_id}/granskning")
    def granska_rattelse(rattelse_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _rattelse(rattelser.granska, rattelse_id, anv.epost)

    @app.post("/api/rattelser/{rattelse_id}/publicering")
    def publicera_rattelse(rattelse_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _rattelse(rattelser.publicera, rattelse_id, anv.epost)

    # Ändra en granskad eller publicerad rättelse genom en ny version, och återkalla en publicerad (#74).
    @app.post("/api/rattelser/{rattelse_id}/versioner", status_code=201)
    def ny_version_av_rattelse(rattelse_id: int, data: dict,
                               anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> dict:
        """En ny version som utkast: {nytt, motivering, felet_i}. Saknade fält tas från den gamla versionen."""
        return _rattelse(rattelser.ny_version, rattelse_id, data, anv.epost, set(anv.roller))

    @app.post("/api/rattelser/{rattelse_id}/aterkallelse")
    def aterkalla_rattelse(rattelse_id: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        """Återkalla en publicerad rättelse direkt: {motivering}. Tolkningen gäller igen."""
        return _rattelse(rattelser.aterkalla, rattelse_id, data, anv.epost)

    # Fastställd partitillhörighet per period (#100, ADR-0006): redaktören skriver, en annan person med rollen
    # utgivare granskar och publicerar. Ändras genom en ny version och kan återkallas, som en rättelse.

    def _period(steg, *args):
        with db.connect(database_url) as conn:
            try:
                return steg(conn, *args)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except partitillhorighet.Ogiltig as e:
                raise HTTPException(422, str(e)) from e
            except partitillhorighet.EjTillatet as e:
                raise HTTPException(403, str(e)) from e
            except partitillhorighet.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.get("/api/partitillhorighet", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_partitillhorighet(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt|aterkallad)$"),
        ledamot_id: int | None = None,
    ) -> list[dict]:
        return _period(partitillhorighet.lista, status, ledamot_id)

    @app.post("/api/partitillhorighet", status_code=201)
    def skapa_partitillhorighet(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """En period som utkast: {ledamot_id, parti, fran, till, motivering}. till kan vara null (tills vidare)."""
        return _period(partitillhorighet.skapa, data, anv.epost)

    @app.get("/api/partitillhorighet/forslag", dependencies=[Depends(krav_roll("redaktor"))])
    def partitillhorighet_forslag() -> list[dict]:
        """Föreslagna perioder per person ur närvarolistorna, med belägg och krockar (#100, del 2)."""
        with db.connect(database_url) as conn:
            return partiforslag.forslag(conn)

    @app.get("/api/partitillhorighet/krockar", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def partitillhorighet_krockar() -> list[dict]:
        """Obekräftade krockar per person: närvarolistan anger ett annat parti än perioden (#100, del 3)."""
        with db.connect(database_url) as conn:
            return krockar.lista(conn)

    @app.post("/api/partitillhorighet/krockar/bekraftelser", status_code=201)
    def bekrafta_krockar(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> list[dict]:
        """Bekräftar krockar som rättelser (utkast): {felet_i, motivering, krockar: [{sammantrade_id, namn}]}."""
        return _rattelse(krockar.bekrafta, data, anv.epost)

    @app.get("/api/partitillhorighet/personer", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def partitillhorighet_personer() -> list[dict]:
        """Personerna med perioder, väntande och krockar, för filtren i fliken (#100, del 3)."""
        with db.connect(database_url) as conn:
            return krockar.personer(conn)

    @app.post("/api/partitillhorighet/batcher", status_code=201)
    def skapa_partitillhorighet_batch(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> list[dict]:
        """Bekräftade förslag som utkast i en batch: {motivering, perioder: [{ledamot_id, parti, fran, till,
        motivering?}]}."""
        return _period(partitillhorighet.skapa_batch, data, anv.epost)

    @app.post("/api/partitillhorighet/batcher/{batch}/granskning")
    def granska_partitillhorighet_batch(batch: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> list[dict]:
        return _period(partitillhorighet.granska_batch, batch, anv.epost)

    @app.post("/api/partitillhorighet/batcher/{batch}/publicering")
    def publicera_partitillhorighet_batch(batch: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> list[dict]:
        return _period(partitillhorighet.publicera_batch, batch, anv.epost)

    @app.patch("/api/partitillhorighet/{period_id}")
    def andra_partitillhorighet(period_id: int, data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _period(partitillhorighet.andra, period_id, data, anv.epost)

    @app.delete("/api/partitillhorighet/{period_id}", status_code=204)
    def ta_bort_partitillhorighet(period_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> Response:
        _period(partitillhorighet.ta_bort, period_id, anv.epost)
        return Response(status_code=204)

    @app.post("/api/partitillhorighet/{period_id}/granskning")
    def granska_partitillhorighet(period_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _period(partitillhorighet.granska, period_id, anv.epost)

    @app.post("/api/partitillhorighet/{period_id}/publicering")
    def publicera_partitillhorighet(period_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _period(partitillhorighet.publicera, period_id, anv.epost)

    @app.post("/api/partitillhorighet/{period_id}/versioner", status_code=201)
    def ny_version_av_partitillhorighet(period_id: int, data: dict,
                                        anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _period(partitillhorighet.ny_version, period_id, data, anv.epost)

    @app.post("/api/partitillhorighet/{period_id}/aterkallelse")
    def aterkalla_partitillhorighet(period_id: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _period(partitillhorighet.aterkalla, period_id, data, anv.epost)

    # Partiernas budgetförslag (#48): läses in som utkast, rättas av redaktör och publiceras av utgivare.

    def _budget(steg, *args):
        with db.connect(database_url) as conn:
            try:
                return steg(conn, *args)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except budgetforslag.Ogiltig as e:
                raise HTTPException(422, str(e)) from e
            except budgetforslag.EjTillatet as e:
                raise HTTPException(403, str(e)) from e
            except budgetforslag.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.get("/api/budget", dependencies=[Depends(krav_roll("lasare"))])
    def budgetar() -> list[dict]:
        """Budgetåren med publicerade budgetförslag."""
        return _budget(budgetforslag.budgetar)

    @app.get("/api/budget/{ar}", dependencies=[Depends(krav_roll("lasare"))])
    def budgetjamforelse(ar: int) -> dict:
        """De publicerade förslagen för budgetåret bredvid varandra, mot planförutsättningarna och den antagna budgeten."""
        return _budget(budgetforslag.jamforelse, ar)

    @app.get("/api/budgetforslag", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_budgetforslag(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt|aterkallad)$"),
    ) -> list[dict]:
        return _budget(budgetforslag.lista, status)

    @app.get("/api/budgetforslag/{forslag_id}", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def las_budgetforslag(forslag_id: int) -> dict:
        return _budget(budgetforslag.las, forslag_id)

    @app.get("/api/budget/tidigare/forslag/{forslag_id}", dependencies=[Depends(krav_roll("lasare"))])
    def tidigare_budgetforslag(forslag_id: int) -> dict:
        """En förra version av ett förslag som har ändrats efter publicering (#76)."""
        return _budget(budgetforslag.tidigare, forslag_id)

    @app.get("/api/budget/tidigare/planforutsattningar/{pf_id}", dependencies=[Depends(krav_roll("lasare"))])
    def tidigare_planforutsattningar(pf_id: int) -> dict:
        """En förra version av planförutsättningar som har ändrats efter publicering (#76)."""
        return _budget(planforutsattningar.tidigare, pf_id)

    @app.patch("/api/budgetforslag/{forslag_id}")
    def andra_budgetforslag(forslag_id: int, data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Rättar ett utkast: {uppgifter, partier, titel, antagen, anmarkning}."""
        return _budget(budgetforslag.andra, forslag_id, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/budgetforslag/{forslag_id}/granskning")
    def granska_budgetforslag(forslag_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(budgetforslag.granska, forslag_id, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/budgetforslag/{forslag_id}/publicering")
    def publicera_budgetforslag(forslag_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(budgetforslag.publicera, forslag_id, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/budgetforslag/{forslag_id}/versioner", status_code=201)
    def ny_version_av_budgetforslag(forslag_id: int, data: dict,
                                    anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> dict:
        """En ny version av ett publicerat eller återkallat förslag, som utkast: {motivering} (#76)."""
        return _budget(budgetforslag.ny_version, forslag_id, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/budgetforslag/{forslag_id}/aterkallelse")
    def aterkalla_budgetforslag(forslag_id: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        """En utgivare återkallar ett publicerat förslag direkt, med motivering (#76)."""
        return _budget(budgetforslag.aterkalla, forslag_id, data, anv.epost, datetime.now(timezone.utc))

    @app.get("/api/budgetforslag/{forslag_id}/original")
    def budgetforslagets_original(forslag_id: int, request: Request,
                                  anv: Anvandare | None = Depends(krav_roll("lasare"))) -> Response:
        """Originaldokumentet. Ett opublicerat förslag visas bara för redaktör och utgivare."""
        redaktion = bool(anv and anv.roller & {"redaktor", "utgivare"})
        innehall, typ, namn = _budget(budgetforslag.original, forslag_id, redaktion)
        return Response(innehall, media_type=typ, headers={"Content-Disposition": f'inline; filename="{namn}"'})

    # Planförutsättningar per budgetår (#58): läses in som utkast tillsammans med förslagen.

    @app.get("/api/planforutsattningar", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_planforutsattningar(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt|aterkallad)$"),
    ) -> list[dict]:
        return _budget(planforutsattningar.lista, status)

    @app.get("/api/planforutsattningar/{pf_id}", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def las_planforutsattningar(pf_id: int) -> dict:
        return _budget(planforutsattningar.las, pf_id)

    @app.post("/api/planforutsattningar/{pf_id}/granskning")
    def granska_planforutsattningar(pf_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(planforutsattningar.granska, pf_id, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/planforutsattningar/{pf_id}/publicering")
    def publicera_planforutsattningar(pf_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(planforutsattningar.publicera, pf_id, anv.epost, datetime.now(timezone.utc))

    @app.patch("/api/planforutsattningar/{pf_id}")
    def andra_planforutsattningar(pf_id: int, data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Rättar ett utkast: {uppgifter: {skattesats, tabeller}} (#76)."""
        return _budget(planforutsattningar.andra, pf_id, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/planforutsattningar/{pf_id}/versioner", status_code=201)
    def ny_version_av_planforutsattningar(pf_id: int, data: dict,
                                          anv: Anvandare = Depends(krav_roll("redaktor", "utgivare"))) -> dict:
        """En ny version av publicerade eller återkallade planförutsättningar, som utkast: {motivering} (#76)."""
        return _budget(planforutsattningar.ny_version, pf_id, data, anv.epost, datetime.now(timezone.utc))

    # Budget jämfört med utfall per budgetår (#83): läses in som utkast tillsammans med budgetförslagen.

    @app.get("/api/budget-och-utfall", dependencies=[Depends(krav_roll("lasare"))])
    def budget_och_utfall_ar() -> list[dict]:
        """Budgetåren med publicerad uppföljning."""
        return _budget(uppfoljning.ar)

    @app.get("/api/budget-och-utfall/{ar}", dependencies=[Depends(krav_roll("lasare"))])
    def budget_och_utfall(ar: int) -> dict:
        """Antagen och reviderad budget, delårsprognos och utfall för året, per nämnd och för resultatet."""
        return _budget(uppfoljning.publicerad, ar)

    @app.get("/api/uppfoljning/{id_}/dokument/{nyckel}")
    def uppfoljningsdokument(id_: int, nyckel: str, anv: Anvandare | None = Depends(krav_roll("lasare"))) -> Response:
        """Ett dokument som inte finns publikt och lagras i plattformen, t.ex. en utbegärd delårsrapport."""
        redaktion = bool(anv and anv.roller & {"redaktor", "utgivare"})
        innehall, _ = _budget(uppfoljning.dokument, id_, nyckel, redaktion)
        return Response(innehall, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{nyckel}-{id_}.pdf"'})

    @app.get("/api/uppfoljning", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def lista_uppfoljning(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt|aterkallad)$"),
    ) -> list[dict]:
        return _budget(uppfoljning.lista, status)

    @app.get("/api/uppfoljning/{id_}", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def las_uppfoljning(id_: int) -> dict:
        return _budget(uppfoljning.las, id_)

    @app.post("/api/uppfoljning/{id_}/granskning")
    def granska_uppfoljning(id_: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(uppfoljning.granska, id_, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/uppfoljning/{id_}/publicering")
    def publicera_uppfoljning(id_: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _budget(uppfoljning.publicera, id_, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/uppfoljning/{id_}/aterkallelse")
    def aterkalla_uppfoljning(id_: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        """En utgivare återkallar en publicerad uppföljning direkt, med motivering."""
        return _budget(uppfoljning.aterkalla, id_, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/planforutsattningar/{pf_id}/aterkallelse")
    def aterkalla_planforutsattningar(pf_id: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        """En utgivare återkallar publicerade planförutsättningar direkt, med motivering (#76)."""
        return _budget(planforutsattningar.aterkalla, pf_id, data, anv.epost, datetime.now(timezone.utc))

    @app.get("/api/motionarer/parti", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def motionarens_parti(person_id: int, sammantrade_id: int) -> dict:
        """Förslag på parti för en motionär vid sammanträdet där motionen väcktes (#78), med källa."""
        with db.connect(database_url) as conn:
            try:
                return motionarer.parti_for(conn, person_id, sammantrade_id)
            except motionarer.Ogiltig as e:
                raise HTTPException(404, str(e)) from e

    @app.get("/api/ledamoter", dependencies=[Depends(krav_roll("lasare"))])
    def lista_ledamoter(q: str | None = None, parti: str | None = None, organ: str | None = None) -> list[dict]:
        """Registret över ledamöter och ersättare ur protokollens närvarolistor."""
        with db.connect(database_url) as conn:
            return ledamoter.lista(conn, q, parti, organ)

    @app.get("/api/ledamoter/{ledamot_id}", dependencies=[Depends(krav_roll("lasare"))])
    def ledamot(ledamot_id: int) -> dict:
        with db.connect(database_url) as conn:
            resultat = ledamoter.las(conn, ledamot_id)
            if resultat is not None:
                # Märkningarna på behandlingarna där ledamoten röstade (#162).
                markningar.satt_pa_paragrafer(conn, resultat["roster"])
        if resultat is None:
            raise HTTPException(404, f"Ledamoten {ledamot_id} finns inte")
        return resultat

    @app.post("/api/ledamoter/{ledamot_id}/sammanslagningar")
    def sla_ihop_ledamoter(ledamot_id: int, med: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Slår ihop personen `med` med `ledamot_id`, vars namn blir huvudnamn."""
        with db.connect(database_url) as conn:
            try:
                return ledamoter.sla_ihop(conn, ledamot_id, med, anv.epost)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ledamoter.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.post("/api/ledamoter/{ledamot_id}/uppdelning")
    def dela_upp_ledamot(ledamot_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Gör ett sammanslaget namn till en egen person igen."""
        with db.connect(database_url) as conn:
            try:
                return ledamoter.dela_upp(conn, ledamot_id, anv.epost)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ledamoter.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    # Namnvarianter med mellannamn eller annan stavning (#165): förslag som en redaktör bekräftar eller avvisar.

    @app.get("/api/namnforslag", dependencies=[Depends(krav_roll("redaktor"))])
    def lista_namnforslag(status: str = "forslag") -> list[dict]:
        if status not in ("forslag", "bekraftad", "avvisad"):
            raise HTTPException(422, "status ska vara forslag, bekraftad eller avvisad")
        with db.connect(database_url) as conn:
            return namnvarianter.lista_forslag(conn, status)

    def _namnbeslut(forslag_id: int, bekrafta: bool, anv: Anvandare) -> dict:
        with db.connect(database_url) as conn:
            try:
                return namnvarianter.besluta(conn, forslag_id, bekrafta, anv.epost)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ledamoter.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.post("/api/namnforslag/{forslag_id}/bekrafta")
    def bekrafta_namnforslag(forslag_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Namnen slås ihop. Huvudnamnet är det som förekommer oftast."""
        return _namnbeslut(forslag_id, True, anv)

    @app.post("/api/namnforslag/{forslag_id}/avvisa")
    def avvisa_namnforslag(forslag_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Förslaget kommer inte tillbaka."""
        return _namnbeslut(forslag_id, False, anv)

    # Sammansättning: kön och ålder bland kandidater, valda och tjänstgörande (#65). Statistiken är öppen. Kön och
    # ålder per person, kopplingarna och redaktionens uppgifter är bara för redaktionen.

    def _sammansattning(steg, *args):
        with db.connect(database_url) as conn:
            try:
                return steg(conn, *args)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except sammansattning.Ogiltig as e:
                raise HTTPException(422, str(e)) from e
            except sammansattning.EjTillatet as e:
                raise HTTPException(403, str(e)) from e
            except sammansattning.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.get("/api/sammansattning", dependencies=[Depends(krav_roll("lasare"))])
    def sammansattning_statistik(period: int = max(sammansattning.PERIODER), organ: str = "KF") -> dict:
        """Kön och ålder för kandidater, valda och tjänstgörande i ett organ under en mandatperiod."""
        return _sammansattning(sammansattning.statistik, period, organ)

    @app.get("/api/sammansattning/kopplingar", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def sammansattning_kopplingar(
        status: str | None = Query(None, pattern="^(automatisk|forslag|bekraftad|avvisad)$"),
    ) -> list[dict]:
        return _sammansattning(sammansattning.kopplingar, status)

    @app.post("/api/sammansattning/kopplingar/{koppling_id}/bekraftelse")
    def bekrafta_valkoppling(koppling_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _sammansattning(sammansattning.besluta, koppling_id, "bekraftad", anv.epost)

    @app.post("/api/sammansattning/kopplingar/{koppling_id}/avvisning")
    def avvisa_valkoppling(koppling_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _sammansattning(sammansattning.besluta, koppling_id, "avvisad", anv.epost)

    @app.get("/api/sammansattning/personer", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def sammansattning_personer() -> list[dict]:
        """Kön och ålder per person, med källa och kopplingar. Bara för redaktionen."""
        return _sammansattning(sammansattning.personer)

    @app.get("/api/sammansattning/uppgifter", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def sammansattning_uppgifter(
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|aterkallad)$"),
    ) -> list[dict]:
        return _sammansattning(sammansattning.uppgifter, status)

    @app.post("/api/sammansattning/uppgifter", status_code=201)
    def skapa_personuppgift(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Kön och födelseår med källa för en person utan uppgift: {ledamot_id, kon, fodelsear, kalla}."""
        return _sammansattning(sammansattning.skapa_uppgift, data, anv.epost)

    @app.delete("/api/sammansattning/uppgifter/{uppgift_id}", status_code=204)
    def ta_bort_personuppgift(uppgift_id: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> Response:
        _sammansattning(sammansattning.ta_bort_uppgift, uppgift_id, anv.epost)
        return Response(status_code=204)

    @app.post("/api/sammansattning/uppgifter/{uppgift_id}/granskning")
    def granska_personuppgift(uppgift_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _sammansattning(sammansattning.granska_uppgift, uppgift_id, anv.epost)

    @app.post("/api/sammansattning/uppgifter/{uppgift_id}/publicering")
    def publicera_personuppgift(uppgift_id: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _sammansattning(sammansattning.publicera_uppgift, uppgift_id, anv.epost)

    @app.post("/api/sammansattning/uppgifter/{uppgift_id}/aterkallelse")
    def aterkalla_personuppgift(uppgift_id: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _sammansattning(sammansattning.aterkalla_uppgift, uppgift_id, data, anv.epost)

    @app.get("/api/styrande-dokument", dependencies=[Depends(krav_roll("lasare"))])
    def styrande_dokument_lista() -> dict:
        """Kommunens styrande dokument (#63) med kategori, fastställt av och giltighet."""
        with db.connect(database_url) as conn:
            resultat = styrande_dokument.lista(conn, kalender.idag())
            antal = motstridigheter.antal_per_dokument(conn)
            antal_processer = processer.antal_per_dokument(conn)
        for d in resultat["dokument"]:
            d["motstridigheter"] = antal.get(d["id"], 0)
            d["processer"] = antal_processer.get(d["id"], 0)
        return resultat

    @app.get("/api/styrande-dokument/{dokument_id}", dependencies=[Depends(krav_roll("lasare"))])
    def styrande_dokument_sida(dokument_id: int) -> dict:
        with db.connect(database_url) as conn:
            resultat = styrande_dokument.las(conn, dokument_id, kalender.idag())
            if resultat is not None:
                resultat["motstridigheter"] = motstridigheter.for_dokument(conn, dokument_id)
                resultat["processer"] = processer.for_dokument(conn, dokument_id)
        if resultat is None:
            raise HTTPException(404, f"Det styrande dokumentet {dokument_id} finns inte")
        return resultat

    # Motstridigheter i styrande dokument (#151): förslag från insamlingen och skillen, granskade och publicerade av
    # en utgivare som inte läst in dem. Läsaren ser bara de publicerade.

    def _motstridighet(steg, *args):
        with db.connect(database_url) as conn:
            try:
                return steg(conn, *args)
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except motstridigheter.Ogiltig as e:
                raise HTTPException(422, str(e)) from e
            except motstridigheter.EjTillatet as e:
                raise HTTPException(403, str(e)) from e
            except motstridigheter.Konflikt as e:
                raise HTTPException(409, str(e)) from e

    @app.get("/api/motstridigheter", dependencies=[Depends(krav_roll("lasare"))])
    def lista_motstridigheter(typ: str | None = None, status: str | None = None) -> dict:
        """De publicerade motstridigheterna, filtrerbara på typ och status."""
        return _motstridighet(motstridigheter.publicerade, typ, status)

    @app.post("/api/motstridigheter")
    def las_in_motstridigheter(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Läser in skillens fil som utkast, med samma kontroller som `python -m app.motstridigheter`."""
        def steg(conn):
            res = motstridigheter.las_in(conn, data, anv.epost, datetime.now(timezone.utc))
            conn.commit()
            return res
        return _motstridighet(steg)

    @app.get("/api/motstridigheter/forslag", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def motstridighetsforslag(granskning: str | None = None, typ: str | None = None,
                              dokument: int | None = None) -> dict:
        return _motstridighet(motstridigheter.forslag, granskning, typ, dokument)

    @app.post("/api/motstridigheter/{mid}/granskning")
    def granska_motstridighet(mid: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(motstridigheter.granska, mid, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/motstridigheter/{mid}/publicering")
    def publicera_motstridighet(mid: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(motstridigheter.publicera, mid, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/motstridigheter/{mid}/avvisning")
    def avvisa_motstridighet(mid: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(motstridigheter.avvisa, mid, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/motstridigheter/{mid}/aterkallelse")
    def aterkalla_motstridighet(mid: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(motstridigheter.aterkalla, mid, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/motstridigheter/{mid}/status")
    def satt_motstridighetens_status(mid: int, data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        return _motstridighet(motstridigheter.satt_status, mid, data, anv.epost)

    @app.post("/api/motstridigheter/{mid}/stallning")
    def ta_stallning_till_motstridighet(mid: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """En redaktör har tagit ställning till att ett berört dokument har ändrats."""
        return _motstridighet(motstridigheter.ta_stallning, mid, anv.epost)

    # Processer ur reglementen och delegationsordningar (#152): redaktionen bestämmer listan, skillen läser in stegen
    # och en utgivare som inte lagt till eller läst in processen granskar och publicerar den. Läsaren ser bara de
    # publicerade.

    @app.get("/api/processer", dependencies=[Depends(krav_roll("lasare"))])
    def lista_processer() -> dict:
        with db.connect(database_url) as conn:
            return {"processer": processer.publicerade(conn)}

    @app.get("/api/processer/redaktion", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def processer_for_redaktionen() -> dict:
        return _motstridighet(processer.redaktionen)

    @app.post("/api/processer")
    def lagg_till_process(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """En redaktör lägger till en process på listan. Den blir ett utkast utan steg."""
        return _motstridighet(processer.lagg_till, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/processer/inlasning")
    def las_in_processteg(data: dict, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """Läser in skillens steg som utkast, med samma kontroller som `python -m app.processer`."""
        def steg(conn):
            res = processer.las_in(conn, data, anv.epost, datetime.now(timezone.utc))
            conn.commit()
            return res
        return _motstridighet(steg)

    @app.get("/api/processer/{pid}", dependencies=[Depends(krav_roll("lasare"))])
    def las_process(pid: int) -> dict:
        return _motstridighet(processer.las, pid)

    @app.post("/api/processer/{pid}/granskning")
    def granska_process(pid: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(processer.granska, pid, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/processer/{pid}/publicering")
    def publicera_process(pid: int, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(processer.publicera, pid, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/processer/{pid}/avvisning")
    def avvisa_process(pid: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(processer.avvisa, pid, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/processer/{pid}/aterkallelse")
    def aterkalla_process(pid: int, data: dict, anv: Anvandare = Depends(krav_roll("utgivare"))) -> dict:
        return _motstridighet(processer.aterkalla, pid, data, anv.epost, datetime.now(timezone.utc))

    @app.post("/api/processer/{pid}/steg/{sid}/stallning")
    def ta_stallning_till_processteg(pid: int, sid: int, anv: Anvandare = Depends(krav_roll("redaktor"))) -> dict:
        """En redaktör har tagit ställning till att dokumentet som steget citerar har ändrats."""
        return _motstridighet(processer.ta_stallning, pid, sid, anv.epost)

    @app.get("/api/styrande-dokument/{dokument_id}/versioner/{version}", dependencies=[Depends(krav_roll("lasare"))])
    def styrande_dokument_fil(dokument_id: int, version: int) -> Response:
        """Plattformens kopia av en version, så att den finns kvar när kommunen byter ut eller tar bort filen."""
        with db.connect(database_url) as conn:
            d = styrande_dokument.fil(conn, dokument_id, version)
        if d is None:
            raise HTTPException(404, f"Version {version} av dokumentet {dokument_id} finns inte")
        filnamn = d["filnamn"].encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
        return Response(
            bytes(d["innehall"]), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filnamn}"', "ETag": f'"{d["sha256"]}"'},
        )

    @app.get("/api/dokument/{dokument_id}", dependencies=[Depends(krav_roll("lasare"))])
    def dokument(dokument_id: int) -> Response:
        """Plattformens kopia av ett hämtat dokument, så att källan finns kvar även om kommunen tar bort den."""
        with db.connect(database_url) as conn:
            d = protokoll.las_dokument(conn, dokument_id)
        if d is None:
            raise HTTPException(404, f"Dokumentet {dokument_id} finns inte")
        filnamn = d["filnamn"].encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
        return Response(
            bytes(d["innehall"]), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filnamn}"', "ETag": f'"{d["sha256"]}"',
                     "X-Content-SHA256": d["sha256"]},
        )

    return app
