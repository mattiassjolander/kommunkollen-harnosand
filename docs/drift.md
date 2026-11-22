# Drift

Kommunkollen körs på Proxmox-servern i hemnätverket.

| Vad | Värde |
| --- | --- |
| Container | LXC 107 `kommunkollen`, Debian 13, unprivileged, nesting + keyctl |
| Resurser | 2 kärnor, 4 GB RAM, 1 GB swap, 32 GB disk (`local-lvm`) |
| Adress | http://192.168.1.11 (bara hemnätverket) |
| SSH | `ssh kommunkollen` (root, nyckel `id_ed25519_pve`) |
| App | `/opt/kommunkollen`: `docker-compose.yaml` och `.env` (slumpat databaslösenord) |
| Runner | `kommunkollen-lxc`, etikett `kommunkollen`, körs som användaren `runner` |

## Så deployas appen

1. Push till `main` kör CI: söm 1 och söm 2 testas.
2. Jobbet `images` bygger `kommunkollen-backend` och `kommunkollen-frontend` och publicerar dem på ghcr.io, taggade med commitens sha och `latest`.
3. Jobbet `deploy` körs på runnern i containern. Det kopierar `docker-compose.yaml` till `/opt/kommunkollen`, hämtar de nya images och startar om, och kontrollerar sedan att `/api/halsa` svarar.

Deploy är avstängt tills repo-variabeln `DEPLOY_ENABLED` är `true` (Settings → Secrets and variables → Actions → Variables).

Databasen ligger i Docker-volymen `kommunkollen_db-data` och finns kvar mellan deployer. Migreringarna körs när backend startar.

## Inloggning på servern

**Nuvarande läge:** läsning är öppen för alla (`ANONYM_LASNING` är `true` som standard). Servern kör dessutom med `TESTENV=true`, så inloggningssidan visar testknappar för redaktör och utgivare och alla i hemnätverket kan logga in som dem utan lösenord. Det duger så länge servern bara nås från hemnätverket. Stäng av testinloggningen (`TESTENV=false`) innan servern görs nåbar utifrån.

Google godkänner bara redirect-adresser på `localhost` eller https, så `http://192.168.1.11` kan inte användas för Google-inloggning. Tills servern har https och ett eget namn nås den med Google-inloggning via en SSH-tunnel:

```bash
ssh -N -L 8080:127.0.0.1:80 kommunkollen
```

Öppna sedan http://localhost:8080. Sätt `PUBLIK_URL=http://localhost:8080` i `/opt/kommunkollen/.env` och lägg `http://localhost:8080/api/auth/google/callback` som redirect-URI i Google-klienten.

Ändringar i `.env` (till exempel tillåtelselistan) börjar gälla när backend startas om:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose up -d backend"
```

## Schemalagd insamling

Tjänsten `insamlare` (samma image som backend) startar insamlingen den 1:a och 15:e varje månad kl 03:00 svensk tid. Schemat ändras med `INSAMLING_DAGAR` och `INSAMLING_KLOCKAN` i `.env`, följt av `docker compose up -d`. Tomt `INSAMLING_DAGAR` stänger av schemat.

- Var tjänsten nere vid en planerad tidpunkt körs insamlingen när den startar igen, en gång.
- Två insamlingar körs aldrig samtidigt. En manuell insamling under en schemalagd körning (eller tvärtom) får beskedet att en insamling pågår.
- Statusindikatorn visar nästa planerade körning.

Se schemaläggarens logg:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose logs --tail 50 insamlare"
```

## Fel under insamlingen

- Ett fel hos en källa stoppar inte de andra. Källan får status Misslyckad med felmeddelandet i vyn Datakällor.
- Nätverksfel, timeout (30 s) och svar 429 eller 5xx försöks igen två gånger, efter 2 och 4 sekunder.
- Anropen mot varje källa begränsas av `KOLADA_ANROP_PER_SEKUND`, `SCB_ANROP_PER_SEKUND` och `PROTOKOLL_ANROP_PER_SEKUND`.
- Protokollen hämtas från organens sidor och arkivmapparna från 2022. Den första insamlingen hämtar alla, cirka 270 filer och 200 MB som sparas i databasen, och tar några minuter. Därefter hämtas arkivets filer inte igen. `PROTOKOLL_URVAL` sätts inte i drift.
- Ett protokoll som inte går att tolka sparas och visas ändå. Källan får status Delvis fel, och felmeddelandet anger vilket protokoll det gäller.
- Avbryts en körning (t.ex. vid omstart) återupptas den vid nästa insamling. Källor som redan var klara hoppas över, och inga uppgifter dubbleras.
- En redaktör kan köra om en enskild källa med knappen Kör om i vyn Datakällor.

## Vanliga åtgärder

Köra en insamling manuellt (utan inloggning, direkt i backend-containern):

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose exec backend /app/.venv/bin/python -m app.insamla"
```

Tolka om de lagrade protokollen efter en förbättrad tolkning (hämtar inget från kommunen):

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose exec backend /app/.venv/bin/python -m app.tolka_om"
```

Slå ihop planerade sammanträden med protokollet samma dag, när mötet började mer än en timme senare än
planerat och protokollet lästes in före #107. Utan `--utfor` visas bara paren. Ta en säkerhetskopia först:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose exec backend /app/.venv/bin/python -m app.sla_ihop_planer"
```

Se status och loggar:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose ps && docker compose logs --tail 50 backend"
```

Starta om appen:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose restart"
```

Gå tillbaka till en tidigare version (sha från en tidigare lyckad deploy):

```bash
ssh kommunkollen "cd /opt/kommunkollen && TAG=<sha> docker compose up -d"
```

Starta om runnern:

```bash
ssh kommunkollen "systemctl restart actions.runner.mattiassjolander-kommunkollen-harnosand.kommunkollen-lxc.service"
```

## Säkerhetskopiering

Containern ingår **inte** i Proxmox nattliga backupjobb `nattlig-backup` än. Lägg till den på Proxmox-värden:

```bash
ssh pve "pvesh set /cluster/backup/nattlig-backup --vmid 101,103,105,106,107"
```
