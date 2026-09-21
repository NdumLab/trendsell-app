#!/usr/bin/env bash
# Fail unless the newest local TrendSell backup is recent, internally valid, and present
# with its checksum at the configured encrypted S3 destination.
set -euo pipefail

dir="${TRENDSELL_BACKUP_DIR:-/var/backups/trendsell}"
max_age_hours="${TRENDSELL_BACKUP_MAX_AGE_HOURS:-30}"
s3_uri="${TRENDSELL_BACKUP_S3_URI:-}"
s3_sse="${TRENDSELL_BACKUP_S3_SSE:-AES256}"

case "$max_age_hours" in
  ''|*[!0-9]*) echo "TRENDSELL_BACKUP_MAX_AGE_HOURS must be a positive whole number" >&2; exit 2 ;;
esac
if [ "$max_age_hours" -lt 1 ]; then
  echo "TRENDSELL_BACKUP_MAX_AGE_HOURS must be a positive whole number" >&2
  exit 2
fi
case "$s3_uri" in
  s3://*/*) ;;
  *) echo "TRENDSELL_BACKUP_S3_URI must name a bucket and prefix" >&2; exit 2 ;;
esac
for command in aws jq openssl pg_restore sha256sum; do
  command -v "$command" >/dev/null || { echo "required command is unavailable: $command" >&2; exit 2; }
done

latest="$(find "$dir" -maxdepth 1 -type f -name 'trendsell-*.dump' -printf '%T@ %p\n' \
  | sort -nr | awk 'NR == 1 { sub(/^[^ ]+ /, ""); print; exit }')"
if [ -z "$latest" ] || [ ! -r "$latest" ]; then
  echo "no readable TrendSell PostgreSQL backup exists" >&2
  exit 1
fi
sidecar="$latest.sha256"
if [ ! -r "$sidecar" ]; then
  echo "newest TrendSell backup has no readable checksum sidecar" >&2
  exit 1
fi

now_epoch="$(date +%s)"
modified_epoch="$(stat -c %Y "$latest")"
age_seconds=$((now_epoch - modified_epoch))
if [ "$age_seconds" -lt 0 ] || [ "$age_seconds" -gt $((max_age_hours * 3600)) ]; then
  echo "newest TrendSell backup is outside the ${max_age_hours}-hour freshness window" >&2
  exit 1
fi

latest_name="$(basename "$latest")"
if ! (cd "$dir" && sha256sum --check --status "$(basename "$sidecar")"); then
  echo "newest TrendSell backup failed SHA-256 verification" >&2
  exit 1
fi
if ! pg_restore --list "$latest" >/dev/null; then
  echo "newest TrendSell backup is not a readable PostgreSQL custom dump" >&2
  exit 1
fi

remote="${s3_uri#s3://}"
bucket="${remote%%/*}"
prefix="${remote#*/}"
prefix="${prefix%/}"
key="$prefix/$latest_name"

dump_head="$(aws s3api head-object --bucket "$bucket" --key "$key" \
  --checksum-mode ENABLED --output json)"
sidecar_head="$(aws s3api head-object --bucket "$bucket" --key "$key.sha256" \
  --checksum-mode ENABLED --output json)"
dump_size="$(stat -c %s "$latest")"
sidecar_size="$(stat -c %s "$sidecar")"
dump_checksum="$(openssl dgst -sha256 -binary "$latest" | openssl base64 -A)"
sidecar_checksum="$(openssl dgst -sha256 -binary "$sidecar" | openssl base64 -A)"
if ! jq -e --argjson size "$dump_size" --arg sse "$s3_sse" \
    --arg checksum "$dump_checksum" \
    '.ContentLength == $size and .ServerSideEncryption == $sse and
     .ChecksumSHA256 == $checksum' <<<"$dump_head" >/dev/null; then
  echo "offsite dump size, encryption or SHA-256 does not match the local backup" >&2
  exit 1
fi
if ! jq -e --argjson size "$sidecar_size" --arg sse "$s3_sse" \
    --arg checksum "$sidecar_checksum" \
    '.ContentLength == $size and .ServerSideEncryption == $sse and
     .ChecksumSHA256 == $checksum' <<<"$sidecar_head" >/dev/null; then
  echo "offsite sidecar size, encryption or SHA-256 does not match the local sidecar" >&2
  exit 1
fi

echo "PASS newest local and encrypted offsite TrendSell backup agree; age=$((age_seconds / 3600))h"
