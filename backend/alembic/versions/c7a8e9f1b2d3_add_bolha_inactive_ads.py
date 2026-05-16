"""add bolha_inactive_ads for progressive scrape

Revision ID: c7a8e9f1b2d3
Revises: 8a1f2b3c9d77
Create Date: 2026-05-16 01:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a8e9f1b2d3"
down_revision: Union[str, Sequence[str], None] = "8a1f2b3c9d77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bolha_inactive_ads",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("first_inactive_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("ad_id", name="pk_bolha_inactive_ads"),
    )


def downgrade() -> None:
    op.drop_table("bolha_inactive_ads")
