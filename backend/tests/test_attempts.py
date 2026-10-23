from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import (
    ClassGroup,
    Enrollment,
    EnrollmentStatus,
    ExamAttempt,
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionVersion,
    RoleName,
)


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def _headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _approved_questions(sessionmaker, institution_id, n):
    async with sessionmaker() as s:
        for i in range(n):
            q = Question(institution_id=institution_id, is_global=False)
            s.add(q)
            await s.flush()
            v = QuestionVersion(
                question_id=q.id, version_no=1, type="single_mcq",
                text=f"Q{i}", difficulty="easy", marks=2,
                status=QuestionStatus.approved.value,
            )
            s.add(v)
            await s.flush()
            s.add_all([
                QuestionOption(question_version_id=v.id, text="a", is_correct=True, order_index=0),
                QuestionOption(question_version_id=v.id, text="b", is_correct=False, order_index=1),
                QuestionOption(question_version_id=v.id, text="c", is_correct=False, order_index=2),
            ])
        await s.commit()


@pytest.fixture
async def delivery_env(client, factory, sessionmaker):
    inst = await factory.institution("DEL")
    admin = await factory.user(
        email="deladmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    student = await factory.user(
        email="student@example.com", role=RoleName.student, institution=inst
    )
    async with sessionmaker() as s:
        cg = ClassGroup(institution_id=inst.id, name="C1", kind="class")
        s.add(cg)
        await s.flush()
        s.add(Enrollment(
            institution_id=inst.id, student_user_id=student.id,
            class_group_id=cg.id, status=EnrollmentStatus.active.value,
        ))
        await s.commit()
        cg_id = cg.id
    await _approved_questions(sessionmaker, inst.id, 3)

    admin_h = await _headers(client, "deladmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams",
        json={"title": "Final", "class_group_id": cg_id, "duration_minutes": 60,
              "attempt_limit": 1, "randomize": True,
              "distribution": [{"type": "single_mcq", "count": 2}]},
        headers=admin_h,
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=admin_h)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin_h)
    await client.post(
        f"/institutions/{inst.id}/exams/{eid}/schedule",
        json={"start_at": "2020-01-01T00:00:00Z", "end_at": "2035-01-01T00:00:00Z"},
        headers=admin_h,
    )
    return inst, eid


async def test_start_answer_resume_submit(client, delivery_env, sessionmaker):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")

    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    assert start.status_code == 200, start.text
    a = start.json()
    assert a["status"] == "in_progress"
    assert len(a["questions"]) == 2
    assert a["seconds_remaining"] > 0
    aid = a["id"]
    # Answer keys never leak to students.
    for q in a["questions"]:
        for o in q["options"]:
            assert set(o.keys()) == {"id", "text"}

    # Autosave one answer.
    qv = a["questions"][0]["question_version_id"]
    oid = a["questions"][0]["options"][0]["id"]
    save = await client.put(
        f"/attempts/{aid}/answers/{qv}",
        json={"selected_option_ids": [oid]}, headers=sh,
    )
    assert save.status_code == 200
    assert save.json()["answer_version"] == 1
    # Re-save advances the version (idempotent/concurrent-safe).
    save2 = await client.put(
        f"/attempts/{aid}/answers/{qv}",
        json={"selected_option_ids": [oid]}, headers=sh,
    )
    assert save2.json()["answer_version"] == 2

    # Resume: starting again returns the SAME attempt with saved answers + order.
    resume = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    assert resume.json()["id"] == aid
    order_now = [q["question_version_id"] for q in resume.json()["questions"]]
    order_orig = [q["question_version_id"] for q in a["questions"]]
    assert order_now == order_orig
    saved_q = next(q for q in resume.json()["questions"] if q["question_version_id"] == qv)
    assert saved_q["answer"] == {"selected_option_ids": [oid]}

    # Submit, then re-submit is idempotent (no change).
    sub = await client.post(f"/attempts/{aid}/submit", headers=sh)
    assert sub.json()["status"] == "submitted"
    submitted_at = sub.json()["submitted_at"]
    again = await client.post(f"/attempts/{aid}/submit", headers=sh)
    assert again.json()["status"] == "submitted"
    # Same instant (idempotent); tolerate naive-vs-aware formatting from SQLite.
    norm = lambda t: t.replace("+00:00", "")
    assert norm(again.json()["submitted_at"]) == norm(submitted_at)


