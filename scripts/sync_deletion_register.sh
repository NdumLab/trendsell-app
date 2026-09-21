#!/usr/bin/env bash
# Copy immutable deletion intents outside the database/host and verify service-side SHA-256.
set -euo pipefail

repository=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
register_dir="${TRENDSELL_DELETION_REGISTER_DIR:-/var/lib/trendsell/deletions}"
s3_uri="${TRENDSELL_DELETION_S3_URI:-}"
s3_sse="${TRENDSELL_BACKUP_S3_SSE:-AES256}"
python_bin="${TRENDSELL_PYTHON:-python3}"

case "$s3_uri" in
  s3://*/*) ;;
  *) echo 'TRENDSELL_DELETION_S3_URI must name a private bucket and prefix' >&2; exit 2 ;;
esac
case "$s3_sse" in
  AES256|aws:kms) ;;
  *) echo 'TRENDSELL_BACKUP_S3_SSE must be AES256 or aws:kms' >&2; exit 2 ;;
esac
for command in aws jq openssl stat; do
  command -v "$command" >/dev/null || { echo "required command is unavailable: $command" >&2; exit 2; }
done
"$python_bin" "$repository/scripts/verify_deletion_register.py" --register-dir "$register_dir"

remote="${s3_uri#s3://}"
bucket="${remote%%/*}"
prefix="${remote#*/}"
prefix="${prefix%/}"
if [[ -z "$bucket" || -z "$prefix" || "$bucket" == "$remote" ]]; then
  echo 'TRENDSELL_DELETION_S3_URI must name a non-empty bucket and prefix' >&2
  exit 2
fi
shopt -s nullglob
files=("$register_dir"/*.json "$register_dir"/*.json.sha256)
for file in "${files[@]}"; do
  name=$(basename "$file")
  key="$prefix/$name"
  size=$(stat -c %s "$file")
  digest=$(openssl dgst -sha256 -binary "$file" | openssl base64 -A)
  if ! head=$(aws s3api head-object --bucket "$bucket" --key "$key" \
       --checksum-mode ENABLED --output json 2>/dev/null); then
    # Conditional creation prevents a retry from replacing an immutable event even if
    # another sync won the race between HEAD and PUT.
    aws s3api put-object --bucket "$bucket" --key "$key" --body "$file" \
      --server-side-encryption "$s3_sse" --checksum-algorithm SHA256 \
      --if-none-match '*' >/dev/null
    head=$(aws s3api head-object --bucket "$bucket" --key "$key" \
      --checksum-mode ENABLED --output json)
  fi
  if ! jq -e --argjson size "$size" --arg sse "$s3_sse" --arg digest "$digest" \
      '.ContentLength == $size and .ServerSideEncryption == $sse and
       .ChecksumSHA256 == $digest' <<<"$head" >/dev/null; then
    echo "remote deletion-register object differs: $name" >&2
    exit 1
  fi
done
echo "PASS: ${#files[@]} deletion-register objects are verified off host"
