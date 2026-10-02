"""Selected provider adapters, entirely from fixtures (never counted as live collection)."""
import json
from urllib.error import HTTPError

import pytest

from app.providers.common import ProviderError
from app.providers.live_sources import (
    BrightDataConfig, BrightDataJumiaClient, DataForSEOClient, DataForSEOConfig,
    OpenExchangeRatesClient, OpenExchangeRatesConfig, match_jumia_candidates,
)


class Response:
    def __init__(self, body, headers=None, status=200):
        self.body = json.dumps(body).encode()
        self.headers = headers or {}
        self.status = status

    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, size=-1): return self.body if size < 0 else self.body[:size]


def task(result, *, task_id='task-1', cost=.005):
    return {'status_code':20000, 'tasks':[{
        'id':task_id, 'status_code':20000, 'cost':cost, 'result':[result],
    }]}


def test_dataforseo_maps_catalog_and_trends_without_inventing_sales():
    calls = []
    def open_response(request, timeout):
        calls.append(request)
        if '/merchant/amazon/asin/' in request.full_url:
            return Response(task({
                'datetime':'2026-09-17 00:01:02 +00:00',
                'check_url':'https://www.amazon.com/dp/B0ABCDEFGH',
                'items':[{'data_asin':'B0ABCDEFGH', 'title':'Observed steamer',
                          'author':'Example', 'categories':[{'name':'Home'}],
                          'image_url':'https://m.media-amazon.com/example.jpg',
                          'price_from':24.99,'currency':'USD',
                          'rating':{'value':4.3,'votes_count':321}}],
            }))
        if '/merchant/amazon/products/' in request.full_url:
            return Response(task({
                'datetime':'2026-09-17 00:02:03 +00:00',
                'check_url':'https://www.amazon.com/s?k=garment+steamer',
                'items':[
                    {'type':'amazon_paid','data_asin':'B0SPONSORED','title':'Sponsored'},
                    {'type':'amazon_serp','rank_group':1,'rank_absolute':2,
                     'data_asin':'B0DISCOVER','title':'Discovered steamer',
                     'url':'https://www.amazon.com/dp/B0DISCOVER','price_from':29.5,
                     'currency':'USD','bought_past_month':400,
                     'rating':{'value':4.4,'votes_count':88}},
                ],
            }, task_id='task-discovery'))
        return Response(task({
            'datetime':'2026-09-17 00:03:04 +00:00',
            'items':[{'type':'dataforseo_trends_graph','data':[
                {'date_from':'2026-09-15','date_to':'2026-09-15','values':[42]},
                {'date_from':'2026-09-16','date_to':'2026-09-16','values':[64]},
            ]}],
        }, task_id='task-2', cost=.0012))
    client = DataForSEOClient(DataForSEOConfig('login','password'), opener=open_response,
                              sleeper=lambda _:None)
    catalog = client.get_catalog_item('B0ABCDEFGH')
    discovery = client.discover_products('garment steamer', limit=5)
    trends = client.get_search_interest('Observed steamer')
    assert catalog['offer_amount'] == 24.99
    assert catalog['rating_votes'] == 321
    assert catalog['category'] == 'Home'
    assert catalog['author'] == 'Example'
    assert 'image_url' not in catalog
    assert catalog['observed_at'] == '2026-09-17T00:01:02Z'
    assert 'sales' not in catalog and 'sales_history' not in catalog
    assert [item['asin'] for item in discovery['candidates']] == ['B0DISCOVER']
    assert discovery['candidates'][0]['bought_past_month_indicator'] == 400
    assert discovery['candidates'][0]['result_type'] == 'organic'
    assert trends['latest_value'] == 64
    assert trends['series'][0] == {'date':'2026-09-15','value':42}
    assert all(request.headers['Authorization'].startswith('Basic ') for request in calls)
    assert all('password' not in request.full_url for request in calls)


def test_dataforseo_trends_maps_documented_insufficient_data_zero_to_a_gap():
    client = DataForSEOClient(
        DataForSEOConfig('login','password'), opener=lambda request, timeout: Response(task({
            'datetime':'2026-09-17 00:03:04 +00:00',
            'items':[{'type':'dataforseo_trends_graph','data':[
                {'date_from':'2026-09-15','date_to':'2026-09-15','values':[42]},
                {'date_from':'2026-09-16','date_to':'2026-09-16','values':[0]},
            ]}],
        })), sleeper=lambda _:None)
    result = client.get_search_interest('Observed steamer')
    assert result['series'] == [
        {'date':'2026-09-15','value':42},
        {'date':'2026-09-16','value':None},
    ]
    assert result['latest_value'] == 42


