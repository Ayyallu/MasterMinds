from __future__ import annotations

import pytest

from app import rate_limit
from app.ai.base import (
    GenerationResult,
    GenerationSpec,
    ProviderError,
    QuestionProvider,
)
from app.models import RoleName
from app.services import generation_service


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def _headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def inst_staff(client, factory):
    inst = await factory.institution("AI")
    await factory.user(
        email="aiadmin@example.com", role=RoleName.institution_admin, institution=inst
    )
    await factory.user(
        email="aiteacher@example.com", role=RoleName.teacher, institution=inst
    )
    return inst


# --- Endpoint: private generation via mock provider ---
async def test_private_generation_creates_in_review(client, inst_staff):
    inst = inst_staff
    teacher = await _headers(client, "aiteacher@example.com")
    gen = await client.post(
        f"/institutions/{inst.id}/ai/generate",
        json={"question_type": "single_mcq", "count": 3, "topics": ["algebra"]},
        headers=teacher,
    )
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["status"] == "completed"
    assert body["stored_count"] == 3

    # Candidates are stored as in_review (never auto-approved) and searchable by staff.
    search = await client.post(
        f"/institutions/{inst.id}/questions/search",
        json={"status": "in_review"},
        headers=teacher,
    )
    assert len(search.json()) == 3


async def test_generation_requires_staff(client, inst_staff, factory):
    inst = inst_staff
    await factory.user(
        full_name="S", role=RoleName.student, institution=inst, register_number="AS1"
    )
    stud = await _login(
        client, institution_code="AI", register_number="AS1", password="Password123!"
    )
    h = {"Authorization": f"Bearer {stud.json()['access_token']}"}
    r = await client.post(
        f"/institutions/{inst.id}/ai/generate",
        json={"question_type": "single_mcq", "count": 1},
        headers=h,
    )
    assert r.status_code == 403


async def test_generation_idempotency(client, inst_staff):
    inst = inst_staff
    teacher = await _headers(client, "aiteacher@example.com")
    body = {
        "question_type": "single_mcq",
        "count": 2,
        "idempotency_key": "batch-123",
    }
    first = await client.post(
        f"/institutions/{inst.id}/ai/generate", json=body, headers=teacher
    )
    second = await client.post(
        f"/institutions/{inst.id}/ai/generate", json=body, headers=teacher
    )
    assert first.json()["id"] == second.json()["id"]  # same job, no double-generate


async def test_generation_rate_limit(client, inst_staff):
    inst = inst_staff
    teacher = await _headers(client, "aiteacher@example.com")
    rate_limit.clear_all()
    last = None
    for _ in range(11):  # window max is 10
        last = await client.post(
            f"/institutions/{inst.id}/ai/generate",
            json={"question_type": "single_mcq", "count": 1},
            headers=teacher,
        )
    assert last.status_code == 429


async def test_pool_size_cap(client, inst_staff):
    inst = inst_staff
    teacher = await _headers(client, "aiteacher@example.com")
    r = await client.post(
        f"/institutions/{inst.id}/ai/generate",
        json={"question_type": "single_mcq", "count": 9999},
        headers=teacher,
    )
    assert r.status_code == 422  # schema caps at 200


