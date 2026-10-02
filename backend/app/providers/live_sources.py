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
import math
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from .common import ProviderError


DATAFORSEO_COLLECTOR_VERSION = 'dataforseo-live/1.1.0'
DATAFORSEO_PARSER_VERSION = 'dataforseo-catalog-trends/1.1.0'
BRIGHTDATA_COLLECTOR_VERSION = 'brightdata-jumia-custom/1.1.0'
BRIGHTDATA_PARSER_VERSION = 'brightdata-jumia-candidate/1.1.0'
OXR_COLLECTOR_VERSION = 'open-exchange-rates/latest/1.1.0'
OXR_PARSER_VERSION = 'open-exchange-rates/1.1.0'
MAX_PROVIDER_RESPONSE_BYTES = 10 * 1024 * 1024


def _provider_url(value: object, host_suffix: str, label: str) -> str:
    """Accept only HTTPS links on the provider contract's expected public host.

    Provider fields are external input even when the provider itself is trusted.  These
    URLs are later rendered as clickable evidence links, so an unexpected scheme or host
    must fail the collection instead of becoming an authenticated-workspace link.
    """
    if not isinstance(value, str) or not value.strip():
        raise ProviderError('invalid_response', f'The provider omitted the required {label}.')
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or '').lower().rstrip('.')
        port = parsed.port
    except ValueError as problem:
        raise ProviderError('invalid_response', f'The provider returned an invalid {label}.') from problem
    expected = host_suffix.lower().rstrip('.')
    if (parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None
            or port not in {None, 443}
            or not (host == expected or host.endswith(f'.{expected}'))):
        raise ProviderError('invalid_response', f'The provider returned an unexpected {label}.')
    return candidate


