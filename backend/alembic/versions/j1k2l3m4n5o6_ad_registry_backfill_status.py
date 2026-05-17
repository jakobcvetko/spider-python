"""add backfill_started_at to bolha_ads and avtonet_ads

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
"""

from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bolha_ads",
        sa.Column("backfill_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "avtonet_ads",
        sa.Column("backfill_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("avtonet_ads", "backfill_started_at")
    op.drop_column("bolha_ads", "backfill_started_at")
