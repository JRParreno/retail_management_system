# Windows setup — MotoShop RMS

Local development and production on the same Windows PC (Docker Postgres + app on host).

## Prerequisites

Install and start:

| Tool | Notes |
|------|--------|
| [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) | WSL2 backend recommended; leave it running |
| [Python 3.11+](https://www.python.org/downloads/) | Check **Add python.exe to PATH** |
| [Node.js 20+ LTS](https://nodejs.org/) | Or `winget install OpenJS.NodeJS.LTS` |

Optional:

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install --id Cloudflare.cloudflared   # public HTTPS tunnel
```

## Local development

From the repo root in PowerShell:

```powershell
.\local_run.ps1
# or jump straight to start-all:
.\local_run.ps1 5
```

CMD:

```bat
local_run.bat
local_run.bat 5
```

| # | Action |
|---|--------|
| 1 | First-time setup (Docker + migrate + seed + npm install) |
| 2 | Start Postgres |
| 3 | Stop Postgres |
| 4 | Migrate + seed |
| 5 | Start ALL (Postgres + API + UI, LAN HTTPS) |
| 6 | Backend only (`:8000`) |
| 7 | Frontend only (`:3000`) |
| 8 | Status check |
| 9 | Seed / reset admin |
| A | Open Windows Firewall ports 3000/8000 (run as Administrator if it fails) |

- App (this PC): https://127.0.0.1:3000  
- API docs: http://127.0.0.1:8000/docs  
- Demo: `admin` / `admin123` · `cashier` / `cashier123`

On first phone/tablet visit, accept the self-signed certificate warning.

## Production (shop PC)

Same machine, no demo catalog — admin only:

```powershell
.\run_prod.ps1
# restart without rebuild:
.\run_prod.ps1 --skip-build
# stop:
.\run_prod.ps1 --stop-only
```

Public HTTPS (no router port-forward):

```powershell
.\run_prod.ps1 --with-tunnel quick
.\run_prod.ps1 --with-tunnel named
.\run_prod.ps1 --tunnel-only quick
```

See `cloudflare/README.md`. Login after deploy: `admin` / `admin123` — change it immediately.

> Ubuntu Nginx/systemd edge (`run_ubuntu_https.sh`, `run_prod_menu.sh`) is Linux-only. On Windows use `run_prod.ps1` + optional Cloudflare Tunnel.

## Database backups

```powershell
.\run_db_backup.ps1 status
.\run_db_backup.ps1 backup
.\run_db_backup.ps1 install-cron          # Task Scheduler nightly 02:00
.\run_db_backup.ps1 list
.\run_db_backup.ps1 restore latest        # destructive; confirm with YES
```

Dumps default to `.\backups\`. Set `RMS_BACKUP_DIR` / `RMS_BACKUP_OFFSITE` if needed.

## Manual commands (optional)

```powershell
docker compose up -d
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# other terminal
cd frontend
npm install
npm run dev
```
