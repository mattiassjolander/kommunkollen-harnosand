# Ledamotsregister

Registret under Politik och beslut, Ledamöter, listar alla personer som förekommer i protokollens närvarolistor som beslutande, ersättare eller jävig. Övriga närvarande, som tjänstepersoner, är inte med. Registret byggs vid varje insamling och är automatiskt tolkat (ADR-0002).

## Person och namn

Protokollen har inget id för personer, bara namn. Varje namn som förekommer blir en egen person tills en redaktör säger något annat. Skrivs samma person på flera sätt, till exempel "Carl Fredrik Edgren" och "Carl-Fredrik Edgren", kan en redaktör slå ihop namnen. Det ena blir då en namnvariant av det andra. En sammanslagning kan delas upp igen.

Båda åtgärderna loggas med redaktör och tid. De gäller namnen och inte en viss tolkning, så de står kvar när protokollen tolkas om.

## Parti

Partiet är det som protokollet anger vid varje sammanträde (ADR-0004). Ledamotens sida visar partiet över tid, så ett partibyte syns. Registret visar partiet vid det senaste sammanträdet och vilka andra partier personen haft. Står protokollet för något fel, till exempel fel parti för en person, visas det som protokollet anger.

Redaktionen kan fastställa en persons parti för en period (ADR-0006): parti eller partilös ("-"), från och med ett datum och till och med ett datum eller tills vidare, med motivering. En redaktör registrerar perioden på ledamotens sida, och en annan person med rollen utgivare granskar och publicerar den under fliken Partitillhörighet. En publicerad period gäller vid sammanträden under perioden, före protokollets uppgift och efter en rättelse av en enskild förekomst. Ändrar den partiet som protokollet anger markeras förekomsten "Fastställt av redaktionen". Registret och filtret på parti räknar med partiet som gäller. Två publicerade perioder för samma person får inte överlappa.

Partiet visas alltid med förkortning. Partiets färg är bara en prick bredvid (design.md, Partifärger).

## Ledamotens sida

- Fastställd partitillhörighet: de publicerade perioderna, och för en redaktör ett formulär för en ny period.
- Parti över tid, som perioder av sammanträden i följd med samma parti, som protokollen anger det.
- Organ, roller och närvaro: antal sammanträden som beslutande, som ej tjänstgörande ersättare och som frånvarande.
- Alla sammanträden, senaste först, med roll, vem en ersättare tjänstgjorde för, vilka paragrafer och jäv.
- Röster i voteringar, senaste först, med länk till behandlingen och om rösten gick med det vinnande förslaget (`roster` i API:t).

Namn på sammanträdets och behandlingens sidor länkar till ledamotens sida.

## API

- `GET /api/ledamoter?q=&parti=&organ=`: registret.
- `GET /api/partitillhorighet?status=&ledamot_id=`: perioderna. Kräver rollen redaktör eller utgivare.
- `POST /api/partitillhorighet` med `ledamot_id`, `parti`, `fran`, `till` och `motivering`: en period som utkast. Kräver rollen redaktör. 409 om den överlappar en publicerad period.
- `PATCH` och `DELETE /api/partitillhorighet/{id}`: ändrar eller tar bort ett utkast.
- `POST /api/partitillhorighet/{id}/granskning` och `/publicering`: kräver rollen utgivare, och inte den som registrerade perioden.
- `POST /api/partitillhorighet/{id}/versioner`: en ny version av en granskad eller publicerad period, som utkast. `POST /api/partitillhorighet/{id}/aterkallelse` med `motivering`: en utgivare återkallar en publicerad period.
- `GET /api/ledamoter/{id}`: en person. Ett sammanslaget namns id ger personen och `sammanslagen_med`.
- `POST /api/ledamoter/{id}/sammanslagningar?med={id}`: slår ihop `med` (och dess namnvarianter) med `id`. Kräver rollen redaktör. 409 om det redan är samma person.
- `POST /api/ledamoter/{id}/uppdelning`: gör namnet till en egen person igen. Kräver rollen redaktör. 409 om namnet inte är sammanslaget.
