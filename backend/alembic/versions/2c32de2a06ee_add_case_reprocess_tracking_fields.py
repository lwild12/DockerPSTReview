"""add case reprocess tracking fields

Revision ID: 2c32de2a06ee
Revises: 128ceba520c2
Create Date: 2026-09-11 07:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c32de2a06ee"
down_revision: str | None = "128ceba520c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("reprocess_last_run_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("reprocess_last_run_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column(
            "reprocess_last_run_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("cases", "reprocess_last_run_summary", server_default=None)


def downgrade() -> None:
    op.drop_column("cases", "reprocess_last_run_summary")
    op.drop_column("cases", "reprocess_last_run_completed_at")
    op.drop_column("cases", "reprocess_last_run_started_at")
