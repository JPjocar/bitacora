-- Run with the migration/owner account, then set a generated password using \password.
-- Adjust database/schema and use a dedicated runtime account without administrative rights.
CREATE ROLE bitacora_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE bitacora TO bitacora_runtime;
GRANT USAGE ON SCHEMA public TO bitacora_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bitacora_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bitacora_runtime;
-- Execute as the owner of future migration-created objects as well.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bitacora_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO bitacora_runtime;
