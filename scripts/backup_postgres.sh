#!/usr/bin/env bash
# Back up the TrendSell PostgreSQL database (action plan P06).
#
# Writes a compressed custom-format dump, which pg_restore can load selectively and which
# restore_postgres.sh expects. Prunes dumps older than the retention window.
#
#   TRENDSELL_DATABASE_URL   postgresql://... connection string (uses DATABASE_URL when
#                            unset, so the production service env file can be reused)
#   TRENDSELL_BACKUP_DIR     destination directory (default /var/backups/trendsell)
#   TRENDSELL_BACKUP_KEEP    days of dumps to keep (default 14)
#
# The URL is never echoed. Run as a user that can read it and write the backup directory.
set -euo pipefail

url="${TRENDSELL_DATABASE_URL:-${DATABASE_URL:-}}"
dir="${TRENDSELL_BACKUP_DIR:-/var/backups/trendsell}"
keep="${TRENDSELL_BACKUP_KEEP:-14}"

if [ -z "$url" ]; then
  echo "Neither TRENDSELL_DATABASE_URL nor DATABASE_URL is set" >&2
  exit 2
fi
case "$keep" in
  ''|*[!0-9]*) echo "TRENDSELL_BACKUP_KEEP must be a whole number of days" >&2; exit 2 ;;
esac
if [ "$keep" -lt 1 ] || [ "$keep" -gt 3650 ]; then
  echo "TRENDSELL_BACKUP_KEEP must be between 1 and 3650 days" >&2
  exit 2
fi

# SQLAlchemy-style URLs carry a driver suffix that libpq does not understand.
url="${url/postgresql+psycopg:\/\//postgresql://}"

mkdir -p "$dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
partial="$(mktemp "$dir/.trendsell-$stamp.XXXXXX.partial")"
partial_stem="${partial%.partial}"
unique="${partial_stem##*.}"
target="$dir/trendsell-$stamp-$unique.dump"
cleanup() { rm -f "$partial"; }
trap cleanup EXIT

pg_dump --format=custom --compress=9 --no-owner --no-privileges --file="$partial" "$url"

# A dump that cannot be listed is not a backup. Fail loudly rather than keeping it.
if ! pg_restore --list "$partial" >/dev/null; then
  echo "new dump is unreadable; removing the partial file" >&2
  exit 1
fi

chmod 0600 "$partial"
mv "$partial" "$target"
trap - EXIT
echo "wrote $target ($(du -h "$target" | cut -f1))"

find "$dir" -maxdepth 1 -name 'trendsell-*.dump' -type f -mtime "+$keep" -print -delete
