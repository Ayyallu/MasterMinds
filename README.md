# MasterMinds

Multi-tenant Online Exam SaaS for schools and colleges.

The repository contains the phased backend capabilities documented in
[CLAUDE.md](CLAUDE.md), including authentication, tenant-scoped academic
administration, question banks, exam delivery, scoring, and result release.
The Next.js frontend includes the admin portal and a student portal for sign-in,
pending registration, exam attempts, autosaving answers, and released results.

- Student sign-in: `/student`
- Student registration: `/student/register` (requires institution-admin approval)
- Student exam attempt: `/student/attempts/{attemptId}`
- Released result: `/student/results/{attemptId}`
- Admin portal: `/admin`

The student UI uses the existing FastAPI endpoints and does not introduce a new
database migration. Review the current implementation and run CI before merging
student-portal changes.

## Quick start

1. Start Postgres: `docker-compose up -d db`
2. Backend: see [CLAUDE.md](CLAUDE.md) → Running → Backend
3. Frontend: see [CLAUDE.md](CLAUDE.md) → Running → Frontend

## Stack
Next.js + TypeScript · FastAPI · SQLAlchemy 2.x async · Alembic · PostgreSQL

See [CLAUDE.md](CLAUDE.md) for conventions, guardrails, and full run instructions.


## Local demo bootstrap

After applying the database migrations, create the first platform administrator once from `backend/`:

```powershell
python -m scripts.create_super_admin
```

The command prompts for an email, name and a 12-character-minimum password. It does not use a hard-coded credential and will not elevate an existing non-Super-Admin account.

To create a synthetic demo institution, one Institution Admin, one Faculty account, one Student account, an assigned class group and five approved sample MCQs, set three local-only passwords (each at least 12 characters) and run:

```powershell
$env:DEMO_ADMIN_PASSWORD = "use-a-unique-local-password"
$env:DEMO_TEACHER_PASSWORD = "use-another-unique-password"
$env:DEMO_STUDENT_PASSWORD = "use-a-third-unique-password"
python -m scripts.seed_demo_data
```

The seed command refuses to run when `ENVIRONMENT=production`. It is idempotent for the demo institution and existing accounts; existing account passwords are not overwritten. Synthetic credentials:

| Role | Email | Student register number |
|---|---|---|
| Institution Admin | `admin@demo.masterminds.local` | — |
| Faculty | `teacher@demo.masterminds.local` | — |
| Student | `student@demo.masterminds.local` | `MM-DEMO-001` |

The demo Faculty account is assigned to `Grade 10 - Section A`; the sample questions are approved and can be used to create a draft exam. Use the local passwords supplied in the three environment variables above.

For AI question generation, keep `AI_PROVIDER=mock` for a free deterministic local demo. No NVIDIA API key is needed unless you explicitly switch to `AI_PROVIDER=nvidia`.
