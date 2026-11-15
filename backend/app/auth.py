"""Inloggning och roller.

- Google-inloggning (OpenID Connect, authorization code flow). Avstängd utan GOOGLE_CLIENT_ID.
- En tillåtelselista (AUTH_ANVANDARE) anger vilka Google-konton som släpps in och deras roller.
- Testinloggning (TESTENV=true) för utveckling och e2e. Finns inte alls annars.
- Läsning är öppen för alla som standard. ANONYM_LASNING=false stänger den bakom inloggning.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

ROLLER = ("lasare", "redaktor", "utgivare")

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_UTFARDARE = {"https://accounts.google.com", "accounts.google.com"}
TESTDOMAN = "@kommunkollen.test"


@dataclass(frozen=True)
class Inloggning:
    google_client_id: str = ""
    google_client_secret: str = ""
    # e-post (gemener) -> roller
    anvandare: dict[str, frozenset[str]] = field(default_factory=dict)
    testenv: bool = False
    anonym_lasning: bool = False
    publik_url: str = ""  # t.ex. https://kommunkollen.example; tomt = härleds från förfrågan

    @property
    def google_aktiv(self) -> bool:
        return bool(self.google_client_id)

    @classmethod
    def fran_miljo(cls) -> Inloggning:
        return cls(
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            anvandare=las_anvandare(os.environ.get("AUTH_ANVANDARE", "")),
            testenv=os.environ.get("TESTENV", "false").lower() == "true",
            anonym_lasning=os.environ.get("ANONYM_LASNING", "true").lower() == "true",
            publik_url=os.environ.get("PUBLIK_URL", "").rstrip("/"),
        )


def las_anvandare(text: str) -> dict[str, frozenset[str]]:
    """Läser tillåtelselistan.

    Format: "epost=roll+roll; epost=roll", t.ex.
    "anna@example.se=redaktor+utgivare; bo@example.se=lasare".
    Redaktör och utgivare får alltid också läsa.
    """
    resultat: dict[str, frozenset[str]] = {}
    for post in filter(None, (p.strip() for p in text.split(";"))):
        epost, _, roller = post.partition("=")
        rollmangd = {r.strip() for r in roller.split("+") if r.strip()} or {"lasare"}
        okanda = rollmangd - set(ROLLER)
        if okanda:
            raise ValueError(f"Okänd roll i AUTH_ANVANDARE för {epost.strip()}: {', '.join(sorted(okanda))}")
        resultat[epost.strip().lower()] = frozenset(rollmangd | {"lasare"})
    return resultat


@dataclass(frozen=True)
class Anvandare:
    epost: str
    namn: str
    roller: frozenset[str]


def _anvandare(request: Request) -> Anvandare | None:
    data = request.session.get("anvandare")
    if not data:
        return None
    return Anvandare(epost=data["epost"], namn=data["namn"], roller=frozenset(data["roller"]))


def krav_roll(roll: str, *andra: str):
    """Dependency: kräver inloggning med `roll` (eller någon av `andra`). Läsning kan öppnas med ANONYM_LASNING."""

    def kontroll(request: Request) -> Anvandare | None:
        inst: Inloggning = request.app.state.inloggning
        anv = _anvandare(request)
        if roll == "lasare" and inst.anonym_lasning:
            return anv
        if anv is None:
            raise HTTPException(401, "Inloggning krävs")
        # Rollerna läses om från tillåtelselistan, så en ändrad lista gäller direkt.
        # Testanvändare (bara med TESTENV) finns inte i listan och behåller sina roller.
        testanvandare = inst.testenv and anv.epost.endswith(TESTDOMAN)
        if not testanvandare:
            aktuella = inst.anvandare.get(anv.epost)
            if aktuella is None:
                request.session.clear()
                raise HTTPException(401, "Kontot har inte längre åtkomst")
            anv = Anvandare(anv.epost, anv.namn, aktuella)
        if not anv.roller & {roll, *andra}:
            raise HTTPException(403, f"Kräver rollen {' eller '.join((roll, *andra))}")
        return anv

    return kontroll


def _jwt_innehall(token: str) -> dict:
    # id_token kommer direkt från Googles token-endpoint över TLS, så signaturen behöver
    # inte verifieras här (OpenID Connect Core 3.1.3.7). Utfärdare och mottagare kontrolleras.
    del_ = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(del_ + "=" * (-len(del_) % 4)))


def router(http_klient) -> APIRouter:
    r = APIRouter(prefix="/api/auth")

    def redirect_uri(request: Request) -> str:
        inst: Inloggning = request.app.state.inloggning
        bas = inst.publik_url or str(request.base_url).rstrip("/")
        return f"{bas}/api/auth/google/callback"

    @r.get("/metod")
    def metod(request: Request) -> dict:
        inst: Inloggning = request.app.state.inloggning
        return {"google": inst.google_aktiv, "test": inst.testenv, "anonym_lasning": inst.anonym_lasning}

    @r.get("/jag")
    def jag(anv: Anvandare = Depends(krav_roll("lasare"))) -> dict:
        if anv is None:
            raise HTTPException(401, "Inte inloggad")
        return {"epost": anv.epost, "namn": anv.namn, "roller": sorted(anv.roller)}

    @r.post("/logga-ut")
    def logga_ut(request: Request) -> dict:
        request.session.clear()
        return {"ok": True}

    @r.get("/google/start")
    def google_start(request: Request) -> RedirectResponse:
        inst: Inloggning = request.app.state.inloggning
        if not inst.google_aktiv:
            raise HTTPException(404, "Google-inloggning är inte konfigurerad")
        state = secrets.token_urlsafe(24)
        request.session["oauth_state"] = state
        params = {
            "client_id": inst.google_client_id,
            "redirect_uri": redirect_uri(request),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return RedirectResponse(f"{GOOGLE_AUTH}?{urlencode(params)}", status_code=302)

    @r.get("/google/callback")
    def google_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
        inst: Inloggning = request.app.state.inloggning
        forvantad = request.session.pop("oauth_state", None)
        if error or not code or not forvantad or not secrets.compare_digest(state, forvantad):
            return RedirectResponse("/?fel=inloggning-misslyckades", status_code=302)
        with http_klient() as client:
            svar = client.post(
                GOOGLE_TOKEN,
                data={
                    "code": code,
                    "client_id": inst.google_client_id,
                    "client_secret": inst.google_client_secret,
                    "redirect_uri": redirect_uri(request),
                    "grant_type": "authorization_code",
                },
            )
        if svar.status_code != 200:
            return RedirectResponse("/?fel=inloggning-misslyckades", status_code=302)
        claims = _jwt_innehall(svar.json()["id_token"])
        if claims.get("iss") not in GOOGLE_UTFARDARE or claims.get("aud") != inst.google_client_id:
            return RedirectResponse("/?fel=inloggning-misslyckades", status_code=302)
        epost = str(claims.get("email", "")).lower()
        roller = inst.anvandare.get(epost)
        if not claims.get("email_verified") or roller is None:
            return RedirectResponse("/?fel=ej-behorig", status_code=302)
        request.session["anvandare"] = {"epost": epost, "namn": claims.get("name") or epost, "roller": sorted(roller)}
        return RedirectResponse("/", status_code=302)

    @r.post("/test/{roll}")
    def testinloggning(roll: str, request: Request) -> dict:
        inst: Inloggning = request.app.state.inloggning
        if not inst.testenv:
            raise HTTPException(404)
        valda = set(roll.split("+"))
        if not valda <= set(ROLLER):
            raise HTTPException(400, "Okänd roll")
        roller = sorted({"lasare", *valda})
        request.session["anvandare"] = {"epost": f"test-{roll}{TESTDOMAN}", "namn": f"Test ({roll})", "roller": roller}
        return {"ok": True, "roller": roller}

    return r
