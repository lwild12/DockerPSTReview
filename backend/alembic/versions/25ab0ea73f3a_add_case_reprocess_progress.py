"""add case reprocess progress

Revision ID: 25ab0ea73f3a
Revises: 2c32de2a06ee
Create Date: 2026-09-11 08:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25ab0ea73f3a"
down_revision: str | None = "2c32de2a06ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column(
            "reprocess_progress",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("cases", "reprocess_progress", server_default=None)


def downgrade() -> None:
    op.drop_column("cases", "reprocess_progress")
