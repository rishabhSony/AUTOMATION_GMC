#!/bin/sh
# Runs once, on the first start of an empty Postgres volume (docker-entrypoint-initdb.d).
# The API and web connect as a NON-superuser app role that owns the schema: superusers
# bypass row-level security, and the migrations FORCE RLS on the owner (Doc 05 §3).
set -eu
: "${APP_DB_USER:=quotepulse_app}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set app_user="$APP_DB_USER" --set app_password="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')\gexec
SELECT format('GRANT CREATE ON DATABASE %I TO %I', current_database(), :'app_user')\gexec
SELECT format('ALTER SCHEMA public OWNER TO %I', :'app_user')\gexec
SQL
