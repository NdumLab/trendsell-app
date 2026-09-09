from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import time
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, StringConstraints, TypeAdapter, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from . import migrate
from .settings import Settings
from .db import Database, Workspace, User, Session, Record, records, audit, now, uid
from .security import dummy_verify, hash_password, verify_password, token_hash, consume, purge_expired, resolve_input
from .limits import BodyLimit, MAX_BODY_BYTES
from .observability import Counters, REQUEST_ID, USER_ID, WORKSPACE_ID, logger, new_request_id, route_label
from .permissions import matrix, require
from .evidence import EvidenceRequest, MANUAL_TRUTH_STATE, METHOD_VERSION, METRICS, quality
from . import compliance as cmp
from .economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate, economics_summary
from .pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate, searched

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
                ('compliance_review','compliance_reviews')]
EXPORT_SCHEMA = 'trendsell-workspace-export/2'

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

class XrayRequest(StrictModel):
    input: str = Field(min_length=10, max_length=2048)
    market: Literal['NG'] = 'NG'

class ConfirmRequest(StrictModel):
    name: str = Field(min_length=2, max_length=160)

class DecisionRequest(StrictModel):
    product_id: str
    inputs: Inputs

class WatchRequest(StrictModel):
    product_id: str
    threshold_pct: int = Field(default=15, ge=1, le=100)

