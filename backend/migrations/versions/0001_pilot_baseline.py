"""Pilot baseline: the schema the running installation already has.

This revision creates exactly what `/opt/trendsell/bootstrap_schema.py` created once by
hand, so it serves two purposes (action plan P01):

* an empty database reaches this revision by running it;
* the existing production database, whose tables already match, is *stamped* with it
  after `app.migrate check` has verified the schema — never by running it.

Revision ID: 0001_pilot_baseline
Revises:
Created: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0001_pilot_baseline'
down_revision = None
branch_labels = None
depends_on = None

PAYLOAD = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade():
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_workspace_id', 'users', ['workspace_id'])
    op.create_table(
        'sessions',
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('expires_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('token_hash'),
    )
    op.create_table(
        'records',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('payload', PAYLOAD, nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'kind', 'key'),
    )
    op.create_index('ix_records_workspace_id', 'records', ['workspace_id'])
    op.create_index('ix_records_kind', 'records', ['kind'])
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_events_workspace_id', 'audit_events', ['workspace_id'])
    op.create_table(
        'rate_buckets',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade():
    # The baseline is the floor. Dropping it would destroy every customer record, so it is
    # not offered: roll back by restoring a backup (see docs/RUNBOOK.md).
    raise RuntimeError('The pilot baseline cannot be downgraded. Restore from a backup instead.')
