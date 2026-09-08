from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, TypeAdapter, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from . import migrate
from .settings import Settings
from .db import Database, Workspace, User, Session, Record, records, audit, now, uid
from .security import dummy_verify, hash_password, verify_password, token_hash, consume, resolve_input
from .economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate, economics_summary
from .pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate, searched

SOURCES = [
    {'id':'amazon', 'name':'Amazon catalog', 'category':'Product identity', 'markets':['US'], 'reason':'An authorized catalog connection is required. Pasted identifiers are user input, not verified catalog data.', 'rights':'Authorization required'},
    {'id':'google_trends', 'name':'Google Trends', 'category':'Search demand', 'markets':['US','NG'], 'reason':'No approved demand collector is connected. No search observations have been collected.', 'rights':'Source access review required'},
    {'id':'local_market', 'name':'Nigeria market coverage', 'category':'Local supply', 'markets':['NG'], 'reason':'No local marketplace observations. Missing listings do not indicate low competition.', 'rights':'Licensed or user-assisted evidence required'},
    {'id':'compliance', 'name':'Import requirements', 'category':'Compliance & tariffs', 'markets':['NG'], 'reason':'Product classification and effective-dated regulator evidence require review.', 'rights':'Official publications with analyst review'},
    {'id':'freight', 'name':'Freight & currency', 'category':'Landed cost', 'markets':['CN','NG'], 'reason':'Enter dated freight quotes and your exchange-rate assumption in Decision Room.', 'rights':'User-provided inputs only'},
]

EXPORT_KINDS = [('product','products'), ('job','research_jobs'), ('decision','decisions'),
                ('quote','quotes'), ('watch','watches')]

HTTPS_URL = TypeAdapter(HttpUrl)

class StrictModel(BaseModel):
    # str_strip_whitespace normalises *before* the length constraints run, so a name of
    # two spaces is rejected instead of being stored empty (action plan T08).
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)

class Credentials(StrictModel):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=128)
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
        yield
        database.engine.dispose()

    app = FastAPI(title='TrendSell Evidence API', version='2.0.0', lifespan=lifespan)
    app.state.database = database
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True,
                       allow_methods=['GET','POST','PUT','DELETE'], allow_headers=['Content-Type','Idempotency-Key','X-Requested-With'])

    @app.middleware('http')
    async def guard(request, call_next):
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            origin = request.headers.get('origin')
            if (origin and origin not in settings.origins) or request.headers.get('x-requested-with') != 'TrendSell':
                return JSONResponse({'detail':'Request origin or CSRF header rejected'}, status_code=403)
            if int(request.headers.get('content-length','0') or 0) > 32768:
                return JSONResponse({'detail':'Request is too large'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store'
        if settings.environment == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

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
        return user

    def writer(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if user.role not in {'owner','analyst'}:
            raise HTTPException(403, 'Your workspace role is read-only.')
        consume(db, f'write:{user.workspace_id}:{now()[:16]}', 60)
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
        audit(db, user, kind+'.created', row.id)
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

    @app.get('/api/ready')
    def ready(response: Response, db=Depends(get_db)):
        """Readiness: the database answers *and* carries the schema this code expects.

        `SELECT 1` proves connectivity, not that a migration has run (action plan P01).
        A database at the wrong revision is reported as not ready rather than serving
        requests against a schema the code does not match.
        """
        db.execute(text('SELECT 1'))
        expected = migrate.head_revision(settings.database_url)
        try:
            actual = migrate.current_revision(database.engine)
        except Exception:
            actual = None
        ready_now = actual == expected
        if not ready_now:
            response.status_code = 503
        return {'status':'ready' if ready_now else 'schema_mismatch', 'database':'ok',
                'schema_revision':actual, 'expected_revision':expected}

    @app.get('/api/v1/config')
    def config():
        return {'allow_registration':settings.allow_registration, 'destination':'NG', 'demo':False, 'research_daily_limit':settings.research_daily_limit}

    @app.post('/api/v1/auth/register', status_code=201)
    def register(payload: Credentials, request: Request, response: Response, db=Depends(get_db)):
        if not settings.allow_registration: raise HTTPException(403, 'Registration is closed. Contact your workspace owner.')
        consume(db, f'auth:{request.client.host}:{now()[:13]}', 20)
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
        consume(db, f'auth:{request.client.host}:{now()[:13]}', 20)
        user = db.query(User).filter_by(email=payload.email.lower().strip()).first()
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
        return with_latest_assessment(db,user,[owned(db,user,'product',product_id)])[0]

    @app.get('/api/v1/products/{product_id}/evidence')
    @app.get('/api/v1/products/{product_id}/timeline')
    def evidence(product_id: str, user=Depends(current_user), db=Depends(get_db)):
        owned(db,user,'product',product_id)
        return {'observations':[], 'truth_state':'Unavailable', 'reason':'No approved collector has produced an observation for this product.'}

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
        audit(db,user,'product.confirmed',product_id)
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
        result=calculate(payload.inputs)
        # The assessment carries its own evidence snapshot and versions, so an export never
        # has to reconstruct provenance from whatever product a screen has open (T03).
        result.update(product_id=product.id,product_name=product.payload['name'],product_asin=product.payload.get('asin'),
                      input_author=user.id,evidence=[],evidence_version='no-observations/1',
                      threshold_version=THRESHOLD_VERSION,formula_version=FORMULA_VERSION,
                      economics=economics_summary(result['scenarios']))
        row,created=insert_unique(db,user,'decision',idempotency_key,result)
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
        audit(db,user,'watch.removed',row.id)
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
    def export_workspace(user=Depends(current_user)):
        """Every authorised record in this workspace, exactly once, independent of paging.

        The generator opens its own session: a dependency-provided one is closed before a
        streaming body is sent. Records are emitted oldest first with a stable
        (created_at, id) order, so two exports of unchanged data are byte-identical.
        """
        def document():
            with database.session() as export_db:
                counts = {name: records(export_db,user,kind).count() for kind, name in EXPORT_KINDS}
                header = {'workspace_id':user.workspace_id, 'workspace':user.name, 'exported_at':now(),
                          'exported_by':user.id, 'demo':False, 'schema':'trendsell-workspace-export/1',
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
        filename = f'trendsell-workspace-{now()[:10]}.json'
        return StreamingResponse(document(), media_type='application/json',
                                 headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.post('/api/v1/quotes',status_code=201)
    def quote(payload:QuoteRequest,user=Depends(writer),db=Depends(get_db)):
        owned(db,user,'product',payload.product_id)
        try: datetime.strptime(payload.quote_date,'%Y-%m-%d')
        except ValueError: raise HTTPException(422,'Quote date is invalid.')
        row=insert(db,user,'quote',{**payload.model_dump(),'truth_state':'User input','verification':'Unverified','input_author':user.id,'market':'NG'})
        db.commit()
        return serialize(row)

    @app.get('/api/v1/audit')
    def audit_log(user=Depends(current_user),db=Depends(get_db)):
        from .db import Audit
        if user.role!='owner': raise HTTPException(403,'Owner access required.')
        return {'events':[{'action':r.action,'record_id':r.record_id,'created_at':r.created_at} for r in db.query(Audit).filter_by(workspace_id=user.workspace_id).order_by(Audit.created_at.desc()).limit(100).all()]}

    @app.api_route('/api/{retired:path}',methods=['GET','POST','PUT','DELETE'])
    def retired(retired:str):
        raise HTTPException(410,'The synthetic prototype API is retired. Use the authenticated /api/v1 evidence API.')
    return app
