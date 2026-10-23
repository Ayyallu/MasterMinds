# Phase 9 — Full-System Verification & Hardening: Findings Report

**Scope:** Audit of the integrated MasterMinds system (Phases 1–8) against the approved requirements. No major new features added. Fixes applied only where in-scope and safe.

**Verification performed**
- End-to-end journeys for **two synthetic institutions** through the public API: onboarding → academic setup → question bank → exam authoring/approval → student delivery → scoring → publication → reporting (`tests/test_e2e.py`).
- **Cross-tenant negative sweep**: direct reads, updates, search, nested resources, scoring, reports, and student attempt/result access — all denied across tenants (403/404).
- **Reliability**: concurrent/duplicate submit (idempotent), autosave idempotency, expiry auto-submit, attempt limits (existing + E2E tests).
- **Clean migration from scratch** on a throwaway DB (`mm_clean`): 8 revisions → 33 tables.
- **Backup/restore** verified: `pg_dump` of `mm_clean` restored into `mm_restore` (33 tables, head `0008_scoring`), no errors. Throwaway DBs dropped afterward.
- **Index review**: all hot columns (`institution_id`, `exam_id`, `attempt_id`, `*token_hash`) are indexed. No speculative indexes added.
- Full test suite: **79 passed**.

---

## Findings

### Fixed in this phase (safe, in-scope)

| # | Severity | Area | Finding | Fix |
|---|----------|------|---------|-----|
| 1 | Medium | Resource use | Question-bank search (`search`, `search_global`) returned unbounded result sets — a large bank could be dumped in one call. | Added a `MAX_SEARCH_ROWS = 2000` cap. |
| 2 | Low | Auth hygiene | `verify_password` caught `(VerifyMismatchError, Exception)` (redundant/over-broad). | Split into explicit `VerifyMismatchError` and a commented catch-all for malformed hashes. |
| 3 | Low | Accessibility | Admin form inputs relied on `placeholder` only (no accessible name). | Added `aria-label` to email/password/class-group inputs. |

### Accepted / deferred (documented, not fixed here)

| # | Severity | Area | Finding | Rationale |
|---|----------|------|---------|-----------|
| A | Medium | Scale | Login/AI/generation rate limiting is **in-process**; multi-instance deployments need a shared store (Redis). | Documented in `rate_limit.py`; belongs to Phase 10 infrastructure. |
| B | Low | Reliability | Autosave has no per-request throttle. | Autosave is idempotent (last-write-wins, versioned); abusive-request throttling is a deployment/WAF concern (Phase 10). |
| C | Low | Data model | `AttemptStatus.expired` is defined but never set — expiry auto-submits with `status="submitted"` + `auto_submitted=True`. | Not a bug; scoring includes both statuses. Left as-is to avoid rippling changes; distinction is carried by `auto_submitted`. |
| D | Low | Uploads | Document `content_type` is taken from the client for the allowlist check. | Files are stored privately, never executed, and download is authorized per institution; content-sniffing is a possible Phase 10 enhancement. |
| E | Low | Reporting | Per-exam report returns all participant rows (no page cursor). | Bounded naturally by exam size; cursor pagination can be added if cohorts grow large. |
| F | Info | Accessibility | No full WCAG audit/automated a11y tooling run; the admin UI is intentionally minimal. | A dedicated a11y pass belongs with a real UI build-out. |

### Confirmed correct (no action)
- **Tenant isolation**: enforced server-side on every institution-scoped route; manipulated IDs denied (tested across layers, two institutions).
- **Answer-key secrecy**: student-facing views and results never expose correct options, numerical answers, or explanations.
- **Result release**: hidden until Institution Admin publishes; re-scoring blocked after publish; corrections audited + reason-required.
- **Token lifecycle**: refresh rotation with family-based replay detection; logout/all-session revocation; disabled accounts rejected.
- **Secrets**: no secrets committed; production rejects the dev JWT secret; `.env` git-ignored.
- **CORS**: explicit origin only; wildcard-with-credentials rejected at config and startup.

---

## Load-test plan (repeatable, local limits only)

Run against a local instance; **report measured limits honestly** — do not extrapolate to production.

1. **Exam start** — N students starting one exam concurrently; measure p50/p95 latency and snapshot-build time.
2. **Autosave** — sustained answer PUTs across active attempts; confirm no lost updates and bounded latency.
3. **Submit** — concurrent submits (including duplicates); confirm idempotency and single score row per attempt.
4. **Reporting** — admin report + CSV export under load; confirm result cap and query time.

Suggested local tool: `locust` or `k6`, capped at the dev machine's resources. Record the hardware, concurrency reached, and the point where latency degrades — these are **local** numbers, not production guarantees.

---

## Recommendation
The integrated system passes end-to-end verification with tenant isolation, answer secrecy, and result-release controls enforced and tested. The three fixes above are applied. Items A–F are documented and safe to defer; A and B are naturally resolved by the Phase 10 infrastructure work. No production deployment performed.
