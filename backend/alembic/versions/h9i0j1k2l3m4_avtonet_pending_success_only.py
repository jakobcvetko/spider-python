"""avtonet_ads: map legacy removed status to pending."""

from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE avtonet_ads
        SET status = 'pending'
        WHERE status = 'removed'
        """
    )


def downgrade() -> None:
    pass
