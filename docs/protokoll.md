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

- **Protokollets sidor**: en kallelse före protokollet tolkas inte, och inte heller ett protokollsutdrag eller bilagor efter det. De börjar med en ny förstasida, med "Plats och tid", "Beslutande" och sidnummer 1. En andra sittning samma dag fortsätter sidnumreringen och hör till protokollet.
- **Diarienummer** där textlagret delat förkortningen ("S AM/2026-131") läses som "SAM/2026-131".

Av de 274 protokoll som fanns i november 2026 tolkas 271. Tre visas som ej tolkade:

- Samhällsnämnden 2026-04-30 och 2026-05-28 är inskannade och saknar text. En PDF räknas som inskannad när första sidan saknar text, även om enstaka senare sidor har det.
- Samhällsnämnden 2022-06-16: kommunens fil har bara första sidan av protokollets 58. Det står i avvikelserna ("PDF:en har 1 av protokollets 58 sidor").

Ett protokoll tolkas när det är nytt eller ändrat. Efter en förbättrad tolkning tolkas de lagrade protokollen om med `python -m app.tolka_om` (docs/drift.md). Sammanträdena behåller sina id.

## Yrkanden, voteringar och reservationer

Läses per behandling ur avsnitten "Yrkanden", "Propositionsordning" och "Reservation(er)" och ur voteringslistorna. Allt visas på behandlingens sida och i `GET /api/sammantraden/{id}/behandlingar/{paragraf}` (`yrkanden`, `propositionsordning`, `voteringar`, `reservationer`).

- **Yrkanden**: en mening per yrkande, med de personer som står med parti ("Namn (SD) yrkar …").
- **Reservationer**: personer med parti, och partier som reserverar sig ("Sverigedemokraterna reserverar sig" → SD).
- **Voteringar**, i protokollets ordning: ja- och nejförslaget ur propositionen ("Ja för X och nej för Y", "Ja = X. Nej = Y.", "den som vill att X röstar ja"), siffrorna som texten anger och ordförandens konstaterande ("finner att …").
- **Voteringslistan** ger varje röst. Den läses i fyra former:
  - kryss under Ja/Nej/Avstår med parti och tjänstgörande ersättare i egna kolumner, ibland med flera voteringar bredvid varandra i närvaro- och voteringslistan ("Vot § 96", "Vot § 98"),
  - en tabell med "Ledamot/tjänstgörande ersättare" och paragrafkolumner,
  - en numrerad lista "Namn och parti, Röst" med "X ersatt av Y",
  - en lista "Namn, Röst" med JA och NEJ och "tjänstgörande ersättare för Y".

  Listor efter paragrafen eller i en bilaga knyts till paragrafen genom "§ N" i tabellhuvudet.
- **Kolumnerna** läses ur kryssen, inte ur rubrikerna. Rubrikerna kan stå flera tecken vid sidan av kryssen, vara avstavade ("Part"/"i", "När"/"var"/"o") eller stå på flera rader. Kryssen samlas i klungor som tilldelas kolumnerna i ordning. På en ny sida kan indragningen vara en annan, så klungorna räknas ur raderna på tabellens vanligaste indragning.
- Den som röstade är den tjänstgörande ersättaren när en sådan står för paragrafen ("Tom stol §§ 1–4" och paragrafintervall avgör). En ruta kan ha flera ersättare vid olika paragrafer ("Brendan Mc Carthy §§ 57-61", "Hans Rosengren § 66"). En ersättare som tjänstgjorde på en vakant plats visas utan ersatt ledamot. En ersättare från ett annat parti står med sitt eget parti ("Keith Bryant (V)" på en plats för S).
- En tom stol är **frånvarande**, även om listan har ett kryss på raden: protokollets text räknar platsen som tom. "Ej röstat" är frånvarande.
- Ett streck utan kryss är **avstår** i en lista utan Avstår-kolumn och **frånvarande** i en lista med Avstår-kolumn.
- **Vinnaren** (`ja`/`nej`) läses ur ordförandens konstaterande genom att jämföra det med förslagen. Den räknas aldrig fram ur siffrorna: en minoritet kan begära återremiss och vinna med färre röster. Går den inte att avgöra visas konstaterandet.
- Röster per parti summeras ur listan och visas med förkortning och siffror, aldrig bara med färg.
- När listan och texten anger olika siffror visas listan som den står, och skillnaden står i avvikelserna: "§ 112, votering 1: voteringslistan har 20 ja, 18 nej, protokollets text 21 ja, 18 nej". Avstår och frånvarande jämförs bara när texten anger dem.

I hela arkivet (november 2026, 116 voteringar) stämmer listan med texten i 104. I sex anger protokollet olika siffror i texten och listan, eller har kryss under både Ja och Nej för samma ledamot. Sex saknar lista i protokollet: en sluten omröstning, ett digitalt sammanträde där bara utfallet antecknades, och listor som inte finns i PDF:ens textlager.

Rösterna knyts till ledamotsregistret på namn. Namn som bara förekommer i voteringslistor, eller stavas annorlunda där än i närvarolistan, länkas inte.

## Avvikelser

Det som inte stämmer med protokollets egna uppgifter visas på sammanträdet, t.ex. när paragraferna inte stämmer med protokollets paragrafintervall. Ett protokoll utan sammanträdesdatum eller behandlingar räknas som ej tolkat: det visas med länk till protokollet, och kontrollen för organet får status Delvis fel.

En paragraf utan beslut (t.ex. en informationspunkt) är ingen avvikelse.

## Filter och sökning

Vyn Politik och beslut filtrerar sammanträdena på organ och år och söker bland behandlingarna på rubrik eller diarienummer. Allt speglas i adressen, så en vy går att dela. API:t: `/api/sammantraden?organ=&ar=` och `/api/behandlingar?q=&organ=&ar=` (högst 200 träffar, senaste först).

## Inspelningar och test

Inspelningarna har två protokoll per sida och årsmapp (`PROTOKOLL_URVAL=2`), så att de hålls små. Testerna och utvecklingsservern med `--inspelningar` sätter samma urval. Testerna av kommunfullmäktiges protokoll för 2026 läser hela organets sida utan arkivet.
