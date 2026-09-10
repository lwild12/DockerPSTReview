"""add ai review

Revision ID: 1ba360c283ba
Revises: 6949002af119
Create Date: 2026-09-10 11:50:04.263698

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1ba360c283ba"
down_revision: Union[str, None] = "6949002af119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AI_RELEVANCE_STATUS = postgresql.ENUM(
    "queued", "running", "completed", "failed", name="ai_relevance_status"
)


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("ai_review_criteria", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("cases", "ai_review_criteria", server_default=None)
    op.add_column(
        "cases",
        sa.Column("ai_review_last_run_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("ai_review_last_run_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "system_settings",
        sa.Column("ollama_base_url", sa.String(500), nullable=False, server_default=""),
    )
    op.alter_column("system_settings", "ollama_base_url", server_default=None)
    op.add_column(
        "system_settings",
        sa.Column("ollama_model", sa.String(255), nullable=False, server_default=""),
    )
    op.alter_column("system_settings", "ollama_model", server_default=None)
    op.add_column(
        "system_settings",
        sa.Column("ollama_api_key_encrypted", sa.String(2000), nullable=False, server_default=""),
    )
    op.alter_column("system_settings", "ollama_api_key_encrypted", server_default=None)
    op.add_column(
        "system_settings",
        sa.Column("ai_review_concurrency", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("system_settings", "ai_review_concurrency", server_default=None)

    _AI_RELEVANCE_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "document_ai_relevance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "completed",
                "failed",
                name="ai_relevance_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("criteria_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_document_ai_relevance_document_id", "document_ai_relevance", ["document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_ai_relevance_document_id", table_name="document_ai_relevance")
    op.drop_table("document_ai_relevance")
    _AI_RELEVANCE_STATUS.drop(op.get_bind(), checkfirst=True)

    op.drop_column("system_settings", "ai_review_concurrency")
    op.drop_column("system_settings", "ollama_api_key_encrypted")
    op.drop_column("system_settings", "ollama_model")
    op.drop_column("system_settings", "ollama_base_url")

    op.drop_column("cases", "ai_review_last_run_completed_at")
    op.drop_column("cases", "ai_review_last_run_started_at")
    op.drop_column("cases", "ai_review_criteria")
