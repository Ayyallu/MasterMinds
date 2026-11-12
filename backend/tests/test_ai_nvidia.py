"""NVIDIA NIM adapter: parsing, normalisation and error mapping (no network)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.ai import nvidia
from app.ai.base import GenerationSpec, ProviderAuthError, ProviderError, ProviderNotConfigured
from app.config import get_settings
from app.schemas_questions import QuestionCreate
from app.services import generation_service


@pytest.fixture
def nim(monkeypatch):
    """Configure the adapter and route its HTTP calls to a handler."""
    s = get_settings()
    monkeypatch.setattr(s, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(s, "nvidia_model", "test/model")
    calls: list[dict] = []
    state = {"handler": None}

    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        def handle(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls.append(body)
            return state["handler"](request, body)

        kwargs["transport"] = httpx.MockTransport(handle)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(nvidia.httpx, "AsyncClient", client_factory)
    return state, calls


def _reply(content: str, usage=None) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    })


def test_requires_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "nvidia_api_key", "  ")
    with pytest.raises(ProviderNotConfigured):
        nvidia.NvidiaNimProvider()


async def test_fenced_json_and_variants_are_normalised(nim):
    state, calls = nim
    content = "Here you go:\n```json\n" + json.dumps({"questions": [
        {"question": "What is 1/2 + 1/4?", "choices": ["A) 3/4", "B) 1/6", "C) 2/6", "D) 1"],
         "answer": "A", "difficulty": "Easy", "marks": "1"},
    ]}) + "\n```"
    state["handler"] = lambda req, body: _reply(content)
    result = await nvidia.NvidiaNimProvider().generate(
        GenerationSpec(question_type="single_mcq", count=1, difficulty="easy", subject="Maths")
    )
    q = result.candidates[0]
    assert q["text"] == "What is 1/2 + 1/4?"
    assert [o["text"] for o in q["options"]] == ["3/4", "1/6", "2/6", "1"]
    assert [o["is_correct"] for o in q["options"]] == [True, False, False, False]
    QuestionCreate(**q)  # passes the app's own validation
    assert calls[0]["model"] == "test/model"
    assert calls[0]["response_format"] == {"type": "json_object"}


async def test_numerical_answer_number_becomes_string(nim):
    state, _ = nim
    state["handler"] = lambda req, body: _reply(json.dumps({"questions": [
        {"text": "Speed for 100 m in 20 s (m/s)?", "numerical_answer": 5, "tolerance": 0.1}
    ]}))
    result = await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="numerical", count=1))
    q = result.candidates[0]
    assert q["numerical_answer"] == "5" and q["numerical_tolerance"] == "0.1"
    QuestionCreate(**q)


async def test_true_false_from_bare_answer(nim):
    state, _ = nim
    state["handler"] = lambda req, body: _reply(json.dumps([{"text": "Water boils at 100 C at sea level.", "answer": True}]))
    result = await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="true_false", count=1))
    QuestionCreate(**result.candidates[0])


async def test_large_pool_is_batched(nim):
    state, calls = nim

    def handler(req, body):
        n = int(body["messages"][1]["content"].split()[1])  # "Write <n> ..."
        return _reply(json.dumps({"questions": [
            {"text": f"Q{len(calls)}-{i}", "options": [{"text": "a", "is_correct": True}, {"text": "b"}]}
            for i in range(n)
        ]}))

    state["handler"] = handler
    result = await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="single_mcq", count=23))
    assert len(calls) == 5  # 5 + 5 + 5 + 5 + 3
    assert len(result.candidates) == 23
    assert result.usage["total_tokens"] == 150


async def test_partial_batch_failure_keeps_good_batches(nim):
    state, calls = nim

    def handler(req, body):
        if len(calls) == 2:
            return httpx.Response(503, json={"detail": "busy"})
        return _reply(json.dumps({"questions": [
            {"text": f"Q{len(calls)}-{i}", "options": [{"text": "a", "is_correct": True}, {"text": "b"}]}
            for i in range(5)
        ]}))

    state["handler"] = handler
    result = await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="single_mcq", count=15))
    assert len(result.candidates) == 10
    assert result.usage["failed_batches"] == 1


async def test_json_mode_rejection_falls_back(nim):
    state, calls = nim

    def handler(req, body):
        if "response_format" in body:
            return httpx.Response(400, json={"detail": "response_format is not supported"})
        return _reply(json.dumps({"questions": [{"text": "x?", "options": [{"text": "a", "is_correct": True}, {"text": "b"}]}]}))

    state["handler"] = handler
    result = await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="single_mcq", count=1))
    assert len(result.candidates) == 1 and len(calls) == 2


@pytest.mark.parametrize("status,needle", [(403, "rejected the API key"), (401, "rejected the API key"), (410, "not available")])
async def test_permanent_errors_are_clear_and_secret_free(nim, status, needle):
    state, _ = nim
    state["handler"] = lambda req, body: httpx.Response(status, json={"detail": "nope"})
    with pytest.raises(ProviderAuthError) as exc:
        await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="single_mcq", count=1))
    assert needle in str(exc.value)
    assert "nvapi-test" not in str(exc.value)


async def test_garbage_output_is_provider_error(nim):
    state, _ = nim
    state["handler"] = lambda req, body: _reply("Sorry, I can't help with that.")
    with pytest.raises(ProviderError):
        await nvidia.NvidiaNimProvider().generate(GenerationSpec(question_type="single_mcq", count=1))


async def test_auth_failure_not_retried_and_reason_kept(nim, sessionmaker, factory):
    state, calls = nim
    state["handler"] = lambda req, body: httpx.Response(403, json={"detail": "Authorization failed"})
    inst = await factory.institution("NIM1")
    async with sessionmaker() as s:
        job = await generation_service.run_generation(
            s, provider=nvidia.NvidiaNimProvider(), institution_id=inst.id, is_global=False,
            actor_id=1, spec=GenerationSpec(question_type="single_mcq", count=2),
        )
        await s.commit()
    assert job.status == "failed"
    assert "rejected the API key" in job.error
    assert len(calls) == 1  # no pointless retries


async def test_ai_status_endpoint(client, factory, monkeypatch):
    from app.models import RoleName

    inst = await factory.institution("ST1")
    await factory.user(email="t@example.com", role=RoleName.teacher, institution=inst)
    r = await client.post("/auth/login", json={"email": "t@example.com", "password": "Password123!"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    monkeypatch.setattr(get_settings(), "ai_provider", "nvidia")
    monkeypatch.setattr(get_settings(), "nvidia_api_key", "nvapi-secret")
    body = (await client.get("/ai/status", headers=h)).json()
    assert body["provider"] == "nvidia" and body["configured"] is True
    assert "nvapi-secret" not in json.dumps(body)
