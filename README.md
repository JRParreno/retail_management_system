# Motorcycle Shop RMS & POS

All-in-one retail management and POS for a motorcycle repair shop.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL, JWT + bcrypt
- **Frontend:** Next.js App Router, TypeScript, Tailwind CSS, Shadcn UI
- **DB (dev):** Docker Postgres (`docker-compose.yml`)
- **Deploy:** Windows or Ubuntu / Pop!_OS — same Compose Postgres, app on host

## Windows (local + production)

Full guide: [`docs/windows-setup.md`](docs/windows-setup.md) · Script index: [`scripts/README.md`](scripts/README.md)

**Prereqs:** Docker Desktop (running), Python 3.11+, Node 20+ LTS.

### Local development

```powershell
# Prefer .bat if PowerShell blocks scripts:
scripts\local_run.bat
# or:
.\scripts\local_run.ps1
# jump to start-all:
scripts\local_run.bat 5
```

| # | Action |
|---|--------|
| 1 | First-time setup (Docker + migrate + seed + npm install) |
| 2 | Start Postgres |
| 3 | Stop Postgres |
| 4 | Migrate + seed |
| 5 | Start ALL (Postgres + API + UI) |
| 6 | Backend only (`:8000`) |
| 7 | Frontend only (`:3000`) |
| 8 | Status check |
| A | Open Windows Firewall ports 3000/8000 (Administrator if needed) |

- App: https://127.0.0.1:3000 · API docs: http://127.0.0.1:8000/docs  
- LAN tablets: use the HTTPS LAN URL printed by option 5 (accept cert warning once)

### Production deploy (no demo data)

```powershell
.\scripts\run_prod.ps1
.\scripts\run_prod.ps1 --skip-build
.\scripts\run_prod.ps1 --stop-only
.\scripts\run_prod.ps1 --with-tunnel quick
```

### Backups

```powershell
.\scripts\run_db_backup.ps1 status
.\scripts\run_db_backup.ps1 backup
.\scripts\run_db_backup.ps1 install-cron    # Windows Task Scheduler @ 02:00
```

---

## Linux / macOS — Launcher menu

From the project root:

```bash
chmod +x scripts/local_run.sh   # once
./scripts/local_run.sh
```

Or:

```bash
python scripts/dev_menu.py
# jump straight to an option (e.g. start all):
python scripts/dev_menu.py 5
```

| # | Action |
|---|--------|
| 1 | First-time setup (Docker + migrate + seed + npm install) |
| 2 | Start Postgres |
| 3 | Stop Postgres |
| 4 | Migrate + seed |
| 5 | Start ALL (Postgres + API + UI) |
| 6 | Backend only (`:8000`) |
| 7 | Frontend only (`:3000`) |
| 8 | Status check |

- App (this PC): http://127.0.0.1:3000  
- API docs: http://127.0.0.1:8000/docs  
- **LAN / Wi‑Fi:** option 5 binds UI + API on `0.0.0.0`, serves the UI over **HTTPS** (needed for tablet camera barcode), and prints your PC’s LAN URL (e.g. `https://192.168.x.x:3000`). On first visit, accept the certificate warning. Allow firewall ports 3000 and 8000 if needed (`sudo ufw allow 3000,8000/tcp`).

### Demo logins

| User | Password | Role |
|------|----------|------|
| `admin` | `admin123` | ADMIN |
| `cashier` | `cashier123` | CASHIER |

Reset/create admin only:
```bash
cd backend && python -m app.scripts.seed_admin
# or from launcher menu option 9
```

## Production deploy (no demo data)

From the project root:

**Windows:** `.\scripts\run_prod.ps1` · **Linux:** `./scripts/run_prod.sh`

```bash
chmod +x scripts/run_prod.sh   # once (Linux)
./scripts/run_prod.sh
```

Or:

```bash
python scripts/prod_deploy.py
# restart only (reuse existing build):
python scripts/prod_deploy.py --skip-build
# stop servers:
python scripts/prod_deploy.py --stop-only
```

What it does:
1. Checks Docker, Node, npm, Python  
2. Starts Postgres  
3. Installs backend deps, sets `DEBUG=false`  
4. Runs migrations (includes `product_brands` catalog)  
5. Seeds **Main branch**, **`admin` / `admin123`**, **product brands**, and **motorcycle/scooter models** (no demo products, mechanics, or cashier)  
6. Builds the Next.js app  
7. Stops old processes on ports 3000/8000 and starts production servers  
8. Prints local + LAN URLs  

Re-deploy and reset the admin password to `admin123`:

```bash
python scripts/prod_deploy.py --reset-admin
```

After deploy, use **Inventory → Import Excel** for bulk product upload (physical or auto `RMS…` barcodes).

Login after deploy: `admin` / `admin123`

### Cloudflare Tunnel (public HTTPS)

No router port-forward needed. See `cloudflare/README.md`.

```bash
# Temporary public URL (testing)
./scripts/run_prod.sh --with-tunnel quick          # Linux
.\scripts\run_prod.ps1 --with-tunnel quick         # Windows

# Permanent hostname (after cloudflare/config.yml is set up)
./scripts/run_prod.sh --with-tunnel named

# Tunnel only (app already running)
./scripts/run_prod.sh --tunnel-only quick
```

### Full Ubuntu production edge (Nginx, no domain)

Manual guide: [`docs/production-https-ubuntu.md`](docs/production-https-ubuntu.md)

**One-shot setup** (Ubuntu — Nginx reverse proxy by LAN/public IP, no DNS):

```bash
chmod +x scripts/run_ubuntu_https.sh
sudo ./scripts/run_ubuntu_https.sh --yes
# HTTPS with self-signed cert (tablet camera; accept browser warning once):
sudo ./scripts/run_ubuntu_https.sh --self-signed --yes
```

Installs UFW, Nginx, and systemd units `rms-api` / `rms-web`. Open `http://<server-lan-ip>` (or `https://…` with `--self-signed`).

**Day-to-day ops menu** (start / stop / restart / deploy after changes / logs):

```bash
chmod +x scripts/run_prod_menu.sh
./scripts/run_prod_menu.sh
# or jump to an option, e.g. deploy:
./scripts/run_prod_menu.sh 5
```

### Database backups (recommended)

One local Postgres + nightly dumps (no second live DB). Dumps go to `/opt/rms/backups` when that path exists, otherwise `./backups/`.

```bash
# Linux
chmod +x scripts/run_db_backup.sh
./scripts/run_db_backup.sh status
./scripts/run_db_backup.sh backup
./scripts/run_db_backup.sh install-cron                    # nightly 02:00

# Windows
.\scripts\run_db_backup.ps1 status
.\scripts\run_db_backup.ps1 backup
.\scripts\run_db_backup.ps1 install-cron                   # Task Scheduler 02:00
```

Or from the production menu (Linux): option **13**. Keep 14 days by default; set `RMS_BACKUP_DIR` / `RMS_BACKUP_OFFSITE` if needed.

---

```bash
docker compose up -d
cd backend && python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head && python -m app.scripts.seed
uvicorn app.main:app --reload --port 8000

# other terminal
cd frontend && npm install && npm run dev
```

## Features in this build

- Multi-bay job board (IN_PROGRESS / awaiting payment)
- Service jobs with parts + labor + mechanic commissions
- Direct sale POS with barcode gun support
- Payments: **CASH** (tender/change) and **GCASH** (reference + camera proof photo)
- Inventory search/adjust, mechanics, shifts, reports (Export PDF), admin users
