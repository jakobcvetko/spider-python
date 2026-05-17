"""avtonet progressive pipeline tables (mirror bolha)

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
"""

from alembic import op
import sqlalchemy as sa

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "avtonet_ad_states",
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
        sa.PrimaryKeyConstraint("ad_id", name="pk_avtonet_ad_states"),
    )
    op.create_index("ix_avtonet_ad_states_status", "avtonet_ad_states", ["status"])

    op.create_table(
        "avtonet_ad_probes",
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("gtm_ad_status", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ad_id", name="pk_avtonet_ad_probes"),
    )

    op.create_table(
        "avtonet_inactive_ads",
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
        sa.PrimaryKeyConstraint("ad_id", name="pk_avtonet_inactive_ads"),
    )

    op.add_column(
        "avtonet_scrape_meta",
        sa.Column("last_homepage_max", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "avtonet_scrape_meta",
        sa.Column("last_homepage_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "avtonet_scrape_meta",
        sa.Column("last_fetch_high_water", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "avtonet_scrape_meta",
        sa.Column("last_fetch_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("avtonet_scrape_meta", "last_fetch_started_at")
    op.drop_column("avtonet_scrape_meta", "last_fetch_high_water")
    op.drop_column("avtonet_scrape_meta", "last_homepage_fetched_at")
    op.drop_column("avtonet_scrape_meta", "last_homepage_max")
    op.drop_table("avtonet_inactive_ads")
    op.drop_table("avtonet_ad_probes")
    op.drop_table("avtonet_ad_states")
