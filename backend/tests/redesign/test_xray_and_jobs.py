"""X-Ray capture, identifier safety, job honesty and idempotency."""
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'


def create(client, key='job-1', payload=None):
    return client.post('/api/v1/xray', json=payload or {'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': key})


def test_a_supported_url_creates_a_job_and_a_canonical_product(client, owner):
    response = create(client)
    assert response.status_code == 202
    job = response.json()
    product = client.get(f'/api/v1/products/{job["product_id"]}').json()
    assert product['asin'] == 'B0ABCDEFGH'
    assert product['confirmed'] is False
    assert product['truth_state'] == 'User input'
    assert product['decision'] == 'INSUFFICIENT EVIDENCE'
    assert product['confidence'] == 0


def test_a_bare_asin_is_accepted(client, owner):
    assert create(client, payload={'input': 'B0ABCDEFGH'}).status_code == 202


def test_the_job_never_reports_a_source_that_did_not_run(client, owner):
    job = client.get(f'/api/v1/research-jobs/{create(client).json()["id"]}').json()
    assert job['status'] == 'partial'
    steps = {event['step']: event['status'] for event in job['events']}
    assert steps['Amazon identifier captured'] == 'succeeded'
    assert steps['Amazon catalog'] == 'unavailable'
    assert steps['Google Trends'] == 'unavailable'
    assert 'succeeded' not in [steps['Amazon catalog'], steps['Google Trends']]
    for event in job['events']:
        assert event['detail'] and event['at']


def test_event_ids_are_unique_and_ordered(client, owner):
    events = client.get(f'/api/v1/research-jobs/{create(client).json()["id"]}').json()['events']
    ids = [event['id'] for event in events]
    assert ids == sorted(ids) == list(range(1, len(ids) + 1))


def test_the_event_stream_resumes_from_a_cursor(client, owner):
    job_id = create(client).json()['id']
    stream = client.get(f'/api/v1/research-jobs/{job_id}/events', headers={'Last-Event-Id': '2'})
    assert stream.status_code == 200
    assert stream.headers['content-type'].startswith('text/event-stream')
    assert 'id: 1\n' not in stream.text and 'id: 3\n' in stream.text


def test_an_invalid_cursor_is_refused(client, owner):
    job_id = create(client).json()['id']
    assert client.get(f'/api/v1/research-jobs/{job_id}/events', headers={'Last-Event-Id': 'nope'}).status_code == 422


def test_the_same_input_and_key_is_idempotent(client, owner):
    first, second = create(client).json(), create(client).json()
    assert first['id'] == second['id']
    assert len(client.get('/api/v1/products').json()['products']) == 1


def test_the_same_input_twice_reuses_the_canonical_product(client, owner):
    first, second = create(client, key='a').json(), create(client, key='b').json()
    assert first['id'] != second['id']
    assert first['product_id'] == second['product_id']


def test_a_reused_key_with_a_different_request_is_refused(client, owner):
    create(client, key='same')
    conflict = create(client, key='same', payload={'input': 'B0ZZZZZZZZ'})
    assert conflict.status_code == 409


def test_refresh_queues_collection_without_changing_the_score(client, owner):
    product_id = create(client).json()['product_id']
    client.post(f'/api/v1/products/{product_id}/confirm', json={'name': 'Portable garment steamer'}, headers=HEADERS)
    before = client.get(f'/api/v1/products/{product_id}').json()
    assert client.post(f'/api/v1/products/{product_id}/refresh', json={}, headers={**HEADERS, 'Idempotency-Key': 'r1'}).status_code == 202
    after = client.get(f'/api/v1/products/{product_id}').json()
    assert (after['confidence'], after['decision']) == (before['confidence'], before['decision'])


def test_confirmation_records_the_user_supplied_name_only(client, owner):
    product_id = create(client).json()['product_id']
    product = client.post(f'/api/v1/products/{product_id}/confirm', json={'name': '  Portable garment steamer  '}, headers=HEADERS).json()
    assert product['name'] == 'Portable garment steamer'
    assert product['confirmed'] is True
    assert product['confidence'] == 0


def test_evidence_and_timeline_report_unavailable_rather_than_empty_success(client, owner):
    product_id = create(client).json()['product_id']
    for path in ('evidence', 'timeline'):
        body = client.get(f'/api/v1/products/{product_id}/{path}').json()
        assert body['observations'] == []
        assert body['truth_state'] == 'Unavailable'
        assert body['reason']


def test_data_health_reports_every_source_as_unconfigured(client):
    body = client.get('/api/v1/data-health').json()
    assert body['coverage'] is None
    assert body['sources']
    for source in body['sources']:
        assert source['status'] == 'unconfigured'
        assert source['last_success'] is None
        assert source['reason'] and source['rights']


def test_alerts_are_reported_as_unavailable_not_quiet(client, owner):
    body = client.get('/api/v1/alerts').json()
    assert body['alerts'] == []
    assert body['status'] == 'unavailable'
    assert body['reason']


def test_a_new_workspace_contains_no_demo_or_seeded_records(client, owner):
    assert client.get('/api/v1/products').json()['products'] == []
    assert client.get('/api/v1/decisions').json()['decisions'] == []
    assert client.get('/api/v1/quotes').json()['quotes'] == []
    assert client.get('/api/v1/watchlists/default/items').json()['items'] == []
    assert client.get('/api/health').json()['demo'] is False


def test_the_daily_research_quota_is_enforced(client, owner, settings):
    for index in range(settings.research_daily_limit):
        assert create(client, key=f'quota-{index}').status_code == 202
    assert create(client, key='quota-over').status_code == 429
