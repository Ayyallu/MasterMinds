# MasterMinds — End-to-End QA Report

> **Update (same day): all 10 defects fixed and re-verified.** QA API suite **213/213** (one new check, J08: concurrent "Start exam"), browser suite **52/52**, backend tests **120/120** (16 new regression tests in `backend/tests/test_qa_regressions.py`), browser e2e 2/2, typecheck and lint clean. See §7.

**Date:** 2026-11-12 · **Branch:** `feature/arun-v1` (uncommitted working tree) · **Tester:** senior QA pass (automated + exploratory)

## 1. Verdict

**Not release-ready.** Core journeys work end to end (onboarding → structure → people → question bank → exam → attempt → scoring → results), and tenant isolation of data reads is solid. But there are **1 critical and 3 high-severity defects**: data loss on delete, a "disable institution" control that does nothing, and two ways a student can be locked out of exams with a server error.

| Suite | Checks | Pass | Fail |
|---|---:|---:|---:|
| API scenario suite (`qa/api_e2e.py`, isolated QA DB) | 212 | 198 | 14 |
| Tolerance edge (unit-level, J07) | 1 | 0 | 1 |
| Browser suite (`qa/ui_e2e.py`, Edge, all roles + mobile) | 52 | 52 | 0 |
| Existing backend tests (`pytest`) | 104 | 104 | 0 |
| Existing browser e2e (`frontend/e2e`) | 2 | 2 | 0 |
| Frontend typecheck + lint | — | ✔ | — |
| Migrations from empty DB: up 9 / down 9 / up 9 | — | ✔ | — |

The 14 API failures map to 10 distinct defects (some defects fail several checks).

## 2. Environment

- **API suite:** a dedicated database `masterminds_qa`, created from scratch by Alembic and served by a second backend on port 8001. It used `AI_PROVIDER=mock`, so no NVIDIA cost. Demo data was untouched.
- **Browser suite:** the dev stack (`:3000` → `:8000`) with the demo accounts, Microsoft Edge via Playwright, desktop 1440×900 and mobile 390×844.
- **Real AI:** NVIDIA NIM was verified separately (`python -m scripts.check_ai`), not in these suites.

## 3. Defects

| ID | Sev | Area | Defect | Failing checks |
|---|---|---|---|---|
| DEF-01 | **Critical** | Academic structure | Deleting a record silently destroys or detaches related data instead of refusing. Deleting a **class group** deletes its **enrollments** and **teacher assignments** (FK `ON DELETE CASCADE`) and un-links its **exams** (`SET NULL`). Deleting an **academic year** deletes its terms. Deleting a term, course or grade nulls those links on enrollments, exams, questions and topics. The delete endpoints added in the CRUD feature assumed the DB would refuse. *(Regression from that feature.)* | D19, D19b |
| DEF-02 | **High** | Platform / access control | **Disabling an institution has no effect.** Its admins can still sign in, existing sessions keep working, students still see and can start exams, and new self-registrations are accepted. The UI claims the institution is "suspended". | I06, I07, I08, I09 |
| DEF-03 | **High** | Enrollment → exams | The **same student can be enrolled twice** in the same class. That student then gets **HTTP 500** on `GET /student/exams` and on exam start (`MultipleResultsFound`), so they are locked out of every exam. A double-click on "Enroll" is enough. | D18, G26 |
| DEF-04 | **High** | Exam delivery | **Concurrent autosaves** of the same question (fast clicking, network retries) return **HTTP 500** and produce **duplicate `answer_version`s**. Observed: `[1, 500, 500, 500, 500, 2, 2, 3]`. This is a race on the per-question answer row. | J03 |
| DEF-05 | Medium | Tenant integrity | **Creating** a class group accepts a term, grade or course **from another institution** (cross-tenant link). A non-existent id gives **HTTP 500** instead of 404. (Edit already validates; create does not.) | J01, C10 |
| DEF-06 | Medium | Scoring | Result **correction accepts marks above the maximum** (99 on an 8-mark exam). Negative values are correctly refused. | H18 |
| DEF-07 | Medium | Scoring | **Numerical tolerance boundary is wrong** because of floating-point maths: `3.13` against `3.14 ± 0.01` is marked **incorrect** (while `3.15` is correct). Students exactly on the boundary lose marks. | J07 |
| DEF-08 | Medium | Enrollment | A **teacher (or any non-student) can be enrolled as a student**. | D17 |
| DEF-09 | Low | Exam delivery | Numerical autosave accepts **non-numeric text** (`"abc"`). It is silently scored as wrong, with no feedback to the student. | G17 |
| DEF-10 | Low | UI (mobile) | On narrow screens the tab switcher wraps onto three lines inside a large rounded "pill" that looks broken (Academic structure, 390 px). | visual |

### Reproduction notes
- **DEF-01:** create class group → assign a teacher (or enroll a student) → `DELETE /institutions/{id}/class-groups/{cg}` → 204. The enrollment and assignment rows are gone.
- **DEF-02:** `POST /admin/institutions/{id}/disable` → that institution's admin logs in (200) and reads `/institutions/{id}/academic-years` (200).
- **DEF-03:** `POST /enrollments` twice with the same student and class → both 201 → that student's `GET /student/exams` → 500.
- **DEF-04:** 8 parallel `PUT /attempts/{a}/answers/{q}` for one question.
- **DEF-07:** `scoring_service._numeric_match("3.13", "3.14", "0.01")` → `False`.

## 4. Observations (not defects — confirm intent)

- **Topics/objectives are admin-only.** Teachers get 403 creating syllabus topics, though they can author questions. Confirm this is intended.
- **Multi-select with one correct option is allowed**, by design (`≥1 correct`).
- **Question options are not shuffled at authoring time.** AI output usually lists the correct option first. Delivery shuffles per student, so exams are fine, but reviewers may notice the pattern.
- **Production build (`next build`) was not run**, because it would collide with the running dev server's `.next`. CI runs it.

