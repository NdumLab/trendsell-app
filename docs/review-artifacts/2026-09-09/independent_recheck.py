"""Independent follow-up reproductions; disposable test data only.

Run with the repository venv. By default uses a temporary SQLite file. With
--postgres, uses a fresh UUID schema in the documented disposable test instance
at 127.0.0.1:55433, and drops only that schema in finally. No live records read.
The concurrency case synchronizes two requests after both have validated the
same token, without altering application logic or the resulting SQL writes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
import logging
from pathlib import Path
import sys
import tempfile
from threading import Barrier
import uuid
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'backend')]
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app import passwords, migrate
from app.db import Record
from app.main import create_app
from app.settings import Settings

logging.getLogger('trendsell').disabled = True
passwords.PARAMETERS = {'n': 4096, 'r': 8, 'p': 1}
HEADERS = {'X-Requested-With': 'TrendSell'}
OLD = 'original-review-password'
CHANGED = 'changed-review-password'
RESET = 'reset-review-password'
OPERATOR = 'independent-review-operator'


def check(url, postgres=False):
    migrate.upgrade(url)
    app = create_app(Settings(environment='test', database_url=url,
                             allow_registration=True, mail_transport='sink',
                             metrics_token=OPERATOR))
    results = {}
    with TestClient(app) as client:
        def post(path, body, expected=200):
            response = client.post(path, json=body, headers=HEADERS)
            assert response.status_code == expected, (path, response.status_code, response.text)
            return response.json()

        post('/api/v1/auth/register', {'email': 'review@example.test',
                                     'password': OLD, 'name': 'Disposable review'}, 201)
        post('/api/v1/auth/recovery/request', {'email': 'review@example.test'}, 202)
        token = app.state.mailer.latest().body.split('Reset token: ', 1)[1].splitlines()[0]
        post('/api/v1/auth/password', {'current_password': OLD, 'new_password': CHANGED})
        response = client.post('/api/v1/auth/recovery/reset',
                               json={'token': token, 'password': RESET}, headers=HEADERS)
        results['reset_token_after_password_change'] = {
            'reset_status': response.status_code, 'expected_status': 400,
            'changed_password_login': client.post('/api/v1/auth/login',
                json={'email': 'review@example.test', 'password': CHANGED}, headers=HEADERS).status_code,
            'reset_password_login': client.post('/api/v1/auth/login',
                json={'email': 'review@example.test', 'password': RESET}, headers=HEADERS).status_code,
        }

        pid = post('/api/v1/xray', {'input': 'B0CHECK001'}, 202)['product_id']
        post(f'/api/v1/products/{pid}/confirm', {'name': 'Disposable classification specimen'})
        request = {'product_id': pid, 'specifications': 'Disposable testing specifications',
                   'intended_use': 'Local software testing', 'question': 'Disposable review question?'}
        review = post(f'/api/v1/products/{pid}/compliance/requests', request, 201)
        source = {'title': 'Disposable source', 'publisher': 'Test publisher',
                  'url': 'https://example.test/fixture',
                  'effective_from': (date.today() - timedelta(days=3)).isoformat()}
        response = client.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', headers=HEADERS,
                               json={'status': 'approved', 'rationale': 'Disposable reviewed rationale',
                                     'hs_code': '.', 'no_additional_requirements': True,
                                     'sources': [source]})
        results['punctuation_only_classification'] = {
            'approval_status': response.status_code, 'expected_status': 422,
            'gate': client.get(f'/api/v1/products/{pid}/compliance').json()['gate'],
        }
        # A record the previous release accepted, with CURRENT sources but no reviewed
        # classification or requirements. Upgrade validation must cover existing data too.
        with app.state.database.session() as db:
            row = db.get(Record, review['id'])
            row.payload = {**row.payload, 'hs_code': '', 'requirements': [],
                           'no_additional_requirements': False}
            db.commit()
        results['legacy_incomplete_approval'] = {
            'gate': client.get(f'/api/v1/products/{pid}/compliance').json()['gate'],
            'expected_resolved': False,
        }

        # A CSRF rejection occurs BEFORE routing; a catch-all route cannot protect it.
        before = len(app.state.counters.requests)
        for i in range(20):
            assert client.post(f'/api/review-private-marker-{i}').status_code == 403
        metrics = client.get('/api/v1/ops/metrics', headers={'X-Metrics-Token': OPERATOR}).json()
        results['pre_router_metrics_paths'] = {
            'new_labels': len(app.state.counters.requests) - before - 1,
            'expected_at_most': 1,
            'raw_marker_retained': any('review-private-marker-' in label for label in metrics['requests']),
            'owner_metrics_status': client.get('/api/v1/ops/metrics').status_code,
        }

        if postgres:
            post('/api/v1/auth/recovery/request', {'email': 'review@example.test'}, 202)
            token = app.state.mailer.latest().body.split('Reset token: ', 1)[1].splitlines()[0]
            barrier = Barrier(2, timeout=15)
            original_hash = passwords.hash_password

            def synchronized_hash(value):
                barrier.wait()
                return original_hash(value)

            def redeem(value):
                with TestClient(app) as other:
                    return other.post('/api/v1/auth/recovery/reset',
                                      json={'token': token, 'password': value},
                                      headers=HEADERS).status_code

            with patch('app.main.hash_password', synchronized_hash):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(redeem, 'parallel-first-password')
                    second = pool.submit(redeem, 'parallel-second-password')
                    statuses = [first.result(timeout=30), second.result(timeout=30)]
            results['concurrent_reset_single_use'] = {
                'statuses': statuses, 'expected_successes': 1,
                'actual_successes': statuses.count(200),
            }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres', action='store_true')
    args = parser.parse_args()
    if not args.postgres:
        with tempfile.TemporaryDirectory(prefix='trendsell-independent-review-') as directory:
            print(json.dumps(check(f'sqlite:///{directory}/review.db'), indent=2))
        return
    base = 'postgresql+psycopg://trendsell_test:disposable@127.0.0.1:55433/trendsell_test'
    schema = 'independent_review_' + uuid.uuid4().hex
    engine = create_engine(base, isolation_level='AUTOCOMMIT')
    with engine.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        print(json.dumps(check(f'{base}?options=-csearch_path%3D{schema}', postgres=True), indent=2))
    finally:
        with engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == '__main__':
    main()
