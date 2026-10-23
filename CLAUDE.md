# MasterMinds — Online Exam SaaS

Multi-tenant online examination platform for schools and colleges.

## Status
- **Phase 1 (foundation):** implemented — backend + frontend skeleton with a health check and an empty baseline migration.
- Later phases (auth, academic admin, question bank, AI generation, exams, delivery, scoring, hardening, deployment) are **not** implemented. Build them one phase at a time.

## Stack
- **Backend:** FastAPI, SQLAlchemy 2.x **async** (asyncpg), Alembic, PostgreSQL.
- **Frontend:** Next.js (App Router) + TypeScript.
- **Local dev:** Windows 11 (PowerShell). Postgres via `docker-compose up -d db`.

## Out of scope (all phases)
No in-app billing, payments, subscriptions, or payment enforcement.

## Layout
```
backend/     FastAPI app, async DB, Alembic migrations, tests
frontend/    Next.js + TypeScript app
docker-compose.yml   local Postgres
```

## Conventions / guardrails
- Use SQLAlchemy 2.x async consistently. Never create/alter schema at app startup — use Alembic.
- Store timestamps in UTC; display in institution-configured time zones (later phases).
- Keep secrets in environment config only. Never commit `.env`; `.env.example` holds placeholders.
- CORS: explicit frontend origin only; never wildcard origins with `allow_credentials=True`.
- Add tests for new business rules; do not claim tests passed unless actually run.
- Use synthetic demo data only.

## Running

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then edit .env
alembic upgrade head
uvicorn app.main:app --reload
```
Health check: `GET http://localhost:8000/health`

### Backend tests
```powershell
cd backend
pytest
```

### Frontend
```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```
App: `http://localhost:3000`
