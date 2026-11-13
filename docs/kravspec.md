# Kravspecifikation – Härnösands kommun: ekonomi, utveckling och politiska beslut

**Dokumenttyp:** Funktionell och teknisk kravspecifikation  
**Frontend:** Vue 3 + TypeScript  
**Användningsområde:** Desktopbaserad analysplattform  
**Datainsamling:** Automatiserad, två gånger per månad

> Begrepp definieras i [GLOSSARY.md](../GLOSSARY.md). Arkitekturbeslut finns i [docs/adr/](adr/). Beslut som fattats efter att specen skrevs finns i avsnitt 18.

## 1. Syfte och mål

Målet är att utveckla en digital analysplattform som samlar, strukturerar och visualiserar information om Härnösands kommuns utveckling över tid.

Plattformen ska ge en samlad bild av kommunens ekonomi, verksamheter, befolkning, näringsliv och politiska beslut.

En särskilt viktig del är att kunna följa hur kommunens ekonomiska resurser används, vilka prioriteringar som görs och vilka ekonomiska konsekvenser olika beslut får.

Plattformen ska även identifiera och dokumentera kostnader som hade kunnat undvikas genom bättre planering, handläggning, beslutsunderlag eller genomförande.

Informationen ska hämtas från offentliga källor och presenteras med tydlig källhänvisning och historik.

## 2. Övergripande funktioner

Plattformen ska erbjuda:

- Historisk uppföljning av kommunens utveckling.
- Ekonomisk analys och visualisering.
- Visualisering av ekonomiska flöden med Sankey-diagram.
- Uppföljning av budget, prognos och faktiskt utfall.
- Statistik om befolkning, arbetsmarknad och näringsliv.
- Insamling och analys av politiska beslut.
- Spårbarhet genom den kommunala beslutsprocessen.
- Uppföljning av revisionsrapporter och rekommenderade åtgärder.
- Identifiering och uppföljning av undvikbara kostnader.
- Jämförelser med andra kommuner.
- Dokumentinsamling och automatiserade sammanfattningar.
- Historisk jämförelse mellan olika mandatperioder.
- Analys av partiernas budgetförslag (se avsnitt 17A).

All information ska kunna filtreras på år, tidsperiod, nämnd, förvaltning, verksamhetsområde och kategori där det är relevant.

## 3. Ekonomi och finansiell utveckling

### 3.1 Ekonomisk översikt

Samla ekonomisk information från kommunens årsredovisningar, delårsrapporter, budgetar och SCB.

Följande nyckeltal ska kunna visas över tid:

- Årets resultat.
- Budgeterat resultat.
- Resultatprognos.
- Skatteintäkter.
- Generella statsbidrag.
- Riktade statsbidrag.
- Utjämningsbidrag och utjämningsavgifter.
- Verksamheternas nettokostnader.
- Investeringar.
- Låneskuld.
- Pensionsåtaganden.
- Likviditet.
- Soliditet.
- Kassaflöde.
- Kostnad per invånare.

Det ska vara möjligt att jämföra utvecklingen mellan olika år och identifiera större förändringar.

### 3.2 Budget jämfört med utfall

För varje ekonomiskt område ska det gå att jämföra:

- Ursprunglig budget.
- Reviderad budget.
- Delårsprognos.
- Faktiskt utfall.
- Avvikelse i kronor.
- Avvikelse i procent.

Det ska även vara möjligt att följa om en budgetavvikelse beror på ökade kostnader, minskade intäkter, förändrad verksamhetsvolym eller andra omständigheter.

### 3.3 Likviditet och soliditet

Skapa en särskild vy för kommunens finansiella ställning.

Följ bland annat:

- Likvida medel.
- Kassalikviditet.
- Rörelsekapital.
- Kassaflöde.
- Soliditet inklusive pensionsförpliktelser.
- Soliditet exklusive pensionsförpliktelser.
- Långfristiga skulder.
- Kortfristiga skulder.

