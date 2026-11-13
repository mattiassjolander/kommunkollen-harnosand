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

## Vanliga åtgärder

Köra en insamling manuellt:

```bash
ssh kommunkollen "curl -s -X POST http://127.0.0.1/api/insamlingar"
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
