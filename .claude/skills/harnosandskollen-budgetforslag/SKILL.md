---
name: harnosandskollen-budgetforslag
description: Läser in partiernas budgetförslag och planförutsättningarna per budgetår i Kommunkollen. Använd när användaren ger ett budgetförslag (PDF eller Word) eller planförutsättningar som ska tolkas, kontrolleras och läsas in som utkast, lokalt eller på servern.
---

# Budgetförslag och planförutsättningar

Skillen har två grenar som slutar likadant:

- **Planförutsättningar** för ett budgetår: en flik i Excelfilen. Gör dem före förslagen, eftersom förslagen räknas mot dem.
- **Budgetförslag**: ett partis förslag som tolkas till `budget.json`.

Båda kontrolleras med `kontroll.py`, läses in lokalt och, efter användarens ja, på servern. Det som läses in blir **utkast**. En utgivare som inte läst in uppgifterna granskar och publicerar dem (utkast → granskad → publicerad, ADR-0002). Claude läser in och lämnar granskningen och publiceringen till utgivaren.

Filformatet (fälten i `budget.json`, kolumnerna i Excelfilen, åtgärder, summering och behandling) står i `docs/budgetforslag.md`. Läs den innan du skriver något. Begreppen är de i `GLOSSARY.md`, avsnitt Budget.

## 1. Lägg filerna på plats

Allt ligger i `data/budgetforslag/` i huvudmappen för repot. Mappen versionshanteras inte och finns därför inte i en worktree, så använd sökvägen till huvudmappen.

- `planforutsattningar.xlsx`: en flik per budgetår, och fliken heter året. Bara den här filen läses. Andra Excelfiler bredvid, till exempel `planforutsattningar 2027.xlsx`, är underlag.
- `<budgetår>/<partier>.pdf` (eller `.docx`) och `<budgetår>/budget.json`. Budgetåret är året budgeten gäller, inte året förslaget lades fram. Filnamnet är partiförkortningarna i alfabetisk ordning (`L+M.pdf`). Majoritetens förslag heter `majoritet.pdf` och är årsplanen. Det namnet behålls.

Kopiera originalet från användaren till rätt namn och lämna innehållet orört. Det lagras som källa och visas för läsaren.

Klart när filen ligger under rätt budgetår med rätt namn.

## 2. Tolka dokumentet

Läs hela dokumentet, sida för sida. En inskannad sida läses som bild. Varje värde får en **källa**: förslaget och sidan, till exempel "M s. 4". Sidan är sidan i PDF:en räknat från 1, inte det tryckta sidnumret. Ett Word-dokument har inga fasta sidor och får ingen sida.

Skriv det som står i dokumentet, i den form det står:

| Uppgift | Så skrivs den |
|---|---|
| Ram per organ | `mnkr` för budgetåret. Anger förslaget också förändringen mot planförutsättningarna, skriv båda: `mnkr` lagras och `forandring` används i kontrollen av versionen. Står bara förändringen, skriv bara `forandring`. Organen heter som i planförutsättningarna. |
| Skattesats | Som förslaget anger den: `ore`, `forandring` i procentenheter eller `procent`. Utelämnas om förslaget inte nämner den. |
| Budgeterat resultat | `procent` och, om förslaget anger det, `mnkr`. Procenten lagras och beloppet kontrolleras mot den. |
| Åtgärder | `atgarder` för varje nämnd som förslaget tar upp, också en oförändrad: besparingar med negativt och satsningar med positivt belopp, utan belopp när förslaget inte anger något. Anger förslaget inga åtgärder för nämnden, skriv `"atgarder": []`. Utan fältet visas "Åtgärderna är inte avlästa". |
| Summering, behandling | Enligt `docs/budgetforslag.md`. Texten ligger nära originalet och värderar inte. |

Bara budgetåret läses. Planåren tas inte med. Ett värde som inte står i dokumentet utelämnas och nämns i rapporten till användaren. Det räknas aldrig fram eller uppskattas. Är en siffra svårläst, till exempel på en inskannad sida, fråga användaren.

I planförutsättningarna har varje rad sin källa i kolumn D, i samma form ("L s. 8", flera skiljs med komma).

För varje förslag finns nu en post i `budget.json` och en **källförteckning** i rapporten: varje värde med sin källa. Nya poster skrivs i formatet ovan. Befintliga poster i det tidigare formatet med planår (`"ar": 2027`) läses som de är.

Klart när varje siffra i ramtabellen, skattesatsen och resultatet för budgetåret har en post med källa, eller står i rapporten som saknad, och varje ram har `atgarder`.

## 3. Kontrollera

Kör från repots rot, med sökvägen till datamappen i huvudmappen:

```bash
uv run --directory backend python ../.claude/skills/harnosandskollen-budgetforslag/kontroll.py ../data/budgetforslag --ar 2027
```

Skriptet läser mappen som inläsningen gör, utan databas. Stoppar inläsningen på något, till exempel ett okänt fält, en sida som saknas eller ett organ som inte finns, skriver skriptet felet med fil och avbryter. Annars skriver det kontrollerna och märker det som behöver åtgärdas med **AVVIKER**:

