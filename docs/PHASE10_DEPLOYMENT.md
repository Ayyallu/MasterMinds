# Phase 10 — Production Deployment Preparation

**Status: preparation only.** Nothing in this phase deploys to a paid or production
environment, creates billable resources, changes DNS, or publishes images. Do none
of that until the cloud **provider, region, budget, and plan are explicitly approved**.
Cost estimates are deliberately omitted until provider + region are chosen.

The application stays runnable on local Windows throughout (see `CLAUDE.md`).
There is **no billing/payment functionality** in the product.

---

## 1. AWS vs Azure — comparison and recommendation

Evaluated on portability, expected scale (schools/colleges; bursty exam windows),
operational effort, privacy, and cost control. **The provider is not assumed.**

| Need | AWS | Azure |
|------|-----|-------|
| Managed PostgreSQL | RDS / Aurora PostgreSQL | Azure Database for PostgreSQL Flexible Server |
| Container app hosting | ECS Fargate (or App Runner) | Azure Container Apps |
| Private object storage | S3 (private buckets) | Blob Storage (private containers) |
| Background worker/queue | SQS + Fargate worker | Azure Queue/Service Bus + Container App job |
| Secret manager | Secrets Manager / SSM | Key Vault |
| TLS / custom domain | ACM + ALB/CloudFront | App Gateway / Front Door + managed certs |
| Logs/metrics/alerts/trace | CloudWatch + X-Ray | Azure Monitor + App Insights |
| Backups / PITR | RDS automated + snapshots | Flexible Server automated + PITR |
| CI/CD | GitHub Actions → ECR/ECS | GitHub Actions → ACR/Container Apps |

**Both are a good fit and the architecture below is provider-portable** (containers +
managed Postgres + object storage + secret manager). The choice should follow the
organization's existing footprint and data-residency requirements:

- **Pick Azure** if the institution is Microsoft-centric (Entra ID, existing Azure
  tenancy, Canadian/EU residency via Azure regions already in use). Container Apps +
  Flexible Server is the lowest operational effort here.
- **Pick AWS** if the org already runs on AWS or wants the broadest service maturity.
  ECS Fargate + RDS is equally capable.

**Recommendation:** a **single managed-service, container-based architecture** (see §2)
on whichever provider matches existing tenancy and data-residency rules. Do **not**
provision anything until the provider, region, and budget are approved.

---

## 2. Target architecture (provider-neutral)

```
            ┌────────────┐      ┌─────────────────┐
  Browser ─▶│  CDN/TLS    │─────▶│ Frontend (Next) │  (standalone container)
            │ edge + cert │      └─────────────────┘
            └─────┬──────┘                 │ calls API
                  │                         ▼
                  │               ┌─────────────────┐
                  └──────────────▶│ Backend (FastAPI)│  (container, 2+ replicas)
                                  └───────┬─────────┘
            ┌─────────────┐   ┌───────────┴───────┐   ┌──────────────┐
            │ Secret mgr   │   │ Managed PostgreSQL│   │ Object store │
            │ (keys/creds) │   │  (private, PITR)  │   │ (uploads, private)
            └─────────────┘   └───────────────────┘   └──────────────┘
                  ▲                     ▲
            ┌─────┴───────┐     ┌───────┴────────┐
            │ Logs/metrics│     │ Optional worker│ (AI generation / imports)
            │ alerts/trace│     │   + queue      │
            └─────────────┘     └────────────────┘
```

