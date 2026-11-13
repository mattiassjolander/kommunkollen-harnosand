"""Inloggning och roller: 401, 403, tillåtelselista och Google-flödet."""

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from conftest import GOOGLE_CLIENT_ID, skapa_app

SERIE = "/api/matt/kolada:N03007/serie"


def logga_in_med_google(api: TestClient, google, **claims) -> str:
    """Kör hela flödet: start → (Google) → callback. Returnerar vart callbacken skickar vidare."""
    start = api.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code == 302
    url = urlparse(start.headers["location"])
    assert url.netloc == "accounts.google.com"
    params = parse_qs(url.query)
    assert params["client_id"] == [GOOGLE_CLIENT_ID]
    assert params["redirect_uri"] == ["http://testserver/api/auth/google/callback"]
    google.nasta_id_token = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_CLIENT_ID,
        "email_verified": True,
        "name": "Anna Andersson",
        **claims,
    }
    svar = api.get(
        "/api/auth/google/callback",
        params={"code": "kod-fran-google", "state": params["state"][0]},
        follow_redirects=False,
    )
    assert svar.status_code == 302
    return svar.headers["location"]


def test_oinloggad_far_401(api):
    assert api.get(SERIE).status_code == 401
    assert api.post("/api/insamlingar").status_code == 401
    assert api.get("/api/auth/jag").status_code == 401


def test_halsa_och_inloggningsmetod_kraver_inte_inloggning(api):
    assert api.get("/api/halsa").status_code == 200
    assert api.get("/api/auth/metod").json() == {"google": True, "test": True, "anonym_lasning": False}


def test_lasare_kan_lasa_men_inte_starta_insamling(api, redaktor):
    redaktor.post("/api/insamlingar")
    redaktor.post("/api/auth/logga-ut")

    api.post("/api/auth/test/lasare")
    assert api.get(SERIE).status_code == 200
    assert api.post("/api/insamlingar").status_code == 403


def test_redaktor_kan_starta_insamling(redaktor):
    assert redaktor.post("/api/insamlingar").status_code == 200
    assert redaktor.get("/api/auth/jag").json()["roller"] == ["lasare", "redaktor"]


def test_utloggning_tar_bort_sessionen(redaktor):
    redaktor.post("/api/auth/logga-ut")
    assert redaktor.get("/api/auth/jag").status_code == 401


def test_google_inloggning_ger_roller_fran_tillatelselistan(api, google):
    assert logga_in_med_google(api, google, email="Anna@Example.se") == "/"
    jag = api.get("/api/auth/jag").json()
    assert jag == {"epost": "anna@example.se", "namn": "Anna Andersson", "roller": ["lasare", "redaktor", "utgivare"]}
    assert api.post("/api/insamlingar").status_code == 200

    # Token-anropet gick till Google med koden och samma redirect_uri.
    [anrop] = google.anrop
    form = parse_qs(anrop.content.decode())
    assert form["code"] == ["kod-fran-google"]
    assert form["redirect_uri"] == ["http://testserver/api/auth/google/callback"]


def test_konto_utanfor_tillatelselistan_nekas(api, google):
    assert logga_in_med_google(api, google, email="okand@example.se") == "/?fel=ej-behorig"
    assert api.get("/api/auth/jag").status_code == 401


def test_overifierad_epost_nekas(api, google):
    assert logga_in_med_google(api, google, email="anna@example.se", email_verified=False) == "/?fel=ej-behorig"
    assert api.get("/api/auth/jag").status_code == 401


def test_token_for_annan_klient_nekas(api, google):
    assert logga_in_med_google(api, google, email="anna@example.se", aud="nagon-annan") == "/?fel=inloggning-misslyckades"
    assert api.get("/api/auth/jag").status_code == 401


def test_callback_med_fel_state_nekas(api, google):
    api.get("/api/auth/google/start", follow_redirects=False)
    svar = api.get("/api/auth/google/callback", params={"code": "x", "state": "forfalskad"}, follow_redirects=False)
    assert svar.headers["location"] == "/?fel=inloggning-misslyckades"
    assert google.anrop == []


def test_andrad_tillatelselista_galler_direkt(database_url, google):
    forsta = TestClient(skapa_app(database_url, google))
    logga_in_med_google(forsta, google, email="bo@example.se")
    assert forsta.get(SERIE).status_code in (200, 404)  # läsare: släpps in

    # Samma session mot en app där Bo har tagits bort ur listan.
    andra = TestClient(skapa_app(database_url, google, anvandare={}))
    andra.cookies = forsta.cookies
    assert andra.get(SERIE).status_code == 401


def test_testinloggning_finns_inte_utan_testenv(database_url, google):
    api = TestClient(skapa_app(database_url, google, testenv=False))
    assert api.post("/api/auth/test/redaktor").status_code == 404
    assert api.get("/api/auth/metod").json()["test"] is False


def test_anonym_lasning_kan_slas_pa(database_url, google):
    api = TestClient(skapa_app(database_url, google, anonym_lasning=True))
    assert api.get(SERIE).status_code == 404  # släpps förbi inloggningen; måttet finns inte än
    assert api.post("/api/insamlingar").status_code == 401  # skrivning kräver fortfarande inloggning
