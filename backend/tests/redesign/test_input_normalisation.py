"""Inputs are normalised before they are validated (action plan T08).

Review finding 12: confirming a name of two spaces returned 200 and stored an empty
name, because the length constraint ran before the trim. A quote with
`source_url: "https://"` was accepted, because validation only checked the prefix.
"""
import pytest

from conftest import HEADERS, PASSWORD

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
QUOTE = {'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/quote-4821',
         'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB'}


@pytest.fixture
def product(client, owner):
    return client.post('/api/v1/xray', json={'input': AMAZON},
                       headers={**HEADERS, 'Idempotency-Key': 'x'}).json()['product_id']


def test_a_whitespace_only_confirmed_name_is_refused(client, product):
    before = client.get(f'/api/v1/products/{product}').json()['name']
    for blank in ('  ', '\t\t', '\n', '   \t '):
        response = client.post(f'/api/v1/products/{product}/confirm', json={'name': blank}, headers=HEADERS)
        assert response.status_code == 422, blank
    after = client.get(f'/api/v1/products/{product}').json()
    assert after['name'] == before
    assert after['confirmed'] is False


def test_a_padded_name_is_stored_trimmed(client, product):
    body = client.post(f'/api/v1/products/{product}/confirm',
                       json={'name': '  Portable garment steamer \n'}, headers=HEADERS).json()
    assert body['name'] == 'Portable garment steamer'


def test_a_name_that_is_too_short_after_trimming_is_refused(client, product):
    assert client.post(f'/api/v1/products/{product}/confirm', json={'name': ' a '}, headers=HEADERS).status_code == 422


@pytest.mark.parametrize('bad', [
    'https://',            # the reviewed case: a scheme with nothing to open
    'https:// ',
    'https://localhost',   # no dot, not an addressable supplier reference
    'http://example.com/quote',
    'ftp://example.com/quote',
    'example.com/quote',
    'javascript:alert(1)',
    'https://exa mple.com/quote',
])
def test_an_unusable_supplier_reference_is_refused(client, product, bad):
    response = client.post('/api/v1/quotes', json={**QUOTE, 'product_id': product, 'source_url': bad}, headers=HEADERS)
    assert response.status_code == 422, bad
    assert client.get('/api/v1/quotes').json()['quotes'] == []


def test_a_real_supplier_reference_is_accepted_and_normalised(client, product):
    body = client.post('/api/v1/quotes',
                       json={**QUOTE, 'product_id': product, 'source_url': ' https://supplier.example.com/quote-4821 '},
                       headers=HEADERS).json()
    assert body['source_url'] == 'https://supplier.example.com/quote-4821'


def test_a_padded_supplier_name_is_trimmed_and_a_blank_one_refused(client, product):
    body = client.post('/api/v1/quotes', json={**QUOTE, 'product_id': product, 'supplier': '  Example Ltd  '},
                       headers=HEADERS).json()
    assert body['supplier'] == 'Example Ltd'
    assert client.post('/api/v1/quotes', json={**QUOTE, 'product_id': product, 'supplier': '   '},
                       headers=HEADERS).status_code == 422


def test_a_whitespace_only_workspace_name_is_refused_at_registration(client):
    blank = client.post('/api/v1/auth/register', json={'email': 'blank@example.com', 'password': PASSWORD, 'name': '  '},
                        headers=HEADERS)
    assert blank.status_code == 422


def test_an_email_is_stored_lowercased_and_trimmed(client):
    user = client.post('/api/v1/auth/register',
                       json={'email': '  Owner@Example.COM ', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).json()
    assert user['email'] == 'owner@example.com'
