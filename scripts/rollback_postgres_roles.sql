\set ON_ERROR_STOP on

-- Availability-only rollback for a failed role split. This deliberately restores the
-- old broad single-role behavior by allowing the runtime identity to assume the migration
-- owner role. It is a temporary rollback, not an acceptable steady state.
SELECT set_config('trendsell.database_name', :'database_name', false);
DO $$
BEGIN
    IF current_database() <> current_setting('trendsell.database_name') THEN
        RAISE EXCEPTION 'administrator URL points at a different database';
    END IF;
END $$;
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name" TO :"runtime_role";
GRANT USAGE, CREATE ON SCHEMA public TO :"runtime_role";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :"runtime_role";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";
GRANT :"migration_role" TO :"runtime_role";
