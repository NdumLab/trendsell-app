\set ON_ERROR_STOP on

-- Applied by configure_postgres_roles.sh after it validates all identifiers and confirms
-- that the administrator URL points at database_name.  Roles are provisioned separately
-- so their passwords never enter this repository, SQL input, or captured command output.

SELECT set_config('trendsell.database_name', :'database_name', false),
       set_config('trendsell.runtime_role', :'runtime_role', false),
       set_config('trendsell.migration_role', :'migration_role', false);
DO $$
BEGIN
    IF current_database() <> current_setting('trendsell.database_name') THEN
        RAISE EXCEPTION 'administrator URL points at %, expected %', current_database(),
            current_setting('trendsell.database_name');
    END IF;
    IF current_setting('trendsell.runtime_role') = current_setting('trendsell.migration_role') THEN
        RAISE EXCEPTION 'runtime and migration roles must be separate';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles
                   WHERE rolname = current_setting('trendsell.runtime_role')) THEN
        RAISE EXCEPTION 'runtime role does not exist';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles
                   WHERE rolname = current_setting('trendsell.migration_role')) THEN
        RAISE EXCEPTION 'migration role does not exist';
    END IF;
END $$;

-- A dedicated TrendSell database does not need PUBLIC defaults. Named operational roles
-- retain access only when an administrator grants it deliberately.
REVOKE CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name" FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

GRANT CONNECT ON DATABASE :"database_name" TO :"runtime_role", :"migration_role";
GRANT USAGE ON SCHEMA public TO :"runtime_role";
GRANT USAGE, CREATE ON SCHEMA public TO :"migration_role";
ALTER SCHEMA public OWNER TO :"migration_role";

-- Existing objects must be owned by the migration identity. Object-level grants cannot
-- confer ALTER/DROP, and giving the web role membership in the owner role would defeat
-- the split. psql's gexec quotes every catalog identifier before executing it.
SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'migration_role')
FROM pg_tables WHERE schemaname = 'public'
\gexec
SELECT format('ALTER SEQUENCE %I.%I OWNER TO %I', sequence_schema, sequence_name,
              :'migration_role')
FROM information_schema.sequences WHERE sequence_schema = 'public'
\gexec
SELECT format('ALTER VIEW %I.%I OWNER TO %I', schemaname, viewname, :'migration_role')
FROM pg_views WHERE schemaname = 'public'
\gexec

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM :"runtime_role";
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"runtime_role";
GRANT SELECT, USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";
SELECT format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
              'ON TABLE public.alembic_version FROM %I', :'runtime_role')
WHERE to_regclass('public.alembic_version') IS NOT NULL
\gexec

-- Alembic-created objects inherit the same runtime DML grants. This statement must be
-- executed by an administrator allowed to alter defaults for migration_role.
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
    GRANT SELECT, USAGE, UPDATE ON SEQUENCES TO :"runtime_role";

-- Remove historical broad privileges and any emergency membership left by rollback.
REVOKE CREATE, TEMPORARY ON DATABASE :"database_name" FROM :"runtime_role";
REVOKE CREATE ON SCHEMA public FROM :"runtime_role";
SELECT format('REVOKE %I FROM %I', :'migration_role', :'runtime_role')
WHERE pg_has_role(:'runtime_role', :'migration_role', 'MEMBER')
\gexec
