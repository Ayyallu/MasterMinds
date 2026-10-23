"""Schemas for Phase 4 syllabus & question bank, incl. validation rules."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models import Difficulty, QuestionType


# --- Syllabus ---
class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    course_id: int | None = None
    grade_level_id: int | None = None
    term_id: int | None = None
    parent_id: int | None = None


class ObjectiveCreate(BaseModel):
    topic_id: int
    description: str = Field(min_length=1, max_length=1000)
    code: str | None = Field(default=None, max_length=64)


# --- Questions ---
class OptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False


class QuestionCreate(BaseModel):
    type: QuestionType
    text: str = Field(min_length=1, max_length=4000)
    explanation: str | None = Field(default=None, max_length=4000)
    difficulty: Difficulty = Difficulty.medium
    marks: int = Field(default=1, ge=1)
    course_id: int | None = None
    topic_id: int | None = None
    objective_id: int | None = None
    grade_level_id: int | None = None
    term_id: int | None = None
    source: str | None = Field(default=None, max_length=255)

    options: list[OptionIn] = Field(default_factory=list)
    numerical_answer: str | None = None
    numerical_tolerance: str | None = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> "QuestionCreate":
        t = self.type
        if t == QuestionType.numerical:
            if self.options:
                raise ValueError("Numerical questions must not have options")
            if self.numerical_answer is None:
                raise ValueError("Numerical questions require numerical_answer")
            _ensure_float(self.numerical_answer, "numerical_answer")
            if self.numerical_tolerance is not None:
                _ensure_float(self.numerical_tolerance, "numerical_tolerance")
            return self

        # Option-based types.
        if self.numerical_answer is not None:
            raise ValueError("Only numerical questions use numerical_answer")

        texts = [o.text.strip().lower() for o in self.options]
        if len(texts) != len(set(texts)):
            raise ValueError("Option texts must be unique")
        correct = [o for o in self.options if o.is_correct]

        if t == QuestionType.true_false:
            labels = {o.text.strip().lower() for o in self.options}
            if labels != {"true", "false"}:
                raise ValueError("True/False must have exactly 'True' and 'False' options")
            if len(correct) != 1:
                raise ValueError("True/False must have exactly one correct option")
        elif t == QuestionType.single_mcq:
            if len(self.options) < 2:
                raise ValueError("Single-answer MCQ needs at least two options")
            if len(correct) != 1:
                raise ValueError("Single-answer MCQ must have exactly one correct option")
        elif t == QuestionType.multi_mcq:
            if len(self.options) < 2:
                raise ValueError("Multi-select MCQ needs at least two options")
            if len(correct) < 1:
                raise ValueError("Multi-select MCQ needs at least one correct option")
        return self


def _ensure_float(value: str, field: str) -> None:
    try:
        float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")


class OptionOut(BaseModel):
    id: int
    text: str
    order_index: int
    is_correct: bool | None = None  # present for staff, stripped for students


class QuestionVersionOut(BaseModel):
    question_id: int
    version_id: int
    version_no: int
    type: str
    text: str
    explanation: str | None
    difficulty: str
    marks: int
    status: str
    options: list[OptionOut]
    numerical_answer: str | None = None
    numerical_tolerance: str | None = None


class QuestionSearch(BaseModel):
    course_id: int | None = None
    grade_level_id: int | None = None
    term_id: int | None = None
    topic_id: int | None = None
    objective_id: int | None = None
    type: QuestionType | None = None
    difficulty: Difficulty | None = None
    status: str | None = None