Visa både absoluta värden och utveckling över tid.

## 4. Ekonomiska flöden – Sankey

En central funktion ska vara att visualisera hur kommunens pengar flödar genom organisationen.

Sankey-diagram ska användas för att illustrera hur pengar kommer in till kommunen, hur de fördelas och hur de slutligen används.

### 4.1 Intäktsflöden

Visualisera kommunens intäkter uppdelade på exempelvis:

- Kommunalskatt.
- Inkomstutjämning.
- Kostnadsutjämning.
- Regleringsbidrag och regleringsavgifter.
- Generella statsbidrag.
- Riktade statsbidrag.
- Avgifter och taxor.
- Försäljning och övriga intäkter.
- Finansiella intäkter.

### 4.2 Fördelning av ekonomiska resurser

Visa hur intäkterna fördelas vidare till:

- Kommunstyrelsen.
- Samhällsnämnden.
- Socialnämnden.
- Skolnämnden.
- Övriga nämnder och verksamheter.
- Gemensamma kostnader.
- Finansiering och finansiella poster.
- Investeringar.

### 4.3 Kostnadsflöden

Gör det möjligt att följa hur respektive nämnds och verksamhets ekonomiska resurser används.

Exempel:

- Personal.
- Lokaler.
- Köp av externa tjänster.
- Konsulter.
- Entreprenader.
- Bidrag och transfereringar.
- Material och förbrukning.
- Kapitalkostnader.
- Övriga verksamhetskostnader.

### 4.4 Interaktivitet

Sankey-diagrammet ska vara interaktivt.

Användaren ska kunna:

- Välja vilket år som ska analyseras.
- Växla mellan budget och faktiskt utfall.
- Klicka på ett flöde för att se bakomliggande belopp.
- Filtrera på nämnd och verksamhetsområde.
- Fördjupa sig från övergripande intäkter till enskilda kostnadskategorier.
- Jämföra ekonomiska flöden mellan olika år.
- Se förändringar i både kronor och procent.
- Gå vidare till bakomliggande rapport eller datakälla.

Diagrammet ska även kunna visa hur fördelningen förändrats mellan olika år.

Det ska finnas möjlighet att visa ekonomiska flöden på olika detaljnivåer, från hela kommunen till enskilda verksamhetsområden.

### 4.5 Datakvalitet i ekonomiska flöden

Flöden ska baseras på faktiska redovisningsuppgifter eller tydligt markerade budgetuppgifter.

Interna överföringar ska inte dubbelräknas som externa intäkter eller kostnader.

Det ska framgå om diagrammet visar bruttoflöden, nettoflöden eller en förenklad fördelningsmodell.

Om underlaget inte räcker för att fastställa ett fullständigt ekonomiskt flöde ska detta tydligt framgå.

## 5. Undvikbara kostnader och ekonomiska konsekvenser

### 5.1 Syfte

Skapa en särskild analysfunktion för att identifiera och följa kostnader som kommunen hade kunnat undvika.

Syftet är att synliggöra ekonomiska konsekvenser av exempelvis bristande planering, felaktiga beslut, ineffektiva processer, förseningar eller brister i kommunens interna styrning.

Det ska vara möjligt att följa både direkta kostnader och uppskattade följdkostnader.

### 5.2 Kostnadskategorier

Följande kategorier ska kunna identifieras:

**Överklaganden och rättsliga processer**
- Kostnader för juridiska ombud.
- Externa konsultkostnader.
- Intern arbetstid för hantering av överklaganden.
- Kostnader för omtag i handläggning.
- Kostnader till följd av försenade projekt eller beslut.
- Eventuella skadestånd och andra ekonomiska följder.

**Bristande planering och beslutsunderlag**
- Projekt som behöver göras om.
- Utredningar som måste kompletteras.
- Felaktiga eller ofullständiga kalkyler.
- Kostnader för ändrade inriktningar.
- Investeringar som inte uppnår avsett syfte.

