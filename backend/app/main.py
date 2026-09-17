from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import secrets
import time
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import (BaseModel, Field, ConfigDict, HttpUrl, StringConstraints,
                      TypeAdapter, field_validator, model_validator)
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from . import migrate
from .settings import Settings
from .db import (Database, Workspace, User, Session, RecoveryToken, Invitation, Record,
                 Audit, RateBucket, records, audit, now, uid)
from .deletions import (DeletionRegister, DeletionRegisterError, delete_workspace_rows,
                        replay as replay_deletions)
from .security import (dummy_verify, hash_password, verify_password, keyed_hash, token_hash,
                       consume, purge_expired, purge_old_audit_events, resolve_input)
from .limits import BodyLimit, MAX_BODY_BYTES
from .observability import Counters, REQUEST_ID, USER_ID, WORKSPACE_ID, logger, new_request_id, route_label
from .permissions import matrix, require
from . import mail
from .evidence import EvidenceRequest, MANUAL_TRUTH_STATE, METHOD_VERSION, METRICS, quality
from . import compliance as cmp
from .economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate, economics_summary
from .pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate, searched
from .providers.amazon_creators import (AmazonCreatorsClient, AmazonCreatorsConfig,
                                        COLLECTOR_VERSION as AMAZON_COLLECTOR_VERSION,
                                        PARSER_VERSION as AMAZON_PARSER_VERSION,
                                        ProviderError)

SOURCES = [
    {'id':'amazon', 'name':'Amazon catalog', 'category':'Product identity', 'markets':['US'], 'reason':'An authorized catalog connection is required. Pasted identifiers are user input, not verified catalog data.', 'rights':'Authorization required'},
    {'id':'google_trends', 'name':'Google Trends', 'category':'Search demand', 'markets':['US','NG'], 'reason':'No approved demand collector is connected. No search observations have been collected.', 'rights':'Source access review required'},
    {'id':'local_market', 'name':'Nigeria market coverage', 'category':'Local supply', 'markets':['NG'], 'reason':'No local marketplace observations. Missing listings do not indicate low competition.', 'rights':'Licensed or user-assisted evidence required'},
    {'id':'compliance', 'name':'Import requirements', 'category':'Compliance & tariffs', 'markets':['NG'], 'reason':'Product classification and effective-dated regulator evidence require review.', 'rights':'Official publications with analyst review'},
    {'id':'freight', 'name':'Freight & currency', 'category':'Landed cost', 'markets':['CN','NG'], 'reason':'Enter dated freight quotes and your exchange-rate assumption in Decision Room.', 'rights':'User-provided inputs only'},
]

#: Every record kind a workspace owns, and the collection it is exported under.
#:
#: Review finding R05: `evidence` and `compliance_review` were added as record kinds but
#: never added here, so "export workspace records" silently omitted them — and because
#: the counts are derived from this same list, the export could not report what it had
#: left out. A new kind belongs in this list at the moment it becomes a kind; the export
#: contract test asserts exactly that, so a future kind cannot go missing quietly.
EXPORT_KINDS = [('product','products'), ('job','research_jobs'), ('decision','decisions'),
                ('quote','quotes'), ('watch','watches'), ('evidence','evidence'),
                ('compliance_review','compliance_reviews'),
                ('source_snapshot','source_snapshots'), ('source_status','source_statuses')]
EXPORT_SCHEMA = 'trendsell-workspace-export/3'

HTTPS_URL = TypeAdapter(HttpUrl)

class StrictModel(BaseModel):
    # str_strip_whitespace normalises *before* the length constraints run, so a name of
    # two spaces is rejected instead of being stored empty (action plan T08).
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)

class Credentials(StrictModel):
    """Sign-in and registration credentials.

    Review finding R02: `StrictModel` sets `str_strip_whitespace=True`, which is right for
    an email or a display name and wrong for a password. The pilot hashed the password
    exactly as it was typed, so stripping it here made every existing account whose
    password began or ended with a space unable to sign in — the legacy verifier was
    correct, but it was being handed a different string than the one that was hashed.

    A password is an opaque secret: it is stored, compared and length-checked exactly as
    entered. Email and name keep their own normalisation, at their own fields.
    """
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]
    name: str = Field(default='My workspace', min_length=1, max_length=80)

#: A password field, everywhere one appears. Same rule as `Credentials.password` and for
#: the same reason (R02): a password is an opaque secret, never normalised.
Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]

class RecoveryRequest(StrictModel):
    """Ask for a reset link. Deliberately says nothing about whether the account exists."""
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

class PasswordReset(StrictModel):
    """Redeem a reset token. The token is a bearer credential, so it is never normalised."""
    token: Annotated[str, StringConstraints(strip_whitespace=False, min_length=20, max_length=200)]
    password: Password

class PasswordChange(StrictModel):
    """Change a password while signed in. The current one is required: a borrowed session
    must not be enough to lock the owner out of their own account."""
    current_password: Password
    new_password: Password

class VerificationConfirm(StrictModel):
    token: Annotated[str, StringConstraints(strip_whitespace=False, min_length=20, max_length=200)]

class InvitationCreate(StrictModel):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    role: Literal['analyst', 'reviewer', 'viewer']

class InvitationAccept(StrictModel):
    token: Annotated[str, StringConstraints(strip_whitespace=False, min_length=20, max_length=200)]
    name: str = Field(min_length=1, max_length=80)
    password: Password

class MemberRoleChange(StrictModel):
    role: Literal['analyst', 'reviewer', 'viewer']

class AccountDeletion(StrictModel):
    password: Password
    confirmation: str = Field(min_length=8, max_length=200)

class XrayRequest(StrictModel):
    input: str = Field(min_length=10, max_length=2048)
    market: Literal['NG'] = 'NG'

class ConfirmRequest(StrictModel):
    name: str = Field(min_length=2, max_length=160)

class DecisionRequest(StrictModel):
    product_id: str
    inputs: Inputs
    quote_id: str | None = Field(default=None, max_length=64)
    # Currency conversion is an explicit user assumption. USD quotes use 1.0 and do not
    # need this field; a CNY (or other) quote can never silently become a USD input.
    quote_fx_to_usd: float | None = Field(default=None, gt=0, le=1000000)

class WatchRequest(StrictModel):
    product_id: str
    threshold_pct: int = Field(default=15, ge=1, le=100)

