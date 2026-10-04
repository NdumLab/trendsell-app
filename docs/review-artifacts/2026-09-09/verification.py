"""Verification of the R01-R11 corrections, on the same disposable pattern the review used.

Adapted from `../2026-09-08/backend_reproductions.py`. That script asserted the *defective*
outcomes, so it now aborts at the third case: an approval with no classification is
correctly refused. This walks the same cases and records what each one does now, so the
handoff can state outcomes rather than claims.

Never reads a live database: every case runs against a temporary SQLite file that is
deleted on exit. All fixture values -- sources, classifications, prices -- are disposable
test data, not market or regulatory evidence.

Run from the repository root: `.venv/bin/python docs/review-artifacts/2026-09-09/verification.py`
"""
import sys, json, logging, tempfile, hashlib
from datetime import date, timedelta
from pathlib import Path
REPOSITORY = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPOSITORY / 'backend'), str(REPOSITORY / 'scripts')]
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app.main import create_app
from app.settings import Settings
from app.db import User
from app import passwords, migrate
from verify_restore import inspect_database

logging.getLogger('trendsell').disabled = True
passwords.PARAMETERS = {'n': 4096, 'r': 8, 'p': 1}
HEADERS = {'X-Requested-With': 'TrendSell'}
OPERATOR = {'X-Metrics-Token': 'verification-operator-token'}
INPUTS = dict(quantity=300, unit_cost_usd=2, fx_ngn=1500, freight_ngn=90000,
    duty_pct=5, import_tax_pct=7.5, selling_price_ngn=30000, channel_fee_pct=5,
    returns_pct=2, marketing_ngn=10000, fixed_cost_ngn=10000, stress_pct=15,
    compliance='unresolved', channel='Direct sales', shipping='Air')
# Evidence must be current to count, so the fixture dates itself relative to the run
# rather than to the day the review was written.
TODAY = date.today()
OBSERVED = (TODAY - timedelta(days=3)).isoformat()
findings = {}

