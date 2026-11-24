# AI-analys av dokument körs som skill, inte i insamlingen

Kravspecen (avsnitt 18) säger att AI-analys "körs på alla nya dokument vid varje insamling". I stället körs analysen som en Claude Code-skill som en redaktör startar. Skillen läser dokumenten, skriver förslagen med källhänvisning och läser in dem som utkast. En utgivare som inte läst in dem granskar och publicerar dem (ADR-0002). Budgetförslagens summering görs redan så (`harnosandskollen-budgetforslag`), och motstridigheter och processer i de styrande dokumenten (#63) görs på samma sätt.

Skälen:

1. **Analysen behöver alla dokument samtidigt.** En motstridighet mellan två reglementen syns bara om båda läses tillsammans. De 25 reglementena och delegationsordningarna är cirka 150 000 tokens. Ett anrop per nytt dokument i insamlingen hittar inte motstridigheter mellan dokumenten.
2. **Ingen API-nyckel eller AI-kostnad i driften.** Backend och insamlaren anropar ingen AI-tjänst. Det blir ingen löpande kostnad som växer med antalet dokument, och ingen nyckel ligger på servern.
3. **Varje förslag ska ändå granskas av en människa.** En automatisk körning publicerar ingenting och sparar därför ingen tid för redaktionen. Den skapar bara utkast som någon måste ta hand om.

Konsekvenser:

- När ett analyserat dokument får en ny version körs analysen inte om av sig själv. Den publicerade analysen märks "Dokumentet har ändrats" tills en redaktör har kört skillen igen och tagit ställning.
- Insamlingen gör bara det som går att läsa av utan AI: dokumentinformation, giltighet, versioner och kandidater till flera gällande versioner.
- Ska en analys någon gång köras automatiskt i insamlingen krävs en ny ADR som ersätter den här.
