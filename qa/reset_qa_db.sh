#!/bin/sh
# Recreate the isolated QA database from scratch: migrations + QA Super Admin.
# Usage (repo root, Git Bash): sh qa/reset_qa_db.sh
# Then start a QA backend:   cd backend && DATABASE_URL=postgresql+asyncpg://masterminds:masterminds@localhost:5433/masterminds_qa AI_PROVIDER=mock ./.venv/Scripts/python -m uvicorn app.main:app --port 8001
set -e
DB_CONTAINER=${DB_CONTAINER:-mm-db}
URL=${QA_DATABASE_URL:-postgresql+asyncpg://masterminds:masterminds@localhost:5433/masterminds_qa}
docker exec "$DB_CONTAINER" psql -U masterminds -q -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='masterminds_qa' AND pid<>pg_backend_pid();" >/dev/null
docker exec "$DB_CONTAINER" psql -U masterminds -q -c "DROP DATABASE IF EXISTS masterminds_qa;" -c "CREATE DATABASE masterminds_qa;"
cd "$(dirname "$0")/../backend"
DATABASE_URL="$URL" ./.venv/Scripts/python -m alembic upgrade head >/dev/null 2>&1
DATABASE_URL="$URL" ./.venv/Scripts/python -c "
import asyncio
from scripts.create_super_admin import create_super_admin
asyncio.run(create_super_admin('qa.root@qa.example.com','QA Root','QaRootPass#2026'))"
