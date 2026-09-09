"""Account recovery, password change and session revocation (action plan P03).

Delivery is still blocked on a provider decision, so these run against the local mail
sink P03's acceptance checks call for: the token is read out of the message the user
would have received, not out of the database. That is the difference between testing
recovery and testing a token table.

Review finding R02 is why this matters beyond the plan: a normalisation bug locked valid
accounts out, and there was no way for an affected person to get back in.
"""
import pytest
from fastapi.testclient import TestClient

from app import mail
from app.db import RecoveryToken, Session, User
from app.main import create_app
from app.security import token_hash
from app.settings import Settings
from conftest import HEADERS, PASSWORD, register

NEW_PASSWORD = 'a-brand-new-long-password'


@pytest.fixture
def sink_app(database_url):
    """An app whose mail goes to a local sink, so a test can read what was sent."""
    settings = Settings(environment='test', database_url=database_url,
                        origins=('http://localhost:3000',), allow_registration=True,
                        mail_transport='sink')
    return create_app(settings)


@pytest.fixture
def sink_client(sink_app):
    with TestClient(sink_app) as client:
        yield client


@pytest.fixture
def sink(sink_app):
    return sink_app.state.mailer


@pytest.fixture
def second_sink_client(sink_app):
    """A second cookie jar on the *sink* app. `second_client` follows the default app,
    so using it here would sign in against a different database entirely."""
    return TestClient(sink_app)


def reset_token(sink):
    """The token as the user would receive it: parsed out of the message body."""
    message = sink.latest('password_reset')
    assert message is not None, 'no reset message was sent'
    line = next(line for line in message.body.splitlines() if line.startswith('Reset token:'))
    return line.split(':', 1)[1].strip()


def ask(client, email='owner@example.com'):
    return client.post('/api/v1/auth/recovery/request', json={'email': email}, headers=HEADERS)


# --- The end-to-end flow -------------------------------------------------------------

def test_a_locked_out_user_can_reset_and_sign_in_again(sink_client, sink):
    owner = register(sink_client)
    assert ask(sink_client).status_code == 202

    response = sink_client.post('/api/v1/auth/recovery/reset',
                                json={'token': reset_token(sink), 'password': NEW_PASSWORD},
                                headers=HEADERS)
    assert response.status_code == 200, response.text

    # The old password is gone and the new one works.
    assert sink_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': PASSWORD},
                            headers=HEADERS).status_code == 401
    assert sink_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 200


def test_the_message_is_addressed_to_the_account_and_says_what_it_is_for(sink_client, sink):
    owner = register(sink_client)
    ask(sink_client)
    message = sink.latest('password_reset')
    assert message.to == owner['email']
    assert 'reset' in message.subject.lower()
    # It must be usable by a person who did not ask for it: no action needed.
    assert 'no action is needed' in message.body.lower()


def test_a_reset_ends_every_session_including_the_one_that_asked(sink_client, sink, second_sink_client):
    """A reset exists because someone may be holding a session they should not have."""
    owner = register(sink_client)
    second_sink_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': PASSWORD},
                            headers=HEADERS)
    assert second_sink_client.get('/api/v1/auth/me').status_code == 200

    ask(sink_client)
    body = sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': reset_token(sink), 'password': NEW_PASSWORD},
                            headers=HEADERS).json()
    assert body['sessions_revoked'] >= 2
    assert sink_client.get('/api/v1/auth/me').status_code == 401
    assert second_sink_client.get('/api/v1/auth/me').status_code == 401


# --- The token is a credential -------------------------------------------------------

def test_only_the_hash_of_a_token_is_stored(sink_client, sink, sink_app):
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    with sink_app.state.database.session() as db:
        rows = db.query(RecoveryToken).all()
        assert len(rows) == 1
        assert rows[0].token_hash != token
        assert rows[0].token_hash == token_hash(token)


def test_a_token_works_once(sink_client, sink):
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    first = sink_client.post('/api/v1/auth/recovery/reset',
                             json={'token': token, 'password': NEW_PASSWORD}, headers=HEADERS)
    assert first.status_code == 200
    second = sink_client.post('/api/v1/auth/recovery/reset',
                              json={'token': token, 'password': 'yet-another-long-password'},
                              headers=HEADERS)
    assert second.status_code == 400