## 5. What passed (coverage highlights)

- **Auth:** login and logout; no user enumeration (login and password reset); rate limiting (429); refresh rotation with replay detection that revokes the whole token family; password change and reset (single-use token); TOTP MFA setup, enable and enforced login.
- **Onboarding:** registration submit/approve/reject (decided requests can't be re-decided); direct institution create with full profile validation (required fields, time zone, duplicate code/email with no partial record); profile edit; logo upload; SVG refused; old temporary password invalidated after change.
- **Structure & people:** CRUD with duplicate protection; invitations (single-use, can't grant admin); self-registration → pending → approve; duplicate register numbers; roster preview, error rows, all-or-nothing commit, idempotent re-import; teacher assignment role checks; transfer preserves history.
- **Question bank:** all 4 types plus 10 invalid-question rules; immutable versions; draft → review → approve/reject; teachers can't approve; search filters; students blocked; documents (type allow-list, path traversal neutralised, staff-only download, tenant-scoped).
- **AI:** mock generation lands `in_review`; idempotency key; pool cap; students blocked; global library (reviewer-only generation; teachers see only approved global items; private questions never leak).
- **Exams:** teachers limited to assigned classes; state machine enforced; pool-sufficiency blocks approval; approval freezes config; frozen exams not editable; preview has no answer keys; schedule validation; time zone kept.
- **Delivery:** eligibility (enrollment, transfer, other tenant, teachers); attempt payload has **no answer keys**; resume returns the same snapshot; autosave versioning; single-answer and foreign-option validation; other students can't read or write the attempt; idempotent submit including **6 concurrent submits**; attempt limit; **timer expiry auto-submits and keeps autosaved answers**; results hidden until published.
- **Scoring & reports:** expected score 6/8 reproduced; re-score reproducible; CSV export (no formula injection); report access by role (assigned teacher yes, unassigned teacher and student no, Super Admin cross-tenant path yes, admin no); publish; result has no answer keys; re-score blocked after publish; corrections require a reason and are admin-only; census report.
- **Isolation:** another institution's admin denied on 12 endpoints; members denied the other tenant's profile and data; tenant context guard.
- **UI:** every page for public, Super Admin, admin, teacher and student renders with **no JS errors, no 5xx, no error screens**. Real form logins; wrong-password message; sign-out clears access; role-restricted URLs typed directly are handled; students are redirected away from `/admin`; bad attempt/result ids show friendly messages; academic CRUD through the UI (create, edit dialog, delete confirm, duplicate-name toast); mobile menu open/close; no horizontal overflow; all inputs labelled, icon buttons named, images have alt text; visible keyboard focus.

## 6. Re-running

```sh
sh qa/reset_qa_db.sh                       # fresh masterminds_qa (migrations + QA Super Admin)
cd backend && DATABASE_URL=postgresql+asyncpg://masterminds:masterminds@localhost:5433/masterminds_qa \
  AI_PROVIDER=mock ./.venv/Scripts/python -m uvicorn app.main:app --port 8001   # QA backend
./.venv/Scripts/python -I -X utf8 ../qa/api_e2e.py http://localhost:8001 results.json
./.venv/Scripts/python -I -X utf8 ../qa/ui_e2e.py <screenshot-dir>         # needs dev stack on :3000/:8000
```
The API suite takes about 2 minutes (it includes a 65 s timer-expiry wait). Reset the QA database before each run, because the suite turns on MFA for the QA Super Admin.

## 7. Fixes (re-verified)

| ID | Fix |
|---|---|
| DEF-01 | `academic_service.delete_row` inspects **every foreign key** that points at the row and refuses the delete with **409** and a list of what still uses it (e.g. "2 enrollments, 1 teacher assignments"). Nothing is deleted or nulled behind the scenes. |
| DEF-02 | Sessions only count memberships in **active** institutions (`get_user_institution_ids`). A user whose only institutions are disabled is refused (**403**) at login, on every request with an existing token, and on token refresh. Exam eligibility also needs an active institution. Self-registration and invitation acceptance are refused for inactive institutions. Super Admin is unaffected, and re-enabling restores access. |
| DEF-03 | A second active enrollment in the same class group is refused (**409**). The student exam list and attempt start no longer crash if legacy duplicates exist. Also fixed while here: **transfer** now validates that the target class group is in the same institution, that the enrollment is still active, and that the student isn't already in the target class. |
| DEF-04 | Autosave and submit take a **row lock** on the attempt (`SELECT … FOR UPDATE`). Start takes a per-(exam, student) **advisory lock**, so concurrent requests run one at a time: no 500s, unique answer versions, one attempt per double-click. The exam page now saves only *changed* answers instead of re-sending all of them on every keystroke. |
| DEF-05 | Class-group create validates term, grade and course belong to the same institution (**404** otherwise; no more 500). |
| DEF-06 | Corrections must be between 0 and the attempt's total marks (**400**). |
| DEF-07 | Tolerance comparison uses `Decimal`, so boundaries are exact (3.13 vs 3.14 ± 0.01 → correct). |
| DEF-08 | Only users with the student role in the institution can be enrolled (**400**). |
| DEF-09 | Numerical answers must be numbers (**400**); an empty value clears the answer. The exam page holds unfinished input ("-", "3e") and shows an inline hint until the number is valid. |
| DEF-10 | Tabs stay on one row and scroll sideways on narrow screens. |

Concurrency fixes rely on PostgreSQL locks. They are no-ops on the SQLite unit-test database, so they are verified by `qa/api_e2e.py` section J (J02, J03, J08) against PostgreSQL.
