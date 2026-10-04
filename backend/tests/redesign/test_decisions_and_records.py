"""Saved decisions, supplier quotes and watches: reproducible, immutable, workspace-scoped."""
import pytest

from app.economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate
from app.main import COST_LINE_ITEMS
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'packaging_ngn': 0, 'insurance_ngn': 0, 'clearance_ngn': 0, 'local_delivery_ngn': 0,
          'payment_fee_pct': 0, 'reserve_ngn': 0, 'fx_buffer_pct': 0,
          'supplier_deposit_pct': 0, 'cash_tied_up_days': 0,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


@pytest.fixture
def product(client, owner):
    job = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'x'}).json()
    return job['product_id']


@pytest.fixture
def confirmed(client, product):
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Portable garment steamer'}, headers=HEADERS)
    return product


def save(client, product_id, key='decision-1', inputs=None):
    return client.post('/api/v1/decisions', json={'product_id': product_id, 'inputs': inputs or INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': key})


def test_a_decision_needs_a_confirmed_product(client, product):
    response = save(client, product)
    assert response.status_code == 409
    assert 'Confirm product identity' in response.json()['detail']


def test_a_saved_decision_keeps_its_inputs_and_versions(client, confirmed):
    saved = save(client, confirmed).json()
    assert saved['inputs'] == INPUTS
    assert saved['formula_version'] == FORMULA_VERSION
    assert saved['threshold_version'] == THRESHOLD_VERSION
    assert saved['cost_model_version'] == 'landed-cost/2.0.0'
    assert saved['input_truth_state'] == 'User input'
    assert saved['truth_state'] == 'Calculated'
    assert len(saved['cost_lineage']) == 19
    assert {line['truth_state'] for line in saved['cost_lineage']} == {'User input'}
    assert saved['landed_cost_method']['missing_cost_policy'].startswith('Every current cost input')
    assert saved['created_at'] and saved['id']


def test_a_new_decision_cannot_turn_omitted_costs_into_zero(client, confirmed):
    old_shape = {key: value for key, value in INPUTS.items()
                 if key not in {'packaging_ngn', 'insurance_ngn', 'clearance_ngn',
                                'local_delivery_ngn', 'payment_fee_pct', 'reserve_ngn',
                                'fx_buffer_pct', 'supplier_deposit_pct', 'cash_tied_up_days'}}
    response = save(client, confirmed, key='missing-costs', inputs=old_shape)
    assert response.status_code == 422
    detail = str(response.json()['detail'])
    assert 'requires explicit values' in detail
    assert 'insurance_ngn' in detail


def test_a_new_decision_cannot_invent_route_labels(client, confirmed):
    for field in ('channel', 'shipping'):
        response = save(
            client, confirmed, key=f'missing-{field}',
            inputs={key: value for key, value in INPUTS.items() if key != field})
        assert response.status_code == 422
        assert field in str(response.json()['detail'])


def test_every_formula_cost_input_has_a_lineage_definition():
    expected = set(Inputs.model_fields) - {'quantity', 'stress_pct', 'compliance', 'channel', 'shipping'}
    assert {key for key, _label, _unit in COST_LINE_ITEMS} == expected


def test_a_saved_decision_is_reproducible_from_its_stored_payload(client, confirmed):
    saved = client.get(f'/api/v1/decisions/{save(client, confirmed).json()["id"]}').json()
    replayed = calculate(Inputs(**saved['inputs']), formula_version=saved['formula_version'])
    for field in ('decision', 'scenarios', 'blockers', 'confidence', 'currency', 'market', 'formula_version'):
        assert replayed[field] == saved[field], field


def test_a_saved_decision_records_the_version_it_must_be_replayed_under(client, confirmed):
    """A stored assessment is replayed with its own formula version, never the current one."""
    saved = client.get(f'/api/v1/decisions/{save(client, confirmed).json()["id"]}').json()
    assert saved['formula_version'] in {'unit-economics/1.0.0', 'unit-economics/1.1.0', 'unit-economics/1.2.0'}
    under_legacy = calculate(Inputs(**saved['inputs']), formula_version='unit-economics/1.0.0')
    assert under_legacy['formula_version'] == 'unit-economics/1.0.0'
    assert under_legacy['formula_version'] != saved['formula_version']


def test_a_decision_without_observations_cannot_be_a_go(client, confirmed):
    saved = save(client, confirmed).json()
    assert saved['decision'] == 'INSUFFICIENT EVIDENCE'
    assert saved['confidence'] == 0
    assert saved['observation_ids'] == []
    assert saved['blockers']


def test_a_prohibited_status_is_refused_regardless_of_margin(client, confirmed):
    saved = save(client, confirmed, key='prohibited', inputs={**INPUTS, 'compliance': 'prohibited'}).json()
    assert saved['decision'] == 'NO-GO'


def test_saving_twice_with_one_key_returns_the_same_assessment(client, confirmed):
    first, second = save(client, confirmed).json(), save(client, confirmed).json()
    assert first['id'] == second['id']
    assert len(client.get('/api/v1/decisions').json()['decisions']) == 1
    changed_quote_assumption = client.post('/api/v1/decisions', json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_fx_to_usd': 1},
        headers={**HEADERS, 'Idempotency-Key': 'decision-1'})
    assert changed_quote_assumption.status_code == 409


def test_a_reused_key_with_different_inputs_is_refused(client, confirmed):
    save(client, confirmed)
    conflict = save(client, confirmed, inputs={**INPUTS, 'quantity': 500})
    assert conflict.status_code == 409


def test_changing_inputs_creates_a_new_assessment_and_keeps_the_old_one(client, confirmed):
    first = save(client, confirmed, key='one').json()
    second = save(client, confirmed, key='two', inputs={**INPUTS, 'selling_price_ngn': 40000}).json()
    assert first['id'] != second['id']
    assert client.get(f'/api/v1/decisions/{first["id"]}').json()['inputs'] == INPUTS
    assert len(client.get('/api/v1/decisions').json()['decisions']) == 2


def test_out_of_range_and_unknown_inputs_are_rejected(client, confirmed):
    for bad in [{'quantity': 0}, {'selling_price_ngn': 0}, {'duty_pct': 140}, {'stress_pct': 90},
                {'fx_ngn': -1}, {'compliance': 'resolved'}, {'shipping': 'Rail'}, {'unexpected': 1}]:
        response = save(client, confirmed, key=f'bad-{list(bad)[0]}', inputs={**INPUTS, **bad})
        assert response.status_code == 422, bad


def test_an_idempotency_key_is_required_for_a_decision(client, confirmed):
    assert client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS}, headers=HEADERS).status_code == 422