class QuoteRequest(StrictModel):
    product_id: str
    supplier: str = Field(min_length=2, max_length=200)
    source_url: str = Field(min_length=12, max_length=2000)
    unit_price_usd: float = Field(gt=0, le=1000000)
    moq: int = Field(ge=1, le=1000000)
    lead_days: int = Field(ge=1, le=1000)
    quote_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    incoterm: Literal['EXW','FOB','CIF','DDP'] = 'FOB'
    notes: str = Field(default='', max_length=2000)

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

    @asynccontextmanager
    async def lifespan(app):
        if settings.environment != 'production':
            database.create()
        # Interrupted investigations become truthful partial results after restart.
        with database.session() as db:
            for job in db.query(Record).filter_by(kind='job').all():
                if job.payload['status'] in {'queued','running'}:
                    p = dict(job.payload)
                    p.update(status='partial', events=p['events']+[{'id':len(p['events'])+1,'step':'Investigation interrupted', 'status':'unavailable','detail':'The service restarted. Refresh the investigation to try again.', 'at':now()}])
                    job.payload = p
            db.commit()
            # Expired sessions and finished rate windows accumulate otherwise; only rows
            # whose own expiry has passed are removed (action plan P04).
            purge_expired(db)
        yield
        database.engine.dispose()

    app = FastAPI(title='TrendSell Evidence API', version='2.0.0', lifespan=lifespan)
    app.state.database = database
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
            response.headers['X-Request-ID'] = identifier
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Cache-Control'] = 'no-store'
            if settings.environment == 'production':
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            matched = request.scope.get('route')
            counters.record(request.method, request.url.path, 500, duration_ms, matched)
            logger.exception('request failed', extra={'request_id': identifier, 'context': {
                'method': request.method, 'route': route_label(request.url.path, matched),
                'duration_ms': round(duration_ms, 1), **identity(request)}})
            raise
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
        if not user: raise HTTPException(401, 'Session is no longer valid.')
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

    def user_view(user):
        return {'id':user.id, 'name':user.name, 'email':user.email, 'workspace_id':user.workspace_id, 'role':user.role}

    def start_session(db, user, response):
        token = secrets.token_urlsafe(48)
        db.add(Session(token_hash=token_hash(token), user_id=user.id, expires_at=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()))
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
        return {'allow_registration':settings.allow_registration, 'destination':'NG', 'demo':False, 'research_daily_limit':settings.research_daily_limit}

    @app.post('/api/v1/auth/register', status_code=201)
    def register(payload: Credentials, request: Request, response: Response, db=Depends(get_db)):
        if not settings.allow_registration: raise HTTPException(403, 'Registration is closed. Contact your workspace owner.')
        consume(db, f'register:{request.client.host}:{now()[:13]}', settings.register_ip_hourly_limit,
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
        return start_session(db, user, response)

    @app.post('/api/v1/auth/login')
    def login(payload: Credentials, request: Request, response: Response, db=Depends(get_db)):
        # Two independent limits (action plan P04). The address limit is generous because a
        # shared network is one address; the account limit is what actually bounds guessing
        # against one person, including from many addresses.
        email = payload.email.lower().strip()
        consume(db, f'login-ip:{request.client.host}:{now()[:13]}', settings.login_ip_hourly_limit,
                message='Too many sign-in attempts from this address. Try again later.')
        consume(db, f'login-account:{token_hash(email)}:{now()[:13]}', settings.login_account_hourly_limit,
                message='Too many sign-in attempts for this account. Try again later.')
        user = db.query(User).filter_by(email=email).first()
        if not user:
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
        return start_session(db, user, response)

    @app.get('/api/v1/auth/me')
    def me(user=Depends(current_user)): return user_view(user)

    @app.post('/api/v1/auth/logout')
    def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
        db.query(Session).filter_by(token_hash=token_hash(request.cookies.get('trendsell_session',''))).delete()
        audit(db,user,'auth.logout')
        db.commit()
        response.delete_cookie('trendsell_session', path='/api')
        return {'status':'signed_out'}

    @app.get('/api/v1/data-health')
    def data_health():
        return {'sources':[{**s,'status':'unconfigured','last_success':None,'last_attempt':None,'next_retry':'After connection and source review','freshness_hours':24} for s in SOURCES], 'market':'NG', 'coverage':None, 'truth_state':'Unavailable'}

    @app.get('/api/v1/products')
    def products(search: str = Query(default='', max_length=200), limit: int = DEFAULT_LIMIT,
                 cursor: str | None = None, user=Depends(current_user), db=Depends(get_db)):
        rows, page = paginate(searched(records(db,user,'product'), search, ['name','asin']), limit, cursor)
        return {'products':with_latest_assessment(db,user,rows), **page}

    @app.get('/api/v1/products/{product_id}')
    def product(product_id: str, user=Depends(current_user), db=Depends(get_db)):
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

    def latest_review(db, user, product_id):
        """The newest import-readiness review for one product, or None."""
        rows = (records(db,user,'compliance_review')
                .filter(Record.payload['product_id'].as_string() == product_id)
                .order_by(Record.created_at.asc()).all())
        return serialize(rows[-1]) if rows else None

    def evidence_gate(db, user, product_id):
        """The gate inputs, computed on the server from stored records (action plan D03).

        Nothing a client sends can raise confidence, assert coverage, or resolve
        compliance: each comes from records this workspace actually holds.
        """
        review = latest_review(db, user, product_id)
        gate = cmp.gate_state(review)
        reading = quality(evidence_records(db, user, product_id), gate['resolved'])
        # The reviewed state itself, not merely whether it resolved the gate. A rejection
        # is authoritative and decides the assessment; under the previous thresholds it
        # reached the screen and never reached the calculation (review finding R04).
        reading['compliance_status'] = gate['status']
        return reading, gate, review

    @app.get('/api/v1/products/{product_id}/evidence')
    @app.get('/api/v1/products/{product_id}/timeline')
    def evidence(product_id: str, user=Depends(current_user), db=Depends(get_db)):
        owned(db,user,'product',product_id)
        stored = evidence_records(db,user,product_id)
        reading, gate, _ = evidence_gate(db,user,product_id)
        return {'observations': stored,
                # No collector exists, so nothing here is an observed fact. The truth state
                # says what the records actually are (action plan E06).
                'truth_state': MANUAL_TRUTH_STATE if stored else 'Unavailable',
                'reason': ('These records were entered by people in this workspace. No approved collector '
                           'has produced an observation for this product.') if stored else
                          'No evidence has been recorded and no approved collector has produced an observation.',
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
    def compliance_state(product_id: str, user=Depends(current_user), db=Depends(get_db)):
        owned(db,user,'product',product_id)
        review = latest_review(db,user,product_id)
        history = [serialize(row) for row in
                   records(db,user,'compliance_review')
                   .filter(Record.payload['product_id'].as_string() == product_id)
                   .order_by(Record.created_at.desc()).all()]
        return {'gate': cmp.gate_state(review), 'current': review, 'history': history,
                'can_review': permissions_granted(user, 'compliance.review'),
                'review_version': cmp.REVIEW_VERSION}

    @app.post('/api/v1/products/{product_id}/compliance/requests', status_code=201)
    def request_review(product_id: str, payload: cmp.ReviewRequest,
                       user=Depends(permitted('workspace.write')), db=Depends(get_db)):
        """Ask a reviewer to resolve import readiness, with the context they need."""
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
        """A reviewer's decision. Only this permission can resolve the compliance gate."""
        row = owned(db,user,'compliance_review',review_id)
        if row.payload['status'] != 'requested':
            raise HTTPException(409, 'This review has already been decided. Request a new review instead.')
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
            for source in SOURCES[:2]:
                p['events'] = p['events']+[{'id':len(p['events'])+1,'step':source['name'],'status':'unavailable','detail':source['reason'],'at':now()}]
            p['status'] = 'partial'
            p['events'] = p['events']+[{'id':len(p['events'])+1,'step':'Review product identity','status':'partial','detail':'Identifier captured. Confirm the product name; source identity and demand remain unverified.','at':now()}]
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
        job, created = insert_unique(db,user,'job',key,{'status':'queued','product_id':canonical.id,'request_hash':request_hash,'events':[{'id':1,'step':'Amazon identifier captured','status':'succeeded','detail':'Parsed from your input. No external page was fetched.','at':now()}]})
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
    def job(job_id:str, user=Depends(current_user), db=Depends(get_db)):
        return serialize(owned(db,user,'job',job_id))

    @app.get('/api/v1/research-jobs/{job_id}/events')
    def events(job_id:str, last_event_id:str=Header(default='0'), user=Depends(current_user), db=Depends(get_db)):
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
            if existing.payload['product_id']!=payload.product_id or existing.payload['inputs']!=payload.inputs.model_dump():
                raise HTTPException(409,'Idempotency key already used.')
            return serialize(existing)
        old=records(db,user,'decision').filter_by(key=idempotency_key).first()
        if old:
            return same_submission(old)
        # The gate inputs are computed here, from records this workspace holds. A client
        # cannot raise confidence, assert coverage or resolve compliance (action plan D03).
        reading, gate, review = evidence_gate(db,user,payload.product_id)
        snapshot = evidence_records(db,user,payload.product_id)
        result=calculate(payload.inputs, reading)
        # The assessment carries its own evidence snapshot and versions, so an export never
        # has to reconstruct provenance from whatever product a screen has open (T03).
        result.update(product_id=product.id,product_name=product.payload['name'],product_asin=product.payload.get('asin'),
                      input_author=user.id,evidence=snapshot,evidence_version=reading['method_version'],
                      evidence_quality=reading,compliance=gate,
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
                  user=Depends(current_user), db=Depends(get_db)):
        query = records(db,user,'decision')
        if product_id: query = query.filter(Record.payload['product_id'].as_string() == product_id)
        rows, page = paginate(query, limit, cursor)
        return {'decisions':[serialize(r) for r in rows], **page}

    @app.get('/api/v1/decisions/{decision_id}')
    def saved_decision(decision_id:str,user=Depends(current_user),db=Depends(get_db)):
        return serialize(owned(db,user,'decision',decision_id))

    @app.get('/api/v1/watchlists/default/items')
    def watches(limit: int = DEFAULT_LIMIT, cursor: str | None = None, user=Depends(current_user), db=Depends(get_db)):
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
    def alerts(user=Depends(current_user)):
        return {'alerts':[], 'status':'unavailable','reason':'Scheduled collection and alert delivery are not enabled.'}

    @app.get('/api/v1/quotes')
    def quotes(limit: int = DEFAULT_LIMIT, cursor: str | None = None, product_id: str | None = None,
               user=Depends(current_user), db=Depends(get_db)):
        query = records(db,user,'quote')
        if product_id: query = query.filter(Record.payload['product_id'].as_string() == product_id)
        rows, page = paginate(query, limit, cursor)
        return {'quotes':with_product_names(db,user,rows), **page}

    @app.get('/api/v1/summary')
    def summary(user=Depends(current_user), db=Depends(get_db)):
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
        try: datetime.strptime(payload.quote_date,'%Y-%m-%d')
        except ValueError: raise HTTPException(422,'Quote date is invalid.')
        row=insert(db,user,'quote',{**payload.model_dump(),'truth_state':'User input','verification':'Unverified','input_author':user.id,'market':'NG'})
        audit(db,user,'quote.recorded',row.id,product_id=payload.product_id,incoterm=payload.incoterm,quote_date=payload.quote_date)
        db.commit()
        return serialize(row)

    @app.get('/api/v1/audit')
    def audit_log(limit: int = 100, user=Depends(permitted('audit.read')), db=Depends(get_db)):
        from .db import Audit
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
