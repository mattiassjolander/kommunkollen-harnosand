# Grafisk profil – Kommunkollen Härnösand

Kommunkollen är partipolitiskt obunden (kravspec avsnitt 18). Profilen ska därför se ut som ett **sakligt, oberoende granskningsverktyg**: lugn, informationstät och utan färger eller former som associerar till något parti. Datan ska vara det som syns.

## Principer

1. **Neutral avsändare.** Ingen partifärg används som profilfärg, accent eller dekor. Partifärger förekommer bara där de märker ut ett parti (se *Partifärger*).
2. **Data före dekor.** Inga gradienter, illustrationer eller stämningsbilder. Ytor är plana, linjer tunna, och färg används bara när den bär information.
3. **Källan syns alltid.** Varje värde, diagram och tabell har en synlig källrad (källa, avsedd period, hämtad). Källhänvisningen är en del av designen, inte en fotnot som göms.
4. **Osäkerhet syns visuellt.** Det ska gå att se på ett ögonkast om något är belagt, uppskattat eller AI-analys (se *Säkerhetsmarkeringar*).
5. **Desktop-first och informationstät**, men aldrig trång: tydlig hierarki, generösa marginaler runt sektioner och kompakt inuti tabeller.

## Färger

Alla färger definieras som CSS-variabler (tokens) i `:root`, med egna värden för mörkt läge. Komponenter refererar till roller, aldrig till rå hex.

### Gränssnitt

| Roll | Ljust | Mörkt | Användning |
|---|---|---|---|
| `--page` | `#f9f9f7` | `#0d0d0d` | Sidans bakgrund |
| `--surface` | `#fcfcfb` | `#1a1a19` | Kort, paneler, diagramyta |
| `--surface-raised` | `#ffffff` | `#242423` | Menyer, tooltips, dialoger |
| `--ink` | `#0b0b0b` | `#f0efec` | Brödtext, rubriker, siffror |
| `--ink-secondary` | `#52514e` | `#c3c2b7` | Underrubriker, etiketter |
| `--ink-muted` | `#898781` | `#898781` | Axlar, källrader, metadata |
| `--line` | `#e1e0d9` | `#2c2c2a` | Hårlinjer, rutnät, tabellrader |
| `--line-strong` | `#c3c2b7` | `#383835` | Kantlinjer, baslinjer |
| `--accent` | `#3d3480` | `#a99ff0` | Länkar, fokusring, vald flik, primärknapp |
| `--accent-wash` | `#efedf8` | `#2a2640` | Markerad rad, vald yta |

**Accenten** är en dov indigoviolett. Den valdes för att ingen svensk riksdagspartis profilfärg ligger nära den (röda, blå, gula och gröna toner är upptagna). Den används sparsamt, bara för interaktion och markering, aldrig i diagram.

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
- Partifärgerna klarar **inte** färgblindhetskontrollen: M och L är nästan identiska och S och V ligger nära varandra. Därför är förkortningen obligatorisk, inte valfri.
- Partifärg visas som en liten markering (prick eller kantlinje vid förkortningen), aldrig som stor fyllyta.
- Lokala partier och partier utan etablerad färg visas i `--ink-muted` med förkortning.
- Partilogotyper används inte (varumärken, se kravspec avsnitt 18).
- Exakta partifärger fastställs i fas 2 och dokumenteras här med källa.

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
| AI-analys (ej bekräftad) | Streckad kantlinje och etiketten **Analys**, aldrig samma stil som fakta |
| Ofullständigt underlag | Grå skraffering och texten "Ofullständigt underlag" |
| Saknas | Tomt med texten "Uppgift saknas", aldrig noll |

## Ton i text

- Saklig och beskrivande. Skriv vad datan visar, inte vad läsaren ska tycka.
- Använd begreppen i [GLOSSARY.md](../GLOSSARY.md), till exempel "kostnadshändelse", inte "slöseri".
- Inga värdeladdade ord som "skandal", "misslyckande" eller "slöseri" i gränssnittstext.
- Partier omnämns alltid i samma form och ordning, alfabetiskt efter förkortning om ingen annan ordning är motiverad.

## Logotyp

Ordmärke: **Kommunkollen** i Inter 600 i `--ink`, med **Härnösand** under i `--ink-secondary`. Inget symbolmärke tills vidare.
