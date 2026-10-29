# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. App Name & One-Sentence Tagline

* **App Name:** **QuotePulse GMC**
* **Tagline:** *"Transform messy broker RFQs and employee censuses into validated, underwriter-ready quotes in under three minutes."*

---

## 2. The Problem Being Solved & Who Feels It

### The Problem
Preparing Group Mediclaim (GMC) insurance quotations is a complex, high-latency underwriting bottleneck. Broker RFQ/RFP packs arrive across disparate communication channels as multi-tab Excel files, scanned PDFs, Word documents, and emails with no standardized naming conventions or layouts. Critical policy conditions (such as room rent tiers combined with ICU caps, or maternity waiting period waivers linked to corporate buffers) are buried inside lengthy narrative clauses. Simultaneously, client demography rosters contain non-uniform headers, missing dates of birth, inverted dates, duplicate entries, invalid relationship labels, and uncalculated or conflicting ages.

### Who Feels It
* **Relationship Managers / Sales Underwriting Associates:** Spend 3 to 6 hours per quote manually transcribing terms and copying roster rows into quoting templates.
* **Senior Underwriters:** Spend valuable risk-assessment time hunting for source clauses in 40-page PDF packs to verify whether extracted sub-limits conform to underwriting guidelines.
* **Operations Leaders:** Face lost business from high turnaround times (TAT), delayed quotation SLA breaches, and data-entry errors that propagate into policy issuance and claim disputes.

---

## 3. Core Value Proposition — What Makes This Different

Unlike generic document parsers or simple OCR utilities, **QuotePulse GMC** is a domain-specialized, human-in-the-loop underwriting copilot:

1. **Dual-State Clause Disaggregation:** Automatically separates **Current/Expiring Terms** from **Proposed/Requested Terms**, breaking down compound clauses into granular sub-benefits.
2. **Deterministic Registry Grounding:** Maps unstructured procedure limits to an approved 4-tier sub-limit schedule (Options 1–4) without hallucinatory rounding.
3. **Traceable Source Evidence:** Backs every populated field with verifiable coordinates (file name, page/sheet, cell/line, and verbatim snippet).
4. **High-Performance Vectorized Census Engine:** Cleans, maps, recalculates age based on configurable date modes, and standardizes 100,000+ member demographic records in seconds while enforcing zero-persistence password decryption.
5. **Progressive Delivery & Deployment Model:** Engineered to be built and verified **100% locally first** with zero external cloud blockers, followed by a hardened final phase adding S3 bucket archiving, enterprise forward proxy traversal, and on-server EC2 Dockerization.

---

## 4. Target User Personas

* **Priya Sharma (Corporate Sales / Relationship Manager):** Manages tight broker turnaround SLAs. Needs to upload messy multi-format RFQ packages, quickly enter and edit manual parameters (e.g., **Brokerage %**, **Rater Type**, **PINCODE**, **State**, and **District**), verify extracted company details, and export quote and demographic sheets to meet client deadlines.
* **Rajesh Iyer (Senior GMC Underwriter):** Evaluates risk profiles, non-standard terms, and policy exclusions. Needs to quickly inspect flagged exceptions, review conflicting or unmapped clauses with source evidence, approve procedure sub-limits, and refer high-risk exposures.
* **Neha Kulkarni (Insurance Operations Analyst):** Responsible for data sanity and downstream core system onboarding. Needs clean demography rosters adhering strictly to the standardized 7-column schema, with employee-dependency links and under-18 flags resolved before pricing and policy issuance.

---

## 5. Strategic Development & Delivery Phasing

