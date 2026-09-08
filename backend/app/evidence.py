"""Manual evidence and the evidence-quality method (action plan E06, E07, D03).

No collector is connected. Until one is, the only way a product can carry dated evidence
is for a person to record it — and the product must be honest about what that is:

* a typed number is **User input**, never **Observed**. Only a connected, authorised
  collector produces an observation, and none exists yet;
* a manual record still carries everything an observation carries — metric, value, unit,
  market, when it was observed, where it came from, who entered it — because that is what
  makes it inspectable later;
* manual evidence alone is capped below the confidence a GO requires. That is deliberate:
  the gates are not relaxed so that self-reported numbers can clear them.

``quality()`` is the versioned evidence-quality method. Every component it returns can be
explained from the records that produced it, and the score is a **coverage** reading, not
a probability: it says how much dated, independent, current evidence exists for this
product in this market, and nothing about how likely the product is to sell.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

METHOD_VERSION = 'evidence-quality/1.0.0'

#: What a person may record. A collector would produce 'Observed'; nothing does yet.
MANUAL_TRUTH_STATE = 'User input'
COLLECTED_TRUTH_STATES = {'Observed', 'Demo'}

#: Metrics the method understands. Anything else is stored and shown but scores nothing,
#: because the method cannot say what it would mean.
DEMAND_METRICS = {'Search interest', 'Review velocity', 'Marketplace rank', 'Social mentions'}
LOCAL_METRICS = {'Local listing price', 'Local listing count', 'Local seller count', 'Local demand signal'}
METRICS = sorted(DEMAND_METRICS | LOCAL_METRICS | {'Other'})

WINDOW_DAYS = 90
FRESH_DAYS = 30
#: Self-reported evidence cannot reach the confidence a GO needs. Raising this to admit a
#: GO from typed numbers would be relaxing the gate, not passing it.
MANUAL_ONLY_CAP = 60

WEIGHTS = {
    'demand_metrics': (15, 45),   # points each, capped
    'distinct_sources': (10, 30),
    'destination_coverage': (15, 15),
    'freshness': (10, 10),
}


class EvidenceRequest(BaseModel):
    """One dated observation a person is recording, with where it came from."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    metric: str = Field(min_length=2, max_length=80)
    value: float | None = Field(default=None, ge=-1e12, le=1e12)
    unit: str = Field(min_length=1, max_length=40)
    market: Literal['US', 'NG', 'CN', 'GLOBAL'] = 'NG'
    observed_at: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    source_name: str = Field(min_length=2, max_length=160)
    source_url: str = Field(default='', max_length=2000)
    method: str = Field(min_length=4, max_length=400)
    notes: str = Field(default='', max_length=2000)

    @field_validator('observed_at')
    @classmethod
    def a_real_past_date(cls, value):
        try:
            observed = datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError('Observation date is not a real date.')
        if observed > datetime.now(timezone.utc) + timedelta(days=1):
            raise ValueError('An observation cannot be dated in the future.')
        return value

    @field_validator('source_url')
    @classmethod
    def an_https_reference(cls, value):
        if value and not value.startswith('https://'):
            raise ValueError('A source reference must be an https:// address, or left empty.')
        return value


def age_days(observed_at, now):
    observed = datetime.strptime(observed_at[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return (now - observed).days


def quality(records, compliance_resolved, now=None):
    """The evidence-quality reading for one product, and why it says what it says.

    `records` are stored evidence payloads; `compliance_resolved` comes from the review
    workflow, not from the person entering the numbers. Returns the gate inputs plus a
    `components` breakdown that a screen can show line by line.
    """
    now = now or datetime.now(timezone.utc)
    in_window = [r for r in records if age_days(r['observed_at'], now) <= WINDOW_DAYS]
    demand = {r['metric'] for r in in_window if r['metric'] in DEMAND_METRICS}
    local = [r for r in in_window if r['market'] == 'NG' and r['metric'] in LOCAL_METRICS]
    sources = {(r.get('source_name') or '').strip().lower() for r in in_window if r.get('source_name')}
    freshest = min((age_days(r['observed_at'], now) for r in in_window), default=None)
    collected = any(r.get('truth_state') in COLLECTED_TRUTH_STATES for r in in_window)

    components = [
        {'name': 'Independent demand metrics',
         'detail': f'{len(demand)} distinct demand metric(s) dated within {WINDOW_DAYS} days',
         'points': min(len(demand) * WEIGHTS['demand_metrics'][0], WEIGHTS['demand_metrics'][1]),
         'max': WEIGHTS['demand_metrics'][1]},
        {'name': 'Distinct sources',
         'detail': f'{len(sources)} distinct source(s)',
         'points': min(len(sources) * WEIGHTS['distinct_sources'][0], WEIGHTS['distinct_sources'][1]),
         'max': WEIGHTS['distinct_sources'][1]},
        {'name': 'Destination coverage',
         'detail': f'{len(local)} Nigeria market record(s)' if local else 'No Nigeria market evidence',
         'points': WEIGHTS['destination_coverage'][0] if local else 0,
         'max': WEIGHTS['destination_coverage'][1]},
        {'name': 'Freshness',
         'detail': 'No evidence in window' if freshest is None else f'Newest record is {freshest} day(s) old',
         'points': 0 if freshest is None else (10 if freshest <= FRESH_DAYS else 5),
         'max': WEIGHTS['freshness'][1]},
    ]
    raw = sum(component['points'] for component in components)
    capped = raw if collected else min(raw, MANUAL_ONLY_CAP)

    limitations = []
    if not in_window:
        limitations.append(f'No evidence dated within the last {WINDOW_DAYS} days.')
    if not collected and in_window:
        limitations.append(f'All evidence is self-reported, so the score is capped at {MANUAL_ONLY_CAP}. '
                           'Only a connected, authorised collector can raise it further.')
    if not demand:
        limitations.append('No recognised demand metric has been recorded.')
    if not local:
        limitations.append('No Nigeria market evidence. Missing local listings are not low competition.')
    if not compliance_resolved:
        limitations.append('Import readiness has not been resolved by a reviewer.')

    return {
        'confidence': capped,
        'coverage': bool(demand) and bool(local),
        'compliance_resolved': compliance_resolved,
        # An evidence-coverage reading, not a probability. Named `overall` because the
        # decision gates already read that key.
        'overall': capped,
        'observation_ids': sorted(r['id'] for r in in_window if r.get('id')),
        'method_version': METHOD_VERSION,
        'score_meaning': 'Evidence coverage for this product and market. Not a probability of success.',
        'components': components,
        'raw_points': raw,
        'capped_at': None if collected else MANUAL_ONLY_CAP,
        'records_in_window': len(in_window),
        'records_total': len(records),
        'limitations': limitations,
    }
