# QuotePulse GMC: Offline Handoff Runbook

How to take this repository to a fresh laptop and prove it works end to end. **No Clerk or OpenAI keys are needed:** the app runs in mock mode (dev role switcher instead of Clerk, a deterministic mock AI instead of `gpt-5.4-mini`).

Local development is bare-metal (no Docker). The Docker files in this repo are for the EC2 deployment; see [Production containers](#production-containers-ec2) at the end.

## 1. System requirements

| Tool | Version | macOS install |
| --- | --- | --- |
| Bun | 1.x | `curl -fsSL https://bun.sh/install \| bash` |
| Python | 3.11+ for the backend, created by uv; any `python3` ≥ 3.9 runs the smoke test | `brew install uv` |
| PostgreSQL | 16, running natively on `localhost:5432` | `brew install postgresql@16 && brew services start postgresql@16` |
| Git | any recent | Xcode Command Line Tools |

No PostgreSQL service? `docker compose -f docker-compose.dev.yml up -d` starts PostgreSQL 16 and Redis 7 in containers with the same credentials. The apps still run bare-metal.

## 2. Three-step quickstart

```bash
git clone https://github.com/rishabhSony/AUTOMATION_GMC.git && cd AUTOMATION_GMC
```

1. **Check the machine.** Read-only; it changes nothing.
   ```bash
   ./scripts/verify_handoff.sh
   ```
   - It checks Bun, Python/uv, `psql`, PostgreSQL on :5432, a login to `quotepulse_dev`, and the env templates and samples.
   - Expected last line: **"Environment ready. Run './scripts/dev.sh' to start QuotePulse."**
2. **Create the database** (only if step 1 says it can't log in to `quotepulse_dev`). It creates role `quotepulse_app` / `dev_password_123` and database `quotepulse_dev`, and is safe to re-run.
   ```bash
   psql -d postgres -f scripts/init_local_db.sql
   ```
3. **Start everything.**
   ```bash
   ./scripts/dev.sh
   ```
   - It creates the env files from their templates and installs dependencies on first run.
   - It applies migrations `0000`–`0004` and seeds 4 role users plus the 19-procedure sub-limit registry.
   - It starts the API (http://localhost:8000) and web (http://localhost:3000) in mock mode. **Ctrl+C** stops both.

## 3. Headless smoke test

With `dev.sh` running, in a second terminal:

```bash
python3 scripts/smoke_test.py
```

It acts as the seeded admin and:
- creates a case with intake fields and uploads `samples/rfq_apex.md` and the password-protected census;
- checks that `POST /process` answers **423** without the password, then **202** with it (processing is asynchronous);
- polls `/pipeline-status` until all **4 stages are `done`**, then checks the 5-column quote grid and the 7-column roster.

It ends with `SMOKE TEST PASSED` and a link to the case.

## 4. UI verification checklist

Open http://localhost:3000. The full 14-step list is in `CLAUDE.md` §5 ("Local dry-run checklist"); these are the handoff essentials.

- [ ] **Onboarding tour dismissal**
  - The first visit redirects to `/onboarding` (4 cards).
  - **Launch Workbench** returns to `/dashboard`, and reloading stays on the dashboard.
  - **Product tour** in the header reopens it.
  - To see it again as a first-time user, clear the `qp_onboarding_v1_done` localStorage key.
- [ ] **Amber Dev role switcher** (header, top right). Create a case as **Admin**.
  - **Sales RM:** the case is missing from the dashboard and its URL shows "Case not found" (row-level security: Sales RMs see only assigned cases).
  - **Underwriter:** sees it and can approve sub-limits.
  - **Ops Analyst:** sees all cases but has no quote-override pencils.
  - Switch back to **Admin**.
- [ ] **Password-protected census intake**
  - Go to **New Quote Case**, add `samples/rfq_apex.md` and **`samples/apex_census_locked.xlsx`** (password **`Apex@2026`**), then **Create case & start processing**.
  - A wrong password shakes the field: "Incorrect password (Attempt 1 of 3)".
  - The correct password goes to the live pipeline: 4 stages, 443 members, then Quote Review opens.
- [ ] **PDF inline evidence preview**
  - Create a case with **`samples/rfq_orion.pdf`** (plus `samples/apex_census.csv`).
  - On **Modern Treatments**, open **Robotic Surgeries** (Page 2 ↗), then **View Evidence in Document**.
  - The PDF opens in the split view **at page 2**. This step needs a real browser; it was only automated headless.
  - On an `.md` RFQ, the excerpt is highlighted in the text instead.
- [ ] **Dual Excel downloads**
  - **Quote Sheet** and **Demography (7-col)** in the case header download `QuotePulse_{CaseNumber}_Quote_{YYYYMMDD}.xlsx` and `…_Demography_….xlsx`.
  - Each toast cites its `case_export` audit-log id, and both rows appear on the **Audit Trail** tab.
  - Copies are archived under `storage/outputs/analysis/{case_id}/`.

## 5. Resetting to a clean slate

```bash
# Delete all cases (and their files, extractions, demography, audit rows), keep users + registry
psql "postgresql://quotepulse_app:dev_password_123@localhost:5432/quotepulse_dev" \
  -c "select set_config('app.current_user_role','admin',false)" -c "delete from cases"
find storage/inputs/raw storage/outputs/analysis -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
```

## 6. Going live (real Clerk + OpenAI)

Fill the Clerk keys, `CLERK_JWKS_URL` and `OPENAI_API_KEY` in the two env files, then run `./scripts/dev.sh --live`. The Clerk Dashboard steps are in `CLAUDE.md` §5 ("Live mode").

## Production containers (EC2)

| File | Purpose |
| --- | --- |
| `apps/web/Dockerfile` | Bun install + `next build` (standalone output) and a Node 22 runner as user `node`. A `migrator` target runs the Drizzle migrations. |
| `services/backend/Dockerfile` | Python 3.11 venv built with uv (CPU-only torch for Docling), slim runtime as user `app` (uid 10001). |
| `docker-compose.yml` | `db` (Postgres 16), `redis` (Redis 7), one-off `migrate`, `backend`, `web`, with health checks, `./storage/{inputs,outputs}` mounts and `/tmp` in RAM (tmpfs). |
| `deploy/postgres/init-app-role.sh` | First boot of an empty volume: creates the non-superuser app role that owns the schema, so FORCE RLS applies to it. |
| `.env.example` (root) | Variables for `docker compose`: passwords, keys, origins, proxy, S3. |

```bash
cp .env.example .env                              # set passwords, Clerk and OpenAI keys, WEB_ORIGIN, NEXT_PUBLIC_API_URL
sudo chown -R 10001:10001 storage/inputs storage/outputs
docker compose up -d --build                      # db → migrate → backend → web
docker compose run --rm migrate bun run seed      # once: sub-limit registry (+ placeholder seed users)
```

Build notes:
- **Corporate proxy:** pass the proxy as build args. Docker's predefined `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` args are used during the build and aren't kept in the image config. Both builds need egress: Bun and npm for the web image; PyPI and `download.pytorch.org` (CPU torch) for the API; and Google Fonts, because `next/font` fetches Geist during `next build`.
- **Base-image mirrors:** if Docker Hub rate-limits you, override the bases:
  - `--build-arg PYTHON_IMAGE=mirror.gcr.io/library/python:3.11-slim` (API)
  - `--build-arg NODE_IMAGE=…/node:22-alpine` and `BUN_IMAGE=…` (web)
- **Torch index:** `--build-arg TORCH_INDEX_URL=` (empty) installs torch from PyPI instead of the CPU index. That works, but the CUDA wheels add several GB.

Behind a TLS-inspecting corporate proxy, build the images with the proxy's CA as a BuildKit secret; it's never stored in a layer:

```bash
docker build --secret id=corp_ca,src=/path/to/corp-ca.pem -t quotepulse-api services/backend
```

What was verified (in a cloud sandbox, 29 Oct 2026):
- **Images:** all three build: `web` 357 MB on Node 22 as `node`; the `migrator`; and `backend` as uid 10001. The backend test build left out Docling to fit the sandbox's disk, because the CPU torch index isn't reachable there; Docling is only imported for DOCX and scanned PDFs.
- **Stack:** `docker compose up` reaches healthy for `db`, `redis`, `backend` and `web`, and `migrate` exits 0.
- **Production mode:** `/health` reports production with mock auth and mock AI off; requests without a token, or with dev headers, get 401.
- **Database:** the app role isn't a superuser and owns `public`; FORCE RLS is on all 8 tables; the seed job works.
- **Storage:** writable, and `/tmp` is tmpfs.
- **Dev compose:** `docker-compose.dev.yml` boots Postgres and Redis with the template credentials, and the migrations apply.

Not containerised yet:
- **Reverse proxy:** the TLS reverse proxy (Caddy, TRD §13) isn't included.
- **Celery worker:** not built; `/process` runs in the API process, so the API runs a single uvicorn process and Redis is provisioned but unused.
- **Mock modes:** they can't be enabled in these images (`ENVIRONMENT=production`, production Next build).
