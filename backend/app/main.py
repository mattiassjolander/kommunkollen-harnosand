"""HTTP-API:t."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from starlette.middleware.sessions import SessionMiddleware

from . import arenden, aterkommande, auth, avvikelser, budgetforslag, db, planforutsattningar, rattelser, ekonomi, floden, ledamoter, motionarer, motioner, kalender, protokoll, sammantradesplan, serier, skatteunderlag, statistik, status
from .behandlingstyper import TYPER
from .auth import Anvandare, Inloggning, krav_roll
from .insamling import InsamlingPagar, kor_insamling
from .recorded import InspeladTransport
from .robust import Robusthet
from .schema import SVERIGE, Schema
from .sources.base import Datakalla
from .sources.kolada import Kolada
from .sources.harnosand import ORGAN, Protokollkalla
from .sources.sammantradesplaner import Sammantradesplaner
from .sources.scb import Scb
from .sources.skr import SkrSkatteunderlag

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
        Kolada(nyckeltal=[*ekonomi.KOLADA, floden.INVANARE.split(":")[1]], kommun=KOMMUN,
               anrop_per_sekund=_anropsgrans("KOLADA", 5)),
        Scb(matt=_unika([*ekonomi.SCB, *floden.SCB_MATT]), differenser=[ekonomi.RORELSEKAPITAL], kommun=KOMMUN,
            anrop_per_sekund=_anropsgrans("SCB", 2)),
        SkrSkatteunderlag(anrop_per_sekund=_anropsgrans("SKR", 1)),
        *(Protokollkalla(organ, urval=int(os.environ.get("PROTOKOLL_URVAL") or 0),
                         anrop_per_sekund=_anropsgrans("PROTOKOLL", 1)) for organ in ORGAN),
        Sammantradesplaner(anrop_per_sekund=_anropsgrans("PROTOKOLL", 1)),
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
            resultat = serier.las_serie(conn, matt_id, omrade)
        if resultat is None:
            raise HTTPException(404, f"Måttet {matt_id} finns inte")
        return resultat

    @app.get("/api/ekonomi", dependencies=[Depends(krav_roll("lasare"))])
    def ekonomiska_nyckeltal(omrade: str = KOMMUN) -> dict:
        """Alla ekonomiska nyckeltal i katalogen, grupperade. Ett mått som inte samlats in än har serie null."""
        with db.connect(database_url) as conn:
            grupper = []
            for g in ekonomi.GRUPPER:
                nyckeltal = []
                for matt_id in g.matt:
                    s = serier.las_serie(conn, matt_id, omrade)
                    nyckeltal.append({
                        "id": matt_id,
                        "prisniva": ekonomi.prisniva(s["matt"]["enhet"]) if s else None,
                        "serie": s,
                    })
                grupper.append({"id": g.id, "titel": g.titel, "nyckeltal": nyckeltal})
        return {"omrade": omrade, "grupper": grupper}

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

    @app.get("/api/avvikelser", dependencies=[Depends(krav_roll("lasare"))])
    def protokollens_avvikelser(fran: int | None = None, till: int | None = None, organ: str | None = None) -> dict:
        """Sammanträden vars protokoll har avvikelser eller publicerade rättelser."""
        with db.connect(database_url) as conn:
            fran, till = intervall(conn, fran, till, organ)
            return avvikelser.lista(conn, fran, till, organ)

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
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt)$"),
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
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt)$"),
    ) -> list[dict]:
        return _budget(budgetforslag.lista, status)

    @app.get("/api/budgetforslag/{forslag_id}", dependencies=[Depends(krav_roll("redaktor", "utgivare"))])
    def las_budgetforslag(forslag_id: int) -> dict:
        return _budget(budgetforslag.las, forslag_id)

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
        status: str | None = Query(None, pattern="^(utkast|granskad|publicerad|ersatt)$"),
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
