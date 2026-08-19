"""add user tag and redaction reason presets

Revision ID: 3f7d1a9c5e02
Revises: 8a4f2c1e6b7d
Create Date: 2026-08-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3f7d1a9c5e02"
down_revision = "8a4f2c1e6b7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_tag_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#6366f1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tag_preset_name"),
    )
    op.create_table(
        "user_redaction_reason_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "reason", name="uq_user_redaction_reason_preset"),
    )


def downgrade() -> None:
    op.drop_table("user_redaction_reason_presets")
    op.drop_table("user_tag_presets")
