"""Deterministic scenarios. No FX, tariff, sales or confidence is fabricated.

Three formula versions live here on purpose (action plans T04 and D02):

``unit-economics/1.0.0``
    The float implementation the pilot shipped. It disagreed with the browser on some
    accepted inputs, so nothing new is calculated with it — but every assessment already
    saved under it must still replay to the values it was saved with, so the code stays.

``unit-economics/1.1.0``
    The first exact-decimal version. Identical formulas, evaluated with the shared scaled-integer
    decimal arithmetic in ``money.py`` so the server and the browser agree exactly.

``unit-economics/1.2.0``
    The current landed-cost model. It keeps every 1.1 line and adds explicit packaging,
    insurance, clearance, local delivery, payment-fee, FX-buffer and reserve lines plus
    cash-timing assumptions. No rate or omitted cost is supplied by the application.

``calculate()`` uses the current version unless a caller asks for a stored one.
"""
from math import ceil
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from . import money as m

FORMULA_VERSION = 'unit-economics/1.2.0'
THRESHOLD_VERSION = 'decision-gates/1.2.0'
COST_MODEL_VERSION = 'landed-cost/2.0.0'

# These fields did not exist on historical 1.0/1.1 assessments. Defaults exist only so
# an immutable old payload can still be parsed and replayed under its recorded formula.
# DecisionRequest separately requires every one on a new 2.0 submission; a missing value
# must never silently become a zero in a newly saved assessment.
CURRENT_COST_FIELDS = frozenset({
    'packaging_ngn', 'insurance_ngn', 'clearance_ngn', 'local_delivery_ngn',
    'payment_fee_pct', 'reserve_ngn', 'fx_buffer_pct', 'supplier_deposit_pct',
    'cash_tied_up_days',
})
CURRENT_ROUTE_FIELDS = frozenset({'channel', 'shipping'})


