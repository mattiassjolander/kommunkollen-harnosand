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
      "ramar": [{"organ": "Skolnämnden", "forandring": 15, "sida": 4}]
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
| `ramar` | Per nämnd för budgetåret: `mnkr` eller `forandring` mot planförutsättningen. En förändring räknas om till mnkr. |
| `skattesats` | Förändringen: `ore` (−10 för "10 öre lägre") eller `forandring` i procentenheter (−0.10). En skattesats i `procent` räknas om till förändring. Utelämnas om förslaget inte ändrar skatten. |
| `resultat` | `procent` av skatteintäkter och generella bidrag och utjämning, eller `mnkr`, som räknas om till procent. |
| `anmarkning` | Det läsaren behöver veta om hur förslaget redovisar siffrorna, till exempel att det räknat från en annan version av planförutsättningarna eller ändrar investeringarna. |

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
- **Differens:** förslagets resultat i mnkr − det beräknade. Skiljer de sig saknar förslaget finansiering för skillnaden, eller redovisar den inte. Exempel 2027, mot kommunens planförutsättningar (resultat 50,3 mnkr, nämnderna 2 144,7 mnkr): L budgeterar cirka 80 mnkr men sparar bara 10,7 mnkr netto på ramarna (beräknat 61,0, differens 18,9), och SD räknar resultatet som skatter och bidrag minus ramar och utelämnar kostnaderna utanför nämnderna (beräknat 22,2, differens 22,2). M sänker skatten med 10 öre och går nästan ihop (differens −1,3).

## Inläsning

```bash
tar -C data -c budgetforslag | ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.budgetforslag - --redaktor EPOST'
```

Kommandot läser först planförutsättningarna och sedan förslagen, och skapar utkast. Allt görs i en transaktion: ett fel någonstans avbryter hela inläsningen. Den som läser in räknas som redaktör och kan inte själv granska eller publicera. En ny inläsning med samma uppgifter ändrar inget. Har något ändrats uppdateras ett öppet utkast, även redaktörens ändringar, och det som är publicerat får ett nytt utkast som ersätter det när det publiceras. Ett förslag med förändringar räknas om när planförutsättningarna ändras.

**Överföring av befintliga förslag.** Förslag som lästes in före #58 (med planår, resultat i mnkr och skattesats i procent) förs över av samma kommando, mot årets planförutsättningar: planåren tas bort, resultatet räknas om till procent och skattesatsen till förändring i öre. Redaktörens ändringar följer med. Ett öppet utkast ändras och blir utkast igen, ett publicerat förslag får ett nytt utkast och ett ersatt ändras där det står. Läs därför in planförutsättningarna samtidigt eller före.

## Redigering och publicering

Planförutsättningarna rättas i Excelfilen och läses in igen. Under Politik och beslut → Budgetutkast visas alla tabeller med källa och länk till sidan i förslaget, och kontrollsummorna: det angivna beloppet minus summan av posterna (±0 betyder att tabellen går ihop).

En redaktör rättar ett förslags utkast på samma sida. En ram kan anges i mnkr eller som förändring. En utgivare som inte läst in eller ändrat uppgifterna granskar och publicerar dem (utkast → granskad → publicerad, kravspec 18, ADR-0002). Ändras ett granskat förslag blir det utkast igen.

## Jämförelse

Läsaren ser de publicerade förslagen för ett budgetår bredvid varandra, med planförutsättningarna först och den antagna budgeten som första förslag. Per nämnd visas ramen med förändringen mot planförutsättningen, och sedan skattesatsen (planförutsättningen ± förändringen), resultatet i mnkr och procent, det beräknade resultatet och differensen. Planförutsättningarnas resultat-, investerings-, balans- och kassaflödesbudget visas en gång under förslagen, gemensamt för alla.

Förändringar och beräknat resultat visas först när årets planförutsättningar är publicerade. Dessförinnan, och för ett år utan planförutsättningar, visas förslagens egna ramar, skattesats och resultat i procent.

**Differensanalys:** när den antagna budgeten för året finns visas skillnaden mot den per nämnd i kronor och procent, för resultatet i mnkr och för skattesatsen i öre.