**Förseningar och uteblivna åtgärder**
- Fördyrade bygg- och anläggningsprojekt.
- Förlängda hyres- och lokalkostnader.
- Försenade avvecklingar eller omlokaliseringar.
- Ökade entreprenadkostnader.
- Kostnader till följd av uppskjutna beslut.

**Bristande verksamhetsstyrning**
- Felaktiga utbetalningar.
- Dubbelarbete.
- Ineffektiv resursanvändning.
- Bristande intern kontroll.
- Upprepade upphandlingar eller omtag.
- Kostnader som uppstår genom att tidigare identifierade brister inte åtgärdats.

### 5.3 Registrering av identifierade kostnader

Varje identifierad kostnad ska kunna registreras som ett separat analysobjekt (en *kostnadshändelse*, se GLOSSARY.md).

Information som ska lagras:

- Rubrik och beskrivning.
- Händelsedatum och berörd tidsperiod.
- Berörd nämnd eller förvaltning.
- Ansvarigt verksamhetsområde.
- Kostnadskategori.
- Beskrivning av händelseförloppet.
- Vad som orsakat kostnaden.
- Vilket alternativ som hade kunnat undvika kostnaden.
- Faktisk kostnad.
- Uppskattad indirekt kostnad.
- Beräknad potentiellt undvikbar kostnad.
- Underlag och källhänvisningar.
- Eventuella politiska beslut kopplade till händelsen.
- Status för utredning och uppföljning.

### 5.4 Exempel: kostnader till följd av överklagande

Ett ärende har överklagats och kommunen behöver lägga ytterligare resurser på att hantera ärendet.

Analysen ska kunna visa:

1. Vilket ursprungligt beslut som fattades.
2. Vilken instans som fattade beslutet.
3. Varför beslutet överklagades.
4. Vilka eventuella brister som identifierades.
5. Vilka kostnader som uppstod.
6. Om beslutet ändrades eller upphävdes.
7. Om ärendet behövde handläggas på nytt.
8. Om det finns dokumenterade lärdomar eller åtgärder.

Det ska vara möjligt att summera direkta kostnader och uppskatta den totala ekonomiska påverkan.

### 5.5 Kostnadsbedömning och bevisvärdering

Det är viktigt att skilja mellan faktiska kostnader, uppskattade kostnader och kostnader som bedöms ha kunnat undvikas.

Alla identifierade kostnader ska därför klassificeras:

| Klassificering | Beskrivning |
|---|---|
| Dokumenterad kostnad | Kostnad som kan styrkas med ekonomiskt underlag |
| Uppskattad kostnad | Beräknad kostnad med redovisade antaganden |
| Potentiellt undvikbar | Kostnad där ett rimligt alternativ identifierats |
| Styrkt undvikbar | Undvikbarhet som stöds av dokumenterat underlag |
| Ej fastställd | Det finns indikationer men otillräckligt underlag |

*Tabellen ovan genomförs som två separata dimensioner: beloppssäkerhet per kostnadspost och undvikbarhet per kostnadshändelse. Se ADR-0005.*

Det ska inte automatiskt betraktas som en onödig kostnad bara för att ett beslut överklagats eller ett projekt försenats.

Det ska finnas tydliga belägg för orsakssamband och en redovisning av hur kostnaden beräknats.

### 5.6 Sammanställning

Skapa en särskild dashboard som visar:

- Totalt identifierade kostnader.
- Dokumenterade kostnader.
- Uppskattade kostnader.
- Potentiellt undvikbara kostnader.
- Kostnader per nämnd.
- Kostnader per kategori.
- Kostnader per år.
- Återkommande problemområden.
- Kostnader kopplade till politiska beslut.
- Genomförda åtgärder för att förhindra att kostnaderna upprepas.

