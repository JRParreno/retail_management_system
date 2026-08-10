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

From the repo root in PowerShell (see also [`scripts/README.md`](../scripts/README.md)):

```powershell
# Prefer .bat if PowerShell blocks .ps1 (execution policy):
scripts\local_run.bat
# or after: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\scripts\local_run.ps1
# jump straight to start-all:
scripts\local_run.bat 5
```

CMD:

```bat
scripts\local_run.bat
scripts\local_run.bat 5
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
.\scripts\run_prod.ps1
# restart without rebuild:
.\scripts\run_prod.ps1 --skip-build
# stop:
.\scripts\run_prod.ps1 --stop-only
```

Public HTTPS (no router port-forward):

```powershell
.\scripts\run_prod.ps1 --with-tunnel quick
.\scripts\run_prod.ps1 --with-tunnel named
.\scripts\run_prod.ps1 --tunnel-only quick
```

See `cloudflare/README.md`. Login after deploy: `admin` / `admin123` — change it immediately.

> Ubuntu Nginx/systemd edge (`scripts/run_ubuntu_https.sh`, `scripts/run_prod_menu.sh`) is Linux-only. On Windows use `scripts/run_prod.ps1` + optional Cloudflare Tunnel.

## Database backups

```powershell
.\scripts\run_db_backup.ps1 status
.\scripts\run_db_backup.ps1 backup
.\scripts\run_db_backup.ps1 install-cron          # Task Scheduler nightly 02:00
.\scripts\run_db_backup.ps1 list
.\scripts\run_db_backup.ps1 restore latest        # destructive; confirm with YES
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
