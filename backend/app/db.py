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

class Session(Base):
    __tablename__ = 'sessions'
    token_hash = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    expires_at = Column(String, nullable=False)

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
    __tablename__ = 'audit_events'
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(String, ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String)
    created_at = Column(String, nullable=False, default=now)

class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key = Column(String, primary_key=True)
    count = Column(Integer, nullable=False, default=0)

class Database:
    def __init__(self, url):
        kwargs = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}
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

def audit(db, user, action, record_id=None):
    db.add(Audit(workspace_id=user.workspace_id, user_id=user.id, action=action, record_id=record_id))
