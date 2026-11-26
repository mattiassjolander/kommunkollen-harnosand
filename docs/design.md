# Grafisk profil – Kommunkollen Härnösand

Kommunkollen är partipolitiskt obunden (kravspec avsnitt 18). Profilen ska därför se ut som ett **sakligt, oberoende granskningsverktyg**: lugn, informationstät och utan färger eller former som associerar till något parti. Datan ska vara det som syns.

Ramen runt datan (navigering, sidhuvud, accent och logotyp) använder **Härnösands platsvarumärke** "Härnösand Höga Kusten" (se *Platsvarumärket*). Platsvarumärket är fritt att använda för den som vill visa stolthet över platsen. Det är inte kommunens organisationslogotyp, och plattformen anger alltid att den är oberoende av kommunen.

## Principer

1. **Neutral avsändare.** Ingen partifärg används som profilfärg, accent eller dekor. Partifärger förekommer bara där de märker ut ett parti (se *Partifärger*). Accenten är platsvarumärkets blå, som ligger nära Liberalernas och Moderaternas färger. Därför står ett parti alltid med förkortning, och partifärg visas aldrig i samma roll som accenten (länk, knapp, vald flik).
2. **Data före dekor.** Inga gradienter eller illustrationer. Ytor är plana, linjer tunna, och färg används bara när den bär information. Undantaget är en bild ur platsvarumärket som sidhuvud på Översikt, med fotokredit.
3. **Källan syns alltid.** Varje värde, diagram och tabell har en synlig källrad (källa, avsedd period, hämtad). Källhänvisningen är en del av designen, inte en fotnot som göms.
4. **Osäkerhet syns visuellt.** Det ska gå att se på ett ögonkast om något är belagt, uppskattat eller AI-analys (se *Säkerhetsmarkeringar*).
5. **Desktop-first och informationstät**, men aldrig trång: tydlig hierarki, generösa marginaler runt sektioner och kompakt inuti tabeller.

## Färger

Alla färger definieras som CSS-variabler (tokens) i `:root`, med egna värden för mörkt läge. Komponenter refererar till roller, aldrig till rå hex.

### Gränssnitt

| Roll | Ljust | Mörkt | Användning |
|---|---|---|---|
| `--page` | `#f5f5f5` | `#0d0d0d` | Sidans bakgrund |
| `--surface` | `#ffffff` | `#1a1a19` | Kort, paneler, diagramyta |
| `--surface-raised` | `#ffffff` | `#242423` | Menyer, tooltips, dialoger |
| `--ink` | `#0b0b0b` | `#f0efec` | Brödtext, rubriker, siffror |
| `--ink-secondary` | `#52514e` | `#c3c2b7` | Underrubriker, etiketter |
| `--ink-muted` | `#898781` | `#898781` | Axlar, källrader, metadata |
| `--line` | `#e1e0d9` | `#2c2c2a` | Hårlinjer, rutnät, tabellrader |
| `--line-strong` | `#c3c2b7` | `#383835` | Kantlinjer, baslinjer |
| `--accent` | `#0070b3` | `#6cb6ea` | Länkar, fokusring, vald flik, primärknapp, vyrubrik på Översikt |
| `--accent-wash` | `#e6f1e0` | `#1e2c38` | Markerad rad, vald yta |
| `--nav` | `#fce8ec` | `#2a1f22` | Navigeringens bakgrund |
| `--sidhuvud` | `#0070b3` | `#005a8f` | Sidhuvudet med statusindikatorn |
| `--sidhuvud-ink` | `#ffffff` | `#ffffff` | Text i sidhuvudet |

