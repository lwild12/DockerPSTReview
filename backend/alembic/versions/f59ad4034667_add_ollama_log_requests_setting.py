"""add ollama log requests setting

Revision ID: f59ad4034667
Revises: 1ba360c283ba
Create Date: 2026-09-10 16:58:08.239531

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f59ad4034667"
down_revision: str | None = "1ba360c283ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("ollama_log_requests", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.alter_column("system_settings", "ollama_log_requests", server_default=None)


def downgrade() -> None:
    op.drop_column("system_settings", "ollama_log_requests")
