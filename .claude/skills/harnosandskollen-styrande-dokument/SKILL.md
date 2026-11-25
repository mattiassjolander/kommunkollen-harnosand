---
name: harnosandskollen-styrande-dokument
description: Söker motstridigheter i kommunens reglementen och delegationsordningar i Kommunkollen (motsägelser, felaktiga hänvisningar och flera gällande versioner) och läser in dem som utkast, lokalt eller på servern. Använd när användaren vill analysera de styrande dokumenten eller leta motstridigheter i dem.
---

# Motstridigheter i styrande dokument

Skillen läser kommunens reglementen och delegationsordningar tillsammans och föreslår **motstridigheter** (#151): motsägelser, felaktiga hänvisningar och flera gällande versioner. Förslagen skrivs till en fil, kontrolleras och läses in som **utkast**. En utgivare som inte läst in dem granskar och publicerar dem (utkast → granskad → publicerad, ADR-0002). Claude läser in och lämnar granskningen till utgivaren.

Typerna, filformatet och kontrollerna står i `docs/styrande-dokument.md`. Begreppen är de i `GLOSSARY.md`, avsnitt *Styrande dokument*. Läs båda innan du skriver något.

## 1. Hämta underlaget

Omfånget är dokumenten under rubrikerna *Reglementen, ägardirektiv och bolagsordning* och *Delegationer*, utom delegationsordningen för Överförmyndarnämnden: 25 dokument när skillen skrevs. Sök inte motstridigheter mot andra dokument.

Allt läggs i `data/styrande-dokument/` i huvudmappen för repot. Mappen versionshanteras inte och finns därför inte i en worktree, så använd sökvägen till huvudmappen. Hämta listan och plattformens kopior från servern. Det är bara läsning:

```bash
ssh kommunkollen "curl -s http://localhost/api/styrande-dokument" > data/styrande-dokument/lista.json
ssh kommunkollen "curl -s http://localhost/api/styrande-dokument/ID/versioner/VERSION" > data/styrande-dokument/underlag/ID.pdf
```

Versionen är den första i dokumentets `versioner` (`/api/styrande-dokument/ID`). Varje dokument har `sitevision_id` (`18.…`), som är det id som filen hänvisar till.

Klart när alla dokument i omfånget ligger i `underlag/`, och du har en förteckning med titel, `sitevision_id` och antal sidor.

## 2. Läs dokumenten

Läs varje dokument helt, sida för sida. En inskannad sida läses som bild. Sidan är sidan i PDF:en räknat från 1, inte det tryckta sidnumret.

Leta efter:

- **Felaktiga hänvisningar:** hänvisningar till kapitel, paragrafer, organ, bilagor eller dokument. Kontrollera var och en mot det som finns: innehållsförteckningen, rubrikerna, organen i reglementena och dokumenten i förteckningen. Exempel: det gemensamma reglementet hänvisar till "kapitel 2 till 9", och innehållsförteckningen har kapitel 1–8.
- **Motsägelser:** samma sak reglerad olika, i samma dokument eller i olika. Jämför särskilt tidsfrister, beloppsgränser, vem som beslutar och vem som får delegation. Två bestämmelser som gäller olika saker är ingen motsägelse.
- **Flera gällande versioner:** samma dokument eller sak som ligger ute flera gånger som gällande, till exempel en konsoliderad version bredvid den aktuella, eller ett utkast bredvid den antagna versionen.

En utgången giltighet är ingen motstridighet. Den syns redan som giltigheten.

Insamlingen föreslår själv flera gällande versioner med samma diarienummer eller titlar som bara skiljer sig i skiljetecken eller årtal. De behöver inte föreslås igen. Gör de det läses de inte in två gånger.

Klart när varje dokument är läst och varje fynd har ställena med sida, och paragraf för en motsägelse.

## 3. Skriv filen

Skriv `data/styrande-dokument/motstridigheter.json` enligt `docs/styrande-dokument.md`.

- Citaten är ordagranna från sidan, så korta som möjligt men entydiga. Inläsningen kontrollerar att de står på sidan.
- Förklaringen följer mallen för typen och är högst två meningar. Den återger vad dokumenten säger och värderar inte. Orden *fel*, *brist*, *slarv* och *motsäger sig själv* används inte, och inga personer namnges, inte heller dokumentansvariga. Plattformen är partipolitiskt obunden.
- En felaktig hänvisning har en uppgift med källa om det som finns, till exempel "Reglementet har kapitel 1–8." med innehållsförteckningens sida.

Är du osäker på om något är en motstridighet, ta med det och säg det i rapporten. Utgivaren avgör i granskningen.

Klart när filen har ett förslag per fynd.

## 4. Kontrollera

Prova filen mot servern utan att spara. Kommandot läser filen, gör alla kontroller och rullar tillbaka:

```bash
ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.motstridigheter - --redaktor EPOST --prova' < data/styrande-dokument/motstridigheter.json
```

Ett fel anger förslagets nummer, till exempel "Motstridighet 3, citat 2: citatet står inte ordagrant på sidan 4". Rätta filen och prova igen. Lokalt fungerar samma kommando med `uv run --directory backend python -m app.motstridigheter`, om den lokala databasen har dokumenten.

Klart när provet går igenom och anger antalet nya utkast.

## 5. Läs in på servern

Gör det bara när användaren uttryckligen har sagt ja till just den här inläsningen. Fråga efter redaktörens e-post: den som läser in räknas som redaktör och kan inte själv granska eller publicera.

```bash
ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.motstridigheter - --redaktor EPOST' < data/styrande-dokument/motstridigheter.json
```

## Rapporten till användaren

Avsluta med:

- dokumenten som lästes, med antal sidor,
- förslagen per typ med dokument och sida,
- det du var osäker på,
- vad provet och inläsningen gav,
- att en utgivare som inte läst in förslagen nu granskar och publicerar dem under Redaktion → Motstridigheter.
