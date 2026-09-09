"""add near duplicate clusters and email inclusiveness

Revision ID: 6949002af119
Revises: 3f7d1a9c5e02
Create Date: 2026-09-09 17:42:30.501110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6949002af119'
down_revision: Union[str, None] = '3f7d1a9c5e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('near_duplicate_clusters',
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('cases', sa.Column('analytics_computed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('near_duplicate_cluster_id', sa.UUID(), nullable=True))
    op.add_column('documents', sa.Column('is_inclusive_email', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('documents', 'is_inclusive_email', server_default=None)
    op.create_index(op.f('ix_documents_near_duplicate_cluster_id'), 'documents', ['near_duplicate_cluster_id'], unique=False)
    op.create_foreign_key(None, 'documents', 'near_duplicate_clusters', ['near_duplicate_cluster_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_near_duplicate_cluster_id'), table_name='documents')
    op.drop_column('documents', 'is_inclusive_email')
    op.drop_column('documents', 'near_duplicate_cluster_id')
    op.drop_column('cases', 'analytics_computed_at')
    op.drop_table('near_duplicate_clusters')