Det ska gå att följa utvecklingen över tid och se om kommunen lyckas minska återkommande undvikbara kostnader.

## 6. Befolkning, näringsliv och arbetsmarknad

Följ kommunens demografiska och ekonomiska utveckling.

### 6.1 Befolkning

- Total befolkning.
- Befolkningsutveckling.
- Födda och avlidna.
- In- och utflyttning.
- Åldersfördelning.
- Försörjningskvot.
- Befolkningsprognoser.
- Geografisk fördelning.

### 6.2 Näringsliv

- Antal företag.
- Nystartade företag.
- Företagsnedläggningar.
- Antal anställda.
- Branschfördelning.
- Sysselsättningsutveckling.
- Antal arbetsställen.
- Utveckling av arbetstillfällen.

### 6.3 Arbetslöshet och pendling

- Total arbetslöshet.
- Ungdomsarbetslöshet.
- Långtidsarbetslöshet.
- Sysselsättningsgrad.
- Antal arbetstillfällen.
- Antal personer som bor och arbetar i Härnösand.
- Antal personer som pendlar från Härnösand till andra kommuner.
- Antal personer som pendlar till Härnösand från andra kommuner.
- Viktigaste pendlingsdestinationerna.

## 7. Politiska beslut och ärendespårning

Samla politiska beslut från kommunens nämnder, kommunstyrelsen och kommunfullmäktige.

### 7.1 Beslutande organ

- Samhällsnämnden.
- Socialnämnden.
- Skolnämnden.
- Kommunstyrelsen.
- Kommunfullmäktige.

För respektive organ ska följande samlas:

- Kallelser.
- Dagordningar.
- Protokoll.
- Beslutsunderlag.
- Tjänsteskrivelser.
- Yrkanden.
- Reservationer.
- Voteringsresultat.
- Beslut.

### 7.2 Ärendets väg genom organisationen

Varje ärende ska kunna följas genom den kommunala beslutsprocessen.

Förvaltning → Nämnd → Kommunstyrelse → Kommunfullmäktige → Genomförande → Uppföljning.

Det ska framgå vilka instanser som behandlat ärendet, vilka förändringar som gjorts och vilket slutligt beslut som fattats.

### 7.3 Votering

När en omröstning har genomförts ska det gå att se:

- Vilka ledamöter som röstat ja.
- Vilka ledamöter som röstat nej.
- Vilka som avstått.
- Vilka som varit frånvarande.
- Partitillhörighet.
- Vilket förslag som vann.

Partisymboler ska användas som visuell identifiering. *(Se avsnitt 18: partifärger och förkortningar i stället för logotyper.)*

Informationen ska hämtas från dokumenterade voteringslistor och inte uppskattas utifrån partiernas politiska ställningstaganden.

## 8. Revision och granskning

Samla kommunrevisionens rapporter och följ upp rekommendationer.

För varje rapport ska följande information struktureras:

- Granskat område.
- Datum.
- Syfte.
- Identifierade brister.
- Revisionens bedömning.
- Rekommendationer.
- Ansvarig nämnd.
- Svar från verksamheten.
- Beslutade åtgärder.
- Genomförda åtgärder.
- Status för uppföljning.

Det ska även gå att identifiera återkommande brister och koppla dessa till eventuella ekonomiska konsekvenser.

## 9. Dokumentinsamling och AI-baserad analys

Plattformen ska samla in och bearbeta:

- Budgetar.
- Årsredovisningar.
- Delårsrapporter.
- Nämndsprotokoll.
- Kommunstyrelseprotokoll.
- Kommunfullmäktigeprotokoll.
- Tjänsteskrivelser.
- Revisionsrapporter.
- Uppföljningsrapporter.
- Partiernas budgetförslag.

Dokument ska indexeras och göras sökbara.

AI-baserad dokumentanalys ska kunna identifiera:

