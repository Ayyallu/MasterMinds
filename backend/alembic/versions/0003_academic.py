"""academic: institutions onboarding and academic structure

Revision ID: 0003_academic
Revises: 0002_auth
Create Date: 2026-10-23

Additive migration — Phase 3 tables only. No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_academic"
down_revision: Union[str, None] = "0002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institution_registration_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_name", sa.String(length=255), nullable=False),
        sa.Column("requested_code", sa.String(length=64), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_institution_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_institution_id"], ["institutions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_reg_requests_status",
        "institution_registration_requests",
        ["status"],
    )

    op.create_table(
        "academic_years",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("institution_id", "name", name="uq_academic_year_name"),
    )
    op.create_index("ix_academic_years_inst", "academic_years", ["institution_id"])

    op.create_table(
        "terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("academic_year_id", "name", name="uq_term_name"),
    )
    op.create_index("ix_terms_inst", "terms", ["institution_id"])
    op.create_index("ix_terms_year", "terms", ["academic_year_id"])

    op.create_table(
        "grade_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("institution_id", "name", name="uq_grade_level_name"),
    )
    op.create_index("ix_grade_levels_inst", "grade_levels", ["institution_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("institution_id", "name", name="uq_department_name"),
    )
    op.create_index("ix_departments_inst", "departments", ["institution_id"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("institution_id", "code", name="uq_course_code"),
    )
    op.create_index("ix_courses_inst", "courses", ["institution_id"])

    op.create_table(
        "class_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("grade_level_id", sa.Integer(), nullable=True),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grade_level_id"], ["grade_levels.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("institution_id", "name", name="uq_class_group_name"),
    )
    op.create_index("ix_class_groups_inst", "class_groups", ["institution_id"])

    op.create_table(
        "teacher_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), nullable=False),
        sa.Column("class_group_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["teacher_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["class_group_id"], ["class_groups.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "teacher_user_id", "class_group_id", name="uq_teacher_assignment"
        ),
    )
    op.create_index(
        "ix_teacher_assign_inst", "teacher_assignments", ["institution_id"]
    )
    op.create_index(
        "ix_teacher_assign_teacher", "teacher_assignments", ["teacher_user_id"]
    )
    op.create_index(
        "ix_teacher_assign_class", "teacher_assignments", ["class_group_id"]
    )

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("student_user_id", sa.Integer(), nullable=False),
        sa.Column("class_group_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["class_group_id"], ["class_groups.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_enrollments_inst", "enrollments", ["institution_id"])
    op.create_index("ix_enrollments_student", "enrollments", ["student_user_id"])
    op.create_index("ix_enrollments_class", "enrollments", ["class_group_id"])
    op.create_index("ix_enrollments_status", "enrollments", ["status"])

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("register_number", sa.String(length=64), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("accepted_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("token_hash", name="uq_invitation_token_hash"),
    )
    op.create_index("ix_invitations_inst", "invitations", ["institution_id"])
    op.create_index("ix_invitations_status", "invitations", ["status"])
    op.create_index("ix_invitations_token", "invitations", ["token_hash"])

    op.create_table(
        "roster_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_roster_imports_inst", "roster_imports", ["institution_id"])


def downgrade() -> None:
    op.drop_table("roster_imports")
    op.drop_table("invitations")
    op.drop_table("enrollments")
    op.drop_table("teacher_assignments")
    op.drop_table("class_groups")
    op.drop_table("courses")
    op.drop_table("departments")
    op.drop_table("grade_levels")
    op.drop_table("terms")
    op.drop_table("academic_years")
    op.drop_table("institution_registration_requests")
