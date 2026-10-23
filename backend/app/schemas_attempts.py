"""Schemas for Phase 7 student exam delivery."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AnswerIn(BaseModel):
    selected_option_ids: list[int] | None = None
    numerical_value: str | None = None


class AnswerSaved(BaseModel):
    question_version_id: int
    answer_version: int
    saved: bool = True


class AttemptQuestionOut(BaseModel):
    question_version_id: int
    type: str
    text: str
    marks: int
    options: list[dict]  # {id, text} only — never answer keys
    answer: dict | None = None


class AttemptOut(BaseModel):
    id: int
    exam_id: int
    status: str
    attempt_no: int
    started_at: datetime
    deadline_at: datetime
    submitted_at: datetime | None
    seconds_remaining: int
    questions: list[AttemptQuestionOut]
