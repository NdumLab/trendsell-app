"""Disposable browser-test app with explicit provider fixtures.

These responses never leave the local test process and must never be counted as live
collection. Only the sentinel keyword/ASIN succeeds, so the existing manual-flow browser
tests still exercise missing provider data honestly.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.main import create_app
from app.providers.common import ProviderError
from app.settings import Settings


FIXTURE_ASIN = 'B0E2ELIVE1'


def timestamp(days=0):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace('+00:00', 'Z')


class DataForSEOFixture:
    def discover_products(self, keyword, limit=10):
        if keyword.strip().lower() != 'fixture portable steamer':
            raise ProviderError('not_found', 'The fixture provider returned no organic product candidates.')
        candidate = {
            'asin': FIXTURE_ASIN, 'title': '[Fixture] Portable garment steamer',
            'url': f'https://www.amazon.com/dp/{FIXTURE_ASIN}',
            'position': 1, 'absolute_position': 2, 'price_from': 29.50,
            'currency': 'USD', 'rating': 4.4, 'rating_votes': 88,
            'bought_past_month_indicator': 400, 'result_type': 'organic',
        }
        return {
            'query': keyword, 'candidates': [candidate][:limit], 'observed_at': timestamp(),
            'source_url': 'https://www.amazon.com/s?k=fixture+portable+steamer',
            'request_id': 'fixture-discovery-1', 'task_cost_usd': 0.005,
            'provider_item': {'fixture': True, 'items': [candidate]},
        }

    def get_catalog_item(self, asin):
        if asin != FIXTURE_ASIN:
            raise ProviderError('not_found', 'The fixture catalog did not resolve this ASIN.')
        return {
            'asin': asin, 'title': '[Fixture] Portable garment steamer',
            'brand': 'Fixture Brand', 'category': 'Home',
            'detail_page_url': f'https://www.amazon.com/dp/{asin}',
            'offer_amount': 29.50, 'offer_currency': 'USD',
            'rating': 4.4, 'rating_votes': 88, 'observed_at': timestamp(),
            'source_url': f'https://www.amazon.com/dp/{asin}',
            'request_id': 'fixture-catalog-1', 'task_cost_usd': 0.005,
            'provider_item': {'fixture': True, 'data_asin': asin},
        }

    def get_search_interest(self, keyword):
        if keyword != 'fixture portable steamer':
            raise ProviderError('not_found', 'The fixture trends source returned no series.')
        return {
            'query': keyword, 'latest_value': 64, 'observed_at': timestamp(),
            'source_url': 'https://dataforseo.com/apis/dataforseo-trends-api',
            'request_id': 'fixture-trends-1', 'task_cost_usd': 0.0012,
            'series': [
                {'date': timestamp(-2)[:10], 'value': 42},
                {'date': timestamp(-1)[:10], 'value': 51},
                {'date': timestamp()[:10], 'value': 64},
            ],
            'provider_item': {'fixture': True, 'type': 'dataforseo_trends_graph'},
        }


class BrightDataFixture:
    def search(self, keyword):
        if keyword != '[Fixture] Portable garment steamer':
            raise ProviderError('not_found', 'The fixture local-market source returned no listings.')
        candidates = [{
            'title': '[Fixture] Portable garment steamer 1200W',
            'brand': 'Fixture Brand', 'price': 45000, 'currency': 'NGN',
            'rating': 4.1, 'rating_count': 17, 'availability': True,
            'seller': 'Fixture seller',
            'url': 'https://www.jumia.com.ng/fixture-portable-steamer.html',
        }]
        return {
            'query': keyword, 'candidates': candidates, 'observed_at': timestamp(),
            'source_url': 'https://www.jumia.com.ng/catalog/?q=fixture+portable+steamer',
            'request_id': 'fixture-jumia-1',
            'provider_item': {'fixture': True, 'rows': candidates},
        }


def create_e2e_app():
    settings = replace(
        Settings.from_env(),
        dataforseo_enabled=True, dataforseo_login='fixture-login',
        dataforseo_password='fixture-password',
        dataforseo_usage_rights='TEST FIXTURE ONLY; accepted-terms simulation',
        brightdata_jumia_enabled=True, brightdata_api_token='fixture-token',
        brightdata_jumia_dataset_id='fixture-dataset',
        brightdata_jumia_usage_rights='TEST FIXTURE ONLY; intended-use simulation',
    )
    app = create_app(settings)
    dataforseo = DataForSEOFixture()
    app.state.collectors['catalog'] = dataforseo
    app.state.collectors['search_demand'] = dataforseo
    app.state.collectors['local_market'] = BrightDataFixture()
    return app