To guarantee rapid development velocity and eliminate external infrastructure friction, the engineering lifecycle is divided into two distinct gates:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   STAGE 1: 100% LOCAL BUILD & VERIFY                   │
│ • Local filesystem storage for uploads and outputs                     │
│ • Local bare-metal Bun (Next.js 15) + Python 3.11 (FastAPI + Celery)   │
│ • Direct OpenAI API calls (gpt-5.4-mini) & local Redis/PostgreSQL      │
│ • Complete UI verification: 5-column quote form & 7-column demography  │
│ • Full end-to-end testing with real RFQ/census test packs              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Once 100% Tested & Approved
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             STAGE 2: ENTERPRISE INFRASTRUCTURE & EC2 DEPLOY            │
│ • S3 Dual-Prefix Pipeline (inputs/raw/ -> outputs/analysis/)           │
│ • Corporate Forward Egress Proxy setup (HTTP_PROXY / HTTPS_PROXY)      │
│ • Source artifact transfer to AWS EC2 host                             │
│ • Multi-container Dockerization (Docker Compose build on EC2)          │
└────────────────────────────────────────────────────────────────────────┘
```

* **Gate 1 (Local-First 100% Functional):** Build and test the full application locally without cloud dependencies. File uploads and exports use a local storage provider. All 5 quote columns, 7 demography columns, and manual edit workflows are verified end-to-end.
* **Gate 2 (Cloud & Production Hardening):** Swap the local storage provider for AWS S3 dual-prefix buckets, configure corporate outbound proxy rules for external network calls, deploy artifacts to the target AWS EC2 instance, and build/run the production Docker containers on the server.

---

## 6. Feature Specifications & Core Modules

### 6.1 Multi-Format Case Intake & Ephemeral Decryption
* **Supported Formats:** Concurrent intake of `.xlsx`, `.xls`, `.csv`, `.pdf` (digital and scanned), `.docx`, `.msg`, `.eml`, and snapshot images.
* **Zero-Persistence Password Decryption:** In-memory file decryption challenge for locked files. Passwords are consumed in volatile RAM only and are **never** logged, written to disk, or saved to the database.
* **Document Classifier:** Automated classification into `RFQ_DOCUMENT`, `DEMOGRAPHY_FILE`, or `SUPPORTING_INFO`.

---

### 6.2 RFQ Extraction & Review Grid (Strict 5 Columns)
The primary review interface at `/cases/[id]/quote` renders a structured grid containing exactly five columns:

$$\text{Col 1: Quote Fields} \;\vert\; \text{Col 2: Coverage Details} \;\vert\; \text{Col 3: Proposed Details} \;\vert\; \text{Col 4: Source Status} \;\vert\; \text{Col 5: Confidence}$$

* **Column Definitions:**
  1. **Quote Fields:** The canonical field label from the GMC Field Registry (e.g., Sum Insured, Normal Room Rent, PED).
  2. **Coverage Details:** The current or expiring policy term extracted from the RFQ pack.
  3. **Proposed Details:** The requested or renewal policy term requested by the client/broker.
  4. **Source Status:** Categorical badge indicating provenance: `RFQ Data`, `Default Data`, `AI Derived`, `Demography Derived`, `Manual`, `Fixed`, `Not Found`, `Ambiguous`, `Conflict`, or `Review Required`.
  5. **Confidence:** Explicit quality indicator: `High`, `Medium`, or `Low` (accompanied by an expandable reason and verbatim snippet).

* **Manual Input / Override Fields:**
  The following five fields are designated as editable manual inputs directly on the Quote Form:
  * **`Rater Type`:** Text input (allows manual entry/override; defaults to system placeholder `-`).
  * **`Brokerage %`:** Numeric percentage input (e.g., `5.00%`).
  * **`PINCODE`:** 6-digit postal code input (auto-extracted if present, fully editable by user).
  * **`State`:** Dropdown / text input (auto-extracted or manually set).
  * **`District`:** Dropdown / text input (auto-extracted or manually set).
  * *Note:* Editing `PINCODE`, `State`, or `District` triggers automatic re-evaluation of the derived **`Zone`** field against the internal Zone Master.

---

### 6.3 Standardized Demography Engine (Strict 7 Columns)
The census processing engine standardizes uploaded rosters and generates a preview grid and export spreadsheet containing exactly seven columns in this sequence:

$$\text{Col 1: Age} \;\vert\; \text{Col 2: Date of Birth} \;\vert\; \text{Col 3: Sum Insured} \;\vert\; \text{Col 4: Relationship} \;\vert\; \text{Col 5: Name} \;\vert\; \text{Col 6: EmpCode} \;\vert\; \text{Col 7: Gender}$$

* **Header Normalization:** Automatically maps disparate source column headers (e.g., `Token No`, `Associate Code`, `SI Opted`, `EMP DOB`) to internal canonical fields.
* **Dynamic Age Calculation:**
  * Mode A: `Current Date` (system timestamp).
  * Mode B: `Policy Proposal Start Date` (selected by underwriter via date picker).
  * Formula: Completed years via floor calculation:
    $$\text{Age} = \left\lfloor \frac{\text{Basis Date} - \text{DOB}}{365.25} \right\rfloor$$
  * Dynamic toggle triggers instant recalculation of all rows via vectorized Polars operations.
* **Integrity Guardrails:**
  * Flags primary employees under 18 years old (`under18_employee = true`).
  * Flags orphan dependants lacking an employee code match.
  * Identifies duplicate records across identical `EmpCode` + `Name` + `Relationship`.
* **Derived Metrics Generation:**
  * `Group Size` = Total valid member rows.
  * `Number of Primary Members` = Count of rows where Relationship is `Employee` or `Self`.
  * `SME Flag` = `Yes` if Primary Members $\le 250$; else `No`.

---

### 6.4 Procedure Sub-Limit Option Matcher (19 Procedures)
* Ingests surgical procedures, strips currency symbols (`₹`, `INR`, commas, whitespace), and matches amounts deterministically against the 4-tier matrix (Options 1–4):
  * **Option 1–4 Procedures:** CABG, Valve Replacement, PTCA, Total Knee Replacement, Total Hip Replacement, Arthroscopic Surgeries, Cholecystectomy, Kidney Stone Removal, Appendectomy, Hysterectomy, Fistulectomy, Septoplasty, Hernia Repair, Haemorrhoidectomy, Tympanoplasty, Arthroscopy, Cataract (one eye), Tonsillectomy, Dialysis (per session).
* **Mismatch Handling:** If an amount deviates from standard options (e.g., Cataract at ₹30,000), the system preserves the raw extracted amount, tags the record as `Unmatched / Review Required`, and routes it to the Exceptions Queue.

---

### 6.5 Downstream Artifact Generation & Exports
* **Reviewed Quote Excel:** Generates an underwriter-ready workbook containing the 5-column quote form, hospitalization/treatment sub-tables, procedure sub-limits, and underwriter notes.
* **Clean Demography Excel:** Generates an operational census sheet strictly formatted with the 7 standardized columns.
* **Audit Trail JSON:** Logs every manual override (including edits to Brokerage, Rater Type, PINCODE, State, and District) with user email, timestamp, old value, and new value.

---

## 7. Explicit Out-of-Scope List (v1)

1. Actuarial rate calculation, burning cost modeling, and final premium pricing.
2. Generating final binding policy schedules or certificates of insurance (COIs).
3. Direct automated debiting or payment gateway integration for premium collection.
4. Downstream health claims pre-authorization or claims adjudication processing.
5. Ingesting handwritten doctor prescriptions or clinical hospital discharge summaries.

---

## 8. User Stories (Agile Format)

| ID | Persona | User Story | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **US-01** | Relationship Manager | **As an** RM, **I want to** upload multi-format RFQ packages and locked census files locally during development, **so that** I can test the full pipeline before server deployment. | Files upload and process locally; locked files prompt for password and decrypt in transient RAM. |
| **US-02** | Underwriter | **As an** Underwriter, **I want to** see a strict 5-column review table (`Quote Fields`, `Coverage Details`, `Proposed Details`, `Source Status`, `Confidence`), **so that** I can evaluate policy terms with complete source provenance. | Workbench renders all 5 columns; clicking any row reveals verbatim source text and page coordinates. |
| **US-03** | Relationship Manager | **As an** RM, **I want to** manually enter or edit `Rater Type`, `Brokerage %`, `PINCODE`, `State`, and `District`, **so that** I can complete client details even if they are missing from the broker PDF. | The 5 fields are editable inline; entering a PINCODE recalculates the derived `Zone` within 300ms; changes are logged to the audit trail. |
| **US-04** | Operations Analyst | **As an** Operations Analyst, **I want** the demography roster standardized into exactly 7 columns (`Age`, `Date of Birth`, `Sum Insured`, `Relationship`, `Name`, `EmpCode`, `Gender`), **so that** downstream systems receive clean, uniform data. | Export file contains exactly these 7 columns in exact sequence; dates formatted as `DD-MM-YYYY`. |
| **US-05** | Underwriter | **As an** Underwriter, **I want to** toggle between 'Current Date' and 'Policy Proposal Start Date' for age calculations, **so that** age brackets reflect the actual policy risk inception date. | Changing the date-basis recalculates all member ages in memory in $<1.5$ seconds using the completed-year floor formula. |
| **US-06** | Senior Underwriter | **As a** Senior Underwriter, **I want** non-matching surgical sub-limits routed to an Exceptions Queue, **so that** I can authorize specific broker concessions with written justification. | Unmatched procedure amounts remain unrounded and flagged `Review Required`; overriding updates status and requires an underwriter note. |
| **US-07** | DevOps / Engineer | **As an** Engineer, **I want** the system built and tested 100% locally first before configuring S3, proxy, and EC2 Docker, **so that** development is not blocked by cloud network permissions. | All unit, integration, and UI tests pass on local host runtimes; switching an environment flag activates S3 and proxy handling for EC2. |

---

## 9. Success Metrics (Measurable & Time-Boxed)

| Metric | Baseline (Manual) | Target (Local Phase Done) | Target (EC2 Prod, 60 Days) |
| :--- | :--- | :--- | :--- |
| **Quote Prep Turnaround Time (TAT)** | 240 minutes (4 hours) | $\le 10$ minutes (local run) | $\le 3$ minutes (end-to-end) |
| **Extraction Accuracy (Digital RFQ)** | $\sim 85\%$ (human transcribing) | $\ge 98\%$ (`gpt-5.4-mini`) | $\ge 98\%$ verified |
| **Demography Recalculation Speed** | 45 minutes per 5,000 lives | $\le 1.5$ seconds (Polars) | $\le 1.5$ seconds (Polars) |
| **Manual Data-Entry Time** | 30 minutes | $\le 45$ seconds (5 fields) | $\le 45$ seconds |
| **Security & Decryption Compliance** | Potential cleartext leaks | 0 bytes written to disk | 0 credentials logged |

---

## 10. AI & LLM Integration Architecture (`gpt-5.4-mini`)

| Pipeline Component | Model / Engine | Purpose & Responsibilities | Prompting & Execution Strategy | Guardrail & Fallback Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Document Classification** | `gpt-5.4-mini` (or regex heuristics) | Classify files into RFQ, Demography, or Supporting. | Top-2000 character sample classification. | Fallback to manual selection if confidence $<0.85$. |
| **Core Clause Extraction** | **`gpt-5.4-mini`** (OpenAI) | Extract all 80+ registry fields, disaggregate Current vs. Proposed terms, and decompose compound clauses. | Single-pass prompt ingesting up to 400k tokens of Markdown text via `instructor` with strict JSON Schema. | Max 3 retries; if schema validation fails, tag field as `Review Required`. |
| **Reflection & Evidence Verifier** | **`gpt-5.4-mini`** (OpenAI) | Secondary validation pass cross-checking extracted values against cited verbatim snippets. | Verification prompt: *"Does the verbatim snippet explicitly support the extracted value? Answer YES/NO with reasoning."* | If NO or ambiguous, demote status to `Conflict` or `Review Required`. |
| **Sub-Limit Matcher** | **Deterministic Python Engine** | Normalize procedure amounts and match against Options 1–4. | Strips non-numeric characters; strict lookup against 19-procedure matrix. | Mismatches remain exact numbers; never round or force-map. |
| **Demography Normalizer** | **Polars / DuckDB** | 7-column ordering, date parsing, completed-year age calculation, family-tier linking. | In-memory vectorized columnar execution. Zero LLM involvement. | Missing DOB + Age flags a critical row exception. |

---

## 11. Phased Rollout & Infrastructure Transition Plan

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASE A: LOCAL-FIRST BUILD                      │
│                                                                        │
│  1. Run Next.js 15 App Router natively via Bun (Port 3000)             │
│  2. Run FastAPI and Celery natively via Python 3.11 venv (Port 8000)   │
│  3. Use local filesystem (`./storage/inputs/`, `./storage/outputs/`)   │
│  4. Connect directly to OpenAI API (gpt-5.4-mini)                      │
│  5. Validate 5-column quote form and 7-column demography engine        │
│  6. Validate manual entry: Rater Type, Brokerage %, PINCODE,           │
│     State, District                                                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Once 100% verified locally
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PHASE B: CLOUD & PROXY UPGRADE                       │
│                                                                        │
│  1. Enable S3 storage client (`inputs/raw/` -> `outputs/analysis/`)   │
│  2. Configure corporate forward proxy (`HTTP_PROXY`, `HTTPS_PROXY`)    │
│  3. Verify outbound proxy routes to `api.openai.com` and S3 endpoints  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               PHASE C: AWS EC2 ON-SERVER DOCKERIZATION                 │
│                                                                        │
│  1. Transfer codebase artifacts to AWS EC2 instance                    │
│  2. Build production Docker images directly on the EC2 host            │
│  3. Launch containers: Caddy, Web (Next.js 15), API, Worker, Redis     │
│  4. Run database migrations via Drizzle ORM                            │
│  5. Validate production health check on `https://{DOMAIN}/api/health` │
└────────────────────────────────────────────────────────────────────────┘
```