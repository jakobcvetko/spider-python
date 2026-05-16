"""add bolha_ad_states pipeline table

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c0
Create Date: 2026-05-16 03:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bolha_ad_states",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_lookahead_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_fallback_scrape_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fallback_scrape_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome", sa.String(length=64), nullable=True),
        sa.Column("last_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ad_id", name="pk_bolha_ad_states"),
    )
    op.create_index("ix_bolha_ad_states_status", "bolha_ad_states", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bolha_ad_states_status", table_name="bolha_ad_states")
    op.drop_table("bolha_ad_states")
