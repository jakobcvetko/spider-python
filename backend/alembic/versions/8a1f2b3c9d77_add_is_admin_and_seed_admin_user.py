"""add is_admin to users and seed default admin user

Revision ID: 8a1f2b3c9d77
Revises: 983c4c2c644b
Create Date: 2026-05-16 00:05:00.000000

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.security import hash_password

# revision identifiers, used by Alembic.
revision: str = "8a1f2b3c9d77"
down_revision: Union[str, Sequence[str], None] = "983c4c2c644b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "password"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    bind = op.get_bind()

    existing = bind.execute(
        sa.text("SELECT id, is_admin FROM users WHERE email = :email"),
        {"email": DEFAULT_ADMIN_EMAIL},
    ).first()

    if existing is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO users (id, email, password_hash, display_name, is_admin)
                VALUES (:id, :email, :password_hash, :display_name, true)
                """
            ),
            {
                "id": uuid.uuid4(),
                "email": DEFAULT_ADMIN_EMAIL,
                "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
                "display_name": "Admin",
            },
        )
    elif not existing.is_admin:
        bind.execute(
            sa.text("UPDATE users SET is_admin = true WHERE email = :email"),
            {"email": DEFAULT_ADMIN_EMAIL},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_admin")
