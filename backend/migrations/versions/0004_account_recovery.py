"""Account recovery tokens, and sessions a person can recognise and revoke.

Action plan P03. Additive and reversible. `recovery_tokens` stores only hashes, so the
table is not itself a way into an account. Sessions gain a start time and a short client
label, because a session list nobody can read is a list nobody can act on.

Existing sessions get the migration's own timestamp for `created_at`: their real start is
not recorded anywhere, and inventing a precise one would be worse than an honest
approximation that is clearly the upgrade time. They are short-lived, so the
approximation ages out on its own.

Revision ID: 0004_account_recovery
Revises: 0003_audit_detail
Created: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_account_recovery'
down_revision = '0003_audit_detail'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recovery_tokens',
        sa.Column('token_hash', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('expires_at', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('used_at', sa.String(), nullable=True),
    )
    op.create_index('ix_recovery_tokens_user_id', 'recovery_tokens', ['user_id'])
    op.create_index('ix_recovery_tokens_expires_at', 'recovery_tokens', ['expires_at'])

    # Added nullable, backfilled, then made non-null: an existing row has no value, and
    # SQLite cannot add a NOT NULL column without a default anyway.
    op.add_column('sessions', sa.Column('created_at', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('client', sa.String(), nullable=True))
    op.execute("UPDATE sessions SET created_at = expires_at WHERE created_at IS NULL")
    with op.batch_alter_table('sessions') as batch:
        batch.alter_column('created_at', existing_type=sa.String(), nullable=False)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])


def downgrade():
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_column('sessions', 'client')
    op.drop_column('sessions', 'created_at')
    op.drop_index('ix_recovery_tokens_expires_at', table_name='recovery_tokens')
    op.drop_index('ix_recovery_tokens_user_id', table_name='recovery_tokens')
    op.drop_table('recovery_tokens')
