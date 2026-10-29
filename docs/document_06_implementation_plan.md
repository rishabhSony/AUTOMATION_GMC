# DOCUMENT 06: IMPLEMENTATION PLAN — PHASED ROADMAP & ENGINEERING EXECUTION

## Application Name: QuotePulse GMC (AI-Driven Quote Preparation & Demography Workbench)

| Implementation Attribute | Specification |
| :--- | :--- |
| **Document Version** | 4.0 (Master Engineering Baseline) |
| **Document Type** | Phased Implementation Roadmap & Engineering Plan |
| **Date** | 29 October 2026 |
| **Parent Documents** | `BRD v3.0`, `PRD v2.0`, `TRD v4.0`, `App Flow v4.0`, `UI/UX Brief v4.0`, `Backend Schema v4.0` |
| **Core Architecture** | Next.js 15 (App Router, Bun 1.x) + FastAPI (Python 3.11+) + Neon PostgreSQL + Drizzle ORM + Clerk Auth + OpenAI `gpt-5.4-mini` (400k context) + Polars 1.x |
| **Development Strategy** | **Stage 1 (Local-First 100% Functional):** Bare-metal Bun + Python venv with local filesystem storage. <br>**Stage 2 (EC2 Promotion):** AWS S3 dual-prefix storage, corporate outbound forward proxy, and on-server Dockerization. |

---

## Phased Implementation Roadmap & Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       PHASE ROADMAP & DEPENDENCY GRAPH                                   │
│                                                                                                         │
│  [ Phase 0: Persistent Agent Context (CLAUDE.md / .cursorrules) ]                                       │
│         │                                                                                               │
│         ▼                                                                                               │
│  [ Phase 1: Local Bare-Metal Setup & Workspace Config (No Docker) ]                                      │
│         │                                                                                               │
│         ▼                                                                                               │
│  [ Phase 2: Neon PostgreSQL Schema, Drizzle ORM & RLS Migrations ]                                      │
│         │                                                                                               │
│         ▼                                                                                               │
│  [ Phase 3: Clerk Enterprise SSO & Closed Invite-Only Auth Pipeline ]                                   │
│         │                                                                                               │
│         ▼                                                                                               │
│  [ Phase 4: Case Ingestion, Local Storage Driver & RAM Zero-Persistence Decryption ]                    │
│         │                                                                                               │
│         ├────────────────────────────────────────┬────────────────────────────────────────┐             │
│         ▼                                        ▼                                        ▼             │
│  [ Phase 5: AI Extraction Engine ]    [ Phase 6: Demography Engine ]        [ Phase 7: Workbench UI ]   │
│  • gpt-5.4-mini (400k single-pass)    • Polars 7-Col Normalizer             • 5-Col Quote Review Grid   │
│  • Dual-pass reflection verifier      • Dynamic Age Recalculator            • 7-Col Virtualized Roster  │
│  • 19 Procedure Option 1–4 Matcher    • Under-18 & Dependant Checks         • 5 Editable Manual Inputs  │
│         │                                        │                          • Evidence Inspector Drawer │
│         └────────────────────────────────────────┼────────────────────────────────────────┘             │
│                                                  ▼                                                      │
│                                       [ Phase 8: Audited Export Engine ]                                │
│                                       • Quote Excel & 7-Col Demography Excel                            │
│                                       • Local to S3 Archival Abstraction                                │
│                                                  │                                                      │
│                                                  ▼                                                      │
│                                       [ Phase N: UI/UX Clinical Fintech Polish ]                        │
│                                                  │                                                      │
│                                                  ▼                                                      │
│                                       [ Phase N+1: Testing, Hardening & Edge Cases ]                    │
│                                                  │                                                      │
│                                                  ▼                                                      │
│                                  [ Phase N+2: EC2 On-Server Dockerization & Outbound Proxy ]            │
│                                                  │                                                      │
│                                                  ▼                                                      │
│                                       [ Project "Done" Verification ]                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 0: Persistent Agent Context (`CLAUDE.md` & `.cursorrules`)

