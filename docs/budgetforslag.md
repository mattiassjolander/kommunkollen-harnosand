# Partiernas budgetförslag

Partiernas budgetförslag till kommunfullmäktige läses in i en gemensam budgetmodell för budgetåret (kravspec 17A, #48, #58). Alla förslag för ett budgetår utgår från samma **planförutsättningar**. Ett förslag anger bara sina politiska prioriteringar: ram per nämnd, en ändrad skattesats och sitt budgeterade resultat. Läsaren jämför förslagen med varandra, med planförutsättningarna och med den antagna budgeten.

## Filerna

Förslagen läggs i `data/budgetforslag/<budgetår>/`, som inte versionshanteras. Budgetåret är året budgeten gäller, inte året förslaget lades fram. Planförutsättningarna ligger i `data/budgetforslag/planforutsattningar.xlsx`.

- Filnamnet är partiförkortningarna bakom förslaget i alfabetisk ordning: `C.pdf`, `L+M.pdf`, `KD+MP+S+V.docx`.
- Ett förslag till tilläggsbudget eller reviderad budget får ett eget namn, till exempel `S-tillagg.pdf`.
- Majoritetens förslag heter `majoritet.pdf` från 2023. Det är kommunens årsplan: majoriteten lägger fram den och fullmäktige antar den. Partierna anges då i `budget.json`. Den behandlas som övriga förslag.
- Filerna är PDF eller Word (`.docx`) och ligger kvar i originalformatet som källa.

## planforutsattningar.xlsx

En flik per budgetår, och fliken heter året (`2027`). Andra flikar, till exempel en översikt, läses inte. Kolumnerna är:

| Kolumn | Innehåll |
|---|---|
| A | Tabell: `Resultatbudget`, `Nämnder`, `Investeringar`, `Balansbudget` eller `Kassaflöde` |
| B | Post, till exempel `Skatteintäkter` eller `Skolnämnden` |
| C | Belopp i mnkr |
| D | Källa: förslag och sida, till exempel `L s. 8` eller `C s. 3, M s. 7` |

Rubrikrader, rader med formler (resultatprocent, kontrollsummor), tomma belopp och anteckningarna längst ner läses inte. Skattesatsen står på raden `Skattesats (%)` i resultatbudgeten. Resultatbudgeten måste ha `Skatteintäkter`, `Generella bidrag och utjämning` och `Årets resultat`, och tabellen Nämnder minst en ram. Raden `Totalt` är en summa, inte en nämnd. Ett fel i filen avbryter hela inläsningen med flik och rad.

Ett år utan flik (2022) har inga planförutsättningar. Förslagen för året visas med sina faktiska ramar, utan förändring och utan beräknat resultat.

## budget.json

Bredvid förslagen beskriver `budget.json` varje förslag. Filen tas fram en gång per år genom att läsa dokumenten, eftersom förslagen har olika tabelluppläggning och en del är inskannade. Varje siffra är det som står i dokumentet, med sidan där den står (sidan i PDF:en, inte det tryckta sidnumret). Ett Word-dokument har inga fasta sidor, så där anges ingen sida och siffran visas utan sidlänk.

```json
{
  "behandling": {"organ": "KF", "datum": "2026-06-15", "paragraf": 108},
  "forslag": {
    "majoritet.pdf": {
      "partier": ["KD", "MP", "S"],
      "titel": "Årsplan 2027",
      "antagen": true,
      "resultat": {"procent": 2.3, "sida": 17},
      "ramar": [{"organ": "Kommunstyrelsen", "mnkr": 191.3, "sida": 18}]
    },
    "M.pdf": {
      "titel": "Moderaternas budgetförslag för Härnösands kommun 2027",
      "skattesats": {"ore": -10, "sida": 4},
      "resultat": {"procent": 2.5, "sida": 3},
      "ramar": [{"organ": "Skolnämnden", "forandring": 15, "sida": 4, "atgarder": [
        {"text": "Mindre barngrupper, stödundervisning och elevhälsoteam.", "mnkr": 15, "sida": 4}
      ]}]
    }
  }
}
```

| Fält | Innehåll |
|---|---|
| `partier` | Partiförkortningarna. Utelämnas när de står i filnamnet. |
| `titel` | Förslagets rubrik som i dokumentet. |
| `typ` | `budget` eller `tillagg`. Utelämnas för en budget. |
| `antagen` | `true` för det förslag kommunfullmäktige antog. |
| `ramar` | Per nämnd för budgetåret: `mnkr` eller `forandring` mot planförutsättningen. En förändring räknas om till mnkr. En ram kan ha `atgarder`, se nedan. |
| `skattesats` | Förändringen: `ore` (−10 för "10 öre lägre") eller `forandring` i procentenheter (−0.10). En skattesats i `procent` räknas om till förändring. Utelämnas om förslaget inte ändrar skatten. |
| `resultat` | `procent` av skatteintäkter och generella bidrag och utjämning, eller `mnkr`, som räknas om till procent. |
| `behandling` | `{organ, datum, paragraf}` för behandlingen där förslaget ställdes. Organet är `KF` om det utelämnas. En `behandling` överst i filen gäller alla förslag som inte anger en egen. |
| `summering` | Ett svar per fråga i mallen, se *Summering*. |
| `anmarkning` | Det läsaren behöver veta om hur förslaget redovisar siffrorna, till exempel att det räknat från en annan version av planförutsättningarna eller ändrar investeringarna. |

### Åtgärder per nämnd

En ram kan ha en lista `atgarder` med de besparingar och satsningar förslaget anger för nämnden (#57). Varje åtgärd har:

| Fält | Innehåll |
|---|---|
| `text` | Ett citat eller en kort sammanfattning av det som står i förslaget. Texten ligger nära originalet och värderas inte. |
| `mnkr` | Ramens förändring i mnkr för åtgärden, när förslaget anger ett belopp. Utelämnas annars. Negativt för en besparing. |
| `sida` | Sidan i PDF:en. Krävs för en PDF och anges inte för ett Word-dokument. |

**Avläst eller inte.** `"atgarder": []` betyder att redaktören har läst förslaget och att det inte anger några åtgärder för nämnden. Saknas fältet är åtgärderna inte avlästa, och det står så för läsaren. Läs därför av varje nämnd som förslaget tar upp, också en oförändrad.

Åtgärderna står oftare i löptext än i tabeller, så avläsningen är mer tolkning än för ramarna. Därför krävs sidan. En åtgärd som inte går att knyta till en nämnd, till exempel en avgiftshöjning som inte anges per nämnd, tas inte med. En ogiltig åtgärd (utan text, med okänt fält, utan sida i en PDF) stoppar inläsningen med fil och fel.

### Summering

Varje förslag kan summeras med samma frågor, i samma ordning (`MALL` i `backend/app/budgetforslag.py`):

| Id | Fråga |
|---|---|
| `prioriteringar` | Vilka verksamheter prioriterar förslaget? |
| `besparingar` | Var föreslår förslaget lägre kostnader? |
| `skatt_och_avgifter` | Vad föreslår förslaget om skattesats, avgifter och taxor? |
| `resultat` | Vilket resultat budgeterar förslaget, och hur motiveras det? |
| `investeringar` | Vad föreslår förslaget om investeringar och lån? |
| `ovrigt` | Vad föreslår förslaget utöver budgetmodellen, till exempel uppdrag eller organisation? |

Ett svar är `{"text": …, "sidor": [1, 2]}`, eller `{"anges_inte": true}` när förslaget inte tar upp frågan. Sidorna krävs för en PDF och anges inte för ett Word-dokument. En summering har svar på alla frågor eller finns inte alls. Svaren återger vad förslaget säger, nära texten, och värderar det inte. Summeringen är redaktionens sammanfattning och märks **Analys** (streckad kantlinje, `docs/design.md`). Den granskas och publiceras med förslaget.

Bara budgetåret läses. Planåren tas inte med. Det tidigare formatet med listor per år (`"ar": 2027`) och `utgangslage` tas emot, och då läses bara budgetårets poster. Nämnderna skrivs med samma namn i alla förslag och i planförutsättningarna: Kommunfullmäktige, Kommunstyrelsen, Kommungemensam verksamhet, Samhällsnämnden, Skolnämnden och Socialnämnden.

## Vad som lagras och räknas fram

Ett förslag lagrar ramar i mnkr, skattesatsens förändring i öre och resultatet i procent. Omräkningarna vid inläsningen görs mot årets planförutsättningar:

- **Ram** av en förändring: planförutsättningens ram + förändringen.
- **Skatteförändring** av en skattesats: (skattesatsen − planförutsättningens) × 100 öre.
- **Resultat i procent** av mnkr: mnkr / förslagets bas. Basen är planförutsättningarnas skatteintäkter + generella bidrag och utjämning, justerat för förslagets skatteförändring.

Applikationen räknar fram:

- **Förändring** per nämnd: förslagets ram − planförutsättningens. En nämnd som förslaget inte tar upp är oförändrad.
- **Skatteintäkternas förändring:** skatteintäkterna × öre / 100 / skattesatsen. 10 öre 2027 är cirka −6,4 mnkr.
- **Resultat i mnkr:** procenten av förslagets bas.
- **Beräknat resultat:** planförutsättningarnas resultat − summan av förändringarna + skatteintäkternas förändring.
- **Täckning** per nämnd: antalet åtgärder och summan av deras belopp, mot förändringen. En ram som ändras utan åtgärder, enligt avläsningen, markeras "Inga åtgärder anges". En förändring under 0,05 mnkr är avrundning och räknas inte som en ändrad ram.
- **Differens:** förslagets resultat i mnkr − det beräknade. Skiljer de sig saknar förslaget finansiering för skillnaden, eller redovisar den inte. Exempel 2027, mot kommunens planförutsättningar (resultat 50,3 mnkr, nämnderna 2 144,7 mnkr): L budgeterar cirka 80 mnkr men sparar bara 10,7 mnkr netto på ramarna (beräknat 61,0, differens 18,9), och SD räknar resultatet som skatter och bidrag minus ramar och utelämnar kostnaderna utanför nämnderna (beräknat 22,2, differens 22,2). M sänker skatten med 10 öre och går nästan ihop (differens −1,3).

## Inläsning

```bash
tar -C data -c budgetforslag | ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.budgetforslag - --redaktor EPOST'
```

Kommandot läser först planförutsättningarna och sedan förslagen, och skapar utkast. Allt görs i en transaktion: ett fel någonstans avbryter hela inläsningen. Den som läser in räknas som redaktör och kan inte själv granska eller publicera. En ny inläsning med samma uppgifter ändrar inget. Har något ändrats uppdateras ett öppet utkast, även redaktörens ändringar, och det som är publicerat får ett nytt utkast som ersätter det när det publiceras. Ett förslag med förändringar räknas om när planförutsättningarna ändras.

**Överföring av befintliga förslag.** Förslag som lästes in före #58 (med planår, resultat i mnkr och skattesats i procent) förs över av samma kommando, mot årets planförutsättningar: planåren tas bort, resultatet räknas om till procent och skattesatsen till förändring i öre. Redaktörens ändringar följer med. Ett öppet utkast ändras och blir utkast igen, ett publicerat förslag får ett nytt utkast och ett ersatt ändras där det står. Läs därför in planförutsättningarna samtidigt eller före.

## Redigering och publicering

Planförutsättningarna rättas i Excelfilen och läses in igen. Under Politik och beslut → Budgetutkast visas alla tabeller med källa och länk till sidan i förslaget, och kontrollsummorna: det angivna beloppet minus summan av posterna (±0 betyder att tabellen går ihop).

En redaktör rättar ett förslags utkast på samma sida. En ram kan anges i mnkr eller som förändring. Under varje ram lägger redaktören till, ändrar och tar bort åtgärder, och kryssar i Avläst när förslaget inte anger några för nämnden, och utgivaren ser dem med belopp, sidlänk och täckning innan granskningen. En utgivare som inte läst in eller ändrat uppgifterna granskar och publicerar dem (utkast → granskad → publicerad, kravspec 18, ADR-0002). Ändras ett granskat förslag blir det utkast igen.

## Koppling till behandlingen

Förslaget hänvisar till behandlingen där det ställdes (kravspec 18). Hänvisningen är en uppgift som redaktören anger och utgivaren granskar. Ur protokollet kopplas resten automatiskt och märks ⚙ *Automatisk koppling*:

- **Yrkandet:** det yrkande vars förslagsställare tillhör något av förslagets partier, med dem som ställde sig bakom det. Majoritetens förslag är kommunstyrelsens förslag, som någon i majoriteten yrkar bifall till.
- **Voteringarna** i behandlingen, med siffrorna i voteringslistan och den sida (ja eller nej) där förslagsställarens namn står.

Fullmäktige behandlade förslagen för 2027 den 2026-06-15 i § 108 utan votering: ordföranden ställde de fem förslagen mot varandra. Då visas "Ingen votering i protokollet". Är protokollet inte insamlat visas hänvisningen utan länk.

## Jämförelse

Läsaren ser de publicerade förslagen för ett budgetår bredvid varandra, med planförutsättningarna först och den antagna budgeten som första förslag. Per nämnd visas ramen med förändringen mot planförutsättningen, och sedan skattesatsen (planförutsättningen ± förändringen), resultatet i mnkr och procent, det beräknade resultatet och differensen. Planförutsättningarnas resultat-, investerings-, balans- och kassaflödesbudget visas en gång under förslagen, gemensamt för alla.

Förändringar och beräknat resultat visas först när årets planförutsättningar är publicerade. Dessförinnan, och för ett år utan planförutsättningar, visas förslagens egna ramar, skattesats och resultat i procent.

**Behandling och summering:** sist i tabellen står behandlingen med länk till paragrafen, yrkandet och voteringarna. Under tabellen visas summeringarna bredvid varandra, en rad per fråga, märkta Analys.

**Åtgärder:** varje nämnd kan öppnas, en i taget eller alla på en gång med Visa alla åtgärder. Per förslag visas åtgärderna uppdelade i besparingar (negativt belopp), satsningar (positivt belopp) och åtgärder utan belopp, med länk till sidan i originalet, och täckningen, till exempel "åtgärder för −3,0 av −3,0 mnkr". Annars står varför det saknas åtgärder:

| Text | Betyder |
|---|---|
| Inga åtgärder anges | Förslaget ändrar ramen men anger inga åtgärder för den. |
| Inga besparingar eller satsningar anges | Förslaget anger inga åtgärder för nämnden och ändrar inte ramen. |
| Åtgärderna är inte avlästa | Redaktionen har inte läst av åtgärderna för nämnden. |
| Tar inte upp nämnden | Förslaget har ingen ram för nämnden. |

**Differensanalys:** när den antagna budgeten för året finns visas skillnaden mot den per nämnd i kronor och procent, för resultatet i mnkr och för skattesatsen i öre.

## Jämfört med SKR:s prognoser

Sidan för budgetåret har ett avsnitt "Jämfört med SKR:s prognoser" (#62). Där står planförutsättningarnas
skatteintäkter och generella bidrag och utjämning (summan av de två posterna i resultatbudgeten, i mnkr)
bredvid raden "Summa intäkter (inkl avräkning och fastighetsavgift)" för budgetåret i varje
[skatteunderlagsprognos](skatteunderlag.md), omräknad från tkr till mnkr.

- En rad per prognos som har en siffra för året, sorterade efter publiceringsdatum, med cirkulär, datum och länk
  till filen.
- Differensen är SKR − planförutsättningar, i mnkr (en decimal) och procent. Ingen prognos pekas ut som den rätta.
- Bara summorna jämförs, eftersom kommunen och SKR delar upp posterna olika. En fast text förklarar att
  kommunen kan räkna in generella statsbidrag som SKR:s underlag inte innehåller, och tvärtom.
- Bara publicerade planförutsättningar jämförs. Saknas de, eller har ingen prognos en siffra för året, står
  det kort varför (SKR:s prognoser finns från 2026). Budgetförslagen påverkas inte.

API: fältet `skr` i `GET /api/budget/{år}`.
