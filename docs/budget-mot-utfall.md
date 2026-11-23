# Budget jämfört med utfall: källor (#83, kravspec 3.2)

Utredning av varifrån antagen budget, reviderad budget, delårsprognos och utfall hämtas, för årets resultat och nämndernas ramar. Utredd 2026-11-23 mot kommunens webbplats (*Budget och årsredovisning* under Ekonomi och upphandling) och de öppna källorna som redan används.

## Sammanfattning

| Uppgift | Årets resultat | Per nämnd | Källa |
|---|---|---|---|
| Antagen budget | Ja | Ja (ram) | Årsplanen, som redan läses in som majoritetens budgetförslag (`budget.json`, `docs/budgetforslag.md`), och planförutsättningarna |
| Reviderad budget | Ja | Ja (budget nettokostnad) | Årsredovisningens driftredovisning (budget vid årets slut) och delårsrapportens driftredovisning (budget vid delåret) |
| Delårsprognos | Ja | Ja (prognosavvikelse helår) | Delårsrapporten per augusti, avsnittet *Helårsprognos* |
| Utfall | Ja | Ja (nettokostnad) | Årsredovisningens driftredovisning. Årets resultat finns också hos SCB (ResultKnN 120) |

**Kolada och SCB räcker inte.** Kolada redovisar kommunen som helhet, inte nämnderna. SCB:s räkenskapssammandrag delar upp kostnaderna per verksamhet (t.ex. grundskola eller äldreomsorg), inte per nämnd, och har ingen budget eller prognos. Budget, reviderad budget, prognos och utfall per nämnd finns bara i kommunens PDF:er.

## Dokumenten

Alla finns som PDF på harnosand.se under *Budget och årsredovisning*:

- **Årsplaner** 2019–2027 (2019 heter *Budget*).
- **Delårsrapporter per augusti** 2015–2020 och 2022–2024. Delårsrapporten för 2021 och de för 2025–2026 finns inte på sidan. De behandlas av kommunfullmäktige på hösten och bör finnas bland fullmäktiges handlingar. Det behöver kontrolleras.
- **Årsredovisningar** 2009–2025.

### Årsredovisningen

Exemplet är *Årsredovisning 2025* (96 sidor).

- **Driftredovisning per nämnd** (s. 81, *Drifts- och investeringsredovisning*): intäkter, kostnader och nettokostnad för året och året före, *budget nettokostnad* och *avvikelse mot budget*, per nämnd plus kommunövergripande verksamhet, korrigeringar och *Summa inkl. finansen* (avvikelsen för årets resultat, 13,7 mnkr).
- **Budgetavvikelse för årets resultat** (s. 46 och 48): resultatet 23,7 mnkr mot ett budgeterat resultat på 10,0 mnkr, och tabellen *Total budgetavvikelse*.
- **Budgetkolumnen är den reviderade budgeten.** Årsplan 2025 antog ramen 804,5 mnkr för socialnämnden (årsplanen s. 21). I årsredovisningen är budgeten 838,6 mnkr. Arbetslivsnämnden avvecklades vid halvårsskiftet 2025, och dess ram på 60,3 mnkr fördelades på andra nämnder. Det budgeterade resultatet, 10,0 mnkr, är detsamma i årsplanen (s. 19) och i årsredovisningen.
- Förklaringar till avvikelserna står i texten under tabellen, per nämnd (t.ex. lägre personalkostnader). Det är underlag för kravspecens följdkrav om orsaken till en avvikelse.

### Delårsrapporten

Exemplet är *Delårsrapport augusti 2024* (52 sidor).

- **Helårsprognos** (s. 25): per nämnd *budget helår*, *prognosavvikelse helår* och *prognostiserat resultat helår*. Nämndernas budget redovisas som resultat (0,0), alltså i balans. Prognosen anges som avvikelse mot ramen. Kommunens prognos för helåret var −84,2 mnkr mot ett budgeterat resultat på 13,4 mnkr.
- **Driftredovisning för perioden** (s. 37): utfall per nämnd januari–augusti med periodens budget och avvikelse. Det är ett periodutfall, inte en helårsprognos.
- Nämndernas nettokostnadsbudget för helåret står inte i tabellen. Den fås ur ramen och den reviderade budgeten, eller ur nämndsrapporterna.

### Antagen budget och behandlingen

Den antagna budgeten är årsplanen, som redan läses in med ramar per nämnd och budgeterat resultat, med sidhänvisning (`budget.json`). Behandlingen i kommunfullmäktige finns där som `behandling` (organ, datum, paragraf) och kopplas till behandlingen med yrkanden och voteringar. Planförutsättningarna ger ramarna före politiska prioriteringar. Varje budgetsiffra kan alltså redan länka till förslaget och till behandlingen.

**Revideringar under året** beslutas av fullmäktige (t.ex. omorganisation och ändrade ramar) och finns i protokollen. Årsredovisningens budgetkolumn är summan av dem. Att länka varje revidering till sitt beslut kräver att besluten identifieras i protokollen, och det föreslås som ett senare steg.

## Inläsning

Genomfört i #83: `uppfoljning.json` i budgetårets mapp (`data/budgetforslag/<år>/`) läses in med budgetförslagen
(`python -m app.budgetforslag MAPP`), granskas och publiceras. Formatet står i `backend/app/uppfoljning.py`.
Uppgifterna för 2023–2026 är avlästa: årsredovisningarna 2023–2025, delårsrapporterna 2023 och 2024 och
delårsrapporten 2026 i fullmäktiges handlingar 2026-10-26. Sidnumren är sidorna i PDF-filen, som i dessa dokument
är desamma som de tryckta. Delårsrapporten för 2025 finns inte publikt. Den är begärd ur kommunens diarium och lagras i plattformen (s. 31).

Samma arbetssätt som budgetförslagen. Tabellerna i årsredovisningen och delårsrapporten har olika uppställning mellan åren, och vissa år har nämnder som läggs ned eller tillkommer. Därför tas siffrorna fram genom att läsa dokumenten och skrivs i en fil per år, med sida för varje siffra:

```json
{
  "arsredovisning": {"titel": "Årsredovisning 2025", "url": "https://www.harnosand.se/download/…", "sidor": 96},
  "delarsrapport": {"titel": "Delårsrapport augusti 2025", "url": "…"},
  "resultat": {"budget": {"mnkr": 10.0, "sida": 48}, "prognos": {"mnkr": …, "sida": …}, "utfall": {"mnkr": 23.7, "sida": 46}},
  "namnder": [
    {"organ": "Socialnämnden",
     "reviderad_budget": {"mnkr": -838.6, "sida": 81},
     "prognosavvikelse": {"mnkr": …, "sida": …},
     "utfall": {"mnkr": -823.7, "sida": 81}}
  ]
}
```

Den antagna budgeten hämtas ur årsplanen som redan finns i plattformen och läses inte in igen. Avvikelsen räknas fram i mnkr och procent: utfall eller prognos mot antagen och reviderad budget. När dokumentet anger en avvikelse kontrolleras den räknade mot den, på samma sätt som brodiagrammet kontrolleras mot SCB.
