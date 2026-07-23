"""add structured coding fields

Revision ID: 9c3a7e5b1f2d
Revises: 110f25f0aeae
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c3a7e5b1f2d'
down_revision: Union[str, None] = '110f25f0aeae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODING_FIELD_TYPE = postgresql.ENUM("single_select", "multi_select", name="coding_field_type")


def upgrade() -> None:
    _CODING_FIELD_TYPE.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "coding_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "field_type",
            postgresql.ENUM(
                "single_select", "multi_select", name="coding_field_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("case_id", "name", name="uq_case_coding_field_name"),
    )

    op.create_table(
        "document_coding_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coding_field_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coding_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("set_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "coding_field_id", "value", name="uq_document_coding_value"),
    )
    op.create_index(
        "ix_document_coding_values_document_id", "document_coding_values", ["document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_coding_values_document_id", table_name="document_coding_values")
    op.drop_table("document_coding_values")
    op.drop_table("coding_fields")
    _CODING_FIELD_TYPE.drop(op.get_bind(), checkfirst=True)
