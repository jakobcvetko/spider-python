"""add telegram integration tables and user columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-17 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("telegram_username", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_notifications_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_users_telegram_chat_id",
        "users",
        ["telegram_chat_id"],
        unique=True,
    )

    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_link_tokens_user_id",
        "telegram_link_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_link_tokens_token",
        "telegram_link_tokens",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_telegram_link_tokens_expires_at",
        "telegram_link_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_link_tokens_expires_at", table_name="telegram_link_tokens")
    op.drop_index("ix_telegram_link_tokens_token", table_name="telegram_link_tokens")
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
    op.drop_index("ix_users_telegram_chat_id", table_name="users")
    op.drop_column("users", "telegram_notifications_enabled")
    op.drop_column("users", "telegram_linked_at")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_chat_id")