class QuoteRequest(StrictModel):
    product_id: str
    supplier: str = Field(min_length=2, max_length=200)
    source_url: str = Field(min_length=12, max_length=2000)
    unit_price: float | None = Field(default=None, gt=0, le=1000000)
    # Accepted for compatibility with pilot records and older clients. New clients send
    # unit_price plus an explicit currency; storage is always normalised to those names.
    unit_price_usd: float | None = Field(default=None, gt=0, le=1000000)
    currency: str = Field(default='USD', pattern=r'^[A-Z]{3}$')
    moq: int = Field(ge=1, le=1000000)
    lead_days: int = Field(ge=1, le=1000)
    quote_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    incoterm: Literal['EXW','FOB','CIF','DDP'] = 'FOB'
    notes: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def one_price_field(self):
        if (self.unit_price is None) == (self.unit_price_usd is None):
            raise ValueError('Provide exactly one unit price.')
        if self.unit_price_usd is not None and self.currency != 'USD':
            raise ValueError('unit_price_usd can only be used with USD. Send unit_price for other currencies.')
        return self

    @field_validator('source_url')
    @classmethod
    def real_https_url(cls, value):
        """A prefix check accepted 'https://', which addresses nothing (action plan T08).

        TrendSell never fetches this reference; it must still be a link a person can open.
        """
        try:
            url = HTTPS_URL.validate_python(value)
        except Exception:
            raise ValueError('Enter the full https:// address of the quote, for example https://supplier.example.com/quote-4821')
        if url.scheme != 'https' or not url.host or '.' not in url.host:
            raise ValueError('Enter the full https:// address of the quote, for example https://supplier.example.com/quote-4821')
        return str(url)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    database = Database(settings.database_url)
    deletion_register = DeletionRegister(settings.deletion_register_dir)

    def rate_identity(value):
        """HMAC low-entropy identifiers before they enter the shared rate table."""
        return keyed_hash(value, settings.rate_key_secret)

    @asynccontextmanager
    async def lifespan(app):
        if settings.environment != 'production':
            database.create()
        # Interrupted investigations become truthful partial results after restart.
        with database.session() as db:
            # A deletion request is written outside PostgreSQL before live rows are
            # removed. Replaying on every start closes the crash window between those two
            # durable operations and makes the same path apply after a restore.
            if deletion_register.enabled:
                result = replay_deletions(db, deletion_register.entries())
                if result.workspaces_deleted:
                    logger.info('deletion register replayed', extra={'context': {
                        'entries': result.entries,
                        'workspaces_deleted': result.workspaces_deleted,
                    }})
            for job in db.query(Record).filter_by(kind='job').all():
                if job.payload['status'] in {'queued','running'}:
                    p = dict(job.payload)
                    p.update(status='partial', events=p['events']+[{'id':len(p['events'])+1,'step':'Investigation interrupted', 'status':'unavailable','detail':'The service restarted. Refresh the investigation to try again.', 'at':now()}])
                    job.payload = p
            db.commit()
            # Expired sessions, recovery credentials and finished rate windows accumulate
            # otherwise; only rows whose own expiry has passed are removed (action plan P04).
            purge_expired(db)
            removed_audit = purge_old_audit_events(db, settings.audit_retention_days)
            if removed_audit:
                logger.info('audit retention applied', extra={'context': {
                    'removed': removed_audit,
                    'retention_days': settings.audit_retention_days,
                }})
        yield
        database.engine.dispose()

    app = FastAPI(title='TrendSell Evidence API', version='2.0.0', lifespan=lifespan)
    app.state.database = database
    app.state.deletion_register = deletion_register
    # Exposed so a test can assert against the limit actually in force rather than a
    # number copied into the test and quietly drifting from it.
    app.state.settings = settings
    amazon_required = {
        'credential id': settings.amazon_creators_credential_id,
        'credential secret': settings.amazon_creators_credential_secret,
        'partner tag': settings.amazon_creators_partner_tag,
        'usage-rights and retention approval': settings.amazon_creators_usage_rights,
    }
    amazon_missing = [name for name, value in amazon_required.items() if not value]
    amazon_configured = settings.amazon_creators_enabled and not amazon_missing
    app.state.amazon_creators = AmazonCreatorsClient(AmazonCreatorsConfig(
        credential_id=settings.amazon_creators_credential_id,
        credential_secret=settings.amazon_creators_credential_secret,
        credential_version=settings.amazon_creators_credential_version,
        partner_tag=settings.amazon_creators_partner_tag,
        marketplace=settings.amazon_creators_marketplace,
        usage_rights=settings.amazon_creators_usage_rights,
        timeout_seconds=settings.amazon_creators_timeout_seconds,
    )) if amazon_configured else None
    # Outermost, so an oversized body is refused before anything reads it. Counting the
    # bytes as they arrive is what a Content-Length check could not do (action plan P04).
    app.add_middleware(BodyLimit, limit=MAX_BODY_BYTES)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True,
                       allow_methods=['GET','POST','PUT','DELETE'], allow_headers=['Content-Type','Idempotency-Key','X-Requested-With'])

    counters = Counters()
    app.state.counters = counters

    def identity(request):
        """Who the request turned out to be, for the log line.

        Review finding R11: `current_user` is a synchronous dependency, so FastAPI runs it
        in a worker thread with its own context. Context variables set there are invisible
        to this middleware, which runs in the request's own context — so every
        authenticated request logged `workspace_id: "-"`. Starlette backs `request.state`
        with the ASGI scope, and the scope is the one object both sides genuinely share.
        """
        state = request.scope.get('state') or {}
        return {'workspace_id': state.get('workspace_id', '-'),
                'user_id': state.get('user_id', '-')}

    def protect_response(response, identifier):
        """Apply the headers every response needs, including an internal failure."""
        response.headers['X-Request-ID'] = identifier
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store'
        if settings.environment == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    @app.middleware('http')
    async def guard(request, call_next):
        # One id per request: returned to the caller, written on every log line, and
        # stored on the audit events the request produces (action plan P07).
        identifier = new_request_id(request.headers.get('x-request-id'))
        request_token = REQUEST_ID.set(identifier)
        workspace_token, user_token = WORKSPACE_ID.set('-'), USER_ID.set('-')
        started = time.perf_counter()
        try:
            if request.method in {'POST','PUT','PATCH','DELETE'}:
                origin = request.headers.get('origin')
                if (origin and origin not in settings.origins) or request.headers.get('x-requested-with') != 'TrendSell':
                    response = JSONResponse({'detail':'Request origin or CSRF header rejected'}, status_code=403)
                else:
                    response = await call_next(request)
            else:
                response = await call_next(request)
            duration_ms = (time.perf_counter() - started) * 1000
            # The router records which route it matched on the shared scope, so the label
            # is a bounded template rather than whatever path the caller typed (R07).
            matched = request.scope.get('route')
            counters.record(request.method, request.url.path, response.status_code, duration_ms, matched)
            # No body, no query string, no cookie: a route label, an outcome and who it was.
            logger.info('request', extra={'request_id': identifier, 'context': {
                'method': request.method, 'route': route_label(request.url.path, matched),
                'status': response.status_code, 'duration_ms': round(duration_ms, 1),
                **identity(request)}})
            return protect_response(response, identifier)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            matched = request.scope.get('route')
            counters.record(request.method, request.url.path, 500, duration_ms, matched)
            logger.exception('request failed', extra={'request_id': identifier, 'context': {
                'method': request.method, 'route': route_label(request.url.path, matched),
                'status': 500, 'duration_ms': round(duration_ms, 1), **identity(request)}})
            # Do not re-raise into Uvicorn: its default error logger would emit the full
            # exception text and traceback after our structured logger deliberately
            # redacted them. The request id and exception class above retain correlation;
            # the caller receives one generic response with the same id.
            response = protect_response(
                JSONResponse({'detail': 'Internal server error.'}, status_code=500), identifier)
            # This response is produced outside the inner CORS middleware, so preserve its
            # allowed-origin behavior explicitly for this one path.
            origin = request.headers.get('origin')
            if origin in settings.origins:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Vary'] = 'Origin'
            return response
        finally:
            REQUEST_ID.reset(request_token)
            WORKSPACE_ID.reset(workspace_token)
            USER_ID.reset(user_token)

    def get_db():
        with database.session() as db:
            yield db

    def current_user(request: Request, db=Depends(get_db)):
        token = request.cookies.get('trendsell_session','')
        session = db.get(Session, token_hash(token)) if token else None
        if not session or session.expires_at <= now():
            raise HTTPException(401, 'Sign in to your workspace to continue.')
        user = db.get(User, session.user_id)
        if not user or user.disabled_at: raise HTTPException(401, 'Session is no longer valid.')
        # Both: the context variables serve `audit()` on this same thread, and the request
        # scope carries the identity back out to the logging middleware (R11).
        WORKSPACE_ID.set(user.workspace_id)
        USER_ID.set(user.id)
        request.state.workspace_id = user.workspace_id
        request.state.user_id = user.id
        return user

    def permissions_granted(user, permission):
        from .permissions import granted
        return granted(user.role, permission)

    def permitted(permission):
        """A dependency that asks for a named permission, never for a role (P05)."""
        def dependency(user=Depends(current_user)):
            return require(user, permission)
        return dependency

    def writer(user=Depends(permitted('workspace.write')), db=Depends(get_db)):
        # A fair per-workspace write quota, so one busy workspace cannot crowd out another.
        consume(db, f'write:{user.workspace_id}:{now()[:16]}', settings.workspace_write_minute_limit,
                message='This workspace is making changes too quickly. Try again in a moment.')
        return user

    def owned(db, user, kind, record_id):
        row = records(db, user, kind).filter_by(id=record_id).first()
        if not row: raise HTTPException(404, 'Record not found in this workspace.')
        return row

    def serialize(row):
        return {**row.payload, 'id':row.id, 'created_at':row.created_at}

    def assessment_summary(row):
        """What a product view needs to show about a saved assessment, without its detail."""
        payload = row.payload
        return {'id': row.id, 'decision': payload['decision'], 'saved_at': row.created_at,
                'compliance': payload['inputs']['compliance'], 'channel': payload['inputs']['channel'],
                'shipping': payload['inputs']['shipping'], 'truth_state': payload['truth_state'],
                'formula_version': payload['formula_version'], 'threshold_version': payload.get('threshold_version'),
                'economics': payload.get('economics') or economics_summary(payload['scenarios'])}

    def with_latest_assessment(db, user, rows):
        """Attach each product's most recent saved assessment (action plan T07).

        Review finding 7: saving a prohibited assessment returned NO-GO while the product
        still reported INSUFFICIENT EVIDENCE, and Discover and the watchlist read that
        unchanged product verdict. The two are different facts, so the product carries
        both: `decision` remains its *evidence* status, and `latest_assessment` is the
        user's most recent *commercial* judgement, with its date and scenario. Neither
        overwrites the other, and no saved assessment is modified.
        """
        serialized = [serialize(row) for row in rows]
        ids = {item['id'] for item in serialized}
        if not ids:
            return serialized
        latest = {}
        for decision in (records(db,user,'decision')
                         .filter(Record.payload['product_id'].as_string().in_(ids))
                         .order_by(Record.created_at.asc()).all()):
            latest[decision.payload['product_id']] = decision   # ascending, so the last write wins
        for item in serialized:
            row = latest.get(item['id'])
            item['latest_assessment'] = assessment_summary(row) if row else None
        return serialized

    def with_product_names(db, user, rows, assessments=False):
        """Attach each record's current product name in one extra query.

        Watch and quote lists are paged independently of products, so a screen cannot
        look the name up in whatever product page happens to be loaded (action plan T05).
        With `assessments`, the product's evidence status and latest saved assessment come
        too, so the watchlist can show both rather than only the product verdict (T07).
        """
        serialized = [serialize(row) for row in rows]
        ids = {item['product_id'] for item in serialized if item.get('product_id')}
        if not ids:
            return serialized
        products = records(db,user,'product').filter(Record.id.in_(ids)).all()
        detail = {p['id']: p for p in (with_latest_assessment(db,user,products) if assessments
                                       else [serialize(p) for p in products])}
        for item in serialized:
            product = detail.get(item.get('product_id'))
            item['product_name'] = product['name'] if product else None
            if assessments and product:
                item['product_decision'] = product['decision']
                item['latest_assessment'] = product['latest_assessment']
        return serialized

    def insert(db, user, kind, payload, key=None):
        row = Record(workspace_id=user.workspace_id, kind=kind, key=key or uid(), payload=payload)
        db.add(row)
        db.flush()
        audit(db, user, kind+'.created', row.id)
        return row

    def insert_unique(db, user, kind, key, payload):
        """Insert one keyed record, or return the row a concurrent request inserted first.

        The unique constraint is (workspace_id, kind, key), and the violation surfaces at
        the flush inside this savepoint (action plan T06). Catching it here rather than
        around a later commit is what keeps a duplicate submission from becoming a 500:
        the savepoint rolls back, the outer transaction stays usable, and the caller is
        handed the winning row with `created=False` so it can converge on one result.
        """
        try:
            with db.begin_nested():
                row = Record(workspace_id=user.workspace_id, kind=kind, key=key, payload=payload)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = records(db, user, kind).filter_by(key=key).first()
            if row is None:
                raise
            return row, False
        audit(db, user, kind+'.created', row.id, kind=kind)
        return row, True

    def source_status(db, workspace_id, source_id, **changes):
        """Upsert workspace-scoped source telemetry without storing credentials."""
        row = db.query(Record).filter_by(
            workspace_id=workspace_id, kind='source_status', key=source_id).first()
        base = {'source_id': source_id, 'status': 'configured', 'last_attempt': None,
                'last_success': None, 'next_retry': 'On the next user-requested check',
                'reason': 'Configured; no collection attempt has completed yet.'}
        if row:
            row.payload = {**base, **row.payload, **changes}
        else:
            row = Record(workspace_id=workspace_id, kind='source_status', key=source_id,
                         payload={**base, **changes})
            db.add(row)
            db.flush()
        return row

    def user_view(user):
        return {'id':user.id, 'name':user.name, 'email':user.email, 'workspace_id':user.workspace_id,
                'role':user.role, 'email_verified':bool(user.email_verified_at),
                'email_verified_at':user.email_verified_at}

    def start_session(db, user, response, request=None):
        token = secrets.token_urlsafe(48)
        db.add(Session(token_hash=token_hash(token), user_id=user.id,
                       expires_at=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),
                       created_at=now(), client=client_label(request)))
        audit(db, user, 'auth.login')
        db.commit()
        response.set_cookie('trendsell_session', token, httponly=True, secure=settings.environment=='production', samesite='strict', max_age=604800, path='/api')
        return user_view(user)

    @app.get('/api/health')
    def health():
        """Liveness: the process is up. Deliberately does not touch the database."""
        return {'status':'ok', 'version':'2.0.0', 'demo':False}

    #: Readiness re-inspects the physical schema at most this often (settings, default 30s).
    #: Inspecting tables and columns on every probe would make a liveness-frequency endpoint
    #: do real work; never inspecting at all is what review finding R09 caught.
    schema_check = {'at': 0.0, 'revision': None, 'matches': False, 'missing_tables': [],
                    'missing_columns': {}}

    def schema_state():
        """The cached physical-schema verdict, refreshed when it is stale.

        A revision label is a claim *about* the schema, not the schema. Review finding
        R09: a database migrated to head and then missing `audit_events` answered
        `SELECT 1`, still carried the 0003 row, and reported ready — while every audited
        write would have failed. So the tables and columns the models declare are actually
        inspected, and a changed revision refreshes the verdict immediately.
        """
        try:
            revision = migrate.current_revision(database.engine)
        except Exception:
            revision = None
        stale = (time.monotonic() - schema_check['at']) > settings.schema_recheck_seconds
        if stale or revision != schema_check['revision']:
            try:
                report = migrate.schema_report(database.engine)
            except Exception:
                report = {'matches_models': False, 'missing_tables': ['<schema unreadable>'],
                          'missing_columns': {}}
            schema_check.update(at=time.monotonic(), revision=revision,
                                matches=report['matches_models'],
                                missing_tables=report['missing_tables'],
                                missing_columns=report['missing_columns'])
        return schema_check

    @app.get('/api/ready')
    def ready(response: Response, db=Depends(get_db)):
        """Readiness: the database answers, is at the expected revision, *and* has the
        schema that revision promises.

        `SELECT 1` proves connectivity, a revision row proves a migration was recorded,
        and only inspection proves the tables and columns are there (P01, R09).
        """
        db.execute(text('SELECT 1'))
        expected = migrate.head_revision(settings.database_url)
        state = schema_state()
        actual = state['revision']
        at_revision = actual == expected
        ready_now = at_revision and state['matches']
        if not ready_now:
            response.status_code = 503
        status = 'ready' if ready_now else ('schema_mismatch' if not at_revision else 'schema_incomplete')
        body = {'status':status, 'database':'ok',
                'schema_revision':actual, 'expected_revision':expected,
                'schema_matches_models':state['matches']}
        if not state['matches']:
            # Named, so an operator knows what to restore rather than only that it failed.
            body['missing_tables'] = state['missing_tables']
            body['missing_columns'] = state['missing_columns']
        return body

    @app.get('/api/v1/config')
    def config():
        return {'allow_registration':settings.allow_registration, 'destination':'NG', 'demo':False,
                'release_tier':settings.release_tier,
                'invitation_only':settings.release_tier == 'controlled_pilot',
                'billing_enabled':False,
                'research_daily_limit':settings.research_daily_limit,
                'mail_delivery_configured':mailer.configured,
                'account_recovery':'email' if mailer.configured else 'operator_required',
                'audit_retention_days':settings.audit_retention_days,
                'features': {
                    'billing': False,
                    'public_registration': settings.allow_registration,
                    'recurring_monitoring': False,
                    'alert_delivery': False,
                    'import_review': settings.import_review_enabled,
                    'attachments': False,
                    'additional_markets': False,
                }}

    @app.post('/api/v1/auth/register', status_code=201)
    def register(payload: Credentials, request: Request, response: Response, db=Depends(get_db)):
        if not settings.allow_registration: raise HTTPException(403, 'Registration is closed. Contact your workspace owner.')
        consume(db, f'register:{rate_identity(request.client.host)}:{now()[:13]}', settings.register_ip_hourly_limit,
                message='Too many workspaces created from this address. Try again later.')
        workspace = Workspace(name=payload.name)
        db.add(workspace)
        db.flush()
        user = User(workspace_id=workspace.id, email=payload.email.lower().strip(), name=payload.name.strip(), password_hash=hash_password(payload.password))
        db.add(user)
        try: db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Unable to register this email. Try signing in.')
        view = start_session(db, user, response, request)
        if mailer.configured:
            # The account exists and is committed. A transport failure here must not undo
            # a registration that succeeded; the person can ask for the link again.
            try:
                send_verification(db, user)
            except Exception as problem:
                logger.warning('verification mail undelivered',
                               extra={'context': {'purpose': EMAIL_PURPOSE,
                                                  'error_type': type(problem).__name__}})
        return view

    @app.post('/api/v1/auth/login')
    def login(payload: Credentials, request: Request, response: Response, db=Depends(get_db)):
        # Two independent limits (action plan P04). The address limit is generous because a
        # shared network is one address; the account limit is what actually bounds guessing
        # against one person, including from many addresses.
        email = payload.email.lower().strip()
        consume(db, f'login-ip:{rate_identity(request.client.host)}:{now()[:13]}', settings.login_ip_hourly_limit,
                message='Too many sign-in attempts from this address. Try again later.')
        consume(db, f'login-account:{rate_identity(email)}:{now()[:13]}', settings.login_account_hourly_limit,
                message='Too many sign-in attempts for this account. Try again later.')
        user = db.query(User).filter_by(email=email).first()
        if not user or user.disabled_at:
            dummy_verify(payload.password)   # equalise timing; the account may not exist
            raise HTTPException(401, 'Email or password is incorrect.')
        ok, needs_rehash = verify_password(payload.password, user.password_hash)
        if not ok:
            raise HTTPException(401, 'Email or password is incorrect.')
        if needs_rehash:
            # OWASP's transition: upgrade the stored hash during a correct sign-in, so no
            # existing user is locked out and nobody has to reset a password (P02).
            user.password_hash = hash_password(payload.password)
            audit(db, user, 'auth.password_rehashed')
        return start_session(db, user, response, request)

    @app.get('/api/v1/auth/me')
    def me(user=Depends(current_user)): return user_view(user)

    @app.post('/api/v1/auth/logout')
    def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
        db.query(Session).filter_by(token_hash=token_hash(request.cookies.get('trendsell_session',''))).delete()
        audit(db,user,'auth.logout')
        db.commit()
        response.delete_cookie('trendsell_session', path='/api')
        return {'status':'signed_out'}


    # --- Account recovery and session management (action plan P03) ---------------------
    #
    # Nothing here sends mail unless a transport is configured. Tests use the local sink;
    # production can use the TLS-enforced SMTP transport after its sending identity,
    # credentials, DNS authentication and delivery monitoring are verified.
    #
    # Review finding R02 made this urgent rather than merely planned: a normalisation bug
    # locked valid accounts out, and there was no way for an affected person to get back
    # in without an operator editing the database.

    mailer = mail.build(settings)
    app.state.mailer = mailer
    #: Short, because a reset link is a bearer credential sitting in an inbox.
    RESET_TTL_MINUTES = 30
    RESET_PURPOSE = 'password_reset'
    EMAIL_TTL_HOURS = 24
    EMAIL_PURPOSE = 'email_verification'

    def action_url(path, token):
        """A browser link whose bearer credential stays out of HTTP access logs.

        URL fragments are handled only by the browser, so reverse proxies never receive
        the token. The first explicit CORS origin is the safe default for single-origin
        deployments; PUBLIC_APP_URL selects the canonical UI in multi-origin setups.
        """
        base = (settings.public_app_url or settings.origins[0]).rstrip('/')
        return f'{base}/{path}#token={token}'

    def client_label(request):
        """A short, non-identifying hint so a person can recognise their own session."""
        if request is None:
            return None
        agent = (request.headers.get('user-agent') or '').strip()
        return agent[:120] or None

    def issue_token(db, user, purpose, expires_at):
        """Mint one credential after invalidating older ones for the same purpose."""
        # Every operation that can change account credentials locks this one stable row
        # first. PostgreSQL then gives reset issuance, redemption and password changes a
        # single order. SQLite serializes writes itself; the same code remains portable.
        user = db.execute(select(User).where(User.id == user.id).with_for_update()).scalar_one()
        # Any outstanding token is spent: asking for a new link invalidates the old one,
        # so a forwarded or leaked earlier mail stops working.
        db.query(RecoveryToken).filter_by(user_id=user.id, purpose=purpose,
                                          used_at=None).update({'used_at': now()})
        token = secrets.token_urlsafe(32)
        db.add(RecoveryToken(
            token_hash=token_hash(token), user_id=user.id, purpose=purpose,
            expires_at=expires_at,
            created_at=now()))
        return token

    def issue_reset(db, user):
        return issue_token(db, user, RESET_PURPOSE,
                           (datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)).isoformat())

    def send_verification(db, user):
        """Create and deliver a verification credential through the configured transport."""
        token = issue_token(db, user, EMAIL_PURPOSE,
                            (datetime.now(timezone.utc) + timedelta(hours=EMAIL_TTL_HOURS)).isoformat())
        audit(db, user, 'auth.email_verification_requested')
        db.commit()
        mailer.send(mail.Message(
            to=user.email, purpose=EMAIL_PURPOSE, subject='Verify your TrendSell email',
            body=('Verify that you control this address for your TrendSell workspace.\n\n'
                  f'Open verification: {action_url("verify-email", token)}\n\n'
                  f'Verification token: {token}\n\n'
                  f'It can be used once, and expires in {EMAIL_TTL_HOURS} hours.')))

    def revoke_sessions(db, user, keep=None):
        """End every session for this user, optionally sparing the one in hand."""
        query = db.query(Session).filter_by(user_id=user.id)
        if keep:
            query = query.filter(Session.token_hash != keep)
        return query.delete(synchronize_session=False)

    @app.post('/api/v1/auth/recovery/request', status_code=202)
    def request_recovery(payload: RecoveryRequest, request: Request, db=Depends(get_db)):
        """Start a password reset. Always answers the same way.

        The response cannot depend on whether the account exists, whether it has a
        deliverable address, or whether sending worked — any of those would turn this
        endpoint into an account-existence oracle. What varies is what happens behind it.
        """
        email = payload.email.lower().strip()
        # Two limits, matching sign-in: the address bound stops bulk probing, the account
        # bound stops someone flooding one person's inbox from many addresses.
        consume(db, f'recover-ip:{rate_identity(request.client.host)}:{now()[:13]}', settings.register_ip_hourly_limit,
                message='Too many recovery requests from this address. Try again later.')
        consume(db, f'recover-account:{rate_identity(email)}:{now()[:13]}', settings.login_account_hourly_limit,
                message='Too many recovery requests. Check your inbox, or try again later.')
        # A removed member is not a recoverable account. Treat it exactly like an unknown
        # address: the public response stays identical, but no useless credential or mail
        # is created for an identity that still cannot sign in. A fresh owner invitation
        # is the only path that deliberately reactivates suspended membership.
        user = db.query(User).filter_by(email=email, disabled_at=None).first()
        if user and mailer.configured:
            token = issue_reset(db, user)
            audit(db, user, 'auth.recovery_requested')
            db.commit()
            try:
                mailer.send(mail.Message(
                    to=user.email, purpose=RESET_PURPOSE,
                    subject='Reset your TrendSell password',
                    body=('Someone asked to reset the password for this TrendSell workspace.\n\n'
                          f'Open password reset: {action_url("reset-password", token)}\n\n'
                          f'Reset token: {token}\n\n'
                          f'It can be used once, and expires in {RESET_TTL_MINUTES} minutes.\n'
                          'If this was not you, no action is needed: nothing has changed.')))
            except Exception as problem:
                # Log the failure and still answer identically. A delivery outage must not
                # become an enumeration signal. Provider transports should report delivery
                # failure before accepting a message; the credential expires quickly and a
                # later request supersedes it.
                logger.warning('recovery mail undelivered',
                               extra={'context': {'purpose': RESET_PURPOSE,
                                                  'error_type': type(problem).__name__}})
        elif user:
            # A real account, but nothing can carry the token. Recorded so an operator can
            # see that recovery is being asked for while delivery is unconfigured.
            logger.warning('recovery requested with no mail transport',
                           extra={'context': {'purpose': RESET_PURPOSE}})
        return {'status': 'accepted',
                'detail': ('If that address has a workspace and delivery succeeds, reset instructions will arrive.'
                           if mailer.configured else
                           'No mail transport is configured. Ask an operator for a reset token.'),
                'delivery_configured': mailer.configured}

    @app.post('/api/v1/auth/recovery/reset')
    def reset_password(payload: PasswordReset, db=Depends(get_db)):
        """Redeem a reset token, then end every session the account had."""
        digest = token_hash(payload.token)
        row = db.get(RecoveryToken, digest)
        # One message for every failure mode: expired, already used, wrong purpose, or
        # never existed. Distinguishing them tells an attacker which guess was close.
        if not row or row.used_at or row.purpose != RESET_PURPOSE or row.expires_at <= now():
            raise HTTPException(400, 'This reset link is no longer valid. Request a new one.')
        # Read the token only to find the account, then serialize all security changes on
        # that account before atomically claiming this particular credential.
        user = db.execute(select(User).where(User.id == row.user_id).with_for_update()).scalar_one_or_none()
        if not user:
            raise HTTPException(400, 'This reset link is no longer valid. Request a new one.')
        changed_at = now()
        claimed = db.execute(
            update(RecoveryToken)
            .where(RecoveryToken.token_hash == digest,
                   RecoveryToken.user_id == user.id,
                   RecoveryToken.purpose == RESET_PURPOSE,
                   RecoveryToken.used_at.is_(None),
                   RecoveryToken.expires_at > changed_at)
            .values(used_at=changed_at))
        if claimed.rowcount != 1:
            db.rollback()
            raise HTTPException(400, 'This reset link is no longer valid. Request a new one.')
        user.password_hash = hash_password(payload.password)
        # A reset proves possession of a reset credential, not necessarily control of the
        # account's email address. This distinction matters while the operator procedure
        # may deliver a token through a separately trusted channel. Only the dedicated
        # email-verification credential may set `email_verified_at`.
        # A successful security change invalidates every other recovery credential.
        db.query(RecoveryToken).filter(RecoveryToken.user_id == user.id,
                                       RecoveryToken.used_at.is_(None)).update(
                                           {'used_at': changed_at}, synchronize_session=False)
        # Whoever prompted the reset may be holding a stolen session. Ending all of them,
        # including this browser's, is the point of a reset.
        revoked = revoke_sessions(db, user)
        audit(db, user, 'auth.password_reset', sessions_revoked=revoked)
        db.commit()
        return {'status': 'password_reset', 'sessions_revoked': revoked}

    @app.post('/api/v1/auth/email-verification/request', status_code=202)
    def request_email_verification(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if user.email_verified_at:
            return {'status': 'already_verified', 'delivery_configured': mailer.configured}
        consume(db, f'verify-ip:{rate_identity(request.client.host)}:{now()[:13]}', settings.register_ip_hourly_limit,
                message='Too many verification requests from this address. Try again later.')
        consume(db, f'verify-account:{user.id}:{now()[:13]}', settings.login_account_hourly_limit,
                message='Too many verification requests. Check your inbox, or try again later.')
        if mailer.configured:
            try:
                send_verification(db, user)
            except Exception as problem:
                logger.warning('verification mail undelivered',
                               extra={'context': {'purpose': EMAIL_PURPOSE,
                                                  'error_type': type(problem).__name__}})
        return {'status': 'accepted', 'delivery_configured': mailer.configured}

    @app.post('/api/v1/auth/email-verification/confirm')
    def confirm_email(payload: VerificationConfirm, db=Depends(get_db)):
        digest = token_hash(payload.token)
        credential = db.get(RecoveryToken, digest)
        if not credential or credential.used_at or credential.purpose != EMAIL_PURPOSE or credential.expires_at <= now():
            raise HTTPException(400, 'This verification link is no longer valid. Request a new one.')
        user = db.execute(select(User).where(User.id == credential.user_id).with_for_update()).scalar_one_or_none()
        if not user:
            raise HTTPException(400, 'This verification link is no longer valid. Request a new one.')
        verified_at = now()
        claimed = db.execute(update(RecoveryToken).where(
            RecoveryToken.token_hash == digest, RecoveryToken.user_id == user.id,
            RecoveryToken.purpose == EMAIL_PURPOSE, RecoveryToken.used_at.is_(None),
            RecoveryToken.expires_at > verified_at).values(used_at=verified_at))
        if claimed.rowcount != 1:
            db.rollback()
            raise HTTPException(400, 'This verification link is no longer valid. Request a new one.')
        user.email_verified_at = verified_at
        audit(db, user, 'auth.email_verified')
        db.commit()
        return {'status': 'email_verified', 'email_verified_at': verified_at}

    # --- Controlled workspace intake and membership ---------------------------------

    INVITATION_TTL_DAYS = 7

    def invitation_view(row):
        return {'id': row.id, 'email': row.email, 'role': row.role,
                'created_at': row.created_at, 'expires_at': row.expires_at,
                'sent_at': row.sent_at, 'accepted_at': row.accepted_at,
                'revoked_at': row.revoked_at}

    @app.get('/api/v1/workspace/members')
    def workspace_members(user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        members = (db.query(User).filter_by(workspace_id=user.workspace_id, disabled_at=None)
                   .order_by(User.email.asc()).all())
        invitations = (db.query(Invitation).filter_by(workspace_id=user.workspace_id)
                       .filter(Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
                               Invitation.expires_at > now())
                       .order_by(Invitation.created_at.desc()).all())
        return {'members': [user_view(member) for member in members],
                'invitations': [invitation_view(invitation) for invitation in invitations]}

    @app.post('/api/v1/workspace/invitations', status_code=201)
    def invite_member(payload: InvitationCreate,
                      user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        if not mailer.configured:
            raise HTTPException(503, 'Outbound mail is not configured. Configure delivery before inviting members.')
        email = payload.email.lower().strip()
        consume(db, f'invite-workspace:{user.workspace_id}:{now()[:13]}',
                settings.invitation_workspace_hourly_limit,
                message='This workspace has sent too many invitations. Try again later.')
        consume(db, f'invite-email:{rate_identity(email)}:{now()[:10]}',
                settings.invitation_email_daily_limit,
                message='Too many invitations were sent to this address. Try again later.')
        # Do not make this owner-only endpoint an account-existence oracle. An address
        # that already belongs to another workspace gets the same pending invitation and
        # delivery behavior as any other address. The recipient already controls the
        # mailbox; acceptance can safely explain that one account cannot join two
        # workspaces while the current one-workspace data model is in place.
        # Lock a row that always exists before testing the invitation unique key. This
        # serializes first-time invitations too; locking an absent invitation row cannot.
        db.execute(select(Workspace).where(Workspace.id == user.workspace_id)
                   .with_for_update()).scalar_one()
        token = secrets.token_urlsafe(32)
        invitation = (db.query(Invitation)
                      .filter_by(workspace_id=user.workspace_id, email=email)
                      .with_for_update().first())
        values = {
            'role': payload.role,
            'token_hash': token_hash(token),
            'invited_by': user.id,
            'expires_at': (datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS)).isoformat(),
            'created_at': now(), 'sent_at': None, 'accepted_at': None, 'revoked_at': None,
        }
        if invitation:
            for field, value in values.items():
                setattr(invitation, field, value)
        else:
            invitation = Invitation(workspace_id=user.workspace_id, email=email, **values)
            db.add(invitation)
        audit(db, user, 'workspace.invitation_created', role=payload.role)
        db.commit()
        try:
            mailer.send(mail.Message(
                to=email, purpose='workspace_invitation', subject='Join a TrendSell workspace',
                body=('You were invited to a TrendSell workspace.\n\n'
                      f'Open invitation: {action_url("accept-invitation", token)}\n\n'
                      f'Invitation token: {token}\n\n'
                      f'It can be used once and expires in {INVITATION_TTL_DAYS} days. '
                      'If you were not expecting this invitation, no action is needed.')))
        except Exception as problem:
            logger.warning('invitation mail undelivered', extra={'context': {
                'purpose': 'workspace_invitation', 'error_type': type(problem).__name__}})
            raise HTTPException(503, 'The invitation was created but could not be delivered. Try sending it again.')
        invitation.sent_at = now()
        db.commit()
        return invitation_view(invitation)

    @app.delete('/api/v1/workspace/invitations/{invitation_id}')
    def revoke_invitation(invitation_id: str,
                          user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        invitation = (db.query(Invitation)
                      .filter_by(id=invitation_id, workspace_id=user.workspace_id)
                      .with_for_update().first())
        if not invitation or invitation.accepted_at:
            raise HTTPException(404, 'Pending invitation not found in this workspace.')
        invitation.revoked_at = now()
        audit(db, user, 'workspace.invitation_revoked', role=invitation.role)
        db.commit()
        return {'status': 'revoked'}

    @app.post('/api/v1/auth/invitations/accept', status_code=201)
    def accept_invitation(payload: InvitationAccept, request: Request, response: Response,
                          db=Depends(get_db)):
        invitation = db.execute(
            select(Invitation).where(Invitation.token_hash == token_hash(payload.token))
            .with_for_update()).scalar_one_or_none()
        if (not invitation or invitation.accepted_at or invitation.revoked_at
                or invitation.expires_at <= now()):
            raise HTTPException(400, 'This invitation is no longer valid. Ask the workspace owner to send another.')
        existing = db.execute(select(User).where(User.email == invitation.email)
                              .with_for_update()).scalar_one_or_none()
        if existing and not (existing.disabled_at
                             and existing.workspace_id == invitation.workspace_id):
            raise HTTPException(409, 'That email already belongs to a TrendSell account.')
        if existing:
            member = existing
            member.name = payload.name
            member.password_hash = hash_password(payload.password)
            member.role = invitation.role
            member.email_verified_at = now()
            member.disabled_at = None
        else:
            member = User(workspace_id=invitation.workspace_id, email=invitation.email,
                          name=payload.name, password_hash=hash_password(payload.password),
                          role=invitation.role, email_verified_at=now())
            db.add(member)
        invitation.accepted_at = now()
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'That email already belongs to a TrendSell account.')
        audit(db, member, 'workspace.invitation_accepted', role=invitation.role)
        return start_session(db, member, response, request)

    @app.post('/api/v1/workspace/members/{member_id}/role')
    def change_member_role(member_id: str, payload: MemberRoleChange,
                           user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        member = db.execute(select(User).where(
            User.id == member_id, User.workspace_id == user.workspace_id,
            User.disabled_at.is_(None)).with_for_update()).scalar_one_or_none()
        if not member:
            raise HTTPException(404, 'Member not found in this workspace.')
        if member.id == user.id or member.role == 'owner':
            raise HTTPException(409, 'The workspace owner role cannot be changed here.')
        previous = member.role
        member.role = payload.role
        audit(db, user, 'workspace.member_role_changed', member_id=member.id,
              from_role=previous, to_role=payload.role)
        db.commit()
        return user_view(member)

    @app.delete('/api/v1/workspace/members/{member_id}')
    def remove_member(member_id: str,
                      user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        """Revoke a non-owner's access while retaining their audit identity."""
        member = db.execute(select(User).where(
            User.id == member_id, User.workspace_id == user.workspace_id,
            User.disabled_at.is_(None)).with_for_update()).scalar_one_or_none()
        if not member:
            raise HTTPException(404, 'Member not found in this workspace.')
        if member.id == user.id or member.role == 'owner':
            raise HTTPException(409, 'The workspace owner cannot be removed here.')
        revoked = revoke_sessions(db, member)
        db.query(RecoveryToken).filter(
            RecoveryToken.user_id == member.id,
            RecoveryToken.used_at.is_(None)).update({'used_at': now()}, synchronize_session=False)
        member.disabled_at = now()
        audit(db, user, 'workspace.member_removed', member_id=member.id,
              role=member.role, sessions_revoked=revoked)
        db.commit()
        return {'status': 'removed', 'sessions_revoked': revoked}

    @app.post('/api/v1/auth/password')
    def change_password(payload: PasswordChange, request: Request, user=Depends(current_user), db=Depends(get_db)):
        """Change a password while signed in, keeping only the session doing it."""
        user = db.execute(select(User).where(User.id == user.id).with_for_update()).scalar_one()
        ok, _ = verify_password(payload.current_password, user.password_hash)
        if not ok:
            raise HTTPException(403, 'Current password is incorrect.')
        if payload.new_password == payload.current_password:
            raise HTTPException(400, 'The new password must be different from the current one.')
        user.password_hash = hash_password(payload.new_password)
        db.query(RecoveryToken).filter(RecoveryToken.user_id == user.id,
                                       RecoveryToken.used_at.is_(None)).update(
                                           {'used_at': now()}, synchronize_session=False)
        current = token_hash(request.cookies.get('trendsell_session', ''))
        revoked = revoke_sessions(db, user, keep=current)
        audit(db, user, 'auth.password_changed', sessions_revoked=revoked)
        db.commit()
        return {'status': 'password_changed', 'sessions_revoked': revoked}

    @app.get('/api/v1/auth/sessions')
    def list_sessions(request: Request, user=Depends(current_user), db=Depends(get_db)):
        """The sessions this account has open. Never returns a token or a hash of one."""
        current = token_hash(request.cookies.get('trendsell_session', ''))
        rows = (db.query(Session).filter_by(user_id=user.id)
                  .filter(Session.expires_at > now()).order_by(Session.created_at.desc()).all())
        return {'sessions': [{'id': uid_for_session(row), 'started_at': row.created_at,
                              'expires_at': row.expires_at, 'client': row.client,
                              'current': row.token_hash == current} for row in rows],
                'total': len(rows)}

    def uid_for_session(row):
        """A stable handle for one session that is not its token hash.

        The hash verifies a bearer token; handing it to the browser would put a
        password-equivalent value in a list view. This is derived from it, one way, so it
        can address a session without being able to authenticate one.
        """
        return hashlib.sha256(f'session-handle:{row.token_hash}'.encode()).hexdigest()[:32]

    @app.delete('/api/v1/auth/sessions/{handle}')
    def revoke_session(handle: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
        """Revoke one session by its handle. Only ever the caller's own."""
        rows = db.query(Session).filter_by(user_id=user.id).all()
        target = next((row for row in rows if uid_for_session(row) == handle), None)
        if not target:
            raise HTTPException(404, 'That session is not open on this account.')
        was_current = target.token_hash == token_hash(request.cookies.get('trendsell_session', ''))
        db.delete(target)
        audit(db, user, 'auth.session_revoked', was_current=was_current)
        db.commit()
        return {'status': 'revoked', 'was_current': was_current}

    @app.delete('/api/v1/auth/account')
    def delete_account(payload: AccountDeletion, response: Response,
                       user=Depends(permitted('workspace.admin')), db=Depends(get_db)):
        """Delete an owner-only workspace after password and phrase confirmation."""
        user = db.execute(select(User).where(User.id == user.id).with_for_update()).scalar_one()
        ok, _ = verify_password(payload.password, user.password_hash)
        if not ok:
            raise HTTPException(403, 'Password is incorrect.')
        workspace = db.execute(select(Workspace).where(
            Workspace.id == user.workspace_id).with_for_update()).scalar_one()
        expected = f'DELETE {workspace.name}'
        if payload.confirmation != expected:
            raise HTTPException(422, f'Type {expected} exactly to delete this workspace.')
        workspace_id = user.workspace_id
        # Active members must be explicitly removed first so the owner cannot silently
        # erase their access and shared data. Suspended identities remain only to preserve
        # audit attribution and must not make the workspace impossible to delete.
        active_others = db.query(User).filter(
            User.workspace_id == workspace_id, User.id != user.id,
            User.disabled_at.is_(None)).count()
        if active_others:
            raise HTTPException(409, 'This workspace has other members. Deleting a shared '
                                     'workspace requires removing them first.')
        members = db.query(User).filter_by(workspace_id=workspace_id).all()
        member_ids = [member.id for member in members]
        rate_fragments = []
        for member in members:
            rate_fragments.append(rate_identity(member.email))
            # Buckets written before RATE_KEY_SECRET was introduced used a plain SHA-256
            # address digest. Remove that transition format too instead of retaining it
            # until the next expiry sweep after a workspace deletion.
            rate_fragments.append(token_hash(member.email))
        try:
            entry = deletion_register.record(
                workspace_id=workspace_id, member_ids=member_ids,
                rate_fragments=rate_fragments, requested_at=now(),
                request_id=REQUEST_ID.get())
        except DeletionRegisterError as error:
            db.rollback()
            raise HTTPException(503, str(error))
        delete_workspace_rows(db, entry)
        db.commit()
        response.delete_cookie('trendsell_session', path='/api')
        logger.info('workspace deleted', extra={'context': {
            'records_retained': 0, 'deletion_event_id': entry['event_id']}})
        return {'status': 'deleted'}

    @app.get('/api/v1/data-health')
    def data_health(user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        statuses = {row.key: row.payload for row in records(db,user,'source_status').all()}
        presented = []
        for source in SOURCES:
            if source['id'] == 'amazon':
                if not settings.amazon_creators_enabled:
                    state = {'status':'unconfigured', 'reason':source['reason'],
                             'next_retry':'After server-side connection and source review'}
                elif amazon_missing:
                    state = {'status':'misconfigured',
                             'reason':'The Amazon Creators API connection is enabled but missing: '
                                      + ', '.join(amazon_missing) + '.',
                             'next_retry':'After the missing server-side configuration is installed'}
                else:
                    state = statuses.get('amazon', {
                        'status':'configured', 'last_success':None, 'last_attempt':None,
                        'reason':'Amazon Creators API is configured. No collection attempt has completed in this workspace.',
                        'next_retry':'On the next user-requested product check'})
            else:
                state = {'status':'unconfigured', 'reason':source['reason'],
                         'next_retry':'After connection and source review'}
            rights = (settings.amazon_creators_usage_rights
                      if source['id'] == 'amazon' and amazon_configured else source['rights'])
            presented.append({**source, 'rights':rights, 'last_success':None, 'last_attempt':None,
                              'freshness_hours':1 if source['id'] == 'amazon' else 24, **state})
        connected = [source for source in presented if source['status'] == 'connected']
        return {'sources':presented, 'market':'NG',
                'coverage':None if not connected else len(connected) / len(presented) * 100,
                'truth_state':'Observed' if connected else 'Unavailable'}

    @app.get('/api/v1/products')
    def products(search: str = Query(default='', max_length=200), limit: int = DEFAULT_LIMIT,
                 cursor: str | None = None, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        rows, page = paginate(searched(records(db,user,'product'), search, ['name','asin']), limit, cursor)
        return {'products':with_latest_assessment(db,user,rows), **page}

    @app.get('/api/v1/products/{product_id}')
    def product(product_id: str, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        body = with_latest_assessment(db,user,[owned(db,user,'product',product_id)])[0]
        reading, gate, _ = evidence_gate(db,user,product_id)
        # Evidence status is derived from the records, never stored as an opinion (D03).
        return {**body, 'confidence': reading['confidence'], 'evidence_quality': reading,
                'compliance': gate, 'observations': evidence_records(db,user,product_id),
                'decision': 'INSUFFICIENT EVIDENCE' if not reading['coverage'] else body['decision'],
                'blocker': reading['limitations'][0] if reading['limitations'] else body.get('blocker')}

    def evidence_records(db, user, product_id):
        """Every evidence record for one product, oldest first."""
        rows = (records(db,user,'evidence')
                .filter(Record.payload['product_id'].as_string() == product_id)
                .order_by(Record.created_at.asc()).all())
        return [serialize(row) for row in rows]

    def product_reviews(db, user, product_id):
        """Every import-readiness review for one product, oldest first."""
        rows = (records(db,user,'compliance_review')
                .filter(Record.payload['product_id'].as_string() == product_id)
                .order_by(Record.created_at.asc()).all())
        return [serialize(row) for row in rows]

    def latest_review(db, user, product_id):
        """The newest review record of any status — including one still waiting."""
        rows = product_reviews(db, user, product_id)
        return rows[-1] if rows else None

    def governing_review(db, user, product_id):
        """The review that decides the gate: the newest one a reviewer actually decided.

        Review finding E03: the gate read the newest review record *of any status*, so
        merely asking for another review outranked a decision. Anyone holding
        `workspace.write` could therefore erase a reviewer's rejection from every later
        assessment — the gate fell back to `requested` and the "a reviewer rejected this
        product" blocker disappeared — without any reviewer involved.

        A pending request is a question, not an answer. The last answer stands until a
        reviewer gives a new one; `compliance_state` still shows the pending request
        alongside it, so nothing is hidden.
        """
        decided = [review for review in product_reviews(db, user, product_id)
                   if review.get('status') in cmp.DECIDED_STATUSES]
        return decided[-1] if decided else None

    def gate_review(db, user, product_id):
        """What the gate is computed from, and whether a re-review is waiting.

        With no decision yet the pending request is itself the state to report, so a
        product whose first review is still open reads `requested` rather than `none`.
        """
        # Stored review records cannot silently keep an actionable gate enabled after the
        # release scope disables the feature. They remain in exports/history, but no
        # decision calculation treats them as current professional approval.
        if not settings.import_review_enabled:
            return None, False
        latest = latest_review(db, user, product_id)
        governing = governing_review(db, user, product_id)
        pending = bool(latest and latest.get('status') == 'requested'
                       and (not governing or governing['id'] != latest['id']))
        return (governing or latest), pending

    def evidence_gate(db, user, product_id):
        """The gate inputs, computed on the server from stored records (action plan D03).

        Nothing a client sends can raise confidence, assert coverage, or resolve
        compliance: each comes from records this workspace actually holds.
        """
        review, re_review_pending = gate_review(db, user, product_id)
        gate = cmp.gate_state(review)
        if re_review_pending:
            # Visible, but not in charge: the standing decision still governs (E03).
            gate = {**gate, 're_review_pending': True}
        reading = quality(evidence_records(db, user, product_id), gate['resolved'])
        # The reviewed state itself, not merely whether it resolved the gate. A rejection
        # is authoritative and decides the assessment; under the previous thresholds it
        # reached the screen and never reached the calculation (review finding R04).
        reading['compliance_status'] = gate['status']
        return reading, gate, review

    @app.get('/api/v1/products/{product_id}/evidence')
    @app.get('/api/v1/products/{product_id}/timeline')
    def evidence(product_id: str, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        owned(db,user,'product',product_id)
        stored = evidence_records(db,user,product_id)
        reading, gate, _ = evidence_gate(db,user,product_id)
        truth_states = {record.get('truth_state') for record in stored}
        if not stored:
            summary_truth = 'Unavailable'
            summary_reason = 'No evidence has been recorded and no approved collector has produced an observation.'
        elif truth_states == {'Observed'}:
            summary_truth = 'Observed'
            summary_reason = ('Every current evidence record was produced by a connected, authorised collector. '
                              'Its source, collection time, parser, and retained snapshot remain inspectable.')
        elif truth_states == {MANUAL_TRUTH_STATE}:
            summary_truth = MANUAL_TRUTH_STATE
            summary_reason = ('These records were entered by people in this workspace. No approved collector '
                              'has produced an observation for this product.')
        else:
            # Use the least-authoritative state for the collection summary. Individual
            # records retain their own labels, so observed and manual provenance remain
            # distinguishable without presenting the whole collection as observed.
            summary_truth = MANUAL_TRUTH_STATE
            summary_reason = ('This product has both collector-produced observations and records entered by '
                              'people in this workspace. Inspect each record for its own provenance.')
        return {'observations': stored,
                'truth_state': summary_truth, 'reason': summary_reason,
                'quality': reading, 'compliance': gate, 'metrics': METRICS}

    @app.post('/api/v1/products/{product_id}/evidence', status_code=201)
    def record_evidence(product_id: str, payload: EvidenceRequest,
                        user=Depends(permitted('evidence.submit')), db=Depends(get_db)):
        """Record one dated observation a person made.

        The truth state is set here, not by the caller: a typed number is user input, and
        only a connected authorised collector could make it an observation (E06).
        """
        owned(db,user,'product',product_id)
        consume(db, f'evidence:{user.workspace_id}:{now()[:16]}', settings.workspace_write_minute_limit,
                message='This workspace is recording evidence too quickly. Try again in a moment.')
        row = insert(db,user,'evidence', {**payload.model_dump(), 'product_id': product_id,
                                          'truth_state': MANUAL_TRUTH_STATE, 'verification': 'Unverified',
                                          'input_author': user.id, 'recorded_at': now(),
                                          'method_version': METHOD_VERSION})
        audit(db,user,'evidence.recorded',row.id,product_id=product_id,metric=payload.metric,
              market=payload.market,observed_at=payload.observed_at)
        db.commit()
        return serialize(row)

    @app.delete('/api/v1/products/{product_id}/evidence/{evidence_id}')
    def withdraw_evidence(product_id: str, evidence_id: str,
                          user=Depends(permitted('evidence.submit')), db=Depends(get_db)):
        """Withdraw a record entered in error. Assessments that referenced it keep their
        own snapshot, so history does not change."""
        owned(db,user,'product',product_id)
        row = owned(db,user,'evidence',evidence_id)
        if row.payload.get('product_id') != product_id:
            raise HTTPException(404, 'Record not found in this workspace.')
        audit(db,user,'evidence.withdrawn',row.id,product_id=product_id,metric=row.payload.get('metric'))
        db.delete(row)
        db.commit()
        return {'status':'withdrawn'}

    # --- Import-readiness review (action plan N02, N03) ---------------------------

    @app.get('/api/v1/products/{product_id}/compliance')
    def compliance_state(product_id: str, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        if not settings.import_review_enabled:
            raise HTTPException(404, 'Import review is not enabled for this release scope.')
        owned(db,user,'product',product_id)
        review, re_review_pending = gate_review(db,user,product_id)
        gate = cmp.gate_state(review)
        if re_review_pending:
            gate = {**gate, 're_review_pending': True}
        history = list(reversed(product_reviews(db,user,product_id)))
        # `current` is the newest record, so a request waiting for a reviewer is still
        # shown as such even while an earlier decision governs the gate (E03).
        current = latest_review(db,user,product_id)
        # This capability is request-specific, not merely role-specific. Owners normally
        # hold review permission, but the requester must never be invited by the UI to
        # decide their own review only to be rejected by the write endpoint.
        can_review = bool(current and current.get('status') == 'requested'
                          and current.get('requested_by') != user.id
                          and permissions_granted(user, 'compliance.review'))
        return {'gate': gate, 'current': current, 'history': history,
                'can_review': can_review,
                'review_version': cmp.REVIEW_VERSION}

    @app.post('/api/v1/products/{product_id}/compliance/requests', status_code=201)
    def request_review(product_id: str, payload: cmp.ReviewRequest,
                       user=Depends(permitted('workspace.write')), db=Depends(get_db)):
        """Ask a reviewer to resolve import readiness, with the context they need."""
        if not settings.import_review_enabled:
            raise HTTPException(404, 'Import review is not enabled for this release scope.')
        product = owned(db,user,'product',product_id)
        if payload.product_id != product_id:
            raise HTTPException(422, 'The request must name the product it is filed against.')
        current = latest_review(db,user,product_id)
        if current and current['status'] == 'requested':
            raise HTTPException(409, 'A review is already waiting for this product.')
        row = insert(db,user,'compliance_review', {
            **payload.model_dump(), 'product_id': product_id, 'product_name': product.payload.get('name'),
            'status': 'requested', 'requested_by': user.id, 'requested_at': now(),
            'supersedes': current['id'] if current else None, 'superseded_by': None,
            'review_version': cmp.REVIEW_VERSION})
        if current:
            current_row = owned(db,user,'compliance_review',current['id'])
            current_row.payload = {**current_row.payload, 'superseded_by': row.id}
        audit(db,user,'compliance.review_requested',row.id,product_id=product_id,
              hs_code_candidate=payload.hs_code_candidate or None)
        db.commit()
        return serialize(row)

    @app.post('/api/v1/compliance/reviews/{review_id}/decision')
    def decide_review(review_id: str, payload: cmp.ReviewDecision,
                      user=Depends(permitted('compliance.review')), db=Depends(get_db)):
        """A reviewer's decision. Only this permission can resolve the compliance gate.

        The review row is locked before its status is read. Without the lock two decisions
        submitted at the same moment -- two reviewers, or one double submission -- both saw
        `requested`, both returned 200, and the later commit silently replaced the earlier
        decision: a rejection could be overwritten by an approval that then resolved the
        gate, leaving two `compliance.reviewed` events on one review. A decision is the
        one thing in this product that must not be lost to a race.
        """
        if not settings.import_review_enabled:
            raise HTTPException(404, 'Import review is not enabled for this release scope.')
        # The lock IS the read: fetching the row first and locking it afterwards would let
        # the ORM hand back the already-loaded (pre-lock) instance, so the status check
        # could still run against a stale payload. The workspace filter keeps this the
        # same 404 another workspace has always received.
        row = db.execute(select(Record)
                         .where(Record.id == review_id,
                                Record.workspace_id == user.workspace_id,
                                Record.kind == 'compliance_review')
                         .with_for_update()
                         .execution_options(populate_existing=True)).scalar_one_or_none()
        if not row:
            raise HTTPException(404, 'Record not found in this workspace.')
        if row.payload['status'] != 'requested':
            raise HTTPException(409, 'This review has already been decided. Request a new review instead.')
        if row.payload.get('requested_by') == user.id:
            raise HTTPException(403, 'A compliance review must be decided by a different workspace reviewer.')
        sources = [source.model_dump() for source in payload.sources]
        if payload.status == 'approved':
            # The dates are not decoration: an approval has to rest on a publication that
            # applies today, and it lapses when that publication does (R03).
            supported, reason = cmp.approval_support(sources)
            if not supported:
                raise HTTPException(422, reason)
        decided = {**row.payload, 'status': payload.status, 'rationale': payload.rationale,
                   'hs_code': payload.hs_code, 'requirements': payload.requirements,
                   'no_additional_requirements': payload.no_additional_requirements,
                   'sources': sources, 'reviewer_id': user.id, 'decided_at': now(),
                   'expires_at': cmp.approval_expiry(payload.validity_days, sources)
                                 if payload.status == 'approved' else None}
        row.payload = decided
        audit(db,user,'compliance.reviewed',row.id,product_id=row.payload['product_id'],
              status=payload.status,hs_code=payload.hs_code or None,sources=len(payload.sources))
        db.commit()
        return serialize(row)


    def run_job(job_id, workspace_id):
        with database.session() as db:
            row = db.query(Record).filter_by(id=job_id, workspace_id=workspace_id, kind='job').one()
            p = dict(row.payload)
            product = db.query(Record).filter_by(
                id=p['product_id'], workspace_id=workspace_id, kind='product').one()
            collector = app.state.amazon_creators
            if not collector:
                detail = (f"Amazon Creators API is enabled but missing {', '.join(amazon_missing)}."
                          if settings.amazon_creators_enabled else SOURCES[0]['reason'])
                p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Amazon catalog',
                                             'status':'unavailable','detail':detail,'at':now()}]
            else:
                attempted_at = now()
                p.update(status='running')
                row.payload = p
                source_status(db, workspace_id, 'amazon', status='collecting',
                              last_attempt=attempted_at,
                              reason='A user-requested Amazon catalog collection is running.')
                db.commit()
                try:
                    collected = collector.get_item(product.payload['asin'])
                except ProviderError as problem:
                    p = dict(row.payload)
                    p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Amazon catalog',
                                                 'status':'unavailable','detail':problem.detail,
                                                 'error_code':problem.code,'at':now()}]
                    source_status(db, workspace_id, 'amazon', status='degraded',
                                  last_attempt=attempted_at, reason=problem.detail,
                                  next_retry=problem.retry_after)
                except Exception:
                    # The job must resolve even when a provider changes an undocumented
                    # response shape. Log only the class/correlation context; never the
                    # credential, token, request body, or provider response.
                    logger.exception('amazon collector failed', extra={'context': {
                        'workspace_id':workspace_id, 'job_id':job_id,
                        'error_class':'unexpected_provider_failure'}})
                    detail = 'Amazon collection failed in the source adapter. No demand observation was recorded.'
                    p = dict(row.payload)
                    p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Amazon catalog',
                                                 'status':'unavailable','detail':detail,
                                                 'error_code':'adapter_error','at':now()}]
                    source_status(db, workspace_id, 'amazon', status='degraded',
                                  last_attempt=attempted_at, reason=detail,
                                  next_retry='Retry once; review the adapter if it repeats')
                else:
                    collected_at = now()
                    provider_item = collected.pop('provider_item')
                    digest = hashlib.sha256(json.dumps(
                        provider_item, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                    requester = db.get(User, p.get('requested_by'))
                    snapshot_payload = {
                        'product_id': product.id, 'source':'Amazon Creators API',
                        'source_market':settings.amazon_creators_marketplace,
                        'observed_at':collected_at, 'collected_at':collected_at,
                        'collector_version':AMAZON_COLLECTOR_VERSION,
                        'parser_version':AMAZON_PARSER_VERSION,
                        'usage_rights':settings.amazon_creators_usage_rights,
                        'provider_request_id':collected.get('request_id'),
                        'response_sha256':digest, 'provider_item':provider_item,
                    }
                    if requester:
                        snapshot = insert(db, requester, 'source_snapshot', snapshot_payload)
                    else:
                        snapshot = Record(workspace_id=workspace_id, kind='source_snapshot',
                                          key=uid(), payload=snapshot_payload)
                        db.add(snapshot); db.flush()
                    catalog = {key:value for key,value in collected.items() if key != 'request_id'}
                    product.payload = {**product.payload,
                        'name':catalog.get('title') or product.payload['name'],
                        'category':catalog.get('category') or product.payload['category'],
                        'source_url':catalog.get('detail_page_url') or product.payload['source_url'],
                        'confirmed':True, 'confirmed_at':collected_at, 'truth_state':'Observed',
                        'identity_source':'Amazon Creators API',
                        'identity_market':settings.amazon_creators_marketplace,
                        'identity_observed_at':collected_at, 'identity_collected_at':collected_at,
                        'identity_snapshot_id':snapshot.id, 'catalog':catalog,
                        'blocker':'Collect independent demand and Nigeria local-market evidence.'}
                    observations = []
                    if catalog.get('website_sales_rank') is not None:
                        observations.append(('Marketplace rank', catalog['website_sales_rank'],
                                             'rank', catalog.get('rank_category') or 'Amazon website'))
                    if catalog.get('offer_amount') is not None and catalog.get('offer_currency'):
                        observations.append(('Marketplace price', catalog['offer_amount'],
                                             catalog['offer_currency'], 'Featured offer'))
                    for metric, value, unit, notes in observations:
                        evidence_payload = {
                            'product_id':product.id, 'metric':metric, 'value':value, 'unit':unit,
                            'market':'US', 'observed_at':collected_at,
                            'source_name':'Amazon Creators API',
                            'source_url':catalog.get('detail_page_url') or product.payload['source_url'],
                            'method':'GetItems current catalog response', 'notes':notes,
                            'truth_state':'Observed', 'verification':'Provider response',
                            'recorded_at':collected_at, 'fetched_at':collected_at,
                            'snapshot_id':snapshot.id, 'collector_version':AMAZON_COLLECTOR_VERSION,
                            'parser_version':AMAZON_PARSER_VERSION,
                            'usage_rights':settings.amazon_creators_usage_rights,
                        }
                        key = f"amazon:{product.payload['asin']}:{metric}:{collected_at[:10]}:{value}"
                        if requester:
                            insert_unique(db, requester, 'evidence', key, evidence_payload)
                    missing = [label for field,label in (
                        ('website_sales_rank','sales rank'), ('offer_amount','featured offer price'))
                               if field not in catalog]
                    detail = 'Amazon resolved the product identity and stored only supplied catalog fields.'
                    if missing:
                        detail += ' Unavailable in this response: ' + ', '.join(missing) + '.'
                    detail += ' Sales history, review velocity, and seller counts were not requested or inferred.'
                    p = dict(row.payload)
                    p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Amazon catalog',
                                                 'status':'succeeded','detail':detail,
                                                 'snapshot_id':snapshot.id,'at':collected_at}]
                    source_status(db, workspace_id, 'amazon', status='connected',
                                  last_attempt=attempted_at, last_success=collected_at,
                                  reason='The latest user-requested Amazon catalog collection succeeded.',
                                  next_retry='On the next user-requested product check')
            p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Google Trends',
                                         'status':'unavailable','detail':SOURCES[1]['reason'],'at':now()}]
            p['status'] = 'partial'
            if product.payload.get('confirmed'):
                identity_detail = 'Product identity was resolved by the authorised catalog source. Demand and destination evidence remain separate gates.'
                identity_status = 'succeeded'
            else:
                identity_detail = 'Identifier captured. Confirm the product name; source identity and demand remain unverified.'
                identity_status = 'partial'
            p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Review product identity',
                                         'status':identity_status,'detail':identity_detail,'at':now()}]
            row.payload = p
            db.commit()

    def matching_job(existing, request_hash):
        """The stored job for a reused key, or 409 when the key described another request."""
        if existing.payload['request_hash'] != request_hash:
            raise HTTPException(409,'Idempotency key was used for a different request.')
        return serialize(existing)

    def queue_job(payload, db, user, background, idempotency_key):
        identity = resolve_input(payload.input)
        request_hash = hashlib.sha256(json.dumps(payload.model_dump(),sort_keys=True).encode()).hexdigest()
        key = idempotency_key or request_hash
        if len(key)>128: raise HTTPException(422,'Idempotency key is too long.')
        existing = records(db,user,'job').filter_by(key=key).first()
        if existing:
            return matching_job(existing, request_hash)
        canonical, _ = insert_unique(db,user,'product',identity['asin'],{'name':f"Amazon product · {identity['asin']}", 'asin':identity['asin'], 'source_url':identity['url'], 'market':'NG','discovery_market':'US','confirmed':False,'truth_state':'User input','decision':'INSUFFICIENT EVIDENCE','confidence':0,'category':'Unclassified','stage':'Needs evidence','blocker':'Confirm product identity and connect a demand source.','observations':[]})
        job, created = insert_unique(db,user,'job',key,{'status':'queued','product_id':canonical.id,
            'requested_by':user.id,'request_hash':request_hash,
            'events':[{'id':1,'step':'Amazon identifier captured','status':'succeeded',
                       'detail':'Parsed from your input. No external page was fetched yet.','at':now()}]})
        if not created:
            # A concurrent request with the same key won. Converge on its job and do not
            # charge the research entitlement twice for one logical submission.
            db.commit()
            return matching_job(job, request_hash)
        # Charged only once we hold the job row. consume() commits, so a rejected quota
        # rolls the job back rather than leaving an unrunnable record behind.
        consume(db, f'research:{user.workspace_id}:{now()[:10]}', settings.research_daily_limit)
        background.add_task(run_job, job.id, user.workspace_id)
        return serialize(job)

    @app.post('/api/v1/xray', status_code=202)
    def xray(payload:XrayRequest, background:BackgroundTasks, idempotency_key: str | None=Header(default=None), user=Depends(writer), db=Depends(get_db)):
        return queue_job(payload,db,user,background,idempotency_key)

    @app.post('/api/v1/products/{product_id}/refresh', status_code=202)
    def refresh(product_id:str, background:BackgroundTasks, idempotency_key: str | None=Header(default=None), user=Depends(writer), db=Depends(get_db)):
        product = owned(db,user,'product',product_id)
        return queue_job(XrayRequest(input=product.payload['asin']),db,user,background,idempotency_key or uid())

    @app.get('/api/v1/research-jobs/{job_id}')
    def job(job_id:str, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        return serialize(owned(db,user,'job',job_id))

    @app.get('/api/v1/research-jobs/{job_id}/events')
    def events(job_id:str, last_event_id:str=Header(default='0'), user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        job = owned(db,user,'job',job_id)
        try: cursor = int(last_event_id)
        except ValueError: raise HTTPException(422,'Invalid event cursor')
        stream = ''.join(f"id: {e['id']}\nevent: progress\ndata: {json.dumps(e)}\n\n" for e in job.payload['events'] if e['id']>cursor)
        return StreamingResponse(iter([stream]), media_type='text/event-stream')

    @app.post('/api/v1/products/{product_id}/confirm')
    def confirm(product_id:str, payload:ConfirmRequest, user=Depends(writer), db=Depends(get_db)):
        row=owned(db,user,'product',product_id)
        row.payload={**row.payload,'name':payload.name.strip(),'confirmed':True,'confirmed_at':now(),'blocker':'Collect independent demand and local-market evidence.'}
        audit(db,user,'product.confirmed',product_id,kind='product',name_length=len(payload.name))
        db.commit()
        return serialize(row)

    @app.post('/api/v1/decisions', status_code=201)
    def decision(payload:DecisionRequest, idempotency_key:str=Header(min_length=1,max_length=128), user=Depends(writer), db=Depends(get_db)):
        product=owned(db,user,'product',payload.product_id)
        if not product.payload['confirmed']: raise HTTPException(409,'Confirm product identity before saving a decision.')
        def same_submission(existing):
            existing_conversion = existing.payload.get('quote_conversion')
            requested_rate = payload.quote_fx_to_usd
            if existing_conversion and existing_conversion.get('source_currency') == 'USD' and requested_rate is None:
                requested_rate = 1.0
            if (existing.payload['product_id']!=payload.product_id
                    or existing.payload['inputs']!=payload.inputs.model_dump()
                    or existing.payload.get('quote_id') != payload.quote_id
                    or (existing_conversion is None and payload.quote_fx_to_usd is not None)
                    or (existing_conversion is not None
                        and existing_conversion.get('rate_to_usd') != requested_rate)):
                raise HTTPException(409,'Idempotency key already used.')
            return serialize(existing)
        old=records(db,user,'decision').filter_by(key=idempotency_key).first()
        if old:
            return same_submission(old)
        # The gate inputs are computed here, from records this workspace holds. A client
        # cannot raise confidence, assert coverage or resolve compliance (action plan D03).
        reading, gate, review = evidence_gate(db,user,payload.product_id)
        snapshot = evidence_records(db,user,payload.product_id)
        quote_snapshot = None
        quote_conversion = None
        if payload.quote_id:
            quote_row = owned(db,user,'quote',payload.quote_id)
            if quote_row.payload.get('product_id') != payload.product_id:
                raise HTTPException(422, 'The supplier quote belongs to a different product.')
            quote_snapshot = serialize(quote_row)
            currency = quote_snapshot.get('currency', 'USD')
            amount = quote_snapshot.get('unit_price', quote_snapshot.get('unit_price_usd'))
            if currency == 'USD' and payload.quote_fx_to_usd not in {None, 1.0}:
                raise HTTPException(422, 'A USD supplier quote uses a USD conversion rate of 1.')
            rate = 1.0 if currency == 'USD' else payload.quote_fx_to_usd
            if rate is None:
                raise HTTPException(422, f'Enter the {currency} to USD rate used for this decision.')
            expected_usd = Decimal(str(amount)) * Decimal(str(rate))
            if abs(expected_usd - Decimal(str(payload.inputs.unit_cost_usd))) > Decimal('0.005'):
                raise HTTPException(422, 'The supplier cost must match the selected quote and its currency conversion.')
            quote_conversion = {'source_currency': currency, 'rate_to_usd': rate,
                                'effective_unit_cost_usd': float(expected_usd),
                                'truth_state': 'User input'}
        elif payload.quote_fx_to_usd is not None:
            raise HTTPException(422, 'A quote currency conversion requires a selected supplier quote.')
        result=calculate(payload.inputs, reading)
        # The assessment carries its own evidence snapshot and versions, so an export never
        # has to reconstruct provenance from whatever product a screen has open (T03).
        result.update(product_id=product.id,product_name=product.payload['name'],product_asin=product.payload.get('asin'),
                      input_author=user.id,evidence=snapshot,evidence_version=reading['method_version'],
                      evidence_quality=reading,compliance=gate,
                      quote_id=payload.quote_id,supplier_quote=quote_snapshot,
                      quote_conversion=quote_conversion,
                      compliance_review_id=review['id'] if review else None,
                      threshold_version=THRESHOLD_VERSION,formula_version=FORMULA_VERSION,
                      economics=economics_summary(result['scenarios']))
        row,created=insert_unique(db,user,'decision',idempotency_key,result)
        if created:
            audit(db,user,'decision.saved',row.id,product_id=product.id,decision=result['decision'],
                  formula_version=result['formula_version'],threshold_version=result['threshold_version'])
        db.commit()
        # A retry after an ambiguous timeout reuses its key and must not save twice.
        return serialize(row) if created else same_submission(row)

    @app.get('/api/v1/decisions')
    def decisions(limit: int = DEFAULT_LIMIT, cursor: str | None = None, product_id: str | None = None,
                  user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        query = records(db,user,'decision')
        if product_id: query = query.filter(Record.payload['product_id'].as_string() == product_id)
        rows, page = paginate(query, limit, cursor)
        return {'decisions':[serialize(r) for r in rows], **page}

    @app.get('/api/v1/decisions/{decision_id}')
    def saved_decision(decision_id:str,user=Depends(permitted('workspace.read')),db=Depends(get_db)):
        return serialize(owned(db,user,'decision',decision_id))

    @app.get('/api/v1/watchlists/default/items')
    def watches(limit: int = DEFAULT_LIMIT, cursor: str | None = None, user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        rows, page = paginate(records(db,user,'watch'), limit, cursor)
        return {'items':with_product_names(db,user,rows,assessments=True), **page}

    @app.post('/api/v1/watchlists/default/items')
    def watch(payload:WatchRequest,user=Depends(writer),db=Depends(get_db)):
        owned(db,user,'product',payload.product_id)
        body={**payload.model_dump(),'status':'Awaiting evidence','delivery':'In-app','scheduled':False}
        row=records(db,user,'watch').filter_by(key=payload.product_id).first()
        if not row:
            # Two concurrent watches on one product converge on a single rule.
            row,created=insert_unique(db,user,'watch',payload.product_id,body)
            if created:
                db.commit()
                return serialize(row)
        row.payload=body
        audit(db,user,'watch.updated',row.id)
        db.commit()
        return serialize(row)

    @app.delete('/api/v1/watchlists/default/items/{watch_id}')
    def unwatch(watch_id:str,user=Depends(writer),db=Depends(get_db)):
        row=owned(db,user,'watch',watch_id)
        audit(db,user,'watch.removed',row.id,product_id=row.payload.get('product_id'))
        db.delete(row)
        db.commit()
        return {'status':'removed'}

    @app.get('/api/v1/alerts')
    def alerts(user=Depends(permitted('workspace.read'))):
        return {'alerts':[], 'status':'unavailable','reason':'Scheduled collection and alert delivery are not enabled.'}

    @app.get('/api/v1/quotes')
    def quotes(limit: int = DEFAULT_LIMIT, cursor: str | None = None, product_id: str | None = None,
               user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        query = records(db,user,'quote')
        if product_id: query = query.filter(Record.payload['product_id'].as_string() == product_id)
        rows, page = paginate(query, limit, cursor)
        return {'quotes':with_product_names(db,user,rows), **page}

    @app.get('/api/v1/summary')
    def summary(user=Depends(permitted('workspace.read')), db=Depends(get_db)):
        """Workspace counts computed in the database, not from whatever page is loaded (T05).

        `products_awaiting_evidence` counts the product records whose evidence status is
        not GO. It is a coverage figure, not a commercial verdict: a product's evidence
        status and a user's saved assessment are different things (see T07).
        """
        products = records(db,user,'product')
        decisions_query = records(db,user,'decision')
        return {
            'products': products.count(),
            'products_awaiting_evidence': products.filter(Record.payload['decision'].as_string() != 'GO').count(),
            'decisions': decisions_query.count(),
            'decisions_go': decisions_query.filter(Record.payload['decision'].as_string() == 'GO').count(),
            'quotes': records(db,user,'quote').count(),
            'watches': records(db,user,'watch').count(),
        }

    @app.get('/api/v1/export')
    def export_workspace(user=Depends(permitted('workspace.export'))):
        """Every authorised record in this workspace, exactly once, independent of paging.

        The generator opens its own session: a dependency-provided one is closed before a
        streaming body is sent. Records are emitted oldest first with a stable
        (created_at, id) order, so two exports of unchanged data are byte-identical.
        """
        def document():
            with database.session() as export_db:
                counts = {name: records(export_db,user,kind).count() for kind, name in EXPORT_KINDS}
                header = {'workspace_id':user.workspace_id, 'workspace':user.name, 'exported_at':now(),
                          'exported_by':user.id, 'demo':False, 'schema':EXPORT_SCHEMA,
                          'counts':counts}
                yield json.dumps(header)[:-1]
                for kind, name in EXPORT_KINDS:
                    yield f',{json.dumps(name)}:['
                    separator = ''
                    for row in records(export_db,user,kind).order_by(Record.created_at.asc(), Record.id.asc()).yield_per(200):
                        yield separator + json.dumps(serialize(row))
                        separator = ','
                    yield ']'
                yield '}'
        with database.session() as audit_db:
            # A download is an event worth keeping: who took the whole workspace, and when.
            audit(audit_db, user, 'workspace.exported', scope='all-records',
                  schema=EXPORT_SCHEMA)
            audit_db.commit()
        filename = f'trendsell-workspace-{now()[:10]}.json'
        return StreamingResponse(document(), media_type='application/json',
                                 headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.post('/api/v1/quotes',status_code=201)
    def quote(payload:QuoteRequest,user=Depends(writer),db=Depends(get_db)):
        owned(db,user,'product',payload.product_id)
        try: quoted = datetime.strptime(payload.quote_date,'%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError: raise HTTPException(422,'Quote date is invalid.')
        if quoted > datetime.now(timezone.utc) + timedelta(days=1):
            raise HTTPException(422, 'A supplier quote cannot be dated in the future.')
        body = payload.model_dump(exclude_none=True)
        amount = body.pop('unit_price_usd', None)
        if body.get('unit_price') is None:
            body['unit_price'] = amount
        row=insert(db,user,'quote',{**body,'truth_state':'User input','verification':'Unverified',
                                   'input_author':user.id,'recorded_at':now(),'market':'NG'})
        audit(db,user,'quote.recorded',row.id,product_id=payload.product_id,incoterm=payload.incoterm,quote_date=payload.quote_date)
        db.commit()
        return serialize(row)

    @app.get('/api/v1/audit')
    def audit_log(limit: int = 100, user=Depends(permitted('audit.read')), db=Depends(get_db)):
        if limit < 1 or limit > 500: raise HTTPException(422, 'Page size must be between 1 and 500.')
        rows = db.query(Audit).filter_by(workspace_id=user.workspace_id).order_by(Audit.created_at.desc()).limit(limit).all()
        return {'events':[{'action':r.action, 'actor':r.user_id, 'workspace_id':r.workspace_id,
                           'record_id':r.record_id, 'request_id':r.request_id, 'detail':r.detail,
                           'created_at':r.created_at} for r in rows],
                'total': db.query(Audit).filter_by(workspace_id=user.workspace_id).count()}

    @app.get('/api/v1/permissions')
    def permissions(user=Depends(current_user)):
        """The permission matrix and this user's place in it. Enforced server-side (P05)."""
        table = matrix()
        return {**table, 'role': user.role, 'granted': table['roles'].get(user.role, [])}

    @app.get('/api/v1/ops/metrics')
    def metrics(x_metrics_token: str | None = Header(default=None)):
        """Operational counters for this worker: an operator surface, not a workspace one.

        Review finding R07: this was granted by `workspace.admin`, so any workspace owner
        read counters covering every workspace the worker had served — request labels and
        aggregate activity that are not theirs. Administering a workspace is not operating
        the service, and no workspace permission can express "operates the fleet".

        So it is gated on a token configured with the deployment, alongside the process
        rather than inside the product. Unset means the surface does not exist, which is
        the default and the right answer for anyone who has not deliberately enabled it.
        """
        if not settings.metrics_token:
            raise HTTPException(404, 'Operational metrics are not enabled on this deployment.')
        if not x_metrics_token or not secrets.compare_digest(x_metrics_token, settings.metrics_token):
            raise HTTPException(403, 'Operational metrics require the operator token.')
        return {**counters.snapshot(), 'environment': settings.environment,
                'schema_revision': migrate.head_revision(settings.database_url)}

    @app.api_route('/api/{retired:path}',methods=['GET','POST','PUT','DELETE'])
    def retired(retired:str):
        raise HTTPException(410,'The synthetic prototype API is retired. Use the authenticated /api/v1 evidence API.')
    return app
