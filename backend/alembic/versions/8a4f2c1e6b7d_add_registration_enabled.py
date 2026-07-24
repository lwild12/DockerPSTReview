"""add registration_enabled to system_settings

Revision ID: 8a4f2c1e6b7d
Revises: 2d6c8a1f9b34
Create Date: 2026-07-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a4f2c1e6b7d'
down_revision: Union[str, None] = '2d6c8a1f9b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("registration_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("system_settings", "registration_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("system_settings", "registration_enabled")
