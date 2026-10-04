"""Server-side search, keyset pagination and complete exports (action plan T05).

Review finding 3: the products endpoint read the newest 200 rows and then filtered in
Python. Past 200 products the oldest one vanished from the list, from search, from the
product selector and from the workspace export, while its direct URL still returned 200.

Two rules follow from that, and both are implemented here:

* **Search runs in the database, before the page is cut.** A term the caller typed is
  matched against the stored payload by the engine, so a match on record 900 is found.
* **A page boundary is a record, not an offset.** The cursor carries the last row's
  ``(created_at, id)``. `id` is the tie-breaker, so rows created in the same instant
  cannot be skipped or repeated when a page is fetched twice.

Exports do not paginate at all — they stream every authorised record — so a complete
export can be reconciled against `total` from the same list endpoint.
"""
import base64
import json

from fastapi import HTTPException
from sqlalchemy import and_, func, or_

from .db import Record

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def encode_cursor(row):
    return base64.urlsafe_b64encode(json.dumps([row.created_at, row.id]).encode()).decode()


def decode_cursor(cursor):
    try:
        created_at, record_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if not isinstance(created_at, str) or not isinstance(record_id, str):
            raise ValueError
        return created_at, record_id
    except Exception:
        raise HTTPException(422, 'Page cursor is not valid. Start from the first page.')


def searched(query, term, fields):
    """Filter on JSON payload fields inside the database, case-insensitively.

    `Record.payload[field].as_string()` compiles to `JSON_EXTRACT` on SQLite and `->>`
    on PostgreSQL, so one expression covers both engines.
    """
    term = (term or '').strip()
    if not term:
        return query
    pattern = f'%{term.lower()}%'
    return query.filter(or_(*[func.lower(Record.payload[field].as_string()).like(pattern) for field in fields]))


def paginate(query, limit=None, cursor=None):
    """One page of `query`, newest first, plus the total and the next cursor.

    `total` counts every row the filter matched, not the page, so a caller can tell how
    much is still unread and reconcile a complete export against it.
    """
    limit = DEFAULT_LIMIT if limit is None else limit
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(422, f'Page size must be between 1 and {MAX_LIMIT}.')
    total = query.order_by(None).count()
    page = query.order_by(Record.created_at.desc(), Record.id.desc())
    if cursor:
        created_at, record_id = decode_cursor(cursor)
        page = page.filter(or_(Record.created_at < created_at,
                               and_(Record.created_at == created_at, Record.id < record_id)))
    rows = page.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return rows, {'total': total, 'limit': limit,
                  'next_cursor': encode_cursor(rows[-1]) if has_more and rows else None}
