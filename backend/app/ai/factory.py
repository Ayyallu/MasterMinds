"""Provider selection. Defaults to the deterministic mock provider."""
from __future__ import annotations

from app.ai.base import ProviderNotConfigured, QuestionProvider
from app.ai.mock import MockProvider
from app.config import get_settings


def get_provider() -> QuestionProvider:
    settings = get_settings()
    if settings.ai_provider == "nvidia":
        # Imported lazily so the mock path needs no httpx/network at all.
        from app.ai.nvidia import NvidiaNimProvider

        return NvidiaNimProvider()
    if settings.ai_provider == "mock":
        return MockProvider()
    raise ProviderNotConfigured(f"Unknown AI provider: {settings.ai_provider}")
