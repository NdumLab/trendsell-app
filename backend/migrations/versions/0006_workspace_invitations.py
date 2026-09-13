"""Expiring invitations and revocable multi-person workspace access.

Revision ID: 0006_workspace_invitations
Revises: 0005_email_verification
Created: 2026-09-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_workspace_invitations'
down_revision = '0005_email_verification'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('disabled_at', sa.String(), nullable=True))
    op.create_table(
        'invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('invited_by', sa.String(), nullable=False),
        sa.Column('expires_at', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('sent_at', sa.String(), nullable=True),
        sa.Column('accepted_at', sa.String(), nullable=True),
        sa.Column('revoked_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
        sa.UniqueConstraint('workspace_id', 'email'),
    )
    op.create_index('ix_invitations_workspace_id', 'invitations', ['workspace_id'])
    op.create_index('ix_invitations_token_hash', 'invitations', ['token_hash'], unique=True)
    op.create_index('ix_invitations_expires_at', 'invitations', ['expires_at'])


def downgrade():
    op.drop_index('ix_invitations_expires_at', table_name='invitations')
    op.drop_index('ix_invitations_token_hash', table_name='invitations')
    op.drop_index('ix_invitations_workspace_id', table_name='invitations')
    op.drop_table('invitations')
    op.drop_column('users', 'disabled_at')