**Accenten** är platsvarumärkets blå (#0070B3). I mörkt läge används en ljusare blå med samma kulör. Den används för interaktion och markering, aldrig i diagram. Den ljusrosa och den ljusgröna kommer också ur platsvarumärket. Platsvarumärkets gula (#F2B219) och korallröda (#F56365) används inte, eftersom de ligger nära SD:s respektive S:s och V:s färger och inte behövs för någon roll.

Kontrast (WCAG): accenten mot vit yta 5,3:1, mot sidans bakgrund 4,9:1, mot markering och navigering 4,5:1. Vit text på sidhuvudet 5,3:1 (mörkt läge 7,3:1). Accenten i mörkt läge mot kort 7,9:1.

### Diagram

Diagramfärgerna följer dataviz-metodens validerade referenspalett. Ordningen är en del av färgblindhetsskyddet och får inte ändras.

**Kategorisk** (identitet, t.ex. verksamhetsområden i Sankey):

| Plats | Ljust | Mörkt |
|---|---|---|
| 1 | `#2a78d6` | `#3987e5` |
| 2 | `#eb6834` | `#d95926` |
| 3 | `#1baf7a` | `#199e70` |
| 4 | `#eda100` | `#c98500` |
| 5 | `#e87ba4` | `#d55181` |
| 6 | `#008300` | `#008300` |
| 7 | `#6250d6` | `#9085e9` |
| 8 | `#e34948` | `#e66767` |

- Färger tilldelas i fast ordning och följer entiteten, inte rangordningen. Ett verksamhetsområde har alltid samma färg i alla vyer och år.
- Fler än åtta kategorier slås ihop till "Övrigt" eller visas som småmultiplar.
- Spridnings- och kartdiagram använder bara de tre första platserna.

**Sekventiell** (storlek): en blå skala från `#cde2fb` till `#0d366b`.

**Divergerande** (ökning/minskning, avvikelse mot budget): blå ↔ röd med grå mittpunkt (`#f0efec` / `#383835`). Röd betyder "lägre än jämförelsen", inte "dåligt". Tokens: `--diverg-hogre` (`#2a78d6` / `#3987e5`) och `--diverg-lagre` (`#e34948` / `#e66767`). Brodiagrammet för årets resultat använder dem för tillskott och avdrag, och summan är grå (`--ink-muted`).

**Status** (datakällornas uppdateringsstatus), alltid tillsammans med ikon och text:

| Status | Färg | Ikon |
|---|---|---|
| Lyckad | `#0ca30c` | ✓ |
| Inga nya uppgifter | `--ink-muted` | – |
| Delvis fel | `#fab219` | ! |
| Misslyckad | `#d03b3b` | ✕ |

### Partifärger

Partifärger används **bara** för att märka ut ett parti: i voteringar, i ledamotslistor och vid jämförelse av partiernas budgetförslag. De används aldrig i ekonomivyer och aldrig i samma diagram som den kategoriska paletten.

- Partiet visas **alltid med förkortning** (S, M, SD, C, V, KD, L, MP). Färgen är ett komplement och bär aldrig betydelse ensam.
- Partifärgerna klarar **inte** färgblindhetskontrollen: S och V är båda röda och går inte att skilja åt (se Validering nedan). Därför är förkortningen obligatorisk, inte valfri.
- Partifärg visas som en liten markering (prick eller kantlinje vid förkortningen), aldrig som stor fyllyta.
- Lokala partier och partier utan etablerad färg visas i `--ink-muted` med förkortning.
- Partilogotyper används inte (varumärken, se kravspec avsnitt 18).
- Markeringen är en prick på 8 px med en tunn ring i `--line-strong`. Ringen gör att ljusa färger (SD, MP) syns mot ljus yta och mörka (KD) mot mörk yta.
- Partilös ("(-)" i protokollet) visas som texten *partilös* utan prick. Saknas parti visas *parti anges inte i protokollet* utan prick.

| Parti | Förkortning | Token | Färg |
|---|---|---|---|
| Socialdemokraterna | S | `--parti-s` | `#e8112d` |
| Moderaterna | M | `--parti-m` | `#52bdec` |
| Sverigedemokraterna | SD | `--parti-sd` | `#dddd00` |
| Centerpartiet | C | `--parti-c` | `#009933` |
| Vänsterpartiet | V | `--parti-v` | `#da291c` |
| Kristdemokraterna | KD | `--parti-kd` | `#000077` |
| Liberalerna | L | `--parti-l` | `#006ab3` |
| Miljöpartiet | MP | `--parti-mp` | `#83cf39` |
| Norrlandspartiet | NP | ingen | neutral prick i `--ink-muted` |

Färgerna är närmevärden till partiernas etablerade profilfärger, så som de brukar återges i valrapportering. De är inte hämtade ur partiernas grafiska manualer och kan bytas mot exakta värden utan att något annat ändras. Samma värden används i ljust och mörkt läge.

Norrlandspartiet skriver sig "NorrP" i protokollen. Plattformen förkortar det NP, som de andra partiernas förkortningar med versaler. Partiet har ännu ingen egen färg och visas med den neutrala pricken.

**Validering** (dataviz-metodens `validate_palette.js`, alla par, november 2026):

| Kontroll | Ljust läge | Mörkt läge |
|---|---|---|
| Färgblindhet (deutan/protan) | Underkänd: S–V ΔE 1,8 | Underkänd: S–V ΔE 1,8 |
| Normalt seende | Underkänd: S–V ΔE 3,3 | Underkänd: S–V ΔE 3,3 |
| Kontrast mot yta | Under 3:1 för M, SD och MP | Under 3:1 för KD |

Paletten klarar alltså inte kontrollerna, och det går inte att rätta utan att överge partiernas färger: S och V är båda röda. Därför bär färgen aldrig information. Förkortningen står alltid bredvid, och ringen ger pricken kontrast.

### Organfärger

De fem organen har varsin färg, så att det syns vilket organ som sammanträder, till exempel i kalendern. Färgerna är den kategoriska paletten i fast ordning, och de följer organet i alla vyer. Det finns inga ikoner för organen, och partifärger blandas aldrig in.

| Organ | Förkortning | Token | Palettplats |
|---|---|---|---|
| Kommunfullmäktige | KF | `--organ-kf` | `--series-1` |
| Kommunstyrelsen | KS | `--organ-ks` | `--series-2` |
| Samhällsnämnden | SAM | `--organ-sam` | `--series-3` |
| Socialnämnden | SOC | `--organ-soc` | `--series-4` |
| Skolnämnden | SKOL | `--organ-skol` | `--series-5` |

- Organtokens pekar på palettplatserna och får därför mörka lägets värden av sig själva.
- **Förkortningen eller det fulla namnet står alltid bredvid färgen.** Färgen bär aldrig betydelse ensam.
- Färgen visas bara som kantlinje eller prick, aldrig som stor fyllyta. Texten bredvid står i `--ink`, inte i accentblått, så att KF:s blå inte förväxlas med en länk.
- Där utrymmet är litet, som i kalenderns månadsvy, står förkortningen. Det fulla namnet finns då i `title` och i text för skärmläsare. Där det finns plats, som i listor, står det fulla namnet.
- Ett okänt organ (inte ett av de fem) får markeringen i `--ink-muted`, och förkortningen är organets id i versaler.
- Färgerna och förkortningarna finns på ett ställe i koden (`frontend/src/organ.ts`).

## Typografi

- **Typsnitt:** Inter (öppen licens, självhostat) med `system-ui, "Segoe UI", sans-serif` som reserv. Ett enda typsnitt i hela gränssnittet, inget display- eller serift typsnitt.
- **Siffror:** `font-variant-numeric: tabular-nums` i tabeller, på axlar och i alla kolumner som ska linjera. Stora enstaka nyckeltal använder proportionella siffror.
- **Talformat:** svensk standard med mellanslag som tusentalsavgränsare och komma som decimaltecken (`1 234,5 mnkr`). Enheten anges alltid (kr, tkr, mnkr, %, kr/inv).
- **Datum:** `15 nov 2026` i löptext och statusrader, `2026-11-15` i tabeller och export.

| Nivå | Storlek / vikt | Användning |
|---|---|---|
| Nyckeltal | 32 px / 600 | Stora siffror på översikt och stat-kort |
| H1 | 24 px / 600 | Vyrubrik |
| H2 | 18 px / 600 | Sektionsrubrik |
| H3 | 15 px / 600 | Kortrubrik, diagramtitel |
| Brödtext | 14 px / 400 | Standard |
| Tabell | 13 px / 400 | Tabellceller |
| Liten | 12 px / 400 | Källrader, metadata, axlar |

## Layout

- Desktop-first. Innehållets maxbredd är 1440 px, och en vänsterställd navigering listar huvudvyerna (kravspec avsnitt 14).

### Navigering

- Vänsternavigeringen listar huvudvyerna. Den står still när sidan skrollar. Logotypen, avsändartexten och användarrutan (inloggning, namn, roller) syns alltid längst ner i fönstret, och bara länklistan skrollar om den inte får plats.
- Ordningen är *Översikt · Ekonomi · Politik och beslut · Kommunen i jämförelse · Om Kommunkollen · Redaktion*.
  - **Ekonomi:** Nyckeltal, Skatteunderlagsprognos, Budget och utfall, Ekonomiska flöden.
  - **Politik och beslut**, med underrubriker: *Sammanträden* (Sammanträden, Kommande ärenden, Kalender), *Förtroendevalda* (Ledamöter, Sammansättning), *Dokument* (Budgetförslag, Styrande dokument) och *Uppföljning* (Statistik, Avvikelser).
  - **Kommunen i jämförelse:** Rankningar, Undersökningar.
  - **Om Kommunkollen** är en diskret rad längre ner, med mindre text, och leder till Datakällor. Statusindikatorn i sidhuvudet länkar också dit.
- En huvudvy med undervyer är en grupp. Gruppens namn leder till dess första undervy och fäller ut gruppen. Bredvid namnet står en pil, ▸ när gruppen är stängd och ▾ när den är öppen. Pilen är en knapp med `aria-expanded` och `aria-controls`. Den fäller ut eller in gruppen utan att byta sida och nås med tangentbordet. Den grupp man är i är alltid utfälld. Undervyerna är indragna länkar, och underrubrikerna står i `--ink-muted` med 12 px. Den valda undervyn markeras med `--accent-wash` och `--accent`. Det finns inga flikrader.
- **Redaktion** är en egen huvudvy för redaktör och utgivare. Den står sist i navigeringen, avskild med en linje, och samlar redaktionens verktyg i grupperna *Granska* (Rättelser, Kopplingar, Partitillhörighet, Motstridigheter, Processer och Att anmäla, med antal som väntar) och *Registrera* (Sammanträdesplaner, Budgetutkast). Varje verktyg visas bara för de roller som har tillgång till det. Att anmäla, protokollavvikelser att lämna till kommunen, är inte publik, och API:t kräver också rollen redaktör eller utgivare.
- En vy som byter adress styrs om från den gamla adressen, med frågan kvar (`FLYTTADE` i `navigering.ts`).
- Vyns rubrik (`h1`) är undervyns namn. Ovanför står en brödsmula med huvudvyn, och på en detaljsida också undervyn: *Politik och beslut › Ledamöter ›*. Dokumentets titel följer samma ordning: *Statistik · Politik och beslut · Kommunkollen Härnösand*.
- Katalogen över huvudvyer och undervyer finns på ett ställe (`frontend/src/navigering.ts`). En ny undervy läggs till där, inte som en egen flikrad.
- Under 900 px bredd fälls navigeringen ihop till knappen *Meny* i sidhuvudet. Menyn öppnas från vänster med samma innehåll, med logotypen och användarrutan i nederkant. Den stängs med Esc, med knappen ✕, vid klick utanför och när man väljer en vy, och fokus går tillbaka till knappen.
- Statusindikatorn för datainsamlingen ligger alltid synlig i sidhuvudet.
- Under högtider står en kort rad i sidhuvudet och en liten symbol vid ordmärket (se *Högtidsteman*). Sidfoten har länken "Visa inte teman".
- Till höger i sidhuvudet finns en knapp som byter mellan ljust och mörkt läge. Utan eget val följer sidan systemets inställning. Valet sparas i webbläsaren.
- Filter (år, period, organ, verksamhetsområde) ligger samlade i en rad ovanför diagrammen de påverkar och speglas i URL:en.
- Avståndsskala med bas 4 px: 4, 8, 12, 16, 24, 32, 48.
- Hörnradie: 6 px på kort och knappar, 4 px på datamarkeringar.
- Inga skuggor på kort, bara hårlinjekant (`--line`). Svag skugga endast på flytande lager (tooltip, meny, dialog).

## Diagram

Följ dataviz-metodens regler. Det viktigaste:

- Aldrig dubbla y-axlar. Två mått med olika skala blir två diagram eller indexeras.
- Tunna markeringar: 2 px linjer och 2 px mellanrum mellan fyllda ytor.
- Tooltip vid hover på alla diagram, med värde, enhet, period och källa.
- Teckenförklaring alltid vid två eller fler serier, och direktetiketter när det är fyra eller färre.
- Varje diagram har en tabellvy och CSV-export.
- Mandatperioder markeras som diskreta bakgrundsband i tidsdiagram, utan partifärg.
- Mörkt läge använder egna, validerade steg och är inte en automatisk invertering.

## Säkerhetsmarkeringar

Visuellt språk för hur säker en uppgift är. Det används konsekvent i tabeller, diagram och kort.

| Typ | Markering |
|---|---|
| Hämtad ur källa | Normal visning med källrad |
| Reviderad av källan | Liten ikon ↻ vid värdet, och tooltip med tidigare värde och datum |
| Dokumenterad kostnad | Hel fyllning |
| Uppskattad kostnad | Diagonal skraffering (45°) i samma färg, och texten "uppskattad" |
| Automatiskt tolkad uppgift (ur protokoll, ej granskad) | Prickad kantlinje, ikonen ⚙ och texten "Automatiskt tolkad, ej granskad". Ett protokoll som inte gick att tolka får varningsikonen ! och texten "Kunde inte tolkas automatiskt" |
| Rättad av redaktionen | Ikonen ✎ och texten "Rättad av redaktionen" vid uppgiften. Den fälls ut och visar vad tolkningen sa, motiveringen och när rättelsen publicerades |
| Protokoll med felaktigheter (publicerade rättelser av fel i protokollet, #74) | Varningsikonen ! och texten "Innehåller felaktigheter" i en ram, på sammanträdessidan och i protokollistan. Den länkar till listan över felaktigheterna under Avvikelser. Tonen är saklig: markeringen beskriver vad som står i protokollet, inte vem som gjort fel |
| Protokollavvikelse att anmäla (#47) | Listan "Att anmäla" under Politik och beslut. Varje avvikelse har typ, paragraf, en länk till sidan i protokollet och statusen i en ram: Ny, Anmäld till kommunen, Rättad av kommunen eller Inte ett fel, med datum och anteckning. En avvikelse som inte finns i kommunens nya version av protokollet får ↻ och texten "Reviderad av källan". Tonen är saklig: texten återger vad som står i protokollet, inte vem som gjort fel |
| Härlett parti (närvarolistan anger inget) | Ikonen ≈ och texten "Härlett" med prickad kantlinje vid partiet. Den fälls ut och visar källan: samma protokoll, eller vilket sammanträde partiet hämtades från |
| Fastställd partitillhörighet (#100, ADR-0006) | Ikonen ◆ och texten "Fastställt av redaktionen" i en hel ram vid partiet, bara när perioden ändrar partiet som protokollet anger. Den fälls ut och visar vad protokollet anger, perioden och motiveringen |
| Diarienummer ur kallelsen (protokollet saknar det, #109) | Ikonen ↗ och texten "ur kallelsen" med prickad kantlinje vid diarienumret. Den fälls ut och länkar till kallelsen och sidan i föredragningslistan där numret står. Ett diarienummer i protokollet eller en publicerad rättelse går före och visas utan markering |
| Koppling mellan behandlingar i ett ärende | Ikonen ⚙ och "Automatisk koppling", ? och "Förslag, inte bekräftat", ✓ och "Bekräftad av redaktör" eller × och "Avvisad av redaktör", alltid med grunden: "samma diarienummer", hänvisningen i beslutsunderlaget, eller "Samma motionstitel" med motionens titel när ett svar på en motion kopplas till fullmäktiges beslut att väcka den (#108) |
| AI-analys (ej bekräftad) | Streckad kantlinje och etiketten **Analys**, aldrig samma stil som fakta |
| Ofullständigt underlag | Grå skraffering och texten "Ofullständigt underlag" |
| Saknas | Tomt med texten "Uppgift saknas", aldrig noll |

## Märkningar

Märkningar (#162) är regelbaserade uppgifter om en behandling eller ett ärende, till exempel votering eller reservation (se GLOSSARY.md). De visas som små chips där behandlingar och ärenden listas: på sammanträdet, behandlingen, ärendet, ledamotens röster, Kommande ärenden och träffarna i Sök.

- Chipet är 11 px text med hörnradie 4 px. Texten står alltid på chipet, t.ex. "Votering 26–24" eller "Reservation C, M", så färgen bär aldrig betydelse ensam.
- **Votering**, **Reservation** och **Oenighet** har var sin dämpade, neutrala ton (`--markning-votering`, `--markning-reservation`, `--markning-oenighet`) med texten i `--ink`. Övriga märkningar (Återremitterad, Bordlagd, Jäv, behandlingstypen, Lång beredning och Återkommande) är konturchips med `--line-strong` och texten i `--ink-secondary`.
- Inga partifärger, inte heller när reservationen anger partier. Partierna står som förkortningar, alfabetiskt.
- På ett ärende har en märkning som finns vid flera behandlingar antalet, "Votering (2)".
- Filtret *Märkning* ligger i filterraden ovanför listan och speglas i URL:en (`markning=`).

## Ton i text

- Saklig och beskrivande. Skriv vad datan visar, inte vad läsaren ska tycka.
- Använd begreppen i [GLOSSARY.md](../GLOSSARY.md), till exempel "kostnadshändelse", inte "slöseri".
- Inga värdeladdade ord som "skandal", "misslyckande" eller "slöseri" i gränssnittstext.
- Partier omnämns alltid i samma form och ordning, alfabetiskt efter förkortning om ingen annan ordning är motiverad.

## Logotyp

Överst i navigeringen står platsvarumärkets primära logotyp "Härnösand Höga Kusten" (blå i ljust läge, vit i mörkt) och under den ordmärket **Kommunkollen** i Inter 600 i `--ink`. Längst ned i navigeringen står den runda sekundära logotypen och texten "Oberoende granskning. Inte en kanal för Härnösands kommun."

## Platsvarumärket

Härnösands platsvarumärke (grafisk profil, logotyper, ikoner, mönster och bilder) är fritt att använda för samprofilering. Plattformen använder:

- den primära logotypen (blå och vit) och den runda sekundära logotypen (blå), beskurna och nedskalade, i `frontend/public/platsvarumarke/`,
- ikonerna stjärnan och vågen (linjevarianten), nedskalade på samma ställe, i högtidstemana (se *Högtidsteman*),
- färgerna blå #0070B3, ljusrosa #FCE8EC, ljusgrön #E6F1E0 och ljusgrå #F5F5F5 (se *Gränssnitt*),
- bilden från Smitingen som sidhuvud på Översikt, med texten "Foto: Härnösands platsvarumärke".

Platsvarumärkets egna regler gäller: logotyperna används som de är och görs aldrig om. Originalfilerna ligger i `platsvarumarke/` i projektmappen och checkas inte in, eftersom bilderna är stora.

## Högtidsteman

På några svenska högtidsdagar och på Härnösands dag får ramen ett diskret tema (#70). Det är ett begränsat undantag från *Data före dekor*.

**Vad ett tema får ändra.** Bara ramen:

- en liten symbol vid ordmärket i navigeringen, högst 24 px och dold för skärmläsare,
- en kort rad i sidhuvudet, bredvid statusindikatorn.

Diagram, datafärger, partifärger, statusfärger, `--accent`, navigeringens bakgrund och säkerhetsmarkeringar ändras aldrig. Inget rör sig: temana har inga animationer eller övergångar.

**Färger.** Bara platsvarumärkets blå, ljusrosa, ljusgröna och vita. Inga röda, gula eller gröna fyllytor, eftersom de ligger nära partifärgerna. Undantaget är Sverigeflaggan på nationaldagen, som är en officiell flaggdag och visas som en liten symbol.

| Token | Ljust | Mörkt | Användning |
|---|---|---|---|
| `--hogtid-linje` | `#0070b3` | `#6cb6ea` | Symbolernas linjer, 1,5 px. Mot navigeringen 4,5:1 (mörkt läge 7,2:1) |
| `--hogtid-rosa` | `#fce8ec` | `#fce8ec` | Påskägget |
| `--hogtid-gron` | `#e6f1e0` | `#e6f1e0` | Blommorna i midsommarkransen |
| `--hogtid-vit` | `#ffffff` | `#ffffff` | Valsedeln och ljuset |
| `--flagga-bla`, `--flagga-gul` | `#006aa7`, `#fecc02` | samma | Bara Sverigeflaggan |

Raden i sidhuvudet är vit på sidhuvudets blå (5,3:1, mörkt läge 7,3:1). Ljusa fyllningar har alltid en linje i `--hogtid-linje`, så att symbolen syns mot den ljusrosa navigeringen.

**Symboler.** Stjärnan och vågen är platsvarumärkets ikoner (linjevarianten), nedskalade i `frontend/public/platsvarumarke/`. Formen används som den är och fylls med `--hogtid-linje`. Övriga symboler är enkla egna SVG:er med tunna linjer och utan gradienter.

| Tema | Period (svensk tid) | Symbol | Rad i sidhuvudet |
|---|---|---|---|
| Nyår | 31 dec–1 jan | Gnistor | Gott nytt år |
| Påsk | Skärtorsdag–annandag påsk (gregoriansk påskberäkning) | Ägg i ljusrosa | Glad påsk |
| Nationaldagen | 6 juni | Sverigeflaggan | Sveriges nationaldag |
| Midsommar | Midsommarafton (fredagen 19–25 juni) och midsommardagen | Blomkrans i ljusgrönt | Glad midsommar |
| Valdagen | Andra söndagen i september valåren (2026, 2030 …) | Valsedel | I dag är det val – val.se |
| Härnösands dag | 11 mars | Vågen | Härnösand fick sina stadsprivilegier i dag för N år sedan (1585) |
| Lucia | 13 dec | Ljus | Glad lucia |
| Jul | 24–26 dec | Stjärnan | God jul |

**Härnösands dag** är den 11 mars. Den 11 mars 1585 fick Härnösand sina stadsprivilegier av Johan III, och det är den dag som brukar firas. N är året minus 1585. Raden har en tooltip med källan. Andra datum som förekommer i källorna (till exempel 14 september 1585 och 8 februari 1587) används inte.

**Nedräkning.** Under de 30 dagarna före den 11 mars visar sidhuvudet en nedräkning, till exempel "12 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna", och dagen före "I morgon är det Härnösands dag". Den är bara text, utan symbol. Dagarna räknas som skillnaden i kalenderdagar i svensk tid, så skottår hanteras rätt.

**Krockar.** Gäller flera teman samma dag vinner valdagen, därefter tabellens ordning. Ett tema går alltid före nedräkningen.

**Dagar utan tema.** Dagar som står olika nära olika partier får inget tema, till exempel 1 maj, internationella kvinnodagen och Pride. Ett tema skulle ge plattformen en politisk avsändare (kravspec avsnitt 18). Allhelgona får inget tema, eftersom det är en sorgedag.

**Stänga av och förhandsvisa.** Sidfoten har länken "Visa inte teman" (och "Visa teman" när den är vald). Valet sparas i webbläsaren, och går lagringen inte att nå visas teman som vanligt. `?tema=<namn>` förhandsvisar ett tema oavsett datum (`nyar`, `pask`, `nationaldagen`, `midsommar`, `valdagen`, `harnosandsdag`, `lucia`, `jul`, `nedrakning`), och `?tema=inget` stänger av det. `?datum=ÅÅÅÅ-MM-DD` räknar temat för en annan dag, till exempel `?tema=nedrakning&datum=2026-03-01`.

Logiken ligger i `frontend/src/hogtider.ts` (`temaFor`), helt i frontend.
