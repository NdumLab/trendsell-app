#!/usr/bin/env bash
# Verify, migrate and atomically activate one exact CI artifact. This script changes its
# configured target installation; it is not run by CI and requires an explicit approval
# latch. A failed readiness check switches back to the recorded previous application.
set -euo pipefail

archive="${1:-}"
expected_commit="${2:-}"
release_root="${TRENDSELL_RELEASE_ROOT:-/opt/trendsell/releases}"
current_link="${TRENDSELL_CURRENT_LINK:-/opt/trendsell/current}"
previous_link="${TRENDSELL_PREVIOUS_LINK:-/opt/trendsell/previous}"
python_bin="${TRENDSELL_PYTHON:-/opt/trendsell/venv/bin/python}"
migration_url="${TRENDSELL_MIGRATION_DATABASE_URL:-}"
runtime_url="${TRENDSELL_RUNTIME_DATABASE_URL:-}"
ready_url="${TRENDSELL_READY_URL:-http://127.0.0.1:8021/api/ready}"

if [[ -z "$archive" || -z "$expected_commit" ]]; then
    echo "usage: $0 <artifact.tar.gz> <full-commit-sha>" >&2; exit 2
fi
if [[ "${TRENDSELL_APPROVE_DEPLOY:-}" != "$expected_commit" ]]; then
    echo 'refusing deployment: TRENDSELL_APPROVE_DEPLOY must equal the exact commit' >&2; exit 2
fi
if [[ -z "$migration_url" || -z "$runtime_url" ]]; then
    echo 'separate TRENDSELL_MIGRATION_DATABASE_URL and TRENDSELL_RUNTIME_DATABASE_URL are required' >&2
    exit 2
fi
if [[ "$migration_url" == "$runtime_url" ]]; then
    echo 'runtime and migration database URLs must be different' >&2; exit 2
fi
if [[ "${TRENDSELL_BACKUP_VERIFIED:-}" != yes ]]; then
    echo 'refusing deployment until the pre-release backup/restore is recorded' >&2; exit 2
fi

service="${TRENDSELL_SERVICE:-trendsell}"

# The installed service must actually load what this script activates, and must run
# migrations under the interpreter it serves from. A host installed outside this layout
# otherwise passes every latch above, migrates the database, switches links nothing reads,
# restarts onto unchanged code and reports success. Checked against the running unit
# rather than a documented assumption.
if systemctl list-unit-files "$service.service" >/dev/null 2>&1; then
    unit_dir="$(systemctl show "$service" --property=WorkingDirectory --value 2>/dev/null || true)"
    if [[ -n "$unit_dir" && "$unit_dir" != "$current_link" && "$unit_dir" != "$current_link"/* ]]; then
        echo "refusing deployment: $service loads $unit_dir, which is not under $current_link" >&2
        echo 'the installed layout does not match this script; activation would not change the running code' >&2
        exit 2
    fi
    unit_exec="$(systemctl show "$service" --property=ExecStart --value 2>/dev/null \
        | sed -n 's/.*path=\([^ ]*\).*/\1/p' | head -n 1)"
    if [[ -n "$unit_exec" && "${unit_exec%/*}" != "${python_bin%/*}" ]]; then
        echo "refusing deployment: $service runs ${unit_exec%/*} but migrations would use ${python_bin%/*}" >&2
        echo 'the service and its migrations must share one interpreter environment' >&2
        exit 2
    fi
fi

manager="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/release_manager.py"
stage_json="$($python_bin "$manager" stage --archive "$archive" \
    --expected-commit "$expected_commit" --release-root "$release_root")"
release="$($python_bin -c 'import json,sys; print(json.load(sys.stdin)["release"])' <<<"$stage_json")"

(cd "$release/backend" && "$python_bin" -m app.migrate preflight --url "$migration_url")
(cd "$release/backend" && "$python_bin" -m app.migrate upgrade --url "$migration_url")
(cd "$release/backend" && "$python_bin" -m app.migrate check --url "$migration_url")
# Check privileges against the post-migration model set. Running this before upgrade would
# incorrectly reject a legitimate candidate whose migration creates a new table.
TRENDSELL_RUNTIME_DATABASE_URL="$runtime_url" \
TRENDSELL_MIGRATION_DATABASE_URL="$migration_url" \
    "$python_bin" "$release/scripts/check_postgres_privileges.py"

"$python_bin" "$manager" activate --release "$release" \
    --current "$current_link" --previous "$previous_link"
systemctl restart trendsell

ready=false
for _attempt in {1..12}; do
    if curl --fail --silent --show-error "$ready_url" >/dev/null; then ready=true; break; fi
    sleep 5
done
if [[ "$ready" != true ]]; then
    echo 'candidate failed readiness; switching back to the previous application' >&2
    "$python_bin" "$manager" rollback --current "$current_link" --previous "$previous_link"
    systemctl restart trendsell
    curl --fail --silent --show-error "$ready_url" >/dev/null || {
        echo 'rollback target also failed readiness; escalate without in-place schema downgrade' >&2
        exit 1
    }
    exit 1
fi
echo "deployed exact artifact $expected_commit; previous application remains at $previous_link"
