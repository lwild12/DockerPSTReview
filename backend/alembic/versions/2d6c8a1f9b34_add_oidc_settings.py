"""add OIDC fields to system_settings

Revision ID: 2d6c8a1f9b34
Revises: 7b2e9f4c1a08
Create Date: 2026-07-23 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d6c8a1f9b34'
down_revision: Union[str, None] = '7b2e9f4c1a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("oidc_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "system_settings",
        sa.Column("oidc_issuer_url", sa.String(500), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("oidc_client_id", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("oidc_client_secret_encrypted", sa.String(2000), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("oidc_display_name", sa.String(100), nullable=False, server_default="SSO"),
    )
    op.alter_column("system_settings", "oidc_enabled", server_default=None)
    op.alter_column("system_settings", "oidc_issuer_url", server_default=None)
    op.alter_column("system_settings", "oidc_client_id", server_default=None)
    op.alter_column("system_settings", "oidc_client_secret_encrypted", server_default=None)
    op.alter_column("system_settings", "oidc_display_name", server_default=None)


def downgrade() -> None:
    op.drop_column("system_settings", "oidc_display_name")
    op.drop_column("system_settings", "oidc_client_secret_encrypted")
    op.drop_column("system_settings", "oidc_client_id")
    op.drop_column("system_settings", "oidc_issuer_url")
    op.drop_column("system_settings", "oidc_enabled")