* **Goal:** Create persistent agent context files in the repository root so any AI coding assistant or engineer immediately grasps the full architecture, directory standards, and strict operational constraints across all sessions.
* **Tasks:**
  1. Create `CLAUDE.md` and `.cursorrules` in the workspace root.
  2. Embed the condensed architecture from TRD v4.0: Next.js 15 App Router, Bun 1.x (never npm/yarn/pnpm), TypeScript 5.5+ strict mode, Tailwind CSS v4, FastAPI (Python 3.11+), Neon PostgreSQL via Drizzle ORM, Clerk Auth (invite-only), OpenAI `gpt-5.4-mini`, and Polars.
  3. Document explicit **DO-NOT Rules**:
     * *DO NOT* use Pages Router (`pages/` directory is strictly forbidden).
     * *DO NOT* use npm, yarn, or pnpm; only run `bun` / `bunx`.
     * *DO NOT* attempt to run Docker locally; development runs 100% on bare-metal host runtimes.
     * *DO NOT* persist file decryption passwords to logs, database, or disk; passwords must exist strictly in transient RAM.
     * *DO NOT* import `@tanstack/react-query` as `react-query`.
     * *DO NOT* perform demographic age calculation with Python iterative loops; use vectorized Polars expressions.
     * *DO NOT* create public self-service registration pages (`/signup` is disabled; all users are invite-only).
     * *DO NOT* use `pgvector` or document-chunking RAG; pass complete tender markdown into `gpt-5.4-mini`'s 400,000-token context.
  4. Define standardized directory naming conventions (`kebab-case` for folders/files, `PascalCase` for React components, `camelCase` for TypeScript utilities/hooks, and `snake_case` for Python scripts).
* **Done Criteria:** When prompted *"What stack, storage model, and AI engine are we using?"*, the agent accurately outputs the exact stack (Bun, Next.js 15 App Router, FastAPI, Polars, Drizzle, `gpt-5.4-mini`), the local-to-S3 storage strategy, the 5-column quote grid, the 7-column demography schema, and the zero-docker local development constraint directly from context.

---

### Phase 1: Local Bare-Metal Setup & Workspace Configuration (Zero Docker)

* **Goal:** Initialize the workspace on local host runtimes without Docker, configure TypeScript paths, setup Tailwind CSS v4, establish the Python virtual environment, and verify zero-error local boot.
* **Tasks:**
  1. Initialize Next.js 15 App Router frontend with Bun:
     ```bash
     bun create next-app apps/web --typescript --tailwind --app --no-src-dir --import-alias "@/*"
     ```
  2. Install frontend dependencies via Bun:
     ```bash
     cd apps/web
     bun add @clerk/nextjs @neondatabase/serverless drizzle-orm @tanstack/react-query @tanstack/react-table @tanstack/react-virtual lucide-react zod nuqs date-fns sonner clsx tailwind-merge
     bun add -D drizzle-kit @types/node
     ```
  3. Initialize backend directory `services/backend/` and configure Python 3.11+ virtual environment:
     ```bash
     cd services/backend
     python3.11 -m venv .venv
     source .venv/bin/activate
     pip install --upgrade pip
     pip install fastapi uvicorn[standard] celery redis polars duckdb boto3 python-multipart pydantic-settings instructor openai pypdf pdfplumber openpyxl python-calamine
     ```
  4. Create template configuration files with empty values:
     * `apps/web/.env.local` containing all public and private frontend variable names.
     * `services/backend/.env.backend.local` containing database, Redis, local storage path, and OpenAI variable names.
  5. Configure TypeScript paths in `tsconfig.json` (`@/components/*`, `@/lib/*`, `@/db/*`).
  6. Establish local directory storage tree:
     ```bash
     mkdir -p storage/inputs/raw storage/outputs/analysis
     ```
  7. Verify zero-error local boot:
     * Frontend: `bun run dev --port 3000` starts with zero warnings.
     * Backend: `uvicorn app.main:app --port 8000` responds with `{"status": "healthy"}` on `/api/v1/health`.
