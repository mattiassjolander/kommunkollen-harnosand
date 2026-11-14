# Kommunkollen Härnösand

Begreppen som används för att beskriva hur Härnösands kommun fattar beslut och använder sina pengar.

## Organisation

**Organ**:
En politiskt sammansatt församling som håller sammanträden och fattar beslut: kommunfullmäktige, kommunstyrelsen eller en nämnd.
_Avoid_: Instans, beslutande organ

**Förvaltning**:
Den tjänstepersonsorganisation som bereder ärenden åt ett organ. Förvaltningen är inget organ och gör inga behandlingar.

**Sammanträde**:
Ett möte i ett organ, dokumenterat i ett protokoll.
_Avoid_: Möte

**Protokoll**:
Den justerade dokumentationen av ett helt sammanträde: närvaro, behandlingar, yrkanden, voteringar och beslut. Protokollet är huvudkällan för allt som hände på sammanträdet.
_Avoid_: Helprotokoll, mötesanteckningar

**Paragrafprotokoll**:
Ett protokoll för en eller några enstaka behandlingar, som justeras eller lämnas ut före protokollet för hela sammanträdet (direktjustering, protokollsutdrag). Det gäller bara tills protokollet finns.
_Avoid_: Utdrag (som begrepp)

**Ledamot**:
En förtroendevald som deltar i ett organs sammanträde, som ordinarie ledamot eller som tjänstgörande ersättare. Partitillhörigheten är den som protokollet anger för personen vid just det sammanträdet.
_Avoid_: Politiker, representant

## Beslutsprocessen

**Ärende**:
En sak som kommunen handlägger och som kan passera flera organ över tid, från beredning till slutligt beslut. Ett ärende kan ha flera diarienummer.
_Avoid_: Fråga, sak, punkt

**Diarienummer**:
Det nummer ett ärende har i ett visst organs diarieserie, till exempel `SAM/2026-131` eller `KS/2026-386`. Det identifierar inte ärendet som helhet.
_Avoid_: Ärendenummer, dnr (som begrepp)

**Tjänsteskrivelse**:
Förvaltningens skriftliga underlag och förslag till beslut i ett ärende.

**Beslutsunderlag**:
De handlingar ett organ har att ta ställning till vid en behandling.
_Avoid_: Bilaga, handling

**Behandling**:
Ett tillfälle där ett organ tar upp ett ärende på ett sammanträde, motsvarande en paragraf i ett protokoll.
_Avoid_: Paragraf (som begrepp), ärendepunkt

**Beslut**:
Det ett organ beslutade vid en behandling, till exempel ett förslag till ett annat organ, ett slutligt beslut eller en återremiss.
_Avoid_: Politiskt beslut, utslag

**Slutligt beslut**:
Det beslut i ett ärende som inte längre är ett förslag till ett annat organ.

**Yrkande**:
Ett förslag till beslut som en ledamot eller ett parti lägger fram vid en behandling.

**Votering**:
En omröstning vid en behandling, där varje ledamots röst (ja, nej, avstår) är dokumenterad i protokollet. En behandling kan ha flera voteringar, till exempel först om kontraproposition och sedan en huvudvotering.
_Avoid_: Omröstning (som begrepp), röstning

**Reservation**:
En ledamots eller ett partis anmälan i protokollet om att de inte står bakom beslutet vid en behandling.

## Ekonomiska konsekvenser

**Kostnadshändelse**:
En avgränsad händelse som har orsakat kommunen kostnader och som registrerats för analys. Den består av en eller flera kostnadsposter och bygger alltid på minst ett källdokument.
_Avoid_: Undvikbar kostnad, onödig kostnad, slöseri

**Kostnadspost**:
Ett enskilt belopp inom en kostnadshändelse, till exempel ombudsarvode eller intern arbetstid.

**Beloppssäkerhet**:
Hur väl en kostnadsposts belopp är belagt: dokumenterad (styrkt med ekonomiskt underlag) eller uppskattad (beräknad med redovisade antaganden).
_Avoid_: Bedömning, klassificering

**Undvikbarhet**:
Om en kostnadshändelse hade kunnat undvikas: ej undvikbar, ej fastställd, potentiellt undvikbar (ett rimligt alternativ har identifierats) eller styrkt undvikbar (stöds av dokumenterat underlag).
_Avoid_: Bedömning, klassificering, onödig

## Revision

**Revisionsrapport**:
Kommunrevisionens skriftliga redovisning av en granskning.

**Granskning**:
Revisionens undersökning av ett område eller ett organs verksamhet. Används bara om revisionens arbete.
_Avoid_: Kontroll, utredning

**Rekommendation**:
En åtgärd som revisionen i en revisionsrapport rekommenderar ett visst organ att vidta.
_Avoid_: Anmärkning, påpekande

**Svar**:
Ett organs yttrande över en revisionsrapports rekommendationer.

**Åtgärd**:
Något ett organ har beslutat att göra med anledning av en rekommendation, med status beslutad, påbörjad, genomförd eller ej genomförd.

## Budget

**Antagen budget**:
Den budget kommunfullmäktige har beslutat om för ett år (i Härnösand kallad årsplan).
_Avoid_: Majoritetens budget

**Budgetförslag**:
Ett partis eller en partigrupps eget förslag till budget, lagt till kommunfullmäktiges budgetbehandling. Det är ett yrkande som ställs i en eller flera voteringar.
_Avoid_: Skuggbudget, alternativbudget

## Redaktionellt arbete

**Redaktör**:
En person som registrerar och redigerar uppgifter på plattformen.

**Utgivare**:
En person som godkänner en redaktörs registrering för publicering. Ingen godkänner sin egen registrering.
_Avoid_: Granskare, godkännare

**Automatiskt tolkad uppgift**:
En uppgift som plattformen har läst ut ur ett protokoll utan att någon redaktör har granskat den. Den visas för läsare med en markering om att den inte är granskad.
_Avoid_: Ogranskad uppgift, maskinuppgift

## Datainsamling

**Datakälla**:
Ett ställe plattformen hämtar uppgifter från, t.ex. Kolada eller kommunens protokoll.
_Avoid_: Källsystem, feed

**Insamlingskörning**:
Ett tillfälle då plattformen kontrollerar alla datakällor, manuellt eller enligt schema. Varje datakälla får ett eget resultat i körningen.

**Kontroll**:
Att plattformen frågar en datakälla om nya eller ändrade uppgifter. En kontroll utan fel är lyckad även när inget nytt fanns.
_Avoid_: Uppdatering (säger inget om huruvida något var nytt)

**Inga nya uppgifter**:
Resultatet när en kontroll gick bra men källan inte hade något nytt eller ändrat. Det är inte ett fel.

**Delvis fel**:
En datakälla där en del av uppgifterna gick att hämta men inte allt.

**Fullständigt uppdaterad / delvis inaktuell**:
Plattformen är fullständigt uppdaterad när den senaste insamlingskörningen kontrollerade alla datakällor utan fel. Annars är informationen delvis inaktuell.

**Reviderad uppgift**:
En uppgift som källan har publicerat på nytt med ett annat värde för samma period. Det nya värdet blir en ny version, och de tidigare versionerna finns kvar.
_Avoid_: Revision (betyder kommunrevisionens granskning), uppdaterat värde

**Avbruten körning**:
En insamlingskörning som stoppades innan alla datakällor var kontrollerade, t.ex. vid en omstart. Nästa insamling återupptar den.
