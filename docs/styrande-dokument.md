# Styrande dokument

Kommunens styrande dokument samlas in från sidan [Kommunens styrande dokument](https://harnosand.se/kommun--styrning/forvaltning-och-organisation/kommunens-styrande-dokument.html) (#63). Varje fil sparas som plattformens kopia, med versioner, dokumentinformationen ur rutan på första sidan, giltighet och koppling till beslutet som fastställde dokumentet. Begreppen står i [GLOSSARY.md](../GLOSSARY.md), avsnitt *Styrande dokument*.

## Motstridigheter

En motstridighet är något i eller mellan styrande dokument som inte går ihop (#151). Den är redaktionens analys och märks **Analys** (`docs/design.md`). Det finns tre typer:

| Typ | `typ` | Vad som anges |
|---|---|---|
| Motsägelse | `motsagelse` | Två bestämmelser som säger olika saker om samma sak. Båda ställena citeras ordagrant med dokument, sida och paragraf. |
| Felaktig hänvisning | `felaktig_hanvisning` | En hänvisning till ett kapitel, en paragraf, ett organ eller ett dokument som inte finns. Hänvisningen citeras, och en kontrollerbar uppgift med källa anger det som finns. |
| Flera gällande versioner | `flera_versioner` | Samma dokument eller sak ligger ute flera gånger som gällande. Dokumenten anges. |

En utgången giltighet är ingen motstridighet. Den syns som giltigheten på dokumentsidan.

### Var förslagen kommer ifrån

- **Insamlingen** tar fram kandidater till flera gällande versioner bland alla gällande styrande dokument: dokument med samma diarienummer i dokumentinformationen (`KS/2022-000209` och `2022-000209` räknas som samma), och titlar som bara skiljer sig i skiljetecken eller årtal. Typen kräver ett omdöme, så kandidaterna blir utkast och publiceras aldrig direkt.
- **Skillen** `harnosandskollen-styrande-dokument` läser reglementena och delegationsordningarna tillsammans och föreslår motstridigheter av alla tre typerna. Backend anropar ingen AI (ADR-0009).

Skillens omfång är dokumenten under rubrikerna *Reglementen, ägardirektiv och bolagsordning* och *Delegationer*, utom delegationsordningen för Överförmyndarnämnden (organet ligger utanför plattformen, kravspec avsnitt 18). Inläsningen avvisar ett förslag som hänvisar till ett dokument utanför omfånget.

Ett förslag som redan finns, i vilken status som helst, läses inte in igen. Två förslag om flera gällande versioner med samma dokument är samma förslag, oavsett om det kom från insamlingen eller skillen.

### Filen från skillen

Skillen skriver `data/styrande-dokument/motstridigheter.json` i huvudmappen för repot (mappen versionshanteras inte):

```json
{
  "motstridigheter": [
    {
      "typ": "felaktig_hanvisning",
      "forklaring": "Reglementet anger att verksamheten tydliggörs i kapitel 2 till 9 (s. 3). Innehållsförteckningen har kapitel 1–8 (s. 2).",
      "citat": [
        {"dokument": "18.580e43d7163221b2781b73fe", "sida": 3, "text": "verksamhet och uppgifter i kapitel 2 till 9"}
      ],
      "uppgift": {"text": "Reglementet har kapitel 1–8.", "dokument": "18.580e43d7163221b2781b73fe", "sida": 2}
    },
    {
      "typ": "motsagelse",
      "forklaring": "Dokument A anger att kallelsen skickas fem dagar före sammanträdet (s. 4). Dokument B anger sju dagar (s. 9).",
      "citat": [
        {"dokument": "18.…", "sida": 4, "paragraf": "3 kap. 2 §", "text": "…"},
        {"dokument": "18.…", "sida": 9, "paragraf": "12 §", "text": "…"}
      ]
    },
    {
      "typ": "flera_versioner",
      "forklaring": "Samhällsnämndens delegationsordning ligger ute både som ”Delegationsordning för samhällsnämnden” och som en konsoliderad version från 2021-06-17.",
      "dokument": ["18.4b6c551c1679dec5d0a4a691", "18.32ef4911832d26bbc62e0bd"]
    }
  ]
}
```

| Fält | Innehåll |
|---|---|
| `typ` | `motsagelse`, `felaktig_hanvisning` eller `flera_versioner`. |
| `forklaring` | Högst två meningar som återger vad som står, efter mallen för typen nedan. |
| `citat` | Ställena i dokumenten. `dokument` är dokumentets id på kommunens sida (`18.…`, `sitevision_id` i API:t). `sida` är sidan i PDF:en räknat från 1, inte det tryckta sidnumret. `text` är ett ordagrant citat från sidan. `paragraf` krävs för en motsägelse, till exempel `"3 kap. 2 §"`. |
| `uppgift` | Bara för en felaktig hänvisning: `text` är den kontrollerbara uppgiften om det som finns, med `dokument` och `sida` som källa. Med `citat` kan ett ordagrant citat från källan läggas till. |
| `dokument` | Bara för flera gällande versioner: minst två dokument-id. |

Varje citat hör till dokumentets senaste version när filen läses in, och versionen sparas med citatet.

### Kontrollerna vid inläsningen

Hela filen läses in i en transaktion. Avvisas något förslag läses inget in, och felet anger förslagets nummer:

- Typen är en av de tre.
- En motsägelse har minst två citat, var och ett med dokument, sida, paragraf och text. En felaktig hänvisning har ett citat och en uppgift med dokument och sida. Flera gällande versioner har minst två dokument.
- Dokumentet finns på kommunens sida och ingår i omfånget. Sidan finns i dokumentet.
- Citatet står ordagrant på sidan. Jämförelsen bortser från blanksteg, radbrytningar, avstavning, skillnader mellan bindestreck och tankstreck och citattecken, och skiftläge.
- Förklaringen är högst två meningar och innehåller inte orden *fel*, *brist*, *slarv* eller *motsäger sig själv*.

### Förklaringens mall

Förklaringen återger vad dokumenten säger och nämner inga personer, inte heller dokumentansvariga.

- **Motsägelse:** "Dokument A anger X (s. 3). Dokument B anger Y (s. 7)."
- **Felaktig hänvisning:** "Dokumentet hänvisar till X (s. 3). Dokumentet har Y (s. 2)."
- **Flera gällande versioner:** "X ligger ute både som A och som B." eller, från insamlingen, "A och B har samma diarienummer i dokumentinformationen, KS/2022-000209."

### Granskning och status

- Flödet är utkast → granskad → publicerad, som för rättelser. En utgivare som inte har läst in förslaget granskar och publicerar det. Ett förslag som inte håller avvisas med motivering.
- Redaktionen har granskningsvyn under Redaktion → Motstridigheter, filtrerbar på typ och dokument.
- En publicerad motstridighet har status **Ny**, **Anmäld till kommunen** (datum) eller **Åtgärdad av kommunen** (datum och anteckning), som en redaktör sätter. Varje ändring sparas. En utgivare kan återkalla den med motivering.
- När ett berört dokument får en ny version märks motstridigheten **"Dokumentet har ändrats"**. Analysen körs inte om av sig själv. En redaktör tar ställning i granskningsvyn: märkningen tas bort och versionerna blir de senaste. Håller motstridigheten inte längre återkallas den för sig.

### Visning

- Dokumentsidan har avsnittet *Motstridigheter* med de publicerade, märkta Analys.
- Listan över styrande dokument visar antalet publicerade motstridigheter per dokument.
- Den samlade listan *Motstridigheter* under Styrande dokument kan filtreras på typ och status och används för att anmäla dem till kommunen.
