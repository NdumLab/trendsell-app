"""Legacy Amazon adapter isolation and selected live-pilot orchestration.

Every provider response in this module is a test fixture.  It proves parser/job behaviour,
never a live connection or successful production collection.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.db import Record
from app.providers.amazon_creators import (AmazonCreatorsClient, AmazonCreatorsConfig,
                                           ProviderError, parse_item)
from app.settings import Settings
from conftest import HEADERS, register


INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500,
          'freight_ngn': 900000, 'duty_pct': 5, 'import_tax_pct': 7.5,
          'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


ITEM = {
    'itemsResult': {'items': [{
        'asin': 'B0ABCDEFGH',
        'detailPageURL': 'https://www.amazon.com/dp/B0ABCDEFGH?tag=pilot-20',
        'itemInfo': {
            'title': {'displayValue': 'Observed garment steamer'},
            'byLineInfo': {'brand': {'displayValue': 'Example Brand'}},
            'classifications': {'productGroup': {'displayValue': 'Home'}},
        },
        'browseNodeInfo': {'websiteSalesRank': {
            'salesRank': 321, 'contextFreeName': 'Home & Kitchen'}},
        'offersV2': {'listings': [{'price': {'money': {'amount': 24.99, 'currency': 'USD'}}}]},
    }]},
}


class Response:
    def __init__(self, body, headers=None):
        self.body = json.dumps(body).encode()
        self.headers = headers or {}

    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self): return self.body


def config():
    return AmazonCreatorsConfig('credential-id', 'credential-secret', '3.1', 'pilot-20',
                                'www.amazon.com', 'Approved internal pilot retention')


def test_get_item_uses_oauth_once_and_maps_only_supplied_fields():
    requests = []
    def open_response(request, timeout):
        requests.append((request, timeout))
        if request.full_url.endswith('/auth/o2/token'):
            return Response({'access_token': 'secret-token', 'expires_in': 3600})
        return Response(ITEM, {'x-amzn-requestid': 'provider-request-1'})

    client = AmazonCreatorsClient(config(), opener=open_response, clock=lambda: 1000)
    first = client.get_item('B0ABCDEFGH')
    second = client.get_item('B0ABCDEFGH')
    assert first['title'] == second['title'] == 'Observed garment steamer'
    assert first['website_sales_rank'] == 321
    assert first['offer_amount'] == 24.99
    assert first['offer_currency'] == 'USD'
    assert 'review_velocity' not in first and 'seller_count' not in first and 'sales' not in first
    assert sum(request.full_url.endswith('/auth/o2/token') for request, _ in requests) == 1
    catalog_request = requests[1][0]
    assert catalog_request.headers['Authorization'] == 'Bearer secret-token'
    assert json.loads(catalog_request.data)['itemIds'] == ['B0ABCDEFGH']


def test_parser_accepts_both_container_spellings_in_amazons_current_documentation():
    alternate = {'itemResults': ITEM['itemsResult']}
    assert parse_item(ITEM, 'B0ABCDEFGH')['title'] == 'Observed garment steamer'
    assert parse_item(alternate, 'B0ABCDEFGH')['title'] == 'Observed garment steamer'


def test_configuration_refuses_a_marketplace_the_pilot_would_mislabel(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('AMAZON_CREATORS_MARKETPLACE', 'www.amazon.co.uk')
    with pytest.raises(ValueError, match='www.amazon.com for this pilot'):
        Settings.from_env()


def test_provider_failures_are_classified_without_exposing_secrets():
    for failure, code in [
        (HTTPError('https://creatorsapi.amazon', 401, 'no', {}, None), 'authorization'),
        (HTTPError('https://creatorsapi.amazon', 429, 'slow', {'Retry-After':'30'}, None), 'rate_limited'),
        (URLError('offline'), 'network'),
    ]:
        def broken(_request, timeout, problem=failure): raise problem
        client = AmazonCreatorsClient(config(), opener=broken)
        try:
            client.get_item('B0ABCDEFGH')
        except ProviderError as problem:
            assert problem.code == code
            assert 'credential-secret' not in problem.detail
        else:
            raise AssertionError('provider error was not raised')


def test_an_authorised_commercial_response_resolves_identity_and_records_traceable_observations(settings):
    configured = replace(settings,
        dataforseo_enabled=True, dataforseo_login='api-login',
        dataforseo_password='api-password',
        dataforseo_usage_rights='contract-ticket-123: research/display/derive/retain 30 days')
    app = create_app(configured)
    controlled = type('ControlledCollector', (), {
        'get_catalog_item': lambda self, asin: {
            'asin': asin, 'title':'Observed garment steamer', 'brand':'Example Brand',
            'category':'Home', 'detail_page_url':'https://www.amazon.com/dp/B0ABCDEFGH',
            'offer_amount':24.99, 'offer_currency':'USD', 'request_id':'provider-request-1',
            'rating_votes':321, 'observed_at':'2026-09-17T00:00:00Z',
            'source_url':'https://www.amazon.com/dp/B0ABCDEFGH',
            'task_cost_usd':.005,
            'provider_item':ITEM['itemsResult']['items'][0],
        },
        'get_search_interest': lambda self, keyword: {
            'query':keyword, 'latest_value':64, 'observed_at':'2026-09-17T00:00:00Z',
            'source_url':'https://dataforseo.com/apis/dataforseo-trends-api',
            'request_id':'provider-request-2',
            'series':[{'date':'2026-09-16','value':64}],
            'provider_item':{'type':'dataforseo_trends_graph','data':[64]},
        }})()
    app.state.collectors['catalog'] = controlled
    app.state.collectors['search_demand'] = controlled
    with TestClient(app) as client:
        register(client)
        job = client.post('/api/v1/xray', json={'input':'B0ABCDEFGH'},
                          headers={**HEADERS, 'Idempotency-Key':'real-adapter'}).json()
        product = client.get(f'/api/v1/products/{job["product_id"]}').json()
        assert product['name'] == 'Observed garment steamer'
        assert product['confirmed'] is True
        assert product['truth_state'] == 'Observed'
        assert product['identity_source'] == 'DataForSEO Amazon API'
        metrics = {record['metric']: record for record in product['observations']}
        assert metrics['Marketplace price']['value'] == 24.99
        assert metrics['Marketplace review count']['value'] == 321
        assert metrics['Search interest']['value'] == 64
        assert all(record['truth_state'] == 'Observed' for record in metrics.values())
        assert metrics['Marketplace price']['snapshot_id'] == product['identity_snapshot_id']
        evidence = client.get(f'/api/v1/products/{job["product_id"]}/evidence').json()
        assert evidence['truth_state'] == 'Observed'
        assert 'authorised collector' in evidence['reason']
        manual = client.post(f'/api/v1/products/{job["product_id"]}/evidence', headers=HEADERS, json={
            'metric':'Social mentions', 'value':12, 'unit':'mentions', 'market':'US',
            'observed_at':datetime.now(timezone.utc).date().isoformat(),
            'source_name':'Manual social check', 'method':'Read the public profile manually',
        })
        assert manual.status_code == 201
        mixed = client.get(f'/api/v1/products/{job["product_id"]}/evidence').json()
        assert mixed['truth_state'] == 'User input'
        assert 'both collector-produced observations and records entered by people' in mixed['reason']
        finished = client.get(f'/api/v1/research-jobs/{job["id"]}').json()
        catalog = next(event for event in finished['events']
                       if event['step'] == 'Catalog identity & current offer')
        assert catalog['status'] == 'succeeded'
        assert 'No sales, history, demand or causation was inferred.' in catalog['detail']
        health = client.get('/api/v1/data-health').json()
        catalog_health = next(source for source in health['sources'] if source['id'] == 'catalog')
        assert catalog_health['last_success']
        assert catalog_health['adapter_state'] == 'implemented'
        assert catalog_health['configuration_state'] == 'configured'
        assert catalog_health['collection_state'] == 'succeeded'
        assert catalog_health['observation_state'] == 'stored_current'
        assert catalog_health['stored_observation_count'] >= 1
        assert catalog_health['api_availability_state'] == 'available'
        assert 'display_status' not in catalog_health and 'status' not in catalog_health
        workspace = client.get('/api/v1/export').json()
        assert len(workspace['source_snapshots']) == 2
        assert workspace['source_snapshots'][0]['response_sha256']
        assert workspace['source_snapshots'][0]['usage_rights'].startswith('contract-ticket-123')
        assert 'api-password' not in json.dumps(workspace)
        client.post('/api/v1/auth/logout', headers=HEADERS, json={})
        register(client, email='other-provider-workspace@example.com', name='Other source workspace')
        other_health = client.get('/api/v1/data-health').json()
        other_catalog = next(source for source in other_health['sources'] if source['id'] == 'catalog')
        assert other_catalog['configuration_state'] == 'configured'
        assert other_catalog['collection_state'] == 'never_attempted'
        assert other_catalog['last_attempt'] is None
        assert other_catalog['last_success'] is None
        assert other_catalog['observation_state'] == 'none'
        assert other_catalog['stored_observation_count'] == 0
        assert other_catalog['api_availability_state'] == 'unavailable'


def test_a_source_failure_stays_unavailable_and_does_not_create_declining_demand(settings):
    configured = replace(settings,
        dataforseo_enabled=True, dataforseo_login='api-login',
        dataforseo_password='api-password',
        dataforseo_usage_rights='contract-ticket-123')
    app = create_app(configured)
    def fail(_asin):
        raise ProviderError('network', 'DataForSEO could not be reached for this collection attempt.',
                            'Retry when provider connectivity recovers')
    app.state.collectors['catalog'] = type(
        'FailingCollector', (), {'get_catalog_item':lambda self, asin:fail(asin)})()
    with TestClient(app) as client:
        register(client)
        job = client.post('/api/v1/xray', json={'input':'B0ABCDEFGH'},
                          headers={**HEADERS, 'Idempotency-Key':'provider-failure'}).json()
        finished = client.get(f'/api/v1/research-jobs/{job["id"]}').json()
        catalog = next(event for event in finished['events']
                       if event['step'] == 'Catalog identity & current offer')
        assert catalog['status'] == 'unavailable'
        assert catalog['error_code'] == 'network'
        product = client.get(f'/api/v1/products/{job["product_id"]}').json()
        assert product['observations'] == []
        assert product['confidence'] == 0
        health = client.get('/api/v1/data-health').json()
        catalog_health = next(source for source in health['sources'] if source['id'] == 'catalog')
        assert catalog_health['configuration_state'] == 'configured'
        assert catalog_health['collection_state'] == 'failed'
        assert catalog_health['last_success'] is None
        assert catalog_health['observation_state'] == 'none'
        assert catalog_health['api_availability_state'] == 'unavailable'


def test_an_enabled_but_incomplete_connection_names_missing_server_configuration(settings):
    app = create_app(replace(settings, dataforseo_enabled=True))
    with TestClient(app) as client:
        register(client)
        source = next(item for item in client.get('/api/v1/data-health').json()['sources']
                      if item['id'] == 'catalog')
        assert source['adapter_state'] == 'implemented'
        assert source['configuration_state'] == 'missing_requirements'
        assert source['collection_state'] == 'never_attempted'
        assert source['observation_state'] == 'none'
        assert source['api_availability_state'] == 'unavailable'
        assert 'API login' in source['reason']
        assert 'API password' in source['reason']
        assert 'accepted terms/usage-basis reference' in source['reason']


def test_keyword_candidate_selection_preserves_lineage_and_requires_exact_identity_resolution(settings):
    configured = replace(settings,
        dataforseo_enabled=True, dataforseo_login='api-login',
        dataforseo_password='api-password', dataforseo_usage_rights='accepted-terms-v2026-06')
    app = create_app(configured)
    controlled = type('DiscoveryCollector', (), {
        'discover_products': lambda self, query, limit: {
            'query':query, 'observed_at':'2026-09-18T00:00:00Z',
            'source_url':'https://www.amazon.com/s?k=portable+steamer',
            'request_id':'discovery-task-1', 'task_cost_usd':.005,
            'candidates':[{'asin':'B0DISCOVER','title':'Portable steamer candidate',
                           'url':'https://www.amazon.com/dp/B0DISCOVER',
                           'position':1, 'absolute_position':2, 'result_type':'organic'}],
            'provider_item':{'type':'amazon_serp','items':['B0DISCOVER']},
        },
        'get_catalog_item': lambda self, asin: (_ for _ in ()).throw(
            ProviderError('not_found', 'The current catalog source did not resolve this exact ASIN.')),
    })()
    app.state.collectors['catalog'] = controlled
    # Search is intentionally unavailable because identity is not resolved.
    app.state.collectors['search_demand'] = None
    with TestClient(app) as client:
        register(client)
        created = client.post('/api/v1/discovery', json={'query':'portable steamer'},
                              headers={**HEADERS, 'Idempotency-Key':'discover-1'})
        assert created.status_code == 202
        discovery = client.get(f'/api/v1/discovery/{created.json()["id"]}').json()
        assert discovery['status'] == 'succeeded'
        assert discovery['truth_state'] == 'Observed'
        assert len(discovery['candidates']) == 1
        assert discovery['candidates'][0].get('price_from') is None

        selected = client.post('/api/v1/xray', json={
            'input':'B0DISCOVER', 'discovery_id':discovery['id']},
            headers={**HEADERS, 'Idempotency-Key':'selected-1'})
        assert selected.status_code == 202
        job = client.get(f'/api/v1/research-jobs/{selected.json()["id"]}').json()
        assert job['events'][0]['step'] == 'Keyword candidate selected'
        product = client.get(f'/api/v1/products/{job["product_id"]}').json()
        assert product['confirmed'] is False
        assert product['truth_state'] == 'User input'
        assert product['discovery_context']['discovery_id'] == discovery['id']
        assert product['discovery_context']['match_state'] == 'candidate_selected'
        assert product['discovery_context']['selected_asin'] == 'B0DISCOVER'
        assert 'must still resolve the exact ASIN' in product['discovery_context']['limitations']

        wrong = client.post('/api/v1/xray', json={
            'input':'B0NOTFOUND', 'discovery_id':discovery['id']},
            headers={**HEADERS, 'Idempotency-Key':'selected-wrong'})
        assert wrong.status_code == 422


def test_keyword_discovery_reports_missing_access_and_provider_empty_results_honestly(settings):
    unconfigured = create_app(settings)
    with TestClient(unconfigured) as client:
        register(client)
        row = client.post('/api/v1/discovery', json={'query':'portable steamer'},
                          headers={**HEADERS, 'Idempotency-Key':'not-configured'}).json()
        result = client.get(f'/api/v1/discovery/{row["id"]}').json()
        assert result['status'] == 'unavailable'
        assert result['error_code'] == 'not_configured'
        assert result['candidates'] == []

    configured = replace(settings,
        dataforseo_enabled=True, dataforseo_login='api-login',
        dataforseo_password='api-password', dataforseo_usage_rights='accepted-terms-v2026-06')
    app = create_app(configured)
    app.state.collectors['catalog'] = type('EmptyCollector', (), {
        'discover_products': lambda self, query, limit: (_ for _ in ()).throw(
            ProviderError('not_found', 'The provider returned no organic product candidates.')),
    })()
    with TestClient(app) as client:
        register(client, email='empty-results@example.com')
        row = client.post('/api/v1/discovery', json={'query':'unmatched phrase'},
                          headers={**HEADERS, 'Idempotency-Key':'empty'}).json()
        result = client.get(f'/api/v1/discovery/{row["id"]}').json()
        assert result['status'] == 'unavailable'
        assert result['error_code'] == 'not_found'
        assert result['candidates'] == []
        source = next(item for item in client.get('/api/v1/data-health').json()['sources']
                      if item['id'] == 'catalog')
        assert source['collection_state'] == 'failed'
        assert source['observation_state'] == 'none'
        assert source['api_availability_state'] == 'unavailable'


def test_provider_expiry_deletes_live_records_and_redacts_historical_assessment_values(settings):
    configured = replace(settings,
        dataforseo_enabled=True, dataforseo_login='api-login',
        dataforseo_password='api-password',
        dataforseo_usage_rights='accepted-terms-v2026-06; internal 30-day policy')
    app = create_app(configured)
    controlled = type('RetentionCollector', (), {
        'get_catalog_item': lambda self, asin: {
            'asin':asin, 'title':'Retention test product', 'category':'Home',
            'detail_page_url':f'https://www.amazon.com/dp/{asin}',
            'offer_amount':24.99, 'offer_currency':'USD', 'rating_votes':321,
            'request_id':'catalog-retention-1', 'observed_at':'2026-09-18T00:00:00Z',
            'source_url':f'https://www.amazon.com/dp/{asin}',
            'provider_item':{'data_asin':asin, 'title':'Retention test product'},
        },
        'get_search_interest': lambda self, keyword: {
            'query':keyword, 'latest_value':55, 'observed_at':'2026-09-18T00:00:00Z',
            'source_url':'https://dataforseo.com/apis/dataforseo-trends-api',
            'series':[{'date':'2026-09-18','value':55}],
            'provider_item':{'type':'dataforseo_trends_graph','data':[55]},
        },
    })()
    app.state.collectors['catalog'] = controlled
    app.state.collectors['search_demand'] = controlled
    with TestClient(app) as client:
        owner = register(client, email='retention@example.com')
        job = client.post('/api/v1/xray', json={'input':'B0RETENT01'},
                          headers={**HEADERS, 'Idempotency-Key':'retention-job'}).json()
        product_id = job['product_id']
        before = client.get(f'/api/v1/products/{product_id}').json()
        assert before['confirmed'] is True and before['observations']
        saved = client.post('/api/v1/decisions',
            json={'product_id':product_id, 'inputs':INPUTS},
            headers={**HEADERS, 'Idempotency-Key':'retention-decision'}).json()
        assert any(item['value'] is not None for item in saved['evidence'])
        original_inputs, original_scenarios = saved['inputs'], saved['scenarios']

        expired_at = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with app.state.database.session() as db:
            provider_rows = (db.query(Record)
                .filter(Record.workspace_id == owner['workspace_id'])
                .filter(Record.kind.in_(['evidence','source_snapshot'])).all())
            assert provider_rows
            for index, row in enumerate(provider_rows):
                # Corrupt expiry metadata must fail closed instead of retaining a
                # provider payload indefinitely; the remaining rows exercise normal expiry.
                expires_at = 'not-a-timestamp' if index == 0 else expired_at
                row.payload = {**row.payload, 'expires_at':expires_at}
            db.commit()

        after = client.get(f'/api/v1/products/{product_id}').json()
        assert after['confirmed'] is False
        assert after['truth_state'] == 'User input'
        assert after['observations'] == []
        historical = client.get(f'/api/v1/decisions/{saved["id"]}').json()
        assert historical['inputs'] == original_inputs
        assert historical['scenarios'] == original_scenarios
        assert historical['expired_evidence_count'] == len(saved['evidence'])
        assert historical['evidence_retention_applied_at']
        assert all(item['retention_state'] == 'expired' for item in historical['evidence'])
        assert all(item['value'] is None and item['source_url'] is None
                   for item in historical['evidence'])
        assert all('series' not in item for item in historical['evidence'])

        exported = client.get('/api/v1/export').json()
        assert exported['evidence'] == []
        assert exported['source_snapshots'] == []
        health = client.get('/api/v1/data-health').json()
        catalog = next(item for item in health['sources'] if item['id'] == 'catalog')
        assert catalog['collection_state'] == 'succeeded'
        assert catalog['observation_state'] == 'none'
        assert catalog['api_availability_state'] == 'unavailable'


def test_disabling_configuration_does_not_erase_collection_history_from_typed_health(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        owner = register(client, email='disabled-health@example.com')
        with app.state.database.session() as db:
            db.add(Record(
                workspace_id=owner['workspace_id'], kind='source_status', key='catalog',
                payload={'status':'connected', 'last_attempt':'2026-09-18T00:00:00Z',
                         'last_success':'2026-09-18T00:00:01Z',
                         'reason':'A prior collection succeeded.'}))
            db.commit()

        catalog = next(item for item in client.get('/api/v1/data-health').json()['sources']
                       if item['id'] == 'catalog')
        assert catalog['configuration_state'] == 'disabled'
        assert catalog['collection_state'] == 'succeeded'
        assert catalog['last_success'] == '2026-09-18T00:00:01Z'
        assert catalog['observation_state'] == 'none'
        assert catalog['api_availability_state'] == 'unavailable'
