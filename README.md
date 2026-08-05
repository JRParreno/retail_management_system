# Motorcycle Shop RMS & POS

All-in-one retail management and POS for a motorcycle repair shop.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL, JWT + bcrypt
- **Frontend:** Next.js App Router, TypeScript, Tailwind CSS, Shadcn UI
- **DB (dev now):** Docker Postgres on Windows Docker Desktop
- **Later deploy:** Ubuntu ProDesk — same `docker-compose.yml`, app on host

## Launcher menu (Windows + Ubuntu)

From the project root:

**Windows**
```bat
run.cmd
```
or
```powershell
.\run.ps1
```

**Ubuntu / Linux**
```bash
chmod +x run.sh   # once
./run.sh
```

**Either OS**
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
- **LAN / Wi‑Fi:** option 5 binds UI + API on `0.0.0.0`, serves the UI over **HTTPS** (needed for tablet camera barcode), and prints your PC’s LAN URL (e.g. `https://192.168.x.x:3000`). On first visit, accept the certificate warning. Allow Windows Firewall on ports 3000 and 8000 if needed.

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

**Windows**
```powershell
.\run_prod.ps1
```
or
```bat
run_prod.cmd
```

**Ubuntu / Linux**
```bash
chmod +x run_prod.sh   # once
./run_prod.sh
```

**Either OS**
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
4. Runs migrations  
5. Seeds **Main branch + `admin` / `admin123` only** (no demo products, mechanics, or cashier)  
6. Builds the Next.js app  
7. Stops old processes on ports 3000/8000 and starts production servers  
8. Prints local + LAN URLs  

Login after deploy: `admin` / `admin123`

### Cloudflare Tunnel (public HTTPS)

No router port-forward needed. See `cloudflare/README.md`.

```powershell
# Temporary public URL (testing)
.\run_prod.ps1 --with-tunnel quick

# Permanent hostname (after cloudflare/config.yml is set up)
.\run_prod.ps1 --with-tunnel named

# Tunnel only (app already running)
.\run_prod.ps1 --tunnel-only quick
```

---

```bash
docker compose up -d
cd backend && python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Ubuntu:  source .venv/bin/activate
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
