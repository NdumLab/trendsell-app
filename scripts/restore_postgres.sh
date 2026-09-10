#!/usr/bin/env bash
# Restore a TrendSell dump into a SEPARATE database (action plan P06).
#
#   scripts/restore_postgres.sh <dump-file> <new-database-name>
#
#   TRENDSELL_ADMIN_URL   postgresql://... connection to the server, pointing at a
#                         database the restoring role may connect to (e.g. postgres)
#
# The target database must not already exist. This script never drops or writes to an
# existing database, so it cannot be used to overwrite the live one by accident. Verify the
# result with scripts/verify_restore.py before pointing any service at it.
set -euo pipefail

dump="${1:-}"
target="${2:-}"
admin="${TRENDSELL_ADMIN_URL:-}"

if [ -z "$dump" ] || [ -z "$target" ]; then
  echo "usage: $0 <dump-file> <new-database-name>" >&2
  exit 2
fi
if [ -z "$admin" ]; then
  echo "TRENDSELL_ADMIN_URL is not set" >&2
  exit 2
fi
if [ ! -r "$dump" ]; then
  echo "cannot read dump: $dump" >&2
  exit 2
fi
case "$target" in
  *[!a-zA-Z0-9_]*) echo "database name must be alphanumeric or underscore: $target" >&2; exit 2 ;;
esac

admin="${admin/postgresql+psycopg:\/\//postgresql://}"

exists="$(psql "$admin" -tAc "SELECT 1 FROM pg_database WHERE datname = '$target'")"
if [ -n "$exists" ]; then
  echo "database $target already exists; refusing to restore over it" >&2
  exit 1
fi

psql "$admin" -c "CREATE DATABASE \"$target\""

# Derive the target URL by swapping only the database path. Preserve libpq query options
# such as sslmode; appending the name after an existing query silently produces a bad URL.
if [[ "$admin" == *\?* ]]; then
  options="?${admin#*\?}"
  admin_without_options="${admin%%\?*}"
else
  options=""
  admin_without_options="$admin"
fi
restore_url="${admin_without_options%/*}/$target$options"
pg_restore --dbname="$restore_url" --no-owner --no-privileges --exit-on-error "$dump"

echo "restored $dump into $target"
echo "verify it before use:  python scripts/verify_restore.py --url '<url for $target>'"
