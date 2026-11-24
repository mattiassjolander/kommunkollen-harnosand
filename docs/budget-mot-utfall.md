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

**Revideringar under året** beslutas av fullmäktige (t.ex. omorganisation och ändrade ramar) och finns i protokollen. Årsredovisningens budgetkolumn är summan av dem. Var de finns och hur de kopplas till besluten står under *Revideringarna och besluten* nedan (#134).

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

## Revideringarna och besluten (#134)

Utrett 2026-11-24 mot årsredovisningarna 2023–2025, delårsrapporterna 2024–2026 och fullmäktiges och kommunstyrelsens protokoll i plattformen. Frågan är var besluten som ändrar nämndernas budget under året finns, och om de förklarar hela skillnaden mellan antagen och reviderad budget.

### Var revideringarna finns

- **Inte i årsredovisningens eller delårsrapportens förteckning.** Ingen av årsredovisningarna 2023–2025 har en förteckning över tilläggsanslag eller ombudgeteringar. Driftredovisningen visar bara budgeten vid årets slut. Årsredovisningen 2024 skriver under driftredovisningen (s. 87) att inga anslagsförändringar har beslutats under året. Årsredovisningen 2025 skriver (s. 81) att arbetslivsnämndens budget är fördelad till de nämnder som tog över verksamheten. Delårsrapporterna redovisar nämndernas budget som 0,0 (i balans) i helårsprognosen och har ingen förteckning.
- **I fullmäktiges protokoll, under varierande rubriker.** Inget ärende 2023–2025 har *tilläggsanslag* eller *ombudgetering* i rubriken. Sökningen på *budget* ger mest årsplanerna och koncernbudgetarna. Besluten om ändrade ramar finns i ärenden om ekonomiska åtgärder och om organisationen:

| År | Antagen → reviderad budget | Beslut | Belopp i beslutet |
|---|---|---|---|
| 2023 | Socialnämnden 685,3 → 705,5 (+20,2), samhällsnämnden 190,5 → 202,9 (+12,4) | KF 2023-06-19 § 104 *Förändrat finansiellt mål och ekonomiska åtgärder för 2023* | Ja: 20,2 och 12,4 mnkr "extra skattemedel" |
| 2024 | Ingen skillnad | – | Årsredovisningen s. 87: inga anslagsförändringar |
| 2025 | Arbetslivsnämnden 60,3 → 0,0, socialnämnden 804,5 → 838,6 (+34,1), skolnämnden 645,4 → 664,6 (+19,2), kommunstyrelsen 184,3 → 191,3 (+7,0) | KF 2025-05-26 § 75 *Avveckling av arbetslivsnämnd* | Nej. Beslutet flyttar ansvarsområdena. Beloppen framgår av årsredovisningens budgetkolumn (s. 81), och de går jämnt upp: 34,1 + 19,2 + 7,0 = 60,3 |

- **Kommunstyrelsens protokoll** ger inga egna beslut om ändrade ramar för åren vid sökning på *budget*, *ram* och *omfördelning*. Kommunstyrelsen bereder fullmäktiges beslut, t.ex. KS 2025-05-06 § 79 om arbetslivsnämnden. Andra beslut med *budget* i rubriken gäller resultatkrav eller investeringar. Ett exempel är KF 2025-09-29 § 112 *budgetändring kommunstyrelsen och nämnder*, där nämnderna ska nå ett överskott. Ramarna ändras inte, och årsredovisningens budgetkolumn påverkas inte.
- **Årets resultat:** KF 2023-06-19 § 104 sänkte också det budgeterade resultatet från 38,3 till 1,9 mnkr. Årsredovisningen 2023 jämför ändå resultatet med 38,3 mnkr (s. 52). Uppföljningen följer årsredovisningen, och revideringarna gäller bara nämnderna.

**Svar:** För 2023–2025 förklarar besluten hela skillnaden. Ingen rest blir okopplad. Beloppen för 2025 står inte i beslutet. De visas med sidan i årsredovisningen som anger dem. För 2026 finns ingen årsredovisning än. Delårsrapporten 2026 nämner att kommunstyrelsen tagit över verksamhet och budgetmedel från andra nämnder, men den reviderade budgeten per nämnd redovisas först i årsredovisningen.

### Orsakerna till avvikelserna

Årsredovisningens text under driftredovisningen förklarar avvikelserna per nämnd, ibland för två nämnder i samma mening (2023: skol- och socialnämnden). Delårsrapporten 2024 hänvisar till nämndernas egna rapporter. Delårsrapporterna 2025 och 2026 ger en kort förklaring i texten till driftredovisningen eller helårsprognosen. Texterna läses in ordagrant som citat med sida och visas vid nämnden. En mening om nämnderna i stort visas under tabellen.

### Inläsning

I `uppfoljning.json` (formatet står i `backend/app/uppfoljning.py`):

```json
"revideringar": [
  {"beslut": {"organ": "KF", "datum": "2023-06-19", "paragraf": 104},
   "andringar": [{"organ": "Socialnämnden", "mnkr": 20.2}, {"organ": "Samhällsnämnden", "mnkr": 12.4}]},
  {"beslut": {"organ": "KF", "datum": "2025-05-26", "paragraf": 75}, "belopp_sida": 81,
   "andringar": [{"organ": "Arbetslivsnämnden", "mnkr": -60.3}, {"organ": "Socialnämnden", "mnkr": 34.1}]}
],
"orsaker": [
  {"dokument": "arsredovisning", "sida": 81, "organ": ["Socialnämnden"], "text": "Samtliga nämnder gör …"}
]
```

- Beslutet länkar till behandlingen när protokollet finns i plattformen och visas annars som hänvisning.
- Resten, reviderad minus antagen budget minus besluten, räknas fram per nämnd och visas som *ej kopplat till beslut*.
- `revideringar: []` betyder att inga beslut hittades. Utan fältet är året inte utrett, och avsnittet visas inte.
- Uppgifterna hör till uppföljningen och går utkast → granskad → publicerad med den. De behöver ingen egen tabell.
