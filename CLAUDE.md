# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AGENT DIRECTIVE: QuotePulse GMC Engine

You are the senior full-stack AI engineer developing **QuotePulse GMC**, which turns multi-format Group Medical Cover (GMC) RFQ/tender packs and unclean census rosters into audited, client-ready quote sheets. Your objective is to implement the platform step by step and accurately, with zero hallucinations.

## Current State

As of 29 Oct 2026:
- **Phase 1 (local scaffold): done.** `apps/web` (Next.js 15.5, shadcn/ui) and `services/backend` (FastAPI exposing only `GET /api/v1/health`).
- **Phase 2 (schema): done.** Migrations `0000`–`0002` are applied to local `quotepulse_dev`, and the seed has run (4 users, 19 sub-limit rows).
- **Phase 3 (Clerk auth): code done, not yet exercised with a real Clerk login.**
  - Working: middleware redirects, `/login`, `/invite/accept`, a placeholder `/dashboard`, the Clerk webhook (tested with signed events), and `lib/auth.ts`.
  - Blocked on: the Clerk keys and `CLERK_WEBHOOK_SIGNING_SECRET` in `.env.local`, plus Clerk Dashboard setup (Restricted / invite-only sign-up mode, a webhook endpoint for `user.*` events).
  - Not built: the `/onboarding` screen from Plan Phase 3.

Phase 0 is complete: this file is the only agent-context file. Update this section and the Commands section as phases land.

---

## 1. MANDATORY CONTEXT: Read Specifications First

Before executing any phase, writing code, or suggesting architectures, **read the relevant spec files in `/docs`**:

1. `docs/gmc_quote_preparation_automation_brd-2.md`: Business requirements, RFQ field registry, 19-procedure sub-limit Option 1–4 grid, demography header aliases & validation rules.
2. `docs/gmc_quote_preparation_prd-2.md`: Product scope, user stories, out-of-scope list.
3. `docs/gmc_quote_preparation_automation_trd.md`: Stack, architecture, storage contract, AI extraction (Pass 1/Pass 2), env var catalog, EC2 Docker runbook.
4. `docs/gmc_quote_preparation_automation_app_flow.md`: All 16 routes, redirect matrix, empty/error/loading states.
5. `docs/gmc_quote_preparation_automation_ui_ux_design_brief.md`: Palette tokens, typography, 5-column quote grid, 7-column demography grid, drawer/modal specs.
6. `docs/gmc_quote_preparation_backend_schema.md`: Drizzle schema (8 tables), RLS SQL, role matrix, REST API catalog.
7. `docs/document_06_implementation_plan.md`: Phased roadmap and per-phase "Done" criteria.

---

## 2. Hard Technical Stack & Constraints

- **Local Build Strategy:** **100% bare-metal local development first.** Do **NOT** run Docker locally. Dockerization occurs exclusively on the target AWS EC2 server in Phase N+2.
- **Frontend:** Next.js 15 (App Router only; `pages/` is forbidden), TypeScript 5.5+ strict, Tailwind CSS v4, shadcn/ui, TanStack Table v8 + `@tanstack/react-virtual`, `nuqs` for URL state, Zod.
- **Frontend Package Manager:** **Bun 1.x ONLY** (`bun run`, `bun add`, `bunx`). Never use npm, yarn, or pnpm.
- **Data Fetching:** TanStack Query v5 (`@tanstack/react-query`). Never import `react-query`.
- **Backend:** Python 3.11+ within `.venv`, FastAPI, Celery, Redis.
- **Demography Engine:** **Polars 1.x / DuckDB**. Vectorized operations only. Never use Python iterative row loops for age calculation or validation.
- **AI Inference:** **OpenAI `gpt-5.4-mini`** (400k-token single-pass context via `instructor` and strict JSON schemas). Do **NOT** use `pgvector`, chunking, or vector RAG.
- **Database & ORM:** PostgreSQL via **Drizzle ORM** (`apps/web/db/schema.ts`, no `src/` dir; see §6) with the `postgres` (postgres-js) driver. Local development uses native PostgreSQL on macOS (`localhost:5432`, database `quotepulse_dev`, role `quotepulse_app`). There are no Neon or other cloud-specific drivers, even where the docs mention Neon. Migrations are owned by the frontend workspace (`drizzle-kit`).
- **Authentication:** **Clerk** (closed, invite-only). Self-registration (`/signup`) is strictly disabled.
- **Storage Abstraction:** Backend storage provider in `services/backend/app/services/storage.py`, selected by env:
  - **Local Phase:** `./storage/inputs/raw/{case_id}/` and `./storage/outputs/analysis/{case_id}/`.
  - **EC2 Phase:** `s3://{bucket}/inputs/raw/{case_id}/` and `s3://{bucket}/outputs/analysis/{case_id}/`.
