from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    ClassGroup,
    Enrollment,
    EnrollmentStatus,
    Exam,
    ExamAttempt,
    ExamStatus,
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionVersion,
    RoleName,
)
from app.services import scoring_service


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def _headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _approved_mcq(sessionmaker, institution_id, n):
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
            ])
        await s.commit()


@pytest.fixture
async def scored_env(client, factory, sessionmaker):
    inst = await factory.institution("SC")
    await factory.user(
        email="scadmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    student = await factory.user(
        email="scstudent@example.com", role=RoleName.student, institution=inst
    )
    async with sessionmaker() as s:
        cg = ClassGroup(institution_id=inst.id, name="C", kind="class")
        s.add(cg)
        await s.flush()
        s.add(Enrollment(
            institution_id=inst.id, student_user_id=student.id,
            class_group_id=cg.id, status=EnrollmentStatus.active.value,
        ))
        await s.commit()
        cg_id = cg.id
    await _approved_mcq(sessionmaker, inst.id, 2)

    admin = await _headers(client, "scadmin@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/exams",
        json={"title": "T", "class_group_id": cg_id, "duration_minutes": 60,
              "distribution": [{"type": "single_mcq", "count": 2}]},
        headers=admin,
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst.id}/exams/{eid}/submit", headers=admin)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/approve", headers=admin)
    await client.post(
        f"/institutions/{inst.id}/exams/{eid}/schedule",
        json={"start_at": "2020-01-01T00:00:00Z", "end_at": "2035-01-01T00:00:00Z"},
        headers=admin,
    )
    return inst, eid


async def _complete_attempt(client, eid, sh, *, correct_first=True):
    start = await client.post(f"/exams/{eid}/attempts/start", headers=sh)
    aid = start.json()["id"]
    qs = start.json()["questions"]
    # Answer Q1 correct ("a"), Q2 wrong ("b").
    for idx, q in enumerate(qs):
        want = "a" if (idx == 0 and correct_first) else "b"
        oid = next(o["id"] for o in q["options"] if o["text"] == want)
        await client.put(
            f"/attempts/{aid}/answers/{q['question_version_id']}",
            json={"selected_option_ids": [oid]}, headers=sh,
        )
    await client.post(f"/attempts/{aid}/submit", headers=sh)
    return aid


async def test_score_publish_and_student_result(client, scored_env):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    aid = await _complete_attempt(client, eid, sh)

    scored = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/score", headers=admin
    )
    assert scored.json()["scored_attempts"] == 1

    # Hidden before publish.
    pre = await client.get(f"/attempts/{aid}/result", headers=sh)
    assert pre.status_code == 403

    pub = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/publish-results", headers=admin
    )
    assert pub.json()["results_published"] is True

    res = await client.get(f"/attempts/{aid}/result", headers=sh)
    assert res.status_code == 200
    body = res.json()
    assert body["total_marks"] == 4
    assert body["awarded_marks"] == 2  # one correct (2), one wrong (0)
    # Per-question outcome only — no correct-answer text leaked.
    for q in body["questions"]:
        assert set(q.keys()) == {"version_id", "marks", "awarded", "correct"}


async def test_rescore_blocked_after_publish(client, scored_env):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    await _complete_attempt(client, eid, sh)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/score", headers=admin)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/publish-results", headers=admin)
    again = await client.post(
        f"/institutions/{inst.id}/exams/{eid}/score", headers=admin
    )
    assert again.status_code == 409


async def test_manual_correction_with_reason(client, scored_env):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    aid = await _complete_attempt(client, eid, sh)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/score", headers=admin)

    corr = await client.post(
        f"/institutions/{inst.id}/attempts/{aid}/correct",
        json={"awarded_marks": 4, "reason": "re-marked Q2"},
        headers=admin,
    )
    assert corr.status_code == 200
    assert corr.json()["awarded_marks"] == 4
    assert corr.json()["score_version"] >= 2


