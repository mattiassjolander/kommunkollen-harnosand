# Partiernas budgetförslag

Partiernas budgetförslag till kommunfullmäktige läses in i samma budgetmodell som den antagna budgeten: skattesats, budgeterat resultat och ram per nämnd (kravspec 17A, #48). Läsaren jämför förslagen för ett budgetår med varandra och med den antagna budgeten.

## Filerna

Förslagen läggs i `data/budgetforslag/<budgetår>/`, som inte versionshanteras. Budgetåret är året budgeten gäller, inte året förslaget lades fram.

- Filnamnet är partiförkortningarna bakom förslaget i alfabetisk ordning: `C.pdf`, `L+M.pdf`, `KD+MP+S+V.docx`.
- Ett förslag till tilläggsbudget eller reviderad budget får ett eget namn, till exempel `S-tillagg.pdf`.
- Majoritetens förslag heter `majoritet.pdf` från 2023. Det är kommunens årsplan: majoriteten lägger fram den och fullmäktige antar den. Partierna anges då i `budget.json`.
- Filerna är PDF eller Word (`.docx`) och ligger kvar i originalformatet som källa.

## budget.json

Bredvid filerna beskriver `budget.json` varje förslag. Filen tas fram en gång per år genom att läsa dokumenten, eftersom förslagen har olika tabelluppläggning och en del är inskannade. Varje siffra är det som står i dokumentet, med sidan där den står (sidan i PDF:en, inte det tryckta sidnumret). Ett Word-dokument har inga fasta sidor, så där anges ingen sida och siffran visas utan sidlänk.

```json
{
  "forslag": {
    "majoritet.pdf": {
      "partier": ["KD", "MP", "S"],
      "titel": "Årsplan 2027",
      "antagen": true,
      "skattesats": {"procent": 23.34, "sida": 17},
      "resultat": [{"ar": 2027, "mnkr": 50.3, "procent": 2.3, "sida": 17}],
      "ramar": [{"organ": "Kommunstyrelsen", "ar": 2027, "mnkr": 191.3, "sida": 18}]
    },
    "M.pdf": {
      "titel": "Moderaternas budgetförslag för Härnösands kommun 2027",
      "utgangslage": "Planförutsättningar 2027",
      "skattesats": {"forandring": -0.10, "sida": 4},
      "resultat": [{"ar": 2027, "procent": 3.0, "sida": 5}],
      "ramar": [{"organ": "Skolnämnden", "ar": 2027, "forandring": 15, "sida": 4}],
      "anmarkning": "Förslaget anger ramarna som förändringar mot planförutsättningarna."
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
| `skattesats` | `procent` (t.ex. 23.34) och/eller `forandring` i procentenheter (−0.10 för "10 öre lägre"). |
| `resultat` | Per år: `mnkr` och/eller `procent` av skatteintäkter, generella statsbidrag och utjämning. |
| `ramar` | Per nämnd och år: `mnkr` (nettokostnad eller tilldelade skattemedel) och/eller `forandring` i mnkr. |
| `utgangslage` | Vad förändringarna räknas från, t.ex. "Planförutsättningar 2027". |
| `anmarkning` | Det läsaren behöver veta om hur förslaget redovisar siffrorna. |

Planåren ("plan 2028–2029") läses ut som en del av förslaget, med sina år. Nämnderna skrivs med samma namn i alla förslag: Kommunfullmäktige, Kommunstyrelsen, Kommungemensam verksamhet, Samhällsnämnden, Skolnämnden och Socialnämnden. Siffror som inte står i dokumentet räknas inte fram.

## Inläsning

```bash
tar -C data -c budgetforslag | ssh kommunkollen 'cd /opt/kommunkollen && docker compose exec -T backend /app/.venv/bin/python -m app.budgetforslag - --redaktor EPOST'
```

Kommandot skapar ett utkast per förslag. Den som läser in räknas som redaktör och kan inte själv granska eller publicera förslaget. En ny inläsning med samma fil och samma uppgifter ändrar inget. Har något ändrats uppdateras ett öppet utkast, och ett publicerat förslag får ett nytt utkast som ersätter det när det publiceras.

## Redigering och publicering

En redaktör rättar utkastet under Politik och beslut → Budgetförslag. En utgivare som inte läst in eller ändrat förslaget granskar och publicerar det (utkast → granskad → publicerad, kravspec 18). Ändras ett granskat förslag blir det utkast igen.

## Jämförelse

Läsaren ser de publicerade förslagen för ett budgetår bredvid varandra, med den antagna budgeten först. För budgetåret och planåren visas skattesats, resultat och ram per nämnd, med länk till sidan i originalet.

**Differensanalys:** när den antagna budgeten för året finns visas skillnaden mot den per nämnd, i kronor och procent, och skattesatsen i procentenheter. Skillnaden räknas bara när både förslaget och den antagna budgeten anger ett belopp för samma nämnd och år. Ett förslag som bara anger förändringar visas med förändringen och sitt utgångsläge, och beloppet räknas inte fram.
