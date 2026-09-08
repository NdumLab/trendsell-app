"""Record the request and the target version on every audit event.

Additive and reversible (action plan P05/P07). `request_id` is the thread from a reported
error to the exact row that was written; `detail` holds the small, non-secret facts about
the target — its kind, the version referenced, the export scope — so an entry can be read
without re-deriving context from the record it names.

Revision ID: 0003_audit_detail
Revises: 0002_rate_bucket_expiry
Created: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0003_audit_detail'
down_revision = '0002_rate_bucket_expiry'
branch_labels = None
depends_on = None

PAYLOAD = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade():
    op.add_column('audit_events', sa.Column('request_id', sa.String(), nullable=True))
    op.add_column('audit_events', sa.Column('detail', PAYLOAD, nullable=True))
    op.create_index('ix_audit_events_request_id', 'audit_events', ['request_id'])
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])


def downgrade():
    op.drop_index('ix_audit_events_created_at', table_name='audit_events')
    op.drop_index('ix_audit_events_request_id', table_name='audit_events')
    op.drop_column('audit_events', 'detail')
    op.drop_column('audit_events', 'request_id')