async def test_report_and_csv_and_scope(client, scored_env, factory):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    await _complete_attempt(client, eid, sh)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/score", headers=admin)

    rep = await client.get(f"/institutions/{inst.id}/exams/{eid}/report", headers=admin)
    j = rep.json()
    assert j["participants"] == 1 and j["completed"] == 1
    assert j["score_distribution"] == [2]

    csv_resp = await client.get(
        f"/institutions/{inst.id}/exams/{eid}/report.csv", headers=admin
    )
    assert csv_resp.status_code == 200
    assert "student_user_id" in csv_resp.text

    # A student cannot read the admin report.
    r = await client.get(f"/institutions/{inst.id}/exams/{eid}/report", headers=sh)
    assert r.status_code == 403


async def test_super_admin_report_audited(client, scored_env, factory):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    await _complete_attempt(client, eid, sh)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/score", headers=admin)

    await factory.user(email="root@example.com", is_super_admin=True)
    root = await _headers(client, "root@example.com")
    r = await client.get(
        f"/admin/institutions/{inst.id}/exams/{eid}/report", headers=root
    )
    assert r.status_code == 200 and r.json()["participants"] == 1


async def test_enrollment_census(client, scored_env):
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    r = await client.get(
        f"/institutions/{inst.id}/reports/enrollment",
        params={"census_date": date.today().isoformat()},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["active_enrollments"] >= 1


# --- Service-level scoring of all types (deterministic) ---
async def test_scoring_types_deterministic(sessionmaker, factory):
    inst = await factory.institution("TY")
    async with sessionmaker() as s:
        exam = Exam(institution_id=inst.id, title="x", status=ExamStatus.scheduled.value)
        s.add(exam)
        await s.flush()

        async def mk(qtype, marks, opts=None, num=None, tol=None):
            q = Question(institution_id=inst.id)
            s.add(q); await s.flush()
            v = QuestionVersion(question_id=q.id, version_no=1, type=qtype,
                                text="q", difficulty="easy", marks=marks,
                                status=QuestionStatus.approved.value,
                                numerical_answer=num, numerical_tolerance=tol)
            s.add(v); await s.flush()
            ids = []
            for i, (t, c) in enumerate(opts or []):
                o = QuestionOption(question_version_id=v.id, text=t, is_correct=c, order_index=i)
                s.add(o); await s.flush(); ids.append(o.id)
            return v, ids

        v_single, s_ids = await mk("single_mcq", 2, [("a", True), ("b", False)])
        v_multi, m_ids = await mk("multi_mcq", 3, [("a", True), ("b", True), ("c", False)])
        v_num, _ = await mk("numerical", 5, num="3.14", tol="0.01")
        await s.flush()

        attempt = ExamAttempt(
            exam_id=exam.id, institution_id=inst.id, student_user_id=1, attempt_no=1,
            status="submitted",
            snapshot={"marking": {"negative_marking": False}, "questions": [
                {"version_id": v_single.id, "type": "single_mcq", "marks": 2, "option_order": s_ids},
                {"version_id": v_multi.id, "type": "multi_mcq", "marks": 3, "option_order": m_ids},
                {"version_id": v_num.id, "type": "numerical", "marks": 5, "option_order": []},
            ]},
            started_at=scoring_service._utcnow(),
            deadline_at=scoring_service._utcnow(),
        )
        s.add(attempt); await s.flush()
        from app.models import AttemptAnswer
        # single correct (a), multi only one correct (all-or-nothing wrong),
        # numerical within tolerance (3.145 vs 3.14 +/- 0.01).
        s.add_all([
            AttemptAnswer(attempt_id=attempt.id, question_version_id=v_single.id,
                          answer={"selected_option_ids": [s_ids[0]]}, answer_version=1),
            AttemptAnswer(attempt_id=attempt.id, question_version_id=v_multi.id,
                          answer={"selected_option_ids": [m_ids[0]]}, answer_version=1),
            AttemptAnswer(attempt_id=attempt.id, question_version_id=v_num.id,
                          answer={"numerical_value": "3.145"}, answer_version=1),
        ])
        await s.flush()

        score = await scoring_service.score_attempt(s, attempt, actor_id=None)
        await s.commit()

    assert score.total_marks == 10  # 2 + 3 + 5
    assert score.awarded_marks == 7  # single(2) + numerical(5); multi all-or-nothing(0)