* **Done Criteria:** Both the Next.js 15 development server and the FastAPI server run on local host bare-metal concurrently with zero compiler warnings, zero dependency conflicts, and zero Docker processes.

---

### Phase 2: Neon PostgreSQL Database Schema & Migrations

* **Goal:** Model all 8 core tables in Drizzle ORM, execute migrations against Neon PostgreSQL, configure Row Level Security (RLS), and seed initial administrative and procedure registry records.
* **Tasks:**
  1. Create `apps/web/src/db/schema.ts` defining all 8 tables specified in Backend Schema v4.0:
     * `users`, `cases`, `case_files`, `rfq_extractions`, `procedure_sublimits`, `demography_records`, `demography_exceptions`, `audit_logs`.
  2. Ensure table `cases` includes dedicated manual input columns:
     * `rater_type`, `brokerage_pct`, `pincode`, `state`, `district`, and auto-derived `zone`.
  3. Ensure table `rfq_extractions` matches the 5-column quote form (`field_name`, `coverage_details`, `proposed_details`, `source_status`, `confidence_rating`/`confidence_score`).
  4. Ensure table `demography_records` matches the 7-column schema (`calculated_age`, `dob`, `sum_insured`, `relationship`, `member_name`, `employee_code`, `gender`).
  5. Create `drizzle.config.ts` linking to Neon serverless PostgreSQL via `DATABASE_URL`.
  6. Generate and run the initial migration:
     ```bash
     bun drizzle-kit generate
     bun drizzle-kit migrate
     ```
  7. Apply Row Level Security (RLS) SQL scripts (`migrations/0001_rls.sql`):
     * Enforce tenant data isolation based on `app.current_user_id` and role permissions.
     * Enforce append-only insert protection on `audit_logs` (prohibiting `UPDATE` and `DELETE`).
  8. Create and run `src/db/seed.ts` seeding:
     * 1 Admin user, 1 Senior Underwriter, 1 Sales RM.
     * Complete 19-procedure master registry across Options 1–4.
     * Master PIN-to-Zone reference table (Zone A, B, C, D, Pan India).
* **Done Criteria:** All 8 tables exist in Neon PostgreSQL with foreign keys and compound indexes verified via `drizzle-kit studio`; RLS policies block unassigned queries; and the 19 procedure sub-limit baselines are queryable.

---

### Phase 3: Clerk Authentication & Closed Invite-Only Authorization Flow

* **Goal:** Integrate Clerk enterprise authentication, block public self-registration, configure protected route middleware, and synchronize user sessions with the Neon `users` table.
* **Tasks:**
  1. Wrap the root Next.js layout in `<ClerkProvider>`.
  2. Implement Next.js 15 middleware (`middleware.ts`):
     * Protect `/dashboard`, `/cases/*`, `/settings`, `/admin/*`.
     * Redirect unauthenticated traffic to `/login?redirect={target_path}`.
     * Restrict `/admin/*` routes strictly to users with role `admin`.
     * Intercept users with `user.metadata.onboarding_completed == false` and route to `/onboarding`.
  3. Configure Clerk dashboard settings:
     * Explicitly disable public sign-ups (invite-only mode).
     * Enable Enterprise SAML / OIDC SSO.
  4. Build the custom `/login` screen utilizing Clerk's `<SignIn />` component.
  5. Implement Clerk webhook receiver (`apps/web/app/api/webhooks/clerk/route.ts`):
     * Listen for `user.created`, `user.updated`, and `user.deleted` events.
     * Upsert user profiles into the Neon `users` table via Drizzle.
  6. Build the token-gated `/invite/accept` screen and the `/onboarding` profile setup screen.
* **Done Criteria:** Public visitors cannot register via `/signup` or `/login`; an administrator-invited user successfully accepts an invitation token, completes profile onboarding, syncs to the Neon `users` table, and accesses `/dashboard`.

---

### Phase 4: Core Feature 1 — Case Ingestion, Local Storage & RAM Decryption

