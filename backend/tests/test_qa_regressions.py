"""Regression tests for defects found in the 2026-11-12 end-to-end QA pass
(docs/QA_E2E_REPORT.md). Concurrency defects (DEF-04, double Start) need real
PostgreSQL row/advisory locks and are covered by qa/api_e2e.py section J."""
from __future__ import annotations

import pytest

from app.models import (
    ClassGroup,
    Enrollment,
    EnrollmentStatus,
    RoleName,
    TeacherAssignment,
)
from app.services.scoring_service import _numeric_match
from tests.test_scoring import _complete_attempt, _headers, scored_env  # noqa: F401


@pytest.fixture
async def inst_env(client, factory):
    a = await factory.institution("RA")
    b = await factory.institution("RB")
    await factory.user(email="ra@example.com", role=RoleName.institution_admin, institution=a)
    await factory.user(email="rb@example.com", role=RoleName.institution_admin, institution=b)
    teacher = await factory.user(email="rt@example.com", role=RoleName.teacher, institution=a)
    student = await factory.user(role=RoleName.student, institution=a, register_number="R1", full_name="Stu")
    return a, b, teacher, student


# --- DEF-01: deleting an in-use record must be refused, never cascade --------
async def test_delete_in_use_class_group_refused(client, inst_env, sessionmaker):
    a, _, teacher, student = inst_env
    h = await _headers(client, "ra@example.com")
    cg = (await client.post(f"/institutions/{a.id}/class-groups", json={"name": "G"}, headers=h)).json()["id"]
    async with sessionmaker() as s:
        s.add(Enrollment(institution_id=a.id, student_user_id=student.id, class_group_id=cg,
                         status=EnrollmentStatus.active.value))
        s.add(TeacherAssignment(institution_id=a.id, teacher_user_id=teacher.id, class_group_id=cg))
        await s.commit()
    r = await client.delete(f"/institutions/{a.id}/class-groups/{cg}", headers=h)
    assert r.status_code == 409
    assert "enrollments" in r.json()["detail"] and "teacher assignments" in r.json()["detail"]
    async with sessionmaker() as s:
        assert await s.get(ClassGroup, cg) is not None  # nothing destroyed


async def test_delete_year_with_terms_refused(client, inst_env):
    a, *_ = inst_env
    h = await _headers(client, "ra@example.com")
    y = (await client.post(f"/institutions/{a.id}/academic-years", json={"name": "Y"}, headers=h)).json()["id"]
    await client.post(f"/institutions/{a.id}/terms", json={"academic_year_id": y, "name": "T"}, headers=h)
    assert (await client.delete(f"/institutions/{a.id}/academic-years/{y}", headers=h)).status_code == 409


# --- DEF-02: a disabled institution is locked out -------------------------------
async def test_disabled_institution_blocks_login_sessions_and_registration(client, inst_env, factory):
    a, *_ = inst_env
    await factory.user(email="root@example.com", is_super_admin=True)
    root = await _headers(client, "root@example.com")
    admin = await _headers(client, "ra@example.com")
    login = await client.post("/auth/login", json={"email": "ra@example.com", "password": "Password123!"})
    refresh = login.json()["refresh_token"]

    assert (await client.post(f"/admin/institutions/{a.id}/disable", headers=root)).status_code == 200
    assert (await client.post("/auth/login", json={"email": "ra@example.com", "password": "Password123!"})).status_code == 403
    assert (await client.post("/auth/login", json={"institution_code": "RA", "register_number": "R1", "password": "Password123!"})).status_code == 403
    assert (await client.get(f"/institutions/{a.id}/class-groups", headers=admin)).status_code == 403  # old token
    assert (await client.post("/auth/refresh", json={"refresh_token": refresh})).status_code == 403
    reg = await client.post("/students/self-register", json={"institution_code": "RA", "register_number": "R9",
                                                              "full_name": "Late", "password": "Password123!"})
    assert reg.status_code == 403
    # Super Admin is unaffected and can re-enable.
    assert (await client.post(f"/admin/institutions/{a.id}/enable", headers=root)).status_code == 200
    assert (await client.post("/auth/login", json={"email": "ra@example.com", "password": "Password123!"})).status_code == 200


# --- DEF-03 / DEF-08: enrollment integrity --------------------------------------
async def test_duplicate_and_non_student_enrollment_refused(client, inst_env):
    a, _, teacher, student = inst_env
    h = await _headers(client, "ra@example.com")
    cg = (await client.post(f"/institutions/{a.id}/class-groups", json={"name": "G"}, headers=h)).json()["id"]
    url = f"/institutions/{a.id}/enrollments"
    assert (await client.post(url, json={"student_user_id": student.id, "class_group_id": cg}, headers=h)).status_code == 201
    assert (await client.post(url, json={"student_user_id": student.id, "class_group_id": cg}, headers=h)).status_code == 409
    assert (await client.post(url, json={"student_user_id": teacher.id, "class_group_id": cg}, headers=h)).status_code == 400


