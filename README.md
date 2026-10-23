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
