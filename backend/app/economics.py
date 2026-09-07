"""Deterministic scenarios. No FX, tariff, sales or confidence is fabricated."""
from math import ceil
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

FORMULA_VERSION = 'unit-economics/1.0.0'

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

def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def calculate(inputs: Inputs, evidence=None):
    i = inputs
    evidence = evidence or {'confidence': 0, 'coverage': False, 'compliance_resolved': False, 'overall': None, 'observation_ids': []}
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
    base, downside = scenarios[1], scenarios[0]
    blockers = []
    if not evidence['coverage']: blockers.append('Collect independent demand signals and destination-market evidence.')
    if not evidence['compliance_resolved']: blockers.append('Obtain a reviewed product classification and current import requirements.')
    if evidence['confidence'] < 70: blockers.append('Raise evidence confidence to at least 70 before committing inventory.')
    if base['margin_pct'] < 25: blockers.append('Raise base contribution margin to at least 25%.')
    if downside['margin_pct'] < 10: blockers.append('Keep downside contribution margin at or above 10%.')
    if i.compliance == 'prohibited':
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
    return {'formula_version': FORMULA_VERSION, 'truth_state': 'Calculated', 'currency': 'NGN', 'market': 'NG',
            'decision': decision, 'confidence': evidence['confidence'], 'observation_ids': evidence['observation_ids'],
            'blockers': blockers, 'scenarios': scenarios, 'inputs': i.model_dump(), 'input_truth_state': 'User input'}
