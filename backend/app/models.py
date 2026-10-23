"""SQLAlchemy ORM models for Phase 2: identity, roles, sessions, audit."""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RoleName(str, enum.Enum):
    super_admin = "super_admin"
    institution_admin = "institution_admin"
    teacher = "teacher"
    student = "student"
    central_academic_reviewer = "central_academic_reviewer"


# Platform-level roles are not scoped to an institution.
PLATFORM_ROLES = {RoleName.super_admin, RoleName.central_academic_reviewer}


class InstitutionStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    disabled = "disabled"


class UserStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    disabled = "disabled"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=InstitutionStatus.pending.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Email is globally unique when present; students may instead authenticate
    # with an institution-scoped register number (see InstitutionMembership).
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=UserStatus.active.value, nullable=False
    )
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["InstitutionMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_id", "institution_id", name="uq_user_role_scope"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    # Null for platform-level roles (super admin, central reviewer).
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship()


class InstitutionMembership(Base):
    __tablename__ = "institution_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "institution_id", name="uq_membership_user_inst"),
        UniqueConstraint(
            "institution_id", "register_number", name="uq_membership_register"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    register_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=UserStatus.active.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="memberships")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    # Tokens issued from one login share a family; replay of a rotated token
    # revokes the whole family.
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class GradeKind(str, enum.Enum):
    school_grade = "school_grade"
    college_year = "college_year"


class EnrollmentStatus(str, enum.Enum):
    active = "active"
    transferred = "transferred"
    inactive = "inactive"
    completed = "completed"


class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"
    expired = "expired"


class ImportStatus(str, enum.Enum):
    validated = "validated"
    committed = "committed"
    failed = "failed"


class InstitutionRegistrationRequest(Base):
    __tablename__ = "institution_registration_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_code: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=RequestStatus.pending.value, nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_academic_year_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Term(Base):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "name", name="uq_term_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class GradeLevel(Base):
    __tablename__ = "grade_levels"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_grade_level_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(16), default=GradeKind.school_grade.value, nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_department_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_course_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)


class ClassGroup(Base):
    """A class, section or batch that students enroll into."""

    __tablename__ = "class_groups"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_class_group_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="class", nullable=False)
    grade_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("grade_levels.id", ondelete="SET NULL"), nullable=True
    )
    term_id: Mapped[int | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "teacher_user_id", "class_group_id", name="uq_teacher_assignment"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[int | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=EnrollmentStatus.active.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    register_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=InvitationStatus.pending.value, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RosterImport(Base):
    __tablename__ = "roster_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
