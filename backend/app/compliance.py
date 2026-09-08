"""Import-readiness review (action plan N02, N03).

The reviewed problem: the compliance gate could never be cleared. The Decision Room had a
dropdown, but a self-entered assumption is not a classification, so the gate was either
unresolved or prohibited and GO was unreachable for any real product.

The gate is now resolved by a *review*, and only by someone holding `compliance.review`:

* an analyst **requests** a review, supplying the product, its specifications, the
  destination, the intended use and the specific question — so the reviewer is not
  reconstructing context from unrelated screens;
* a reviewer **decides**: approved, rejected, or more information needed. An approval
  carries the classification candidate that was reviewed, the official sources it rests on
  with their effective dates, the requirements found, a rationale, and an expiry;
* a decision **supersedes** the previous one rather than editing it. Prior decisions are
  retained, and the assessments that referenced them keep referencing them.

Nothing here generates a rate, a code or a requirement. A candidate HS code stays a
candidate until a qualified person reviews it, and every rule carries the source it came
from. Software acceptance does not establish classification correctness; the reviewer does.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

REVIEW_VERSION = 'compliance-review/1.0.0'
STATUSES = ('requested', 'approved', 'rejected', 'more_information', 'superseded')
#: An approval is not permanent: rules change, and an unbounded approval would quietly
#: become a claim about the future.
DEFAULT_VALIDITY_DAYS = 180
MAX_VALIDITY_DAYS = 365


class ReviewRequest(BaseModel):
    """What an analyst sends a reviewer. Enough to answer without chasing context."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    product_id: str = Field(min_length=1, max_length=200)
    specifications: str = Field(min_length=10, max_length=4000)
    intended_use: str = Field(min_length=4, max_length=1000)
    question: str = Field(min_length=10, max_length=2000)
    hs_code_candidate: str = Field(default='', max_length=20)
    destination: Literal['NG'] = 'NG'

    @field_validator('hs_code_candidate')
    @classmethod
    def digits_and_dots_only(cls, value):
        if value and not all(character.isdigit() or character == '.' for character in value):
            raise ValueError('An HS code candidate is digits, optionally separated by dots.')
        return value


class RuleSource(BaseModel):
    """One official publication a reviewer relied on."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=300)
    url: str = Field(min_length=12, max_length=2000)
    publisher: str = Field(min_length=2, max_length=200)
    effective_from: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    effective_to: str | None = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('url')
    @classmethod
    def an_https_reference(cls, value):
        if not value.startswith('https://') or '.' not in value[8:].split('/')[0]:
            raise ValueError('A regulatory source must be a full https:// address.')
        return value


class ReviewDecision(BaseModel):
    """A reviewer's answer. An approval must cite what it rests on."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    status: Literal['approved', 'rejected', 'more_information']
    rationale: str = Field(min_length=10, max_length=4000)
    hs_code: str = Field(default='', max_length=20)
    requirements: list[str] = Field(default_factory=list, max_length=30)
    sources: list[RuleSource] = Field(default_factory=list, max_length=20)
    validity_days: int = Field(default=DEFAULT_VALIDITY_DAYS, ge=1, le=MAX_VALIDITY_DAYS)

    @field_validator('requirements')
    @classmethod
    def each_requirement_says_something(cls, value):
        for requirement in value:
            if len(requirement.strip()) < 4:
                raise ValueError('Each requirement must be a sentence, not a placeholder.')
        return value


def approval_is_current(review, now=None):
    """True only for an approval that exists, has not expired and was not superseded."""
    if not review or review.get('status') != 'approved' or review.get('superseded_by'):
        return False
    expires = review.get('expires_at')
    return bool(expires) and expires > (now or datetime.now(timezone.utc)).isoformat()


def expiry(validity_days, now=None):
    return ((now or datetime.now(timezone.utc)) + timedelta(days=validity_days)).isoformat()


def gate_state(review, now=None):
    """How the compliance gate reads, and why — for a screen and for an assessment."""
    if not review:
        return {'resolved': False, 'status': 'none',
                'reason': 'No import-readiness review has been requested for this product.'}
    status = review.get('status')
    if status == 'approved' and approval_is_current(review, now):
        return {'resolved': True, 'status': 'approved',
                'reason': f'Approved by a reviewer on {review["decided_at"][:10]}, valid to {review["expires_at"][:10]}.',
                'review_id': review.get('id'), 'expires_at': review.get('expires_at'),
                'hs_code': review.get('hs_code'), 'requirements': review.get('requirements', [])}
    if status == 'approved':
        return {'resolved': False, 'status': 'expired', 'review_id': review.get('id'),
                'reason': f'The approval expired on {str(review.get("expires_at"))[:10]}. Request a fresh review.'}
    if status == 'rejected':
        return {'resolved': False, 'status': 'rejected', 'review_id': review.get('id'),
                'reason': 'A reviewer rejected this product for import. Do not proceed.'}
    if status == 'more_information':
        return {'resolved': False, 'status': 'more_information', 'review_id': review.get('id'),
                'reason': 'The reviewer asked for more information before deciding.'}
    return {'resolved': False, 'status': 'requested', 'review_id': review.get('id'),
            'reason': 'A review has been requested and is waiting for a reviewer.'}
