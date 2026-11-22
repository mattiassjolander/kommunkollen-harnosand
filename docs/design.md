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

**Divergerande** (ökning/minskning, avvikelse mot budget): blå ↔ röd med grå mittpunkt (`#f0efec` / `#383835`). Röd betyder "lägre än jämförelsen", inte "dåligt".

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

Färgerna är närmevärden till partiernas etablerade profilfärger, så som de brukar återges i valrapportering. De är inte hämtade ur partiernas grafiska manualer och kan bytas mot exakta värden utan att något annat ändras. Samma värden används i ljust och mörkt läge.

**Validering** (dataviz-metodens `validate_palette.js`, alla par, november 2026):

| Kontroll | Ljust läge | Mörkt läge |
|---|---|---|
| Färgblindhet (deutan/protan) | Underkänd: S–V ΔE 1,8 | Underkänd: S–V ΔE 1,8 |
| Normalt seende | Underkänd: S–V ΔE 3,3 | Underkänd: S–V ΔE 3,3 |
| Kontrast mot yta | Under 3:1 för M, SD och MP | Under 3:1 för KD |

Paletten klarar alltså inte kontrollerna, och det går inte att rätta utan att överge partiernas färger: S och V är båda röda. Därför bär färgen aldrig information. Förkortningen står alltid bredvid, och ringen ger pricken kontrast.

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
- Statusindikatorn för datainsamlingen ligger alltid synlig i sidhuvudet.
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
| Härlett parti (närvarolistan anger inget) | Ikonen ≈ och texten "Härlett" med prickad kantlinje vid partiet. Den fälls ut och visar källan: samma protokoll, eller vilket sammanträde partiet hämtades från |
| Koppling mellan behandlingar i ett ärende | Ikonen ⚙ och "Automatisk koppling", ? och "Förslag, inte bekräftat", ✓ och "Bekräftad av redaktör" eller × och "Avvisad av redaktör", alltid med grunden (diarienumret eller hänvisningen) |
| AI-analys (ej bekräftad) | Streckad kantlinje och etiketten **Analys**, aldrig samma stil som fakta |
| Ofullständigt underlag | Grå skraffering och texten "Ofullständigt underlag" |
| Saknas | Tomt med texten "Uppgift saknas", aldrig noll |

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
- färgerna blå #0070B3, ljusrosa #FCE8EC, ljusgrön #E6F1E0 och ljusgrå #F5F5F5 (se *Gränssnitt*),
- bilden från Smitingen som sidhuvud på Översikt, med texten "Foto: Härnösands platsvarumärke".

Platsvarumärkets egna regler gäller: logotyperna används som de är och görs aldrig om. Originalfilerna ligger i `platsvarumarke/` i projektmappen och checkas inte in, eftersom bilderna är stora.
