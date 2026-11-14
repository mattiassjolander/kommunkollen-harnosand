# Protokoll: hämtning och tolkning

Kravspec avsnitt 7, ticket #28 (kommunfullmäktige). Begrepp enligt [GLOSSARY.md](../GLOSSARY.md).

## Hämtning

- Varje organ är en egen datakälla, t.ex. `harnosand-protokoll-kf`, så att varje organ har en egen kontroll i vyn Datakällor och kan köras om för sig.
- Organets sida på harnosand.se listar innevarande års protokoll som PDF-länkar. Alla filer vars namn innehåller "Protokoll" hämtas vid varje insamling.
- Paragrafprotokoll (filnamn med §, "utdrag" eller "direktjustering") hoppas över tills vidare. De hanteras i #29, tillsammans med arkivmapparna från 2022.
- Varje protokoll sparas som plattformens egen kopia med SHA-256. Nytt innehåll under samma adress blir en ny version, och den tidigare finns kvar. Samma innehåll under en ny adress sparas inte igen.

## Tolkning

Tolkningen är reglerbaserad (ADR-0002) och gissar aldrig. Det som inte går att läsa ut lämnas tomt.

- **Sammanträdet**: datum ur sidhuvudet, plats och tid ur "Plats och tid". Ett organ kan sammanträda två gånger samma dag, så sammanträdet identifieras av datum och starttid.
- **Närvaro**, i någon av två former:
  - en lista på första sidan: "Namn (Parti)  Roll  Tjänstgörande för …", "Jäv § N" eller "§§ N–M",
  - tabellerna "Närvaro- och voteringslista, ledamöter" och "Närvaro- och tjänstgöringslista, ersättare".
- **Partitillhörighet** är den protokollet anger vid sammanträdet (ADR-0004). "(-)" visas som partilös, och saknas parti visas "parti anges inte i protokollet".
- **Behandlingar**: paragrafraden "§ N" med eventuellt diarienummer ("KS/2026-584" eller "Dnr 2026-000025"), rubriken och beslutet under "…s beslut" eller "… beslutar". Innehållsförteckningen räknas inte som behandlingar.
- **Beslutande vid en paragraf** räknas fram ur närvaron: beslutande, minus jäv vid paragrafen, och ersättare som bara tjänstgjorde vid vissa paragrafer räknas bara där.

## Avvikelser

Det som inte stämmer med protokollets egna uppgifter visas på sammanträdet, t.ex. när paragraferna inte stämmer med protokollets paragrafintervall. Ett protokoll utan sammanträdesdatum eller behandlingar räknas som ej tolkat: det visas med länk till protokollet, och kontrollen för organet får status Delvis fel.

En paragraf utan beslut (t.ex. en informationspunkt) är ingen avvikelse.
