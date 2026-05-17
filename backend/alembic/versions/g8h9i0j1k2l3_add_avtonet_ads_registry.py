"""add avtonet_ads registry and scrape meta

Revision ID: g8h9i0j1k2l3
Revises: f2a3b4c5d6e7
Create Date: 2026-05-17 10:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avtonet_ads",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "scrape_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
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
        sa.PrimaryKeyConstraint("ad_id", name="pk_avtonet_ads"),
    )
    op.create_index("ix_avtonet_ads_status", "avtonet_ads", ["status"], unique=False)

    op.create_table(
        "avtonet_scrape_meta",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("last_working_ad_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_working_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_batch_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_avtonet_scrape_meta"),
    )
    op.execute(
        sa.text(
            "INSERT INTO avtonet_scrape_meta (id, last_working_ad_id) VALUES (1, 0)"
        )
    )


def downgrade() -> None:
    op.drop_table("avtonet_scrape_meta")
    op.drop_index("ix_avtonet_ads_status", table_name="avtonet_ads")
    op.drop_table("avtonet_ads")
