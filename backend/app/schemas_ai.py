"""Schemas for Phase 5 AI generation."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import Difficulty, QuestionType


class GenerationRequest(BaseModel):
    question_type: QuestionType
    count: int = Field(ge=1, le=200)
    difficulty: Difficulty = Difficulty.medium
    subject: str | None = None
    topics: list[str] = Field(default_factory=list)
    grade: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=64)


class GenerationJobOut(BaseModel):
    id: int
    status: str
    provider: str
    model: str | None
    is_global: bool
    requested_count: int
    stored_count: int
    rejected_count: int
    duplicate_count: int
    error: str | None
    usage: dict | None
