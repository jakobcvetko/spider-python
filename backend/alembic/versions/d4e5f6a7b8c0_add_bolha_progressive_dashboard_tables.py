"""add bolha scrape meta and ad probes for admin progressive UI

Revision ID: d4e5f6a7b8c0
Revises: c7a8e9f1b2d3
Create Date: 2026-05-16 02:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c0"
down_revision: Union[str, Sequence[str], None] = "c7a8e9f1b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bolha_scrape_meta",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("last_working_ad_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_working_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_homepage_max", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_homepage_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_high_water", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_fetch_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_bolha_scrape_meta_singleton"),
        sa.PrimaryKeyConstraint("id", name="pk_bolha_scrape_meta"),
    )
    op.execute(
        """
        INSERT INTO bolha_scrape_meta (id, last_working_ad_id, last_homepage_max, last_fetch_high_water)
        VALUES (1, 0, 0, 0)
        """
    )

    op.create_table(
        "bolha_ad_probes",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("gtm_ad_status", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ad_id", name="pk_bolha_ad_probes"),
    )


def downgrade() -> None:
    op.drop_table("bolha_ad_probes")
    op.drop_table("bolha_scrape_meta")
