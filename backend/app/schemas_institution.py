"""Schemas for the institution profile (Super Admin create/edit, member view)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

InstitutionType = Literal["school", "college", "university", "other"]

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")
_PHONE_RE = re.compile(r"^[0-9+()\-.\s]{6,32}$")


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class InstitutionProfileIn(BaseModel):
    """Editable profile fields. Required ones are the 'basic information'
    every school/college must provide when a Super Admin creates it."""

    name: str = Field(min_length=2, max_length=255)
    institution_type: InstitutionType
    affiliation: str | None = Field(default=None, max_length=255)
    established_year: int | None = None
    head_name: str | None = Field(default=None, max_length=255)
    email: EmailStr
    phone: str = Field(max_length=32)
    website: str | None = Field(default=None, max_length=255)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=128)
    postal_code: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=1, max_length=128)
    time_zone: str = Field(default="UTC", max_length=64)

    _strip = field_validator(
        "affiliation", "head_name", "website", "address_line2", mode="before"
    )(_blank_to_none)

    @field_validator("name", "address_line1", "city", "state", "postal_code", "country", mode="before")
    @classmethod
    def _strip_required(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = v.strip()
        if not _PHONE_RE.match(v):
            raise ValueError("Enter a valid phone number")
        return v

    @field_validator("website")
    @classmethod
    def _website(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^https?://", v, re.I):
            v = "https://" + v
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", v, re.I):
            raise ValueError("Enter a valid website URL")
        return v

    @field_validator("established_year")
    @classmethod
    def _year(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not 1000 <= v <= datetime.now(timezone.utc).year:
            raise ValueError("Enter a valid year")
        return v

    @field_validator("time_zone")
    @classmethod
    def _tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown time zone")
        return v


class InstitutionCreate(InstitutionProfileIn):
    """Super Admin creates an institution directly, with its first admin."""

    code: str = Field(min_length=2, max_length=64)
    admin_full_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_password: str | None = Field(default=None, min_length=8)

    @field_validator("code", mode="before")
    @classmethod
    def _code(cls, v):
        v = (v or "").strip().upper()
        if not _CODE_RE.match(v):
            raise ValueError(
                "Code must be 2-64 characters: letters, digits, '-' or '_'"
            )
        return v


class InstitutionProfileOut(BaseModel):
    id: int
    name: str
    code: str
    status: str
    institution_type: str | None
    affiliation: str | None
    established_year: int | None
    head_name: str | None
    email: str | None
    phone: str | None
    website: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    time_zone: str
    has_logo: bool
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def of(cls, inst) -> "InstitutionProfileOut":
        return cls(
            **{
                f: getattr(inst, f)
                for f in cls.model_fields
                if f != "has_logo"
            },
            has_logo=inst.logo_data is not None,
        )