* **Goal:** Build the multi-format case intake API, implement the abstracted storage driver for local filesystem routing, and build the in-memory RAM `tmpfs` password decryption pipeline.
* **Tasks:**
  1. Implement `StorageDriver` interface and `LocalStorageDriver` class in Python backend:
     * Save raw uploads to `./storage/inputs/raw/{case_id}/{timestamp}_{filename}`.
     * Save downstream analysis artifacts to `./storage/outputs/analysis/{case_id}/`.
  2. Build `POST /api/v1/cases` endpoint to initialize case records in PostgreSQL.
  3. Build `POST /api/v1/cases/{case_id}/upload` supporting multipart intake of `.xlsx`, `.xls`, `.csv`, `.pdf`, `.docx`, `.msg`, and images.
  4. Implement file encryption inspector checking for PDF/Excel security dictionaries.
  5. Build the ephemeral in-memory password challenge flow:
     * Frontend prompts user via the Password Decryption Challenge Modal.
     * Password string is transmitted over TLS to `POST /api/v1/cases/{case_id}/decrypt`.
     * Backend decrypts the file stream strictly within volatile memory (`tmpfs` or RAM buffer).
     * The password variable is overwritten with null bytes immediately after stream consumption; zero passwords or decrypted cleartext are written to disk or logs.
  6. Dispatch asynchronous Celery task `process_case_pipeline(case_id)` over Redis.
* **Done Criteria:** Ingesting a mixed package containing a 40-page PDF and a password-locked Excel census stores raw files in `./storage/inputs/raw/{case_id}/`, decrypts the locked census in volatile RAM without disk writes or log leaks, and initiates background processing in Celery.

---

### Phase 5: Core Feature 2 — AI RFQ Extraction Engine (`gpt-5.4-mini`)

* **Goal:** Extract all 80+ GMC fields using `gpt-5.4-mini` via Instructor, separate Current from Proposed terms, split compound clauses, and match procedure sub-limits against the Option 1–4 grid.
* **Tasks:**
  1. Implement document layout parser using `Docling` / `PyMuPDF` to convert multi-page RFQ PDFs and DOCX files into structural Markdown text.
  2. Implement **Pass 1: Structured Extraction Agent (`gpt-5.4-mini`)**:
     * Ingest complete tender text (up to 400,000 tokens) in a single unified prompt context without chunking.
     * Enforce strict JSON Schema output via `instructor` and Pydantic models.
     * Extract fields into `coverage_details`, `proposed_details`, and `verbatim_excerpt` with coordinates (file, page/sheet, cell/line).
  3. Implement **Compound Clause Disaggregator**:
     * Automatically break down compound room rent statements into Parent Room Rent, Normal Room Rent, and ICU Room Rent.
  4. Implement **Pass 2: Reflection & Verification Agent (`gpt-5.4-mini`)**:
     * Cross-check each extracted value strictly against its cited verbatim snippet to eliminate hallucinations.
     * Assign confidence ratings (`High`, `Medium`, `Low`) and flag discrepancies as `Conflict` or `Review Required`.
  5. Implement **Deterministic Procedure Sub-Limit Matcher**:
     * Strip currency noise (`₹`, commas, whitespace) from extracted procedure amounts.
     * Match exact values against the 19 procedures in the Option 1–4 matrix.
     * Non-matching values are preserved as exact numbers and flagged `Unmatched / Review Required`.
  6. Persist results into `rfq_extractions` and `procedure_sublimits` tables.
* **Done Criteria:** Processing an RFQ tender successfully extracts dual-state Current and Proposed terms with exact page coordinates, isolates Normal vs. ICU room rent, matches ₹1,20,000 CABG to Option 2, and marks non-standard amounts as `Review Required`.

---

### Phase 6: Core Feature 3 — Standardized 7-Column Demography Engine

