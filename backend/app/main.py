from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .settings import Settings
from .db import Database, Workspace, User, Session, Record, records, audit, now, uid
from .security import hash_password, check_password, token_hash, consume, resolve_input
from .economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate

SOURCES = [
    {'id':'amazon', 'name':'Amazon catalog', 'category':'Product identity', 'markets':['US'], 'reason':'An authorized catalog connection is required. Pasted identifiers are user input, not verified catalog data.', 'rights':'Authorization required'},
    {'id':'google_trends', 'name':'Google Trends', 'category':'Search demand', 'markets':['US','NG'], 'reason':'No approved demand collector is connected. No search observations have been collected.', 'rights':'Source access review required'},
    {'id':'local_market', 'name':'Nigeria market coverage', 'category':'Local supply', 'markets':['NG'], 'reason':'No local marketplace observations. Missing listings do not indicate low competition.', 'rights':'Licensed or user-assisted evidence required'},
    {'id':'compliance', 'name':'Import requirements', 'category':'Compliance & tariffs', 'markets':['NG'], 'reason':'Product classification and effective-dated regulator evidence require review.', 'rights':'Official publications with analyst review'},
    {'id':'freight', 'name':'Freight & currency', 'category':'Landed cost', 'markets':['CN','NG'], 'reason':'Enter dated freight quotes and your exchange-rate assumption in Decision Room.', 'rights':'User-provided inputs only'},
]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

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
    source_url: str = Field(min_length=8, max_length=2000, pattern=r'^https://')
    unit_price_usd: float = Field(gt=0, le=1000000)
    moq: int = Field(ge=1, le=1000000)
    lead_days: int = Field(ge=1, le=1000)
    quote_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    incoterm: Literal['EXW','FOB','CIF','DDP'] = 'FOB'
    notes: str = Field(default='', max_length=2000)


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

    def insert(db, user, kind, payload, key=None):
        row = Record(workspace_id=user.workspace_id, kind=kind, key=key or uid(), payload=payload)
        db.add(row)
        db.flush()
        audit(db, user, kind+'.created', row.id)
        return row

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
    def health(db=Depends(get_db)):
        db.execute(text('SELECT 1'))
        return {'status':'ok', 'version':'2.0.0', 'demo':False}

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
        if not user or not check_password(payload.password, user.password_hash):
            if not user: hash_password(payload.password)
            raise HTTPException(401, 'Email or password is incorrect.')
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
    def products(search: str = '', user=Depends(current_user), db=Depends(get_db)):
        rows = records(db,user,'product').order_by(Record.created_at.desc()).limit(200).all()
        return {'products':[serialize(r) for r in rows if search.lower() in r.payload['name'].lower()]}

    @app.get('/api/v1/products/{product_id}')
    def product(product_id: str, user=Depends(current_user), db=Depends(get_db)):
        return serialize(owned(db,user,'product',product_id))

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

    def queue_job(payload, db, user, background, idempotency_key):
        identity = resolve_input(payload.input)
        request_hash = hashlib.sha256(json.dumps(payload.model_dump(),sort_keys=True).encode()).hexdigest()
        key = idempotency_key or request_hash
        if len(key)>128: raise HTTPException(422,'Idempotency key is too long.')
        existing = records(db,user,'job').filter_by(key=key).first()
        if existing:
            if existing.payload['request_hash'] != request_hash: raise HTTPException(409,'Idempotency key was used for a different request.')
            return serialize(existing)
        consume(db, f'research:{user.workspace_id}:{now()[:10]}', settings.research_daily_limit)
        canonical = records(db,user,'product').filter_by(key=identity['asin']).first()
        if not canonical:
            canonical = insert(db,user,'product',{'name':f"Amazon product · {identity['asin']}", 'asin':identity['asin'], 'source_url':identity['url'], 'market':'NG','discovery_market':'US','confirmed':False,'truth_state':'User input','decision':'INSUFFICIENT EVIDENCE','confidence':0,'category':'Unclassified','stage':'Needs evidence','blocker':'Confirm product identity and connect a demand source.','observations':[]},identity['asin'])
        job = insert(db,user,'job', {'status':'queued','product_id':canonical.id,'request_hash':request_hash,'events':[{'id':1,'step':'Amazon identifier captured','status':'succeeded','detail':'Parsed from your input. No external page was fetched.','at':now()}]},key)
        try: db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,'Another request is creating this investigation. Retry with the same idempotency key.')
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
        old=records(db,user,'decision').filter_by(key=idempotency_key).first()
        if old:
            if old.payload['product_id']!=payload.product_id or old.payload['inputs']!=payload.inputs.model_dump(): raise HTTPException(409,'Idempotency key already used.')
            return serialize(old)
        result=calculate(payload.inputs)
        result.update(product_id=product.id,product_name=product.payload['name'],input_author=user.id,evidence_version='no-observations/1',threshold_version=THRESHOLD_VERSION)
        row=insert(db,user,'decision',result,idempotency_key)
        db.commit()
        return serialize(row)

    @app.get('/api/v1/decisions')
    def decisions(user=Depends(current_user),db=Depends(get_db)):
        return {'decisions':[serialize(r) for r in records(db,user,'decision').order_by(Record.created_at.desc()).all()]}

    @app.get('/api/v1/decisions/{decision_id}')
    def saved_decision(decision_id:str,user=Depends(current_user),db=Depends(get_db)):
        return serialize(owned(db,user,'decision',decision_id))

    @app.get('/api/v1/watchlists/default/items')
    def watches(user=Depends(current_user),db=Depends(get_db)):
        return {'items':[serialize(r) for r in records(db,user,'watch').all()]}

    @app.post('/api/v1/watchlists/default/items')
    def watch(payload:WatchRequest,user=Depends(writer),db=Depends(get_db)):
        owned(db,user,'product',payload.product_id)
        row=records(db,user,'watch').filter_by(key=payload.product_id).first()
        body={**payload.model_dump(),'status':'Awaiting evidence','delivery':'In-app','scheduled':False}
        if row:
            row.payload=body
            audit(db,user,'watch.updated',row.id)
        else: row=insert(db,user,'watch',body,payload.product_id)
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
    def quotes(user=Depends(current_user),db=Depends(get_db)):
        return {'quotes':[serialize(r) for r in records(db,user,'quote').all()]}

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
