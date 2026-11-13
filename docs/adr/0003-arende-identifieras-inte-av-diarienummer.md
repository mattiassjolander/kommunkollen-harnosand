# Ett ärende identifieras inte av sitt diarienummer

I Härnösand har nämnderna egna diarieserier. När ett ärende går vidare till kommunstyrelsen får det ett nytt nummer, som kommunfullmäktige sedan återanvänder (Samhällsnämnden `SAM/2026-131` → KS och KF `KS/2026-386`). Nämndens nummer nämns inte i KS-paragrafen. Ett ärende är därför plattformens egen entitet, med ett eller flera diarienummer som egenskaper. Behandlingar kopplas samman via hänvisningarna i beslutsunderlaget ("Protokollsutdrag samhällsnämnden 20260521 §61"). Kopplingar som inte kan göras säkert läggs i en kö för manuell koppling av en redaktör.

## Considered Options

- Diarienummer som nyckel: enkelt, men delar varje nämnd→KS-kedja i två ärenden, och då fungerar inte ärendespårningen.
