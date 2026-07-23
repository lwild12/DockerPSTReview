"""add production_number and bates_end_number to export_jobs

Revision ID: 4f1c8a2d6e93
Revises: 9c3a7e5b1f2d
Create Date: 2026-07-23 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f1c8a2d6e93'
down_revision: Union[str, None] = '9c3a7e5b1f2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("export_jobs", sa.Column("production_number", sa.Integer(), nullable=True))
    op.add_column("export_jobs", sa.Column("bates_end_number", sa.Integer(), nullable=True))

    # Backfill production_number for any pre-existing rows: a sequential
    # counter per case, ordered by when each export was created.
    op.execute(
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY created_at, id) AS rn
            FROM export_jobs
        )
        UPDATE export_jobs
        SET production_number = numbered.rn
        FROM numbered
        WHERE export_jobs.id = numbered.id
        """
    )
    op.alter_column("export_jobs", "production_number", nullable=False)

    # Backfill bates_end_number for completed Bates-numbered exports by
    # parsing the trailing digits off the highest bates_end already recorded
    # for that job, so a follow-up production picks up where a pre-migration
    # export actually left off instead of restarting at 1.
    op.execute(
        """
        UPDATE export_jobs
        SET bates_end_number = sub.max_end + 1
        FROM (
            SELECT export_job_id, MAX(substring(bates_end from '(\\d+)$')::int) AS max_end
            FROM export_document_bates
            WHERE bates_end ~ '\\d+$'
            GROUP BY export_job_id
        ) sub
        WHERE export_jobs.id = sub.export_job_id AND export_jobs.apply_bates = true
        """
    )


def downgrade() -> None:
    op.drop_column("export_jobs", "bates_end_number")
    op.drop_column("export_jobs", "production_number")
