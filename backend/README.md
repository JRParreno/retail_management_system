# Motorcycle Shop RMS — Backend

## Setup

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or cp on Unix
```

Ensure PostgreSQL is running and the `rms` database exists.

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Auth

- `POST /api/v1/auth/login` — OAuth2 password form → JWT
- `GET /api/v1/auth/me` — current user
- `GET /api/v1/auth/admin-check` — ADMIN-only smoke check
