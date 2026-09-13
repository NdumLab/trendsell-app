"""Search, paging and complete exports (action plan T05).

Review finding 3: the products endpoint read the newest 200 rows and filtered in Python.
In a workspace with more than 200 products the oldest one disappeared from the list,
from search, from the selectors and from the workspace export — while its direct API URL
still returned 200 and its decisions, quotes and watches remained.

`COUNT` here is deliberately above 200 so a regression to the old cutoff fails.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.db import Record
from app.main import EXPORT_KINDS, EXPORT_SCHEMA
from conftest import HEADERS

COUNT = 250
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


@pytest.fixture
def big_workspace(client, owner):
    """A workspace larger than the old cutoff, written straight to the store.

    Going through /xray would exhaust the research quota; the records are identical in
    shape to the ones the API creates.
    """
    workspace_id = owner['workspace_id']
    with client.app.state.database.session() as db:
        for index in range(COUNT):
            asin = f'B{index:09d}'
            db.add(Record(workspace_id=workspace_id, kind='product', key=asin,
                          created_at=f'2026-01-01T00:00:{index // 60:02d}.{index % 60:06d}+00:00',
                          payload={'name': f'Investigation {index:03d}', 'asin': asin,
                                   'source_url': f'https://www.amazon.com/dp/{asin}', 'market': 'NG',
                                   'discovery_market': 'US', 'confirmed': True, 'truth_state': 'User input',
                                   'decision': 'INSUFFICIENT EVIDENCE', 'confidence': 0,
                                   'category': 'Unclassified', 'stage': 'Needs evidence',
                                   'blocker': 'Confirm product identity and connect a demand source.',
                                   'observations': []}))
        db.commit()
    return {'oldest': 'B000000000', 'newest': f'B{COUNT - 1:09d}'}


def every_product(client, **params):
    """Walk the whole collection through the cursor, one page at a time."""
    seen, cursor, pages = [], None, 0
    while True:
        query = {**params, **({'cursor': cursor} if cursor else {})}
        body = client.get('/api/v1/products', params=query).json()
        seen.extend(body['products'])
        pages += 1
        cursor = body['next_cursor']
        if not cursor:
            return seen, body['total'], pages
        assert pages < 100, 'cursor did not terminate'


def test_the_oldest_product_is_still_reachable_by_paging(client, big_workspace):
    seen, total, pages = every_product(client)
    assert total == COUNT
    assert len(seen) == COUNT
    assert pages > 1
    assert {p['asin'] for p in seen} == {f'B{i:09d}' for i in range(COUNT)}


def test_paging_never_skips_or_repeats_a_record(client, big_workspace):
    seen, _, _ = every_product(client, limit=7)
    ids = [p['id'] for p in seen]
    assert len(ids) == len(set(ids)) == COUNT


def test_search_runs_before_the_page_is_cut(client, big_workspace):
    """The oldest product must be findable by name even though it is far past page one."""
    body = client.get('/api/v1/products', params={'search': 'Investigation 000'}).json()
    assert body['total'] == 1
    assert body['products'][0]['asin'] == big_workspace['oldest']
    assert body['next_cursor'] is None


def test_search_matches_the_identifier_and_ignores_case(client, big_workspace):
    by_asin = client.get('/api/v1/products', params={'search': big_workspace['oldest'].lower()}).json()
    assert [p['asin'] for p in by_asin['products']] == [big_workspace['oldest']]
    assert client.get('/api/v1/products', params={'search': 'INVESTIGATION 249'}).json()['total'] == 1


def test_a_search_with_no_match_reports_zero_rather_than_a_first_page(client, big_workspace):
    body = client.get('/api/v1/products', params={'search': 'no such product'}).json()
    assert body == {'products': [], 'total': 0, 'limit': 50, 'next_cursor': None}


def test_a_product_far_past_the_first_page_opens_by_id(client, big_workspace):
    listed = client.get('/api/v1/products', params={'search': 'Investigation 000'}).json()['products'][0]
    fetched = client.get(f'/api/v1/products/{listed["id"]}').json()
    assert fetched['asin'] == big_workspace['oldest']
    assert fetched['name'] == 'Investigation 000'


def test_an_invalid_page_size_or_cursor_is_refused(client, big_workspace):
    assert client.get('/api/v1/products', params={'limit': 0}).status_code == 422
    assert client.get('/api/v1/products', params={'limit': 201}).status_code == 422
    assert client.get('/api/v1/products', params={'cursor': 'not-a-cursor'}).status_code == 422


def test_the_export_contains_every_product_exactly_once(client, big_workspace):
    body = json.loads(client.get('/api/v1/export').text)
    assert body['counts']['products'] == COUNT
    asins = [p['asin'] for p in body['products']]
    assert len(asins) == len(set(asins)) == COUNT
    assert big_workspace['oldest'] in asins and big_workspace['newest'] in asins


def test_the_export_total_reconciles_with_the_list_total(client, big_workspace):
    listed = client.get('/api/v1/products', params={'limit': 1}).json()
    exported = json.loads(client.get('/api/v1/export').text)
    assert exported['counts']['products'] == listed['total']


def test_two_exports_of_unchanged_data_agree_record_for_record(client, big_workspace):
    first, second = json.loads(client.get('/api/v1/export').text), json.loads(client.get('/api/v1/export').text)
    assert first['products'] == second['products']
    assert first['exported_at'] <= second['exported_at']


def test_the_export_carries_every_record_kind_and_names_its_schema(client, owner):
    job = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ABCDEFGH'},
                      headers={**HEADERS, 'Idempotency-Key': 'e'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    client.post('/api/v1/decisions', json={'product_id': job['product_id'], 'inputs': INPUTS},
                headers={**HEADERS, 'Idempotency-Key': 'd'})
    client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': job['product_id'], 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://example.com/supplier', 'unit_price_usd': 8.4, 'moq': 300,
        'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB'})
    client.post('/api/v1/watchlists/default/items', json={'product_id': job['product_id']}, headers=HEADERS)
    body = json.loads(client.get('/api/v1/export').text)
    assert body['schema'] == EXPORT_SCHEMA
    # Every kind the export contract names is present, and the ones this test created
    # carry exactly one record. Derived from EXPORT_KINDS, so a kind added to the
    # application without being added to the export fails here rather than passing (R05).
    created = {'products', 'research_jobs', 'decisions', 'quotes', 'watches'}
    assert set(body['counts']) == {name for _, name in EXPORT_KINDS}
    for _, name in EXPORT_KINDS:
        assert name in body, name
        assert len(body[name]) == body['counts'][name], name
        assert len(body[name]) == (1 if name in created else 0), name
    assert body['decisions'][0]['product_id'] == job['product_id']


def test_the_export_is_scoped_to_the_signed_in_workspace(client, big_workspace, second_client, stranger):
    stranger_export = json.loads(second_client.get('/api/v1/export').text)
    assert stranger_export['counts'] == {name: 0 for _, name in EXPORT_KINDS}
    assert stranger_export['workspace_id'] != json.loads(client.get('/api/v1/export').text)['workspace_id']
    assert second_client.get('/api/v1/products').json()['total'] == 0


def test_the_export_requires_a_session(second_client):
    assert second_client.get('/api/v1/export').status_code == 401


def test_decisions_quotes_and_watches_paginate_and_report_a_total(client, owner):
    job = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ABCDEFGH'},
                      headers={**HEADERS, 'Idempotency-Key': 'e'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    for index in range(3):
        client.post('/api/v1/decisions',
                    json={'product_id': job['product_id'], 'inputs': {**INPUTS, 'quantity': 300 + index}},
                    headers={**HEADERS, 'Idempotency-Key': f'd{index}'})
    first = client.get('/api/v1/decisions', params={'limit': 2}).json()
    assert first['total'] == 3 and len(first['decisions']) == 2 and first['next_cursor']
    second = client.get('/api/v1/decisions', params={'limit': 2, 'cursor': first['next_cursor']}).json()
    assert len(second['decisions']) == 1 and second['next_cursor'] is None
    assert {d['id'] for d in first['decisions']} | {d['id'] for d in second['decisions']} == \
        {d['id'] for d in client.get('/api/v1/decisions', params={'limit': 50}).json()['decisions']}
    for path, key in [('/api/v1/quotes', 'quotes'), ('/api/v1/watchlists/default/items', 'items')]:
        body = client.get(path).json()
        assert body['total'] == 0 and body[key] == [] and body['next_cursor'] is None


def test_decisions_and_quotes_can_be_filtered_to_one_product(client, owner):
    first = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ABCDEFGH'},
                        headers={**HEADERS, 'Idempotency-Key': 'a'}).json()
    second = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ZZZZZZZZ'},
                         headers={**HEADERS, 'Idempotency-Key': 'b'}).json()
    for job in (first, second):
        client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Product'}, headers=HEADERS)
        client.post('/api/v1/decisions', json={'product_id': job['product_id'], 'inputs': INPUTS},
                    headers={**HEADERS, 'Idempotency-Key': f'dec-{job["product_id"]}'})
    body = client.get('/api/v1/decisions', params={'product_id': first['product_id']}).json()
    assert body['total'] == 1
    assert body['decisions'][0]['product_id'] == first['product_id']


def test_summary_counts_are_computed_in_the_database_not_from_a_page(client, big_workspace):
    """A screen must be able to state the workspace total without loading every page."""
    body = client.get('/api/v1/summary').json()
    assert body['products'] == COUNT
    assert body['products_awaiting_evidence'] == COUNT
    assert body == {'products': COUNT, 'products_awaiting_evidence': COUNT, 'decisions': 0,
                    'decisions_go': 0, 'quotes': 0, 'watches': 0}
    assert client.get('/api/v1/products', params={'limit': 1}).json()['total'] == body['products']


def test_summary_is_scoped_to_the_workspace_and_needs_a_session(client, big_workspace, second_client, stranger):
    assert second_client.get('/api/v1/summary').json()['products'] == 0
    assert client.get('/api/v1/summary').json()['products'] == COUNT
    signed_out = TestClient(client.app)
    assert signed_out.get('/api/v1/summary').status_code == 401


def test_summary_counts_saved_decisions_separately_from_product_evidence(client, owner):
    job = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ABCDEFGH'},
                      headers={**HEADERS, 'Idempotency-Key': 's'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    client.post('/api/v1/decisions', json={'product_id': job['product_id'], 'inputs': INPUTS},
                headers={**HEADERS, 'Idempotency-Key': 'd'})
    body = client.get('/api/v1/summary').json()
    assert body['products'] == 1 and body['decisions'] == 1
    assert body['decisions_go'] == 0


# --- R05: the export is the whole workspace, not the kinds that existed first --------
#
# Review finding R05: `evidence` and `compliance_review` were never added to EXPORT_KINDS,
# so a workspace holding four evidence records and two reviews exported neither — and the
# `compliance_review_id` on a saved decision referenced a record the export did not carry.

REVIEW_REQUEST = {
    'specifications': '1500 W handheld garment steamer, 260 ml tank, 220 V, 0.9 kg.',
    'intended_use': 'Retail sale to consumers in Lagos',
    'question': 'Which classification applies before import?',
    'hs_code_candidate': '8451.30',
    'destination': 'NG',
}


def evidence_body(**overrides):
    from datetime import datetime, timedelta, timezone
    return {'metric': 'Search interest', 'value': 68, 'unit': 'index / 100', 'market': 'US',
            'observed_at': (datetime.now(timezone.utc) - timedelta(days=5)).strftime('%Y-%m-%d'),
            'source_name': 'Google Trends export', 'source_url': 'https://trends.google.com/x',
            'method': 'Read the latest weekly point from the exported series.', 'notes': '',
            **overrides}


@pytest.fixture
def researched(client, owner, workspace_reviewer):
    """A product carrying evidence and a review history, as a real workspace would."""
    job = client.post('/api/v1/xray', json={'input': 'https://www.amazon.com/dp/B0ABCDEFGH'},
                      headers={**HEADERS, 'Idempotency-Key': 'r05'}).json()
    product_id = job['product_id']
    client.post(f'/api/v1/products/{product_id}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    for metric, market in [('Search interest', 'US'), ('Review velocity', 'US'),
                           ('Marketplace rank', 'US'), ('Local listing price', 'NG')]:
        assert client.post(f'/api/v1/products/{product_id}/evidence',
                           json=evidence_body(metric=metric, market=market,
                                              source_name=f'{metric} source'),
                           headers=HEADERS).status_code == 201
    # Two reviews, so the export has to carry the superseded one as well as the current.
    first = client.post(f'/api/v1/products/{product_id}/compliance/requests',
                        json={**REVIEW_REQUEST, 'product_id': product_id}, headers=HEADERS).json()
    workspace_reviewer.post(f'/api/v1/compliance/reviews/{first["id"]}/decision',
                            json={'status': 'more_information',
                                  'rationale': 'Send the full specification sheet.'},
                            headers=HEADERS)
    second = client.post(f'/api/v1/products/{product_id}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': product_id}, headers=HEADERS).json()
    return {'product_id': product_id, 'first_review': first['id'], 'second_review': second['id']}


def test_the_export_carries_evidence_and_review_records(client, researched):
    body = json.loads(client.get('/api/v1/export').text)
    assert body['counts']['evidence'] == 4
    assert body['counts']['compliance_reviews'] == 2
    assert len(body['evidence']) == 4 and len(body['compliance_reviews']) == 2


def test_exported_evidence_does_not_depend_on_having_been_assessed(client, researched):
    """The regression's sharpest edge: evidence never saved into an assessment was absent
    from the export entirely, because only decisions embedded a snapshot."""
    assert not json.loads(client.get('/api/v1/decisions').text)['decisions'], 'no assessment saved'
    exported = json.loads(client.get('/api/v1/export').text)['evidence']
    assert len(exported) == 4
    assert {record['metric'] for record in exported} == {
        'Search interest', 'Review velocity', 'Marketplace rank', 'Local listing price'}


def test_the_export_carries_superseded_reviews_and_their_sources(client, researched):
    reviews = json.loads(client.get('/api/v1/export').text)['compliance_reviews']
    by_id = {review['id']: review for review in reviews}
    assert by_id[researched['first_review']]['superseded_by'] == researched['second_review']
    assert by_id[researched['second_review']]['supersedes'] == researched['first_review']


def test_a_saved_decision_resolves_its_review_reference_inside_the_export(client, researched):
    """`compliance_review_id` has to name a record the export actually contains.

    It names the review that *governed* the gate, which is the last one a reviewer
    decided — not the later request still waiting for one (review finding E03). The
    fixture decided the first review and then asked again, so the first is the reference.
    """
    client.post('/api/v1/decisions',
                json={'product_id': researched['product_id'], 'inputs': INPUTS},
                headers={**HEADERS, 'Idempotency-Key': 'r05d'})
    body = json.loads(client.get('/api/v1/export').text)
    referenced = body['decisions'][0]['compliance_review_id']
    assert referenced == researched['first_review']
    assert referenced in {review['id'] for review in body['compliance_reviews']}


def test_the_export_reconciles_with_what_the_database_holds(client, researched):
    """Counts are not the export's own opinion: they must match the stored rows."""
    body = json.loads(client.get('/api/v1/export').text)
    with client.app.state.database.session() as db:
        for kind, name in EXPORT_KINDS:
            stored = db.query(Record).filter_by(workspace_id=body['workspace_id'], kind=kind).count()
            assert body['counts'][name] == stored == len(body[name]), name
        # And no record kind the workspace holds is missing from the export contract.
        kinds = {kind for (kind,) in db.query(Record.kind)
                 .filter_by(workspace_id=body['workspace_id']).distinct()}
    assert kinds <= {kind for kind, _ in EXPORT_KINDS}, 'a stored kind is not exported'


def test_a_foreign_workspace_exports_none_of_it(client, researched, second_client, stranger):
    body = json.loads(second_client.get('/api/v1/export').text)
    assert body['counts']['evidence'] == 0 and body['counts']['compliance_reviews'] == 0
    assert body['evidence'] == [] and body['compliance_reviews'] == []
