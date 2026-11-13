# Täckning: ekonomiska nyckeltal (kravspec 3.1 och 3.3)

Vilken källa och vilket mått som används för varje punkt i kravspecens avsnitt 3.1 och 3.3, eller att uppgiften saknas i fas 1. Katalogen finns i `backend/app/ekonomi.py`. Ändras den ska tabellen uppdateras samtidigt.

**Källor**
- **Kolada** (api.kolada.se v3): nyckeltal för kommunen (inte koncernen) i kr/inv eller procent.
- **SCB** (statistikdatabasen, räkenskapssammandraget OE0107A): resultat- och balansräkning i tkr. Tabellerna `ResultKnN`, `BalansKnN` och `SkatteIntKnN`. Ekonomivyn visar tkr som mnkr. Det lagrade värdet är källans.

**Prisnivå.** Alla kronbelopp är i löpande priser. Varken Kolada eller SCB:s räkenskapssammandrag publicerar fasta priser för de här måtten. Kr/inv gör åren jämförbara för befolkningsförändringar, men inte för inflation.

**Historik.** Hela tidsserien hämtas: SCB från 1998, och Kolada så långt tillbaka som nyckeltalet finns. Vyn börjar som standard 2022.

## 3.1 Ekonomisk översikt

| Krav | Källa och mått | Anmärkning |
|---|---|---|
| Årets resultat | Kolada N03007 (kr/inv), N03102 (% av skatt och generella statsbidrag). SCB ResultKnN 120 (tkr) | |
| Budgeterat resultat | Saknas i fas 1 | Finns bara i kommunens budgetdokument (årsplan). Kommer med budget mot utfall (3.2). |
| Resultatprognos | Saknas i fas 1 | Finns bara i delårsrapporterna. Kommer med budget mot utfall (3.2). |
| Skatteintäkter | SCB ResultKnN 040 (tkr). Kolada N03010 (kr/inv) | |
| Generella statsbidrag | SCB ResultKnN 050 (tkr) och SkatteIntKnN 080 (brutto). Kolada N03009 (kr/inv) | Redovisas tillsammans med utjämningen. Generella bidrag från staten finns som egen post (SkatteIntKnN 150) men visas inte än. |
| Riktade statsbidrag | Saknas i fas 1 | Ingår i verksamhetens intäkter och redovisas inte separat per kommun i Kolada eller i de SCB-tabeller som används. Kan komma från SCB:s VerksInt eller årsredovisningen. |
| Utjämningsbidrag och utjämningsavgifter | SCB SkatteIntKnN 080 (bidrag inkl. generella statsbidrag) och 160 (avgifter), tkr | Uppdelning per utjämningssystem finns i tabellen och kan läggas till. |
| Verksamheternas nettokostnader | SCB ResultKnN 030 (tkr). Kolada N03011 (kr/inv), N03100 (% av skatt och generella statsbidrag) | |
| Investeringar | Kolada N03132 (nettoinvesteringar, kr/inv), N03103 (självfinansieringsgrad, %) | Kolada anger 2027 som nästa publicering för N03132. Framtida datum visas inte som publicering. |
| Låneskuld | SCB BalansKnN 081 (långfristiga lån i banker och kreditinstitut, tkr) | Den kortfristiga delen av lånen ingår i kortfristiga skulder och syns inte här. |
| Pensionsåtaganden | SCB BalansKnN 072 (avsättningar i balansräkningen, tkr). Kolada N03044 (avsättning, kr/inv), N03048 (förpliktelser utanför balansräkningen, kr/inv) | |
| Likviditet | SCB BalansKnN 065 (likvida medel, tkr). Kolada N03105 (kassalikviditet, %) | |
| Soliditet | Kolada N03002 (inkl. pensionsåtaganden) och N03106 (exkl.) | |
| Kassaflöde | Saknas i fas 1 | Kassaflödesanalysen finns bara i årsredovisningen. |
| Kostnad per invånare | Kolada N03011 (nettokostnader kr/inv) | Övriga kr/inv-mått ovan kompletterar. |

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
