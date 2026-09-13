"""One-off schema bootstrap.

The app only calls Database.create() outside production, and the repository ships no
alembic revisions, so the production schema is created once from the same metadata.
Re-running is safe: create_all() skips tables that already exist.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import Database  # noqa: E402

url = os.environ['DATABASE_URL']
database = Database(url)
database.create()
with database.session() as db:
    from sqlalchemy import text
    tables = [r[0] for r in db.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))]
print('tables:', ', '.join(tables))
