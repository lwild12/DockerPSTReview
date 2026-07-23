"""add system_settings singleton table

Revision ID: 7b2e9f4c1a08
Revises: 4f1c8a2d6e93
Create Date: 2026-07-23 13:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '7b2e9f4c1a08'
down_revision: Union[str, None] = '4f1c8a2d6e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("enable_api_docs", sa.Boolean(), nullable=False),
        sa.Column("cookie_secure", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # Seed the single row from whatever the deploy's current env vars say, so
    # upgrading never silently flips a running install's effective settings.
    env = get_settings()
    op.execute(
        sa.text(
            "INSERT INTO system_settings (id, enable_api_docs, cookie_secure) "
            "VALUES (:id, :enable_api_docs, :cookie_secure)"
        ).bindparams(
            id=str(uuid.uuid4()),
            enable_api_docs=env.enable_api_docs,
            cookie_secure=env.cookie_secure,
        )
    )


def downgrade() -> None:
    op.drop_table("system_settings")