# --- Service-level: malformed output, timeout, duplicates ---
class _MalformedProvider(QuestionProvider):
    name = "stub"

    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        return GenerationResult(
            candidates=[
                {"type": "single_mcq", "text": "ok", "options": [
                    {"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]},
                {"type": "single_mcq", "text": "bad - two correct", "options": [
                    {"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]},
                {"nonsense": True},
            ],
            model="stub-1",
        )


class _TimeoutProvider(QuestionProvider):
    name = "stub"

    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        raise ProviderError("boom")


async def test_malformed_candidates_rejected(sessionmaker, factory):
    inst = await factory.institution("SVC")
    await factory.user(email="svc@example.com", role=RoleName.teacher, institution=inst)
    async with sessionmaker() as s:
        job = await generation_service.run_generation(
            s,
            provider=_MalformedProvider(),
            institution_id=inst.id,
            is_global=False,
            actor_id=1,
            spec=GenerationSpec(question_type="single_mcq", count=3),
        )
        await s.commit()
    assert job.status == "completed"
    assert job.stored_count == 1
    assert job.rejected_count == 2


async def test_provider_failure_marks_job_failed(sessionmaker, factory):
    inst = await factory.institution("SVC2")
    async with sessionmaker() as s:
        job = await generation_service.run_generation(
            s,
            provider=_TimeoutProvider(),
            institution_id=inst.id,
            is_global=False,
            actor_id=1,
            spec=GenerationSpec(question_type="single_mcq", count=2),
        )
        await s.commit()
    assert job.status == "failed"
    assert job.stored_count == 0


async def test_duplicate_detection(sessionmaker, factory):
    inst = await factory.institution("SVC3")

    class _DupProvider(QuestionProvider):
        name = "stub"

        async def generate(self, spec):
            one = {"type": "single_mcq", "text": "same text", "options": [
                {"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]}
            return GenerationResult(candidates=[dict(one), dict(one)], model="s")

    async with sessionmaker() as s:
        job = await generation_service.run_generation(
            s, provider=_DupProvider(), institution_id=inst.id, is_global=False,
            actor_id=1, spec=GenerationSpec(question_type="single_mcq", count=2),
        )
        await s.commit()
    assert job.stored_count == 1
    assert job.duplicate_count == 1


# --- Global library: central reviewer gate + reuse + privacy ---
async def test_global_generation_and_central_review(client, factory):
    await factory.user(
        email="reviewer@example.com", role=RoleName.central_academic_reviewer
    )
    rev = await _headers(client, "reviewer@example.com")

    gen = await client.post(
        "/global/ai/generate",
        json={"question_type": "single_mcq", "count": 2, "topics": ["physics"]},
        headers=rev,
    )
    assert gen.status_code == 201
    assert gen.json()["is_global"] is True

    # Central reviewers can see generated candidates in the review queue.
    pre = await client.post("/global/library/search", json={"status": "in_review"}, headers=rev)
    candidates = pre.json()
    assert len(candidates) == 2
    assert all(row["status"] == "in_review" for row in candidates)

    # Review the exact returned version ids; no assumptions about sequence IDs.
    for candidate in candidates:
        r = await client.post(
            f"/global/questions/versions/{candidate['version_id']}/review?approve=true",
            headers=rev,
        )
        assert r.status_code == 200

    post = await client.post("/global/library/search", json={"status": "approved"}, headers=rev)
    assert len(post.json()) == 2


async def test_institution_staff_cannot_generate_global(client, inst_staff):
    teacher = await _headers(client, "aiteacher@example.com")
    r = await client.post(
        "/global/ai/generate",
        json={"question_type": "single_mcq", "count": 1},
        headers=teacher,
    )
    assert r.status_code == 403


async def test_private_questions_not_in_global_library(client, inst_staff, factory):
    inst = inst_staff
    teacher = await _headers(client, "aiteacher@example.com")
    # Create + approve a PRIVATE question.
    created = await client.post(
        f"/institutions/{inst.id}/questions",
        json={"type": "single_mcq", "text": "private q", "options": [
            {"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]},
        headers=teacher,
    )
    vid = created.json()["version_id"]
    admin = await _headers(client, "aiadmin@example.com")
    await client.post(f"/institutions/{inst.id}/versions/{vid}/submit", headers=teacher)
    await client.post(
        f"/institutions/{inst.id}/versions/{vid}/review?approve=true", headers=admin
    )
    # The approved private question must NOT appear in the global library.
    lib = await client.post("/global/library/search", json={}, headers=teacher)
    assert lib.json() == []



async def test_global_in_review_candidates_hidden_from_institution_staff(client, factory):
    await factory.user(
        email="reviewer2@example.com", role=RoleName.central_academic_reviewer
    )
    reviewer = await _headers(client, "reviewer2@example.com")
    generated = await client.post(
        "/global/ai/generate",
        json={"question_type": "single_mcq", "count": 1},
        headers=reviewer,
    )
    assert generated.status_code == 201
    candidate = await client.post(
        "/global/library/search",
        json={"status": "in_review"},
        headers=reviewer,
    )
    assert len(candidate.json()) == 1

    inst = await factory.institution("AIG")
    await factory.user(
        email="aigteacher@example.com", role=RoleName.teacher, institution=inst
    )
    teacher = await _headers(client, "aigteacher@example.com")
    hidden = await client.post(
        "/global/library/search",
        json={"status": "in_review"},
        headers=teacher,
    )
    assert hidden.status_code == 200
    assert hidden.json() == []
