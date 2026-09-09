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
from datetime import date, datetime, timedelta, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @field_validator('effective_from', 'effective_to')
    @classmethod
    def a_real_calendar_date(cls, value):
        """Review finding R03: the pattern accepted `2026-13-45`. A date that cannot exist
        cannot say when a rule came into force."""
        if value is None:
            return value
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError('An effective date must be a real calendar date, as YYYY-MM-DD.')
        return value

    @model_validator(mode='after')
    def the_period_runs_forwards(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError('A source cannot stop being effective before it starts.')
        return self


#: The classification shapes this pilot accepts: 4-10 bare digits, or a dotted heading
#: (`8451.30`, `8451.30.00`). Review finding F04: the previous check only asked whether
#: every character was a digit or a dot, so `.` and `....` were accepted as classifications
#: and cleared the gate. Accepting a shape is not accepting a classification — a reviewer
#: still decides whether the code is the right one.
HS_CODE = re.compile(r'^(?:\d{4,10}|\d{4}(?:\.\d{2}){1,3})$')


def valid_hs_code(value):
    """Whether `value` is one of the documented classification shapes."""
    return bool(value and HS_CODE.fullmatch(value.strip()))


class ReviewDecision(BaseModel):
    """A reviewer's answer. An approval must cite what it rests on."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    status: Literal['approved', 'rejected', 'more_information']
    rationale: str = Field(min_length=10, max_length=4000)
    hs_code: str = Field(default='', max_length=20)
    requirements: list[str] = Field(default_factory=list, max_length=30)
    sources: list[RuleSource] = Field(default_factory=list, max_length=20)
    validity_days: int = Field(default=DEFAULT_VALIDITY_DAYS, ge=1, le=MAX_VALIDITY_DAYS)
    #: An approval that lists no requirements must say so deliberately. Silence is not a
    #: finding, and review finding R03 found an empty list clearing the gate (R03).
    no_additional_requirements: bool = False

    @field_validator('requirements')
    @classmethod
    def each_requirement_says_something(cls, value):
        for requirement in value:
            if len(requirement.strip()) < 4:
                raise ValueError('Each requirement must be a sentence, not a placeholder.')
        return value

    @model_validator(mode='after')
    def an_approval_states_what_it_approved(self):
        """Review finding R03: an approval cleared the gate with no classification and no
        requirements. An approval is a determination about a specific classification, so
        it has to name one and say what it found."""
        if self.status != 'approved':
            return self
        if not self.hs_code.strip():
            raise ValueError('An approval must record the classification it reviewed.')
        if not self.requirements and not self.no_additional_requirements:
            raise ValueError('List the requirements found, or record explicitly that no '
                             'additional requirements apply.')
        return self

    @field_validator('hs_code')
    @classmethod
    def digits_and_dots_only(cls, value):
        if value and not valid_hs_code(value):
            raise ValueError('An HS code must contain 4–10 digits, optionally grouped as 8451.30.00.')
        return value


def source_is_in_force(source, moment):
    """Whether one cited publication is in force on `moment` (a date string)."""
    try:
        starts = date.fromisoformat(source.get('effective_from', ''))
        today = date.fromisoformat(moment)
        ends = date.fromisoformat(source['effective_to']) if source.get('effective_to') else None
    except (TypeError, ValueError):
        return False
    if starts > today:
        return False                              # not yet in force
    return not ends or ends >= today              # inclusive of its final day


def approval_determination_complete(review):
    """Whether an approval records an actual classification and requirements finding.

    This is checked on reads as well as writes because releases before R03 allowed an
    incomplete approval to be stored. Historical assessments remain immutable; only the
    current gate stops trusting that legacy record.
    """
    return (valid_hs_code(review.get('hs_code', '')) and
            bool(review.get('requirements') or review.get('no_additional_requirements')))


def sources_in_force(sources, now=None):
    """The cited publications that are in force right now.

    Review finding R03: effective dates were stored and shown but never consulted, so an
    approval could rest entirely on a rule that stopped applying in 2011 and the gate
    still read `resolved`. Support that is expired or not yet in force is not support.
    """
    moment = (now or datetime.now(timezone.utc)).date().isoformat()
    return [source for source in (sources or []) if source_is_in_force(source, moment)]


def approval_support(sources, now=None):
    """``(ok, reason)`` — whether these sources can support an approval at `now`."""
    if not sources:
        return False, 'An approval must cite the official sources it rests on.'
    if not sources_in_force(sources, now):
        return False, ('Every cited source is expired or not yet in force. An approval must '
                       'rest on a publication that applies today.')
    return True, ''


def approval_is_current(review, now=None):
    """True only for an approval that exists, has not expired, was not superseded, and
    still rests on a publication that is in force (review finding R03).

    The support check is applied on read as well as at decision time, so an approval that
    was already stored before this rule existed cannot keep clearing the gate on lapsed
    evidence.
    """
    if not review or review.get('status') != 'approved' or review.get('superseded_by'):
        return False
    if not approval_determination_complete(review):
        return False
    expires = review.get('expires_at')
    if not (expires and expires > (now or datetime.now(timezone.utc)).isoformat()):
        return False
    return bool(sources_in_force(review.get('sources'), now))


def expiry(validity_days, now=None):
    return ((now or datetime.now(timezone.utc)) + timedelta(days=validity_days)).isoformat()


def approval_expiry(validity_days, sources, now=None):
    """When an approval lapses: its validity window, bounded by the support it cites.

    An approval must not outlive the publication it rests on, so a source that stops
    applying in 30 days ends the approval then rather than in 180 days (R03).
    """
    horizon = expiry(validity_days, now)
    ends = [source['effective_to'] for source in (sources or []) if source.get('effective_to')]
    if not ends:
        return horizon
    # Inclusive of the source's final day, in the same UTC ISO shape as `horizon`.
    return min(horizon, f'{min(ends)}T23:59:59.999999+00:00')


#: Statuses that represent a reviewer's actual answer, as opposed to a question waiting
#: for one. Only these decide the gate (review finding E03).
DECIDED_STATUSES = {'approved', 'rejected', 'more_information'}


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
    if status == 'approved' and review.get('superseded_by'):
        # Requesting another review replaces the standing approval. Deliberately
        # asymmetric with a rejection, which keeps standing (E03): asking the question
        # again can hold or worsen the gate, never improve it. Saying "expired" here --
        # as this did -- names the wrong cause and a date that has not passed.
        return {'resolved': False, 'status': 'superseded', 'review_id': review.get('id'),
                'reason': 'This approval was replaced when a new review was requested. '
                          'It resolves nothing until that review is decided.'}
    if status == 'approved' and not approval_determination_complete(review):
        return {'resolved': False, 'status': 'review_incomplete', 'review_id': review.get('id'),
                'reason': 'This older approval does not record a valid classification and an explicit '
                          'requirements determination. Request a new review.'}
    if status == 'approved' and not sources_in_force(review.get('sources'), now):
        return {'resolved': False, 'status': 'support_expired', 'review_id': review.get('id'),
                'reason': 'Every source this approval cites has expired or is not yet in force. '
                          'Request a fresh review.'}
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
