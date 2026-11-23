# Täckning: ekonomiska nyckeltal (kravspec 3.1 och 3.3)

Vilken källa och vilket mått som används för varje punkt i kravspecens avsnitt 3.1 och 3.3, eller att uppgiften saknas i fas 1. Katalogen finns i `backend/app/ekonomi.py`. Ändras den ska tabellen uppdateras samtidigt.

**Källor**
- **Kolada** (api.kolada.se v3): nyckeltal för kommunen (inte koncernen) i kr/inv eller procent.
- **SCB** (statistikdatabasen, räkenskapssammandraget OE0107A): resultat- och balansräkning i tkr. Tabellerna `ResultKnN`, `BalansKnN` och `SkatteIntKnN`. Ekonomivyn visar tkr som mnkr. Det lagrade värdet är källans.

**Riket** (#82). Kolada-nyckeltalen i `ekonomi.KOLADA` hämtas även för riket (kommun-id 0000, genomsnittet för alla kommuner) i samma insamling och lagras med område `0000`. Ett misslyckande redovisas per nyckeltal som "N03002 (riket): …" i källans fel, som för kommunen. SCB-måtten och de beräknade måtten (rörelsekapital och låneskuld per invånare) har ingen motsvarighet för riket.

**Prisnivå.** Alla kronbelopp är i löpande priser. Varken Kolada eller SCB:s räkenskapssammandrag publicerar fasta priser för de här måtten. Kr/inv gör åren jämförbara för befolkningsförändringar, men inte för inflation.

**Beräknat av Kommunkollen.** Två mått finns inte hos källorna och beräknas: rörelsekapitalet (SCB, vid insamlingen) och låneskulden per invånare, som räknas fram när den läses: SCB BalansKnN 081 (långfristiga lån i banker och kreditinstitut, tkr) × 1 000 delat med folkmängden 31 december (Kolada N01951). Ett år där någon av uppgifterna saknas visas som "Uppgift saknas". Båda är märkta "Beräknat av Kommunkollen" i förklaringen och källraden.

**Historik.** Hela tidsserien hämtas: SCB från 1998, och Kolada så långt tillbaka som nyckeltalet finns. Vyn börjar som standard 2022.

## 3.1 Ekonomisk översikt

| Krav | Källa och mått | Anmärkning |
|---|---|---|
| Årets resultat | Kolada N03007 (kr/inv), N03102 (% av skatt och generella statsbidrag). SCB ResultKnN 120 (tkr) | |
| Budgeterat resultat | Årsplanen (antaget budgetförslag) och årsredovisningen (reviderad budget), se 3.2 | Avläst ur kommunens PDF:er och granskat före publicering. |
| Resultatprognos | Delårsrapportens helårsprognos, se 3.2 | Avläst ur kommunens PDF:er och granskat före publicering. |
| Skatteintäkter | SCB ResultKnN 040 (tkr). Kolada N03010 (kr/inv) | |
| Generella statsbidrag | SCB ResultKnN 050 (tkr) och SkatteIntKnN 080 (brutto). Kolada N03009 (kr/inv) | Redovisas tillsammans med utjämningen. Generella bidrag från staten finns som egen post (SkatteIntKnN 150) men visas inte än. |
| Riktade statsbidrag | Saknas i fas 1 | Ingår i verksamhetens intäkter och redovisas inte separat per kommun i Kolada eller i de SCB-tabeller som används. Kan komma från SCB:s VerksInt eller årsredovisningen. |
| Utjämningsbidrag och utjämningsavgifter | SCB SkatteIntKnN 080 (bidrag inkl. generella statsbidrag) och 160 (avgifter), tkr | Uppdelning per utjämningssystem finns i tabellen och kan läggas till. |
| Verksamheternas nettokostnader | SCB ResultKnN 030 (tkr). Kolada N03011 (kr/inv), N03100 (% av skatt och generella statsbidrag) | |
| Investeringar | Kolada N03132 (nettoinvesteringar, kr/inv), N03103 (självfinansieringsgrad, %) | Kolada anger 2027 som nästa publicering för N03132. Framtida datum visas inte som publicering. |
| Låneskuld | SCB BalansKnN 081 (långfristiga lån i banker och kreditinstitut, tkr). Per invånare: beräknat ur 081 och Kolada N01951 (folkmängd) | Den kortfristiga delen av lånen ingår i kortfristiga skulder och syns inte här. Låneskulden per invånare är ett huvudtal och beräknas av Kommunkollen. |
| Pensionsåtaganden | SCB BalansKnN 072 (avsättningar i balansräkningen, tkr). Kolada N03044 (avsättning, kr/inv), N03048 (förpliktelser utanför balansräkningen, kr/inv) | |
| Likviditet | SCB BalansKnN 065 (likvida medel, tkr). Kolada N03105 (kassalikviditet, %) | |
| Soliditet | Kolada N03002 (inkl. pensionsåtaganden) och N03106 (exkl.) | |
| Kassaflöde | Saknas i fas 1 | Kassaflödesanalysen finns bara i årsredovisningen. |
| Kostnad per invånare | Kolada N03011 (nettokostnader kr/inv) | Övriga kr/inv-mått ovan kompletterar. |

## 3.2 Budget jämfört med utfall

Fliken *Budget och utfall* under Ekonomi (`/ekonomi/budget-och-utfall?ar=2025`). Källorna och inläsningen beskrivs i
`docs/budget-mot-utfall.md` och `backend/app/uppfoljning.py`.

| Krav | Källa | Anmärkning |
|---|---|---|
| Ursprunglig budget | Det antagna budgetförslaget (årsplanen): ram per nämnd och budgeterat resultat, med sida | Länkar till årsplanen och till behandlingen i fullmäktige. Resultatet står i procent av skatter och bidrag och räknas om till mnkr ur planförutsättningarna när de finns. |
| Reviderad budget | Årsredovisningens driftredovisning (budget nettokostnad) och budgeterat resultat | Budgeten vid årets slut, efter fullmäktiges ändringar under året. Ändringarna länkas inte till sina beslut än. |
| Delårsprognos | Delårsrapportens helårsprognos: prognosavvikelse per nämnd och prognostiserat resultat | Delårsrapporten för 2025 finns inte på kommunens webbplats eller bland de insamlade handlingarna, så 2025 visas utan prognos. 2026 års rapport finns i fullmäktiges handlingar 2026-10-26. |
| Faktiskt utfall | Årsredovisningens driftredovisning (nettokostnad) och årets resultat | Innevarande år har inget utfall förrän årsredovisningen finns. |
| Avvikelse i kronor | Räknad: budget minus nettokostnad per nämnd, resultat minus budget för resultatet | Kontrolleras mot avvikelsen som årsredovisningen anger, med 0,15 mnkr för avrundning. |
| Avvikelse i procent | Räknad av budgeten | Visas för nämnderna. För resultatet blir procenten av ett litet budgeterat resultat missvisande och visas inte. |
| Orsak till avvikelsen | Saknas | Förklaringarna står i text under driftredovisningen och i delårsrapporten och kan läsas in senare. |

Nämnderna heter som i årsplanen. Årsredovisningens *Kommunövergripande verksamhet* är årsplanens *Kommungemensam
verksamhet* (samma budgetbelopp). Korrigeringsposter och finansiell leasing visas inte.

## 3.3 Likviditet och soliditet

| Krav | Källa och mått | Anmärkning |
|---|---|---|
| Likvida medel | SCB BalansKnN 065 (tkr) | |
| Kassalikviditet | Kolada N03105 (%) | |
| Rörelsekapital | Beräknat: SCB BalansKnN 069 (omsättningstillgångar) minus 098 (kortfristiga skulder), tkr | Beräknat av Kommunkollen. Det står i nyckeltalets förklaring. |
| Kassaflöde | Saknas i fas 1 | Se 3.1. |
| Soliditet inklusive pensionsförpliktelser | Kolada N03002 (%) | |
| Soliditet exklusive pensionsförpliktelser | Kolada N03106 (%) | Kolada: exklusive pensionsåtaganden intjänade före 1998. |
| Långfristiga skulder | SCB BalansKnN 089 (tkr). Kolada N03046 (kr/inv) | |
| Kortfristiga skulder | SCB BalansKnN 098 (tkr). Kolada N03047 (kr/inv) | |

Kravet på absoluta värden och utveckling över tid uppfylls med tkr från SCB och kr/inv från Kolada, båda som tidsserier.

## Uppgift saknas

Ett värde som källan inte har (SCB `..`, eller ett tomt värde i Kolada) lagras som saknat och visas som "Uppgift saknas", aldrig som noll. SCB:s `-` betyder att inget finns att redovisa och lagras som noll.

## Ekonomivyns upplägg (ADR-0007)

**Översikt.** Vyn börjar med fem huvudtal, som `ekonomi.HUVUDTAL` anger: årets resultat i procent av skatter och generella statsbidrag (Kolada N03102), nettokostnadsandel (N03100), självfinansieringsgrad (N03103), soliditet inklusive pensionsåtaganden (N03002) och låneskuld per invånare (beräknad, se ovan). Varje huvudtal visar senaste året med ett värde, förändringen mot året före och en mening om vad måttet betyder, och länkar till sitt kort. Åren kan skilja sig mellan huvudtalen, eftersom källorna publicerar vid olika tidpunkter.

**Grupper som frågor.** `ekonomi.GRUPPER` har en fråga som rubrik och en kort ingress per grupp: *Går kommunen med överskott?*, *Var kommer pengarna ifrån?*, *Vad kostar verksamheten och investeringarna?*, *Hur mycket är lånat och vad är utlovat i pensioner?* och *Klarar kommunen sina betalningar?*

**Ett kort per företeelse.** Där SCB redovisar totalt och Kolada samma sak per invånare visas de på ett kort med växeln *Totalt (mnkr) / Per invånare*. Källraden gäller den variant som visas.

| Kort (totalt) | Per invånare |
|---|---|
| Årets resultat, SCB ResultKnN 120 | Kolada N03007 |
| Skatteintäkter, SCB ResultKnN 040 | Kolada N03010 |
| Generella statsbidrag och utjämning, SCB ResultKnN 050 | Kolada N03009 |
| Verksamhetens nettokostnader, SCB ResultKnN 030 | Kolada N03011 |
| Långfristiga lån, SCB BalansKnN 081 | Låneskuld per invånare (beräknad) |
| Långfristiga skulder, SCB BalansKnN 089 | Kolada N03046 |
| Kortfristiga skulder, SCB BalansKnN 098 | Kolada N03047 |
| Pensionsavsättningar, SCB BalansKnN 072 | Kolada N03044 |

Övriga nyckeltal har ett eget kort. Kortets id är måttet för varianten Totalt, och kortet nås med `#kort-<id>`, t.ex. `/ekonomi#kort-kolada-N03102`.

**Brodiagram för årets resultat** (#81, `backend/app/resultatbro.py`). I gruppen *Går kommunen med överskott?* byggs resultatet upp för ett valt år ur SCB:s resultaträkning (ResultKnN), i mnkr: skatteintäkter (040) + generella statsbidrag och utjämning (050) + verksamhetens nettokostnader (030, negativ) + finansnetto + extraordinära poster (085, visas bara när de inte är noll) = årets resultat (120). SCB har ingen rad för finansnettot, så det summeras av Kommunkollen ur finansiella intäkter (060) och finansiella kostnader (072), och det står vid steget. Saknas en del räknas skillnaden mot årets resultat fram som restposten *Övrigt inklusive finansnetto*, märkt *Beräknat av Kommunkollen*. **Kontroll:** delarna jämförs med årets resultat enligt SCB, med en tolerans på 1 tkr för avrundning, och en avvikelse visas under diagrammet. Med de nuvarande uppgifterna går alla år ihop utan avvikelse. Standardår är senaste året med fullständigt underlag, och valt år sparas som `bro=`. Diagrammet har tabellvy, textalternativ, tooltip med källa och CSV-export. Färgerna följer den divergerande skalan: tillskott blått, avdrag rött och summan grå.

**Hänger ihop med** (#81). Varje kort har en till tre länkar till de närmast relaterade korten, med en saklig mening om räknesambandet. Sambanden finns i `ekonomi.SAMBAND`, bredvid `GRUPPER`, och ett test kontrollerar att varje kort har samband och att alla id finns. Skatteintäkternas kort länkar till skatteunderlagsprognosen. En länk tar läsaren till kortet och markerar det.

## Analysverktyg i ekonomivyn

Alla val speglas i URL:en, så att en länk visar exakt samma sak:

| Parameter | Betydelse | Standard |
|---|---|---|
| `fran`, `till` | Visad period | 2022 till senaste året |
| `jamfor=2018-2024` | Jämför två år | Ingen jämförelse |
| `vy=tabell` | Visa alla nyckeltal som tabell | Diagram |
| `enhet=inv` | Visa korten med båda varianterna per invånare | Totalt (mnkr) |
| `bro=2024` | Brodiagrammets år | Senaste året med fullständigt underlag |
| `riket=1` | Visa genomsnittet för riket som jämförelselinje: ett streckat streck per år i diagrammen, kolumnerna Riket och Skillnad i tabellen, *Riket: x* i huvudtalen och rader med området Riket i CSV-exporten. Kort utan riket förklarar varför. På ett sammanslaget kort i läget Totalt står att riket finns per invånare | Av |

**Större förändring.** En jämförelse markeras som *större förändring* när värdet har ändrats med minst **10 %** jämfört med det tidigare året (relativt beloppet, även när det är negativt). Nyckeltal som själva är procentsatser, t.ex. soliditet, jämförs i procentenheter och markeras vid minst **5 procentenheter**. Tröskeln är densamma för alla nyckeltal och ändras i `frontend/src/analys.ts` (`STOR_FORANDRING`). Jämförelsen görs i löpande priser, utan justering för inflation.

**Mandatperioder.** Tidsdiagrammen har diskreta bakgrundsband för mandatperioderna, utan partifärg. En period skrivs valår–valår (t.ex. 2022–2026) och omfattar budgetåren efter valet (2023–2026), eftersom nya fullmäktige tillträder den 15 oktober valåret.

**CSV-export.** Varje kort har en CSV-knapp, som exporterar båda varianterna när kortet har växeln Totalt / Per invånare, och *Ladda ner alla som CSV* exporterar alla nyckeltal för den visade perioden. Filen har semikolon som fältavgränsare och decimalkomma (svenskt Excel). Varje rad är ett värde i källans enhet, med nyckeltal, mått-id, period, prisnivå, källa, källans publiceringsdatum, hämtdatum, version och område (Härnösand eller Riket). Ett saknat värde är en tom cell, aldrig 0.