* **Goal:** Ingest client employee rosters, resolve header aliases, dynamically calculate member ages across configurable date bases, and compute derived group metrics using Polars.
* **Tasks:**
  1. Implement fast spreadsheet parser using `python-calamine`.
  2. Build header alias mapper connecting common variants to canonical fields (`employee_code`, `member_name`, `relationship`, `dob`, `age`, `gender`, `sum_insured`).
  3. Implement vectorized Polars demography engine:
     * Standardize date strings to `DD-MM-YYYY`.
     * Calculate completed age using floor logic:
       $$\text{Age} = \left\lfloor \frac{\text{Basis Date} - \text{DOB}}{365.25} \right\rfloor$$
     * Support dynamic basis modes: Mode 1 (`Current Date`) and Mode 2 (`Policy Proposal Start Date`).
     * Fallback to reported age if DOB is absent; raise critical exception if both are missing.
  4. Implement demographic integrity rules:
     * Flag primary workers with $\text{Age} < 18$ (`under18_employee = true`).
     * Flag orphan dependants lacking a corresponding primary employee code.
     * Flag duplicate records matching on `EmpCode` + `Name` + `Relationship`.
     * Flag age/DOB discrepancies where $\vert \text{Source Age} - \text{Calculated Age} \vert > 1$.
  5. Compute derived group metrics:
     * `Group Size` = Total valid member rows.
     * `Number of Primary Members` = Count of `Employee` / `Self` rows.
     * `SME Flag` = `Yes` if Primary Members $\le 250$, else `No`.
  6. Enforce strict 7-column ordering:
     $$\text{Age} \;\vert\; \text{Date of Birth} \;\vert\; \text{Sum Insured} \;\vert\; \text{Relationship} \;\vert\; \text{Name} \;\vert\; \text{EmpCode} \;\vert\; \text{Gender}$$
* **Done Criteria:** Ingesting a 10,000-row census executes in $<1.5$ seconds, flags under-18 workers and orphan dependants, computes SME classification, and toggling the reference date dynamically updates all member ages in memory.

---

### Phase 7: Core Feature 4 — Verification Workbench & Manual Inputs Workflow

* **Goal:** Construct the interactive frontend review workbench featuring the 5-column quote form, 7-column demography grid, inline manual inputs with auto-derived Zone, evidence drawer, and immutable audit logging.
* **Tasks:**
  1. Build the multi-tab layout at `/cases/[id]/*` with URL search-param synchronization via `nuqs`.
  2. Implement the **5-Column Quote Review Grid** (`/cases/[id]/quote`):
     * Columns: `Quote Fields`, `Coverage Details`, `Proposed Details`, `Source Status`, `Confidence`.
     * Render semantic provenance pills (`RFQ Data`, `Default Data`, `Conflict`, etc.).
  3. Implement **Inline Manual Inputs & Auto-Derivation**:
     * Enable direct inline editing for `Rater Type`, `Brokerage %`, `PINCODE`, `State`, and `District`.
     * Implement micro-interaction: Updating `PINCODE` triggers a backend lookup that re-derives `Zone` (e.g., `Zone A`) within 300ms, updates the UI with a subtle pulse animation, and displays a confirmation toast.
  4. Implement the **Slide-Out Source Evidence Inspector Drawer** (500px wide):
     * Clicking any confidence link (`↗`) displays document citations, verbatim snippets, and embedded PDF canvas bounding-box highlights.
  5. Implement the **7-Column Virtualized Demography Grid** (`/cases/[id]/demography`) using `@tanstack/react-virtual` to handle 50,000+ member rows with zero DOM lag.
  6. Build the **Exceptions Triage Queue** (`/cases/[id]/exceptions`) allowing underwriters to resolve unmatched sub-limits and demographic anomalies with mandatory text justifications.
  7. Implement the immutable **Audit Trail** (`/cases/[id]/audit`) recording every user override with timestamp, old value, new value, and reviewer email.
* **Done Criteria:** An underwriter can review terms side-by-side, inspect verbatim PDF evidence in the drawer, edit `Brokerage %` and `PINCODE` with automatic `Zone` updates, override an unmatched sub-limit with justification, and verify that all actions appear in the audit log within 200ms.

---

### Phase 8: Core Feature 5 — Audited Export Engine & Local Storage Archival

