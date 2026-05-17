"""partial index for bolha_ads / avtonet_ads backfill worker queue

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-05-17

Backfill workers select rows with status = backfill, ad_id < last_working,
ORDER BY ad_id DESC LIMIT n. A partial index keeps the working set small as
the registry grows to millions of pending/empty rows.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, None] = "n5o6p7q8r9s0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_bolha_ads_backfill_queue
        ON bolha_ads (ad_id DESC)
        WHERE status = 'backfill'
        """
    )
    op.execute(
        """
        CREATE INDEX ix_avtonet_ads_backfill_queue
        ON avtonet_ads (ad_id DESC)
        WHERE status = 'backfill'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_avtonet_ads_backfill_queue", table_name="avtonet_ads")
    op.drop_index("ix_bolha_ads_backfill_queue", table_name="bolha_ads")
