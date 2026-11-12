"""Provider-independent interface for pre-exam AI question generation.

AI is NEVER invoked during a student's timed exam — only to pre-generate pools
that humans review before use. Providers return raw candidate dicts; the
generation service validates every field and answer key before storing.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class GenerationSpec:
    question_type: str
    count: int
    difficulty: str = "medium"
    subject: str | None = None
    topics: list[str] = field(default_factory=list)
    grade: str | None = None
    # A seed makes mock/testable generation deterministic.
    seed: int | None = None


@dataclass
class GenerationResult:
    candidates: list[dict]
    model: str
    usage: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Generic provider failure (network, server, timeout)."""


class ProviderTimeout(ProviderError):
    """The provider did not respond within the allotted time."""


class ProviderNotConfigured(ProviderError):
    """The provider is selected but missing required configuration (e.g. key)."""


class ProviderAuthError(ProviderError):
    """Permanent rejection (bad key, unavailable model, invalid request).
    Retrying cannot help, so callers fail fast and surface the message."""


class QuestionProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        """Return candidate question dicts. Must not raise on empty results;
        raise ProviderError subclasses for genuine failures."""
        raise NotImplementedError
