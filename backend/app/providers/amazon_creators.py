"""Small synchronous adapter for Amazon's Creators API GetItems operation.

The adapter deliberately does not infer sales, review velocity, seller counts, revenue,
advertising spend, or attribution. A current sales rank is a point-in-time marketplace
observation; it becomes a change only after another dated observation exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


COLLECTOR_VERSION = 'amazon-creators/get-items/1.0.0'
PARSER_VERSION = 'amazon-creators-item/1.0.0'
TOKEN_ENDPOINTS = {
    '3.1': 'https://api.amazon.com/auth/o2/token',
    '3.2': 'https://api.amazon.co.uk/auth/o2/token',
    '3.3': 'https://api.amazon.co.jp/auth/o2/token',
}
API_ENDPOINT = 'https://creatorsapi.amazon/catalog/v1/getItems'
RESOURCES = [
    'itemInfo.title',
    'itemInfo.byLineInfo',
    'itemInfo.classifications',
    'itemInfo.externalIds',
    'itemInfo.manufactureInfo',
    'itemInfo.productInfo',
    'images.primary.medium',
    'offersV2.listings.price',
    'offersV2.listings.merchantInfo',
    'offersV2.listings.condition',
    'browseNodeInfo.websiteSalesRank',
    'browseNodeInfo.browseNodes.salesRank',
]


class ProviderError(RuntimeError):
    """A safe error classification suitable for UI/job history."""

    def __init__(self, code: str, detail: str, retry_after: str = 'Manual retry'):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after


@dataclass(frozen=True)
class AmazonCreatorsConfig:
    credential_id: str
    credential_secret: str
    credential_version: str
    partner_tag: str
    marketplace: str
    usage_rights: str
    timeout_seconds: float = 12.0


def _display(container, key):
    value = (container or {}).get(key)
    return value.get('displayValue') if isinstance(value, dict) else None


def parse_item(response: dict, asin: str) -> dict:
    """Map one response without manufacturing absent fields."""
    errors = response.get('errors') or []
    # Amazon's current first-party pages disagree on the container spelling: the cURL
    # guide and resource examples use `itemsResult`, while the GetItems operation
    # reference says `itemResults`. Accept both without accepting arbitrary shapes.
    result = response.get('itemsResult')
    if result is None:
        result = response.get('itemResults')
    items = (result or {}).get('items') or []
    item = next((candidate for candidate in items if candidate.get('asin') == asin), None)
    if item is None:
        detail = errors[0].get('message') if errors and isinstance(errors[0], dict) else None
        raise ProviderError('not_found', detail or 'Amazon returned no item for this ASIN.', 'Check the ASIN or marketplace')

    info = item.get('itemInfo') or {}
    byline = info.get('byLineInfo') or {}
    classifications = info.get('classifications') or {}
    primary = ((item.get('images') or {}).get('primary') or {}).get('medium') or {}
    rank = (item.get('browseNodeInfo') or {}).get('websiteSalesRank') or {}
    listings = (item.get('offersV2') or {}).get('listings') or []
    listing = listings[0] if listings else {}
    money = ((listing.get('price') or {}).get('money') or {})

    mapped = {'asin': item.get('asin')}
    supplied = {
        'title': _display(info, 'title'),
        'brand': _display(byline, 'brand'),
        'manufacturer': _display(byline, 'manufacturer'),
        'category': _display(classifications, 'productGroup'),
        'detail_page_url': item.get('detailPageURL'),
        'image_url': primary.get('url'),
        'website_sales_rank': rank.get('salesRank'),
        'rank_category': rank.get('contextFreeName') or rank.get('displayName'),
        'offer_amount': money.get('amount'),
        'offer_currency': money.get('currency'),
        'merchant': ((listing.get('merchantInfo') or {}).get('name')),
        'condition': ((listing.get('condition') or {}).get('value')),
    }
    mapped.update({key: value for key, value in supplied.items() if value is not None})
    # This is the provider item itself, not headers or credentials. It supports audit and
    # parser replay subject to the explicitly configured usage-rights/retention policy.
    mapped['provider_item'] = item
    return mapped


class AmazonCreatorsClient:
    def __init__(self, config: AmazonCreatorsConfig, opener=urlopen, clock=time.time):
        self.config = config
        self._open = opener
        self._clock = clock
        self._token = ''
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    def _json(self, request: Request) -> tuple[dict, dict]:
        try:
            with self._open(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode('utf-8')), dict(response.headers)
        except HTTPError as problem:
            retry = problem.headers.get('Retry-After') if problem.headers else None
            if problem.code == 429:
                raise ProviderError('rate_limited', 'Amazon rate-limited this collection attempt.',
                                    f'Retry after {retry} seconds' if retry else 'Retry after the provider limit resets')
            if problem.code in {401, 403}:
                raise ProviderError('authorization', 'Amazon rejected the configured Creators API authorization.',
                                    'Review the server-side credential, partner tag, marketplace, and account access')
            if problem.code == 404:
                raise ProviderError('not_found', 'Amazon returned no item for this ASIN.', 'Check the ASIN or marketplace')
            raise ProviderError('provider_error', f'Amazon collection failed with HTTP {problem.code}.')
        except (URLError, TimeoutError, OSError):
            raise ProviderError('network', 'Amazon could not be reached for this collection attempt.', 'Retry when provider connectivity recovers')
        except (UnicodeError, json.JSONDecodeError):
            raise ProviderError('invalid_response', 'Amazon returned a response the configured parser could not read.', 'Retry, then review the adapter if it repeats')

    def _access_token(self) -> str:
        with self._token_lock:
            if self._token and self._clock() < self._token_expires_at - 60:
                return self._token
            body = json.dumps({
                'grant_type': 'client_credentials',
                'client_id': self.config.credential_id,
                'client_secret': self.config.credential_secret,
                'scope': 'creatorsapi::default',
            }).encode()
            request = Request(TOKEN_ENDPOINTS[self.config.credential_version], data=body,
                              headers={'Content-Type': 'application/json'}, method='POST')
            payload, _ = self._json(request)
            token = payload.get('access_token')
            if not token:
                raise ProviderError('authorization', 'Amazon did not return an access token.', 'Review the server-side credential')
            self._token = token
            self._token_expires_at = self._clock() + int(payload.get('expires_in') or 3600)
            return token

    def get_item(self, asin: str) -> dict:
        body = json.dumps({
            'itemIds': [asin], 'itemIdType': 'ASIN',
            'marketplace': self.config.marketplace,
            'partnerTag': self.config.partner_tag,
            'resources': RESOURCES,
        }).encode()
        request = Request(API_ENDPOINT, data=body, method='POST', headers={
            'Authorization': f'Bearer {self._access_token()}',
            'Content-Type': 'application/json',
            'x-marketplace': self.config.marketplace,
        })
        payload, headers = self._json(request)
        return {**parse_item(payload, asin),
                'request_id': headers.get('x-amzn-requestid') or headers.get('X-Amzn-RequestId')}
