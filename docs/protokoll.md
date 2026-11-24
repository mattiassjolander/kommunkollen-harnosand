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

## Sammanträdesplaner

Datakällan "Sammanträdesplaner" (`harnosand-sammantradesplaner`, #68) läser tabellerna med sammanträdesdagar
på de fem organens sidor. Varje tabell har kolumnerna Månad, Datum och Tid, och året står i tabellens rubrik
eller i rubriken ovanför. Kommunstyrelsen har två tabeller (2026 och 2027).

Fritexten i tabellerna tolkas:

| Text | Tolkning |
| --- | --- |
| "Inställt" eller "Inställd" i Tid | Sammanträdet är inställt |
| "Inställd" i Datum, utan dag | Månadens sammanträde är inställt. Har sammanträdet tidigare haft ett datum behåller det datumet |
| "OBS tiden: 11.00" | Ändrad starttid |
| "(8/9 ställs in) 15, 29" | 8 september är inställt, 15 och 29 är planerade |
| "5, 26" | Två sammanträden i månaden |
| Annan text | Sparas som en anmärkning på raden och ger *delvis fel* |

Varje rad blir ett planerat sammanträde i tabellen `sammantrade`, med plan_*-kolumnerna ifyllda och utan
protokoll. Raden identifieras av organet och datumet. En ändrad tid eller status blir en ny version i
`planversion` (en reviderad uppgift) och sammanträdet behåller sitt id. Ett sammanträde som försvinner från
sidan, för ett år som sidan fortfarande visar, markeras som borttaget ur planen och finns kvar.

**Koppling till protokollen.** När ett protokoll läses in kopplas det till det planerade sammanträdet med
samma organ och datum, i stället för att skapa ett nytt. Har organet ett planerat sammanträde och ett
protokoll den dagen kopplas de oavsett starttid, eftersom ett möte kan börja senare än planerat (#107).
Skolnämnden planerade till exempel 2026-10-01 kl. 08.15, och protokollet anger 11.05. Finns flera sammanträden
samma dag avgör tiden: det sammanträde vars tid ligger närmast, högst 60 minuter ifrån. Fullmäktige hade
till exempel två sammanträden 2026-10-26: planens 11.00 gäller protokollet som började 11.10, och protokollet
från 13.15 blir ett eget sammanträde. Kopplades planen till dagens enda protokoll och kommer sedan ett
protokoll som passar planens tid, flyttas planen dit. Finns protokollet redan när planen läses kopplas planen
till det på samma sätt. Ett hållet sammanträde visar protokollets tid, också i kalendern, och planens tid
finns kvar i planens versioner.

Dubbletter från före #107 (ett planerat sammanträde utan protokoll och protokollet samma dag) slås ihop med
`python -m app.sla_ihop_planer` (docs/drift.md).

**Jämförelse med besluten.** Organen beslutar om planen i protokollen, med rubriker som "Sammanträdestider
2027" eller "Socialnämndens sammanträdesdagar 2026". Ur besluten läses att-satser om organets egna sammanträden:

- "att kommunstyrelsen sammanträder 08.15 följande datum: 2 februari, 6 april …" ger hela planen för året.
  Förslag till ett annat organ och arbetsutskottets datum räknas inte.
- "att sammanträdet den 17 juni ställs in" tar bort ett datum.
- "att kommunstyrelsens sammanträde 8 september 2026 senareläggs till 15 september 2026" (även "flyttas" och
  "tidigareläggs") flyttar ett datum.

Besluten gäller i datumordning. Webbsidans planerade sammanträden jämförs med datumen enligt besluten, och
skillnaderna (bara på webbsidan, bara i beslutet och annan tid) visas på sidan Planer för redaktionen. De visas
inte publikt. Anger inget beslut datumen, t.ex. "att anta förslag till sammanträdestider", jämförs planen inte.

**Planen ur besluten när webbsidan saknar tabell (#99).** Kommunen publicerar ofta tabellen för nästa år
först i december, men organet har beslutat om sammanträdestiderna tidigare (fullmäktige 2026-09-28 § 130 om
2027). För år från och med i år som webbsidan inte har någon plan för blir datumen enligt besluten planerade
sammanträden, med källan `beslut` och en hänvisning till paragrafen (`plan_kalla`,
`plan_beslut_sammantrade_id` och `plan_beslut_paragraf`). Samma regler gäller som i jämförelsen: senare beslut
flyttar eller ställer in, och ett flyttat sammanträde behåller sitt id med ett nytt datum. Planen ur besluten
räknas om efter insamling, omtolkning och när en rättelse av ett beslut publiceras. Ingen granskning behövs,
eftersom beslutet redan är publicerat.

När webbsidan publicerar tabellen för året tar den över: samma sammanträde (samma UID i kalendern, högre
SEQUENCE) får en ny version med källan `webbsidan`, och datum som bara fanns i beslutet blir borttagna ur
planen. Därefter läses inte besluten för året. Tidigare år påverkas inte.

Kalendern och ics-flödet märker sådana sammanträden "Enligt beslut i protokollet (kommunfullmäktige
2026-09-28 § 130)" med länk till paragrafen. Sidan Planer visar källan per sammanträde och "Ingen plan på
webbsidan än" för år som bara har beslut.

Planerade sammanträden räknas inte i statistiken och listas inte bland sammanträdena med protokoll.

## Kalender och ics-flöden

Sidan **Kalender** (`/kalender`, #68) visar sammanträdena för de fem organen:
- kommande sammanträden i en lista, och de senaste 12 månaderna under "Tidigare sammanträden";
- en månadsvy;
- filter per organ;
- inställda och borttagna sammanträden överstrukna.

Organ, vy, månad och valt sammanträde står i URL:en.

**Flöden** (`app/kalender.py`), öppna utan inloggning eftersom kalenderappar inte kan logga in:

| Adress | Innehåll |
| --- | --- |
| `/kalender/alla.ics` | Alla fem organen |
| `/kalender/kommunfullmaktige.ics`, `kommunstyrelsen`, `samhallsnamnden`, `socialnamnden`, `skolnamnden` | Ett organ |
| `/kalender/sammantraden/<id>.ics` | Ett sammanträde, som fil att ladda ner |

Flödena innehåller de kommande sammanträdena och de senaste 12 månaderna. Ett sammanträde utan datum (en
månad som bara anges som inställd) ingår inte. Händelserna:

- **UID:** `sammantrade-<id>@kommunkollen-harnosand`, stabilt eftersom sammanträdet behåller sitt id när
  planen ändras och när protokollet kopplas.
- **SEQUENCE:** planens version minus ett, plus ett när protokollet har kommit. En ändrad tid ger alltså ny
  DTSTART och högre SEQUENCE med samma UID.
- **Tid:** DTSTART och DTEND med `TZID=Europe/Stockholm` och en VTIMEZONE. Ett hållet sammanträde har
  protokollets start- och sluttid. Ett planerat sammanträde har planens starttid, och sluttiden är starttiden
  plus medianlängden för organets sammanträden enligt protokollen (3 timmar för fullmäktige och 4 för övriga
  utan historik). Beskrivningen säger då att sluttiden är ungefärlig. Utan starttid blir det en heldag.
- **Plats:** protokollets, annars kallelsens, annars platsen i organets senaste protokoll. I det sista fallet
  säger beskrivningen att platsen är antagen.
- **Status:** ett inställt eller borttaget sammanträde finns kvar med `STATUS:CANCELLED` och "Inställt:" eller
  "Borttaget ur planen:" i titeln.
- **Beskrivning och URL:** beskrivningen har länkar till
  - protokollet i Kommunkollen efter sammanträdet, annars till sammanträdet i kalendern;
  - kallelsen eller kungörelsen och handlingarna;
  - för fullmäktige webb-tv före sammanträdet och inspelningen efter;
  - sammanträdesplanen på harnosand.se.

Raderna avslutas med CRLF och viks vid 75 oktetter utan att dela ett UTF-8-tecken. Testerna läser flödena med
biblioteket icalendar. I e2e-tester och lokalt låser `KOMMUNKOLLEN_IDAG` dagens datum. nginx och Vite skickar
`/kalender/….ics` till backend.

## Kallelser och webbsändningar

Datakällan Sammanträdesplaner läser också kallelserna på organens sidor och fullmäktiges sida för webb-tv
(`app/sources/kallelser.py`, #68).

- **Kallelser:** länkarna till kungörelser (fullmäktige), kallelser (nämnderna) och handlingar
  (kommunstyrelsen och fullmäktige). Datum och klockslag läses ur filnamnet, t.ex. "Kungörelse
  kommunfullmäktige 2026-10-26 kl. 11.00" och "Handlingar kommunfullmäktige 2026-10-26, 11 00", och
  filstorleken ur länktexten. Utskott och beredningar ingår inte.
- **Plats:** läses ur kallelsens första sida ("… kallas härmed till sammanträde 2026-10-26 kl. 11:00 - i
  Rådhuset - KF-salen."). Bara kallelser på högst 2 MB hämtas, eftersom kallelser med handlingar kan vara
  flera hundra MB. En läst kallelse hämtas inte igen. En kallelse som byts ut får en ny adress och läses då.
- **Koppling:** kallelser kopplas till sammanträdena när kalendern läses: samma organ och datum. Har organet
  flera sammanträden samma dag går en kallelse med klockslag till det närmaste (fullmäktige 2026-10-26).
  Den senast publicerade kallelsen gäller.
- **Webbsändningar:** sidan för webb-tv har en länk per sammanträde i fullmäktige ("Sammanträde
  2026-10-26"), till qcnl.tv från 2026 och play.quickchannel.com för 2024–2025. Länken kopplas till
  fullmäktiges sammanträden samma datum. Före sammanträdet länkar kalendern till sidan för webb-tv.

Ett extra sammanträde som bara finns som kallelse, utan plan eller protokoll, visas inte i kalendern än.

## Paragrafprotokoll

Ett paragrafprotokoll (filnamn med §, "utdrag", "direktjustering" eller "omedelbar justering") innehåller de paragrafer som justerades direkt. Hela protokollet är det primära:

- Finns bara paragrafprotokollet visas sammanträdet ur det, med en markering om att uppgifterna ersätts när hela protokollet publiceras.
- När hela protokollet finns ersätter det paragrafprotokollet i samma sammanträde. Sammanträdet behåller sitt id, så länkar fortsätter att fungera.
- Paragrafprotokollet sparas kvar som dokument. Det ersätter aldrig hela protokollet, och inte heller ett annat paragrafprotokoll från samma sammanträde.

## Tolkning

Tolkningen är reglerbaserad (ADR-0002) och gissar aldrig. Det som inte går att läsa ut lämnas tomt.

- **Sammanträdet**: datum ur sidhuvudet, plats och tid ur "Plats och tid". Ett organ kan sammanträda två gånger samma dag, så sammanträdet identifieras av datum och starttid.
- **Närvaro**, i någon av tre former:
  - en lista på första sidan med kolumner: "Namn (Parti)  Roll  Tjänstgörande för …", "Jäv § N" eller "§§ N–M". Namnkolumnen kan sakna parti och bära roll, paragrafer och ersättning, radbrutet över flera rader: "Glenn Sehlin, §§ 131-138, 140-143", "Hans Rosengren, ersätter Ann Kristine Elfvendal § 138 samt Monica Fällström § 139",
  - en lista på första sidan med en rad per person under rubrikerna "Ledamöter", "Tjänstgörande ersättare" och "Ersättare": "Namn (Parti), ordförande", "Namn (Parti) tjänstgörande ersättare för Annan (Parti)",
  - tabellerna "Närvaro- och voteringslista" (ledamöter) och "Närvaro- och tjänstgöringslista" (ersättare), där namn och paragrafer kan vara radbrutna och kolumnrubrikerna avstavade. Tabellen kan fortsätta på nästa sida utan rubrik.
- Paragrafer vid namnet ("Andreas Sjölander §§ 57-61, 63-68, 70-76") är de paragrafer personen var beslutande vid. En ersättare som tjänstgjorde för flera ledamöter vid olika paragrafer får en post per tjänstgöring. Ledamotssidan slår ihop dem till en rad per sammanträde.
- Övriga närvarande tas med när de står med parti eller i en egen kolumn med roll. Tjänstepersoner i löptext ("Namn, förvaltningschef, …") tas inte med.
- **Partitillhörighet** är den protokollet anger vid sammanträdet (ADR-0004). "(-)" visas som partilös. Saknas parti, eller står det "()", härleds partiet och markeras "Härlett" med källan: i första hand samma protokoll (voteringslistan eller "för Namn (S)"), annars närvarolistan i det närmaste sammanträdet där personen har ett parti. Går det inte att härleda visas "parti anges inte i protokollet". En publicerad rättelse går före det härledda partiet. En publicerad fastställd partitillhörighet (ADR-0006, docs/ledamoter.md) gäller före protokollets uppgift och efter en rättelse, och då härleds inget parti. Ändrar den protokollets uppgift markeras det "Fastställt av redaktionen".
- **Behandlingar**: paragrafraden "§ N" med eventuellt diarienummer ("KS/2026-584" eller "Dnr 2026-000025"), rubriken och beslutet under "…s beslut" eller "… beslutar". Innehållsförteckningen räknas inte som behandlingar.
- **Läsordning** (#88): en ensam "§ N"-rad som står sist på en sida i löptexten men direkt före rubriken i layouttexten är lagrad sist i PDF:ens textflöde. Raden flyttas till sidans början innan paragraferna delas upp. Inget annat flyttas.
- **Motkontroll mot ärendelistan** (#88): när protokollet har en ärendelista eller innehållsförteckning jämförs varje rubrik med den, utan hänsyn till mellanslag, radbrytningar, skiljetecken, bindestreck mot tankstreck och versaler. Saknas rubriken i paragrafen tas den ur ärendelistan och märks "Rubriken hämtad ur ärendelistan". Skiljer sig rubrikerna åt skrivs en avvikelse: är paragrafens rubrik längre eller kortare än ärendelistans, eller liknar den inte alls, har inläsningen troligen fel. Liknar den ärendelistans men skiljer sig på något ställe står det så i protokollet. Protokoll som lästs med OCR kontrolleras inte, eftersom OCR ofta läser "§ 45" som "845".
- **Rubriken avgränsas med ärendelistan** (#124): när ingen känd underrubrik följer rubriken (paragrafen saknar underrubriker, eller de fyra första raderna räckte inte) och paragrafens första rader tillsammans är ärendelistans rubrik, på en radgräns, blir de raderna rubriken. Det rättar både en rubrik som fått med paragrafens text ("Allmänhetens frågestund … Inga frågor har inkommit …") och en rubrik som fortsätter på nästa rad. Har paragrafen inga underrubriker alls sparas resten som paragrafens text (`paragraftext`) och visas på behandlingen, utan understreck. Det är inget beslut. Rubriker där protokollet har fler ord än ärendelistan och en underrubrik följer ändras inte. "Beslut" räknas som underrubrik.
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

## Protokoll som bara innehåller bilder (OCR)

Vissa protokoll publiceras som en PDF där varje sida är en bild, utan text (inskannade, eller digitala protokoll som plattats till bilder). Då renderas sidorna i 400 dpi och läses med Tesseract och svensk språkdata (`ocr.py`). Ur ordens placering byggs samma löptext och layouttext som ur en vanlig PDF, och resten av tolkningen är densamma.

Vanliga läsfel rättas bara i OCR-text: paragraftecknet läses som 8, 5, 3, & eller $ ("(SD) 8 45", "$8 43 — 60"). En paragrafrubrik på egen rad ("843", "5849 SAM/2026-116") rättas bara när protokollets paragrafintervall är känt från första sidan, och numret blir den del av siffrorna som ligger inom intervallet. Intervallet läses trots dubbla bindestreck och siffror som lästs som bokstäver ("Paragrafer 62 –- TT" blir §§ 62–77).

Sammanträdet märks "Läst med OCR, ej granskad". Avvikelsen "PDF:en saknar text och har lästs med OCR" står kvar på avvikelsesidan, så att kommunen kan ombes publicera en PDF med text. Finns inte Tesseract blir protokollet ej tolkat, som tidigare.

Lokalt: installera Tesseract (Windows: `winget install UB-Mannheim.TesseractOCR`) och lägg `swe.traineddata` från tessdata_best i en mapp som `TESSDATA_PREFIX` pekar på. Imagen och CI hämtar samma fil, låst med kontrollsumma.

## Avvikelser

Det som inte stämmer med protokollets egna uppgifter visas på sammanträdet, t.ex. när paragraferna inte stämmer med protokollets paragrafintervall. Ett protokoll utan sammanträdesdatum eller behandlingar räknas som ej tolkat: det visas med länk till protokollet, och kontrollen för organet får status Delvis fel.

En paragraf utan beslut (t.ex. en informationspunkt) är ingen avvikelse.

Fliken Avvikelser samlar alla protokoll med avvikelser eller publicerade rättelser, per organ och årsintervall, med länk till originalprotokollet och CSV-export. Avvikelserna delas in så här (`avvikelser.py`):

| Kategori | Avvikelser | Var felet troligen finns |
|---|---|---|
| Motsägelse i protokollet | Voteringslistan stämmer inte med protokollets text, eller en paragrafs rubrik skiljer sig från ärendelistan | I protokollet |
| Felskrivet i protokollet | En paragrafrubrik är felskriven, t.ex. "Ko§ 168" | I protokollet |
| Ofullständigt dokument | PDF:en saknar sidor eller text, eller bara paragrafprotokoll finns | I protokollet |
| Paragraferna stämmer inte | Paragraferna stämmer inte med paragrafintervallet, eller samma paragraf förekommer flera gånger | I protokollet eller i tolkningen |
| Kunde inte läsas av plattformen | Övrigt, t.ex. att närvarolistan eller en rubrik inte hittades, eller att en rubrik troligen är fel läst enligt ärendelistan | I tolkningen |

Indelningen är en hjälp att välja vad som ska kontrolleras mot originalet, inte ett påstående om att kommunens protokoll är fel. API:t: `/api/avvikelser?fran=&till=&organ=`.

Varje publicerad rättelse listas för sig under protokollet (#74): vad som rättats, paragrafen, vad protokollet eller tolkningen sa, det rättade värdet och motiveringen. Listan filtreras på var felet finns: i protokollet, i inläsningen eller inte angivet (filtret `felet` i URL:en). Rättelser av fel i protokollet är felaktigheter i protokollet, och de räknas också som avvikelser i protokollet. CSV-exporten har en rad per rättelse.

## Ärenden

Behandlingar i olika organ kopplas till samma ärende (ADR-0003). Ärendet är plattformens egen entitet, och diarienumren är egenskaper hos det. Reglerna är framtagna ur hela arkivet:

- **Diarienummer.** Samma diarienummer i samma diarieserie kopplar automatiskt. Serien är prefixet (`KS/2026-113`), och utan prefix organets egen serie. Kommunfullmäktige använder kommunstyrelsens serie. Ett diarienummer som återkommer vid sex eller fler sammanträden i ett organ är stående och kopplar ingenting.
- **Hänvisning i beslutsunderlaget** ("Protokollsutdrag kommunstyrelsen 2026-02-24 § 31"). En hänvisning uppåt, från KS till en nämnd eller från KF till KS, kopplar automatiskt när rubrikerna liknar varandra. Annars blir den ett förslag.
- **Övriga hänvisningar**, till samma nivå, nedåt eller utan organ, blir förslag.
- **Samlingspunkter och fasta punkter** (delegationsbeslut, meddelanden, ärenden för kännedom, val av justerare, valärenden, frågestund …) kopplas aldrig.

Förslagen ligger i en kö (`/redaktion/kopplingar`), där en redaktör bekräftar eller avvisar dem (ADR-0002). Vyn har flikarna Förslag, Bekräftade och Avvisade och filtret Mina beslut. En redaktör kan ändra ett beslut åt alla håll, också tillbaka till förslag, med obligatorisk motivering. Ingen andra granskning behövs, eftersom kopplingar beslutas av en redaktör ensam. Varje beslut sparas i en historik som aldrig skrivs över (`kopplingsbeslut`, #77), och beslut från före historiken blev dess första post. Ärendevyn länkar redaktören från en koppling till dess beslut. Automatiska kopplingar bygger på diarienumret och beslutas inte. Kopplingarna och ärendena räknas om efter varje insamling som gav nya eller ändrade protokoll, och efter `python -m app.tolka_om`. Redaktörens beslut står kvar, och ett ärende behåller sitt id. Kopplingarna pekar ut behandlingen med sammanträde och paragraf, eftersom behandlingarna skapas om vid omtolkning.

Slutligt beslut är det senaste beslutet i ärendet, om det inte föreslår kommunfullmäktige eller kommunstyrelsen något.

API:t: `/api/arenden/{id}`, ärendet på `/api/sammantraden/{id}/behandlingar/{paragraf}` (`arende`), `/api/kopplingar?status=forslag` (med `&mina=true` bara egna beslut) samt `POST /api/kopplingar/{id}/bekraftelse`, `/avvisning` och `/beslut` med `{status, motivering}` för att ändra ett beslut (redaktör). Varje koppling har `historik`.

## Rättelser

En redaktör kan rätta en automatiskt tolkad uppgift: en behandlings rubrik, beslut, diarienummer eller typ, en röst i en votering, partiet för en person i närvarolistan, eller en motions motionärer (som också en utgivare kan skriva, se Motioner nedan). Formuläret finns längst ned på behandlingen. Partiet kan också rättas från sammanträdet, för alla i närvarolistan. Rättelsen kräver en motivering, till exempel var i protokollet uppgiften står.

Statusflödet är utkast → granskad → publicerad (kravspec 18). En utgivare som inte skrev rättelsen granskar och publicerar den under fliken Rättelser. Det gäller också den som har båda rollerna. Redaktören kan ändra och ta bort sitt eget utkast. En granskad eller publicerad rättelse ändras inte på plats (#74): redaktören skapar en ny version från den, förifylld med värdet och var felet finns och med en motivering till ändringen. Den nya versionen går igenom granskning och publicering som vanligt, och en annan person med rollen utgivare godkänner den. När den publiceras ersätter den den gamla, som får status ersatt och bevaras. Bara en ny version åt gången kan vänta på granskning. En rättelse utan valet av var felet finns kompletteras på samma sätt, och avvikelsesidan länkar redaktören dit. En utgivare kan återkalla en publicerad rättelse direkt, med obligatorisk motivering (status återkallad). Då gäller tolkningen igen. Fliken Rättelser visar ersatta och återkallade versioner som historik, och läsaren ser tidigare publicerade versioner när markeringen fälls ut. En ny publicerad rättelse av samma uppgift ersätter den tidigare. API: `POST /api/rattelser/{id}/versioner` med `{nytt, motivering, felet_i}` och `POST /api/rattelser/{id}/aterkallelse` med `{motivering}`. Alla listor (statistik, ärenden, motioner, återkommande och kommande ärenden, jämförelsen med sammanträdesplanerna) läser behandlingarna med publicerade rättelser genom `behandlingar.py`. En publicerad rättelse av en rubrik eller ett diarienummer räknar om kopplingarna direkt (ADR-0003).

Redaktören anger i varje rättelse var felet finns (#74): **i protokollet** (protokollet saknar eller anger fel uppgift) eller **i inläsningen** (plattformen läste eller tolkade fel). Valet är obligatoriskt. Saknas partiet i närvarolistan är förvalet "i protokollet". Utgivaren ser valet när rättelsen granskas, och redaktören kan ändra det i sitt utkast. Ett protokoll med minst en publicerad rättelse av fel i protokollet märks *Innehåller felaktigheter* på sammanträdessidan och i protokollistan, med länk till listan över felaktigheterna under Avvikelser (`felaktigheter` i API:t för sammanträdena). Rättelser av fel i inläsningen ger ingen markering. Rättelser från före #74 saknar valet, visas som *Inte angivet* och ger ingen markering förrän det har angetts.

Rättelsen sparas bredvid tolkningen och läggs på när uppgiften läses. Därför bevaras den vid en ny insamling och vid omtolkning. Den pekar ut uppgiften med sammanträde och paragraf, och med namn och votering för en röst. Läsaren ser den rättade uppgiften på behandlingen, sammanträdet och ärendet, med markeringen "Rättad av redaktionen" och vad tolkningen sa. Röstsiffrorna per parti räknas med den rättade rösten. Ledamotssidorna visar också rättade partier. Sökningen och kopplingen av ärenden använder tolkningen.

API:t: `GET /api/rattelser?status=` (redaktör eller utgivare), `POST /api/rattelser`, `PATCH` och `DELETE /api/rattelser/{id}` (redaktören som skrev utkastet), `POST /api/rattelser/{id}/granskning` och `/publicering` (utgivare). Testinloggningen tar flera roller, t.ex. `/api/auth/test/redaktor+utgivare`.

## Statistik

Fliken Statistik visar hur många behandlingar protokollen innehåller per år, organ och behandlingstyp, för ett valt organ och årsintervall (till exempel 2024–2025 eller 2025–2025). Organ och år speglas i adressen. Diagrammet staplar typerna per år, tabellen visar år och organ, och tabellen går att ladda ned som CSV.

Typen läses ut med regler ur rubrik och beslut (`behandlingstyper.py`), i den här ordningen:

| Typ | Regel |
|---|---|
| Motion | Rubriken börjar med "Motion", "Svar på motion" eller "Svar på remiss angående motion" |
| Medborgarförslag | Rubriken börjar med "E-förslag" eller "Medborgarförslag". I Härnösand heter medborgarförslag e-förslag |
| Formalia | Val av justerare, dagordning, föredragningslista, "Eventuellt tillkommande ärende", "Tillkommande motioner, interpellationer och frågor", "Övrigt" |
| Interpellation eller fråga | Interpellationer, "Korta frågor", allmänhetens frågestund, inkomna frågor |
| Informationsärende | Informationsärenden, ärenden för kännedom, anmälda delegationsbeslut, delgivningar, meddelanden, "… rapporterar", eller ett beslut som bara lägger något till handlingarna |
| Förslag till annat organ | Beslutet börjar med att organet föreslår ett annat organ ("Kommunstyrelsen föreslår kommunfullmäktige besluta") |
| Beslut | Annars, när beslutstexten säger att organet beslutar |
| Kunde inte klassas | Ingen regel passar och beslutstext saknas |

Typen räknas fram när behandlingen läses, ur rubrik och beslut efter eventuella rättelser, och kan själv rättas. Underlaget redovisas bredvid siffrorna: antalet sammanträden, protokoll som inte gick att tolka (deras behandlingar saknas), sammanträden som bara finns som paragrafprotokoll och protokoll utan datum. Finns sådana visas "Ofullständigt underlag".

Varje typ i nyckeltalen och teckenförklaringen går att välja. Då listas behandlingarna bakom siffran, med länk till varje behandling, och typen speglas i adressen (`typ=motion`).

API:t: `/api/statistik/behandlingar?fran=&till=&organ=` och `/api/statistik/behandlingar/{typ}?fran=&till=&organ=` (typen eller `okand`). Utan år gäller hela arkivet. Startår efter slutår ger 422.

### Motioner och medborgarförslag

En motion följs genom ärendespårningen (`motioner.py`):

- **Väckt**: kommunfullmäktiges beslut att överlämna motionen till kommunstyrelsen för beredning. Motioner som väcks i samlingspunkten "Tillkommande motioner, interpellationer och frågor" kopplas med diarienumret i beslutet ("Motion – Titel (KS2022-206)"), annars med rubriken. En koppling på rubriken visas som förslag (≈).
- **Remissvar** i nämnderna har ofta nämndens eget diarienummer. Ett sådant ärende utan behandling i fullmäktige kopplas till den motion som har mest lik rubrik och väcktes före. Kopplingen visas som förslag.
- **Besvarad**: fullmäktiges beslut i sak. Utfallet läses ur beslutet: delvis bifall (flera att-satser eller "delvis"), avslag, bifall, besvarad, annars annat beslut. Återremiss och bordläggning besvarar inte motionen men räknas.
- **Motionärer**: personerna eller partiet före "har lämnat in en motion" (och liknande) under Bakgrund, Sammanfattning eller Ärendebeskrivning. "X och Y (SD)" ger båda partiet SD. Saknas motionär eller har tolkningen läst fel kan en redaktör eller en utgivare rätta motionärerna i motionstabellen (#78). Rättelsen anger hela listan: personer ur ledamotsregistret (namnvarianter är ihopslagna, och namnet blir personens huvudnamn) och deras parti, eller ett parti utan namn när en partigrupp står bakom motionen. Partiet förifylls ur personens närvaro vid sammanträdet där motionen väcktes, annars härlett som för närvarolistan (`partier.harled`), och källan visas. Rättelsen hör till ärendets behandling i fullmäktige där motionen väcktes, annars till ärendets första behandling, och följer samma flöde som andra rättelser. Publicerade motionärer visas med rättelsemarkering och länk till personsidan, och partifördelningen räknas med dem. Redaktören har filtret *Motioner utan motionär*. API: `GET /api/motionarer/parti?person_id=…&sammantrade_id=…`, och rättelsen med `falt: "motionarer"`.
- **Ledtid**: dagar från väckt till besvarad. Över ett år, obesvarad eller besvarad, markeras (kommunallagen 5 kap. 35 §).

Väckta räknas på året de väcktes och besvarade på året de besvarades. Ett medborgarförslag (e-förslag) besvaras av nämnden eller kommunstyrelsen. När det lämnades står inte i protokollen, så tiden räknas från den första behandlingen.

API:t: `/api/statistik/motioner?fran=&till=&organ=`.

### Återkommande ärenden

Ett ärende är återkommande när minst två av dess behandlingar, vid olika sammanträden, ligger inom urvalet (år och organ). Samlingspunkter räknas inte. Ärendena sorteras efter antal behandlingar. Återremisser ("återremittera") och bordläggningar ("bordlägga", "bordläggs") läses ur besluten och räknas per ärende. Kopplingar som bara är föreslagna ingår inte i ärendet, men antalet visas med ≈ (`aterkommande.py`).

API:t: `/api/statistik/aterkommande?fran=&till=&organ=`.

## Filter och sökning

Vyn Politik och beslut filtrerar sammanträdena på organ och år och söker bland behandlingarna på rubrik eller diarienummer. Allt speglas i adressen, så en vy går att dela. API:t: `/api/sammantraden?organ=&ar=` och `/api/behandlingar?q=&organ=&ar=` (högst 200 träffar, senaste först).

## Inspelningar och test

Inspelningarna har två protokoll per sida och årsmapp (`PROTOKOLL_URVAL=2`), så att de hålls små. Testerna och utvecklingsservern med `--inspelningar` sätter samma urval. Testerna av kommunfullmäktiges protokoll för 2026 läser hela organets sida utan arkivet.
