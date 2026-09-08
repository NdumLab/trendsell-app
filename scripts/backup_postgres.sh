#!/usr/bin/env bash
# Back up the TrendSell PostgreSQL database (action plan P06).
#
# Writes a compressed custom-format dump, which pg_restore can load selectively and which
# restore_postgres.sh expects. Prunes dumps older than the retention window.
#
#   TRENDSELL_DATABASE_URL   postgresql://... connection string (required)
#   TRENDSELL_BACKUP_DIR     destination directory (default /var/backups/trendsell)
#   TRENDSELL_BACKUP_KEEP    days of dumps to keep (default 14)
#
# The URL is never echoed. Run as a user that can read it and write the backup directory.
set -euo pipefail

url="${TRENDSELL_DATABASE_URL:-}"
dir="${TRENDSELL_BACKUP_DIR:-/var/backups/trendsell}"
keep="${TRENDSELL_BACKUP_KEEP:-14}"

if [ -z "$url" ]; then
  echo "TRENDSELL_DATABASE_URL is not set" >&2
  exit 2
fi

# SQLAlchemy-style URLs carry a driver suffix that libpq does not understand.
url="${url/postgresql+psycopg:\/\//postgresql://}"

mkdir -p "$dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$dir/trendsell-$stamp.dump"

pg_dump --format=custom --compress=9 --no-owner --no-privileges --file="$target" "$url"

# A dump that cannot be listed is not a backup. Fail loudly rather than keeping it.
if ! pg_restore --list "$target" >/dev/null; then
  echo "dump at $target is unreadable; removing it" >&2
  rm -f "$target"
  exit 1
fi

chmod 0600 "$target"
echo "wrote $target ($(du -h "$target" | cut -f1))"

find "$dir" -maxdepth 1 -name 'trendsell-*.dump' -type f -mtime "+$keep" -print -delete
