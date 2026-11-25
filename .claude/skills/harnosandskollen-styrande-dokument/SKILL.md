---
name: harnosandskollen-styrande-dokument
description: Analyserar kommunens reglementen och delegationsordningar i Kommunkollen. Söker motstridigheter (motsägelser, felaktiga hänvisningar och flera gällande versioner) och fyller i stegen i redaktionens processer (vem, vad, när och källa), och läser in dem som utkast, lokalt eller på servern. Använd när användaren vill analysera de styrande dokumenten, leta motstridigheter i dem eller ta fram processer ur dem.
---

# Motstridigheter och processer i styrande dokument

Skillen har två grenar. Den läser kommunens reglementen och delegationsordningar tillsammans och föreslår **motstridigheter** (#151), eller fyller i stegen i redaktionens **processer** (#152, avsnittet *Processer* nedan). Motstridigheter: motsägelser, felaktiga hänvisningar och flera gällande versioner. Förslagen skrivs till en fil, kontrolleras och läses in som **utkast**. En utgivare som inte läst in dem granskar och publicerar dem (utkast → granskad → publicerad, ADR-0002). Claude läser in och lämnar granskningen till utgivaren.

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

# Processer

Grenen för processer (#152) fyller i stegen i de processer som redaktionen har valt att beskriva. Hitta inte på egna processer och gruppera inte om dem: listan bestäms av redaktionen. Saknas en process som användaren vill ha, be en redaktör lägga till den under Redaktion → Processer först. Formatet och kontrollerna står i `docs/styrande-dokument.md`, avsnittet *Processer*.

## P1. Hämta listan och underlaget

Underlaget är detsamma som för motstridigheterna (steg 1 ovan). Hämta redaktionens lista. Den kräver inloggning som redaktör, så läs den från databasen på servern. Det är bara läsning:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose exec -T db psql -U kommunkollen -Atc \"SELECT namn, status FROM process WHERE status <> 'avvisad' ORDER BY ordning\""
```

Användaren kan också ge processerna som ska fyllas i.

Klart när du har listan och alla dokument i omfånget ligger i `underlag/`.

## P2. Läs dokumenten för varje process

Läs alla 25 dokumenten med processen i tankarna. Stegen kan hämtas ur flera dokument. Budgetprocessen kan till exempel ta steg ur *Reglemente för ekonomistyrning*, *Reglemente för god ekonomisk hushållning* och *Kommunfullmäktiges arbetsordning*.

För varje steg, notera:

- **vem** som gör något: ett organ, ordföranden, förvaltningen eller en ledamot, så som dokumentet anger det,
- **vad** som görs, kort och sakligt,
- **när** eller inom vilken tidsfrist, bara om dokumentet anger det,
- **källan**: dokumentets `sitevision_id`, sidan i PDF:en, paragrafen (eller punkten eller avsnittets rubrik om dokumentet saknar paragrafer) och ett ordagrant citat.

Ordna stegen så som arbetsgången går. Ett steg bygger på ett ställe. Säger två dokument olika saker om samma steg, ta med båda stegen och nämn det i rapporten: det kan vara en motstridighet.

Kontrollera alltid kallelsen och justeringen i det gemensamma reglementet för kommunstyrelse och nämnder: kallelsen ska skickas senast fem dagar före sammanträdesdagen (§ 13) och protokollet justeras senast 14 dagar efter sammanträdet (§ 26). De ska komma med som steg.

Klart när varje process på listan har sina steg med källa, eller du kan säga varför en process saknar steg i dokumenten.

## P3. Skriv filen

Skriv `data/styrande-dokument/processer.json` enligt `docs/styrande-dokument.md`. Namnet på processen skrivs som på listan. Citaten är ordagranna och så korta som möjligt men entydiga. `vem` och `vad` återger vad dokumenten säger och värderar inte, och inga personer namnges.

Stegen för en process ersätter de tidigare stegen och blir ett nytt utkast. Ta därför bara med de processer som ska läsas in. En publicerad process läses inte in med andra steg: den måste återkallas av en utgivare först. Fråga användaren innan du föreslår det.

## P4. Kontrollera

```bash
ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.processer - --redaktor EPOST --prova' < data/styrande-dokument/processer.json
```

Ett fel anger processens och stegets nummer. Rätta filen och prova igen. Lokalt fungerar `uv run --directory backend python -m app.processer`.

Klart när provet går igenom och anger antalet processer med nya steg.

## P5. Läs in på servern

Bara när användaren uttryckligen har sagt ja till just den här inläsningen. Den som läser in räknas som redaktör för processen och kan inte själv granska eller publicera den.

```bash
ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.processer - --redaktor EPOST' < data/styrande-dokument/processer.json
```

## Rapporten för processer

Avsluta med processerna och antalet steg i var och en med dokument och paragraf, vad du var osäker på, vad provet och inläsningen gav, och att en utgivare som varken lade till processen eller läste in stegen nu granskar och publicerar den under Redaktion → Processer.
