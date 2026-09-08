import hashlib
import re
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from .db import RateBucket

# Password hashing moved to app/passwords.py, which carries its own algorithm and
# parameters so they can be raised without locking anyone out (action plan P02).
from .passwords import dummy_verify, hash_password, verify_password  # noqa: F401

def check_password(password, stored):
    """Kept for callers that only need the boolean. Prefer verify_password()."""
    return verify_password(password, stored)[0]

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def consume(db, key, limit):
    # Atomic counter across API processes. A nested transaction handles first-use races.
    try:
        with db.begin_nested():
            db.add(RateBucket(key=key, count=0))
            db.flush()
    except IntegrityError:
        pass
    result = db.execute(update(RateBucket).where(RateBucket.key == key, RateBucket.count < limit).values(count=RateBucket.count + 1))
    if not result.rowcount:
        raise HTTPException(429, 'Rate limit reached. Try again after this window.')
    db.commit()

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
