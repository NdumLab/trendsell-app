import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, Column, String, Integer, ForeignKey, UniqueConstraint, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()
Payload = JSON().with_variant(JSONB, 'postgresql')

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

class Workspace(Base):
    __tablename__ = 'workspaces'
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey('workspaces.id'), nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default='owner')
    # Null means this installation has not yet proved control of the address. Existing
    # users are deliberately not grandfathered as verified by the migration.
    email_verified_at = Column(String)
    #: Membership removal suspends access instead of deleting this row because audit
    #: events retain the actor id. A later invitation to the same workspace may reactivate
    #: the account with a new password; every old session is revoked on suspension.
    disabled_at = Column(String)

class Session(Base):
    __tablename__ = 'sessions'
    token_hash = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    expires_at = Column(String, nullable=False)
    #: A session a person cannot recognise is one they cannot decide to revoke, so each
    #: records when it started and the client that started it (action plan P03).
    created_at = Column(String, nullable=False, default=now)
    #: Truncated and never parsed back into an identity: enough to tell "my laptop" from
    #: "something else", not a device fingerprint.
    client = Column(String)

class Record(Base):
    """Versioned pilot records; kind-specific contracts are validated by the API.

    The production expansion splits these into relational domain tables (ADR 001).
    Immutable decisions and events are append-only through the repository.
    """
    __tablename__ = 'records'
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey('workspaces.id'), nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    payload = Column(Payload, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    __table_args__ = (UniqueConstraint('workspace_id', 'kind', 'key'),)

class Audit(Base):
    """Append-only record of who did what, to which record, under which request.

    `detail` carries small non-secret facts about the target — its kind, the version
    referenced, an export's scope — so an entry can be read without re-deriving context
    from the record it names. It never holds credentials or record payloads (P05/P07).
    """
    __tablename__ = 'audit_events'
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String)
    request_id = Column(String, index=True)
    detail = Column(Payload)
    created_at = Column(String, nullable=False, default=now, index=True)

class RecoveryToken(Base):
    """A single-use, purpose-bound, short-lived account-security credential.

    Only the hash is stored: the token itself exists in the message or the operator's
    one-time handoff, so a database copy cannot be used to take over an account (action
    plan P03). `purpose` is part of the lookup, so a token minted for one action cannot be
    replayed against another. `used_at` makes it single-use without deleting the row during
    its validity window, which keeps a reuse attempt distinguishable from a token that never
    existed. The startup sweep removes the row after its original expiry.
    """
    __tablename__ = 'recovery_tokens'
    token_hash = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    purpose = Column(String, nullable=False)
    expires_at = Column(String, nullable=False, index=True)
    created_at = Column(String, nullable=False, default=now)
    used_at = Column(String)


class Invitation(Base):
    """An expiring, single-use invitation into one existing workspace.

    The bearer token is never stored in clear text or returned by list endpoints. The
    invited address is bound to the credential, so accepting it cannot create an account
    under a different identity or workspace.
    """
    __tablename__ = 'invitations'
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey('workspaces.id'), nullable=False, index=True)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    invited_by = Column(String, ForeignKey('users.id'), nullable=False)
    expires_at = Column(String, nullable=False, index=True)
    created_at = Column(String, nullable=False, default=now)
    sent_at = Column(String)
    accepted_at = Column(String)
    revoked_at = Column(String)
    __table_args__ = (UniqueConstraint('workspace_id', 'email'),)

class RateBucket(Base):
    """One counter for one key in one window.

    `expires_at` exists so a finished window can be swept without parsing the key, and so
    cleanup can never touch a window that is still counting (action plan P04).
    """
    __tablename__ = 'rate_buckets'
    key = Column(String, primary_key=True)
    count = Column(Integer, nullable=False, default=0)
    expires_at = Column(String, nullable=True, index=True)

class Database:
    def __init__(self, url):
        kwargs = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {'pool_pre_ping': True}
        if url in {'sqlite://', 'sqlite:///:memory:'}:
            kwargs['poolclass'] = StaticPool
        self.engine = create_engine(url, **kwargs)
        if url.startswith('sqlite'):
            @event.listens_for(self.engine, 'connect')
            def foreign_keys(connection, _):
                connection.execute('PRAGMA foreign_keys=ON')
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def create(self):
        Base.metadata.create_all(self.engine)

def records(db, user, kind):
    return db.query(Record).filter_by(workspace_id=user.workspace_id, kind=kind)

def audit(db, user, action, record_id=None, **detail):
    """Append one audit event, tagged with the request that caused it.

    Callers pass small facts as keyword arguments; never a payload, a body or a secret.
    """
    from .observability import request_id
    db.add(Audit(workspace_id=user.workspace_id, user_id=user.id, action=action, record_id=record_id,
                 request_id=request_id(), detail=detail or None))
