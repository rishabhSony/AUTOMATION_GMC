# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AGENT DIRECTIVE: QuotePulse GMC Engine

You are the senior full-stack AI engineer developing **QuotePulse GMC**, which turns multi-format Group Medical Cover (GMC) RFQ/tender packs and unclean census rosters into audited, client-ready quote sheets. Your objective is to implement the platform step by step and accurately, with zero hallucinations.

## Current State

As of 29 Oct 2026:
- **Phase 1 (local scaffold): done.** `apps/web` (Next.js 15.5, shadcn/ui) and `services/backend` (FastAPI exposing only `GET /api/v1/health`).
- **Phase 2 (schema): done.** Migrations `0000`–`0003` are applied to local `quotepulse_dev`, and the seed has run (4 users, 19 sub-limit rows).
- **Phase 3 (Clerk auth): code done, not yet exercised with a real Clerk login.**
  - Working: middleware redirects, `/login`, `/invite/accept`, a placeholder `/dashboard`, the Clerk webhook (tested with signed events), and `lib/auth.ts`.
  - Blocked on: the Clerk keys and `CLERK_WEBHOOK_SIGNING_SECRET` in `.env.local`, plus Clerk Dashboard setup (Restricted / invite-only sign-up mode, a webhook endpoint for `user.*` events).
  - Not built: the `/onboarding` screen from Plan Phase 3.
- **Plan Phase 4 (ingestion & decryption) + Phase 6 (demography engine): done**, with 60 pytest tests passing.
  - Files: `app/services/storage.py`, `app/services/demography.py`, and `app/api/v1/cases.py`.
  - Endpoints: `POST /cases`, `POST /cases/{id}/upload` and `POST /cases/{id}/demography/process`.
  - Performance: the engine handles 50k rows in about 0.1 s; the full API request takes about 2.6 s including the DB insert and Excel export.
  - Not built yet:
    - Celery dispatch (`process_case_pipeline`); Redis isn't installed.
    - The `/decrypt` endpoint (decryption happens inside `/demography/process`).
    - `GET` endpoints and `/demography/recalculate-age`. The engine's `apply_ages` is ready for the latter.
  - The user called this work "Phase 4 & 5", but the demography engine is Plan Phase 6.
- **Plan Phase 5 (AI extraction & sub-limit matcher): code done and unit-tested with a mocked OpenAI client.** The full suite is 111 tests.
  - Files: `app/services/parser.py`, `extractor.py`, `field_registry.py`, `sublimits.py` and `derivations.py`.
  - **No live `gpt-5.4-mini` call has been made yet:** `OPENAI_API_KEY` is empty. The strict tool schemas are checked offline against OpenAI's strict-mode rules.
  - Extraction runs synchronously inside the request (no Celery yet).
- **Doc 05 §8 read/review/export API: done** (122 pytest tests). Files: `app/api/v1/workbench.py`, `app/api/v1/exports.py`, `app/services/exports.py`, plus `GET /cases` and `GET /cases/{id}` in `cases.py`.
  - Still missing from Doc 05 §8: `/decrypt`, `/process` (Celery), `/pipeline-status` (SSE) and `POST /recalculate-zone` (zone is already re-derived by `/manual-inputs`).
  - 50k-member census: recalculate-age ≈ 2.6 s worst case (every age changes; only changed rows are written), a 1,000-row roster page ≈ 0.15 s.
- **Plan Phase 7 (workbench UI): built; exercised only against a local harness, not with a real Clerk login.**
  - Routes: `/dashboard` (metric cards, status filter pills, search, paginated case table) and `/cases/[id]/{quote,sublimits,demography,exceptions,audit}`. `/cases/[id]` redirects to `quote`.
  - Quote tab: 5-column grid grouped by section, inline manual inputs that re-derive Zone (pulse + toast), the evidence drawer (`?evidence=<field>`), and a justified override dialog.
  - Demography tab: 7-column grid virtualized with `@tanstack/react-virtual` (36 px rows, 1,000-row pages via `useInfiniteQuery`), the age-basis switcher with Recalc, and `?flagged=true`.
  - Exceptions tab: unmatched sub-limit triage cards, quote fields needing review, and demographic anomalies with resolve/reopen (`?view=open|resolved|all`). Audit tab: append-only log, newest first.
  - Not built: `/cases/new` (create + upload UI), `/cases/[id]/treatments` (the quote grid shows those sections), the SSE pipeline hub, `/onboarding`, the decryption modal, and PDF bounding-box previews (no layout coordinates are stored).
  - Verified by running a copy of the app with Clerk stubbed out against the real API and DB in Playwright: every tab, PIN → Zone, overrides, recalculation, resolutions and export download. No console errors.

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
uvicorn app.main:app --reload --port 8000        # health: GET /api/v1/health; docs: /docs
celery -A app.tasks.worker worker --loglevel=INFO   # not wired yet (no app/tasks)
brew install redis && brew services start redis   # native Redis (not installed yet), no Docker
ruff check .                                      # lint
ruff format .                                     # format