def test_a_quote_is_stored_as_unverified_user_input(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/supplier',
        'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB', 'notes': 'Valid 30 days'}).json()
    assert quote['truth_state'] == 'User input'
    assert quote['verification'] == 'Unverified'
    assert quote['input_author']
    assert quote['unit_price'] == 8.4
    assert quote['currency'] == 'USD'
    assert quote['recorded_at']
    assert 'included_costs' not in quote


def test_missing_quote_facts_remain_unknown_instead_of_becoming_defaults(client, confirmed):
    missing_incoterm = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Legacy Client Ltd',
        'source_url': 'https://example.com/legacy-client', 'unit_price_usd': 8.4,
        'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01'}).json()
    assert 'incoterm' not in missing_incoterm
    assert 'included_costs' not in missing_incoterm

    implicit_currency = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Ambiguous Currency Ltd',
        'source_url': 'https://example.com/ambiguous-currency', 'unit_price': 8.4,
        'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01'})
    assert implicit_currency.status_code == 422
    assert 'Currency must be explicit' in str(implicit_currency.json()['detail'])


def test_a_quote_records_explicit_commercial_scope_and_immutable_revisions(client, confirmed):
    first = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://example.com/supplier/v1', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 300, 'lead_days': 25,
        'quote_date': '2026-09-01', 'valid_until': '2026-10-01',
        'incoterm': 'FOB', 'product_specifications': '1500 W, 220 V, 260 ml tank',
        'payment_terms': '30% deposit; 70% before shipment',
        'delivery_scope': 'factory_only'}).json()
    assert first['revision'] == 1
    assert first['valid_until'] == '2026-10-01'
    assert first['product_specifications'] == '1500 W, 220 V, 260 ml tank'
    assert first['payment_terms'] == '30% deposit; 70% before shipment'
    assert first['delivery_scope'] == 'factory_only'

    second_payload = {
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://example.com/supplier/v2', 'unit_price': 8.1,
        'currency': 'USD', 'moq': 500, 'lead_days': 22,
        'quote_date': '2026-09-15', 'valid_until': '2026-10-15',
        'incoterm': 'CIF', 'product_specifications': '1500 W, 220 V, 260 ml tank',
        'payment_terms': '20% deposit; 80% before shipment',
        'delivery_scope': 'international_freight', 'included_costs': ['international_freight'],
        'supersedes_quote_id': first['id']}
    second = client.post('/api/v1/quotes', headers=HEADERS, json=second_payload).json()
    assert second['revision'] == 2
    assert second['root_quote_id'] == first['id']
    assert second['supersedes_quote_id'] == first['id']
    assert client.get(f'/api/v1/quotes?product_id={confirmed}').json()['total'] == 2
    assert client.post('/api/v1/quotes', headers=HEADERS,
                       json={**second_payload, 'source_url': 'https://example.com/supplier/v3'}).status_code == 409


