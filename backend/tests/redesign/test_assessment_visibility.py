"""A product's evidence status and the user's saved assessment are separate facts (T07).

Review finding 7: saving a prohibited-product assessment returned NO-GO, but the product
still reported INSUFFICIENT EVIDENCE with a generic evidence blocker, and Discover and the
watchlist read that unchanged product verdict. The two were presented as one decision.
"""
import pytest

from app.economics import Inputs, calculate, economics_summary
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}
LOSS_MAKING = {**INPUTS, 'selling_price_ngn': 9000}


@pytest.fixture
def confirmed(client, owner):
    job = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'x'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    return job['product_id']


def save(client, product_id, key, inputs=None):
    return client.post('/api/v1/decisions', json={'product_id': product_id, 'inputs': inputs or INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': key}).json()


def test_a_product_with_no_assessment_says_so_rather_than_implying_one(client, confirmed):
    product = client.get(f'/api/v1/products/{confirmed}').json()
    assert product['decision'] == 'INSUFFICIENT EVIDENCE'
    assert product['latest_assessment'] is None


def test_a_saved_prohibited_assessment_is_visible_from_the_product(client, confirmed):
    saved = save(client, confirmed, 'prohibited', {**INPUTS, 'compliance': 'prohibited'})
    assert saved['decision'] == 'NO-GO'
    product = client.get(f'/api/v1/products/{confirmed}').json()
    # The evidence status is unchanged — no collector ran — and that is the point.
    assert product['decision'] == 'INSUFFICIENT EVIDENCE'
    latest = product['latest_assessment']
    assert latest['decision'] == 'NO-GO'
    assert latest['compliance'] == 'prohibited'
    assert latest['id'] == saved['id']
    assert latest['saved_at'] == saved['created_at']
    assert latest['channel'] == 'Direct sales' and latest['shipping'] == 'Air'


def test_the_same_assessment_is_visible_from_discover_and_the_watchlist(client, confirmed):
    save(client, confirmed, 'prohibited', {**INPUTS, 'compliance': 'prohibited'})
    client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed}, headers=HEADERS)

    listed = client.get('/api/v1/products').json()['products'][0]
    assert listed['latest_assessment']['decision'] == 'NO-GO'
    assert listed['decision'] == 'INSUFFICIENT EVIDENCE'

    watch = client.get('/api/v1/watchlists/default/items').json()['items'][0]
    assert watch['product_decision'] == 'INSUFFICIENT EVIDENCE'
    assert watch['latest_assessment']['decision'] == 'NO-GO'
    assert watch['latest_assessment']['compliance'] == 'prohibited'


def test_only_the_newest_assessment_is_summarised_and_the_older_one_is_untouched(client, confirmed):
    first = save(client, confirmed, 'one')
    second = save(client, confirmed, 'two', {**INPUTS, 'compliance': 'prohibited'})
    product = client.get(f'/api/v1/products/{confirmed}').json()
    assert product['latest_assessment']['id'] == second['id']
    # The superseded assessment still reads exactly as it was saved.
    stored = client.get(f'/api/v1/decisions/{first["id"]}').json()
    assert stored['inputs'] == INPUTS
    assert stored['decision'] == first['decision']
    assert stored['created_at'] == first['created_at']


def test_an_economic_failure_is_visible_alongside_insufficient_evidence(client, confirmed):
    """Both facts, not one: the gate order used to hide a loss-making scenario."""
    saved = save(client, confirmed, 'loss', LOSS_MAKING)
    assert saved['decision'] == 'INSUFFICIENT EVIDENCE'
    economics = saved['economics']
    assert economics['viable'] is False
    assert economics['base_margin_pct'] < 0
    assert any('does not cover its own costs' in failure for failure in economics['failures'])
    latest = client.get(f'/api/v1/products/{confirmed}').json()['latest_assessment']
    assert latest['decision'] == 'INSUFFICIENT EVIDENCE'
    assert latest['economics']['viable'] is False


def test_a_profitable_scenario_reports_viable_economics_while_evidence_is_still_missing(client, confirmed):
    saved = save(client, confirmed, 'healthy', {**INPUTS, 'selling_price_ngn': 60000})
    assert saved['decision'] == 'INSUFFICIENT EVIDENCE'
    assert saved['economics']['viable'] is True
    assert saved['economics']['failures'] == []


def test_a_stranger_never_sees_another_workspaces_assessment_summary(client, confirmed, second_client, stranger):
    save(client, confirmed, 'prohibited', {**INPUTS, 'compliance': 'prohibited'})
    assert second_client.get(f'/api/v1/products/{confirmed}').status_code == 404
    assert second_client.get('/api/v1/products').json()['products'] == []


# --- The economics reading itself -------------------------------------------------

def test_economics_summary_is_computed_from_scenarios_alone():
    """It must not consult evidence: that is the separation the review asked for."""
    healthy = economics_summary(calculate(Inputs(**{**INPUTS, 'selling_price_ngn': 60000}))['scenarios'])
    assert healthy['viable'] is True and healthy['failures'] == []
    thin = economics_summary(calculate(Inputs(**{**INPUTS, 'selling_price_ngn': 26000}))['scenarios'])
    assert thin['viable'] is False
    loss = economics_summary(calculate(Inputs(**LOSS_MAKING))['scenarios'])
    assert loss['viable'] is False
    assert loss['contribution'] < 0
    assert loss['threshold_version'] == 'decision-gates/1.0.0'


def test_economics_summary_is_not_part_of_the_versioned_formula_output():
    """Adding it to calculate() would change every replayed historical assessment."""
    assert 'economics' not in calculate(Inputs(**INPUTS))
