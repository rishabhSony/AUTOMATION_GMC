#!/usr/bin/env bash
# One-command local startup: FastAPI on :8000 and Next.js on :3000.
#
#   ./scripts/dev.sh          offline mock mode (no Clerk / OpenAI keys needed)
#   ./scripts/dev.sh --live   use the Clerk / OpenAI settings in the env files as-is
#
# Prerequisites: PostgreSQL on localhost:5432 with quotepulse_dev
# (psql -d postgres -f scripts/init_local_db.sql), Bun 1.x, uv, Python 3.11.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/apps/web"
API="$ROOT/services/backend"
MODE="mock"
[[ "${1:-}" == "--live" ]] && MODE="live"

info() { printf '\033[1;34m[dev]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[dev]\033[0m %s\n' "$*" >&2; exit 1; }

# 1. PostgreSQL
if command -v pg_isready >/dev/null 2>&1; then
  pg_isready -h localhost -p 5432 -q || fail "PostgreSQL is not responding on localhost:5432. Start it (e.g. brew services start postgresql@16)."
else
  (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null || fail "Nothing is listening on localhost:5432. Start PostgreSQL."
fi
info "PostgreSQL is up on :5432"

# 2. Env files from the committed templates
for pair in "$WEB/.env.example:$WEB/.env.local" "$API/.env.example:$API/.env.backend.local"; do
  src="${pair%%:*}" dst="${pair##*:}"
  if [[ ! -f "$dst" ]]; then
    cp "$src" "$dst"
    info "Created ${dst#"$ROOT"/} from ${src#"$ROOT"/}"
  fi
done

# 3. Offline mock mode: exported variables override the env files for these processes only.
if [[ "$MODE" == "mock" ]]; then
  export NEXT_PUBLIC_ENABLE_DEV_MOCK_AUTH="true"   # web: no Clerk, Dev role switcher
  export ENVIRONMENT="development"                  # API: dev mock auth needs development
  export ENABLE_DEV_MOCK_AUTH="true"                # API: trust X-Dev-User-Id headers
  info "Mode: MOCK (dev auth headers; mock AI unless OPENAI_API_KEY is set and USE_MOCK_AI=false)"
else
  info "Mode: LIVE (Clerk / OpenAI settings from the env files)"
fi

# 4. Dependencies (first run only)
if [[ ! -d "$WEB/node_modules" ]]; then
  info "Installing web dependencies (bun install)…"
  (cd "$WEB" && bun install)
fi
if [[ ! -x "$API/.venv/bin/python" ]]; then
  info "Creating the backend venv (uv, Python 3.11)…"
  (cd "$API" && uv venv .venv --python 3.11 && uv pip install --python .venv/bin/python -r requirements-dev.txt)
fi

# 5. Migrations (incl. 0004_ops_analyst_rls) and the idempotent seed (users for the role switcher)
info "Applying migrations…"
(cd "$WEB" && bun run db:migrate)
info "Seeding role users and the sub-limit registry…"
(cd "$WEB" && bun run seed)

# 6. Both servers; Ctrl+C (or either one exiting) stops both.
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  info "Stopping servers…"
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do
    pkill -TERM -P "$pid" 2>/dev/null || true   # children (next dev under bun, uvicorn reloader)
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd "$API" && exec .venv/bin/uvicorn app.main:app --reload --port 8000) &
PIDS+=($!)
(cd "$WEB" && exec bun run dev --port 3000) &
PIDS+=($!)

info "API  → http://localhost:8000/api/v1/health   (docs: /docs)"
info "Web  → http://localhost:3000"
info "Smoke test (another terminal): services/backend/.venv/bin/python scripts/smoke_test.py"
info "Press Ctrl+C to stop both."

# Exit when either server stops (`wait -n` needs bash 4.3+; macOS /bin/bash 3.2 waits for all).
set +e
if (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 3) )); then
  wait -n
else
  wait
fi
