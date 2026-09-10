import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from .db import RateBucket, RecoveryToken, Session

#: Windows in this app are hourly or daily; a day plus a margin outlives all of them.
DEFAULT_BUCKET_TTL = 26 * 3600

# Password hashing moved to app/passwords.py, which carries its own algorithm and
# parameters so they can be raised without locking anyone out (action plan P02).
from .passwords import dummy_verify, hash_password, verify_password  # noqa: F401

def check_password(password, stored):
    """Kept for callers that only need the boolean. Prefer verify_password()."""
    return verify_password(password, stored)[0]

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def keyed_hash(value, secret):
    """A stable, non-enumerable digest for low-entropy rate-limit identifiers.

    Email and network addresses have small enough search spaces that plain SHA-256 is only
    obfuscation. A deployment-specific HMAC still lets every worker share one database
    bucket without leaving a value that can be recovered with an offline dictionary.
    """
    if not secret:
        raise ValueError('A rate-key secret is required')
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()

def window_end(seconds):
    """When the current bucket stops counting, so cleanup knows what is finished."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def consume(db, key, limit, ttl_seconds=DEFAULT_BUCKET_TTL, message=None):
    # Atomic counter across API processes. A nested transaction handles first-use races.
    try:
        with db.begin_nested():
            db.add(RateBucket(key=key, count=0, expires_at=window_end(ttl_seconds)))
            db.flush()
    except IntegrityError:
        pass
    result = db.execute(update(RateBucket).where(RateBucket.key == key, RateBucket.count < limit).values(count=RateBucket.count + 1))
    if not result.rowcount:
        raise HTTPException(429, message or 'Rate limit reached. Try again after this window.')
    db.commit()


def purge_expired(db, now=None):
    """Remove finished rate windows, dead sessions and expired recovery credentials.

    Only rows whose own expiry has passed are removed, so an active window keeps counting
    and a live session or recovery credential keeps working. Used recovery credentials stay
    until their original expiry so a replay can still be distinguished during that window.
    Returns what was removed, for the operational log.
    """
    moment = now or datetime.now(timezone.utc).isoformat()
    sessions = db.query(Session).filter(Session.expires_at <= moment).delete(synchronize_session=False)
    recovery_tokens = db.query(RecoveryToken).filter(
        RecoveryToken.expires_at <= moment).delete(synchronize_session=False)
    buckets = db.query(RateBucket).filter(RateBucket.expires_at.isnot(None),
                                          RateBucket.expires_at <= moment).delete(synchronize_session=False)
    db.commit()
    return {'sessions': sessions, 'recovery_tokens': recovery_tokens, 'rate_buckets': buckets}

def resolve_input(value):
    """Parse identifiers only. Never fetch a user-controlled URL or follow redirects."""
    value = value.strip()
    if re.fullmatch(r'[A-Za-z0-9]{10}', value):
        asin = value.upper()
    else:
        try:
            url = urlsplit(value)
            if url.scheme != 'https' or url.hostname not in {'amazon.com', 'www.amazon.com'} or url.username or url.password or url.port not in {None, 443}:
                raise ValueError()
            match = re.search(r'/(?:dp|gp/product)/([A-Za-z0-9]{10})(?:/|$)', url.path)
            if not match:
                raise ValueError()
            asin = match[1].upper()
        except (ValueError, AttributeError):
            raise HTTPException(422, 'Use a 10-character ASIN or an https://www.amazon.com/dp/ASIN product URL. Images, videos, short links and other markets are not supported yet.')
    return {'asin': asin, 'url': f'https://www.amazon.com/dp/{asin}', 'market': 'US'}
