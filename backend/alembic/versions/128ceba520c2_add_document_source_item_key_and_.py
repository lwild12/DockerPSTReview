"""add document source item key and content changed at

Revision ID: 128ceba520c2
Revises: f59ad4034667
Create Date: 2026-09-11 07:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "128ceba520c2"
down_revision: str | None = "f59ad4034667"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_item_key", sa.String(500), nullable=False, server_default=""),
    )
    op.alter_column("documents", "source_item_key", server_default=None)
    op.create_index("ix_documents_source_item_key", "documents", ["source_item_key"])
    op.add_column(
        "documents",
        sa.Column("content_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "content_changed_at")
    op.drop_index("ix_documents_source_item_key", table_name="documents")
    op.drop_column("documents", "source_item_key")
