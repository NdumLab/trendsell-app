"""Adapters for the minimum live-evidence pilot.

These adapters map only fields a provider actually returns.  They do not manufacture
sales, demand, geography, causality, or product matches.  Callers must separately gate
configuration on a documented right to use, display, derive from, and retain the data.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .common import ProviderError


DATAFORSEO_COLLECTOR_VERSION = 'dataforseo-live/1.0.0'
DATAFORSEO_PARSER_VERSION = 'dataforseo-catalog-trends/1.0.0'
BRIGHTDATA_COLLECTOR_VERSION = 'brightdata-jumia-custom/1.0.0'
BRIGHTDATA_PARSER_VERSION = 'brightdata-jumia-candidate/1.0.0'
OXR_COLLECTOR_VERSION = 'open-exchange-rates/latest/1.0.0'
OXR_PARSER_VERSION = 'open-exchange-rates/1.0.0'


def _iso_provider_datetime(value: str) -> str:
    """Normalise a provider timestamp; reject absent/ambiguous observation time."""
    if not value:
        raise ProviderError('invalid_response', 'The provider response had no observation timestamp.')
    try:
        parsed = datetime.fromisoformat(value.replace(' UTC', '+00:00').replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S %z')
        except ValueError as problem:
            raise ProviderError('invalid_response', 'The provider returned an unreadable observation timestamp.') from problem
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class JsonClient:
    """Small JSON transport with bounded retries for transient provider failures."""

    def __init__(self, timeout_seconds=15.0, opener=urlopen, sleeper=time.sleep, attempts=3):
        self.timeout_seconds = timeout_seconds
        self._open = opener
        self._sleep = sleeper
        self.attempts = attempts

    def _json(self, request: Request) -> tuple[object, dict, int]:
        for attempt in range(self.attempts):
            try:
                with self._open(request, timeout=self.timeout_seconds) as response:
                    status = getattr(response, 'status', None)
                    if status is None and hasattr(response, 'getcode'):
                        status = response.getcode()
                    return (json.loads(response.read().decode('utf-8')),
                            dict(response.headers), int(status or 200))
            except HTTPError as problem:
                retry = problem.code == 429 or 500 <= problem.code < 600
                if retry and attempt + 1 < self.attempts:
                    self._sleep(min(2 ** attempt, 4))
                    continue
                if problem.code in {401, 403}:
                    raise ProviderError('authorization', 'The provider rejected the server-side authorization.',
                                        'Review the provider account, credential, and permitted product')
                if problem.code == 429:
                    raise ProviderError('rate_limited', 'The provider rate-limited this collection attempt.',
                                        'Retry after the provider limit resets')
                raise ProviderError('provider_error', f'The provider returned HTTP {problem.code}.')
            except (URLError, TimeoutError, OSError):
                if attempt + 1 < self.attempts:
                    self._sleep(min(2 ** attempt, 4))
                    continue
                raise ProviderError('network', 'The provider could not be reached after three attempts.',
                                    'Retry when provider connectivity recovers')
            except (UnicodeError, json.JSONDecodeError):
                raise ProviderError('invalid_response', 'The provider returned a response the configured parser could not read.')
        raise ProviderError('network', 'The provider could not be reached.')


@dataclass(frozen=True)
class DataForSEOConfig:
    login: str
    password: str
    catalog_location_code: int = 2840
    trends_location_code: int = 2566
    timeout_seconds: float = 15.0


class DataForSEOClient(JsonClient):
    endpoint = 'https://api.dataforseo.com/v3'

    def __init__(self, config: DataForSEOConfig, **transport):
        super().__init__(timeout_seconds=config.timeout_seconds, **transport)
        self.config = config
        token = b64encode(f'{config.login}:{config.password}'.encode()).decode()
        self._headers = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}

    def _post(self, path: str, task: dict) -> dict:
        request = Request(f'{self.endpoint}/{path}', data=json.dumps([task]).encode(),
                          headers=self._headers, method='POST')
        payload, _, _ = self._json(request)
        if not isinstance(payload, dict) or payload.get('status_code') != 20000:
            raise ProviderError('invalid_response', 'DataForSEO did not return a successful task envelope.')
        tasks = payload.get('tasks') or []
        current = tasks[0] if tasks else {}
        if current.get('status_code') != 20000:
            message = current.get('status_message') or 'DataForSEO did not complete the requested task.'
            raise ProviderError('provider_error', message[:300])
        return current

    def get_catalog_item(self, asin: str) -> dict:
        task = self._post('merchant/amazon/asin/live/advanced', {
            'asin': asin, 'location_code': self.config.catalog_location_code,
            'language_code': 'en_US',
        })
        result = (task.get('result') or [{}])[0]
        items = result.get('items') or []
        item = next((candidate for candidate in items
                     if str(candidate.get('data_asin') or candidate.get('asin') or '').upper()
                     == asin.upper()), None)
        if not item:
            raise ProviderError('not_found', 'DataForSEO returned no Amazon item for this ASIN.',
                                'Check the ASIN and configured Amazon location')
        price = item.get('price') or {}
        category = item.get('category')
        if not category and item.get('categories'):
            last = item['categories'][-1]
            category = ((last.get('category') or last.get('name'))
                        if isinstance(last, dict) else str(last))
        mapped = {
            'asin': item.get('data_asin') or item.get('asin'),
            'title': item.get('title'), 'brand': item.get('brand'),
            'author': item.get('author'),
            'category': category,
            'detail_page_url': result.get('check_url') or item.get('url'),
            'image_url': item.get('image_url'),
            'offer_amount': (item.get('price_from') if item.get('price_from') is not None
                             else price.get('current') if isinstance(price, dict) else None),
            'offer_currency': (item.get('currency') or
                               (price.get('currency') if isinstance(price, dict) else None)),
            'rating': ((item.get('rating') or {}).get('value')
                       if isinstance(item.get('rating'), dict) else item.get('rating')),
            'rating_votes': ((item.get('rating') or {}).get('votes_count')
                             if isinstance(item.get('rating'), dict) else None),
            'observed_at': _iso_provider_datetime(result.get('datetime')),
            'source_url': result.get('check_url') or item.get('url'),
            'request_id': task.get('id'), 'task_cost_usd': task.get('cost'),
            'provider_item': item,
        }
        return {key: value for key, value in mapped.items() if value is not None}

    def discover_products(self, keyword: str, limit: int = 10) -> dict:
        """Return current organic Amazon query results as candidates, not recommendations."""
        task = self._post('merchant/amazon/products/live/advanced', {
            'keyword': keyword, 'location_code': self.config.catalog_location_code,
            'language_code': 'en_US', 'depth': limit, 'sort_by': 'relevance',
        })
        result = (task.get('result') or [{}])[0]
        seen = set()
        candidates = []
        for item in result.get('items') or []:
            asin = item.get('data_asin') or item.get('asin')
            if item.get('type') != 'amazon_serp' or not asin or asin in seen:
                continue
            seen.add(asin)
            rating = item.get('rating') or {}
            candidate = {
                'asin': asin, 'title': item.get('title'), 'url': item.get('url'),
                'position': item.get('rank_group'), 'absolute_position': item.get('rank_absolute'),
                'price_from': item.get('price_from'), 'price_to': item.get('price_to'),
                'currency': item.get('currency'),
                'rating': rating.get('value') if isinstance(rating, dict) else None,
                'rating_votes': rating.get('votes_count') if isinstance(rating, dict) else None,
                'bought_past_month_indicator': item.get('bought_past_month'),
                'is_amazon_choice': item.get('is_amazon_choice'),
                'is_best_seller': item.get('is_best_seller'),
                'result_type': 'organic',
            }
            if candidate['title'] and candidate['url']:
                candidates.append({key: value for key, value in candidate.items()
                                   if value is not None})
            if len(candidates) >= limit:
                break
        if not candidates:
            raise ProviderError('not_found',
                                'DataForSEO returned no organic Amazon product candidates for this query.')
        return {
            'query': keyword, 'candidates': candidates,
            'observed_at': _iso_provider_datetime(result.get('datetime')),
            'source_url': result.get('check_url'), 'request_id': task.get('id'),
            'task_cost_usd': task.get('cost'),
            'provider_item': {'query': keyword, 'check_url': result.get('check_url'),
                              'items': candidates},
        }

    def get_search_interest(self, keyword: str) -> dict:
        task = self._post('keywords_data/dataforseo_trends/explore/live', {
            'keywords': [keyword], 'location_code': self.config.trends_location_code,
            'time_range': 'past_90_days', 'type': 'web',
        })
        result = (task.get('result') or [{}])[0]
        graph = next((item for item in (result.get('items') or [])
                      if item.get('type') == 'dataforseo_trends_graph'), None)
        if not graph:
            raise ProviderError('not_found', 'DataForSEO Trends returned no search-interest series for this query.')
        series = []
        for point in graph.get('data') or []:
            values = point.get('values') or []
            series.append({'date': point.get('date_to') or point.get('date_from'),
                           'value': values[0] if values else None})
        observed_values = [point['value'] for point in series
                           if isinstance(point.get('value'), (int, float))]
        if not series or not observed_values:
            raise ProviderError('not_found', 'DataForSEO Trends returned an empty search-interest series for this query.')
        observed_at = _iso_provider_datetime(result.get('datetime'))
        return {'query': keyword, 'series': series, 'latest_value': observed_values[-1],
                'observed_at': observed_at, 'source_url': result.get('check_url') or
                'https://dataforseo.com/apis/dataforseo-trends-api',
                'request_id': task.get('id'), 'task_cost_usd': task.get('cost'),
                'provider_item': graph}


@dataclass(frozen=True)
class BrightDataConfig:
    api_token: str
    dataset_id: str
    timeout_seconds: float = 65.0
    poll_attempts: int = 6
    poll_interval_seconds: float = 10.0


def _tokens(value: str) -> set[str]:
    return {part for part in ''.join(character.lower() if character.isalnum() else ' '
                                     for character in (value or '')).split() if len(part) > 1}


def match_jumia_candidates(title: str, brand: str | None, candidates: list[dict]) -> list[dict]:
    """Rank candidates lexically and label them candidates, never identity matches."""
    expected = _tokens(title) | _tokens(brand or '')
    ranked = []
    for candidate in candidates:
        actual = _tokens(' '.join(str(candidate.get(key) or '') for key in ('title', 'brand')))
        overlap = len(expected & actual) / max(len(expected), 1)
        ranked.append({**candidate, 'match_score': round(overlap, 3),
                       'match_status': 'candidate',
                       'match_method': 'normalised title/brand token overlap; human review required'})
    return sorted(ranked, key=lambda value: value['match_score'], reverse=True)


class BrightDataJumiaClient(JsonClient):
    endpoint = 'https://api.brightdata.com/datasets/v3/scrape'
    management_endpoint = 'https://api.brightdata.com/datasets/v3'

    def __init__(self, config: BrightDataConfig, **transport):
        super().__init__(timeout_seconds=config.timeout_seconds, **transport)
        self.config = config

    def search(self, keyword: str) -> dict:
        url = f'{self.endpoint}?{urlencode({"dataset_id": self.config.dataset_id, "format": "json"})}'
        # The configured custom scraper must publish this exact input contract.  Keeping
        # it stable makes an incompatible Studio edit fail visibly instead of changing
        # the meaning of a collection silently.
        inputs = [{'url': f'https://www.jumia.com.ng/catalog/?q={quote(keyword)}',
                   'keyword': keyword, 'country': 'NG'}]
        request = Request(url, data=json.dumps({'input': inputs}).encode(), method='POST', headers={
            'Authorization': f'Bearer {self.config.api_token}', 'Content-Type': 'application/json'})
        payload, headers, status = self._json(request)
        snapshot_id = payload.get('snapshot_id') if isinstance(payload, dict) else None
        if status == 202:
            if not snapshot_id:
                raise ProviderError('invalid_response',
                                    'Bright Data accepted a delayed collection but returned no snapshot ID.')
            payload = self._retrieve_snapshot(snapshot_id)
        rows = payload if isinstance(payload, list) else (payload.get('results') or [])
        if not isinstance(rows, list):
            raise ProviderError('invalid_response', 'The configured Jumia scraper returned an unsupported result shape.')
        candidates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            candidate = {
                'title': row.get('title') or row.get('name'), 'brand': row.get('brand'),
                'price': row.get('price') or row.get('current_price'),
                'currency': row.get('currency') or 'NGN',
                'rating': row.get('rating'), 'rating_count': row.get('rating_count') or row.get('reviews_count'),
                'availability': row.get('availability') or row.get('in_stock'),
                'seller': row.get('seller') or row.get('seller_name'),
                'url': row.get('url') or row.get('product_url'), 'sku': row.get('sku'),
            }
            if candidate['title'] and candidate['url']:
                candidates.append({key: value for key, value in candidate.items() if value is not None})
        observed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return {'query': keyword, 'candidates': candidates, 'observed_at': observed_at,
                'source_url': inputs[0]['url'],
                'request_id': snapshot_id or headers.get('x-request-id') or headers.get('X-Request-Id'),
                'provider_item': rows}

    def _retrieve_snapshot(self, snapshot_id: str) -> object:
        """Bounded polling for the documented synchronous-timeout fallback."""
        authorization = {'Authorization': f'Bearer {self.config.api_token}'}
        for attempt in range(self.config.poll_attempts):
            progress, _, _ = self._json(Request(
                f'{self.management_endpoint}/progress/{quote(snapshot_id, safe="")}',
                headers=authorization))
            state = progress.get('status') if isinstance(progress, dict) else None
            if state == 'ready':
                result, _, download_status = self._json(Request(
                    f'{self.management_endpoint}/snapshot/{quote(snapshot_id, safe="")}?format=json',
                    headers=authorization))
                if download_status == 202:
                    state = 'running'
                else:
                    return result
            if state in {'failed', 'canceled'}:
                raise ProviderError('provider_error',
                                    f'Bright Data snapshot {state}; no local-market observation was recorded.',
                                    'Review the custom scraper run before retrying')
            if attempt + 1 < self.config.poll_attempts:
                self._sleep(self.config.poll_interval_seconds)
        raise ProviderError('collection_pending',
                            'Bright Data did not finish the snapshot within the bounded collection window.',
                            f'Retrieve snapshot {snapshot_id} in Bright Data, then retry after it completes')


@dataclass(frozen=True)
class OpenExchangeRatesConfig:
    app_id: str
    timeout_seconds: float = 12.0


class OpenExchangeRatesClient(JsonClient):
    endpoint = 'https://openexchangerates.org/api/latest.json'

    def __init__(self, config: OpenExchangeRatesConfig, **transport):
        super().__init__(timeout_seconds=config.timeout_seconds, **transport)
        self.config = config

    def latest(self) -> dict:
        # OXR's documented authentication is the app_id query parameter.  The complete
        # URL is never logged or persisted; snapshots contain only timestamps/rates.
        request = Request(f'{self.endpoint}?{urlencode({"app_id": self.config.app_id, "symbols": "NGN,CNY"})}')
        payload, headers, _ = self._json(request)
        if not isinstance(payload, dict) or payload.get('base') != 'USD':
            raise ProviderError('invalid_response', 'Open Exchange Rates did not return the required USD-base response.')
        rates = payload.get('rates') or {}
        if not isinstance(payload.get('timestamp'), (int, float)):
            raise ProviderError('invalid_response', 'Open Exchange Rates omitted its UTC observation timestamp.')
        if not all(isinstance(rates.get(code), (int, float)) for code in ('NGN', 'CNY')):
            raise ProviderError('invalid_response', 'Open Exchange Rates omitted NGN or CNY from the response.')
        observed = datetime.fromtimestamp(payload.get('timestamp'), timezone.utc).isoformat().replace('+00:00', 'Z')
        return {'base': 'USD', 'usd_ngn': rates['NGN'], 'usd_cny': rates['CNY'],
                'observed_at': observed, 'source_url': 'https://openexchangerates.org/',
                'request_id': headers.get('x-request-id') or headers.get('X-Request-Id'),
                'provider_item': {'timestamp': payload['timestamp'], 'base': 'USD',
                                  'rates': {'NGN': rates['NGN'], 'CNY': rates['CNY']}}}
