"""Record verified email ownership without inventing it for existing users.

Revision ID: 0005_email_verification
Revises: 0004_account_recovery
Created: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_email_verification'
down_revision = '0004_account_recovery'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.String(), nullable=True))


def downgrade():
    op.drop_column('users', 'email_verified_at')