class Inputs(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    quantity: int = Field(ge=1, le=1000000)
    unit_cost_usd: float = Field(ge=0, le=1000000)
    fx_ngn: float = Field(gt=0, le=1000000)
    freight_ngn: float = Field(ge=0, le=1e12)
    packaging_ngn: float = Field(default=0, ge=0, le=1e12)
    insurance_ngn: float = Field(default=0, ge=0, le=1e12)
    clearance_ngn: float = Field(default=0, ge=0, le=1e12)
    local_delivery_ngn: float = Field(default=0, ge=0, le=1e12)
    duty_pct: float = Field(ge=0, le=100)
    import_tax_pct: float = Field(ge=0, le=100)
    fx_buffer_pct: float = Field(default=0, ge=0, le=100)
    selling_price_ngn: float = Field(gt=0, le=1e12)
    channel_fee_pct: float = Field(ge=0, le=100)
    payment_fee_pct: float = Field(default=0, ge=0, le=100)
    returns_pct: float = Field(ge=0, le=100)
    marketing_ngn: float = Field(ge=0, le=1e12)
    fixed_cost_ngn: float = Field(ge=0, le=1e12)
    reserve_ngn: float = Field(default=0, ge=0, le=1e12)
    supplier_deposit_pct: float = Field(default=0, ge=0, le=100)
    cash_tied_up_days: int = Field(default=0, ge=0, le=10000)
    stress_pct: float = Field(ge=0, le=50)
    compliance: Literal['unresolved', 'prohibited'] = 'unresolved'
    channel: str = Field(default='Direct sales', max_length=100)
    shipping: Literal['Air', 'Sea'] = 'Air'


NO_EVIDENCE = {'confidence': 0, 'coverage': False, 'compliance_resolved': False, 'overall': None,
               'observation_ids': [], 'compliance_status': 'none'}


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


def _scenarios_v1_2_0(i):
    """Expanded, explicit landed-cost lines evaluated with the shared exact arithmetic.

    Duty is applied to supplier value (including the user's FX buffer), international
    freight and insurance. Import tax is applied to that same base plus duty. This is a
    transparent scenario formula, not a tariff claim; the UI requires the user to enter
    the rates and tells them to confirm the actual assessment basis through review.
    """
    one, hundred = m.parse(1), m.parse(100)
    quantity = m.parse(i.quantity)
    unit_cost = m.parse(i.unit_cost_usd)
    fx = m.parse(i.fx_ngn)
    totals = {key: m.parse(getattr(i, key)) for key in (
        'freight_ngn', 'packaging_ngn', 'insurance_ngn', 'clearance_ngn',
        'local_delivery_ngn', 'marketing_ngn', 'fixed_cost_ngn', 'reserve_ngn')}
    duty_rate = m.div(m.parse(i.duty_pct), hundred)
    tax_rate = m.div(m.parse(i.import_tax_pct), hundred)
    fx_buffer_rate = m.div(m.parse(i.fx_buffer_pct), hundred)
    selling_price = m.parse(i.selling_price_ngn)
    channel_rate = m.div(m.parse(i.channel_fee_pct), hundred)
    payment_rate = m.div(m.parse(i.payment_fee_pct), hundred)
    returns_rate = m.div(m.parse(i.returns_pct), hundred)
    deposit_rate = m.div(m.parse(i.supplier_deposit_pct), hundred)
    stress = m.div(m.parse(i.stress_pct), hundred)

    scenarios = []
    factors = [('Downside', one - stress, one + stress),
               ('Base', one, one), ('Upside', one + stress, one - stress)]
    for name, price_factor, cost_factor in factors:
        supplier = m.mul(m.mul(unit_cost, fx), cost_factor)
        fx_buffer = m.mul(supplier, fx_buffer_rate)
        packaging = m.mul(m.div(totals['packaging_ngn'], quantity), cost_factor)
        freight = m.mul(m.div(totals['freight_ngn'], quantity), cost_factor)
        insurance = m.mul(m.div(totals['insurance_ngn'], quantity), cost_factor)
        clearance = m.mul(m.div(totals['clearance_ngn'], quantity), cost_factor)
        local_delivery = m.mul(m.div(totals['local_delivery_ngn'], quantity), cost_factor)
        customs_base = supplier + fx_buffer + freight + insurance
        duty = m.mul(customs_base, duty_rate)
        tax = m.mul(customs_base + duty, tax_rate)
        landed = (supplier + fx_buffer + packaging + freight + insurance + duty + tax
                  + clearance + local_delivery)
        price = m.mul(selling_price, price_factor)
        channel_fees = m.mul(price, channel_rate)
        payment_fees = m.mul(price, payment_rate)
        returns = m.mul(price, returns_rate)
        marketing = m.div(totals['marketing_ngn'], quantity)
        overhead = m.div(totals['fixed_cost_ngn'], quantity)
        reserve = m.div(totals['reserve_ngn'], quantity)
        contribution = (price - landed - channel_fees - payment_fees - returns
                        - marketing - overhead - reserve)
        before_fixed = price - landed - channel_fees - payment_fees - returns
        supplier_deposit_cash = m.mul(m.mul(supplier, quantity), deposit_rate)
        launch_totals = (totals['marketing_ngn'] + totals['fixed_cost_ngn']
                         + totals['reserve_ngn'])
        scenarios.append({
            'name': name, 'supplier': m.money(supplier), 'fx_buffer': m.money(fx_buffer),
            'packaging': m.money(packaging), 'freight': m.money(freight),
            'insurance': m.money(insurance), 'duty': m.money(duty),
            'import_tax': m.money(tax), 'clearance': m.money(clearance),
            'local_delivery': m.money(local_delivery), 'landed_cost': m.money(landed),
            'price': m.money(price), 'fees': m.money(channel_fees),
            'payment_fees': m.money(payment_fees), 'returns': m.money(returns),
            'marketing': m.money(marketing), 'overhead': m.money(overhead),
            'reserve': m.money(reserve), 'contribution': m.money(contribution),
            'margin_pct': m.money(m.mul(m.div(contribution, price), hundred)),
            'cash_required': m.money(m.mul(landed, quantity) + launch_totals),
            'supplier_deposit_cash': m.money(supplier_deposit_cash),
            'cash_tied_up_days': i.cash_tied_up_days,
            'break_even_cac': m.money(max(0, before_fixed - overhead - reserve)),
            'break_even_units': (m.ceil_units(m.div(launch_totals, before_fixed))
                                 if before_fixed > 0 else None),
        })
    return scenarios


SCENARIO_FORMULAS = {
    'unit-economics/1.0.0': _scenarios_v1_0_0,
    'unit-economics/1.1.0': _scenarios_v1_1_0,
    'unit-economics/1.2.0': _scenarios_v1_2_0,
}


#: What a reviewer's rejection says, in the assessment as well as on the screen.
REJECTED_BLOCKER = 'A reviewer rejected this product for import. Do not proceed.'
PROHIBITED_BLOCKER = 'The product is marked prohibited. Do not proceed.'


def _blockers_v1_1_0(scenarios, inputs, evidence):
    """The original labels, retained so saved 1.0/1.1 decisions replay exactly."""
    base, downside = scenarios[1], scenarios[0]
    blockers = []
    if not evidence['coverage']: blockers.append('Collect independent demand signals and destination-market evidence.')
    if not evidence['compliance_resolved']: blockers.append('Obtain a reviewed product classification and current import requirements.')
    if evidence['confidence'] < 70: blockers.append('Raise evidence confidence to at least 70 before committing inventory.')
    if base['margin_pct'] < 25: blockers.append('Raise base contribution margin to at least 25%.')
    if downside['margin_pct'] < 10: blockers.append('Keep downside contribution margin at or above 10%.')
    return blockers


def _blockers_v1_2_0(scenarios, inputs, evidence):
    """The same thresholds with financially accurate user-facing terminology.

    `margin_pct` deducts allocated marketing and fixed costs, so it is a net batch
    margin under the entered assumptions—not contribution margin in the usual sense.
    """
    blockers = _blockers_v1_1_0(scenarios, inputs, evidence)
    return [blocker.replace('base contribution margin', 'base net margin after allocated launch costs')
            .replace('downside contribution margin', 'downside net margin after allocated launch costs')
            for blocker in blockers]


def _decide(scenarios, evidence, blockers):
    """The evidence/economics ladder, once nothing has forced NO-GO."""
    base = scenarios[1]
    if evidence['confidence'] < 40 or not evidence['coverage']:
        return 'INSUFFICIENT EVIDENCE'
    if base['margin_pct'] < 15 or (evidence['overall'] is not None and evidence['overall'] < 55):
        return 'NO-GO'
    if not blockers and (evidence['overall'] or 0) >= 75:
        return 'GO'
    return 'WATCH'


def _gates_v1_0_0(scenarios, inputs, evidence):
    """The gates the pilot shipped: only the user's own dropdown can force NO-GO.

    Frozen. Assessments saved under this version replay to the values they were saved
    with, including the ones review finding R04 identifies as wrong.
    """
    blockers = _blockers_v1_1_0(scenarios, inputs, evidence)
    if inputs.compliance == 'prohibited':
        return 'NO-GO', [PROHIBITED_BLOCKER] + blockers
    return _decide(scenarios, evidence, blockers), blockers


def _gates_v1_1_0(scenarios, inputs, evidence):
    """The current gates: a reviewer's rejection is authoritative (review finding R04).

    Under 1.0.0 the gate text said "a reviewer rejected this product for import; do not
    proceed" while the decision beside it read WATCH, because the rejection reached the
    screen but never reached the calculation — only the user re-stating it in a dropdown
    did. A reviewer decision is the authority on import readiness, so it decides here.

    `compliance_status` is the reviewed state from the review workflow, computed on the
    server. It is absent from assessments saved before this version, and a missing value
    means "no reviewer has rejected this", which reproduces 1.0.0 exactly.
    """
    blockers = _blockers_v1_1_0(scenarios, inputs, evidence)
    if evidence.get('compliance_status') == 'rejected':
        return 'NO-GO', [REJECTED_BLOCKER] + blockers
    if inputs.compliance == 'prohibited':
        return 'NO-GO', [PROHIBITED_BLOCKER] + blockers
    return _decide(scenarios, evidence, blockers), blockers


def _gates_v1_2_0(scenarios, inputs, evidence):
    """The 1.1 gates with corrected financial labels; numeric thresholds are unchanged."""
    blockers = _blockers_v1_2_0(scenarios, inputs, evidence)
    if evidence.get('compliance_status') == 'rejected':
        return 'NO-GO', [REJECTED_BLOCKER] + blockers
    if inputs.compliance == 'prohibited':
        return 'NO-GO', [PROHIBITED_BLOCKER] + blockers
    return _decide(scenarios, evidence, blockers), blockers


GATE_RULES = {
    'decision-gates/1.0.0': _gates_v1_0_0,
    'decision-gates/1.1.0': _gates_v1_1_0,
    'decision-gates/1.2.0': _gates_v1_2_0,
}


def gates(scenarios, inputs, evidence, threshold_version: str = THRESHOLD_VERSION):
    """The decision gates for `threshold_version`."""
    if threshold_version not in GATE_RULES:
        raise ValueError(f'unknown threshold version: {threshold_version}')
    return GATE_RULES[threshold_version](scenarios, inputs, evidence)


def economics_summary(scenarios):
    """Whether the scenario pays for itself, judged without reference to evidence.

    Kept out of `calculate()` on purpose: that function's output is pinned by
    `formula_version`, and a replayed historical assessment must reproduce byte for byte.
    This is a separate reading of the same scenarios so a screen can say "the economics
    fail under these assumptions" *and* "demand is unverified" instead of collapsing both
    into one verdict (action plan T07).
    """
    base, downside = scenarios[1], scenarios[0]
    failures = []
    if base['contribution'] <= 0:
        failures.append('The unit does not cover its own costs under these assumptions.')
    if base['margin_pct'] < 15:
        failures.append('Base net margin after allocated launch costs is below the 15% floor.')
    elif base['margin_pct'] < 25:
        failures.append('Base net margin after allocated launch costs is below the 25% target.')
    if downside['margin_pct'] < 10:
        failures.append('Downside net margin after allocated launch costs is below 10%.')
    return {'base_margin_pct': base['margin_pct'], 'downside_margin_pct': downside['margin_pct'],
            'contribution': base['contribution'], 'break_even_units': base['break_even_units'],
            'viable': not failures, 'failures': failures, 'threshold_version': THRESHOLD_VERSION}


def calculate(inputs: Inputs, evidence=None, formula_version: str = FORMULA_VERSION,
              threshold_version: str = THRESHOLD_VERSION):
    """Scenarios and gates for `inputs`.

    `formula_version` and `threshold_version` exist so a stored assessment replays under
    the versions it was saved with — the arithmetic and the decision rules move
    independently. Callers producing a *new* assessment must leave both at the default.
    """
    if formula_version not in SCENARIO_FORMULAS:
        raise ValueError(f'unknown formula version: {formula_version}')
    evidence = {**NO_EVIDENCE, **(evidence or {})}
    scenarios = SCENARIO_FORMULAS[formula_version](inputs)
    decision, blockers = gates(scenarios, inputs, evidence, threshold_version)
    return {'formula_version': formula_version, 'truth_state': 'Calculated', 'currency': 'NGN', 'market': 'NG',
            'decision': decision, 'confidence': evidence['confidence'], 'observation_ids': evidence['observation_ids'],
            'blockers': blockers, 'scenarios': scenarios,
            # Historical payloads retain their old shape; current calculations retain a
            # complete set, including explicit/default route labels used by idempotency.
            'inputs': inputs.model_dump(exclude_unset=formula_version != FORMULA_VERSION),
            'input_truth_state': 'User input'}