* **Goal:** Generate standardized client-ready Excel quotation summaries and clean 7-column demography spreadsheets, automatically archiving them to local storage (and later S3).
* **Tasks:**
  1. Implement `ExcelExportService` using `openpyxl`:
     * Generate `gmc_quote_summary_sheet.xlsx`: Comprehensive corporate quotation workbook containing the 5-column quote form, hospitalization/treatment sub-tables, procedure sub-limits, and underwriter notes.
     * Generate `standardized_demography_7col.xlsx`: Exact 7-column sanitized member roster.
     * Generate `quote_extracted_5col.json` and `exceptions_anomalies.json` machine-readable manifests.
  2. Save all generated outputs to `./storage/outputs/analysis/{case_id}/`.
  3. Build secure file download endpoints (`GET /api/v1/cases/{case_id}/export/{file_type}`).
  4. Log all export actions to `audit_logs`.
* **Done Criteria:** Clicking "Download Reviewed Quote Sheet" generates the reviewed Excel file in $<2$ seconds, streams the download to the browser, archives a permanent copy in `./storage/outputs/analysis/{case_id}/`, and logs the action in the audit trail.

---

### Phase N: UI/UX Clinical Fintech Polish

* **Goal:** Apply the Clinical Fintech design brief, ensuring pixel-perfect alignment with Sora, Geist, and JetBrains Mono typography, custom color palettes, loading skeletons, and responsive viewports.
* **Tasks:**
  1. Configure typography in `layout.tsx`: `Sora` for headings, `Geist` for body copy, and `JetBrains Mono` for financial and demographic data.
  2. Enforce color palette variables: `#0052CC` (Pacific Cobalt), `#0066FF` (Electric Royal CTA), `#F8FAFC` (Canvas), `#0F172A` (Text).
  3. Style all 9 semantic status badges with standard background, text, and border tokens.
  4. Replace plain loading spinners with content-specific shimmer skeletons (`<Skeleton className="h-8 w-full" />`).
  5. Implement empty states with SVG illustrations and primary CTAs for the Dashboard, Exceptions Queue, and Audit Log.
  6. Add smooth 150ms ease-out transitions (`transition: all 150ms cubic-bezier(0.16, 1, 0.3, 1)`) on interactive controls, modal overlays, and drawer animations.
  7. Verify responsive breakpoints (collapsible sidebar for tablet/mobile, scrollable tables with sticky first columns).
* **Done Criteria:** The application presents a unified, clinical fintech aesthetic with zero layout shifts, smooth 150ms interactions, correct font pairings, and responsive rendering across desktop, laptop, and tablet screens.

---

### Phase N+1: Testing, Hardening & Local Edge-Case Verification

* **Goal:** Subject the platform to edge-case stress testing, demographic anomaly validation, security audits, and automated unit/integration suites on the local environment.
* **Tasks:**
  1. Write Python Pytest suite for the demography engine:
     * Test leap-year birth dates, missing DOBs, inverted dates (`MM/DD/YYYY` vs. `DD/MM/YYYY`), and 50,000-row batch benchmarks.
  2. Write Pytest suite for the procedure sub-limit matcher:
     * Test exact matching for all 19 procedures across Options 1–4.
     * Test handling of non-standard amounts (e.g., ₹33,000 Appendectomy correctly flagged as `Unmatched`).
  3. Write Playwright/Jest integration tests for:
     * Clerk auth route protection and invite-only acceptance flow.
     * 5-column quote form rendering and inline edits to `Brokerage %`, `PINCODE`, and auto-derived `Zone`.
     * Dynamic age recalculation when switching between `Current Date` and `Proposal Date`.
  4. Audit zero-persistence password decryption:
     * Verify that transient decryption buffers are wiped immediately after processing and zero passwords or credentials appear in log dumps.
* **Done Criteria:** Automated test suites pass with $\ge 90\%$ code coverage; stress tests process 50,000 demography rows in $<2$ seconds; and zero password strings appear in log dumps.

---

### Phase N+2: AWS S3 Promotion, Corporate Proxy Upgrade & EC2 On-Server Dockerization

