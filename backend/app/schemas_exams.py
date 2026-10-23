"""Schemas for Phase 6 exam authoring, blueprint and approval."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import QuestionType, ResultReleaseRule, Difficulty


class DistributionRule(BaseModel):
    count: int = Field(ge=1)
    type: QuestionType | None = None
    difficulty: Difficulty | None = None
    topic_id: int | None = None


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    course_id: int | None = None
    grade_level_id: int | None = None
    term_id: int | None = None
    class_group_id: int | None = None
    duration_minutes: int = Field(default=60, ge=1)
    attempt_limit: int = Field(default=1, ge=1)
    distribution: list[DistributionRule] = Field(default_factory=list)
    randomize: bool = True
    late_entry_minutes: int = Field(default=0, ge=0)
    negative_marking: bool = False
    result_release_rule: ResultReleaseRule = ResultReleaseRule.manual
    timezone: str = "UTC"
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def _check_schedule(self) -> "ExamCreate":
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ScheduleIn(BaseModel):
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"

    @model_validator(mode="after")
    def _check(self) -> "ScheduleIn":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ExamOut(BaseModel):
    id: int
    title: str
    status: str
    num_questions: int
    duration_minutes: int
    attempt_limit: int
    randomize: bool
    result_release_rule: str
    frozen: bool
    start_at: datetime | None
    end_at: datetime | None
    timezone: str