1. **Kontrollsummor** i planförutsättningarna: summan av posterna mot det angivna beloppet. Avrundningen ger några tiondelar, mer än 0,3 mnkr avviker.
2. **Budgeterat mot beräknat resultat**: förslagets resultat i mnkr mot planförutsättningarnas resultat − förändringarna + skatteintäkternas förändring. En skillnad på 2 mnkr eller mer avviker. Den betyder att förslaget saknar finansiering för skillnaden eller inte redovisar den.
3. **Samma version av planförutsättningarna**: för en ram med både mnkr och förändring jämförs ram − förändring med den gemensamma planförutsättningen. Förändringen är förslagets eget beslut och ramen är avrundad till hela mnkr, så mer än 0,5 mnkr avviker. Det fångar både ett förslag som räknat från en annan version och en rad som inte går ihop i förslagets egen tabell (C 2027: plan 187 − 3 men ram 185, s. 4). Har förslaget en egen kolumn med planförutsättningarna, gå igenom den rad för rad: plan + förändring ska bli ramen, och planen ska vara den gemensamma avrundad. Jämför också andra planförutsättningar som förslaget redovisar, till exempel skatteintäkterna. Använder flera förslag samma andra version, säg det till användaren: den version som flest förslag använder gäller (#58, beslut 1), och kanske är det fliken som ska rättas.
4. **Resultatet i procent mot mnkr**, när förslaget anger båda: mer än 0,1 procentenheter avviker.
5. **Organ utanför planförutsättningarna**: ett organ som inte finns där är oftast ett felstavat namn.
6. **Åtgärderna**: en ram utan `atgarder` avviker. Summan av åtgärderna står mot förändringen. En stor skillnad betyder ofta ett tecken som blivit fel eller en åtgärd som hör till en annan nämnd.

Kör om efter varje rättelse.

Klart när varje AVVIKER har en förklaring: ett läsfel som har rättats i filen, eller en avvikelse i förslaget som har blivit en anmärkning (steg 4).

## 4. Skriv anmärkningar

Ett läsfel rättas i filen. En avvikelse i själva förslaget blir en anmärkning, så att läsaren ser den:

- **Budgetförslag**: fältet `anmarkning` i förslagets post.
- **Planförutsättningar**: en rad under rubriken "Avvikelser och anmärkningar" längst ner i fliken. Raden läses inte in.

En anmärkning säger vad förslaget anger och vad beräkningen ger, med belopp och sida, och värderar inte förslaget eftersom plattformen är partipolitiskt obunden. Ett förslag som ändrar investeringar, balans eller kassaflöde får också en anmärkning (#58, beslut 5). Förebilden är L 2027 i `data/budgetforslag/2027/budget.json`: "Resultatbudgeten räknar med 30 mnkr i lägre kostnader som läggs på resultatet (50 till 80 mnkr), men ramarna per nämnd minskar bara 10 mnkr netto […] så cirka 20 mnkr av resultatet saknar finansiering (sidan 8)."

## 5. Läs in lokalt

Starta utvecklingsservern med inläsningen. Uppgifterna läses in som `import@kommunkollen.test`, och sedan startar API:t på `http://127.0.0.1:8000`:

```bash
uv run --directory backend kommunkollen-dev --budgetforslag ../data/budgetforslag
```

Raden "N budgetförslag: … nya utkast, … uppdaterade, … oförändrade." visar vad som hände. Hela inläsningen görs i en transaktion, så ett fel avbryter allt. Med `--databas <mapp>` används en annan inbäddad databas än `backend/.dev-db`, till exempel en mapp i scratchpaden för ett prov.

Logga in som redaktör med testinloggningen och kontrollera utkasten:

```bash
curl -c .kaka -X POST http://127.0.0.1:8000/api/auth/test/redaktor
curl -b .kaka "http://127.0.0.1:8000/api/budgetforslag?status=utkast"
curl -b .kaka "http://127.0.0.1:8000/api/planforutsattningar?status=utkast"
```

Utkastets `berakning` ska ge samma förändringar, beräknat resultat och skillnad som `kontroll.py`. I webben finns utkasten under Politik och beslut → Budgetutkast.

## 6. Läs in på servern

Gör det bara när användaren uttryckligen har sagt ja till just den här inläsningen. Fråga efter redaktörens e-post: den som läser in räknas som redaktör och kan inte själv granska eller publicera. Kommandot skickar hela mappen. Det som inte har ändrats blir oförändrat.

```bash
tar -C data -c budgetforslag | ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.budgetforslag - --redaktor EPOST'
```

## Rapporten till användaren

Avsluta med:

- källförteckningen per förslag,
- kontrollerna med det som avvek och hur det förklarades,
- anmärkningarna som skrevs,
- vad inläsningen gav lokalt och, om den kördes, på servern,
- att en utgivare som inte läst in uppgifterna nu granskar och publicerar dem under Budgetutkast.
