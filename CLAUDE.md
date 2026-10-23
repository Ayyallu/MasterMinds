# MasterMinds — Online Exam SaaS

Multi-tenant online examination platform for schools and colleges.

## Status
- **Phase 1 (foundation):** implemented — backend + frontend skeleton, health check, empty baseline migration.
- **Phase 1.1 (hardening):** implemented — CORS guard, bounded health probe, resilient frontend polling.
- **Phase 2 (auth, sessions, tenant security):** implemented — identity, roles, institution memberships, argon2 password hashing, JWT access + rotating refresh tokens with replay detection, login rate limiting, password reset (email stubbed) and change, TOTP MFA for Super Admin, server-side tenant isolation, audit events. Migration `0002_auth`.
- **Phase 3 (institution & academic admin):** implemented — Super Admin reviews/approves/rejects institution registrations and provisions Institution Admins; academic structure (academic years, terms, grade levels, departments, courses, class groups); invitations + student self-registration (pending until admin approval); teacher assignments; enrollments with preserved history (transfer closes the old row); tenant-scoped retryable CSV roster import with preview + error report; audit events; a minimal admin UI at `/admin`. Migration `0003_academic`.
- **Phase 4 (syllabus & question bank):** implemented — syllabus topics + learning objectives; institution-private questions with **immutable versions** (editing creates a new version); 4 launch types (single MCQ, multi-select MCQ, true/false, numerical) with type-specific validation; per-version review status (draft → in_review → approved/rejected), only approved versions selectable later; **answer keys never exposed to students** (staff-only endpoints + a student-safe serializer); search/filter by curriculum/grade/term/topic/objective/type/difficulty; private document uploads stored on the filesystem (`backend/var/uploads`, git-ignored) with validated type/size and authorized download. Migration `0004_questionbank`.
- **Phase 5 (AI generation & global library):** implemented — provider-independent interface (`app/ai/`) with a deterministic **mock** provider (default/tests) and an **NVIDIA NIM** adapter (inert until `NVIDIA_API_KEY` set); pre-exam generation only (never during a live exam); every candidate validated + deduped before storing as `in_review`; **dual review gates** (Institution Admin for private AI questions; Central Academic Reviewer for the global shared library); cross-institution reuse only via approved global questions (private never shared); cost controls (per-user rate limit, pool-size cap, bounded retries, idempotency key); usage/cost metadata recorded, secrets/full prompts never logged; no student PII sent to the provider. Migration `0005_ai`.
- **Phase 6 (exam authoring, blueprint & approval):** implemented — explicit exam lifecycle state machine with server-enforced transitions (draft → awaiting_approval → approved → scheduled → … → archived, + cancelled); teachers draft/edit/submit only within **assigned** class groups and **cannot approve/schedule/publish**; Institution Admin approval **freezes** config, selects an approved question pool (private + approved global, institution-first) with a **pool-sufficiency** check that blocks on shortfall; only approved question versions are pinned; material change after approval requires **reopen → re-approval**; timezone-aware scheduling stored in UTC; staff preview with **no answer keys**; audit events. Migration `0006_exams`.
- **Phase 7 (student delivery & reliable attempts):** implemented — immutable per-attempt snapshot (pinned question version ids + per-student question/option shuffle, marks, marking rules); server-authoritative timing with auto-submit at expiry; disconnect→resume on the same snapshot; idempotent autosave (per-question row + monotonic `answer_version`); idempotent submit (no duplicate submissions/score changes); attempt-limit enforcement; eligibility by active membership + enrollment; answer keys never returned to students. Migration `0007_attempts`.
- **Phase 8 (scoring, result release & reporting):** implemented — deterministic scoring from the frozen attempt snapshot (single/true-false exact; multi-select all-or-nothing; numerical with absolute tolerance; negative marking off unless the snapshot enabled it; final score floored at 0); reproducible re-scoring with `score_version` + append-only `score_history`; results hidden until Institution Admin publishes (respecting `manual`/`after_close` release rule); re-score blocked after publish — corrections go through an audited, reason-required path; role/tenant-scoped reports (admin full, teacher only assigned classes, student only own released result, Super Admin audited cross-tenant) with CSV export; explicit **semester census-date** enrollment rule. No billing. Migration `0008_scoring`.
- Later phases (hardening, deployment) are **not** implemented. Build them one phase at a time.

## Scoring notes (Phase 8)
- `scoring_service.score_attempt` recomputes from `snapshot` + `attempt_answers` + immutable `question_versions`; `attempt_scores` holds the current score, `score_history` every run/correction. Census rule: enrollment counts if it began on/before the census date and had not ended before it.
- Student result (`GET /attempts/{id}/result`) returns per-question outcome only (marks/awarded/correct) — never the correct answer or explanation — and only once `results_published`.

## Attempt engine notes (Phase 7)
- `exam_attempts.snapshot` holds order only (no answer keys); `attempt_answers` keyed uniquely per (attempt, question_version). Timing is wall-clock, server-authoritative (`deadline_at` = start+duration, capped at exam `end_at`); the timer continues through disconnection.
- `attempt_service._finalize_if_expired` auto-submits any expired in-progress attempt on the next request; answers already autosaved are kept. Scoring/grading is Phase 8 — attempts capture answers, not grades.

## Exam notes (Phase 6)
- `exams` holds identity + cohort + blueprint + lifecycle + `frozen_snapshot`; `exam_questions` pins selected approved `question_versions`.
- Transitions enforced in `exam_service.ALLOWED_TRANSITIONS`; approval does selection + sufficiency + freeze. Per-student randomization/attempts are Phase 7.
- Teacher authoring scope checked against `teacher_assignments`; approve/reject/schedule/reopen require Institution Admin.

## AI generation notes (Phase 5)
- `AI_PROVIDER=mock` by default. Real NIM needs `AI_PROVIDER=nvidia` + `NVIDIA_API_KEY`; if selected but unconfigured, generate endpoints return 503.
- Generation is synchronous+bounded (no Celery/Redis yet — documented follow-up). AI candidates land as `in_review` and require human approval; only approved versions are exam-selectable (Phase 6).
- Private generation: `POST /institutions/{id}/ai/generate` (staff). Global: `POST /global/ai/generate` (Central Reviewer). Global library reuse: `POST /global/library/search` (any staff).

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
