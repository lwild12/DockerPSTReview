"""add ocr fields and extend search vector

Revision ID: 110f25f0aeae
Revises: 71c89b9c20e0
Create Date: 2026-07-23 11:11:59.308984

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '110f25f0aeae'
down_revision: Union[str, None] = '71c89b9c20e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OCR_STATUS = sa.Enum("not_applicable", "completed", "failed", name="ocr_status")

_SEARCH_VECTOR_EXPR = (
    "to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(sender, '') "
    "|| ' ' || coalesce(body_text, '') || ' ' || coalesce(ocr_text, ''))"
)


def upgrade() -> None:
    _OCR_STATUS.create(op.get_bind(), checkfirst=True)
    op.add_column("documents", sa.Column("ocr_text", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "documents",
        sa.Column(
            "ocr_status",
            _OCR_STATUS,
            nullable=False,
            server_default="not_applicable",
        ),
    )
    op.add_column("documents", sa.Column("ocr_error", sa.Text(), nullable=False, server_default=""))
    op.alter_column("documents", "ocr_text", server_default=None)
    op.alter_column("documents", "ocr_status", server_default=None)
    op.alter_column("documents", "ocr_error", server_default=None)

    # Postgres has no ALTER COLUMN ... SET EXPRESSION for generated columns,
    # so the search_vector column (added in 71c89b9c20e0) is dropped and
    # re-added with ocr_text folded into the indexed text.
    op.execute("DROP INDEX IF EXISTS ix_documents_search_vector")
    op.drop_column("documents", "search_vector")
    op.add_column(
        "documents",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(_SEARCH_VECTOR_EXPR, persisted=True),
            nullable=True,
        ),
    )
    op.execute("CREATE INDEX ix_documents_search_vector ON documents USING GIN (search_vector)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_search_vector")
    op.drop_column("documents", "search_vector")
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
    op.execute("CREATE INDEX ix_documents_search_vector ON documents USING GIN (search_vector)")

    op.drop_column("documents", "ocr_error")
    op.drop_column("documents", "ocr_status")
    op.drop_column("documents", "ocr_text")
    _OCR_STATUS.drop(op.get_bind(), checkfirst=True)
