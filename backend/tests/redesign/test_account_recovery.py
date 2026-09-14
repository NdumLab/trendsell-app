"""Account recovery, password change and session revocation (action plan P03).

Delivery is still blocked on a provider decision, so these run against the local mail
sink P03's acceptance checks call for: the token is read out of the message the user
would have received, not out of the database. That is the difference between testing
recovery and testing a token table.

Review finding R02 is why this matters beyond the plan: a normalisation bug locked valid
accounts out, and there was no way for an affected person to get back in.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app import mail
from app.db import Audit, RateBucket, Record, RecoveryToken, Session, User, Workspace
from app.main import create_app
from app.security import token_hash
from app.settings import Settings
from conftest import HEADERS, PASSWORD, register

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'

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


def test_a_password_reset_does_not_claim_that_the_email_was_verified(sink_client, sink):
    """An operator may deliver a reset through a different trusted channel.

    Possession of that credential proves authority to reset; only the dedicated token
    delivered to the account address proves control of the email address itself.
    """
    register(sink_client)
    assert ask(sink_client).status_code == 202
    response = sink_client.post('/api/v1/auth/recovery/reset',
                                json={'token': reset_token(sink), 'password': NEW_PASSWORD},
                                headers=HEADERS)
    assert response.status_code == 200, response.text
    sink_client.post('/api/v1/auth/login',
                     json={'email': 'owner@example.com', 'password': NEW_PASSWORD},
                     headers=HEADERS)
    account = sink_client.get('/api/v1/auth/me').json()
    assert account['email_verified'] is False
    assert account['email_verified_at'] is None


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
        # Registration also mints a verification credential, so scope this to the reset.
        rows = db.query(RecoveryToken).filter_by(purpose='password_reset').all()
        assert len(rows) == 1
        assert rows[0].token_hash != token
        assert rows[0].token_hash == token_hash(token)
    # Whatever else was issued, no row anywhere stores a token in the clear.
    with sink_app.state.database.session() as db:
        assert token not in [row.token_hash for row in db.query(RecoveryToken).all()]


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


def test_changing_the_password_invalidates_an_older_reset_link(sink_client, sink):
    register(sink_client)
    ask(sink_client)
    token = reset_token(sink)
    changed = sink_client.post('/api/v1/auth/password',
                               json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
                               headers=HEADERS)
    assert changed.status_code == 200, changed.text
    stale = sink_client.post('/api/v1/auth/recovery/reset',
                             json={'token': token, 'password': 'a-third-long-password'},
                             headers=HEADERS)
    assert stale.status_code == 400


def test_one_reset_token_has_one_winner_under_postgres(sink_app, sink, database_url):
    """Two overlapping transactions must not both consume one bearer credential."""
    if not database_url.startswith('postgresql'):
        pytest.skip('PostgreSQL row-lock behavior')
    with TestClient(sink_app) as client:
        register(client)
        ask(client)
    token = reset_token(sink)
    barrier = Barrier(2, timeout=15)
    # Synchronize immediately before both requests enter the database transaction. The
    # application still performs its own token lookup, locks, hash and writes.
    def redeem(password):
        barrier.wait()
        with TestClient(sink_app) as contender:
            return contender.post('/api/v1/auth/recovery/reset',
                                  json={'token': token, 'password': password},
                                  headers=HEADERS).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(redeem, 'parallel-first-password')
        second = pool.submit(redeem, 'parallel-second-password')
        statuses = sorted([first.result(timeout=30), second.result(timeout=30)])
    assert statuses == [200, 400]


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
    # Registration sends its own verification message, so assert on resets specifically:
    # an address with no workspace must receive nothing at all.
    assert [message for message in sink.sent if message.purpose == 'password_reset'] == []
    assert [message for message in sink.sent if message.to == 'nobody@example.com'] == []


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


def test_the_logging_transport_is_not_mistaken_for_delivery(database_url):
    """Logging a delivery attempt cannot make an inbox receive a bearer credential."""
    settings = Settings(environment='test', database_url=database_url,
                        origins=('http://localhost:3000',), allow_registration=True,
                        mail_transport='log')
    app = create_app(settings)
    with TestClient(app) as logged:
        register(logged)
        assert logged.get('/api/v1/config').json()['mail_delivery_configured'] is False
        response = ask(logged)
        assert response.status_code == 202
        assert response.json()['delivery_configured'] is False
        with app.state.database.session() as db:
            assert db.query(RecoveryToken).count() == 0


@pytest.mark.parametrize('transport', ['sink', 'log'])
def test_diagnostic_mail_transports_are_refused_in_production(monkeypatch, transport):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('ALLOW_REGISTRATION', 'false')
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://user:password@db.example/app')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('RATE_KEY_SECRET', 'an-independent-production-rate-key-secret')
    monkeypatch.setenv('MAIL_TRANSPORT', transport)
    with pytest.raises(ValueError, match='development diagnostics'):
        Settings.from_env()


def test_smtp_transport_uses_starttls_authentication_and_an_email_message(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(mail.smtplib, 'SMTP', constructor)
    transport = mail.SMTPMailer(
        host='smtp.example.com', port=587, sender='security@example.com',
        username='mailer', password='secret', starttls=True)
    message = mail.Message('owner@example.com', 'Reset access', 'Use this token.', 'password_reset')

    assert transport.send(message) is message
    constructor.assert_called_once_with('smtp.example.com', 587, timeout=15.0)
    client.starttls.assert_called_once()
    client.login.assert_called_once_with('mailer', 'secret')
    sent = client.send_message.call_args.args[0]
    assert sent['From'] == 'security@example.com'
    assert sent['To'] == 'owner@example.com'
    assert sent['Subject'] == 'Reset access'
    assert 'Use this token.' in sent.get_content()


def test_smtp_transport_can_use_implicit_tls_without_starttls(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(mail.smtplib, 'SMTP_SSL', constructor)
    transport = mail.SMTPMailer(
        host='smtp.example.com', port=465, sender='security@example.com',
        implicit_tls=True, starttls=False)
    transport.send(mail.Message('owner@example.com', 'Subject', 'Body'))
    assert constructor.call_args.kwargs['context'] is not None
    client.starttls.assert_not_called()
    client.login.assert_not_called()


def test_production_accepts_a_complete_tls_smtp_configuration(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('ALLOW_REGISTRATION', 'false')
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://user:password@db.example/app')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('RATE_KEY_SECRET', 'an-independent-production-rate-key-secret')
    monkeypatch.setenv('MAIL_TRANSPORT', 'smtp')
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_USERNAME', 'mailer')
    monkeypatch.setenv('SMTP_PASSWORD', 'secret')
    monkeypatch.setenv('MAIL_FROM', 'security@example.com')
    settings = Settings.from_env()
    assert settings.mail_transport == 'smtp'
    assert mail.build(settings).configured is True


@pytest.mark.parametrize('change,match', [
    ({'SMTP_HOST': ''}, 'SMTP_HOST'),
    ({'MAIL_FROM': ''}, 'MAIL_FROM'),
    ({'SMTP_STARTTLS': 'false'}, 'requires SMTP_STARTTLS'),
    ({'SMTP_SSL': 'true'}, 'cannot both be true'),
])
def test_incomplete_or_insecure_production_smtp_is_refused(monkeypatch, change, match):
    values = {
        'APP_ENV': 'production',
        'ALLOW_REGISTRATION': 'false',
        'DATABASE_URL': 'postgresql+psycopg://user:password@db.example/app',
        'CORS_ORIGINS': 'https://app.example.com',
        'RATE_KEY_SECRET': 'an-independent-production-rate-key-secret',
        'MAIL_TRANSPORT': 'smtp',
        'SMTP_HOST': 'smtp.example.com',
        'MAIL_FROM': 'security@example.com',
        'SMTP_STARTTLS': 'true',
        'SMTP_SSL': 'false',
    }
    values.update(change)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=match):
        Settings.from_env()


def test_production_requires_a_non_enumerable_rate_key(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('ALLOW_REGISTRATION', 'false')
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://user:password@db.example/app')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('MAIL_TRANSPORT', '')
    monkeypatch.setenv('RATE_KEY_SECRET', '')
    with pytest.raises(ValueError, match='RATE_KEY_SECRET'):
        Settings.from_env()
    monkeypatch.setenv('RATE_KEY_SECRET', 'an-independent-production-rate-key-secret')
    settings = Settings.from_env()
    assert settings.rate_key_secret == 'an-independent-production-rate-key-secret'
    assert settings.mail_transport == ''


def test_a_transport_failure_does_not_reveal_which_account_exists(monkeypatch, database_url):
    """Delivery failures must not turn recovery or registration into an oracle."""
    class FailingMailer(mail.Mailer):
        configured = True

        def send(self, message):
            raise OSError('diagnostic delivery failure')

    monkeypatch.setattr(mail, 'build', lambda settings: FailingMailer())
    app = create_app(Settings(environment='test', database_url=database_url,
                              origins=('http://localhost:3000',), allow_registration=True))
    with TestClient(app) as failing:
        account = failing.post('/api/v1/auth/register',
                               json={'email': 'known@example.com', 'password': PASSWORD,
                                     'name': 'Known'}, headers=HEADERS)
        assert account.status_code == 201
        known = ask(failing, 'known@example.com')
        unknown = ask(failing, 'unknown@example.com')
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        verification = failing.post('/api/v1/auth/email-verification/request', headers=HEADERS)
        assert verification.status_code == 202


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


# --- Proving control of an address (local sink, so tests send no external mail) ----------
#
# A production deployment can configure the SMTP transport after its provider and sending
# identity are approved. Ownership verification itself is exercised end to end against the
# sink, exactly as recovery is, without making the test suite depend on an external service.

def verification_token(sink):
    """The token as the user would receive it, parsed out of the message body."""
    message = sink.latest('email_verification')
    assert message is not None, 'no verification message was sent'
    line = next(line for line in message.body.splitlines() if line.startswith('Verification token:'))
    return line.split(':', 1)[1].strip()


def test_a_new_account_starts_unverified_and_is_sent_a_link(sink_client, sink):
    account = register(sink_client)
    assert account['email_verified'] is False
    assert account['email_verified_at'] is None
    message = sink.latest('email_verification')
    assert message.to == 'owner@example.com'
    # The credential travels in the message and nowhere else.
    assert verification_token(sink) not in sink_client.get('/api/v1/auth/me').text


def test_confirming_the_token_verifies_the_address_once(sink_client, sink):
    register(sink_client)
    token = verification_token(sink)
    confirmed = sink_client.post('/api/v1/auth/email-verification/confirm',
                                 json={'token': token}, headers=HEADERS)
    assert confirmed.status_code == 200, confirmed.text
    assert sink_client.get('/api/v1/auth/me').json()['email_verified'] is True
    # Single use: the same token cannot verify again.
    assert sink_client.post('/api/v1/auth/email-verification/confirm',
                            json={'token': token}, headers=HEADERS).status_code == 400


def test_a_reset_token_cannot_verify_an_address(sink_client, sink):
    """Purposes are not interchangeable: one credential does exactly one thing."""
    register(sink_client)
    ask(sink_client)
    assert sink_client.post('/api/v1/auth/email-verification/confirm',
                            json={'token': reset_token(sink)}, headers=HEADERS).status_code == 400
    assert sink_client.get('/api/v1/auth/me').json()['email_verified'] is False


def test_a_verification_token_cannot_reset_a_password(sink_client, sink):
    register(sink_client)
    assert sink_client.post('/api/v1/auth/recovery/reset',
                            json={'token': verification_token(sink), 'password': NEW_PASSWORD},
                            headers=HEADERS).status_code == 400


def test_asking_again_invalidates_the_previous_verification_link(sink_client, sink):
    register(sink_client)
    stale = verification_token(sink)
    assert sink_client.post('/api/v1/auth/email-verification/request',
                            headers=HEADERS).status_code == 202
    assert verification_token(sink) != stale
    assert sink_client.post('/api/v1/auth/email-verification/confirm',
                            json={'token': stale}, headers=HEADERS).status_code == 400


def test_an_expired_verification_token_is_refused(sink_client, sink, sink_app):
    register(sink_client)
    token = verification_token(sink)
    with sink_app.state.database.session() as db:
        db.query(RecoveryToken).filter_by(purpose='email_verification').update(
            {'expires_at': '2020-01-01T00:00:00+00:00'})
        db.commit()
    assert sink_client.post('/api/v1/auth/email-verification/confirm',
                            json={'token': token}, headers=HEADERS).status_code == 400


def test_a_verified_address_stops_asking(sink_client, sink):
    register(sink_client)
    sink_client.post('/api/v1/auth/email-verification/confirm',
                     json={'token': verification_token(sink)}, headers=HEADERS)
    again = sink_client.post('/api/v1/auth/email-verification/request', headers=HEADERS)
    assert again.status_code == 202
    assert again.json()['status'] == 'already_verified'


def test_verification_requires_a_session(sink_client):
    assert sink_client.post('/api/v1/auth/email-verification/request',
                            headers=HEADERS).status_code == 401


def test_verification_is_audited(sink_client, sink):
    register(sink_client)
    sink_client.post('/api/v1/auth/email-verification/confirm',
                     json={'token': verification_token(sink)}, headers=HEADERS)
    actions = {event['action'] for event in sink_client.get('/api/v1/audit').json()['events']}
    assert {'auth.email_verification_requested', 'auth.email_verified'} <= actions


def test_no_verification_is_promised_when_no_transport_exists(client):
    """The default app has no transport; registration must still succeed (P03)."""
    account = register(client)
    assert account['email_verified'] is False
    assert client.get('/api/v1/config').json()['mail_delivery_configured'] is False
    response = client.post('/api/v1/auth/email-verification/request', headers=HEADERS)
    assert response.status_code == 202
    assert response.json()['delivery_configured'] is False


# --- Deleting a workspace -------------------------------------------------------------
#
# The pilot promises a person can take their data out and then remove it. Deletion is
# destructive and irreversible, so it is gated on the password *and* a typed phrase, and
# it must leave nothing of the workspace behind in any table.

DELETE_URL = '/api/v1/auth/account'


def delete_account(client, password=PASSWORD, confirmation='DELETE Test workspace'):
    return client.request('DELETE', DELETE_URL, headers=HEADERS,
                          json={'password': password, 'confirmation': confirmation})


def test_deleting_a_workspace_requires_the_password(client, owner):
    assert delete_account(client, password='not-the-right-password').status_code == 403
    assert client.get('/api/v1/auth/me').status_code == 200


def test_deleting_a_workspace_requires_the_typed_phrase(client, owner):
    assert delete_account(client, confirmation='DELETE something else').status_code == 422
    assert client.get('/api/v1/auth/me').status_code == 200


def test_deleting_a_workspace_requires_a_session(client):
    assert delete_account(client).status_code == 401


def test_deletion_removes_every_row_the_workspace_owned(sink_client, sink, sink_app):
    """Nothing may survive in any table — including the tables deletion does not name.

    The sink app is used so registration really does mint a recovery credential: on the
    default app no token exists, and the recovery-token assertion would pass vacuously.
    """
    owner = register(sink_client)
    created = sink_client.post('/api/v1/xray', json={'input': AMAZON},
                               headers={**HEADERS, 'Idempotency-Key': 'delete-1'})
    assert created.status_code == 202, created.text
    ask(sink_client)
    # This creates a user-id keyed window, which deletion must not leave behind.
    assert sink_client.post('/api/v1/auth/email-verification/request',
                            headers=HEADERS).status_code == 202
    with sink_app.state.database.session() as db:
        # Simulate an unexpired account bucket left by the release before keyed HMACs.
        db.add(RateBucket(key=f'login-account:{token_hash("owner@example.com")}:legacy',
                          count=1, expires_at='2999-01-01T00:00:00+00:00'))
        db.commit()
        assert db.query(Record).filter_by(workspace_id=owner['workspace_id']).count() > 0
        assert db.query(Audit).filter_by(workspace_id=owner['workspace_id']).count() > 0
        assert db.query(RecoveryToken).filter_by(user_id=owner['id']).count() > 0
        assert db.query(RateBucket).filter(RateBucket.key.contains(owner['id'])).count() > 0
    assert delete_account(sink_client).status_code == 200
    with sink_app.state.database.session() as db:
        assert db.query(User).filter_by(id=owner['id']).count() == 0
        assert db.query(Workspace).filter_by(id=owner['workspace_id']).count() == 0
        assert db.query(Record).filter_by(workspace_id=owner['workspace_id']).count() == 0
        assert db.query(Audit).filter_by(workspace_id=owner['workspace_id']).count() == 0
        assert db.query(Session).filter_by(user_id=owner['id']).count() == 0
        assert db.query(RecoveryToken).filter_by(user_id=owner['id']).count() == 0
        assert db.query(RateBucket).filter(RateBucket.key.contains(owner['id'])).count() == 0
        assert db.query(RateBucket).filter(
            RateBucket.key.contains(token_hash('owner@example.com'))).count() == 0
    # The session it was holding is gone, not merely uncookied.
    assert sink_client.get('/api/v1/auth/me').status_code == 401


def test_deletion_frees_the_address_to_register_again(client, owner):
    assert delete_account(client).status_code == 200
    again = client.post('/api/v1/auth/register',
                        json={'email': owner['email'], 'password': PASSWORD, 'name': 'Test workspace'},
                        headers=HEADERS)
    assert again.status_code == 201, again.text
    assert again.json()['workspace_id'] != owner['workspace_id']


def test_deletion_does_not_touch_another_workspace(client, owner, second_client, stranger):
    """The blast radius is exactly one workspace (tenant isolation, T01)."""
    kept = second_client.post('/api/v1/xray', json={'input': AMAZON},
                              headers={**HEADERS, 'Idempotency-Key': 'keep-1'})
    assert kept.status_code == 202, kept.text
    before = second_client.get('/api/v1/products').json()['total']
    audited = second_client.get('/api/v1/audit').json()['total']
    assert before > 0 and audited > 0, 'the neighbour must own rows for this to prove anything'
    assert delete_account(client).status_code == 200
    assert second_client.get('/api/v1/auth/me').status_code == 200
    assert second_client.get('/api/v1/products').json()['total'] == before
    assert second_client.get('/api/v1/audit').json()['total'] == audited


def test_a_shared_workspace_is_refused_rather_than_half_deleted(client, owner, app):
    """An active member must be explicitly removed before shared data is erased."""
    with app.state.database.session() as db:
        db.add(User(id='second-member', email='colleague@example.com',
                    workspace_id=owner['workspace_id'], name='Colleague',
                    password_hash='x', role='analyst'))
        db.commit()
    assert delete_account(client).status_code == 409
    with app.state.database.session() as db:
        assert db.query(Workspace).filter_by(id=owner['workspace_id']).count() == 1
        assert db.query(User).filter_by(id=owner['id']).count() == 1
