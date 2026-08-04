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

- App: http://127.0.0.1:3000  
- API docs: http://127.0.0.1:8000/docs  

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

## Manual quick start (optional)

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
