# Protokoll: hämtning och tolkning

Kravspec avsnitt 7, ticket #28 (kommunfullmäktige) och #29 (övriga organ och arkivet). Begrepp enligt [GLOSSARY.md](../GLOSSARY.md).

## Organ

Kommunfullmäktige (KF), kommunstyrelsen (KS), samhällsnämnden (SAM), socialnämnden (SOC) och skolnämnden (SKOL). Utskott och beredningar är egna organ och ingår inte än.

## Hämtning

- Varje organ är en egen datakälla, t.ex. `harnosand-protokoll-sam`, så att varje organ har en egen kontroll i vyn Datakällor och kan köras om för sig.
- Organets sida på harnosand.se listar innevarande års protokoll som PDF-länkar. De hämtas vid varje insamling, så att ändrat innehåll under samma adress upptäcks.
- Under rubriken "… arkiverade protokoll" finns en mapp per år. Mapparna från 2022 och framåt hämtas. En fil i arkivet hämtas bara en gång: Sitevision ger en utbytt fil en ny adress.
- Som protokoll räknas filer vars namn innehåller "Protokoll" och organets namn. Filer från utskott och beredningar tas inte med.
- Varje protokoll sparas som plattformens egen kopia med SHA-256. Nytt innehåll under samma adress blir en ny version, och den tidigare finns kvar. Samma innehåll under en ny adress sparas inte igen.
- Den första insamlingen hämtar alla protokoll sedan 2022, ungefär 270 filer och 200 MB. Med standardgränsen ett anrop per sekund tar det några minuter.

## Paragrafprotokoll

Ett paragrafprotokoll (filnamn med §, "utdrag", "direktjustering" eller "omedelbar justering") innehåller de paragrafer som justerades direkt. Hela protokollet är det primära:

- Finns bara paragrafprotokollet visas sammanträdet ur det, med en markering om att uppgifterna ersätts när hela protokollet publiceras.
- När hela protokollet finns ersätter det paragrafprotokollet i samma sammanträde. Sammanträdet behåller sitt id, så länkar fortsätter att fungera.
- Paragrafprotokollet sparas kvar som dokument. Det ersätter aldrig hela protokollet, och inte heller ett annat paragrafprotokoll från samma sammanträde.

## Tolkning

Tolkningen är reglerbaserad (ADR-0002) och gissar aldrig. Det som inte går att läsa ut lämnas tomt.

- **Sammanträdet**: datum ur sidhuvudet, plats och tid ur "Plats och tid". Ett organ kan sammanträda två gånger samma dag, så sammanträdet identifieras av datum och starttid.
- **Närvaro**, i någon av tre former:
  - en lista på första sidan med kolumner: "Namn (Parti)  Roll  Tjänstgörande för …", "Jäv § N" eller "§§ N–M",
  - en lista på första sidan med en rad per person under rubrikerna "Ledamöter", "Tjänstgörande ersättare" och "Ersättare": "Namn (Parti), ordförande", "Namn (Parti) tjänstgörande ersättare för Annan (Parti)",
  - tabellerna "Närvaro- och voteringslista" (ledamöter) och "Närvaro- och tjänstgöringslista" (ersättare), där namn och paragrafer kan vara radbrutna och kolumnrubrikerna avstavade.
- Övriga närvarande tas med när de står med parti eller i en egen kolumn med roll. Tjänstepersoner i löptext ("Namn, förvaltningschef, …") tas inte med.
- **Partitillhörighet** är den protokollet anger vid sammanträdet (ADR-0004). "(-)" visas som partilös. Saknas parti, eller står det "()", visas "parti anges inte i protokollet".
- **Behandlingar**: paragrafraden "§ N" med eventuellt diarienummer ("KS/2026-584" eller "Dnr 2026-000025"), rubriken och beslutet under "…s beslut" eller "… beslutar". Innehållsförteckningen räknas inte som behandlingar.
- **Beslutande vid en paragraf** räknas fram ur närvaron: beslutande, minus jäv vid paragrafen, och ersättare som bara tjänstgjorde vid vissa paragrafer räknas bara där.

Av de 274 protokoll som fanns i november 2026 tolkades 268. De övriga sex saknar text (inskannade), har ett annat sidhuvud eller saknar paragrafrubriker, och visas som ej tolkade.

## Avvikelser

Det som inte stämmer med protokollets egna uppgifter visas på sammanträdet, t.ex. när paragraferna inte stämmer med protokollets paragrafintervall. Ett protokoll utan sammanträdesdatum eller behandlingar räknas som ej tolkat: det visas med länk till protokollet, och kontrollen för organet får status Delvis fel.

En paragraf utan beslut (t.ex. en informationspunkt) är ingen avvikelse.

## Filter och sökning

Vyn Politik och beslut filtrerar sammanträdena på organ och år och söker bland behandlingarna på rubrik eller diarienummer. Allt speglas i adressen, så en vy går att dela. API:t: `/api/sammantraden?organ=&ar=` och `/api/behandlingar?q=&organ=&ar=` (högst 200 träffar, senaste först).

## Inspelningar och test

Inspelningarna har två protokoll per sida och årsmapp (`PROTOKOLL_URVAL=2`), så att de hålls små. Testerna och utvecklingsservern med `--inspelningar` sätter samma urval. Testerna av kommunfullmäktiges protokoll för 2026 läser hela organets sida utan arkivet.
