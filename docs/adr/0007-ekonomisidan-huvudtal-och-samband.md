# Ekonomisidan börjar med huvudtal och visar hur nyckeltalen hänger ihop

Ekonomisidan visade 37 kort i fem grupper utan läsordning. Samma företeelse visades ofta två gånger, som belopp från SCB och som kronor per invånare från Kolada, och det fanns inga samband mellan talen och ingen referenspunkt. Sidan var svår att navigera och att förstå (#79).

Sidan byggs därför om efter de här principerna:

1. **Huvudtal först.** Sidan börjar med en översikt med fem huvudtal: årets resultat i procent av skatter och generella statsbidrag, nettokostnadsandel, självfinansieringsgrad, soliditet inklusive pensionsåtaganden och låneskuld per invånare. Varje huvudtal har en mening i klartext om vad måttet betyder och länkar till sitt kort. Övriga kort är fördjupning. Låneskulden per invånare finns inte som mått hos källorna och beräknas av Kommunkollen ur SCB:s långfristiga lån och folkmängden. Det står vid talet, som för rörelsekapitalet.
2. **Grupper som frågor.** Grupperna formuleras som frågor en invånare kan ställa, t.ex. *Går kommunen med överskott?*, med en kort ingress.
3. **Ett kort per företeelse.** Redovisar SCB ett belopp totalt och Kolada samma sak per invånare blir det ett kort med växeln *Totalt (mnkr) / Per invånare*. Källan anges för den variant som visas. Valet gäller alla kort och sparas i URL:en.
4. **Kopplingar är räknesamband.** Sambanden visas som räkning, inte som tolkning: ett brodiagram bygger upp årets resultat av sina delar, korten länkar till varandra under *Hänger ihop med* med en saklig mening om sambandet, och skatteintäkterna länkar till skatteunderlagsprognosen. Går delarna inte ihop med summan enligt källan visas avvikelsen.
5. **Riket som referens.** Genomsnittet för riket från Kolada kan visas som en valbar jämförelselinje. Bara skillnaden visas.
6. **Budget mot utfall** och kopplingen till politiska beslut är ett eget arbete (#83). Jämförelse med liknande kommuner kan komma senare.

**Ingen värdering.** Plattformen säger inte om ett värde är bra eller dåligt, högt eller lågt, eller om Härnösand ligger bra eller dåligt till jämfört med riket. Texterna förklarar vad måttet betyder och hur det räknas. Färger och markeringar skiljer serier och källor åt och signalerar inte bra eller dåligt. En divergerande skala betyder högre eller lägre än jämförelsen (`docs/design.md`). Detta följer kravspecens krav på en partipolitiskt obunden avsändare utan värderande formuleringar.

Begreppen *nyckeltal* och *huvudtal* finns i GLOSSARY.md. Vilka mått som används för varje krav redovisas i `docs/tackning-ekonomi.md`.