- Ekonomiska förändringar.
- Nya politiska beslut.
- Kostnadsökningar.
- Förseningar.
- Avvikelser.
- Identifierade risker.
- Revisionsanmärkningar.
- Föreslagna åtgärder.
- Potentiellt undvikbara kostnader.

AI ska kunna skapa sammanfattningar men alla slutsatser ska kunna verifieras mot originaldokument, sidnummer och relevanta textavsnitt.

AI-genererade bedömningar ska markeras som analys och inte presenteras som fastställda fakta.

## 10. Datakällor

### Kommunala källor

- [Budget och årsredovisning](https://harnosand.se/kommun--styrning/ekonomi-och-upphandling/budget-och-arsredovisning.html)
- [Samhällsnämnden](https://harnosand.se/kommun--styrning/politik-och-demokrati/namnder/samhallsnamnden.html)
- [Socialnämnden](https://harnosand.se/kommun--styrning/politik-och-demokrati/namnder/socialnamnden.html)
- [Skolnämnden](https://harnosand.se/kommun--styrning/politik-och-demokrati/namnder/skolnamnden.html)
- [Kommunstyrelsen](https://harnosand.se/kommun--styrning/politik-och-demokrati/kommunstyrelse.html)
- [Revisionen](https://harnosand.se/kommun--styrning/politik-och-demokrati/revisionen.html)
- Kommunfullmäktiges protokoll och handlingar.

### Nationella datakällor

- SCB.
- Skatteverket.
- Kolada.
- SKR.
- Arbetsförmedlingen.
- Valmyndigheten (valresultat och mandatfördelning).
- Andra relevanta myndigheter.

Datakällorna ska prioriteras enligt följande:

1. Officiella API:er.
2. Nedladdningsbara strukturerade datafiler.
3. Offentliga dokument i PDF eller andra format.
4. Webbsidor och dokumentarkiv.

## 11. Automatiserad datainsamling

### 11.1 Övergripande krav

Datainsamlingen ska ske automatiskt två gånger per månad.

Det ska finnas en separat backendtjänst som ansvarar för att hämta, bearbeta, kontrollera och lagra information från externa källor.

Datainsamlingen ska vara oberoende av frontendapplikationen.

Föreslagen körning:

- Första körningen: den 1:a varje månad.
- Andra körningen: den 15:e varje månad.

Körningarna ska ske automatiskt utan att någon behöver starta dem manuellt.

### 11.2 Backendtjänstens ansvar

Backendtjänsten ska:

1. Starta enligt konfigurerat schema.
2. Kontrollera tillgängliga datakällor.
3. Identifiera nya eller förändrade dokument.
4. Hämta nya statistikuppgifter.
5. Hämta och lagra dokument.
6. Extrahera relevant information.
7. Strukturera och normalisera data.
8. Validera uppgifter och identifiera avvikelser.
9. Uppdatera databas och sökindex.
10. Logga körningens resultat.
11. Uppdatera information om senaste lyckade hämtning.

### 11.3 Inkrementell hämtning

Systemet ska i första hand hämta förändringar sedan föregående körning.

Det ska inte behöva ladda ner och bearbeta samtliga historiska dokument vid varje körning.

För varje källa ska systemet kunna hålla reda på:

- Senaste genomförda hämtning.
- Senaste lyckade hämtning.
- Senaste publicerade uppgift.
- Senaste identifierade dokument.
- Antal nya dokument.
- Antal uppdaterade dokument.
- Eventuella fel.

Om en källa inte har publicerat någon ny information ska detta registreras som en genomförd kontroll utan nya uppgifter.

### 11.4 Felhantering

Backendtjänsten ska ha stöd för:

- Automatisk retry vid tillfälliga fel.
- Begränsning av anropsfrekvens.
- Timeout-hantering.
- Loggning av fel.
- Återupptagning av avbrutna körningar.
- Manuell omkörning av enskilda datakällor.
- Kontroll av dubbletter.
- Kontroll av förändrade dokument.
- Notering av källor som inte kunnat hämtas.

Ett fel hos en enskild datakälla ska inte stoppa övrig datainsamling.

### 11.5 Historik och versionshantering

Tidigare hämtade dokument och uppgifter ska bevaras.

Om en källa publicerar en reviderad uppgift ska systemet kunna visa:

- Tidigare värde.
- Nytt värde.
- Datum för förändringen.
- Vilken källa som uppdaterats.

Historiken ska inte skrivas över utan bevaras för framtida jämförelser.

## 12. Uppdateringsstatus och datakvalitet

Det ska vara tydligt för användaren när informationen senast uppdaterades.

### 12.1 Global uppdateringsinformation

På plattformens startsida ska det finnas en tydlig statusindikator som visar:

- Senaste genomförda datainsamling.
- Senaste lyckade datainsamling.
- Nästa planerade körning.
- Antal datakällor som uppdaterats.
- Antal datakällor med fel.
- Om informationen är fullständigt uppdaterad eller delvis inaktuell.

Exempel:

**Senast uppdaterad:** 15 november 2026, 03:42

**Nästa uppdatering:** 1 december 2026

**Datakällor:** 18 av 20 kontrollerade utan fel.

### 12.2 Uppdateringsstatus per datakälla

Varje informationsområde ska visa när dess data senast hämtades.

Exempel:

| Datakälla | Senaste kontroll | Status |
|---|---|---|
| SCB | 15 nov 2026 | Lyckad |
| Kolada | 15 nov 2026 | Lyckad |
| Kommunala rapporter | 15 nov 2026 | Lyckad |
| Kommunala protokoll | 15 nov 2026 | Delvis fel |
| Revisionsrapporter | 15 nov 2026 | Lyckad |

### 12.3 Skillnad mellan hämtning och publicering

Det ska alltid gå att skilja på:

- När uppgiften senast publicerades av källan.
- Vilken period uppgiften avser.
- När systemet hämtade uppgiften.
- När uppgiften senast ändrades i systemet.

Detta är särskilt viktigt för statistik som publiceras med flera månaders fördröjning.

En lyckad hämtning innebär inte automatiskt att det finns nya eller aktuella uppgifter.

## 13. Teknisk arkitektur

### 13.1 Frontend

Frontend utvecklas i Vue 3 med TypeScript.

Gränssnittet ska vara desktop-first och optimerat för stora datamängder och avancerad analys.

Funktioner:

- Interaktiva diagram.
- Sankey-visualisering.
- Avancerade tabeller.
- Tidslinjer.
- Sökning och filtrering.
- Jämförelser mellan år.
- Drill-down till detaljer.
- Källhänvisningar.
- Export av data och rapporter.

### 13.2 Backend

Backend ska tillhandahålla API:er till frontend och hantera datainsamling och bearbetning. *(Se ADR-0001: Python och FastAPI.)*

Föreslagna separata komponenter:

- Datainsamlingstjänst.
- Schemaläggare.
- Dokumenthantering.
- Dokumentextraktion.
- Statistikbearbetning.
- Analys- och klassificeringstjänst.
- API-tjänst.
- Sökindex.

### 13.3 Lagring

Lösningen ska kunna hantera flera typer av information:

- Relationsdata för ekonomiska nyckeltal och politiska beslut.
- Dokumentlagring för PDF:er och andra originalhandlingar.
- Sökindex för fritextsökning.
- Historik och versionsinformation.
- Metadata för datakällor och insamlingskörningar.

### 13.4 Informationsmodell

Det ska finnas en gemensam informationsmodell som gör det möjligt att koppla samman:

- Ekonomiska värden.
- Budgetposter.
- Nämnder.
- Förvaltningar.
- Verksamhetsområden.
- Politiska beslut.
- Ärenden.
- Revisionsrapporter.
- Kostnadshändelser.
- Originaldokument.
- Partiernas budgetförslag.

Detta är en förutsättning för att exempelvis kunna koppla en revisionsanmärkning till ett politiskt beslut och vidare till en ekonomisk konsekvens.

## 14. Övergripande vyer

Plattformen ska innehålla följande huvudvyer:

1. Översikt.
2. Ekonomi.
3. Ekonomiska flöden – Sankey.
4. Undvikbara kostnader.
5. Befolkning och demografi.
6. Näringsliv och arbetsmarknad.
7. Politik och beslut.
8. Ärendespårning.
9. Revision och granskning.
10. Kommunjämförelser.
11. Dokument och rapporter.
12. Datakällor och uppdateringsstatus.
13. Partiernas budgetförslag.

## 15. Icke-funktionella krav

- Desktop-first.
- Responsiv layout där det är lämpligt, men mobilanpassning är inget prioriterat krav.
- God prestanda vid stora datamängder.
- Tydlig separation mellan frontend och backend.
- Spårbarhet för alla uppgifter.
- Historik och versionshantering.
- Robust felhantering.
- Möjlighet till manuell datainsamling.
- Möjlighet att lägga till nya datakällor.
- Möjlighet att komplettera automatiskt insamlad information manuellt.
- Säker hantering av dokument och data.
- Tydlig markering av osäkra, uppskattade och verifierade uppgifter.

## 16. Acceptanskriterier

Lösningen ska betraktas som funktionellt grundläggande när följande kan demonstreras:

1. Kommunens historiska ekonomi kan följas i diagram och tabeller.
2. Budget kan jämföras med faktiskt utfall.
3. Ett Sankey-diagram kan visualisera kommunens intäkter och kostnadsfördelning.
4. Användaren kan fördjupa sig i ekonomiska flöden genom att välja nämnd och verksamhetsområde.
5. Identifierade undvikbara kostnader kan dokumenteras och sammanställas.
6. Kommunala beslut kan sökas och följas mellan olika beslutande instanser.
7. Voteringsresultat kan presenteras med dokumenterad partitillhörighet.
8. Revisionsrapporter kan sammanställas och följas upp.
9. Statistik om befolkning, näringsliv och arbetsmarknad kan visas över tid.
10. Datainsamlingen körs automatiskt två gånger per månad.
11. Det går att se senaste uppdatering och status per datakälla.
12. Misslyckade hämtningar kan identifieras och köras om.
13. Alla centrala uppgifter kan spåras till sin ursprungskälla.
14. Partiernas budgetförslag kan jämföras med antagen budget och med faktiskt utfall.

## 17. Slutlig målbild

Resultatet ska vara en långsiktig analysplattform som gör det möjligt att förstå hur Härnösands kommun utvecklas, hur kommunens pengar används, vilka politiska beslut som fattas och vilka konsekvenser besluten får.

Plattformen ska inte enbart beskriva vad som har hänt, utan även skapa förutsättningar för att analysera varför det har hänt och vad det har fått för konsekvenser.

Den ska kunna användas för att följa upp politiska ambitioner, ekonomiska prioriteringar, verksamheternas resultat och kommunens långsiktiga ekonomiska hållbarhet.

## 17A. Tillägg: Partiernas budgetförslag

Partierna som lägger egna budgetförslag till kommunfullmäktige ska kunna läggas in och analyseras.

- Varje budgetförslag struktureras i samma budgetmodell som den antagna budgeten: skattesats, budgeterat resultat och ram per nämnd.
- **Differensanalys:** hur skiljer sig förslaget från den antagna budgeten, i kronor och procent per nämnd? Kan visas som jämförande Sankey.
- **Efterhandsanalys:** hur förhåller sig förslaget till det faktiska utfallet? Var ramarna mer eller mindre realistiska än i den antagna budgeten?
- **Konsekvensanalys:** konsekvenser utöver ren aritmetik (till exempel effekter på verksamhetsvolym) markeras alltid som analys, med redovisade antaganden, och görs med samma metod för alla partier.

## 18. Beslut och avgränsningar

Beslut fattade 2026-11-13, efter att specen skrevs:

- **Publicering:** plattformen ska bli publik på sikt men är sluten under uppbyggnaden. Allt designas så att det tål publicering: källhänvisning, klassificering och granskningsstatus på varje analys.
- **Avsändare:** plattformen är partipolitiskt obunden. Samma metod gäller för alla partier, och inga värderande formuleringar görs utöver det som är belagt.
- **Roller:** *redaktör* registrerar och redigerar, *utgivare* godkänner för publicering. ("Granskning" används bara om revisionens arbete.) Ingen godkänner sin egen registrering. Inloggning sker med Google. Statusflöde: utkast → granskad → publicerad.
- **Stack:** Python (FastAPI) + Postgres i backend, Vue 3 + TypeScript i frontend. Se ADR-0001.
- **Drift:** egen LXC på Proxmox-servern, deploy via self-hosted GitHub-runner.
- **AI-analys:** körs på alla nya dokument vid varje insamling, och på historiken endast för utvalda dokumenttyper. Budgettak i normaldrift är cirka 200–500 kr per månad, plus en separat engångsbudget för historiken. AI föreslår, och en människa bekräftar. Se ADR-0002.
- **Partisymboler:** partifärger och förkortningar används i stället för logotyper (varumärken).
- **Organ som ingår:** kommunfullmäktige, kommunstyrelsen, samhällsnämnden, socialnämnden och skolnämnden. Utanför: KSAU, vars protokoll inte publiceras rutinmässigt, samt Överförmyndarnämnden och Valnämnden. De kommunala bolagen ingår bara genom koncernsiffrorna i årsredovisningen.
- **Historiskt djup:** dokument (protokoll, handlingar, årsplaner, årsredovisningar, delårsrapporter, revisionsrapporter, budgetförslag) hämtas från och med 2022. Det täcker mandatperioderna 2022–2026 och 2026–2030.
- **Ärenden:** ett ärende kan ha flera diarienummer. Behandlingar kopplas via hänvisningar i beslutsunderlaget, och osäkra kopplingar görs manuellt. Se ADR-0003.
- **Partitillhörighet:** tas från protokollet vid respektive sammanträde. Se ADR-0004.
- **Ekonomiska vyer:** en *nämndvy* (fördelning till organ, från kommunens egna dokument) och en *verksamhetsvy* (verksamhet × kostnadsslag, från SCB:s räkenskapssammandrag, jämförbar med andra kommuner). Verksamhetsvyn byggs först. Mappningen mellan dem byggs när den behövs.
- **Budgetförslag och votering:** varje budgetförslag kopplas till de voteringar där det ställdes.
- **Kostnadshändelser:** beloppssäkerhet per kostnadspost och undvikbarhet per händelse (ADR-0005). En kostnadshändelse kopplas till noll eller flera ärenden, beslut och rekommendationer, och alltid till minst ett källdokument.
- **Revision:** en revisionsrapport innehåller rekommendationer riktade till organ. Varje rekommendation får organets svar och noll eller flera åtgärder med status (beslutad, påbörjad, genomförd, ej genomförd). Uppföljningsstatus beräknas från åtgärderna.
- **Utgivningsbevis:** söks hos Mediemyndigheten inför publik lansering.
- **Kommunjämförelser:** grannkommunerna (Sundsvall, Kramfors, Timrå, Sollefteå, Örnsköldsvik) och Koladas grupp "liknande kommuner", med riksgenomsnittet som referenslinje.
- **Faser:**
  1. Datagrund (källor, insamling, statussida) + ekonomi från Kolada/SCB + Sankey.
  2. Protokoll, ärenden, votering, ledamotsregister.
  3. Revision och uppföljning.
  4. Kostnadshändelser, partibudgetar, AI-analys, kommunjämförelser.