* **Goal:** Promote storage from local filesystem to AWS S3, configure corporate outbound forward proxies, transfer source artifacts to the AWS EC2 instance, and build/run Docker containers on the server.
* **Tasks:**
  1. **Storage Promotion:**
     * Switch `STORAGE_DRIVER=s3` in backend configuration.
     * Activate `S3StorageDriver` targeting `s3://{BUCKET}/inputs/raw/{case_id}/` and `s3://{BUCKET}/outputs/analysis/{case_id}/`.
  2. **Corporate Forward Proxy Configuration on EC2:**
     * Configure host proxy variables in `/etc/environment`:
       ```bash
       HTTP_PROXY="http://proxy.corporate.internal:8080"
       HTTPS_PROXY="http://proxy.corporate.internal:8080"
       NO_PROXY="localhost,127.0.0.1,169.254.169.254,local.net,.internal,gmc_internal_network"
       ```
     * Configure Docker daemon proxy in `/etc/systemd/system/docker.service.d/http-proxy.conf`.
     * Configure Docker CLI proxy in `~/.docker/config.json`.
     * Verify outbound TLS connectivity via proxy: `curl -I https://api.openai.com`.
  3. **Codebase Artifact Transfer:**
     * Transfer validated repository artifacts to the EC2 host at `/opt/gmc-quote-automation`.
  4. **On-Server Multi-Container Docker Build:**
     * Execute on-server container build with proxy build arguments:
       ```bash
       cd /opt/gmc-quote-automation/deploy
       docker compose -f docker-compose.prod.yml --env-file .env build --no-cache
       ```
  5. **Launch Production Container Stack:**
     * Launch multi-container services (`caddy`, `web`, `api`, `worker`, `redis`):
       ```bash
       docker compose -f docker-compose.prod.yml --env-file .env up -d
       ```
  6. **Run Production Migrations:**
     * Run Drizzle migrations on the production container:
       ```bash
       docker compose -f docker-compose.prod.yml exec web bun drizzle-kit migrate
       ```
  7. **Verify Production Health & Egress:**
     * Verify Caddy automatic TLS/SSL certificate issuance.
     * Test `/api/v1/health` verifying database, Redis, S3 bucket access, and OpenAI egress via the corporate forward proxy.
* **Done Criteria:** All five containers show `Up (healthy)` in `docker ps`; Caddy serves the application over trusted HTTPS; external API calls to OpenAI and AWS S3 route successfully through the corporate proxy; and the health check endpoint returns status `healthy`.

---

## Project "Done" Criteria (Definition of Finished)

The entire project is formally accepted and ready for production handoff when all of the following conditions are met:

1. **End-to-End User Journeys Pass:**
   * A Sales RM can upload a mixed package (scanned PDF + password-locked Excel), decrypt the file in memory, edit `Rater Type`, `Brokerage %`, `PINCODE`, `State`, and `District` (with instant `Zone` re-calculation), and export a finalized quote sheet in under 3 minutes.
   * An Underwriter can review side-by-side terms in the 5-column quote grid, inspect verbatim PDF evidence in the 500px drawer, override an unmatched sub-limit with mandatory justification, and verify the immutable audit entry.
   * An Operations Analyst can switch demography age basis between *Current Date* and *Proposal Start Date*, triggering sub-second recalculation across all member records.
2. **Performance SLAs:**
   * API response time $<500\text{ ms}$ for all workbench operations.
   * Demographic processing $<1.5\text{ seconds}$ for 10,000 member rows.
   * End-to-end AI document extraction completed in $<45\text{ seconds}$ for a 40-page RFQ package using `gpt-5.4-mini`.
3. **Data Integrity & Security:**
   * Raw client uploads are stored exclusively under `inputs/raw/{case_id}/` and processed artifacts under `outputs/analysis/{case_id}/` (locally in Stage 1, on S3 in Stage 2).
   * Zero decrypted bytes and zero password strings are written to persistent disk or logged.
   * Audit log records are strictly immutable (enforced by PostgreSQL RLS).
4. **Operational Stability:**
   * Zero unresolved console errors in production browser builds.
   * All Docker containers run as non-root users behind the Caddy reverse proxy on AWS EC2.
   * Outbound corporate egress proxy operates reliably with automated retry policies.