# Frontend calls FastAPI directly from the browser: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# in apps/web/.env.local, and the API's CORS_ALLOWED_ORIGINS must include the web origin.

# Tests (services/backend; config in pyproject.toml). OpenAI is never called: tests inject
# tests/llm_fakes.py (canned Pass 1/2 models from tests/fixtures/*.json, RFQ in rfq_apex.md).
python -m pytest -q                               # all tests (first Docling import adds ~30 s)
python -m pytest tests/test_extractor.py tests/test_sublimits.py tests/test_derivations.py -q
python -m pytest tests/test_demography.py -k 50k  # 50k-row performance test (< 2 s)
python -m pytest tests/test_demography.py::test_integrity_flags   # single test
# tests/test_api_cases.py runs end-to-end against DATABASE_URL (skipped if the DB or the
# seeded admin is unavailable). It overrides Clerk auth and deletes its own case and files.

# Calling the API: every /api/v1/cases route needs `Authorization: Bearer <Clerk session JWT>`
# (CLERK_JWKS_URL must be set in .env.backend.local). Encrypted census → 423 password_required.
curl -X POST localhost:8000/api/v1/cases -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"company_name":"Apex Logistics"}'
curl -X POST localhost:8000/api/v1/cases/$CASE/upload -H "Authorization: Bearer $TOKEN" \
  -F files=@census.xlsx -F files=@rfq.pdf          # optional: -F file_category=demography_census
curl -X POST localhost:8000/api/v1/cases/$CASE/demography/process -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"password":"…","basis_mode":"policy_proposal_start_date","proposal_start_date":"2026-11-01"}'
curl -X POST localhost:8000/api/v1/cases/$CASE/extract/rfq -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"passwords":{"<file_id>":"…"}}'   # 423 lists locked files
curl localhost:8000/api/v1/cases/$CASE/extractions -H "Authorization: Bearer $TOKEN"
curl localhost:8000/api/v1/cases/$CASE/sublimits -H "Authorization: Bearer $TOKEN"
curl -X PATCH localhost:8000/api/v1/cases/$CASE/manual-inputs -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"pincode":"400051","brokerage_pct":"7.50"}'
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
- API endpoints (`app/api/v1/cases.py`, all under `/api/v1`, Clerk Bearer JWT, RLS-scoped):

  | Endpoint | Roles | Purpose |
  | --- | --- | --- |
  | `POST /cases` | sales_rm, underwriter, admin | Create a case. A sales RM is always the assignee. |
  | `POST /cases/{id}/upload` | sales_rm, underwriter, admin | Multipart `files`. Category is inferred (csv/xls/xlsx → census, else RFQ) or set with `file_category`. Encryption is detected. |
  | `POST /cases/{id}/demography/process` | + ops_analyst | Census → `demography_records`/`_exceptions`, group metrics, 7-col xlsx. |
  | `POST /cases/{id}/extract/rfq` | sales_rm, underwriter, admin | Parse RFQ docs → Pass 1 → Pass 2 → sub-limit matcher; upserts results; archives JSON reports. |
  | `GET /cases/{id}/extractions` | all | 5-column Quote Review Grid in registry order, with display labels and evidence. |
  | `GET /cases/{id}/sublimits` | all | All 19 registry procedures, with Option 1–4 amounts and the match result (Matched / Unmatched / Review Required / Not Found). |
  | `PATCH /cases/{id}/manual-inputs` | sales_rm, underwriter, admin | Edits `rater_type`, `brokerage_pct` (0–15), `pincode` (`^[1-9][0-9]{5}$`), `state`, `district`; re-derives Zone; writes `audit_logs`. |
  | `GET /cases` | all | Paginated (`page`, `page_size` ≤ 100), repeatable `status` filter, `q` search on company/case number. Returns `summary` counts for the dashboard cards. |
  | `GET /cases/{id}` | all | Header, manual inputs, metrics, files, and review counts. |
  | `GET /cases/{id}/demography` | all | 7-column roster, `page_size` ≤ 1000, `flagged_only`. |
  | `POST /cases/{id}/demography/recalculate-age` | ops_analyst, underwriter, admin | Reruns `demography.apply_ages` on stored rows for `basis_mode` (+ `proposal_start_date`, else the stored one). |
  | `GET /cases/{id}/demography/exceptions` | all | Queue sorted open → critical → row; filters `resolved`, `exception_type`. |
  | `PATCH /cases/{id}/demography/exceptions/{exc_id}` | ops_analyst, underwriter, admin | `resolution_action` (5–2000 chars) required; `is_resolved` (default true) can reopen. |
  | `PATCH /cases/{id}/extractions/{field_name}` | sales_rm, underwriter, admin | `coverage_details`/`proposed_details` + `justification`; sets Manual / High, `is_manual_override`, `overridden_by_user_id`, `override_reason`. |
  | `PATCH /cases/{id}/sublimits/{proc_name}` | underwriter, admin | `matched_option` (`option_1`–`4`, or `unmatched` to approve the exact amount) + `justification`. |
  | `GET /cases/{id}/export/quote-excel`, `/export/demography-excel` | all | openpyxl workbook archived to `outputs/analysis/{case_id}/`, `case_export` audit row, streamed back. |
  | `GET /cases/{id}/audit` | all | Audit trail, newest first. From TRD §11 (Doc 05 has no audit route); the audit tab needs it. |
