#!/usr/bin/env bash
# Apply the reviewed runtime/migration split to one dedicated TrendSell database.
#
# Required environment:
#   TRENDSELL_ADMIN_URL       administrator URL pointing at the target database
#   TRENDSELL_DATABASE_NAME   exact target database name
#   TRENDSELL_RUNTIME_ROLE    already-provisioned LOGIN role used only by the web service
#   TRENDSELL_MIGRATION_ROLE  already-provisioned LOGIN role used by release migrations
#   TRENDSELL_APPLY_ROLE_GRANTS=yes
#
# Role creation and password rotation remain provider/administrator operations. Keeping
# them out of this script prevents credentials from entering argv, SQL logs, or shell
# history. Run check_postgres_privileges.py with each role's secret URL afterward.
set -euo pipefail

repository=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
admin_url="${TRENDSELL_ADMIN_URL:-}"
database_name="${TRENDSELL_DATABASE_NAME:-}"
runtime_role="${TRENDSELL_RUNTIME_ROLE:-}"
migration_role="${TRENDSELL_MIGRATION_ROLE:-}"

if [[ -z "$admin_url" ]]; then
    echo 'TRENDSELL_ADMIN_URL is required' >&2
    exit 2
fi
for value_name in database_name runtime_role migration_role; do
    value="${!value_name}"
    if [[ ! "$value" =~ ^[a-z_][a-z0-9_]{0,62}$ ]]; then
        echo "$value_name must be a lowercase PostgreSQL identifier" >&2
        exit 2
    fi
done
if [[ "$runtime_role" == "$migration_role" ]]; then
    echo 'runtime and migration roles must be different' >&2
    exit 2
fi
if [[ "${TRENDSELL_APPLY_ROLE_GRANTS:-}" != yes ]]; then
    echo 'refusing to change grants without TRENDSELL_APPLY_ROLE_GRANTS=yes' >&2
    exit 2
fi

admin_url="${admin_url/postgresql+psycopg:\/\//postgresql://}"
psql "$admin_url" --no-psqlrc --set=database_name="$database_name" \
    --set=runtime_role="$runtime_role" --set=migration_role="$migration_role" \
    --file="$repository/scripts/configure_postgres_roles.sql"
echo 'applied TrendSell runtime/migration grants; run check_postgres_privileges.py next'
