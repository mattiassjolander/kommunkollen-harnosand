# Sammansättning

Sidan Sammansättning under Politik och beslut visar hur kandidater, valda och tjänstgörande ledamöter fördelar sig på kön och ålder, totalt och per parti, för ett organ och en mandatperiod (#65). De röstberättigade i Härnösand visas som referens. Bara sammanställd statistik publiceras.

## Källor

Datakällan **Valmyndigheten** ingår i insamlingskörningen och hämtar för valen 2022 och 2026:

| Fil | Innehåll |
|---|---|
| `resultat.val.se/filer/val{år}/info/ledamoter_med_historik.csv` | Valda ledamöter med invalsordning, invalsdatum, avgångsdatum, kön och ålder på valdagen |
| `resultat.val.se/filer/val{år}/info/ledamoter_och_ersattare_utokad.csv` | Ersättare per ledamot, med ersättargrupp, ersättarordning och kandidatnummer |
| `data.val.se/filer/val{år}/parti/kandidaturer.zip` | Kandidaterna: parti, lista, ordning, kandidatnummer, namn, ålder på valdagen, kön och folkbokföringskommun |
| Röstberättigade per valdistrikt uppdelat på kön och ålder, valdagen 2026, kommunfullmäktige (val.se, *Rådata val 2026*) | De röstberättigade i Härnösand per kön och åldersgrupp |

Bara raderna för kommunfullmäktige i Härnösand sparas. De filtreras på kolumnerna (`Valtyp` och `Kommun`, respektive `VALTYP` och `VALOMRÅDESKOD` = 2280), aldrig på en sträng i hela raden. Valmyndighetens förkortning NorrP sparas som NP.

En person i valet identifieras med valår och kandidatnummer, som är detsamma bland kandidaterna, de valda och ersättarna. Ersättare får därför kön och ålder ur kandidaturerna.

**Gallring.** Valmyndigheten gallrar kandidaternas personuppgifter och skriver då "Gallrad uppgift". Ett värde som plattformen redan har sparat skrivs aldrig över, och kandidaten märks med när källan gallrade. 2022 års kandidaturer var redan gallrade när plattformen började hämta dem. De valda 2022 har ändå kön och ålder i filen över valda. 2018 finns inte i filerna.

**Reviderade uppgifter.** Ändrar källan ett värde, till exempel ett avgångsdatum, eller tillkommer en efterträdare, sparas det tidigare värdet med hämtningstid och körning i `valandring`.

## Koppling till ledamotsregistret

Personerna i valet kopplas till personerna i ledamotsregistret, så att tjänstgörande och nämndledamöter får kön och ålder.

- **Automatisk:** namnet stämmer exakt (utan hänsyn till versaler, blanksteg och "Efternamn, Förnamn"), bara en person i registret har namnet, bara en person i valet har det, och partiet som gäller enligt protokollen (ADR-0004, ADR-0006) är ett enda och detsamma som i valet.
- **Förslag:** samma namn men protokollen anger inget parti, ett annat parti eller flera partier (till exempel ett partibyte), samma namn för flera personer i registret eller flera kandidater, eller ett liknande namn med mellannamn eller dubbelnamn (alla delar av det kortare namnet finns i det längre). En redaktör bekräftar eller avvisar förslaget.

Kopplingarna räknas om när val- eller protokolluppgifter ändras. En redaktörs beslut står kvar. När ett förslag bekräftas tas andra förslag för samma person i valet bort.

## Personer utan uppgift

En redaktör kan ange kön, födelseår eller båda för en person som saknar uppgift hos Valmyndigheten, med källa: länk, eller dokument och sida. Uppgiften går genom granskningsflödet (ADR-0002), utkast, granskad och publicerad, och ingen godkänner sin egen registrering. En utgivare kan återkalla en publicerad uppgift med motivering. Att gissa kön utifrån namn eller bild är inte tillåtet, och gränssnittet säger det. Valmyndighetens uppgifter går före redaktionens.

## Statistik

- **Mått:** antal, kvinnor, män och uppgift saknas (antal och andel), medelålder och åldersgrupperna 18–29, 30–49, 50–64 och 65+ samt uppgift saknas.
- **Indelning:** totalt och per parti, per organ (kommunfullmäktige, kommunstyrelsen och nämnderna) och per mandatperiod (2022–2026 och 2026–2030). Kommunfullmäktiges mandatperiod börjar den 15 oktober valåret.
- **Kandidater** (bara kommunfullmäktige): alla på listorna, och de tio högst placerade per parti (bara 2026, eftersom 2022 års uppgifter är gallrade).
- **Valda:** i kommunfullmäktige de ordinarie ledamöterna vid mandatperiodens start, och de valda med efterträdare under perioden. Kommunstyrelsen och nämnderna finns inte i Valmyndighetens filer. För dem räknas de som står som ordinarie ledamöter (inte ersättare) i närvarolistorna under perioden.
- **Tjänstgörande:** de som är beslutande enligt närvarolistan, en gång per person och sammanträde, så den som tjänstgjort ofta väger tyngre. Partiet är det som gäller vid sammanträdet (fastställd period, annars protokollet).
- **Ålder:** åldern på valdagen. För tjänstgörande räknas åldern vid sammanträdet fram ur åldern på valdagen (fel med högst ett år, eftersom födelsedagen är okänd) eller ur födelseåret.
- **Referens:** de röstberättigade på valdagen 2026 per kön och åldersgrupp. Valmyndigheten redovisar kön och ålder var för sig.
- Texten "Kön enligt folkbokföringen (Valmyndigheten)" står vid diagrammen, och varje led har en källrad med fil, källans stämpel och hämtningsdatum.

## Integritet

Bara sammanställd statistik publiceras. Kön och ålder visas inte på personsidorna, och API:t lämnar inte ut dem per person till läsare. Ett parti med en enda ledamot i ett organ visar ändå personens kön och ålder i statistiken. Det accepteras, eftersom uppgiften redan är offentlig hos Valmyndigheten. Redaktörer och utgivare ser uppgifterna per person i redaktionens del av sidan.

## API

- `GET /api/sammansattning?period=2026&organ=KF`: statistiken, öppen för läsare.
- `GET /api/sammansattning/kopplingar?status=`: kopplingarna. Kräver rollen redaktör eller utgivare.
- `POST /api/sammansattning/kopplingar/{id}/bekraftelse` och `/avvisning`: kräver rollen redaktör.
- `GET /api/sammansattning/personer`: personerna i registret med kön, ålder, källa, kopplingar och väntande uppgifter. Kräver rollen redaktör eller utgivare.
- `GET /api/sammansattning/uppgifter?status=` och `POST /api/sammansattning/uppgifter` med `ledamot_id`, `kon`, `fodelsear` och `kalla`: redaktionens uppgifter. Att skapa kräver rollen redaktör, och 409 om personen redan har uppgifter från Valmyndigheten.
- `DELETE /api/sammansattning/uppgifter/{id}`: tar bort ett eget utkast.
- `POST /api/sammansattning/uppgifter/{id}/granskning`, `/publicering` och `/aterkallelse`: kräver rollen utgivare, och inte den som registrerade uppgiften.
