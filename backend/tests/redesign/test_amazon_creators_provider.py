"""Amazon Creators API adapter and X-Ray integration, using controlled responses only."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.providers.amazon_creators import (AmazonCreatorsClient, AmazonCreatorsConfig,
                                           ProviderError, parse_item)
from app.settings import Settings
from conftest import HEADERS, register


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


def test_an_authorised_response_resolves_identity_and_records_traceable_current_observations(settings):
    configured = replace(settings,
        amazon_creators_enabled=True,
        amazon_creators_credential_id='credential-id',
        amazon_creators_credential_secret='credential-secret',
        amazon_creators_partner_tag='pilot-20',
        amazon_creators_usage_rights='Approved internal pilot retention')
    app = create_app(configured)
    app.state.amazon_creators = type('ControlledCollector', (), {
        'get_item': lambda self, asin: {
            'asin': asin, 'title':'Observed garment steamer', 'brand':'Example Brand',
            'category':'Home', 'detail_page_url':'https://www.amazon.com/dp/B0ABCDEFGH?tag=pilot-20',
            'website_sales_rank':321, 'rank_category':'Home & Kitchen',
            'offer_amount':24.99, 'offer_currency':'USD', 'request_id':'provider-request-1',
            'provider_item':ITEM['itemsResult']['items'][0],
        }})()
    with TestClient(app) as client:
        register(client)
        job = client.post('/api/v1/xray', json={'input':'B0ABCDEFGH'},
                          headers={**HEADERS, 'Idempotency-Key':'real-adapter'}).json()
        product = client.get(f'/api/v1/products/{job["product_id"]}').json()
        assert product['name'] == 'Observed garment steamer'
        assert product['confirmed'] is True
        assert product['truth_state'] == 'Observed'
        assert product['identity_source'] == 'Amazon Creators API'
        metrics = {record['metric']: record for record in product['observations']}
        assert metrics['Marketplace rank']['value'] == 321
        assert metrics['Marketplace price']['value'] == 24.99
        assert all(record['truth_state'] == 'Observed' for record in metrics.values())
        assert all(record['snapshot_id'] == product['identity_snapshot_id'] for record in metrics.values())
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
        amazon = next(event for event in finished['events'] if event['step'] == 'Amazon catalog')
        assert amazon['status'] == 'succeeded'
        assert 'Sales history, review velocity, and seller counts were not requested or inferred.' in amazon['detail']
        health = client.get('/api/v1/data-health').json()
        amazon_health = next(source for source in health['sources'] if source['id'] == 'amazon')
        assert amazon_health['status'] == 'connected'
        assert amazon_health['last_success']
        workspace = client.get('/api/v1/export').json()
        assert len(workspace['source_snapshots']) == 1
        assert workspace['source_snapshots'][0]['response_sha256']
        assert workspace['source_snapshots'][0]['usage_rights'] == 'Approved internal pilot retention'
        assert 'credential-secret' not in json.dumps(workspace)
        client.post('/api/v1/auth/logout', headers=HEADERS, json={})
        register(client, email='other-provider-workspace@example.com', name='Other source workspace')
        other_health = client.get('/api/v1/data-health').json()
        other_amazon = next(source for source in other_health['sources'] if source['id'] == 'amazon')
        assert other_amazon['status'] == 'configured'
        assert other_amazon['last_attempt'] is None
        assert other_amazon['last_success'] is None


def test_a_source_failure_stays_unavailable_and_does_not_create_declining_demand(settings):
    configured = replace(settings,
        amazon_creators_enabled=True,
        amazon_creators_credential_id='credential-id',
        amazon_creators_credential_secret='credential-secret',
        amazon_creators_partner_tag='pilot-20',
        amazon_creators_usage_rights='Approved internal pilot retention')
    app = create_app(configured)
    def fail(_asin):
        raise ProviderError('network', 'Amazon could not be reached for this collection attempt.',
                            'Retry when provider connectivity recovers')
    app.state.amazon_creators = type('FailingCollector', (), {'get_item':lambda self, asin:fail(asin)})()
    with TestClient(app) as client:
        register(client)
        job = client.post('/api/v1/xray', json={'input':'B0ABCDEFGH'},
                          headers={**HEADERS, 'Idempotency-Key':'provider-failure'}).json()
        finished = client.get(f'/api/v1/research-jobs/{job["id"]}').json()
        amazon = next(event for event in finished['events'] if event['step'] == 'Amazon catalog')
        assert amazon['status'] == 'unavailable'
        assert amazon['error_code'] == 'network'
        product = client.get(f'/api/v1/products/{job["product_id"]}').json()
        assert product['observations'] == []
        assert product['confidence'] == 0
        health = client.get('/api/v1/data-health').json()
        amazon_health = next(source for source in health['sources'] if source['id'] == 'amazon')
        assert amazon_health['status'] == 'degraded'
        assert amazon_health['last_success'] is None


def test_an_enabled_but_incomplete_connection_names_missing_server_configuration(settings):
    app = create_app(replace(settings, amazon_creators_enabled=True))
    with TestClient(app) as client:
        register(client)
        source = next(item for item in client.get('/api/v1/data-health').json()['sources']
                      if item['id'] == 'amazon')
        assert source['status'] == 'misconfigured'
        assert 'credential id' in source['reason']
        assert 'credential secret' in source['reason']
        assert 'partner tag' in source['reason']
        assert 'usage-rights and retention approval' in source['reason']
