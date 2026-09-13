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
#   TRENDSELL_BACKUP_S3_URI  optional private S3 destination, for example
#                            s3://company-backups/trendsell. When set, both the dump and
#                            its SHA-256 sidecar are copied after local verification.
#   TRENDSELL_BACKUP_S3_SSE  S3 server-side encryption mode (default AES256; use aws:kms
#                            only with a bucket/key policy configured for this identity)
#
# The URL is never echoed. Run as a user that can read it and write the backup directory.
set -euo pipefail

url="${TRENDSELL_DATABASE_URL:-${DATABASE_URL:-}}"
dir="${TRENDSELL_BACKUP_DIR:-/var/backups/trendsell}"
keep="${TRENDSELL_BACKUP_KEEP:-14}"
s3_uri="${TRENDSELL_BACKUP_S3_URI:-}"
s3_sse="${TRENDSELL_BACKUP_S3_SSE:-AES256}"

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
if [ -n "$s3_uri" ]; then
  case "$s3_uri" in
    s3://?*) ;;
    *) echo "TRENDSELL_BACKUP_S3_URI must start with s3:// and name a bucket" >&2; exit 2 ;;
  esac
  case "$s3_sse" in
    AES256|aws:kms) ;;
    *) echo "TRENDSELL_BACKUP_S3_SSE must be AES256 or aws:kms" >&2; exit 2 ;;
  esac
  command -v aws >/dev/null || {
    echo "TRENDSELL_BACKUP_S3_URI is set but the aws command is unavailable" >&2
    exit 2
  }
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
(cd "$dir" && sha256sum "$(basename "$target")" > "$(basename "$target").sha256")
chmod 0600 "$target.sha256"
echo "wrote $target ($(du -h "$target" | cut -f1))"

# Retention is a local safety control and must still run when the offsite service is
# unavailable. Prune after a new verified local dump exists, but before an upload can
# fail the job. The new file is never old enough to match this window.
find "$dir" -maxdepth 1 -name 'trendsell-*.dump' -type f -mtime "+$keep" -print -delete
find "$dir" -maxdepth 1 -name 'trendsell-*.dump.sha256' -type f -mtime "+$keep" -print -delete

# A successful local dump is not an off-host recovery point. When an S3 destination is
# configured, failure to copy either object fails the one-shot so monitoring can alert.
# The database URL and AWS credentials are never passed on the command line or printed.
if [ -n "$s3_uri" ]; then
  remote="${s3_uri%/}/$(basename "$target")"
  aws s3 cp "$target" "$remote" --only-show-errors --sse "$s3_sse"
  aws s3 cp "$target.sha256" "$remote.sha256" --only-show-errors --sse "$s3_sse"
  echo "copied backup and checksum to the configured offsite destination"
fi