async def test_existing_duplicate_enrollment_does_not_crash_student(client, scored_env, sessionmaker):  # noqa: F811
    inst, eid = scored_env
    sh = await _headers(client, "scstudent@example.com")
    async with sessionmaker() as s:
        first = (await s.execute(Enrollment.__table__.select())).first()
        s.add(Enrollment(institution_id=inst.id, student_user_id=first.student_user_id,
                         class_group_id=first.class_group_id, status=EnrollmentStatus.active.value))
        await s.commit()
    assert (await client.get("/student/exams", headers=sh)).status_code == 200
    assert (await client.post(f"/exams/{eid}/attempts/start", headers=sh)).status_code in (200, 201)


async def test_transfer_validates_target(client, inst_env):
    a, b, _, student = inst_env
    h = await _headers(client, "ra@example.com")
    hb = await _headers(client, "rb@example.com")
    cg1 = (await client.post(f"/institutions/{a.id}/class-groups", json={"name": "G1"}, headers=h)).json()["id"]
    cgb = (await client.post(f"/institutions/{b.id}/class-groups", json={"name": "GB"}, headers=hb)).json()["id"]
    enr = (await client.post(f"/institutions/{a.id}/enrollments", json={"student_user_id": student.id, "class_group_id": cg1}, headers=h)).json()["id"]
    url = f"/institutions/{a.id}/enrollments/transfer"
    assert (await client.post(url, json={"enrollment_id": enr, "new_class_group_id": cgb}, headers=h)).status_code == 404
    assert (await client.post(url, json={"enrollment_id": enr, "new_class_group_id": cg1}, headers=h)).status_code == 409


# --- DEF-05: no cross-tenant links on create; bad ids are 404 not 500 -----------
async def test_class_group_create_validates_links(client, inst_env):
    a, b, *_ = inst_env
    h = await _headers(client, "ra@example.com")
    hb = await _headers(client, "rb@example.com")
    yb = (await client.post(f"/institutions/{b.id}/academic-years", json={"name": "YB"}, headers=hb)).json()["id"]
    tb = (await client.post(f"/institutions/{b.id}/terms", json={"academic_year_id": yb, "name": "TB"}, headers=hb)).json()["id"]
    assert (await client.post(f"/institutions/{a.id}/class-groups", json={"name": "X", "term_id": tb}, headers=h)).status_code == 404
    assert (await client.post(f"/institutions/{a.id}/class-groups", json={"name": "Y", "term_id": 999999}, headers=h)).status_code == 404


# --- DEF-06: corrections bounded by the exam's total marks ----------------------
async def test_correction_bounded(client, scored_env):  # noqa: F811
    inst, eid = scored_env
    admin = await _headers(client, "scadmin@example.com")
    sh = await _headers(client, "scstudent@example.com")
    aid = await _complete_attempt(client, eid, sh)
    await client.post(f"/institutions/{inst.id}/exams/{eid}/score", headers=admin)
    url = f"/institutions/{inst.id}/attempts/{aid}/correct"
    assert (await client.post(url, json={"awarded_marks": 5, "reason": "x"}, headers=admin)).status_code == 400  # total is 4
    assert (await client.post(url, json={"awarded_marks": 4, "reason": "x"}, headers=admin)).status_code == 200


# --- DEF-07: tolerance boundary is exact -----------------------------------------
@pytest.mark.parametrize("student,answer,tol,expected", [
    ("3.13", "3.14", "0.01", True), ("3.15", "3.14", "0.01", True),
    ("3.16", "3.14", "0.01", False), ("0.3", "0.1", "0.2", True),
    ("2", "2.0", None, True), ("abc", "2", "0.1", False), ("NaN", "2", "1", False),
])
def test_numeric_tolerance_exact(student, answer, tol, expected):
    assert _numeric_match(student, answer, tol) is expected


# --- DEF-09: numerical autosave rejects text, allows clearing -------------------
async def test_numerical_answer_validation_unit():
    from types import SimpleNamespace

    from app.services.attempt_service import _validate_answer
    from app.services.auth_service import AuthError

    q = {"type": "numerical", "option_order": []}
    assert _validate_answer(q, SimpleNamespace(numerical_value=" 3.14 ", selected_option_ids=None)) == {"numerical_value": "3.14"}
    assert _validate_answer(q, SimpleNamespace(numerical_value="", selected_option_ids=None)) == {"numerical_value": ""}
    for bad in ("abc", "1.2.3", "inf", "NaN"):
        with pytest.raises(AuthError):
            _validate_answer(q, SimpleNamespace(numerical_value=bad, selected_option_ids=None))
