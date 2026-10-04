"""Capture inputs the pilot supports. The frontend asserts the same file in src/lib/identifier.test.ts."""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.security import resolve_input
from conftest import HEADERS

CONTRACT = json.loads((Path(__file__).resolve().parents[3] / 'contracts' / 'identifier_cases.json').read_text())
ACCEPTED = [pytest.param(case, id=case['why']) for case in CONTRACT['accepted']]
REJECTED = [pytest.param(case, id=case['why']) for case in CONTRACT['rejected']]


@pytest.mark.parametrize('case', ACCEPTED)
def test_accepted_input_resolves_to_its_asin(case):
    resolved = resolve_input(case['input'])
    assert resolved['asin'] == case['asin']
    assert resolved['url'] == f"https://www.amazon.com/dp/{case['asin']}"
    assert resolved['market'] == 'US'


@pytest.mark.parametrize('case', REJECTED)
def test_rejected_input_raises_a_helpful_error(case):
    with pytest.raises(HTTPException) as error:
        resolve_input(case['input'])
    assert error.value.status_code == 422
    assert 'ASIN' in error.value.detail


@pytest.mark.parametrize('case', REJECTED)
def test_rejected_input_creates_nothing_through_the_api(client, owner, case):
    response = client.post('/api/v1/xray', json={'input': case['input']}, headers={**HEADERS, 'Idempotency-Key': 'rejected'})
    assert response.status_code == 422
    assert client.get('/api/v1/products').json()['products'] == []
