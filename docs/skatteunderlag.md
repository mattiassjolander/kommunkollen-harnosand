# SKR:s skatteunderlagsprognos

Datakällan `skr-skatteunderlagsprognos` (#61) hämtar SKR:s prognos av skatteintäkter och generella bidrag och
utjämning för Härnösand. Budgetarbetet utgår från den.

## Hämtning

1. Sidan [Skatteunderlagsprognoser](https://skr.se/ekonomiochbudgetplanering/skatteunderlagsprognoser.8271.html)
   läses. Länkar vars text börjar med "Prognosunderlag kommuner" och anger ett cirkulär (t.ex. "cirkulär 26:28")
   är prognosfiler. Regionernas filer tas inte med.
2. Varje fil hämtas. Länktexten säger "(xlsx)" men filerna är `.xlsm` med makron.
3. SKR har bara de senaste årens cirkulär på sidan, så äldre prognoser än 2026 finns inte att hämta.

## Omräkning för Härnösand

Filen visar en kommun i taget, vald med kommunkoden i `Prognosunderlag!B1`. Värdena är formler som Excel räknar
om när koden ändras. Så här görs det utan Excel:

1. openpyxl sätter `Prognosunderlag!B1` till `2280` och sparar arbetsboken som `.xlsx`, utan makron.
2. LibreOffice (`soffice --headless --convert-to xlsx`) räknar om alla formler, med en tillfällig profil där
   makron är avstängda och omräkning vid inläsning alltid görs.
3. Resultatet läses med openpyxl (`data_only`). Raderna hittas på etiketten i kolumn A och åren på raden
   "Belopp i tkr", inte på fasta celler. B1 kontrolleras mot kommunkoden.

Det som sparas per cirkulär, i tkr per år: skatteintäkter, inkomstutjämning, kostnadsutjämning,
regleringsbidrag/-avgift, strukturbidrag, införandebidrag, LSS-utjämning, summa intäkter, slutavräkning per år,
fastighetsavgift och summa intäkter inklusive avräkning och fastighetsavgift. Dessutom invånarantalet enligt
riksprognosen, skattesatsen prognosen räknar med (bladet Data, kolumn `Utdeb åå`) och publiceringsdatumet (J1).

Facit för cirkulär 26:28 är kontrollerat mot Excel efter omräkning med kommunkoden 2280 och finns i
`backend/tests/test_skatteunderlag.py`.

## Versioner

- Samma cirkulär med samma fil (sha256) räknas inte om.
- Ändrad fil med samma värden: bara källhänvisningen uppdateras.
- Ändrade värden: en ny version sparas, och den tidigare finns kvar.

Saknas en förväntad rad blir insamlingen *delvis fel* med filnamn, cirkulär och raden som saknas. Övriga
cirkulär sparas ändå.

## Visning

`/ekonomi/skatteunderlag` visar den senaste prognosen i mnkr och ett linjediagram över summa intäkter med en
linje per cirkulär, så att det syns hur prognosen för samma år har ändrats. API: `GET /api/skatteunderlagsprognoser`.
