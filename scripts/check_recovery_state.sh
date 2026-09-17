#!/usr/bin/env bash
# One monitoring entry point for recovery points and deletion-register replication.
# The monitor identity is deliberately read-only in S3.  The separate sync unit owns the
# PUT path, so this check observes its most recent result instead of trying to upload.
set -euo pipefail
repository=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
"$repository/scripts/check_backup.sh"
sync_timer="${TRENDSELL_DELETION_SYNC_TIMER:-trendsell-deletion-register-sync.timer}"
sync_service="${TRENDSELL_DELETION_SYNC_SERVICE:-trendsell-deletion-register-sync.service}"
if ! systemctl is-active --quiet "$sync_timer"; then
    echo "deletion-register sync timer is not active: $sync_timer" >&2
    exit 1
fi
sync_result=$(systemctl show "$sync_service" --property=Result --value)
sync_started=$(systemctl show "$sync_service" \
    --property=ExecMainStartTimestampMonotonic --value)
if [[ "$sync_result" != success || -z "$sync_started" || "$sync_started" == 0 ]]; then
    echo "deletion-register sync has no successful completed run: $sync_service" >&2
    exit 1
fi
echo 'PASS: deletion-register sync timer is active and its latest run succeeded'
