"""Disposable PostgreSQL backup/restore drill against current evidence and review records.

Seeds a workspace with evidence, an approved review and a saved assessment, dumps it,
restores into a *separate* database, and verifies the restored copy replays.
Two workspaces deliberately share a display name (R06's second half).
"""
import json, subprocess, sys, hashlib, logging
from datetime import date, timedelta
from pathlib import Path
REPO = Path('/root/trendsell-app')
sys.path[:0] = [str(REPO / 'backend'), str(REPO / 'scripts')]
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import Settings
from app import passwords, migrate
from verify_restore import inspect_database

logging.getLogger('trendsell').disabled = True
passwords.PARAMETERS = {'n': 4096, 'r': 8, 'p': 1}
H = {'X-Requested-With': 'TrendSell'}
BASE = 'postgresql+psycopg://trendsell_test:disposable@127.0.0.1:55433/'
TODAY = date.today()
INPUTS = dict(quantity=300, unit_cost_usd=2, fx_ngn=1500, freight_ngn=90000, duty_pct=5,
    import_tax_pct=7.5, selling_price_ngn=30000, channel_fee_pct=5, returns_pct=2,
    marketing_ngn=10000, fixed_cost_ngn=10000, stress_pct=15, compliance='unresolved',
    channel='Direct sales', shipping='Air')

def psql(sql, db='postgres'):
    subprocess.run(['docker','exec','trendsell-test-db','psql','-U','trendsell_test','-d',db,
                    '-v','ON_ERROR_STOP=1','-tAc',sql], check=True, capture_output=True)

for name in ('drill_src','drill_dst'):
    psql(f'DROP DATABASE IF EXISTS {name}')
    psql(f'CREATE DATABASE {name}')

src = BASE + 'drill_src'
migrate.upgrade(src)
app = create_app(Settings(environment='test', database_url=src, allow_registration=True))
with TestClient(app) as c:
    def post(p, b, e=201, **x):
        r = c.post(p, json=b, headers={**H, **x}); assert r.status_code == e, (p, r.status_code, r.text); return r.json()
    # Two workspaces sharing a display name: reconciliation must keep them apart.
    for i, email in enumerate(['a@example.test', 'b@example.test']):
        with TestClient(app) as w:
            r = w.post('/api/v1/auth/register', json={'email': email, 'password': 'long-drill-password',
                       'name': 'Shared workspace name'}, headers=H)
            assert r.status_code == 201, r.text
            def wpost(p, b, e=201, **x):
                rr = w.post(p, json=b, headers={**H, **x}); assert rr.status_code == e, (p, rr.status_code, rr.text); return rr.json()
            pid = wpost('/api/v1/xray', {'input': f'B0DRILL{i}01'}, 202)['product_id']
            wpost(f'/api/v1/products/{pid}/confirm', {'name': f'Drill product {i}'}, 200)
            for j, m in enumerate(['Search interest','Review velocity','Social mentions','Local listing count']):
                wpost(f'/api/v1/products/{pid}/evidence', {'metric': m, 'value': 100, 'unit': 'count',
                    'market': 'NG' if j == 3 else 'US', 'observed_at': (TODAY - timedelta(days=3)).isoformat(),
                    'source_name': f'Drill source {j}', 'source_url': 'https://example.test/drill',
                    'method': 'Disposable drill fixture'})
            rev = wpost(f'/api/v1/products/{pid}/compliance/requests', {'product_id': pid,
                'specifications': 'Disposable drill specifications', 'intended_use': 'Drill only',
                'question': 'Does this disposable drill fixture qualify?'})
            wpost(f'/api/v1/compliance/reviews/{rev["id"]}/decision', {'status': 'approved',
                'rationale': 'Disposable drill approval on current support', 'hs_code': '8516.79',
                'requirements': ['Disposable drill requirement statement'],
                'sources': [{'title': 'Drill publication', 'publisher': 'Drill publisher',
                    'url': 'https://example.test/current',
                    'effective_from': (TODAY - timedelta(days=30)).isoformat(),
                    'effective_to': (TODAY + timedelta(days=365)).isoformat()}]}, 200)
            wpost('/api/v1/decisions', {'product_id': pid, 'inputs': INPUTS}, **{'Idempotency-Key': f'drill-{i}'})

before = inspect_database(src)
# Dump and restore into a separate database, as the runbook's rollback path does.
dump = subprocess.run(['docker','exec','trendsell-test-db','pg_dump','-U','trendsell_test','-d','drill_src'],
                      check=True, capture_output=True)
subprocess.run(['docker','exec','-i','trendsell-test-db','psql','-U','trendsell_test','-d','drill_dst',
                '-v','ON_ERROR_STOP=1'], input=dump.stdout, check=True, capture_output=True)
after = inspect_database(BASE + 'drill_dst')

print(json.dumps({
    'dump_bytes': len(dump.stdout),
    'source_revision': before['schema_revision'], 'restored_revision': after['schema_revision'],
    'source_records_by_kind': before['records_by_kind'], 'restored_records_by_kind': after['records_by_kind'],
    'records_match': before['records_by_kind'] == after['records_by_kind'],
    'workspaces_source': before['workspaces'], 'workspaces_restored': after['workspaces'],
    'per_workspace_match': before['workspaces'] == after['workspaces'],
    'source_replay_failures': before['assessment_replay_failures'],
    'restored_replay_failures': after['assessment_replay_failures'],
}, indent=2, default=str))
for name in ('drill_src','drill_dst'):
    psql(f'DROP DATABASE {name}')
print('disposable drill databases dropped')
