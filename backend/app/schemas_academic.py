"""Pydantic schemas for Phase 3 institution & academic administration."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field


# --- Institution onboarding ---
class RegistrationCreate(BaseModel):
    institution_name: str = Field(min_length=1, max_length=255)
    requested_code: str = Field(min_length=2, max_length=64)
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr


class RegistrationOut(BaseModel):
    id: int
    institution_name: str
    requested_code: str
    contact_name: str
    contact_email: str
    status: str


class RegistrationApprove(BaseModel):
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=1, max_length=255)
    admin_password: str | None = Field(default=None, min_length=8)


class RegistrationReject(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class InstitutionOut(BaseModel):
    id: int
    name: str
    code: str
    status: str


# --- Academic structure ---
class AcademicYearCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class TermCreate(BaseModel):
    academic_year_id: int
    name: str = Field(min_length=1, max_length=64)
    sequence: int = 1
    start_date: date | None = None
    end_date: date | None = None


class GradeLevelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: str = "school_grade"
    sequence: int = 1


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    department_id: int | None = None


class ClassGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: str = "class"
    grade_level_id: int | None = None
    term_id: int | None = None
    course_id: int | None = None


class IdNameOut(BaseModel):
    id: int
    name: str


# --- Provisioning ---
class InvitationCreate(BaseModel):
    role: str
    email: EmailStr | None = None
    register_number: str | None = Field(default=None, max_length=64)


class InvitationOut(BaseModel):
    id: int
    role: str
    email: str | None
    status: str


class InvitationAccept(BaseModel):
    token: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class StudentSelfRegister(BaseModel):
    institution_code: str = Field(min_length=1)
    register_number: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    email: EmailStr | None = None


class MembershipApprove(BaseModel):
    user_id: int


class TeacherAssignmentCreate(BaseModel):
    teacher_user_id: int
    class_group_id: int


class EnrollmentCreate(BaseModel):
    student_user_id: int
    class_group_id: int
    term_id: int | None = None


class EnrollmentTransfer(BaseModel):
    enrollment_id: int
    new_class_group_id: int
    term_id: int | None = None


# --- Roster CSV import ---
class RosterRequest(BaseModel):
    csv_text: str = Field(min_length=1)
    class_group_code: str | None = None
    commit: bool = False


class RosterError(BaseModel):
    row: int
    message: str


class RosterResult(BaseModel):
    import_id: int
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[RosterError]
    committed: bool