def test_transport_retries_only_transient_failure_before_success():
    calls = 0
    def flaky(_request, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise HTTPError('https://api.dataforseo.com', 503, 'later', {}, None)
        return Response(task({'datetime':'2026-09-17 00:00:00 +00:00',
                              'check_url':'https://www.amazon.com/dp/B0ABCDEFGH', 'items':[
            {'data_asin':'B0ABCDEFGH','title':'Product'}]}))
    client = DataForSEOClient(DataForSEOConfig('login','password'), opener=flaky,
                              sleeper=lambda _:None)
    assert client.get_catalog_item('B0ABCDEFGH')['title'] == 'Product'
    assert calls == 3


def test_dataforseo_retries_internal_transient_codes_returned_over_http_200():
    calls = 0
    def flaky(_request, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            return Response({'status_code':20000, 'tasks':[{
                'status_code':50301, 'status_message':'upstream unavailable'}]})
        return Response(task({'datetime':'2026-09-17 00:00:00 +00:00',
                              'check_url':'https://www.amazon.com/dp/B0ABCDEFGH',
                              'items':[{'data_asin':'B0ABCDEFGH','title':'Product'}]}))
    client = DataForSEOClient(DataForSEOConfig('login','password'), opener=flaky,
                              sleeper=lambda _:None)
    assert client.get_catalog_item('B0ABCDEFGH')['title'] == 'Product'
    assert calls == 3


@pytest.mark.parametrize(('status_code', 'error_code'), [
    (40104, 'authorization'), (40202, 'rate_limited'), (40210, 'quota_exceeded'),
    (40102, 'not_found'), (40505, 'configuration'),
])
def test_dataforseo_classifies_internal_failures_without_exposing_provider_text(
        status_code, error_code):
    client = DataForSEOClient(
        DataForSEOConfig('login','password'),
        opener=lambda request, timeout: Response({'status_code':20000, 'tasks':[{
            'status_code':status_code, 'status_message':'secret provider detail'}]}),
        sleeper=lambda _:None)
    with pytest.raises(ProviderError) as raised:
        client.get_catalog_item('B0ABCDEFGH')
    assert raised.value.code == error_code
    assert 'secret provider detail' not in raised.value.detail


def test_provider_responses_are_size_bounded():
    client = DataForSEOClient(
        DataForSEOConfig('login','password'),
        opener=lambda request, timeout: Response('x' * (10 * 1024 * 1024 + 1)),
        sleeper=lambda _:None)
    with pytest.raises(ProviderError) as raised:
        client.get_catalog_item('B0ABCDEFGH')
    assert raised.value.code == 'invalid_response'
    assert 'safety limit' in raised.value.detail


def test_jumia_adapter_keeps_results_as_candidates_and_does_not_claim_total_coverage():
    def open_response(request, timeout):
        body = json.loads(request.data)
        assert body['input'][0]['country'] == 'NG'
        return Response([{'name':'Example portable garment steamer 1200W',
                          'brand':'Example', 'price':45000,
                          'url':'https://www.jumia.com.ng/example-steamer.html'}],
                        {'x-request-id':'bright-1'})
    client = BrightDataJumiaClient(BrightDataConfig('token','dataset-id'),
                                   opener=open_response, sleeper=lambda _:None)
    result = client.search('Example garment steamer')
    ranked = match_jumia_candidates('Example garment steamer', 'Example', result['candidates'])
    assert ranked[0]['match_status'] == 'candidate'
    assert ranked[0]['match_score'] > 0
    assert 'human review required' in ranked[0]['match_method']
    assert result['request_id'] == 'bright-1'


def test_provider_links_are_restricted_to_the_expected_https_marketplace_hosts():
    dataforseo = DataForSEOClient(
        DataForSEOConfig('login','password'), opener=lambda request, timeout: Response(task({
            'datetime':'2026-09-17 00:00:00 +00:00',
            'check_url':'javascript:alert(1)',
            'items':[{'data_asin':'B0ABCDEFGH','title':'Product'}],
        })), sleeper=lambda _:None)
    with pytest.raises(ProviderError) as amazon_problem:
        dataforseo.get_catalog_item('B0ABCDEFGH')
    assert amazon_problem.value.code == 'invalid_response'

    brightdata = BrightDataJumiaClient(
        BrightDataConfig('token','dataset-id'), opener=lambda request, timeout: Response([{
            'title':'Product', 'url':'https://attacker.example/product'}]),
        sleeper=lambda _:None)
    with pytest.raises(ProviderError) as jumia_problem:
        brightdata.search('Product')
    assert jumia_problem.value.code == 'invalid_response'


def test_discovery_rejects_an_unexpected_clickable_search_source():
    client = DataForSEOClient(
        DataForSEOConfig('login','password'), opener=lambda request, timeout: Response(task({
            'datetime':'2026-09-17 00:00:00 +00:00',
            'check_url':'https://attacker.example/search',
            'items':[{'type':'amazon_serp', 'data_asin':'B0DISCOVER',
                      'title':'Product', 'url':'https://www.amazon.com/dp/B0DISCOVER'}],
        })), sleeper=lambda _:None)
    with pytest.raises(ProviderError) as problem:
        client.discover_products('Product')
    assert problem.value.code == 'invalid_response'


def test_jumia_adapter_preserves_zero_and_false_observations():
    client = BrightDataJumiaClient(
        BrightDataConfig('token','dataset-id'), opener=lambda request, timeout: Response([{
            'title':'Observed product', 'price':0, 'rating_count':0, 'availability':False,
            'url':'https://www.jumia.com.ng/observed.html'}]), sleeper=lambda _:None)
    candidate = client.search('Observed product')['candidates'][0]
    assert candidate['price'] == 0
    assert candidate['rating_count'] == 0
    assert candidate['availability'] is False


def test_jumia_adapter_retrieves_a_delayed_snapshot_with_bounded_polling():
    calls = []
    def open_response(request, timeout):
        calls.append(request.full_url)
        if '/scrape?' in request.full_url:
            return Response({'snapshot_id':'s_delayed'}, status=202)
        if '/progress/' in request.full_url:
            return Response({'snapshot_id':'s_delayed', 'status':'ready'})
        return Response([{'title':'Observed product', 'price':12000,
                          'url':'https://www.jumia.com.ng/observed.html'}])
    client = BrightDataJumiaClient(
        BrightDataConfig('token','dataset-id', poll_attempts=2, poll_interval_seconds=0),
        opener=open_response, sleeper=lambda _:None)
    result = client.search('Observed product')
    assert result['request_id'] == 's_delayed'
    assert result['candidates'][0]['price'] == 12000
    assert calls[1].endswith('/progress/s_delayed')
    assert calls[2].endswith('/snapshot/s_delayed?format=json')


def test_open_exchange_rates_retains_source_pairs_and_labels_no_regulatory_rate():
    client = OpenExchangeRatesClient(OpenExchangeRatesConfig('app-id'), opener=lambda request, timeout:
        Response({'timestamp':1789603200,'base':'USD','rates':{'NGN':1600.0,'CNY':7.2}}),
        sleeper=lambda _:None)
    result = client.latest()
    assert result['usd_ngn'] == 1600.0
    assert result['usd_cny'] == 7.2
    assert set(result['provider_item']['rates']) == {'NGN','CNY'}


@pytest.mark.parametrize('bad_rate', [0, -1, True, float('inf'), float('nan')])
def test_open_exchange_rates_rejects_non_positive_or_non_finite_rates(bad_rate):
    client = OpenExchangeRatesClient(OpenExchangeRatesConfig('app-id'), opener=lambda request, timeout:
        Response({'timestamp':1789603200,'base':'USD','rates':{'NGN':1600.0,'CNY':bad_rate}}),
        sleeper=lambda _:None)
    with pytest.raises(ProviderError) as raised:
        client.latest()
    assert raised.value.code == 'invalid_response'


@pytest.mark.parametrize('bad_timestamp', [0, -1, True, float('inf'), float('nan')])
def test_open_exchange_rates_rejects_invalid_observation_timestamps(bad_timestamp):
    client = OpenExchangeRatesClient(OpenExchangeRatesConfig('app-id'), opener=lambda request, timeout:
        Response({'timestamp':bad_timestamp,'base':'USD','rates':{'NGN':1600.0,'CNY':7.2}}),
        sleeper=lambda _:None)
    with pytest.raises(ProviderError) as raised:
        client.latest()
    assert raised.value.code == 'invalid_response'
