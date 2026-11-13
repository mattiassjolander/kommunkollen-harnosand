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

Det startar API:t på `http://127.0.0.1:8000` och webben på `http://localhost:5173`. Databasen är tom tills en insamling har körts:

```bash
curl -X POST http://127.0.0.1:8000/api/insamlingar
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

## Konfiguration

| Variabel | Vad |
| --- | --- |
| `DATABASE_URL` | Postgres-anslutning. Utelämnad i utveckling = inbäddad Postgres. |
| `KOLADA_NYCKELTAL` | Kommaseparerade Kolada-nyckeltal att hämta (standard `N03007`). |
| `INSPELNINGAR` | Katalog med inspelade källsvar (bara för test och utveckling). |
