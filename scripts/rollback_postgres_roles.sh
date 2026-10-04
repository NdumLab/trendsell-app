#!/usr/bin/env bash
# Emergency availability rollback for configure_postgres_roles.sh. See the SQL warning:
# this reintroduces broad runtime rights and must be removed after the incident.
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
if [[ "${TRENDSELL_ROLLBACK_ROLE_GRANTS:-}" != yes ]]; then
    echo 'refusing broad rollback without TRENDSELL_ROLLBACK_ROLE_GRANTS=yes' >&2
    exit 2
fi

admin_url="${admin_url/postgresql+psycopg:\/\//postgresql://}"
psql "$admin_url" --no-psqlrc --set=database_name="$database_name" \
    --set=runtime_role="$runtime_role" --set=migration_role="$migration_role" \
    --file="$repository/scripts/rollback_postgres_roles.sql"
echo 'WARNING: broad runtime database rights restored for availability; reapply the split'