- Review API decisions:
  - Field and procedure names contain `/` (e.g. `Maternity Expenses / Benefits`), so those routes use `{name:path}`; clients send `encodeURIComponent(name)`.
  - `PATCH /extractions` rejects the manual-input fields (Rater Type, Brokerage %, PIN Code, State, District) and Zone with 422: `/manual-inputs` keeps the `cases` columns, grid rows and Zone in sync.
  - `PATCH /extractions` on a field the extraction never produced inserts the row (manual fill-in).
  - Sub-limit approval sets `status = 'manual'` and `is_underwriter_approved`. Approving a tier for a procedure missing from the RFQ stores that tier's amount as the value; `unmatched` needs an RFQ amount.
  - Recalculate-age regenerates only age-dependent exceptions (`under18_employee`, `age_dob_mismatch`, and `invalid_dob` where a DOB was parsed). Resolved ones are kept and suppress an identical new one. A DOB now after the basis date with no source age keeps its previous age.
  - Quote workbook (`gmc_quote_summary_sheet.xlsx`): sheets Quote Summary (case header + 5-column grid), Hospitalization & Treatments, Procedure Sub-Limits, Underwriter Notes (audit rows with a justification).
  - The browser calls FastAPI directly, so CORS allows `CORS_ALLOWED_ORIGINS` (default `http://localhost:3000`).
  - RLS limits ops analysts to cases assigned to them (Doc 05 §3 as written), even though the role matrix says "system-wide".

- Extraction pipeline (Phase 5):
  - **Registry:** `field_registry.py` is the single source of truth: 95 BRD §6–7 fields, 88 of them sent to the LLM as a strict `Literal`. Names are lightly shortened from the BRD (e.g. modern-treatment titles). An extra `Incumbent Insurer` field exists to drive the BRD proposal-type rule.
  - **LLM call:** instructor 1.17 deprecates `TOOLS_STRICT` (it silently becomes `TOOLS`), so strictness comes from `Mode.TOOLS` + `strict=True` per call + `extra="forbid"` models. `store=False` is sent while `OPENAI_ZERO_DATA_RETENTION=true`.
  - **Grounding:** Pass 2's verdict is overridden by a deterministic check. If the verbatim evidence isn't in the parsed text, the field becomes Review Required / Low.
  - **Fallbacks and validation:** missing fields use BRD defaults as `default_data`. The room-rent splitter in `derivations.py` fills Normal/ICU from the parent clause (`ai_derived`). The TPA rule and the co-pay %/PIN validators also live there.
  - **Re-extraction:** rows with `is_manual_override`, and underwriter-approved sub-limits, are never overwritten.
  - **Case updates:** grounded PIN/State/District from the RFQ fill only empty case columns. The case also gets `proposal_type`, `status`, `model_version` and `pipeline_duration_ms`, and an `ai_extraction` audit row records model, latency and token usage.
  - **Sub-limit status:** stored with Doc 05 enums (`matched_option` option_1–4/unmatched; `status` rfq_data or review_required). The "Matched" label exists only in the API.
  - **Ties:** when two tiers share an amount, the lowest option wins.
  - **Non-numeric amounts** (e.g. "10% of SI") are kept raw with `cleaned_amount` null.
  - **Zone:** looked up in `zone_master` by PIN, then by state + district, falling back to `"Review Required"` (user decision; the BRD says `Pan India`).
  - **Parser:** PDFs use PyMuPDF with `[[File: x | Page n]]` markers and Markdown tables. DOCX, and scanned PDFs, use Docling from an in-memory stream (`PARSER_PDF_ENGINE=docling` forces it for every PDF). TXT/MD are decoded directly.