- **Frontend**: the Next.js standalone image (`frontend/Dockerfile`).
- **Backend**: the FastAPI image (`backend/Dockerfile`), 2+ replicas behind the LB.
- **Uploads**: move from local `backend/var/uploads` to the object store in production
  (the document service's storage layer is the single integration point to swap).
- **Worker/queue**: only if AI generation / large roster imports need to move off the
  request path (today they are synchronous+bounded — Phase 5 follow-up).

---

## 3. Containerization

- `backend/Dockerfile` and `frontend/Dockerfile` use **pinned** base images
  (`python:3.12.10-slim`, `node:22.14.0-alpine`) and **non-root** runtime users.
- Rebuild on a schedule to pick up base-image security patches (don't float tags).
- `.dockerignore` keeps secrets, tests, `node_modules`, and local artefacts out of images.

## 4. Environment & secret separation

- Frontend and backend configuration are separate. **No secrets in images, source,
  browser bundles, or logs.**
- All secrets (DB credentials, `JWT_SECRET`, `NVIDIA_API_KEY`) come from the provider's
  secret manager injected as env vars at runtime — never baked into an image or committed.
- Each environment (dev/staging/prod) has its **own** secret set. Production startup
  **rejects the dev `JWT_SECRET` default** (`Settings.validate_production_secrets`).
- Generate production `JWT_SECRET`:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 5. Health, readiness, graceful shutdown, pool sizing

- Liveness/readiness probe: `GET /health` (bounded `SELECT 1`, returns 503 when the DB
  is unavailable without leaking internals).
- **Graceful shutdown**: the FastAPI lifespan disposes the SQLAlchemy engine on shutdown
  so the pool drains cleanly during rolling deploys.
- **Pool sizing**: `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT_SECONDS` /
  `DB_POOL_RECYCLE_SECONDS` are configurable. Size so that
  `(replicas × workers × (pool_size + max_overflow))` stays within the managed
  Postgres `max_connections`. Start conservative (pool_size 5, overflow 10) and tune
  from real connection metrics; consider a provider pooler (RDS Proxy / PgBouncer).

## 6. Database migrations as a release step

- Migrations are **never** run at app startup. The release pipeline runs
  `alembic upgrade head` as an explicit, gated step **before** rolling out new app
  images, using a migration identity with DDL rights (separate from the runtime role).
- Roll forward with a new migration rather than editing a released one. Each migration
  so far is additive and has been verified to apply from a clean database.

## 7. Security hardening

- **Least-privilege identities**: distinct roles for app runtime (DML only), migrations
  (DDL), and CI. Scope object-store access to the app's prefix only.
- **Network**: Postgres and object store are private (no public ingress); only the LB is
  public. Security groups / NSGs restrict traffic to required ports.
- **TLS** everywhere (edge + in transit to DB). HTTPS in production — set
  cookie/`SameSite` behavior accordingly (local HTTP vs prod HTTPS documented in Phase 2).
- **Secret rotation**: rotate `JWT_SECRET`, DB creds, and `NVIDIA_API_KEY` on a schedule
  via the secret manager; app picks up new values on restart.
- **Admin MFA**: Super Admin TOTP MFA is implemented (Phase 2) — require it in production.
- **Log redaction**: secrets and full AI prompts are never logged (enforced in code).

## 8. Data region, retention, privacy

- Choose a **region** that satisfies data-residency obligations before any data lands.
- Define retention/deletion for PII/PHI-adjacent data (users, attempts, audit, uploads)
  and a documented deletion path. Keep enrollment history (census rule, Phase 8).
- Access logging and audit events already capture privileged/cross-tenant actions.
- Document incident response (who, how, notification timelines) before go-live.

## 9. Availability, RPO/RTO, backups

- **Backups**: enable automated managed-Postgres backups + point-in-time recovery; keep
  object-store versioning for uploads.
- **Targets (to confirm with the business)**: suggested starting point —
  **RPO ≤ 15 min** (PITR), **RTO ≤ 1 hour**. Availability target e.g. 99.5% for launch.
- **Restore testing**: rehearse restore into an isolated environment on a schedule — the
  `pg_dump`/restore drill in Phase 9 proves the mechanism locally.
- **Monitoring/alert ownership**: name an owner for each alert (DB CPU/connections/
  storage, API 5xx/latency, failed logins spike, failed migrations, backup failures).

## 10. CI/CD (dev / staging / production)

- `.github/workflows/ci.yml` runs on every push/PR: backend migrations-from-clean +
  tests (against a Postgres service), frontend typecheck/lint/build.
- **Deployment is not automated in this repo.** Promotion to staging/prod is a separate,
  **manually-approved** workflow that builds and pushes images, runs
  `alembic upgrade head` as a release step, then rolls out — provider chosen later.

---

## 11. Staging deployment checklist

1. Provider, region, budget approved in writing.
2. Secret manager populated (DB creds, strong `JWT_SECRET`, `NVIDIA_API_KEY` or mock).
3. Managed Postgres provisioned (private), app + migration DB roles created.
4. Object store (private) provisioned; backend configured to use it for uploads.
5. Images built from pinned Dockerfiles, scanned, pushed to the registry.
6. `alembic upgrade head` run as a release step; verify `alembic current` = head.
7. App rolled out; `/health` green; smoke-test login + one exam flow with synthetic data.
8. Backups + PITR enabled and a test restore performed.
9. Monitoring/alerts wired with named owners.
10. CORS `FRONTEND_ORIGIN` set to the real frontend origin; TLS verified.

## 12. Rollback procedure

- **App**: redeploy the previous known-good image tag (keep the last N tags).
- **Database**: prefer roll-forward. If a migration must be undone, apply the tested
  `alembic downgrade <prev>` in a controlled window, or restore from PITR to just before
  the release — never hand-edit a released migration.
- Rolling back app images is safe as long as the schema is backward-compatible with the
  prior image (keep migrations additive; stage destructive changes across releases).

---

## Acceptance (Phase 10)
Architecture and deployment runbooks reviewed ✓ · secrets and environments separated ✓ ·
backup/restore and rollback documented ✓ · containerization pinned + non-root ✓ ·
migrations defined as a release step ✓ · **no resources created; no provider assumed;
no cost estimates until provider+region approved** ✓ · local Windows development still
supported ✓ · no billing features ✓.