def test_a_quote_revision_cannot_change_supplier_identity(client, confirmed):
    first = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://example.com/supplier/v1', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 300, 'lead_days': 25,
        'quote_date': '2026-09-01'}).json()
    changed = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Different Supplier Ltd',
        'source_url': 'https://example.com/supplier/v2', 'unit_price': 8.1,
        'currency': 'USD', 'moq': 300, 'lead_days': 25,
        'quote_date': '2026-09-15', 'supersedes_quote_id': first['id']})
    assert changed.status_code == 422
    assert 'same supplier identity' in changed.json()['detail']


def test_quote_validity_cannot_end_before_the_quote_date(client, confirmed):
    response = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://example.com/supplier', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 300, 'lead_days': 25,
        'quote_date': '2026-09-01', 'valid_until': '2026-08-31'})
    assert response.status_code == 422
    assert 'cannot end before' in response.json()['detail']


def test_a_non_usd_quote_preserves_its_original_amount_and_currency(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Shenzhen Example Ltd',
        'source_url': 'https://example.com/cny-quote', 'unit_price': 61.5, 'currency': 'CNY',
        'moq': 240, 'lead_days': 18, 'quote_date': '2026-09-01', 'incoterm': 'EXW'}).json()
    assert quote['unit_price'] == 61.5
    assert quote['currency'] == 'CNY'
    assert 'unit_price_usd' not in quote


def test_a_dated_quote_feeds_and_is_snapshotted_in_a_reproducible_decision(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Shenzhen Example Ltd',
        'source_url': 'https://example.com/cny-quote', 'unit_price': 61.5, 'currency': 'CNY',
        'moq': 240, 'lead_days': 18, 'quote_date': '2026-09-01', 'incoterm': 'FOB'}).json()
    inputs = {**INPUTS, 'quantity': 240, 'unit_cost_usd': 8.61}
    saved = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'quoted'}, json={
        'product_id': confirmed, 'inputs': inputs, 'quote_id': quote['id'],
        'quote_fx_to_usd': 0.14}).json()
    assert saved['inputs'] == inputs
    assert saved['quote_id'] == quote['id']
    assert saved['supplier_quote']['unit_price'] == 61.5
    assert saved['supplier_quote']['currency'] == 'CNY'
    assert saved['supplier_quote']['quote_date'] == '2026-09-01'
    assert saved['supplier_quote']['source_url'] == 'https://example.com/cny-quote'
    assert saved['quote_conversion'] == {
        'source_currency': 'CNY', 'rate_to_usd': 0.14,
        'effective_unit_cost_usd': 8.61, 'truth_state': 'User input'}

    retry = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'quoted'}, json={
        'product_id': confirmed, 'inputs': inputs, 'quote_id': quote['id'],
        'quote_fx_to_usd': 0.14}).json()
    assert retry['id'] == saved['id']
    changed_rate = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'quoted'}, json={
        'product_id': confirmed, 'inputs': inputs, 'quote_id': quote['id'],
        'quote_fx_to_usd': 0.14001})
    assert changed_rate.status_code == 409


def test_a_saved_decision_preserves_expiry_and_moq_conflicts(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Historical Quote Ltd',
        'source_url': 'https://example.com/historical-quote', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 500, 'lead_days': 18,
        'quote_date': '2020-01-01', 'valid_until': '2020-02-01',
        'incoterm': 'EXW', 'product_specifications': 'Archived supplier specification',
        'payment_terms': 'Payment before shipment', 'delivery_scope': 'factory_only'}).json()
    saved = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'quote-warnings'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': quote['id']}).json()
    assert saved['quote_checks']['validity_state'] == 'expired'
    assert saved['quote_checks']['quantity_state'] == 'below_moq'
    assert saved['quote_checks']['required_moq'] == 500
    assert saved['quote_checks']['scenario_quantity'] == INPUTS['quantity']
    assert len(saved['quote_checks']['warnings']) == 3
    assert any('no explicit cost-inclusion list' in warning
               for warning in saved['quote_checks']['warnings'])