def _first_present(row: dict, *keys: str):
    """Return the first non-null field without erasing valid zero/false observations."""
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


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
                    body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
                    if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
                        raise ProviderError(
                            'invalid_response',
                            'The provider response exceeded the configured safety limit.')
                    return (json.loads(body.decode('utf-8')),
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
        # DataForSEO documents that most provider failures arrive as internal status
        # codes inside an HTTP 200 response.  Classify and retry those codes here; the
        # transport retry in JsonClient alone cannot see them.
        transient = {40101, 40103, 50000, 50001, 50301, 50302, 50303, 50304, 50401, 50402}
        retryable = transient | {40202, 40209}
        for attempt in range(self.attempts):
            request = Request(f'{self.endpoint}/{path}', data=json.dumps([task]).encode(),
                              headers=self._headers, method='POST')
            payload, _, _ = self._json(request)
            if not isinstance(payload, dict):
                raise ProviderError('invalid_response', 'DataForSEO returned an unreadable task envelope.')
            envelope_code = payload.get('status_code')
            tasks = payload.get('tasks') or []
            current = tasks[0] if tasks and isinstance(tasks[0], dict) else {}
            code = current.get('status_code') if envelope_code == 20000 else envelope_code
            if code == 20000:
                return current
            if code in retryable and attempt + 1 < self.attempts:
                self._sleep(min(2 ** attempt, 4))
                continue
            if code in {40100, 40104, 40201, 40204, 40207}:
                raise ProviderError(
                    'authorization',
                    f'DataForSEO rejected the configured account or access policy (status {code}).',
                    'Review account verification, credentials, plan access, and IP allowlisting')
            if code in {40202, 40205, 40206, 40209}:
                raise ProviderError(
                    'rate_limited', f'DataForSEO rate-limited the task (status {code}).',
                    'Retry after the provider limit resets')
            if code in {40200, 40203, 40210}:
                raise ProviderError(
                    'quota_exceeded', f'DataForSEO refused the task under its balance or cost cap (status {code}).',
                    'Review the approved provider balance and cost limit before retrying')
            if code == 40102:
                raise ProviderError('not_found', 'DataForSEO returned no results for this task.')
            if code == 40505:
                raise ProviderError(
                    'configuration',
                    'DataForSEO rejected an outdated configured location or language code.',
                    'Re-verify the configured codes with the authenticated locations endpoint')
            if code in transient:
                raise ProviderError(
                    'provider_error', f'DataForSEO could not complete the task after three attempts (status {code}).',
                    'Retry after the provider service recovers')
            raise ProviderError(
                'provider_error', f'DataForSEO rejected the task (status {code or "unknown"}).')
        raise ProviderError('provider_error', 'DataForSEO could not complete the task.')

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
        source_url = _provider_url(
            result.get('check_url') or item.get('url'), 'amazon.com', 'Amazon source URL')
        mapped = {
            'asin': item.get('data_asin') or item.get('asin'),
            'title': item.get('title'), 'brand': item.get('brand'),
            'author': item.get('author'),
            'category': category,
            'detail_page_url': source_url,
            'offer_amount': (item.get('price_from') if item.get('price_from') is not None
                             else price.get('current') if isinstance(price, dict) else None),
            'offer_currency': (item.get('currency') or
                               (price.get('currency') if isinstance(price, dict) else None)),
            'rating': ((item.get('rating') or {}).get('value')
                       if isinstance(item.get('rating'), dict) else item.get('rating')),
            'rating_votes': ((item.get('rating') or {}).get('votes_count')
                             if isinstance(item.get('rating'), dict) else None),
            'observed_at': _iso_provider_datetime(result.get('datetime')),
            'source_url': source_url,
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
            if not item.get('title') or not item.get('url'):
                continue
            item_url = _provider_url(item['url'], 'amazon.com', 'Amazon candidate URL')
            seen.add(asin)
            rating = item.get('rating') or {}
            candidate = {
                'asin': asin, 'title': item.get('title'), 'url': item_url,
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
            candidates.append({key: value for key, value in candidate.items()
                               if value is not None})
            if len(candidates) >= limit:
                break
        if not candidates:
            raise ProviderError('not_found',
                                'DataForSEO returned no organic Amazon product candidates for this query.')
        source_url = _provider_url(
            result.get('check_url'), 'amazon.com', 'Amazon search source URL')
        return {
            'query': keyword, 'candidates': candidates,
            'observed_at': _iso_provider_datetime(result.get('datetime')),
            'source_url': source_url, 'request_id': task.get('id'),
            'task_cost_usd': task.get('cost'),
            'provider_item': {'query': keyword, 'check_url': source_url,
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
            if not isinstance(point, dict):
                raise ProviderError('invalid_response',
                                    'DataForSEO Trends returned an unreadable series point.')
            values = point.get('values') or []
            date = point.get('date_to') or point.get('date_from')
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except (TypeError, ValueError) as problem:
                raise ProviderError(
                    'invalid_response',
                    'DataForSEO Trends returned a point with an unreadable date.') from problem
            value = values[0] if isinstance(values, list) and values else None
            if value is not None and (isinstance(value, bool)
                                      or not isinstance(value, (int, float))
                                      or not math.isfinite(value)
                                      or not 0 <= value <= 100):
                raise ProviderError(
                    'invalid_response',
                    'DataForSEO Trends returned a popularity value outside its documented scale.')
            # DataForSEO documents 0 as "not enough data", not observed zero
            # popularity. Store a gap so it cannot lower a trend or count as coverage.
            series.append({'date': date, 'value': None if value == 0 else value})
        observed_values = [point['value'] for point in series
                           if point.get('value') is not None]
        if not series or not observed_values:
            raise ProviderError('not_found', 'DataForSEO Trends returned an empty search-interest series for this query.')
        observed_at = _iso_provider_datetime(result.get('datetime'))
        return {'query': keyword, 'series': series, 'latest_value': observed_values[-1],
                # This endpoint does not document a result check_url. Keep the clickable
                # reference on our reviewed constant instead of trusting an undocumented
                # provider field that could become an arbitrary authenticated-workspace link.
                'observed_at': observed_at,
                'source_url': 'https://dataforseo.com/apis/dataforseo-trends-api',
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
            title = _first_present(row, 'title', 'name')
            candidate_url = _first_present(row, 'url', 'product_url')
            if not title or not candidate_url:
                continue
            candidate = {
                'title': title, 'brand': row.get('brand'),
                'price': _first_present(row, 'price', 'current_price'),
                'currency': row.get('currency') or 'NGN',
                'rating': row.get('rating'),
                'rating_count': _first_present(row, 'rating_count', 'reviews_count'),
                'availability': _first_present(row, 'availability', 'in_stock'),
                'seller': _first_present(row, 'seller', 'seller_name'),
                'url': _provider_url(candidate_url, 'jumia.com.ng', 'Jumia candidate URL'),
                'sku': row.get('sku'),
            }
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
        timestamp = payload.get('timestamp')
        if (not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool)
                or not math.isfinite(timestamp) or timestamp <= 0):
            raise ProviderError('invalid_response', 'Open Exchange Rates omitted its UTC observation timestamp.')
        if not all(isinstance(rates.get(code), (int, float))
                   and not isinstance(rates.get(code), bool)
                   and math.isfinite(rates[code]) and rates[code] > 0
                   for code in ('NGN', 'CNY')):
            raise ProviderError('invalid_response', 'Open Exchange Rates omitted NGN or CNY from the response.')
        try:
            observed = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z')
        except (OverflowError, OSError, ValueError) as problem:
            raise ProviderError(
                'invalid_response',
                'Open Exchange Rates returned an invalid UTC observation timestamp.') from problem
        return {'base': 'USD', 'usd_ngn': rates['NGN'], 'usd_cny': rates['CNY'],
                'observed_at': observed, 'source_url': 'https://openexchangerates.org/',
                'request_id': headers.get('x-request-id') or headers.get('X-Request-Id'),
                'provider_item': {'timestamp': payload['timestamp'], 'base': 'USD',
                                  'rates': {'NGN': rates['NGN'], 'CNY': rates['CNY']}}}
