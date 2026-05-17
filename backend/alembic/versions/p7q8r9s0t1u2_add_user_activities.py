"""add user_activities table

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, None] = "o6p7q8r9s0t1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_activities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activities_user_id", "user_activities", ["user_id"], unique=False)
    op.create_index(
        "ix_user_activities_telegram_chat_id",
        "user_activities",
        ["telegram_chat_id"],
        unique=False,
    )
    op.create_index("ix_user_activities_kind", "user_activities", ["kind"], unique=False)
    op.create_index("ix_user_activities_created_at", "user_activities", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_activities_created_at", table_name="user_activities")
    op.drop_index("ix_user_activities_kind", table_name="user_activities")
    op.drop_index("ix_user_activities_telegram_chat_id", table_name="user_activities")
    op.drop_index("ix_user_activities_user_id", table_name="user_activities")
    op.drop_table("user_activities")
