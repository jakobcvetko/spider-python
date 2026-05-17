"""drop bolha_ad_states, bolha_ad_probes, bolha_inactive_ads

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-05-17

"""

from typing import Sequence, Union

from alembic import op

revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_bolha_ad_states_status", table_name="bolha_ad_states")
    op.drop_table("bolha_ad_states")
    op.drop_table("bolha_ad_probes")
    op.drop_table("bolha_inactive_ads")


def downgrade() -> None:
    import sqlalchemy as sa

    op.create_table(
        "bolha_inactive_ads",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "first_inactive_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
        sa.PrimaryKeyConstraint("ad_id", name="pk_bolha_inactive_ads"),
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
    op.create_table(
        "bolha_ad_states",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_lookahead_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_fallback_scrape_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_fallback_scrape_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
    op.create_index(
        "ix_bolha_ad_states_status",
        "bolha_ad_states",
        ["status"],
        unique=False,
    )
