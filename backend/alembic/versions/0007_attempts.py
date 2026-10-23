"""attempts: student exam delivery engine

Revision ID: 0007_attempts
Revises: 0006_exams
Create Date: 2026-10-23

Additive migration — Phase 7 tables only. No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_attempts"
down_revision: Union[str, None] = "0006_exams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("student_user_id", sa.Integer(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_submitted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "exam_id", "student_user_id", "attempt_no", name="uq_attempt_no"
        ),
    )
    op.create_index("ix_attempts_exam", "exam_attempts", ["exam_id"])
    op.create_index("ix_attempts_student", "exam_attempts", ["student_user_id"])
    op.create_index("ix_attempts_status", "exam_attempts", ["status"])
    op.create_index("ix_attempts_inst", "exam_attempts", ["institution_id"])

    op.create_table(
        "attempt_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_version_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("answer_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "attempt_id", "question_version_id", name="uq_attempt_answer"
        ),
    )
    op.create_index("ix_attempt_answers_attempt", "attempt_answers", ["attempt_id"])


def downgrade() -> None:
    op.drop_table("attempt_answers")
    op.drop_table("exam_attempts")
