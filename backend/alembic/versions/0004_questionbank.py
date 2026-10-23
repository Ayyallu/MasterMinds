"""question bank: syllabus, objectives, documents, questions

Revision ID: 0004_questionbank
Revises: 0003_academic
Create Date: 2026-10-23

Additive migration — Phase 4 tables only. No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_questionbank"
down_revision: Union[str, None] = "0003_academic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "syllabus_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("grade_level_id", sa.Integer(), nullable=True),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["grade_level_id"], ["grade_levels.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["syllabus_topics.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "institution_id", "name", "parent_id", name="uq_topic_name"
        ),
    )
    op.create_index("ix_topics_inst", "syllabus_topics", ["institution_id"])

    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["syllabus_topics.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_objectives_inst", "learning_objectives", ["institution_id"])
    op.create_index("ix_objectives_topic", "learning_objectives", ["topic_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_documents_inst", "documents", ["institution_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("withdrawn", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_questions_inst", "questions", ["institution_id"])

    op.create_table(
        "question_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.Column("explanation", sa.String(length=4000), nullable=True),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("objective_id", sa.Integer(), nullable=True),
        sa.Column("grade_level_id", sa.Integer(), nullable=True),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Column("numerical_answer", sa.String(length=64), nullable=True),
        sa.Column("numerical_tolerance", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["syllabus_topics.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["learning_objectives.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["grade_level_id"], ["grade_levels.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "question_id", "version_no", name="uq_question_version_no"
        ),
    )
    op.create_index("ix_qversions_question", "question_versions", ["question_id"])
    op.create_index("ix_qversions_topic", "question_versions", ["topic_id"])
    op.create_index("ix_qversions_status", "question_versions", ["status"])

    op.create_table(
        "question_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_version_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_options_version", "question_options", ["question_version_id"]
    )


def downgrade() -> None:
    op.drop_table("question_options")
    op.drop_table("question_versions")
    op.drop_table("questions")
    op.drop_table("documents")
    op.drop_table("learning_objectives")
    op.drop_table("syllabus_topics")