- Backend (Phases 4 and 6):
  - **Data access:** FastAPI uses raw SQL via psycopg 3 (no ORM; Drizzle owns the schema). Every query runs inside `app.core.db.rls_transaction(ctx)`.
  - **Auth:** `app.core.auth.get_current_user` verifies the Clerk session JWT against `CLERK_JWKS_URL`, maps `sub` to the `users` row, and `require_roles(...)` enforces the Doc 05 §8 role sets.
  - **Bulk loads:** Postgres refuses `COPY` into RLS tables, so bulk loads COPY into a temp table and then `INSERT … SELECT`.
  - **Upload path:** `/cases/{id}/upload` follows the Doc 05 §8 catalog. The user's brief said `/files`.
  - **Decryption:** the password is sent with the `/demography/process` request (`SecretStr`) and used only on in-memory buffers, because a separate `/decrypt` step would require storing it. The raw upload stays encrypted on disk.
  - **Storage keys:** `case_files.storage_path` holds a key relative to the storage root (`inputs/raw/{case_id}/{ms}_{name}`), the same for local and S3. `LOCAL_STORAGE_PATH` is resolved relative to `services/backend`.
- `demography_exceptions.record_id` is nullable (migration `0003`), a deviation from Doc 05. Critical rows (missing Age and DOB, or an unmapped relationship) aren't stored as records but still get an exception.
- Exception type values follow Doc 05's lowercase style: `under18_employee`, `orphan_dependent`, `duplicate_member`, `age_dob_mismatch`, `missing_required_field`, `invalid_dob`, `missing_age_and_dob` (BRD `CRITICAL_ERROR`) and `unmapped_relationship`. Severity is `critical` only when the row couldn't be stored.
- Demography engine choices:
  - Header aliases are the BRD §9.1 list merged with the user's list; priority order matters (e.g. `Member Name` beats `Employee Name`).
  - Dates are read day-first, falling back to MM/DD only when the day-first reading is impossible.
  - A DOB after the basis date counts as invalid and falls back to the source age.
  - Group Size = stored rows, duplicates included.
- Frontend (Phase 7):
  - **Data access:** client components call FastAPI through `lib/api/client.ts` (`useApi()`), which sends the Clerk session token (`useAuth().getToken()`) as the Bearer header. Hooks live in `lib/api/queries.ts` (TanStack Query v5); every mutation invalidates the case's queries (`["case", id, …]`).
  - **Roles:** `app/(app)/layout.tsx` resolves the `users` row on the server and provides it through `SessionUserProvider`. `useCan()` only hides controls; the API enforces roles.
  - **URL state:** nuqs for dashboard filters (`status`, `q`, `page`), `evidence`, `flagged` and `view`.
  - **Components:** shadcn's registry (ui.shadcn.com) isn't reachable from the cloud environment, so `sheet`, `textarea`, `skeleton` and `label` were written by hand on `radix-ui`, following the generated files' style.
  - **Pills:** provenance pills use the UI brief §1.1 palette (`components/workbench/status-pill.tsx`).
  - **Fonts:** the Geist font variables sit on `<html>`, because `font-sans` is applied there (on `<body>` they never resolved and text fell back to serif). Sora and JetBrains Mono remain Phase N.
  - **State / District:** plain text inputs. The brief's searchable dropdowns need master data that `zone_master` doesn't have yet.
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
