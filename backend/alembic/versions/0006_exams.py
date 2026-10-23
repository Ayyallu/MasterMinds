"""exams: authoring, blueprint, lifecycle, pinned questions

Revision ID: 0006_exams
Revises: 0005_ai
Create Date: 2026-10-23

Additive migration — Phase 6 tables only. No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_exams"
down_revision: Union[str, None] = "0005_ai"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("grade_level_id", sa.Integer(), nullable=True),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("class_group_id", sa.Integer(), nullable=True),
        sa.Column("num_questions", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("attempt_limit", sa.Integer(), nullable=False),
        sa.Column("distribution", sa.JSON(), nullable=True),
        sa.Column("randomize", sa.Boolean(), nullable=False),
        sa.Column("late_entry_minutes", sa.Integer(), nullable=False),
        sa.Column("negative_marking", sa.Boolean(), nullable=False),
        sa.Column("result_release_rule", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        sa.Column("frozen_snapshot", sa.JSON(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["grade_level_id"], ["grade_levels.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["class_group_id"], ["class_groups.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_exams_inst", "exams", ["institution_id"])
    op.create_index("ix_exams_status", "exams", ["status"])

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("question_version_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "exam_id", "question_version_id", name="uq_exam_question_version"
        ),
    )
    op.create_index("ix_exam_questions_exam", "exam_questions", ["exam_id"])


def downgrade() -> None:
    op.drop_table("exam_questions")
    op.drop_table("exams")
