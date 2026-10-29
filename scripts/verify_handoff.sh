#!/usr/bin/env bash
# Pre-flight check for a fresh clone (organization laptop). Read-only: it installs and
# changes nothing.
#
#   ./scripts/verify_handoff.sh
#
# Exit code 0 when the machine is ready for ./scripts/dev.sh, 1 otherwise.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILS=0
WARNS=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; WARNS=$((WARNS + 1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; FAILS=$((FAILS + 1)); }

# "3.11.4" >= "3.11" ?
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -n1)" = "$2" ]; }

echo "QuotePulse GMC · handoff verification"
echo
echo "Prerequisites"

if command -v bun >/dev/null 2>&1; then
  v="$(bun --version 2>/dev/null)"
  if [[ "$v" == 1.* ]]; then ok "bun $v"; else bad "bun $v found; Bun 1.x is required"; fi
else
  bad "bun not found (https://bun.sh); the frontend uses Bun only"
fi

PY_OK=0
if command -v python3 >/dev/null 2>&1; then
  v="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if version_ge "$v" "3.11"; then
    ok "python3 $v"
    PY_OK=1
  else
    warn "python3 $v is older than 3.11 (fine for scripts/smoke_test.py, which needs 3.9+)"
  fi
else
  bad "python3 not found"
fi
if command -v uv >/dev/null 2>&1; then
  ok "uv $(uv --version 2>/dev/null | awk '{print $2}') (creates the backend's Python 3.11 venv)"
elif [[ -x "$ROOT/services/backend/.venv/bin/python" ]]; then
  ok "backend venv already exists (uv not needed)"
elif [[ $PY_OK -eq 1 ]]; then
  warn "uv not found; scripts/dev.sh uses it to create the backend venv (brew install uv)"
else
  bad "Neither uv nor Python 3.11+ is available for the backend (brew install uv)"
fi

if command -v psql >/dev/null 2>&1; then
  ok "psql $(psql --version | awk '{print $3}')"
else
  bad "psql not found (brew install postgresql@16)"
fi
command -v git >/dev/null 2>&1 && ok "git $(git --version | awk '{print $3}')" || bad "git not found"

echo
echo "PostgreSQL"
PG_UP=0
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -p 5432 -q; then
  PG_UP=1
elif (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then
  PG_UP=1
fi
if [[ $PG_UP -eq 1 ]]; then
  ok "PostgreSQL is accepting connections on localhost:5432"
  # Same credentials as the .env.example templates (local development only).
  url="postgresql://quotepulse_app:dev_password_123@localhost:5432/quotepulse_dev?sslmode=disable"
  if command -v psql >/dev/null 2>&1 && psql "$url" -Atqc "select 1" >/dev/null 2>&1; then
    ok "database quotepulse_dev reachable as quotepulse_app"
  else
    warn "can't log in to quotepulse_dev as quotepulse_app yet; run: psql -d postgres -f scripts/init_local_db.sql"
  fi
else
  bad "nothing is listening on localhost:5432 (brew services start postgresql@16)"
fi

echo
echo "Repository"
for f in apps/web/.env.example services/backend/.env.example scripts/dev.sh \
         scripts/smoke_test.py scripts/init_local_db.sql samples/rfq_apex.md \
         samples/apex_census_locked.xlsx; do
  if [[ -f "$ROOT/$f" ]]; then ok "$f"; else bad "missing $f"; fi
done
for f in scripts/dev.sh scripts/verify_handoff.sh; do
  [[ -x "$ROOT/$f" ]] || warn "$f is not executable (chmod +x $f)"
done
for f in apps/web/.env.local services/backend/.env.backend.local; do
  if [[ -f "$ROOT/$f" ]]; then ok "$f present"; else ok "$f will be created from its template by dev.sh"; fi
done

echo
if [[ $FAILS -eq 0 ]]; then
  [[ $WARNS -gt 0 ]] && echo "$WARNS warning(s) above; none of them block startup."
  printf '\033[1;32mEnvironment ready. Run '"'"'./scripts/dev.sh'"'"' to start QuotePulse.\033[0m\n'
  exit 0
fi
printf '\033[1;31m%d problem(s) found. Fix the ✗ items above, then run this script again.\033[0m\n' "$FAILS"
exit 1