def test_asking_again_invalidates_the_previous_link(sink_client, sink):
    """A forwarded or leaked earlier mail must stop working once a new one is asked for."""
    register(sink_client)
    ask(sink_client)
    stale = reset_token(sink)
    ask(sink_client)
    fresh = reset_token(sink)
    assert stale != fresh
    assert sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': stale, 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 400
    assert sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': fresh, 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 200


def test_an_expired_token_is_refused(sink_client, sink, sink_app):
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    with sink_app.state.database.session() as db:
        db.query(RecoveryToken).update({'expires_at': '2020-01-01T00:00:00+00:00'})
        db.commit()
    assert sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': token, 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 400


def test_a_token_minted_for_another_purpose_cannot_reset_a_password(sink_client, sink, sink_app):
    """Purpose-bound: a future verification token must not double as a reset token."""
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    with sink_app.state.database.session() as db:
        db.query(RecoveryToken).update({'purpose': 'email_verification'})
        db.commit()
    assert sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': token, 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 400


def test_every_rejection_reads_the_same(sink_client, sink, sink_app):
    """Expired, spent, wrong-purpose and never-existed must be indistinguishable."""
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    sink_client.post('/api/v1/auth/recovery/reset',
                     json={'token': token, 'password': NEW_PASSWORD}, headers=HEADERS)
    spent = sink_client.post('/api/v1/auth/recovery/reset',
                             json={'token': token, 'password': NEW_PASSWORD}, headers=HEADERS)
    invented = sink_client.post('/api/v1/auth/recovery/reset',
                                json={'token': 'x' * 40, 'password': NEW_PASSWORD}, headers=HEADERS)
    assert spent.status_code == invented.status_code == 400
    assert spent.json()['detail'] == invented.json()['detail']


# --- The request endpoint must not be an account oracle -------------------------------

def test_the_response_is_identical_whether_or_not_the_account_exists(sink_client, sink):
    register(sink_client)
    known = ask(sink_client, 'owner@example.com')
    unknown = ask(sink_client, 'nobody@example.com')
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_no_message_is_sent_for_an_address_with_no_workspace(sink_client, sink):
    register(sink_client)
    ask(sink_client, 'nobody@example.com')
    assert sink.sent == []


def test_recovery_requests_are_rate_limited(sink_client, sink, sink_app):
    """Otherwise this endpoint is a way to flood one person's inbox, or to probe addresses."""
    register(sink_client)
    limit = sink_app.state.settings.login_account_hourly_limit
    accepted = sum(ask(sink_client).status_code == 202 for _ in range(limit + 5))
    assert accepted == limit, accepted
    assert ask(sink_client).status_code == 429


# --- With no transport configured -----------------------------------------------------

def test_recovery_reports_itself_unavailable_rather_than_silently_dropping(client):
    """The default app has no transport. It must not imply a mail is coming."""
    register(client)
    response = client.post('/api/v1/auth/recovery/request',
                           json={'email': 'owner@example.com'}, headers=HEADERS)
    assert response.status_code == 202
    assert response.json()['delivery_configured'] is False


def test_no_token_is_minted_when_nothing_can_deliver_it(client, app):
    """A token that cannot reach anyone is a credential sitting in a table for no reason."""
    register(client)
    client.post('/api/v1/auth/recovery/request', json={'email': 'owner@example.com'}, headers=HEADERS)
    with app.state.database.session() as db:
        assert db.query(RecoveryToken).count() == 0


def test_the_unconfigured_transport_refuses_rather_than_pretending():
    with pytest.raises(mail.MailNotConfigured):
        mail.UnconfiguredMailer().send(mail.Message('a@example.com', 'subject', 'body'))


# --- Changing a password while signed in ----------------------------------------------

def test_a_password_change_requires_the_current_password(client, owner):
    response = client.post('/api/v1/auth/password',
                           json={'current_password': 'not-the-right-password',
                                 'new_password': NEW_PASSWORD}, headers=HEADERS)
    assert response.status_code == 403
    # The old password still works, so a wrong guess changed nothing.
    assert client.get('/api/v1/auth/me').status_code == 200


