# Sökning på betydelse med en lokal modell och pgvector

Fulltextsökningen (#142) hittar ord och böjningar men inte betydelse. Den som söker på "skolnedläggning" hittar inte "Avveckling av Säbrå skola". Sökningen kompletteras därför med vektorer (#69), och fulltextlistan och vektorlistan slås ihop med reciprocal rank fusion. Exakta träffar på diarienummer och ledamotsnamn ligger fortfarande först.

Besluten:

1. **En lokal modell, inte en API-tjänst.** Vektorerna räknas med `intfloat/multilingual-e5-small` (384 dimensioner, flerspråkig) med ONNX via fastembed, på processorn i backend. Sökfrågorna lämnar aldrig servern, ingen extern tjänst behöver avtal eller nycklar, och kostnaden är densamma oavsett antal sökningar. Modellfilen (cirka 0,5 GB) byggs in i backend-bilden och laddas inte ner vid start. Den laddas i minnet först när en process behöver den: backend för sökfrågor och rättelser, insamlaren för nya protokoll.
2. **pgvector i den Postgres som redan finns.** Vektorerna ligger i tabellen `sokstycke` med ett HNSW-index, bredvid fulltextindexet. Ingen ny tjänst att driva eller säkerhetskopiera, och filtren (organ, år, typ) är vanlig SQL. Databasbilden byts från `postgres:17-alpine` till `pgvector/pgvector` (`docs/drift.md`). Utan pgvector skapas tabellen inte, och sökningen är enbart fulltext.
3. **Modellens namn lagras vid varje vektor.** En sökenhet väntar på nya vektorer när dess text ändrats (`sha256`) eller när modellen inte är den som används. Ett modellbyte kräver att alla enheter räknas om, men det kan göras stegvis och återupptas: vektorsökningen använder bara vektorer från den aktuella modellen, och fulltextsökningen fungerar under tiden.
4. **Stycken om cirka 300 ord med 50 ords överlapp.** Rubriken och diarienumret står först i varje stycke. En enhet som är kortare är ett stycke.
5. **En lägsta likhet.** Vektorsökningen ger alltid de närmaste styckena, också när inget handlar om frågan. Stycken under en lägsta likhet för modellen räknas därför inte som träffar.

**Inga AI-svar (ADR-0002).** Modellen används bara för att hitta och ordna träffar i källorna. Den skriver ingen text. En träff som bara kommer från vektorsökningen markeras *Liknande innehåll*, och utdraget är en mening ur källan, den som ligger närmast frågan.

Begreppen *sökenhet*, *sökindex* och *stycke* finns i GLOSSARY.md.
