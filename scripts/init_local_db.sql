-- One-time local database setup (run as a PostgreSQL superuser; idempotent):
--   psql -d postgres -f scripts/init_local_db.sql
-- Creates the app role and database used by DATABASE_URL in the .env.example templates.
-- Local development credentials only; never reuse them on a shared server.

SELECT 'CREATE ROLE quotepulse_app LOGIN PASSWORD ''dev_password_123'''
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quotepulse_app')\gexec

SELECT 'CREATE DATABASE quotepulse_dev OWNER quotepulse_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'quotepulse_dev')\gexec

-- drizzle-kit migrate creates its `drizzle` journal schema.
GRANT CREATE ON DATABASE quotepulse_dev TO quotepulse_app;

\connect quotepulse_dev
-- The app role owns `public`, so it owns the tables and FORCE RLS applies to it.
ALTER SCHEMA public OWNER TO quotepulse_app;
