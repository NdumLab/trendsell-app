#!/usr/bin/env bash
set -euo pipefail

# Build the exact tracked commit into a deterministic release archive. The archive is
# deliberately refused from a dirty checkout: a release artifact must never contain an
# ambiguous mixture of committed and workstation-only source.

repository=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-"$repository/release"}

for command_name in git npm tar gzip sha256sum mktemp; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "release build requires $command_name" >&2
        exit 2
    fi
done

cd "$repository"

if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code || \
   [[ -n $(git ls-files --others --exclude-standard) ]]; then
    echo "refusing to build a release artifact from a dirty checkout" >&2
    exit 2
fi

commit=$(git rev-parse --verify HEAD)
short_commit=${commit:0:12}
source_date_epoch=$(git show -s --format=%ct "$commit")
archive_name="trendsell-${short_commit}.tar.gz"

required_paths=(
    backend/app
    backend/migrations
    backend/alembic.ini
    backend/requirements.lock
    backend/server.py
    contracts
    deploy
    docs/PRIVACY_AND_PERMISSIONS.md
    docs/DEPENDENCY_LICENSES.md
    docs/PRODUCTION_READINESS.md
    docs/RUNBOOK.md
    frontend/package.json
    frontend/package-lock.json
    scripts/backup_postgres.sh
    scripts/build_release_artifact.sh
    scripts/check_backup.sh
    scripts/check_dependency_licenses.py
    scripts/check_postgres_privileges.py
    scripts/check_recovery_state.sh
    scripts/configure_postgres_roles.sh
    scripts/configure_postgres_roles.sql
    scripts/deploy_release.sh
    scripts/monitor_trendsell.py
    scripts/release_manager.py
    scripts/rollback_postgres_roles.sh
    scripts/rollback_postgres_roles.sql
    scripts/restore_postgres.sh
    scripts/replay_deletions.py
    scripts/scan_secrets.sh
    scripts/sync_deletion_register.sh
    scripts/verify_deletion_register.py
    scripts/verify_restore.py
)

for path in "${required_paths[@]}"; do
    if ! git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
        echo "required release path is not tracked: $path" >&2
        exit 2
    fi
done

# The lockfile-backed install is a separate CI step. This command always rebuilds the
# browser assets so a stale local dist directory can never enter the artifact.
npm --prefix frontend run build

temporary_dir=$(mktemp -d)
trap 'rm -rf -- "$temporary_dir"' EXIT
release_root="$temporary_dir/trendsell-${short_commit}"
mkdir -p "$release_root"

git archive --format=tar "$commit" "${required_paths[@]}" | tar -xf - -C "$release_root"
mkdir -p "$release_root/frontend"
cp -a frontend/dist "$release_root/frontend/dist"

printf '%s\n' \
    '{' \
    '  "schema": "trendsell-release/1",' \
    "  \"commit\": \"$commit\"," \
    "  \"source_date_epoch\": $source_date_epoch" \
    '}' > "$release_root/RELEASE.json"

# Normalize permissions because git-archive extraction and copied build output otherwise inherit
# the runner's umask. Restore executable bits only where the committed Git mode requires them.
find "$release_root" -type d -exec chmod 0755 {} +
find "$release_root" -type f -exec chmod 0644 {} +
while read -r mode _ _ path; do
    if [[ "$mode" == 100755 ]]; then
        chmod 0755 "$release_root/$path"
    fi
done < <(git ls-files -s -- "${required_paths[@]}")

# Normalize every timestamp and archive owner. gzip -n suppresses its own filename and timestamp
# header. Two builds of the same source and toolchain therefore have one digest across umasks.
find "$release_root" -exec touch -h -d "@$source_date_epoch" {} +

mkdir -p "$output_dir"
archive="$output_dir/$archive_name"
checksum="$archive.sha256"
if [[ -e "$archive" || -e "$checksum" ]]; then
    echo "refusing to overwrite existing release output: $archive" >&2
    exit 2
fi

tar --sort=name --format=gnu --mtime="@$source_date_epoch" \
    --owner=0 --group=0 --numeric-owner -C "$temporary_dir" \
    -cf - "trendsell-${short_commit}" | gzip -n > "$archive"
(
    cd "$output_dir"
    sha256sum "$archive_name" > "$archive_name.sha256"
)

echo "$archive"
echo "$checksum"
