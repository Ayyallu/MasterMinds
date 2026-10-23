"""ai generation: jobs and question provenance

Revision ID: 0005_ai
Revises: 0004_questionbank
Create Date: 2026-10-23

Additive migration — adds generation_jobs and a provenance column on
question_versions. No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ai"
down_revision: Union[str, None] = "0004_questionbank"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("stored_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_generation_idempotency"),
    )
    op.create_index("ix_generation_jobs_inst", "generation_jobs", ["institution_id"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_index(
        "ix_generation_jobs_idem", "generation_jobs", ["idempotency_key"]
    )

    op.add_column(
        "question_versions",
        sa.Column("generation_job_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_qversion_generation_job",
        "question_versions",
        "generation_jobs",
        ["generation_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_qversion_generation_job", "question_versions", type_="foreignkey"
    )
    op.drop_column("question_versions", "generation_job_id")
    op.drop_table("generation_jobs")
