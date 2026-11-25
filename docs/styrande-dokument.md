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

## Processer

En process är en arbetsgång som redaktionen har valt att beskriva ur reglementena och delegationsordningarna (#152), till exempel att kallelsen ska skickas senast fem dagar före sammanträdet. Den består av steg som kan hämtas ur flera dokument. Den är redaktionens analys och märks **Analys** (`docs/design.md`). Hur det faktiskt går till enligt protokollen jämförs inte här. Processer ur policyer, planer, program, riktlinjer och föreskrifter ingår inte.

### Listan

AI hittar och grupperar inte processer på egen hand, eftersom det blir subjektivt. Redaktionen bestämmer listan, och skillen fyller i stegen. Den första listan:

1. Kallelse till sammanträde
2. Justering av protokoll
3. Motion
4. Medborgarförslag
5. Anmälan av delegationsbeslut
6. Budgetprocessen

En redaktör lägger till en ny process under Redaktion → Processer. Den blir ett utkast utan steg.

### Stegen

Varje steg anger:

- **vem** som gör något: ett organ, ordföranden, förvaltningen eller en ledamot,
- **vad** som görs,
- **när**, eller inom vilken tidsfrist, om dokumentet anger det,
- **källan**: ett ordagrant citat med dokument, version, sida och paragraf.

Skillen `harnosandskollen-styrande-dokument` läser de 25 dokumenten i omfånget (se *Motstridigheter*) för varje process på listan och skriver stegen. Backend anropar ingen AI (ADR-0009).

### Filen från skillen

Skillen skriver `data/styrande-dokument/processer.json` i huvudmappen för repot:

```json
{
  "processer": [
    {
      "process": "Kallelse till sammanträde",
      "steg": [
        {
          "vem": "Ordföranden",
          "vad": "Kallelsen skickas digitalt till varje ledamot och ersättare.",
          "nar": "Senast fem dagar före sammanträdesdagen",
          "kalla": {"dokument": "18.580e43d7163221b2781b73fe", "sida": 4, "paragraf": "§ 13",
                    "text": "Kallelsen ska digitalt tillsändas varje ledamot och ersättare senast fem dagar före sammanträdesdagen."}
        }
      ]
    },
    {
      "process": "Justering av protokoll",
      "steg": [
        {
          "vem": "Ordföranden och en ledamot",
          "vad": "Justerar protokollet.",
          "nar": "Senast 14 dagar efter sammanträdet",
          "kalla": {"dokument": "18.580e43d7163221b2781b73fe", "sida": 5, "paragraf": "§ 26",
                    "text": "Protokoll justeras senast 14 dagar efter sammanträdet av ordförande och en ledamot."}
        }
      ]
    }
  ]
}
```

| Fält | Innehåll |
|---|---|
| `process` | Namnet på processen som det står på redaktionens lista. |
| `steg` | Stegen i ordning. Minst ett. |
| `vem` | Vem som gör något, som dokumentet anger det. |
| `vad` | Vad som görs, kort och utan värdering. |
| `nar` | När eller inom vilken tidsfrist, om dokumentet anger det. Utelämnas annars. |
| `kalla` | `dokument` (`18.…`), `sida` i PDF:en räknat från 1, `paragraf` och `text`, ett ordagrant citat från sidan. Saknar dokumentet paragrafer anges punkten eller avsnittets rubrik, till exempel `"Registrering och anmälan av delegationsbeslut"`. |

Citatet hör till dokumentets senaste version när filen läses in, och versionen sparas med steget. Filen kan ha en eller flera processer. Stegen för en process ersätter de tidigare stegen, och processen blir ett utkast som granskas på nytt. Samma steg som redan finns läses inte in igen.

### Kontrollerna vid inläsningen

Hela filen läses in i en transaktion. Avvisas något läses inget in, och felet anger processens och stegets nummer, till exempel "Process 2 (Justering av protokoll), steg 1, källan: citatet står inte ordagrant på sidan 5":

- Processen finns på redaktionens lista och står bara en gång i filen. Den har minst ett steg.
- Varje steg har vem, vad och en källa med dokument, sida, paragraf och citat.
- Dokumentet finns på kommunens sida och ingår i omfånget, de 25 dokumenten. Sidan finns i dokumentet.
- Citatet står ordagrant på sidan, med samma jämförelse som för motstridigheter.
- En publicerad process läses inte in med andra steg. Håller den inte längre återkallar en utgivare den först. En avvisad process läses inte in.

### Granskning

- Processen går som en helhet, med alla sina steg, från utkast via granskad till publicerad (ADR-0002). En utgivare som varken lade till processen eller läste in stegen granskar och publicerar den. En process utan steg kan inte granskas.
- En process som inte ska beskrivas avvisas med motivering. En publicerad process kan återkallas med motivering.
- När ett dokument som ett steg citerar får en ny version märks **det steget** "Dokumentet har ändrats". Processen förblir publicerad. En redaktör läser den nya versionen och tar ställning under Redaktion → Processer: står citatet kvar på sidan tas märkningen bort och versionen blir den senaste. Annars körs skillen för processen igen, efter att en utgivare har återkallat den.

### Visning

- **Processidan** under Styrande dokument → Processer visar stegen i ordning med vem, vad, när, citat och källa med länk till sidan i PDF:en. Hela processen har streckad kantlinje och etiketten Analys.
- En publicerad motstridighet som citerar samma ställe som ett steg visas vid steget. Samma ställe är samma dokument och sida, och samma paragraf när båda anger en (`§ 13` och `13 §` räknas som samma).
- **Dokumentsidan** listar de publicerade processerna som dokumentet ingår i.
- **Listan** över styrande dokument visar antalet publicerade processer per dokument.
