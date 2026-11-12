"""Check the configured AI provider end-to-end (key, model, JSON output).

Run from backend/:  python -m scripts.check_ai
Uses the same settings as the app (backend/.env). Never prints the key.
"""
from __future__ import annotations

import asyncio
import sys

from app.ai.base import GenerationSpec, ProviderError
from app.ai.factory import get_provider
from app.config import get_settings
from app.schemas_questions import QuestionCreate


async def main() -> int:
    s = get_settings()
    print(f"AI_PROVIDER   = {s.ai_provider}")
    if s.ai_provider == "nvidia":
        key = s.nvidia_api_key.strip()
        print(f"NVIDIA_MODEL  = {s.nvidia_model}")
        print(f"NVIDIA_API_KEY= {'set (' + str(len(key)) + ' chars, ' + key[:6] + '…)' if key else 'NOT SET'}")
    try:
        provider = get_provider()
        result = await provider.generate(
            GenerationSpec(question_type="single_mcq", count=2, difficulty="easy",
                           subject="Mathematics", topics=["Fractions"], grade="Grade 6")
        )
    except ProviderError as exc:
        print(f"\nFAILED: {exc}")
        return 1
    ok = 0
    for c in result.candidates:
        try:
            QuestionCreate(**c)
            ok += 1
            print(f"  ✓ {c['text'][:90]}")
        except Exception as exc:  # noqa: BLE001 - diagnostic output only
            print(f"  ✗ rejected by validation: {type(exc).__name__}")
    print(f"\nOK: {ok}/{len(result.candidates)} valid questions from {result.model}; usage={result.usage}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
