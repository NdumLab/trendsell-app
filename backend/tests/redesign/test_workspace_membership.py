"""Controlled workspace intake and separation of review duties."""
import pytest
from fastapi.testclient import TestClient

from app.db import Invitation, User, Workspace
from app.main import create_app
from app.security import token_hash
from app.settings import Settings
from conftest import HEADERS, PASSWORD, register

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'


@pytest.fixture
def membership_app(database_url, tmp_path):
    return create_app(Settings(environment='test', database_url=database_url,
                               origins=('http://localhost:3000',), allow_registration=True,
                               mail_transport='sink',
                               deletion_register_dir=str(tmp_path / 'deletion-register')))


@pytest.fixture
def owner_client(membership_app):
    with TestClient(membership_app) as client:
        register(client)
        yield client


@pytest.fixture
def confirmed(client, owner):
    job = client.post('/api/v1/xray', json={'input': AMAZON},
                      headers={**HEADERS, 'Idempotency-Key': 'membership-review'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm',
                json={'name': 'Review subject'}, headers=HEADERS)
    return job['product_id']


def invite(client, email='reviewer@example.com', role='reviewer'):
    response = client.post('/api/v1/workspace/invitations',
                           json={'email': email, 'role': role}, headers=HEADERS)
    assert response.status_code == 201, response.text
    message = client.app.state.mailer.latest('workspace_invitation')
    assert message is not None and message.to == email
    line = next(line for line in message.body.splitlines() if line.startswith('Invitation token:'))
    return response.json(), line.split(':', 1)[1].strip()


def accept(client, token, name='Independent reviewer'):
    return client.post('/api/v1/auth/invitations/accept',
                       json={'token': token, 'name': name, 'password': PASSWORD}, headers=HEADERS)


def test_an_owner_can_invite_a_member_without_exposing_the_bearer_token(owner_client):
    invitation, token = invite(owner_client)
    assert invitation['role'] == 'reviewer'
    assert invitation['sent_at'] and invitation['accepted_at'] is None
    assert token not in str(invitation)
    message = owner_client.app.state.mailer.latest('workspace_invitation')
    assert '/accept-invitation#token=' in message.body
    with owner_client.app.state.database.session() as db:
        stored = db.query(Invitation).one()
        assert stored.token_hash == token_hash(token)
        assert stored.token_hash != token


def test_accepting_an_invitation_creates_a_verified_member_in_the_bound_workspace(owner_client):
    owner = owner_client.get('/api/v1/auth/me').json()
    _, token = invite(owner_client)
    member_client = TestClient(owner_client.app)
    response = accept(member_client, token)
    assert response.status_code == 201, response.text
    member = response.json()
    assert member['role'] == 'reviewer'
    assert member['email'] == 'reviewer@example.com'
    assert member['workspace_id'] == owner['workspace_id']
    assert member['email_verified'] is True
    assert member_client.get('/api/v1/auth/me').json()['id'] == member['id']
    assert accept(TestClient(owner_client.app), token).status_code == 400
    accepted = next(event for event in owner_client.get('/api/v1/audit').json()['events']
                    if event['action'] == 'workspace.invitation_accepted')
    assert accepted['actor'] == member['id']
    assert accepted['detail'] == {'role': 'reviewer'}


def test_only_an_owner_can_list_members_and_change_a_non_owner_role(owner_client):
    _, token = invite(owner_client)
    member_client = TestClient(owner_client.app)
    member = accept(member_client, token).json()
    listed = owner_client.get('/api/v1/workspace/members').json()
    assert {item['email'] for item in listed['members']} == {
        'owner@example.com', 'reviewer@example.com'}
    assert listed['invitations'] == []
    assert member_client.get('/api/v1/workspace/members').status_code == 403

    changed = owner_client.post(f'/api/v1/workspace/members/{member["id"]}/role',
                                json={'role': 'viewer'}, headers=HEADERS)
    assert changed.status_code == 200 and changed.json()['role'] == 'viewer'
    role_event = next(event for event in owner_client.get('/api/v1/audit').json()['events']
                      if event['action'] == 'workspace.member_role_changed')
    assert role_event['detail'] == {
        'member_id': member['id'], 'from_role': 'reviewer', 'to_role': 'viewer'}
    assert member_client.get('/api/v1/audit').status_code == 403
    owner_id = owner_client.get('/api/v1/auth/me').json()['id']
    assert owner_client.post(f'/api/v1/workspace/members/{owner_id}/role',
                             json={'role': 'viewer'}, headers=HEADERS).status_code == 409


def test_inviting_an_existing_account_does_not_reveal_that_it_exists(owner_client):
    other_workspace = TestClient(owner_client.app)
    register(other_workspace, email='existing@example.com', name='Other workspace')
    invitation, token = invite(owner_client, email='existing@example.com')
    assert invitation['email'] == 'existing@example.com'
    assert invitation['sent_at'] and invitation['accepted_at'] is None
    assert accept(TestClient(owner_client.app), token).status_code == 409


def test_revoking_an_invitation_invalidates_it(owner_client):
    invitation, token = invite(owner_client)
    response = owner_client.delete(f'/api/v1/workspace/invitations/{invitation["id"]}',
                                   headers=HEADERS)
    assert response.status_code == 200
    assert accept(TestClient(owner_client.app), token).status_code == 400


def test_inviting_refuses_to_pretend_delivery_when_mail_is_unconfigured(client, owner, app):
    response = client.post('/api/v1/workspace/invitations',
                           json={'email': 'reviewer@example.com', 'role': 'reviewer'}, headers=HEADERS)
    assert response.status_code == 503
    with app.state.database.session() as db:
        assert db.query(Invitation).count() == 0


def test_a_non_owner_cannot_invite_or_administer_members(owner_client):
    _, token = invite(owner_client)
    member_client = TestClient(owner_client.app)
    member = accept(member_client, token).json()
    assert member_client.post('/api/v1/workspace/invitations',
                              json={'email': 'another@example.com', 'role': 'viewer'},
                              headers=HEADERS).status_code == 403
    assert member_client.post(f'/api/v1/workspace/members/{member["id"]}/role',
                              json={'role': 'analyst'}, headers=HEADERS).status_code == 403
    assert member_client.delete(f'/api/v1/workspace/members/{member["id"]}',
                                headers=HEADERS).status_code == 403


def test_removing_a_member_revokes_access_and_allows_a_fresh_invitation(owner_client):
    _, token = invite(owner_client)
    member_client = TestClient(owner_client.app)
    member = accept(member_client, token).json()
    removed = owner_client.delete(f'/api/v1/workspace/members/{member["id"]}', headers=HEADERS)
    assert removed.status_code == 200 and removed.json()['sessions_revoked'] == 1
    removed_event = next(event for event in owner_client.get('/api/v1/audit').json()['events']
                         if event['action'] == 'workspace.member_removed')
    assert removed_event['detail'] == {
        'member_id': member['id'], 'role': 'reviewer', 'sessions_revoked': 1}
    assert member_client.get('/api/v1/auth/me').status_code == 401
    listed = owner_client.get('/api/v1/workspace/members').json()
    assert [row['email'] for row in listed['members']] == ['owner@example.com']
    recovery = member_client.post('/api/v1/auth/recovery/request',
                                  json={'email': member['email']}, headers=HEADERS)
    assert recovery.status_code == 202
    assert owner_client.app.state.mailer.latest('password_reset') is None

    _, fresh_token = invite(owner_client)
    returning = TestClient(owner_client.app)
    accepted = accept(returning, fresh_token, name='Returning reviewer')
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()['id'] == member['id']
    assert returning.get('/api/v1/auth/me').status_code == 200


def test_a_suspended_member_cannot_be_changed_and_does_not_block_workspace_deletion(owner_client):
    _, token = invite(owner_client)
    member_client = TestClient(owner_client.app)
    member = accept(member_client, token).json()
    assert member_client.request('DELETE', '/api/v1/auth/account', headers=HEADERS, json={
        'password': PASSWORD, 'confirmation': 'DELETE Test workspace',
    }).status_code == 403
    assert owner_client.delete(
        f'/api/v1/workspace/members/{member["id"]}', headers=HEADERS).status_code == 200
    assert owner_client.post(f'/api/v1/workspace/members/{member["id"]}/role',
                             json={'role': 'viewer'}, headers=HEADERS).status_code == 404
    deleted = owner_client.request('DELETE', '/api/v1/auth/account', headers=HEADERS, json={
        'password': PASSWORD, 'confirmation': 'DELETE Test workspace',
    })
    assert deleted.status_code == 200, deleted.text
    with owner_client.app.state.database.session() as db:
        assert db.query(User).count() == 0
        assert db.query(Workspace).count() == 0


def test_a_person_with_review_permission_still_cannot_decide_their_own_request(client, confirmed):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests', json={
        'product_id': confirmed,
        'specifications': '1500 W appliance with a grounded plug and plastic housing.',
        'intended_use': 'Retail sale to consumers in Lagos',
        'question': 'Which classification and import requirements apply to this product?',
        'hs_code_candidate': '8451.30', 'destination': 'NG',
    }, headers=HEADERS).json()
    response = client.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json={
        'status': 'rejected',
        'rationale': 'The requester has not supplied enough information for classification.',
    }, headers=HEADERS)
    assert response.status_code == 403
    assert 'different workspace reviewer' in response.json()['detail']
    assert client.get(f'/api/v1/products/{confirmed}/compliance').json()['can_review'] is False


