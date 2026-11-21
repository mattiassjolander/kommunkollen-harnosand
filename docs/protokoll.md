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
  - en lista på första sidan med kolumner: "Namn (Parti)  Roll  Tjänstgörande för …", "Jäv § N" eller "§§ N–M". Namnkolumnen kan sakna parti och bära roll, paragrafer och ersättning, radbrutet över flera rader: "Glenn Sehlin, §§ 131-138, 140-143", "Hans Rosengren, ersätter Ann Kristine Elfvendal § 138 samt Monica Fällström § 139",
  - en lista på första sidan med en rad per person under rubrikerna "Ledamöter", "Tjänstgörande ersättare" och "Ersättare": "Namn (Parti), ordförande", "Namn (Parti) tjänstgörande ersättare för Annan (Parti)",
  - tabellerna "Närvaro- och voteringslista" (ledamöter) och "Närvaro- och tjänstgöringslista" (ersättare), där namn och paragrafer kan vara radbrutna och kolumnrubrikerna avstavade. Tabellen kan fortsätta på nästa sida utan rubrik.
- Paragrafer vid namnet ("Andreas Sjölander §§ 57-61, 63-68, 70-76") är de paragrafer personen var beslutande vid. En ersättare som tjänstgjorde för flera ledamöter vid olika paragrafer får en post per tjänstgöring. Ledamotssidan slår ihop dem till en rad per sammanträde.
- Övriga närvarande tas med när de står med parti eller i en egen kolumn med roll. Tjänstepersoner i löptext ("Namn, förvaltningschef, …") tas inte med.
- **Partitillhörighet** är den protokollet anger vid sammanträdet (ADR-0004). "(-)" visas som partilös. Saknas parti, eller står det "()", härleds partiet och markeras "Härlett" med källan: i första hand samma protokoll (voteringslistan eller "för Namn (S)"), annars närvarolistan i det närmaste sammanträdet där personen har ett parti. Går det inte att härleda visas "parti anges inte i protokollet". En publicerad rättelse går före det härledda partiet.
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
| Motsägelse i protokollet | Voteringslistan stämmer inte med protokollets text | I protokollet |
| Ofullständigt dokument | PDF:en saknar sidor eller text, eller bara paragrafprotokoll finns | I protokollet |
| Paragraferna stämmer inte | Paragraferna stämmer inte med paragrafintervallet, eller samma paragraf förekommer flera gånger | I protokollet eller i tolkningen |
| Kunde inte läsas av plattformen | Övrigt, t.ex. att närvarolistan eller en rubrik inte hittades | I tolkningen |

Indelningen är en hjälp att välja vad som ska kontrolleras mot originalet, inte ett påstående om att kommunens protokoll är fel. API:t: `/api/avvikelser?fran=&till=&organ=`.

## Ärenden

Behandlingar i olika organ kopplas till samma ärende (ADR-0003). Ärendet är plattformens egen entitet, och diarienumren är egenskaper hos det. Reglerna är framtagna ur hela arkivet:

- **Diarienummer.** Samma diarienummer i samma diarieserie kopplar automatiskt. Serien är prefixet (`KS/2026-113`), och utan prefix organets egen serie. Kommunfullmäktige använder kommunstyrelsens serie. Ett diarienummer som återkommer vid sex eller fler sammanträden i ett organ är stående och kopplar ingenting.
- **Hänvisning i beslutsunderlaget** ("Protokollsutdrag kommunstyrelsen 2026-02-24 § 31"). En hänvisning uppåt, från KS till en nämnd eller från KF till KS, kopplar automatiskt när rubrikerna liknar varandra. Annars blir den ett förslag.
- **Övriga hänvisningar**, till samma nivå, nedåt eller utan organ, blir förslag.
- **Samlingspunkter och fasta punkter** (delegationsbeslut, meddelanden, ärenden för kännedom, val av justerare, valärenden, frågestund …) kopplas aldrig.

Förslagen ligger i en kö (`/politik/kopplingar`), där en redaktör bekräftar eller avvisar dem (ADR-0002). Vyn har flikarna Förslag, Bekräftade och Avvisade och filtret Mina beslut. En redaktör kan ändra ett beslut åt alla håll, också tillbaka till förslag, med obligatorisk motivering. Ingen andra granskning behövs, eftersom kopplingar beslutas av en redaktör ensam. Varje beslut sparas i en historik som aldrig skrivs över (`kopplingsbeslut`, #77), och beslut från före historiken blev dess första post. Ärendevyn länkar redaktören från en koppling till dess beslut. Automatiska kopplingar bygger på diarienumret och beslutas inte. Kopplingarna och ärendena räknas om efter varje insamling som gav nya eller ändrade protokoll, och efter `python -m app.tolka_om`. Redaktörens beslut står kvar, och ett ärende behåller sitt id. Kopplingarna pekar ut behandlingen med sammanträde och paragraf, eftersom behandlingarna skapas om vid omtolkning.

Slutligt beslut är det senaste beslutet i ärendet, om det inte föreslår kommunfullmäktige eller kommunstyrelsen något.

API:t: `/api/arenden/{id}`, ärendet på `/api/sammantraden/{id}/behandlingar/{paragraf}` (`arende`), `/api/kopplingar?status=forslag` (med `&mina=true` bara egna beslut) samt `POST /api/kopplingar/{id}/bekraftelse`, `/avvisning` och `/beslut` med `{status, motivering}` för att ändra ett beslut (redaktör). Varje koppling har `historik`.

## Rättelser

En redaktör kan rätta en automatiskt tolkad uppgift: en behandlings rubrik, beslut, diarienummer eller typ, en röst i en votering, partiet för en person i närvarolistan, eller en motions motionärer (som också en utgivare kan skriva, se Motioner nedan). Formuläret finns längst ned på behandlingen. Partiet kan också rättas från sammanträdet, för alla i närvarolistan. Rättelsen kräver en motivering, till exempel var i protokollet uppgiften står.

Statusflödet är utkast → granskad → publicerad (kravspec 18). En utgivare som inte skrev rättelsen granskar och publicerar den under fliken Rättelser. Det gäller också den som har båda rollerna. Redaktören kan ändra och ta bort sitt eget utkast. En ny publicerad rättelse av samma uppgift ersätter den tidigare, som får status ersatt.

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