def test_explicit_quote_inclusions_prevent_double_counting(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Included Freight Ltd',
        'source_url': 'https://example.com/included-freight', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 300, 'lead_days': 18, 'quote_date': '2026-09-01',
        'incoterm': 'CIF', 'delivery_scope': 'international_freight',
        'included_costs': ['international_freight', 'insurance']}).json()
    doubled = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'doubled'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': quote['id']})
    assert doubled.status_code == 422
    assert 'avoid double counting' in doubled.json()['detail']
    assert 'international freight' in doubled.json()['detail']

    explicit_zeroes = {**INPUTS, 'freight_ngn': 0, 'insurance_ngn': 0}
    saved = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'not-doubled'}, json={
        'product_id': confirmed, 'inputs': explicit_zeroes, 'quote_id': quote['id']}).json()
    inclusions = saved['quote_checks']['cost_inclusions']
    assert inclusions['basis'] == 'explicit_quote_record'
    assert inclusions['declared_included'] == ['international_freight', 'insurance']
    assert inclusions['double_counting'] is False


def test_an_incoterm_without_explicit_inclusions_does_not_suppress_costs(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Unspecified CIF Ltd',
        'source_url': 'https://example.com/unspecified-cif', 'unit_price': 8.4,
        'currency': 'USD', 'moq': 300, 'lead_days': 18, 'quote_date': '2026-09-01',
        'incoterm': 'CIF', 'included_costs': []}).json()
    assert quote['included_costs'] == []
    saved = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'cif-context'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': quote['id']}).json()
    assert saved['inputs']['freight_ngn'] == INPUTS['freight_ngn']
    assert any('Incoterm alone does not prove' in warning
               for warning in saved['quote_checks']['warnings'])


def test_a_decision_cannot_misstate_the_selected_quote_conversion(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Shenzhen Example Ltd',
        'source_url': 'https://example.com/cny-quote', 'unit_price': 61.5, 'currency': 'CNY',
        'moq': 240, 'lead_days': 18, 'quote_date': '2026-09-01'}).json()
    missing = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'missing-fx'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': quote['id']})
    mismatched = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'bad-fx'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': quote['id'], 'quote_fx_to_usd': 0.14})
    assert missing.status_code == 422
    assert 'CNY to USD rate' in missing.json()['detail']
    assert mismatched.status_code == 422
    assert 'must match' in mismatched.json()['detail']

    usd_quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'USD Example Ltd',
        'source_url': 'https://example.com/usd-quote', 'unit_price': 8.4, 'currency': 'USD',
        'moq': 300, 'lead_days': 18, 'quote_date': '2026-09-01'}).json()
    unnecessary = client.post('/api/v1/decisions', headers={**HEADERS, 'Idempotency-Key': 'usd-fx'}, json={
        'product_id': confirmed, 'inputs': INPUTS, 'quote_id': usd_quote['id'],
        'quote_fx_to_usd': 0.14})
    assert unnecessary.status_code == 422
    assert 'conversion rate of 1' in unnecessary.json()['detail']


def test_a_quote_needs_an_https_source_and_a_real_date(client, confirmed):
    base = {'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/s',
            'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB'}
    assert client.post('/api/v1/quotes', json={**base, 'source_url': 'http://example.com'}, headers=HEADERS).status_code == 422
    assert client.post('/api/v1/quotes', json={**base, 'quote_date': '2026-02-31'}, headers=HEADERS).status_code == 422
    assert client.post('/api/v1/quotes', json={**base, 'unit_price_usd': 0}, headers=HEADERS).status_code == 422


def test_a_quote_must_belong_to_a_product_in_the_workspace(client, owner):
    response = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': 'not-a-product', 'supplier': 'Example Ltd', 'source_url': 'https://example.com/s',
        'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01'})
    assert response.status_code == 404


def test_watching_a_product_twice_updates_one_rule(client, confirmed):
    first = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': 15}, headers=HEADERS).json()
    second = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': 25}, headers=HEADERS).json()
    items = client.get('/api/v1/watchlists/default/items').json()['items']
    assert first['id'] == second['id']
    assert len(items) == 1
    assert items[0]['threshold_pct'] == 25
    assert items[0]['scheduled'] is False


def test_a_watch_declares_that_collection_is_not_scheduled(client, confirmed):
    watch = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed}, headers=HEADERS).json()
    assert watch['scheduled'] is False
    assert watch['status'] == 'Awaiting evidence'


def test_a_watch_threshold_is_validated(client, confirmed):
    for bad in (0, 101):
        assert client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': bad}, headers=HEADERS).status_code == 422


def test_removing_a_watch_is_scoped_to_the_workspace(client, confirmed):
    watch = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed}, headers=HEADERS).json()
    assert client.delete(f'/api/v1/watchlists/default/items/{watch["id"]}', headers=HEADERS).status_code == 200
    assert client.delete(f'/api/v1/watchlists/default/items/{watch["id"]}', headers=HEADERS).status_code == 404
