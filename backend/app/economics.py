"""Deterministic scenarios. No FX, tariff, sales or confidence is fabricated.

Two formula versions live here on purpose (action plan T04):

``unit-economics/1.0.0``
    The float implementation the pilot shipped. It disagreed with the browser on some
    accepted inputs, so nothing new is calculated with it — but every assessment already
    saved under it must still replay to the values it was saved with, so the code stays.

``unit-economics/1.1.0``
    The current version. Identical formulas, evaluated with the shared scaled-integer
    decimal arithmetic in ``money.py`` so the server and the browser agree exactly.

``calculate()`` uses the current version unless a caller asks for a stored one.
"""
from math import ceil
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from . import money as m

FORMULA_VERSION = 'unit-economics/1.1.0'
THRESHOLD_VERSION = 'decision-gates/1.0.0'


class Inputs(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    quantity: int = Field(ge=1, le=1000000)
    unit_cost_usd: float = Field(ge=0, le=1000000)
    fx_ngn: float = Field(gt=0, le=1000000)
    freight_ngn: float = Field(ge=0, le=1e12)
    duty_pct: float = Field(ge=0, le=100)
    import_tax_pct: float = Field(ge=0, le=100)
    selling_price_ngn: float = Field(gt=0, le=1e12)
    channel_fee_pct: float = Field(ge=0, le=100)
    returns_pct: float = Field(ge=0, le=100)
    marketing_ngn: float = Field(ge=0, le=1e12)
    fixed_cost_ngn: float = Field(ge=0, le=1e12)
    stress_pct: float = Field(ge=0, le=50)
    compliance: Literal['unresolved', 'prohibited'] = 'unresolved'
    channel: str = Field(default='Direct sales', max_length=100)
    shipping: Literal['Air', 'Sea'] = 'Air'


NO_EVIDENCE = {'confidence': 0, 'coverage': False, 'compliance_resolved': False, 'overall': None, 'observation_ids': []}


def money(value):
    """Legacy (1.0.0) rounding: quantise the shortest decimal form of a float."""
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def _scenarios_v1_0_0(i):
    scenarios = []
    for name, price_factor, cost_factor in [('Downside', 1-i.stress_pct/100, 1+i.stress_pct/100), ('Base', 1, 1), ('Upside', 1+i.stress_pct/100, 1-i.stress_pct/100)]:
        supplier = i.unit_cost_usd * i.fx_ngn * cost_factor
        freight = i.freight_ngn / i.quantity * cost_factor
        duty = (supplier + freight) * i.duty_pct / 100
        tax = (supplier + freight + duty) * i.import_tax_pct / 100
        landed = supplier + freight + duty + tax
        price = i.selling_price_ngn * price_factor
        fees = price * i.channel_fee_pct / 100
        returns = price * i.returns_pct / 100
        marketing = i.marketing_ngn / i.quantity
        overhead = i.fixed_cost_ngn / i.quantity
        contribution = price - landed - fees - returns - marketing - overhead
        before_fixed = price - landed - fees - returns
        scenarios.append({
            'name': name, 'supplier': money(supplier), 'freight': money(freight), 'duty': money(duty),
            'import_tax': money(tax), 'landed_cost': money(landed), 'price': money(price),
            'fees': money(fees), 'returns': money(returns), 'marketing': money(marketing), 'overhead': money(overhead),
            'contribution': money(contribution), 'margin_pct': money(contribution/price*100),
            'cash_required': money(landed*i.quantity + i.marketing_ngn + i.fixed_cost_ngn),
            'break_even_cac': money(max(0, before_fixed-overhead)),
            'break_even_units': ceil((i.marketing_ngn+i.fixed_cost_ngn)/before_fixed) if before_fixed > 0 else None,
        })
    return scenarios


def _scenarios_v1_1_0(i):
    """The same formulas, evaluated on scaled integers so the browser can match exactly."""
    one, hundred = m.parse(1), m.parse(100)
    quantity = m.parse(i.quantity)
    unit_cost = m.parse(i.unit_cost_usd)
    fx = m.parse(i.fx_ngn)
    freight_total = m.parse(i.freight_ngn)
    duty_rate = m.div(m.parse(i.duty_pct), hundred)
    tax_rate = m.div(m.parse(i.import_tax_pct), hundred)
    selling_price = m.parse(i.selling_price_ngn)
    fee_rate = m.div(m.parse(i.channel_fee_pct), hundred)
    returns_rate = m.div(m.parse(i.returns_pct), hundred)
    marketing_total = m.parse(i.marketing_ngn)
    fixed_total = m.parse(i.fixed_cost_ngn)
    stress = m.div(m.parse(i.stress_pct), hundred)

    scenarios = []
    for name, price_factor, cost_factor in [('Downside', one - stress, one + stress), ('Base', one, one), ('Upside', one + stress, one - stress)]:
        supplier = m.mul(m.mul(unit_cost, fx), cost_factor)
        freight = m.mul(m.div(freight_total, quantity), cost_factor)
        duty = m.mul(supplier + freight, duty_rate)
        tax = m.mul(supplier + freight + duty, tax_rate)
        landed = supplier + freight + duty + tax
        price = m.mul(selling_price, price_factor)
        fees = m.mul(price, fee_rate)
        returns = m.mul(price, returns_rate)
        marketing = m.div(marketing_total, quantity)
        overhead = m.div(fixed_total, quantity)
        contribution = price - landed - fees - returns - marketing - overhead
        before_fixed = price - landed - fees - returns
        scenarios.append({
            'name': name, 'supplier': m.money(supplier), 'freight': m.money(freight), 'duty': m.money(duty),
            'import_tax': m.money(tax), 'landed_cost': m.money(landed), 'price': m.money(price),
            'fees': m.money(fees), 'returns': m.money(returns), 'marketing': m.money(marketing), 'overhead': m.money(overhead),
            'contribution': m.money(contribution), 'margin_pct': m.money(m.mul(m.div(contribution, price), hundred)),
            'cash_required': m.money(m.mul(landed, quantity) + marketing_total + fixed_total),
            'break_even_cac': m.money(max(0, before_fixed - overhead)),
            'break_even_units': m.ceil_units(m.div(marketing_total + fixed_total, before_fixed)) if before_fixed > 0 else None,
        })
    return scenarios


SCENARIO_FORMULAS = {
    'unit-economics/1.0.0': _scenarios_v1_0_0,
    'unit-economics/1.1.0': _scenarios_v1_1_0,
}


def gates(scenarios, inputs, evidence):
    """The decision gates. Unchanged by T04 and versioned separately as THRESHOLD_VERSION."""
    base, downside = scenarios[1], scenarios[0]
    blockers = []
    if not evidence['coverage']: blockers.append('Collect independent demand signals and destination-market evidence.')
    if not evidence['compliance_resolved']: blockers.append('Obtain a reviewed product classification and current import requirements.')
    if evidence['confidence'] < 70: blockers.append('Raise evidence confidence to at least 70 before committing inventory.')
    if base['margin_pct'] < 25: blockers.append('Raise base contribution margin to at least 25%.')
    if downside['margin_pct'] < 10: blockers.append('Keep downside contribution margin at or above 10%.')
    if inputs.compliance == 'prohibited':
        decision = 'NO-GO'
        blockers.insert(0, 'The product is marked prohibited. Do not proceed.')
    elif evidence['confidence'] < 40 or not evidence['coverage']:
        decision = 'INSUFFICIENT EVIDENCE'
    elif base['margin_pct'] < 15 or (evidence['overall'] is not None and evidence['overall'] < 55):
        decision = 'NO-GO'
    elif not blockers and (evidence['overall'] or 0) >= 75:
        decision = 'GO'
    else:
        decision = 'WATCH'
    return decision, blockers


def calculate(inputs: Inputs, evidence=None, formula_version: str = FORMULA_VERSION):
    """Scenarios and gates for `inputs`.

    `formula_version` exists so a stored assessment replays under the version it was
    saved with. Callers producing a *new* assessment must leave it at the default.
    """
    if formula_version not in SCENARIO_FORMULAS:
        raise ValueError(f'unknown formula version: {formula_version}')
    evidence = evidence or dict(NO_EVIDENCE)
    scenarios = SCENARIO_FORMULAS[formula_version](inputs)
    decision, blockers = gates(scenarios, inputs, evidence)
    return {'formula_version': formula_version, 'truth_state': 'Calculated', 'currency': 'NGN', 'market': 'NG',
            'decision': decision, 'confidence': evidence['confidence'], 'observation_ids': evidence['observation_ids'],
            'blockers': blockers, 'scenarios': scenarios, 'inputs': inputs.model_dump(), 'input_truth_state': 'User input'}
