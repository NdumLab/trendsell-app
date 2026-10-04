"""Give rate buckets an expiry so finished windows can be swept.

Additive and backwards compatible (action plan P04): the column is nullable, so the
previous application version keeps running against this schema for the length of a
rollback window. Existing rows are backfilled a day ahead of the migration, which is
longer than any window this application uses, so nothing that is still counting is swept.

Revision ID: 0002_rate_bucket_expiry
Revises: 0001_pilot_baseline
Created: 2026-09-08
"""
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = '0002_rate_bucket_expiry'
down_revision = '0001_pilot_baseline'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rate_buckets', sa.Column('expires_at', sa.String(), nullable=True))
    op.create_index('ix_rate_buckets_expires_at', 'rate_buckets', ['expires_at'])
    horizon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    op.execute(sa.text('UPDATE rate_buckets SET expires_at = :horizon WHERE expires_at IS NULL')
               .bindparams(horizon=horizon))


def downgrade():
    op.drop_index('ix_rate_buckets_expires_at', table_name='rate_buckets')
    op.drop_column('rate_buckets', 'expires_at')
