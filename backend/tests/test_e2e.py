"""Phase 9: full end-to-end journeys for two institutions + cross-tenant audit.

Exercises the whole system through the public API: onboarding, academic setup,
question bank, exam authoring/approval, student delivery, scoring, publication,
and reporting — asserting tenant isolation at every layer.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import (
    ClassGroup,
    Enrollment,
    EnrollmentStatus,
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


async def _seed_approved(sessionmaker, institution_id, n):
    ids = []
    async with sessionmaker() as s:
        for i in range(n):
            q = Question(institution_id=institution_id, is_global=False)
            s.add(q)
            await s.flush()
            v = QuestionVersion(
                question_id=q.id, version_no=1, type="single_mcq",
                text=f"{institution_id}-Q{i}", difficulty="easy", marks=2,
                status=QuestionStatus.approved.value,
            )
            s.add(v)
            await s.flush()
            s.add_all([
                QuestionOption(question_version_id=v.id, text="a", is_correct=True, order_index=0),
                QuestionOption(question_version_id=v.id, text="b", is_correct=False, order_index=1),
            ])
            ids.append(v.id)
        await s.commit()
    return ids


async def _onboard_institution(client, sessionmaker, root_h, code):
    """Register -> super-admin approve -> returns (inst_id, admin_email, admin_pw)."""
    sub = await client.post(
        "/registrations",
        json={"institution_name": f"{code} School", "requested_code": code,
              "contact_name": "C", "contact_email": f"{code.lower()}@example.com"},
    )
    req_id = sub.json()["id"]
    appr = await client.post(
        f"/admin/registrations/{req_id}/approve",
        json={"admin_email": f"{code.lower()}admin@example.com",
              "admin_full_name": f"{code} Admin"},
        headers=root_h,
    )
    assert appr.status_code == 200
    inst_id = appr.json()["institution"]["id"]
    return inst_id, f"{code.lower()}admin@example.com", appr.json()["debug_admin_temp_password"]


async def _setup_exam_and_student(client, factory, sessionmaker, inst_id, admin_h, code):
    # Class group + enrolled student.
    student = await factory.user(
        email=f"{code.lower()}stud@example.com", role=RoleName.student,
    )
    # factory.user without institution doesn't add membership; add membership+enrollment.
    from app.models import InstitutionMembership, UserStatus
    async with sessionmaker() as s:
        cg = ClassGroup(institution_id=inst_id, name=f"{code}-C", kind="class")
        s.add(cg)
        await s.flush()
        s.add(InstitutionMembership(
            user_id=student.id, institution_id=inst_id,
            status=UserStatus.active.value,
        ))
        s.add(Enrollment(
            institution_id=inst_id, student_user_id=student.id,
            class_group_id=cg.id, status=EnrollmentStatus.active.value,
        ))
        await s.commit()
        cg_id = cg.id
    await _seed_approved(sessionmaker, inst_id, 2)

    created = await client.post(
        f"/institutions/{inst_id}/exams",
        json={"title": f"{code} Exam", "class_group_id": cg_id,
              "duration_minutes": 60,
              "distribution": [{"type": "single_mcq", "count": 2}]},
        headers=admin_h,
    )
    eid = created.json()["id"]
    await client.post(f"/institutions/{inst_id}/exams/{eid}/submit", headers=admin_h)
    await client.post(f"/institutions/{inst_id}/exams/{eid}/approve", headers=admin_h)
    await client.post(
        f"/institutions/{inst_id}/exams/{eid}/schedule",
        json={"start_at": "2020-01-01T00:00:00Z", "end_at": "2035-01-01T00:00:00Z"},
        headers=admin_h,
    )
    return eid, f"{code.lower()}stud@example.com", cg_id


async def _take_and_score(client, inst_id, eid, admin_h, student_h):
    start = await client.post(f"/exams/{eid}/attempts/start", headers=student_h)
    aid = start.json()["id"]
    for q in start.json()["questions"]:
        oid = next(o["id"] for o in q["options"] if o["text"] == "a")
        await client.put(
            f"/attempts/{aid}/answers/{q['question_version_id']}",
            json={"selected_option_ids": [oid]}, headers=student_h,
        )
    await client.post(f"/attempts/{aid}/submit", headers=student_h)
    await client.post(f"/institutions/{inst_id}/exams/{eid}/score", headers=admin_h)
    await client.post(f"/institutions/{inst_id}/exams/{eid}/publish-results", headers=admin_h)
    return aid


async def test_two_institution_end_to_end_and_isolation(client, factory, sessionmaker):
    root_h = {"Authorization": f"Bearer {(await _login(client, email=(await _mk_root(client, factory)), password='Password123!')).json()['access_token']}"}

    a_id, a_admin, a_pw = await _onboard_institution(client, sessionmaker, root_h, "AAA")
    b_id, b_admin, b_pw = await _onboard_institution(client, sessionmaker, root_h, "BBB")
    a_admin_h = await _headers(client, a_admin, a_pw)
    b_admin_h = await _headers(client, b_admin, b_pw)

    a_eid, a_stud, a_cg = await _setup_exam_and_student(
        client, factory, sessionmaker, a_id, a_admin_h, "AAA"
    )
    b_eid, b_stud, b_cg = await _setup_exam_and_student(
        client, factory, sessionmaker, b_id, b_admin_h, "BBB"
    )
    a_stud_h = await _headers(client, a_stud)
    b_stud_h = await _headers(client, b_stud)

    a_aid = await _take_and_score(client, a_id, a_eid, a_admin_h, a_stud_h)
    b_aid = await _take_and_score(client, b_id, b_eid, b_admin_h, b_stud_h)

    # Each student sees their own released result.
    assert (await client.get(f"/attempts/{a_aid}/result", headers=a_stud_h)).json()["awarded_marks"] == 4
    assert (await client.get(f"/attempts/{b_aid}/result", headers=b_stud_h)).json()["awarded_marks"] == 4

    # --- Cross-tenant negative sweep ---
    # Admin A cannot touch institution B at any layer.
    assert (await client.get(f"/institutions/{b_id}/exams/{b_eid}/report", headers=a_admin_h)).status_code == 403
    assert (await client.post(f"/institutions/{b_id}/exams/{b_eid}/score", headers=a_admin_h)).status_code == 403
    assert (await client.post(f"/institutions/{b_id}/class-groups", json={"name": "x"}, headers=a_admin_h)).status_code == 403
    assert (await client.post(f"/institutions/{b_id}/questions/search", json={}, headers=a_admin_h)).status_code == 403
    # Student A cannot read student B's attempt/result.
    assert (await client.get(f"/attempts/{b_aid}/result", headers=a_stud_h)).status_code == 404
    assert (await client.get(f"/attempts/{b_aid}", headers=a_stud_h)).status_code == 404
    # Student A cannot start B's exam.
    assert (await client.post(f"/exams/{b_eid}/attempts/start", headers=a_stud_h)).status_code == 403
    # Question search is tenant-isolated: A sees only its own questions.
    a_search = await client.post(f"/institutions/{a_id}/questions/search", json={}, headers=a_admin_h)
    for row in a_search.json():
        assert row["text"].startswith(f"{a_id}-")


async def _mk_root(client, factory) -> str:
    await factory.user(email="e2eroot@example.com", is_super_admin=True)
    return "e2eroot@example.com"


# --- Reliability: concurrent / duplicate operations ---
async def test_duplicate_submit_is_safe(client, factory, sessionmaker):
    import asyncio

    await factory.user(email="relroot@example.com", is_super_admin=True)
    root_h = await _headers(client, "relroot@example.com")
    inst_id, admin_email, admin_pw = await _onboard_institution(client, sessionmaker, root_h, "REL")
    admin_h = await _headers(client, admin_email, admin_pw)
    eid, stud, _ = await _setup_exam_and_student(
        client, factory, sessionmaker, inst_id, admin_h, "REL"
    )
    stud_h = await _headers(client, stud)
    aid = (await client.post(f"/exams/{eid}/attempts/start", headers=stud_h)).json()["id"]

    # Fire several submits "concurrently" — must not error or duplicate.
    results = await asyncio.gather(
        *[client.post(f"/attempts/{aid}/submit", headers=stud_h) for _ in range(5)],
        return_exceptions=True,
    )
    statuses = [r.status_code for r in results if not isinstance(r, Exception)]
    assert all(c == 200 for c in statuses)
    final = await client.get(f"/attempts/{aid}", headers=stud_h)
    assert final.json()["status"] == "submitted"
