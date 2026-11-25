# Kommunkollen Härnösand

Insyn i hur kommunpolitiken i Härnösand bedrivs.

Projektet samlar in protokoll, handlingar och annan offentlig data från Härnösands kommun, analyserar den och presenterar resultatet på en webbplats där man kan navigera mellan ärenden, organ, beslut och ledamöter.

- Kravspecifikation: [docs/kravspec.md](docs/kravspec.md)
- Begrepp: [GLOSSARY.md](GLOSSARY.md)
- Arkitekturbeslut: [docs/adr/](docs/adr/)
- Grafisk profil: [docs/design.md](docs/design.md)
- Drift: [docs/drift.md](docs/drift.md)

## Struktur

```
backend/    Python 3.12 + FastAPI + Postgres (uv). Insamling och API.
frontend/   Vue 3 + TypeScript + Vite. Playwright för e2e.
```

## Kom igång

Kräver [uv](https://docs.astral.sh/uv/) och Node 24. Docker eller en installerad Postgres behövs inte: utan `DATABASE_URL` startar backend en inbäddad Postgres (pgserver) i `backend/.dev-db`.

```bash
npm install && npm --prefix frontend install
```

```bash
npm run dev
```

Det startar API:t på `http://127.0.0.1:8000` och webben på `http://localhost:5173`, med testinloggning påslagen. Databasen är tom tills en insamling har körts, vilket kräver en inloggad redaktör:

```bash
curl -c .kaka -X POST http://127.0.0.1:8000/api/auth/test/redaktor && curl -b .kaka -X POST http://127.0.0.1:8000/api/insamlingar
```

Vill du köra mot inspelade källsvar i stället för nätet:

```bash
uv run --directory backend kommunkollen-dev --inspelningar tests/recordings
```

## Tester

```bash
npm test
```

- **Söm 1** (`backend/tests`): HTTP-API:t mot riktig Postgres, med externa källor utbytta mot inspelade svar i `backend/tests/recordings`. Använder `TEST_DATABASE_URL` om den är satt, annars inbäddad Postgres.
- **Söm 2** (`frontend/e2e`): Playwright mot riktig backend som hämtar från inspelningarna. Första gången: `npx --prefix frontend playwright install chromium`.

Inspelningarna uppdateras från de riktiga källorna (Kolada, SCB, SKR och protokollen på harnosand.se) med:

```bash
PROTOKOLL_URVAL=2 STYRANDE_URVAL=1 uv run --directory backend python -m app.spela_in tests/recordings
```

`PROTOKOLL_URVAL=2` begränsar protokollen till två per sida och årsmapp, vilket är vad testerna förväntar sig. Utan det hämtas alla protokoll sedan 2022 (cirka 200 MB). `STYRANDE_URVAL=1` begränsar kommunens styrande dokument till ett per rubrik. Utan det hämtas alla 138 (cirka 190 MB). Ange källans id för att bara spela in en källa, t.ex. `... tests/recordings harnosand-protokoll-kf`. Testerna av protokollen har förväntade värden som är kontrollerade för hand, så de behöver ses över när protokollen spelas in på nytt.

Hur protokollen hämtas och tolkas står i [docs/protokoll.md](docs/protokoll.md).

Ledamotsregistret, partiet över tid och hur en redaktör slår ihop namn står i [docs/ledamoter.md](docs/ledamoter.md).

Vilka ekonomiska nyckeltal som hämtas, och hur de täcker kravspecen, står i [docs/tackning-ekonomi.md](docs/tackning-ekonomi.md).

Hur SKR:s skatteunderlagsprognos hämtas och räknas om för Härnösand står i [docs/skatteunderlag.md](docs/skatteunderlag.md). Omräkningen kräver LibreOffice (`soffice`).

## Konfiguration

| Variabel | Vad |
| --- | --- |
| `DATABASE_URL` | Postgres-anslutning. Utelämnad i utveckling = inbäddad Postgres. |
| `INSPELNINGAR` | Katalog med inspelade källsvar (bara för test och utveckling). |
| `INSAMLING_DAGAR` | Dagar i månaden då insamlingen körs automatiskt, t.ex. `1,15` (standard). Tomt stänger av schemat. |
| `INSAMLING_KLOCKAN` | Klockslag för den automatiska insamlingen, svensk tid (standard `03:00`). |
| `KOLADA_ANROP_PER_SEKUND`, `SCB_ANROP_PER_SEKUND`, `SKR_ANROP_PER_SEKUND`, `PROTOKOLL_ANROP_PER_SEKUND` | Högsta anropsfrekvens mot källan (standard 5, 2, 1 respektive 1). `0` tar bort gränsen. |
| `SOFFICE` | Sökväg till LibreOffice `soffice` om den inte finns i `PATH`. |
| `PROTOKOLL_URVAL` | Högst så många protokoll per organsida och årsmapp. Bara för inspelningar och test, sätts inte i drift. |
| `STYRANDE_URVAL` | Högst så många styrande dokument per rubrik på kommunens sida. Bara för inspelningar och test, sätts inte i drift. |
| `SESSION_SECRET` | Hemlighet för sessionskakan. Krävs på servern. Saknas den blir alla utloggade vid omstart. |
| `SESSION_HTTPS_ONLY` | `true` när appen nås via https. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google-inloggning. Utan klient-id är den avstängd. |
| `AUTH_ANVANDARE` | Tillåtelselistan: `epost=roll+roll; epost=roll`. Roller: `lasare`, `redaktor`, `utgivare`. |
| `PUBLIK_URL` | Adressen användarna når appen på, om den skiljer sig från förfrågans (styr Googles redirect-adress). |
| `ANONYM_LASNING` | Standard `true`: läsning är öppen utan inloggning. `false` stänger läsning bakom inloggning. Skrivning kräver alltid inloggning. |
| `TESTENV` | `true` ger testinloggning utan lösenord. På som standard i `npm run dev`, aldrig på en publik server. |

## Inloggning

Läsning är öppen för alla. Inloggning krävs för att skriva, till exempel starta insamling, och bara Google-konton i `AUTH_ANVANDARE` släpps in. Listan läses vid varje förfrågan efter omstart, så en borttagen person loggas ut direkt.

| Roll | Får |
| --- | --- |
| `lasare` | läsa alla vyer (behövs bara om läsning stängs med `ANONYM_LASNING=false`) |
| `redaktor` | läsa, starta insamling och (senare) registrera uppgifter |
| `utgivare` | läsa och (senare) godkänna registreringar för publicering |

Så skapas Google-klienten:

1. I [Google Cloud Console](https://console.cloud.google.com/apis/credentials): skapa ett projekt och konfigurera OAuth-samtyckesskärmen (Extern, testläge räcker; lägg till kontona som testanvändare).
2. Skapa ett OAuth-klient-id av typen *Webbapplikation*.
3. Lägg till den auktoriserade omdirigerings-URI:n där appen nås, följt av `/api/auth/google/callback`, till exempel:
   - `http://localhost:5173/api/auth/google/callback` (`npm run dev`)
   - `http://localhost:8080/api/auth/google/callback` (servern via SSH-tunnel, se [docs/drift.md](docs/drift.md))

   Google tillåter bara `localhost` eller https, inte en lokal IP-adress som `http://192.168.1.11`.
4. Lägg in id, hemlighet och tillåtelselistan i `.env`.
