"""add search_tokens and title_normalized

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

from app.search_normalize import normalize_text, tokenize_scraper_name

revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_search_columns(connection: sa.Connection) -> None:
    scrapers = connection.execute(sa.text("SELECT id, name FROM scrapers")).fetchall()
    for row in scrapers:
        tokens = tokenize_scraper_name(row.name)
        connection.execute(
            sa.text("UPDATE scrapers SET search_tokens = :tokens WHERE id = :id"),
            {"tokens": tokens, "id": row.id},
        )

    listings = connection.execute(sa.text("SELECT id, title FROM listings")).fetchall()
    for row in listings:
        connection.execute(
            sa.text("UPDATE listings SET title_normalized = :norm WHERE id = :id"),
            {"norm": normalize_text(row.title), "id": row.id},
        )


def upgrade() -> None:
    op.add_column(
        "scrapers",
        sa.Column("search_tokens", ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "listings",
        sa.Column("title_normalized", sa.Text(), nullable=True),
    )

    _backfill_search_columns(op.get_bind())

    op.alter_column(
        "scrapers",
        "search_tokens",
        nullable=False,
        server_default=sa.text("'{}'::text[]"),
    )
    op.alter_column(
        "listings",
        "title_normalized",
        nullable=False,
        server_default=sa.text("''"),
    )


def downgrade() -> None:
    op.drop_column("listings", "title_normalized")
    op.drop_column("scrapers", "search_tokens")
