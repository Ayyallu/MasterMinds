"""Schemas for Phase 8 scoring and results."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CorrectionIn(BaseModel):
    awarded_marks: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)