- **Naming:** `kebab-case` folders/files, `PascalCase` React components, `camelCase` TS utilities/hooks, `snake_case` Python.

---

## 3. Planned Repository Layout & Architecture

```
apps/web/             Next.js 15 frontend (Bun); Drizzle schema, migrations & seed live here
services/backend/     FastAPI app (app/main.py), Celery worker (app/tasks/worker.py), services/
storage/              Local-phase file store (inputs/raw, outputs/analysis)
deploy/               docker-compose.prod.yml (EC2 only: caddy, web, api, worker, redis)
```

**Request/processing pipeline** (spans frontend, API, worker, DB):
1. Frontend creates a case → `POST /api/v1/cases`, uploads files → `POST /api/v1/cases/{id}/upload` (raw files saved via the storage provider).
2. Encrypted PDF/Excel → password challenge modal → `POST /api/v1/cases/{id}/decrypt`, decrypted in RAM only.
3. Celery task `process_case_pipeline(case_id)` runs: document → Markdown (Docling/PyMuPDF) → **Pass 1** extraction (`gpt-5.4-mini`, Current vs Proposed + verbatim citations) → **Pass 2** reflection verifier (confidence High/Medium/Low, Conflict/Review Required) → **deterministic** sub-limit matcher → Polars demography engine.
4. Results persist to `rfq_extractions`, `procedure_sublimits`, `demography_records`, `demography_exceptions`; every user override writes to append-only `audit_logs`.
5. Workbench tabs under `/cases/[id]/*` (quote, demography, exceptions, audit) review/edit; exports via `GET /api/v1/cases/{id}/export/{file_type}` (openpyxl), archived to `outputs/analysis/`.

**AI vs deterministic split:** the LLM only does language comprehension, Current/Proposed separation and citation grounding. Age math, SME flag, sub-limit Option 1–4 matching, and PINCODE→Zone resolution are pure Python/Polars rules, never the LLM.

---

## 4. Core Business & UI Invariants

1. **Quote Review Grid (Strict 5 Columns):**
   `Quote Fields` | `Coverage Details` | `Proposed Details` | `Source Status` | `Confidence`
2. **Standardized Demography Grid (Strict 7 Columns in exact order):**
   `Age` (Col 1) | `Date of Birth` (Col 2) | `Sum Insured` (Col 3) | `Relationship` (Col 4) | `Name` (Col 5) | `EmpCode` (Col 6) | `Gender` (Col 7)
3. **Manual Inputs with Auto-Derivation:**
   `Rater Type`, `Brokerage %`, `PINCODE`, `State`, and `District` must be directly editable inline (stored as columns on `cases`). Updating `PINCODE` must dynamically recalculate the derived `Zone` parameter.
4. **Zero-Persistence Password Decryption:**
   Protected files must be decrypted in ephemeral memory (`tmpfs` / RAM buffer). Never log passwords or write decrypted raw bytes to persistent disk; overwrite the password variable after use.
5. **Demography rules:** Age = ⌊(Basis Date − DOB) / 365.25⌋, basis toggles between `Current Date` and `Policy Proposal Start Date`; dates normalized to `DD-MM-YYYY`; fall back to source age if DOB missing, `CRITICAL_ERROR` if both missing. Flags: under-18 employee, orphan dependant, duplicate (EmpCode+Name+Relationship), `AGE_DOB_MISMATCH` (>1 yr). SME = primary members ≤ 250.
6. **Sub-limit matching:** strip `₹`/commas/whitespace, exact-match against the 19-procedure Option 1–4 grid; non-matches keep the exact amount and are flagged `Unmatched / Review Required`.

---

## 5. Commands

```bash
# Frontend (apps/web)
bun install
bun run dev --port 3000
bun run lint                                      # ESLint 9 flat config (eslint.config.mjs, with eslint-config-prettier)
bun run format:check                              # prettier --check .
bun run format                                    # prettier --write .
bunx tsc --noEmit                                 # typecheck
bunx --bun shadcn@latest add <component>          # add shadcn/ui components
bun run typecheck                                 # tsc --noEmit
bun run db:generate                               # drizzle-kit generate (schema.ts → drizzle/*.sql)
bun run db:migrate                                # apply to DATABASE_URL
bun run db:studio
bun run seed                                      # idempotent: 4 role users + BRD §8.1 sub-limit registry

# Backend (services/backend), inside .venv
uv venv .venv --python 3.11 && uv pip install -r requirements-dev.txt   # first-time setup
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000        # health: GET /api/v1/health
celery -A app.tasks.worker worker --loglevel=INFO   # from Phase 4
brew install redis && brew services start redis   # native Redis (not installed yet), no Docker
ruff check .                                      # lint
ruff format .                                     # format

# Tests (Phase N+1): Pytest for demography engine & sub-limit matcher; Playwright for UI/auth
pytest path/to/test_file.py::test_name            # single test
```

