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

Google godkänner bara redirect-adresser på `localhost` eller https, så `http://192.168.1.11` kan inte användas för Google-inloggning. Tills servern har https och ett eget namn nås den med Google-inloggning via en SSH-tunnel:

```bash
ssh -N -L 8080:127.0.0.1:80 kommunkollen
```

Öppna sedan http://localhost:8080. Sätt `PUBLIK_URL=http://localhost:8080` i `/opt/kommunkollen/.env` och lägg `http://localhost:8080/api/auth/google/callback` som redirect-URI i Google-klienten.

Ändringar i `.env` (till exempel tillåtelselistan) börjar gälla när backend startas om:

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose up -d backend"
```

## Vanliga åtgärder

Köra en insamling manuellt (utan inloggning, direkt i backend-containern):

```bash
ssh kommunkollen "cd /opt/kommunkollen && docker compose exec backend /app/.venv/bin/python -m app.insamla"
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