with tempfile.TemporaryDirectory(prefix='trendsell-verification-') as directory:
    url = 'sqlite:///' + directory + '/verify.db'
    migrate.upgrade(url)
    app = create_app(Settings(environment='test', database_url=url, allow_registration=True,
                              metrics_token=OPERATOR['X-Metrics-Token']))
    with TestClient(app) as client:
        def call(method, path, body=None, expected=201, **extra):
            response = getattr(client, method)(path, **({'json': body} if body is not None else {}),
                                               headers={**HEADERS, **extra})
            assert response.status_code == expected, (path, response.status_code, response.text)
            return response.json()
        post = lambda path, body, expected=201, **extra: call('post', path, body, expected, **extra)

        owner = post('/api/v1/auth/register', dict(email='verify@example.test',
                     password='long-review-password', name='Verification workspace'))

        # R02 -- a legacy hash of a password with surrounding spaces must still sign in.
        original = ' long-review-password '
        salt = 'd' * 32
        digest = hashlib.scrypt(original.encode(), salt=salt.encode(), **passwords.LEGACY_PARAMETERS).hex()
        with app.state.database.session() as db:
            db.get(User, owner['id']).password_hash = salt + ':' + digest
            db.commit()
        login = client.post('/api/v1/auth/login', json={'email': 'verify@example.test',
                            'password': original}, headers=HEADERS)
        findings['R02_legacy_password_with_spaces'] = {
            'hash_verifies_directly': passwords.verify_password(original, salt + ':' + digest)[0],
            'login_status': login.status_code, 'expected_login_status': 200}

        pid = post('/api/v1/xray', {'input': 'B0C1STEAM1'}, 202)['product_id']
        post(f'/api/v1/products/{pid}/confirm', {'name': 'Disposable review product'}, 200)
        for index, metric in enumerate(['Search interest', 'Review velocity', 'Social mentions', 'Local listing count']):
            post(f'/api/v1/products/{pid}/evidence', {'metric': metric, 'value': 100, 'unit': 'count',
                 'market': 'NG' if index == 3 else 'US', 'observed_at': OBSERVED,
                 'source_name': f'Review source {index}', 'source_url': 'https://example.test/review',
                 'method': 'Manually entered test fixture'})

        def request_review():
            return post(f'/api/v1/products/{pid}/compliance/requests', {'product_id': pid,
                        'specifications': 'Disposable test specifications', 'intended_use': 'Testing only',
                        'question': 'Does this disposable test qualify?'})

        # R03 -- an approval resting on expired support, with no classification and no
        # requirements, cleared the gate. Each defect is now refused on its own.
        review = request_review()
        expired_source = {'title': 'Expired fixture publication', 'publisher': 'Test publisher',
                          'url': 'https://example.test/expired',
                          'effective_from': '2010-01-01', 'effective_to': '2011-01-01'}
        refusals = {}
        for label, body in {
            'no_classification_or_requirements': {'status': 'approved',
                'rationale': 'Disposable review approval for validation testing',
                'sources': [expired_source]},
            'expired_support_only': {'status': 'approved',
                'rationale': 'Disposable review approval for validation testing',
                'hs_code': '8516.79', 'no_additional_requirements': True,
                'sources': [expired_source]},
        }.items():
            response = client.post(f'/api/v1/compliance/reviews/{review["id"]}/decision',
                                   json=body, headers=HEADERS)
            refusals[label] = {'status': response.status_code,
                               'reason': response.json().get('detail')}
            if isinstance(refusals[label]['reason'], list):
                refusals[label]['reason'] = refusals[label]['reason'][0]['msg']
        findings['R03_expired_or_incomplete_approval'] = refusals

        # An approval that does rest on current support still works: the gate was tightened,
        # not broken.
        current_source = {'title': 'Current fixture publication', 'publisher': 'Test publisher',
                          'url': 'https://example.test/current',
                          'effective_from': (TODAY - timedelta(days=30)).isoformat(),
                          'effective_to': (TODAY + timedelta(days=365)).isoformat()}
        approved = post(f'/api/v1/compliance/reviews/{review["id"]}/decision',
                        {'status': 'approved', 'rationale': 'Disposable approval on current support',
                         'hs_code': '8516.79', 'requirements': ['Disposable test requirement statement'],
                         'sources': [current_source]}, 200)
        gate = client.get(f'/api/v1/products/{pid}/compliance').json()['gate']
        findings['R03_valid_approval_still_resolves'] = {
            'status': approved['status'], 'hs_code': approved['hs_code'],
            'gate_resolved': gate['resolved']}

        # R04 -- a rejected import review produced WATCH. The rejection must decide it.
        review = request_review()
        post(f'/api/v1/compliance/reviews/{review["id"]}/decision',
             {'status': 'rejected', 'rationale': 'This product must not be imported in this test scenario.'}, 200)
        decision = post('/api/v1/decisions', {'product_id': pid, 'inputs': INPUTS},
                        **{'Idempotency-Key': 'verify-rejected'})
        findings['R04_rejected_import_assessment'] = {
            'decision': decision['decision'], 'compliance': decision['compliance'],
            'confidence': decision['confidence'], 'expected_decision': 'NO-GO'}

        # R05 -- the workspace export omitted evidence and compliance reviews entirely.
        exported = client.get('/api/v1/export').json()
        findings['R05_export'] = {'keys': sorted(exported), 'exported_counts': exported['counts']}

        # R06 -- the restore verifier replayed evidence-bearing assessments without their
        # evidence and reported every one of them corrupt.
        report = inspect_database(url)
        findings['R06_restore_verification'] = {
            'records_by_kind': report['records_by_kind'],
            'assessment_replay_failures': report['assessment_replay_failures'],
            'expected_replay_failures': 0}

        # R07 -- arbitrary paths became permanent metric labels, and any workspace owner
        # could read every worker counter.
        client.get('/api/review-workspace-private-marker')
        with TestClient(app) as stranger:
            registered = stranger.post('/api/v1/auth/register',
                                       json={'email': 'stranger@example.test', 'password': 'long-review-password',
                                             'name': 'Second workspace'}, headers=HEADERS)
            assert registered.status_code == 201, registered.text
            as_owner = stranger.get('/api/v1/ops/metrics')
            as_operator = stranger.get('/api/v1/ops/metrics', headers=OPERATOR)
            findings['R07_cross_workspace_metrics'] = {
                'workspace_owner_status': as_owner.status_code, 'expected_owner_status': 403,
                'operator_status': as_operator.status_code,
                'foreign_marker_visible_to_owner': as_owner.status_code == 200 and
                    'GET /api/review-workspace-private-marker' in as_owner.json().get('requests', {})}
        before = len(app.state.counters.requests)
        for index in range(20):
            client.get(f'/api/review-unmatched-path-{index}')
        findings['R07_unmatched_route_labels'] = {
            'new_labels_from_20_unknown_paths': len(app.state.counters.requests) - before,
            'expected_at_most': 1}

        # R09 -- a database at head with a table dropped reported ready.
        with app.state.database.engine.begin() as connection:
            connection.execute(text('DROP TABLE audit_events'))
        readiness = client.get('/api/ready')
        findings['R09_readiness_missing_audit_table'] = {
            'status': readiness.status_code, 'expected_status': 503, 'body': readiness.json()}

    # R08 -- the documented adoption sequence, run verbatim through the same CLI.
    legacy_url = 'sqlite:///' + directory + '/legacy.db'
    migrate.upgrade(legacy_url, migrate.BASELINE)
    legacy_engine = create_engine(legacy_url)
    with legacy_engine.begin() as connection:
        connection.execute(text('DROP TABLE alembic_version'))
    legacy_engine.dispose()
    step2 = migrate.check(legacy_url, against=migrate.BASELINE)
    # The same database asked the *other* question, captured before anything changes it:
    # this is the answer the old guide told the operator to stop on.
    step2_models = migrate.check(legacy_url)
    migrate.stamp_baseline(legacy_url)
    step5 = migrate.check(legacy_url, against=migrate.BASELINE)
    migrate.upgrade(legacy_url)
    step7 = migrate.check(legacy_url)
    findings['R08_documented_legacy_migration'] = {
        'step2_against_baseline_matches': step2['matches_models'],
        'step2_revision': step2['current_revision'],
        'step2_against_models_matches': step2_models['matches_models'],
        'step2_against_models_missing_columns': step2_models['missing_columns'],
        'step5_revision': step5['current_revision'], 'step5_up_to_date': step5['up_to_date'],
        'step7_up_to_date': step7['up_to_date'], 'step7_matches_models': step7['matches_models'],
        'head_revision': step7['head_revision']}

print(json.dumps(findings, indent=2))
