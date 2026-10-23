# MasterMinds

Multi-tenant Online Exam SaaS for schools and colleges.

**Phase 1 (foundation) is implemented:** a FastAPI backend with an async
PostgreSQL health check and an empty baseline Alembic migration, plus a Next.js +
TypeScript frontend that displays backend health. No authentication, exams, AI, or
billing yet — those arrive in later phases.

## Quick start

1. Start Postgres: `docker-compose up -d db`
2. Backend: see [CLAUDE.md](CLAUDE.md) → Running → Backend
3. Frontend: see [CLAUDE.md](CLAUDE.md) → Running → Frontend

## Stack
Next.js + TypeScript · FastAPI · SQLAlchemy 2.x async · Alembic · PostgreSQL

See [CLAUDE.md](CLAUDE.md) for conventions, guardrails, and full run instructions.