async def test_no_answer_after_submit(client, delivery_env):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")
    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    aid = start.json()["id"]
    qv = start.json()["questions"][0]["question_version_id"]
    oid = start.json()["questions"][0]["options"][0]["id"]
    await client.post(f"/attempts/{aid}/submit", headers=sh)
    late = await client.put(
        f"/attempts/{aid}/answers/{qv}",
        json={"selected_option_ids": [oid]}, headers=sh,
    )
    assert late.status_code == 409


async def test_attempt_limit_enforced(client, delivery_env):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")
    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    await client.post(f"/attempts/{start.json()['id']}/submit", headers=sh)
    # attempt_limit is 1 -> a second start is denied.
    second = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    assert second.status_code == 403


async def test_expiry_auto_submits(client, delivery_env, sessionmaker):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")
    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    aid = start.json()["id"]

    # Force the deadline into the past (simulate time passing).
    async with sessionmaker() as s:
        att = await s.get(ExamAttempt, aid)
        att.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()

    view = await client.get(f"/attempts/{aid}", headers=sh)
    assert view.json()["status"] == "submitted"
    assert view.json()["seconds_remaining"] == 0
    # No further answers accepted after expiry.
    qv = start.json()["questions"][0]["question_version_id"]
    oid = start.json()["questions"][0]["options"][0]["id"]
    late = await client.put(
        f"/attempts/{aid}/answers/{qv}", json={"selected_option_ids": [oid]}, headers=sh
    )
    assert late.status_code == 409


async def test_ineligible_student_denied(client, delivery_env, factory):
    inst, eid = delivery_env
    # A student in the institution but NOT enrolled in the exam's class.
    await factory.user(
        email="outsider@example.com", role=RoleName.student, institution=inst
    )
    oh = await _headers(client, "outsider@example.com")
    r = await client.post(f"/exams/{eid}/attempts/start", headers=oh)
    assert r.status_code == 403


async def test_other_student_cannot_read_attempt(client, delivery_env, factory, sessionmaker):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")
    aid = (await client.post(f"/exams/{eid}/attempts/start", headers=sh)).json()["id"]

    other = await factory.user(
        email="other@example.com", role=RoleName.student, institution=inst
    )
    oh = await _headers(client, "other@example.com")
    r = await client.get(f"/attempts/{aid}", headers=oh)
    assert r.status_code == 404


async def test_single_answer_rejects_multiple(client, delivery_env):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")
    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    aid = start.json()["id"]
    q = start.json()["questions"][0]
    two = [o["id"] for o in q["options"][:2]]
    r = await client.put(
        f"/attempts/{aid}/answers/{q['question_version_id']}",
        json={"selected_option_ids": two}, headers=sh,
    )
    assert r.status_code == 400


async def test_student_exam_listing_shows_eligible_exam_and_attempt_state(client, delivery_env):
    inst, eid = delivery_env
    sh = await _headers(client, "student@example.com")

    listing = await client.get("/student/exams", headers=sh)
    assert listing.status_code == 200, listing.text
    exams = listing.json()
    exam = next(row for row in exams if row["id"] == eid)
    assert exam["title"] == "Final"
    assert exam["can_start"] is True
    assert exam["attempts"] == []

    started = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    assert started.status_code == 200
    refreshed = await client.get("/student/exams", headers=sh)
    exam_after_start = next(row for row in refreshed.json() if row["id"] == eid)
    assert exam_after_start["attempts"][0]["id"] == started.json()["id"]
    assert exam_after_start["attempts"][0]["status"] == "in_progress"


async def test_non_student_cannot_use_student_attempt_routes(client, delivery_env):
    inst, eid = delivery_env
    admin_headers = await _headers(client, "deladmin@example.com")

    start = await client.post(f"/exams/{eid}/attempts/start", headers=admin_headers)
    assert start.status_code == 403
    listing = await client.get("/student/exams", headers=admin_headers)
    assert listing.status_code == 403