def test_review_capability_is_true_only_for_a_different_reviewer(owner_client):
    job = owner_client.post('/api/v1/xray', json={'input': AMAZON},
                            headers={**HEADERS, 'Idempotency-Key': 'review-capability'}).json()
    product_id = job['product_id']
    owner_client.post(f'/api/v1/products/{product_id}/confirm',
                      json={'name': 'Review subject'}, headers=HEADERS)
    requested = owner_client.post(f'/api/v1/products/{product_id}/compliance/requests', json={
        'product_id': product_id,
        'specifications': '1500 W appliance with a grounded plug and plastic housing.',
        'intended_use': 'Retail sale to consumers in Lagos',
        'question': 'Which classification and import requirements apply to this product?',
        'hs_code_candidate': '8451.30', 'destination': 'NG',
    }, headers=HEADERS)
    assert requested.status_code == 201
    _, token = invite(owner_client)
    reviewer = TestClient(owner_client.app)
    assert accept(reviewer, token).status_code == 201
    assert owner_client.get(f'/api/v1/products/{product_id}/compliance').json()['can_review'] is False
    assert reviewer.get(f'/api/v1/products/{product_id}/compliance').json()['can_review'] is True


def test_invitation_delivery_is_rate_limited_per_workspace(database_url):
    app = create_app(Settings(
        environment='test', database_url=database_url,
        origins=('http://localhost:3000',), allow_registration=True,
        mail_transport='sink', invitation_workspace_hourly_limit=1))
    with TestClient(app) as owner_client:
        register(owner_client)
        assert owner_client.post('/api/v1/workspace/invitations',
                                 json={'email': 'first@example.com', 'role': 'reviewer'},
                                 headers=HEADERS).status_code == 201
        limited = owner_client.post('/api/v1/workspace/invitations',
                                    json={'email': 'second@example.com', 'role': 'reviewer'},
                                    headers=HEADERS)
        assert limited.status_code == 429
        assert len([message for message in app.state.mailer.sent
                    if message.purpose == 'workspace_invitation']) == 1