Lint/format tooling: **ESLint + Prettier** (frontend, Next.js 15) and **Ruff** (backend, Python 3.11+). These are project choices, not from `/docs`.

Setup notes:
- Python 3.11 is not on the system path; the `.venv` uses a uv-managed CPython 3.11 (`uv venv --python 3.11`).
- Backend runtime deps are in `services/backend/requirements.txt` (includes `ruff`); `requirements-dev.txt` adds `pytest`. Polars is pinned `<2` to honour the 1.x constraint.
- Version pins that latest tags would break: `next` 15.5.x (don't upgrade to 16), `@tanstack/react-table` ^8 (latest is v9).
- shadcn/ui uses the `radix-nova` style; `cn` comes from shadcn's `cn` package (re-exported by `lib/utils.ts`). Toasts use `sonner` (shadcn `toast` is deprecated).

Env files (gitignored): `apps/web/.env.local` and `services/backend/.env.backend.local`, holding TRD §12 variable names split by frontend and backend. The frontend file also has `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/invite/accept`, `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` and `CLERK_WEBHOOK_SIGNING_SECRET`. Without Clerk keys every route returns 500.

---

## 6. Known Spec Inconsistencies (resolve before/while implementing)

- Schema source of truth is **Backend Schema v4.0 §2 (Doc 05), as written** (user decision). Use its names and enums (`case_number`, `assigned_user_id`, roles `admin|underwriter|sales_rm|ops_analyst`, snake_case enum values such as `rfq_data`/`option_1`), not variants found in other docs or prompts. Map to display labels (e.g. "RFQ Data", "Option 2") in the UI and exports.
- Two reference tables were added beyond Doc 05's eight (user decision). `sublimit_registry` holds the 19 BRD §8.1 procedures with Option 1–4 amounts, and the sub-limit matcher must read it. `zone_master` maps PINCODE/District to `Zone A–D` or `Pan India`. It is **intentionally empty** until Underwriting Ops sign off the mapping (BRD §10); don't invent rows.
- RLS: `0001_rls.sql` holds Doc 05 §3's policies verbatim. `0002_rls_patch.sql` adds policies for `users` (own row by id or Clerk id; admin writes), `case_files` and `demography_exceptions`, and sets **FORCE RLS**. The app role `quotepulse_app` owns the tables, and FORCE RLS stops the owner from bypassing them.
  - All app queries must therefore go through `withRlsContext` / `getAuthenticatedDb()`, which set `app.current_user_id`, `app.current_user_role` and `app.current_clerk_user_id` per transaction. A bare `db` query sees no rows in RLS tables.
  - `withSystemContext` (admin role) is only for trusted writers: the seed and the verified Clerk webhook.
  - The FastAPI backend will need the same per-transaction settings once it touches these tables.
- `quotepulse_app` was granted `CREATE ON DATABASE quotepulse_dev`, which `drizzle-kit migrate` needs to create its `drizzle` journal schema.
- Routes (user decision): `/` redirects to `/dashboard` (signed in) or `/login`, not App Flow's public landing page. The signed-in home is `/dashboard` (App Flow), not `/workbench`.
  - Signed-in pages live under `app/(app)/`, whose layout re-checks the session. Middleware redirects with `?redirect=`, using prefix matching because Clerk 7 deprecates `createRouteMatcher`.
  - Admin-only pages must call `requireRole("admin")`.
  - New users get their role from the Clerk invitation's `publicMetadata.role` (defaulting to `sales_rm`), and `user.deleted` deactivates the user rather than deleting the row.

- Plan Phase 1 uses `--no-src-dir`, but Phase 2 and the Backend Schema doc say `apps/web/src/db/schema.ts`. Resolved: no `src/`. The schema goes at `apps/web/db/schema.ts`, and seed scripts sit alongside it under `db/` (`@/*` → `./*`).
- Storage env var is `STORAGE_BACKEND` in TRD §12 but `STORAGE_DRIVER` in Plan Phase N+2; class names differ (`LocalStorageProvider` vs `LocalStorageDriver`). Follow the TRD.
- Plan Phase 1's `pip install` list omits `docling` and `pymupdf`, which the pipeline needs for parsing (Plan Phase 5, TRD, App Flow). Resolved: both are in `requirements.txt`.

---

## 7. Operational Instructions for the Agent

- Always check the current phase in `docs/document_06_implementation_plan.md` and meet its "Done" criteria before advancing.
- Never jump ahead to UI polish (Phase N) until underlying data models and APIs meet their phase "Done" criteria.
- Keep responses concise, deterministic, and backed by the files in `/docs`.