def test_a_password_change_keeps_this_session_and_ends_the_others(client, owner, second_client):
    second_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': PASSWORD},
                       headers=HEADERS)
    assert second_client.get('/api/v1/auth/me').status_code == 200

    body = client.post('/api/v1/auth/password',
                       json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
                       headers=HEADERS).json()
    assert body['sessions_revoked'] == 1
    # The browser that made the change stays signed in; the other one does not.
    assert client.get('/api/v1/auth/me').status_code == 200
    assert second_client.get('/api/v1/auth/me').status_code == 401


def test_a_password_change_is_rejected_when_nothing_changes(client, owner):
    response = client.post('/api/v1/auth/password',
                           json={'current_password': PASSWORD, 'new_password': PASSWORD},
                           headers=HEADERS)
    assert response.status_code == 400


def test_a_changed_password_is_the_one_that_signs_in(client, owner, second_client):
    client.post('/api/v1/auth/password',
                json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD}, headers=HEADERS)
    assert second_client.post('/api/v1/auth/login',
                              json={'email': owner['email'], 'password': PASSWORD},
                              headers=HEADERS).status_code == 401
    assert second_client.post('/api/v1/auth/login',
                              json={'email': owner['email'], 'password': NEW_PASSWORD},
                              headers=HEADERS).status_code == 200


# --- Listing and revoking sessions -----------------------------------------------------

def test_the_session_list_marks_the_current_one_and_hides_the_tokens(client, owner, second_client):
    second_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': PASSWORD},
                       headers=HEADERS)
    body = client.get('/api/v1/auth/sessions').json()
    assert body['total'] == 2
    assert [s['current'] for s in body['sessions']].count(True) == 1
    serialised = str(body)
    assert 'token' not in serialised.lower()


def test_a_session_handle_is_not_the_token_hash(client, owner, app):
    handle = client.get('/api/v1/auth/sessions').json()['sessions'][0]['id']
    with app.state.database.session() as db:
        hashes = {row.token_hash for row in db.query(Session).all()}
    assert handle not in hashes


def test_revoking_another_session_signs_that_browser_out(client, owner, second_client):
    second_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': PASSWORD},
                       headers=HEADERS)
    other = next(s for s in client.get('/api/v1/auth/sessions').json()['sessions'] if not s['current'])
    response = client.delete(f'/api/v1/auth/sessions/{other["id"]}', headers=HEADERS)
    assert response.status_code == 200 and response.json()['was_current'] is False
    assert second_client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/auth/me').status_code == 200


def test_a_session_belonging_to_another_account_cannot_be_revoked(client, owner, second_client):
    """The handle is derived from a token hash, so a guessed one must still be rejected."""
    stranger = register(second_client, email='stranger@example.com', name='Other workspace')
    theirs = second_client.get('/api/v1/auth/sessions').json()['sessions'][0]['id']
    assert client.delete(f'/api/v1/auth/sessions/{theirs}', headers=HEADERS).status_code == 404
    # Their session is untouched.
    assert second_client.get('/api/v1/auth/me').status_code == 200


def test_an_expired_session_is_not_listed(client, owner, app):
    with app.state.database.session() as db:
        db.query(Session).update({'expires_at': '2020-01-01T00:00:00+00:00'})
        db.commit()
    # The request itself is now unauthenticated, which is the honest consequence.
    assert client.get('/api/v1/auth/sessions').status_code == 401


def test_recovery_and_session_changes_are_audited(sink_client, sink):
    owner = register(sink_client)
    ask(sink_client)
    sink_client.post('/api/v1/auth/recovery/reset',
                     json={'token': reset_token(sink), 'password': NEW_PASSWORD}, headers=HEADERS)
    sink_client.post('/api/v1/auth/login', json={'email': owner['email'], 'password': NEW_PASSWORD},
                     headers=HEADERS)
    actions = {event['action'] for event in sink_client.get('/api/v1/audit').json()['events']}
    assert {'auth.recovery_requested', 'auth.password_reset'} <= actions
