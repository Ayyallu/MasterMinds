# MasterMinds — Online Exam SaaS

Multi-tenant online examination platform for schools and colleges.

## Status
- **Phase 1 (foundation):** implemented — backend + frontend skeleton, health check, empty baseline migration.
- **Phase 1.1 (hardening):** implemented — CORS guard, bounded health probe, resilient frontend polling.
- **Phase 2 (auth, sessions, tenant security):** implemented — identity, roles, institution memberships, argon2 password hashing, JWT access + rotating refresh tokens with replay detection, login rate limiting, password reset (email stubbed) and change, TOTP MFA for Super Admin, server-side tenant isolation, audit events. Migration `0002_auth`.
- **Phase 3 (institution & academic admin):** implemented — Super Admin reviews/approves/rejects institution registrations and provisions Institution Admins; academic structure (academic years, terms, grade levels, departments, courses, class groups); invitations + student self-registration (pending until admin approval); teacher assignments; enrollments with preserved history (transfer closes the old row); tenant-scoped retryable CSV roster import with preview + error report; audit events; a minimal admin UI at `/admin`. Migration `0003_academic`.
- **Phase 4 (syllabus & question bank):** implemented — syllabus topics + learning objectives; institution-private questions with **immutable versions** (editing creates a new version); 4 launch types (single MCQ, multi-select MCQ, true/false, numerical) with type-specific validation; per-version review status (draft → in_review → approved/rejected), only approved versions selectable later; **answer keys never exposed to students** (staff-only endpoints + a student-safe serializer); search/filter by curriculum/grade/term/topic/objective/type/difficulty; private document uploads stored on the filesystem (`backend/var/uploads`, git-ignored) with validated type/size and authorized download. Migration `0004_questionbank`.
- Later phases (AI generation, exams, delivery, scoring, hardening, deployment) are **not** implemented. Build them one phase at a time.

## Question bank notes (Phase 4)
- Questions are logical rows; content lives in immutable `question_versions` with `question_options` (answer key in `is_correct` / `numerical_answer`). Never serialize keys to students — use `question_service.serialize(..., include_keys=False)`.
- Staff = Institution Admin or Teacher (`require_institution_staff`); review/approval = Institution Admin. Students have no access to question-bank endpoints.
- `is_global` / nullable `institution_id` reserve space for the Phase 5 global shared library; global creation is **not** enabled yet.

## Auth model (Phase 2)
- **Login identifier:** email (staff) or institution-scoped register number (students, with institution code).
- **Tokens:** bearer JSON. Access = JWT (15 min); refresh = opaque, hashed, rotating (7 days) with family-based replay detection.
- **Roles:** super_admin, institution_admin, teacher, student, central_academic_reviewer (seeded by migration).
- **Tenant scope** is enforced server-side in `app/dependencies.py` (`enforce_tenant_scope`); never trust a client-supplied institution id. Super Admin cross-tenant access is explicit and audited.
- Endpoints under `/auth/*`. See `app/routers/auth.py`.

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
