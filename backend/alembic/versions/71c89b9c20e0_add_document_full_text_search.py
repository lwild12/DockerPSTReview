"""add document full text search

Revision ID: 71c89b9c20e0
Revises: e6b4acf90a1d
Create Date: 2026-07-23 11:02:55.479721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '71c89b9c20e0'
down_revision: Union[str, None] = 'e6b4acf90a1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "documents",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(sender, '') "
                "|| ' ' || coalesce(body_text, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX ix_documents_search_vector ON documents USING GIN (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_documents_subject_trgm ON documents USING GIN (subject gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_documents_sender_trgm ON documents USING GIN (sender gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_sender_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_subject_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_search_vector")
    op.drop_column("documents", "search_vector")
