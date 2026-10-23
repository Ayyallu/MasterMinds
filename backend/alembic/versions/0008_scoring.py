"""scoring: attempt scores, history, result release

Revision ID: 0008_scoring
Revises: 0007_attempts
Create Date: 2026-10-23

Additive migration — Phase 8 tables and result-release columns on exams.
No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_scoring"
down_revision: Union[str, None] = "0007_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column(
            "results_published", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "exams", sa.Column("results_published_by_user_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "exams",
        sa.Column("results_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_exams_results_publisher",
        "exams",
        "users",
        ["results_published_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Drop the server_default now that existing rows are backfilled.
    op.alter_column("exams", "results_published", server_default=None)

    op.create_table(
        "attempt_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("student_user_id", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("awarded_marks", sa.Integer(), nullable=False),
        sa.Column("score_version", sa.Integer(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("scored_by_user_id", sa.Integer(), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scored_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("attempt_id", name="uq_attempt_score"),
    )
    op.create_index("ix_attempt_scores_exam", "attempt_scores", ["exam_id"])
    op.create_index("ix_attempt_scores_inst", "attempt_scores", ["institution_id"])
    op.create_index(
        "ix_attempt_scores_student", "attempt_scores", ["student_user_id"]
    )

    op.create_table(
        "score_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("score_version", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("awarded_marks", sa.Integer(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("scored_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scored_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_score_history_attempt", "score_history", ["attempt_id"])


def downgrade() -> None:
    op.drop_table("score_history")
    op.drop_table("attempt_scores")
    op.drop_constraint("fk_exams_results_publisher", "exams", type_="foreignkey")
    op.drop_column("exams", "results_published_at")
    op.drop_column("exams", "results_published_by_user_id")
    op.drop_column("exams", "results_published")
