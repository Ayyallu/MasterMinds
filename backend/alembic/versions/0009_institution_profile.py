"""institution profile: type, contacts, address, time zone, logo

Revision ID: 0009_institution_profile
Revises: 0008_scoring
Create Date: 2026-11-12

Additive migration — new nullable profile columns on `institutions`
(time_zone defaults to 'UTC'). No existing data is modified.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_institution_profile"
down_revision: Union[str, None] = "0008_scoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("institution_type", sa.String(32), nullable=True),
    sa.Column("affiliation", sa.String(255), nullable=True),
    sa.Column("established_year", sa.Integer(), nullable=True),
    sa.Column("head_name", sa.String(255), nullable=True),
    sa.Column("email", sa.String(320), nullable=True),
    sa.Column("phone", sa.String(32), nullable=True),
    sa.Column("website", sa.String(255), nullable=True),
    sa.Column("address_line1", sa.String(255), nullable=True),
    sa.Column("address_line2", sa.String(255), nullable=True),
    sa.Column("city", sa.String(128), nullable=True),
    sa.Column("state", sa.String(128), nullable=True),
    sa.Column("postal_code", sa.String(32), nullable=True),
    sa.Column("country", sa.String(128), nullable=True),
    sa.Column("time_zone", sa.String(64), nullable=False, server_default="UTC"),
    sa.Column("logo_data", sa.LargeBinary(), nullable=True),
    sa.Column("logo_content_type", sa.String(64), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column("institutions", col)


def downgrade() -> None:
    for col in reversed(_COLUMNS):
        op.drop_column("institutions", col.name)
