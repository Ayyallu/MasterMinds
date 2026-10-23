from __future__ import annotations

import pytest

from app.models import RoleName


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def _headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def inst_with_staff(client, factory):
    inst = await factory.institution("QB")
    await factory.user(
        email="qadmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    await factory.user(
        email="qteacher@example.com", role=RoleName.teacher, institution=inst
    )
    await factory.user(
        full_name="Student", role=RoleName.student, institution=inst,
        register_number="QS-1",
    )
    return inst


def _single_mcq():
    return {
        "type": "single_mcq",
        "text": "2 + 2 = ?",
        "difficulty": "easy",
        "marks": 1,
        "options": [
            {"text": "3", "is_correct": False},
            {"text": "4", "is_correct": True},
            {"text": "5", "is_correct": False},
        ],
    }


async def test_create_version_review_flow(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    admin = await _headers(client, "qadmin@example.com")

    created = await client.post(
        f"/institutions/{inst.id}/questions", json=_single_mcq(), headers=teacher
    )
    assert created.status_code == 201
    qid = created.json()["question_id"]
    vid = created.json()["version_id"]

    # Submit + approve.
    sub = await client.post(
        f"/institutions/{inst.id}/versions/{vid}/submit", headers=teacher
    )
    assert sub.status_code == 200 and sub.json()["status"] == "in_review"
    rev = await client.post(
        f"/institutions/{inst.id}/versions/{vid}/review?approve=true", headers=admin
    )
    assert rev.json()["status"] == "approved"

    # Editing creates a NEW version (immutability); original untouched.
    edit = await client.post(
        f"/institutions/{inst.id}/questions/{qid}/versions",
        json={**_single_mcq(), "text": "Two plus two?"},
        headers=teacher,
    )
    assert edit.json()["version_no"] == 2
    versions = await client.get(
        f"/institutions/{inst.id}/questions/{qid}/versions", headers=teacher
    )
    vs = versions.json()
    assert len(vs) == 2
    assert vs[0]["status"] == "approved" and vs[1]["status"] == "draft"


async def test_teacher_cannot_approve(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/questions", json=_single_mcq(), headers=teacher
    )
    vid = created.json()["version_id"]
    await client.post(f"/institutions/{inst.id}/versions/{vid}/submit", headers=teacher)
    rev = await client.post(
        f"/institutions/{inst.id}/versions/{vid}/review?approve=true", headers=teacher
    )
    assert rev.status_code == 403


async def test_answer_key_never_exposed_to_students(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    created = await client.post(
        f"/institutions/{inst.id}/questions", json=_single_mcq(), headers=teacher
    )
    qid = created.json()["question_id"]

    # A student cannot reach the staff question endpoints at all.
    student = await _login(
        client, institution_code="QB", register_number="QS-1", password="Password123!"
    )
    stoken = {"Authorization": f"Bearer {student.json()['access_token']}"}
    denied = await client.get(
        f"/institutions/{inst.id}/questions/{qid}/versions", headers=stoken
    )
    assert denied.status_code == 403

    # Staff serialization DOES include keys (so it's a real secret being hidden).
    staff_view = await client.get(
        f"/institutions/{inst.id}/questions/{qid}/versions", headers=teacher
    )
    assert any(o["is_correct"] for o in staff_view.json()[0]["options"])


async def test_serialize_strips_keys_for_students():
    # Unit-level guard on the student serializer used by future exam endpoints.
    from types import SimpleNamespace
    from app.services import question_service

    v = SimpleNamespace(
        question_id=1, id=10, version_no=1, type="single_mcq", text="q",
        explanation="because", difficulty="easy", marks=1, status="approved",
        numerical_answer=None, numerical_tolerance=None,
    )
    opts = [SimpleNamespace(id=1, text="a", order_index=0, is_correct=True)]
    student = question_service.serialize(v, opts, include_keys=False)
    assert student["options"][0]["is_correct"] is None
    assert student["explanation"] is None


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"type": "single_mcq", "text": "q", "options": [
            {"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]},
         "single correct"),
        ({"type": "single_mcq", "text": "q", "options": [
            {"text": "a", "is_correct": True}, {"text": "a", "is_correct": False}]},
         "unique options"),
        ({"type": "numerical", "text": "q", "numerical_answer": "abc"},
         "numeric"),
        ({"type": "numerical", "text": "q"}, "numerical_answer required"),
        ({"type": "true_false", "text": "q", "options": [
            {"text": "Yes", "is_correct": True}, {"text": "No", "is_correct": False}]},
         "true/false labels"),
    ],
)
async def test_validation_rejects_bad_questions(client, inst_with_staff, payload, field):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    r = await client.post(
        f"/institutions/{inst.id}/questions", json=payload, headers=teacher
    )
    assert r.status_code == 422, f"expected 422 for {field}: {r.status_code}"


async def test_numerical_and_search(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    num = {
        "type": "numerical", "text": "pi to 2dp?", "numerical_answer": "3.14",
        "numerical_tolerance": "0.01", "difficulty": "hard", "marks": 2,
    }
    r = await client.post(
        f"/institutions/{inst.id}/questions", json=num, headers=teacher
    )
    assert r.status_code == 201

    found = await client.post(
        f"/institutions/{inst.id}/questions/search",
        json={"type": "numerical", "difficulty": "hard"},
        headers=teacher,
    )
    rows = found.json()
    assert len(rows) == 1 and rows[0]["numerical_answer"] == "3.14"


async def test_question_bank_tenant_scoped(client, factory, inst_with_staff):
    other = await factory.institution("OTHER")
    teacher = await _headers(client, "qteacher@example.com")  # staff of QB
    r = await client.post(
        f"/institutions/{other.id}/questions", json=_single_mcq(), headers=teacher
    )
    assert r.status_code == 403


# --- Documents ---
async def test_document_upload_and_download(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    files = {"file": ("syllabus.txt", b"unit 1 content", "text/plain")}
    up = await client.post(
        f"/institutions/{inst.id}/documents", files=files, headers=teacher
    )
    assert up.status_code == 201
    doc_id = up.json()["id"]

    dl = await client.get(
        f"/institutions/{inst.id}/documents/{doc_id}/download", headers=teacher
    )
    assert dl.status_code == 200
    assert dl.content == b"unit 1 content"


async def test_document_rejects_bad_type(client, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    files = {"file": ("evil.exe", b"MZ...", "application/x-msdownload")}
    up = await client.post(
        f"/institutions/{inst.id}/documents", files=files, headers=teacher
    )
    assert up.status_code == 400


async def test_document_download_tenant_scoped(client, factory, inst_with_staff):
    inst = inst_with_staff
    teacher = await _headers(client, "qteacher@example.com")
    files = {"file": ("s.txt", b"abc", "text/plain")}
    up = await client.post(
        f"/institutions/{inst.id}/documents", files=files, headers=teacher
    )
    doc_id = up.json()["id"]

    # Staff of another institution cannot download it.
    other = await factory.institution("OTHER2")
    await factory.user(
        email="other_staff@example.com", role=RoleName.teacher, institution=other
    )
    other_h = await _headers(client, "other_staff@example.com")
    dl = await client.get(
        f"/institutions/{other.id}/documents/{doc_id}/download", headers=other_h
    )
    assert dl.status_code == 404
