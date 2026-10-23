"""baseline (empty foundation migration)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-23

Phase 1 establishes the migration chain without any domain tables. Identity,
tenant, exam and related schemas are introduced in later phases.
"""
from typing import Sequence, Union

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
