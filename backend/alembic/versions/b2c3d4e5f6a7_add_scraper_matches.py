"""add scraper_matches table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-16 14:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scraper_matches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scraper_id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_scraper_matches_listing_id_listings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scraper_id"],
            ["scrapers.id"],
            name=op.f("fk_scraper_matches_scraper_id_scrapers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scraper_matches")),
        sa.UniqueConstraint(
            "scraper_id",
            "listing_id",
            name="uq_scraper_matches_scraper_listing",
        ),
    )
    op.create_index(
        op.f("ix_scraper_matches_listing_id"),
        "scraper_matches",
        ["listing_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scraper_matches_scraper_id"),
        "scraper_matches",
        ["scraper_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scraper_matches_scraper_id"), table_name="scraper_matches")
    op.drop_index(op.f("ix_scraper_matches_listing_id"), table_name="scraper_matches")
    op.drop_table("scraper_matches")
