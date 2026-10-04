"""Disposable reproduction of review findings. Never reads a live database."""
import sys, json, logging, tempfile, hashlib
from pathlib import Path
REPOSITORY = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPOSITORY / 'backend'), str(REPOSITORY / 'scripts')]
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import create_app
from app.settings import Settings
from app.db import User
from app import passwords, migrate
from verify_restore import inspect_database

logging.getLogger('trendsell').disabled = True
passwords.PARAMETERS = {'n':4096, 'r':8, 'p':1}
HEADERS = {'X-Requested-With':'TrendSell'}
INPUTS = dict(quantity=300, unit_cost_usd=2, fx_ngn=1500, freight_ngn=90000,
    duty_pct=5, import_tax_pct=7.5, selling_price_ngn=30000, channel_fee_pct=5,
    returns_pct=2, marketing_ngn=10000, fixed_cost_ngn=10000, stress_pct=15,
    compliance='unresolved', channel='Direct sales', shipping='Air')
findings = {}
with tempfile.TemporaryDirectory(prefix='trendsell-independent-review-') as directory:
    url = 'sqlite:///' + directory + '/review.db'
    migrate.upgrade(url)
    app = create_app(Settings(environment='test', database_url=url, allow_registration=True))
    with TestClient(app) as client:
        def post(path, body, expected=201, **extra):
            response = client.post(path, json=body, headers={**HEADERS, **extra})
            assert response.status_code == expected, (path, response.status_code, response.text)
            return response.json()
        owner = post('/api/v1/auth/register', dict(email='review@example.test', password='long-review-password', name='Review workspace'))
        # Seed a valid legacy hash exactly as the previous release produced it.
        original = ' long-review-password '
        salt = 'd' * 32
        digest = hashlib.scrypt(original.encode(), salt=salt.encode(), **passwords.LEGACY_PARAMETERS).hex()
        with app.state.database.session() as db:
            db.get(User, owner['id']).password_hash = salt + ':' + digest
            db.commit()
        response = client.post('/api/v1/auth/login', json={'email':'review@example.test', 'password':original}, headers=HEADERS)
        findings['legacy_password_with_spaces'] = {'hash_verifies_directly': passwords.verify_password(original, salt+':'+digest)[0], 'login_status': response.status_code}
        job = post('/api/v1/xray', {'input':'B0C1STEAM1'}, 202)
        pid = job['product_id']
        post(f'/api/v1/products/{pid}/confirm', {'name':'Disposable review product'}, 200)
        for index, metric in enumerate(['Search interest', 'Review velocity', 'Social mentions', 'Local listing count']):
            post(f'/api/v1/products/{pid}/evidence', {'metric':metric, 'value':100, 'unit':'count',
                'market':'NG' if index == 3 else 'US', 'observed_at':'2026-09-08',
                'source_name':f'Review source {index}', 'source_url':'https://example.test/review', 'method':'Manually entered test fixture'})
        def request_review():
            return post(f'/api/v1/products/{pid}/compliance/requests', {'product_id':pid,
                'specifications':'Disposable test specifications', 'intended_use':'Testing only',
                'question':'Does this disposable test qualify?'})
        review = request_review()
        approved = post(f'/api/v1/compliance/reviews/{review["id"]}/decision', {'status':'approved',
            'rationale':'Disposable review approval for validation testing',
            'sources':[{'title':'Expired fixture publication', 'publisher':'Test publisher',
                'url':'https://example.test/expired', 'effective_from':'2010-01-01', 'effective_to':'2011-01-01'}]}, 200)
        gate = client.get(f'/api/v1/products/{pid}/compliance').json()['gate']
        findings['expired_source_approval'] = {'status': approved['status'], 'hs_code':approved['hs_code'], 'requirements':approved['requirements'], 'gate_resolved':gate['resolved']}
        post('/api/v1/decisions', {'product_id':pid, 'inputs':INPUTS}, **{'Idempotency-Key':'review-approved'})
        review = request_review()
        post(f'/api/v1/compliance/reviews/{review["id"]}/decision', {'status':'rejected', 'rationale':'This product must not be imported in this test scenario.'}, 200)
        decision = post('/api/v1/decisions', {'product_id':pid, 'inputs':INPUTS}, **{'Idempotency-Key':'review-rejected'})
        findings['rejected_import_assessment'] = {'decision':decision['decision'], 'compliance':decision['compliance'], 'confidence':decision['confidence']}
        exported = client.get('/api/v1/export').json()
        findings['export'] = {'keys':sorted(exported), 'exported_counts':exported['counts']}
        report = inspect_database(url)
        findings['restore_verification'] = {'records_by_kind':report['records_by_kind'], 'assessment_replay_failures':report['assessment_replay_failures']}
        client.get('/api/review-workspace-private-marker')
        # A new workspace owner sees route labels from the first workspace.
        with TestClient(app) as stranger:
            response = stranger.post('/api/v1/auth/register', json={'email':'stranger@example.test', 'password':'long-review-password', 'name':'Second workspace'}, headers=HEADERS)
            assert response.status_code == 201
            metrics = stranger.get('/api/v1/ops/metrics')
            findings['cross_workspace_metrics'] = {'status':metrics.status_code, 'foreign_marker_visible': 'GET /api/review-workspace-private-marker' in metrics.json()['requests']}
        before = len(app.state.counters.requests)
        for i in range(20):
            client.get(f'/api/review-unmatched-path-{i}')
        findings['unmatched_route_labels'] = {'new_labels_from_20_unknown_paths':len(app.state.counters.requests)-before}
        with app.state.database.engine.begin() as connection:
            connection.execute(text('DROP TABLE audit_events'))
        response = client.get('/api/ready')
        findings['readiness_missing_audit_table'] = {'status':response.status_code, 'body':response.json()}
    legacy_url = 'sqlite:///' + directory + '/legacy.db'
    migrate.upgrade(legacy_url, '0001_pilot_baseline')
    from sqlalchemy import create_engine
    legacy_engine = create_engine(legacy_url)
    with legacy_engine.begin() as connection:
        connection.execute(text('DROP TABLE alembic_version'))
    legacy_engine.dispose()
    before = migrate.check(legacy_url)
    migrate.stamp_baseline(legacy_url)
    after = migrate.check(legacy_url)
    findings['documented_legacy_migration'] = {'before_stamp_matches_models':before['matches_models'], 'before_stamp_missing_columns':before['missing_columns'], 'after_stamp_up_to_date':after['up_to_date'], 'after_stamp_revision':after['current_revision'], 'head_revision':after['head_revision']}
print(json.dumps(findings, indent=2))
