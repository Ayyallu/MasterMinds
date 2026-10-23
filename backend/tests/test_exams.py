from __future__ import annotations

import pytest

from app.models import (
    ClassGroup,
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionVersion,
    RoleName,
    TeacherAssignment,
)


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def _headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_approved_questions(sessionmaker, *, institution_id, n, is_global=False):
    async with sessionmaker() as s:
        for i in range(n):
            q = Question(
                institution_id=None if is_global else institution_id,
                is_global=is_global,
            )
            s.add(q)
            await s.flush()
            v = QuestionVersion(
                question_id=q.id, version_no=1, type="single_mcq",
                text=f"Q{i}-{'g' if is_global else 'p'}-{institution_id}",
                difficulty="easy", marks=2,
                status=QuestionStatus.approved.value,
            )
            s.add(v)
            await s.flush()
            s.add_all([
                QuestionOption(question_version_id=v.id, text="a", is_correct=True, order_index=0),
                QuestionOption(question_version_id=v.id, text="b", is_correct=False, order_index=1),
            ])
        await s.commit()


@pytest.fixture
async def exam_env(client, factory, sessionmaker):
    inst = await factory.institution("EX")
    admin = await factory.user(
        email="exadmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    teacher = await factory.user(
        email="exteacher@example.com", role=RoleName.teacher, institution=inst
    )
    async with sessionmaker() as s:
        cg = ClassGroup(institution_id=inst.id, name="Class-A", kind="class")
        s.add(cg)
        await s.flush()
        s.add(TeacherAssignment(
            institution_id=inst.id, teacher_user_id=teacher.id, class_group_id=cg.id
        ))
        await s.commit()
        cg_id = cg.id
    await _make_approved_questions(sessionmaker, institution_id=inst.id, n=3)
    return inst, cg_id


def _exam_payload(cg_id, count=2):
    return {
        "title": "Midterm",
        "class_group_id": cg_id,
        "duration_minutes": 60,
        "distribution": [{"type": "single_mcq", "count": count}],
    }


async def test_teacher_authors_admin_approves(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")

    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    assert created.status_code == 201, created.text
    eid = created.json()["id"]

    sub = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/submit", headers=teacher
    )
    assert sub.json()["status"] == "awaiting_approval"

    # Teacher cannot approve.
    denied = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/approve", headers=teacher
    )
    assert denied.status_code == 403

    appr = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin
    )
    assert appr.status_code == 200
    body = appr.json()
    assert body["status"] == "approved"
    assert body["frozen"] is True
    assert body["num_questions"] == 2


async def test_teacher_cannot_schedule(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    eid = created.json()["id"]
    r = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/schedule",
        json={"start_at": "2027-01-01T09:00:00Z", "end_at": "2027-01-01T10:00:00Z"},
        headers=teacher,
    )
    assert r.status_code == 403


async def test_insufficient_pool_blocks_approval(client, exam_env):
    inst, cg_id = exam_env  # only 3 approved questions exist
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id, count=10),
        headers=teacher,
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=teacher)
    appr = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin
    )
    assert appr.status_code == 400
    assert "cannot satisfy" in appr.json()["detail"]


async def test_invalid_transition_rejected(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    eid = created.json()["id"]
    # Approve directly from draft (not awaiting) -> invalid transition 409.
    r = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin
    )
    assert r.status_code == 409


async def test_frozen_requires_reopen_to_edit(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=teacher)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin)

    # Editing a frozen (approved) exam is blocked.
    edit = await client.put(
        f"/institutions/{inst.id}/exams/{eid}",
        json=_exam_payload(cg_id, count=1), headers=teacher,
    )
    assert edit.status_code == 409

    # Reopen returns to draft (renewed approval required) and clears the freeze.
    reopen = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/reopen", headers=admin
    )
    assert reopen.json()["status"] == "draft" and reopen.json()["frozen"] is False
    edit2 = await client.put(
        f"/institutions/{inst.id}/exams/{eid}",
        json=_exam_payload(cg_id, count=1), headers=teacher,
    )
    assert edit2.status_code == 200


async def test_preview_hides_answer_keys(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=teacher)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin)

    preview = await client.get(
        f"/institutions/{inst.id}/exams/{eid}/preview", headers=teacher
    )
    rows = preview.json()
    assert len(rows) == 2
    for q in rows:
        for opt in q["options"]:
            assert opt["is_correct"] is None


async def test_schedule_flow(client, exam_env):
    inst, cg_id = exam_env
    teacher = await _headers(client, "exteacher@example.com")
    admin = await _headers(client, "exadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id), headers=teacher
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=teacher)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin)
    sched = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/schedule",
        json={"start_at": "2027-01-01T09:00:00Z", "end_at": "2027-01-01T10:00:00Z",
              "timezone": "America/New_York"},
        headers=admin,
    )
    assert sched.json()["status"] == "scheduled"


async def test_teacher_scope_denied_unassigned_class(client, exam_env, factory, sessionmaker):
    inst, cg_id = exam_env
    # A second class group the teacher is NOT assigned to.
    async with sessionmaker() as s:
        cg2 = ClassGroup(institution_id=inst.id, name="Class-B", kind="class")
        s.add(cg2)
        await s.commit()
        cg2_id = cg2.id
    teacher = await _headers(client, "exteacher@example.com")
    r = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg2_id), headers=teacher
    )
    assert r.status_code == 403


async def test_global_approved_questions_fill_pool(client, factory, sessionmaker):
    inst = await factory.institution("EXG")
    await factory.user(
        email="exgadmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    async with sessionmaker() as s:
        cg = ClassGroup(institution_id=inst.id, name="C", kind="class")
        s.add(cg)
        await s.commit()
        cg_id = cg.id
    # No private questions; only approved GLOBAL ones.
    await _make_approved_questions(sessionmaker, institution_id=inst.id, n=2, is_global=True)
    admin = await _headers(client, "exgadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams", json=_exam_payload(cg_id, count=2),
        headers=admin,
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=admin)
    appr = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin
    )
    assert appr.status_code == 200 and appr.json()["num_questions"] == 2
