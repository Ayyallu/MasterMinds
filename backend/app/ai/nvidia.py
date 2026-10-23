"""NVIDIA NIM provider adapter.

Inert until NVIDIA_API_KEY is configured. Only syllabus/topic/type/difficulty
metadata is ever sent — never student personal data. Secrets and full prompts
are never logged.
"""
from __future__ import annotations

import json

import httpx

from app.ai.base import (
    GenerationResult,
    GenerationSpec,
    ProviderError,
    ProviderNotConfigured,
    ProviderTimeout,
    QuestionProvider,
)
from app.config import get_settings

_settings = get_settings()

_SYSTEM = (
    "You generate exam questions as strict JSON. Return an object "
    '{"questions": [...]} where each item has: type (single_mcq|multi_mcq|'
    "true_false|numerical), text, options (list of {text, is_correct}) for "
    "option types, numerical_answer and numerical_tolerance for numerical, "
    "difficulty, marks. Return ONLY JSON."
)


class NvidiaNimProvider(QuestionProvider):
    name = "nvidia"

    def __init__(self) -> None:
        if not _settings.nvidia_api_key:
            raise ProviderNotConfigured("NVIDIA_API_KEY is not configured")

    def _prompt(self, spec: GenerationSpec) -> str:
        return (
            f"Generate {spec.count} {spec.difficulty} '{spec.question_type}' "
            f"questions for subject '{spec.subject or 'general'}', topics "
            f"{spec.topics or ['general']}, grade '{spec.grade or 'n/a'}'. "
            "Do not include any personal data."
        )

    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        payload = {
            "model": _settings.nvidia_model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": self._prompt(spec)},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {_settings.nvidia_api_key}"}
        try:
            async with httpx.AsyncClient(
                timeout=_settings.ai_request_timeout_seconds
            ) as client:
                resp = await client.post(
                    f"{_settings.nvidia_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("NVIDIA NIM request timed out") from exc
        except httpx.HTTPError as exc:
            # Never include the key or full prompt in the error surface.
            raise ProviderError(f"NVIDIA NIM request failed: {type(exc).__name__}")

        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            candidates = parsed.get("questions", [])
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ProviderError("NVIDIA NIM returned malformed output") from exc

        usage = data.get("usage", {})
        return GenerationResult(
            candidates=candidates, model=_settings.nvidia_model, usage=usage
        )
