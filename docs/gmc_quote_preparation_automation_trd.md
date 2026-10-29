# TECHNICAL REQUIREMENTS DOCUMENT (TRD)
## GMC Quote Preparation Automation Platform
### Enterprise Architecture, Data Contracts, Dual-Environment Lifecycle & Production Engineering Blueprint

---

## Document Control

| Attribute | Specification |
| :--- | :--- |
| **Document Type** | Technical Requirements Document (TRD) — Master Engineering Reference |
| **Document Version** | 4.0 (Enterprise Local-First & EC2 Dockerized Edition) |
| **Date** | 29 October 2026 |
| **Status** | Approved Immutable Technical Blueprint for Development |
| **Associated Documents** | `GMC_Quote_Preparation_Automation_BRD.md` (v3.0), `GMC_Quote_Preparation_PRD.md` (v2.0) |
| **Runtime Platforms** | **Stage 1 (Local):** Bun 1.x + Python 3.11+ (Bare-Metal, Zero Local Docker)<br>**Stage 2 (EC2):** AWS EC2 Multi-Container Docker (Built On-Server) |
| **Inference Source** | OpenAI `gpt-5.4-mini` (400,000-token context, JSON Schema Structured Outputs) |
| **Database & ORM** | PostgreSQL 16 (Neon / AWS RDS) with Drizzle ORM |
| **Storage Architecture** | Swappable Provider: Local Filesystem $\longrightarrow$ AWS S3 (`inputs/raw/` and `outputs/analysis/`) |
| **Network Egress** | Corporate Forward HTTP/HTTPS Outbound Proxy on AWS EC2 |

---

## 1. Executive Technical Summary & Guiding Principles

### 1.1 Core System Objectives
The GMC Quote Preparation Automation Platform converts heterogeneous, multi-format tender packs and dirty census rosters into audited, client-ready quotation sheets in under 3 minutes. The technical foundation balances rapid developer velocity with zero-leakage security, deterministic actuarial precision, and clean cloud migration.

### 1.2 Guiding Engineering Principles
1. **Single Runtime Mandate (Bun & Python):** No runtime pollution. Bun 1.x is strictly pinned for all frontend tooling, builds, package resolutions, and Next.js execution (no mixing with npm/yarn/pnpm). Python 3.11+ is dedicated to data processing and AI orchestration.
2. **Local-First 100% Autonomy (Stage 1):** The entire application is developed, run, and verified locally on bare-metal with zero Docker dependencies, using local storage drivers and direct API access.
3. **Seamless Cloud & Production Promotion (Stage 2):** After full local sign-off, the storage adapter shifts to AWS S3 (`inputs/raw/` and `outputs/analysis/`), corporate forward proxy rules are activated for egress, and containers are built directly on the target AWS EC2 instance.
4. **Deterministic Actuarial Partitioning:** AI (`gpt-5.4-mini`) is strictly confined to unstructured linguistic comprehension, dual-state separation, and citation grounding. Mathematical transformations (census age calculation, SME categorization, 4-tier sub-limit matching, zone resolution) are executed deterministically via vectorized Polars and Python rule engines.
5. **Zero-Persistence Password Decryption:** Passwords for encrypted client files are consumed in transient RAM (`tmpfs`) during active processing and wiped immediately. Zero unencrypted bytes and zero password strings touch disk or persistent logs.

---

## 2. Technology Stack & Component Inventory

| Architectural Tier | Selected Technology | Version / Spec | Justification & Boundaries |
| :--- | :--- | :--- | :--- |
| **Frontend Runtime** | **Bun** | `1.1.x` | High-performance JS/TS runtime, package manager, and bundler. Native speed; single runtime standard. |
| **Frontend Framework** | **Next.js (App Router)** | `15.x` | Server Components (RSC) for dashboard shells; Client Components for virtual grids; Server Actions for data mutations. Pages Router is forbidden. |
| **Styling & Design Kit** | **Tailwind CSS + shadcn/ui** | `v4.x` / Radix | Utility-first CSS theme directives; zero legacy runtime CSS-in-JS overhead; accessible headless primitives. |
| **Data Grid Engine** | **TanStack Table + Virtual** | `v8.x` / `@tanstack/react-virtual` | Virtualized DOM rendering capable of scrolling 100,000+ member rows smoothly without layout thrashing. |
| **State & Data Fetching** | **TanStack Query** | `v5.x` (`@tanstack/react-query`) | Asynchronous server-state management, optimistic mutations, background cache invalidation. |
| **URL State Manager** | **nuqs** | Latest | Type-safe URL query-parameter state synchronization for active tabs, table filters, and search queries. |
| **Validation Schema** | **Zod** | `v3.x` | Full-stack TypeScript validation for forms, Server Actions, and API boundaries. |
| **Backend Runtime** | **Python** | `3.11+` | Dedicated to async REST APIs, distributed task workers, document OCR, and vectorized census math. |
| **Backend Framework** | **FastAPI** | `0.110+` | Asynchronous ASGI routing, native OpenAPI generation, dependency injection, and Pydantic v2 schemas. |
| **Task Queue & Broker** | **Celery + Redis** | Celery `5.4+` / Redis `7.2` | Distributed asynchronous background execution for long-running document OCR, AI parsing, and census processing. |
| **Vectorized Census** | **Polars / DuckDB** | Polars `1.x` | Vectorized columnar execution engine in Rust/C++; recalculates 100,000 census records in $<1.5$ seconds. |
| **AI LLM Inference** | **OpenAI `gpt-5.4-mini`** | API (`2026-03`) | 400,000-token native context window; single-pass multi-file ingestion; strict JSON Schema Structured Outputs via `instructor`. |
| **Database & ORM** | **Neon PostgreSQL + Drizzle** | Postgres 16 / Drizzle ORM | Serverless PostgreSQL with connection pooling. Drizzle provides TypeScript-first schema modeling and zero cold-start overhead. |
| **Authentication** | **Clerk** | `@clerk/nextjs` | Enterprise identity management, SAML SSO, MFA, invite-only token gating, and organization RBAC. Public sign-up is disabled. |
| **Production Proxy** | **Caddy / NGINX** | Caddy `2.8` | Reverse proxy on EC2; automated Let's Encrypt TLS/SSL certificate issuance and header management. |

---

## 3. End-to-End System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   PRESENTATION LAYER (NEXT.JS 15)                                │
│                     Next.js 15 App Router (Bun 1.x)  •  TanStack Table v8 Virtual                │
│                                                                                                  │
│   ┌──────────────────────────────────────────────┐    ┌──────────────────────────────────────┐   │
│   │  5-Column Quote Form Grid                    │    │  7-Column Demography Roster Grid     │   │
│   │  [Quote Fields | Current | Proposed |        │    │  [Age | DOB | SI | Relationship |    │   │
│   │   Source Status | Confidence]                │    │   Name | EmpCode | Gender]           │   │
│   └──────────────────────────────────────────────┘    └──────────────────────────────────────┘   │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │  Editable Overrides: Rater Type, Brokerage %, PINCODE, State, District (Auto Zone Recalc)│   │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬────────────────────────────────────────────────────────────────┘
                                  │ HTTPS / WebSocket (SSE)
┌─────────────────────────────────▼────────────────────────────────────────────────────────────────┐
│                                   APPLICATION & INGESTION SERVICES                               │
│                      FastAPI Async Gateway  •  Celery Task Distribution Pipeline                 │
└───────┬───────────────────────────┬────────────────────────────┬─────────────────────────┬───────┘
        │                           │                            │                         │
        ▼                           ▼                            ▼                         ▼
┌──────────────────┐    ┌───────────────────────────┐    ┌───────────────┐         ┌───────────────┐
│ Ingestion Layer  │    │ AI Pipeline (gpt-5.4-mini)│    │ Demography    │         │ S3 / Storage  │
│ • PyMuPDF/Docling│    │ • 400k Context Single Pass│    │ Engine        │         │ Pipeline      │
│ • python-calamine│    │ • Pass 1: Extraction      │    │ • Polars Rust │         │ • inputs/     │
│ • RAM tmpfs      │    │ • Pass 2: Verifier        │    │ • Completed-  │         │   raw/        │
│   Decryption     │    │ • Strict JSON Schemas     │    │   Year Floor  │         │ • outputs/    │
└──────────────────┘    └───────────┬───────────────┘    │ • SME Status  │         │   analysis/   │
                                    │                    └───────┬───────┘         └───────────────┘
                                    ▼                            │
┌────────────────────────────────────────────────────────────────┴─────────────────────────────────┐
│                            DETERMINISTIC POST-PROCESSING & AUDIT ENGINE                          │
│  • Procedure Sub-Limit Normalizer: Strips currency noise $\rightarrow$ Maps Options 1–4         │
│  • Geographical Zone Matcher: Evaluates PINCODE/District against Zone Master Master              │
│  • Immutable PostgreSQL Audit Log: Captures user, timestamp, old/new value, and reason           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Dual-Environment Architecture (Local-First $\rightarrow$ AWS EC2)

### 4.1 Stage 1: 100% Local Development (Bare-Metal, Zero Docker)
Local development operates without Docker containers. All tools run on native host runtimes:
* **Frontend:** Executed directly via `bun run dev --port 3000`.
* **Backend:** Executed within Python 3.11 virtual environment (`uvicorn app.main:app --reload --port 8000`).
* **Task Queue:** Celery worker executed via `celery -A app.tasks.worker worker --loglevel=INFO`.
* **Redis:** Native service instance (`brew services start redis` or `sudo systemctl start redis`).
* **Database:** Connects directly to Neon PostgreSQL cloud instance over TLS.
* **Storage Driver:** Implements `LocalStorageProvider`, storing files locally under `./storage/inputs/raw/{case_id}/` and `./storage/outputs/analysis/{case_id}/`.
* **AI Access:** Direct HTTPS egress to OpenAI API (`api.openai.com`) without corporate proxy wrappers.

### 4.2 Stage 2: AWS EC2 Server Deployment (On-Server Dockerization)
When promoted to production on AWS EC2 (`c6i.2xlarge`, Ubuntu 24.04 LTS):
* **Source Artifact Transfer:** Codebase transferred via Git or deployment tarball directly to `/opt/gmc-quote-automation`.
* **On-Server Image Build:** Images are built directly on the EC2 host via Docker Compose, passing corporate proxy arguments to prevent build network timeouts.
* **Storage Driver:** Shifts automatically to `S3StorageProvider` pointing to the secure enterprise AWS S3 bucket.
* **Corporate Egress Proxy:** Host OS, Docker daemon, and containers route outbound HTTP/HTTPS traffic through the corporate forward proxy.

---

## 5. Storage Lifecycle & S3 Dual-Prefix Pipeline

The storage layer isolates raw, unedited client files from analyzed underwriting outputs using a swappable interface contract.

```
storage_root/ (or s3://{GMC_S3_BUCKET_NAME}/)
├── inputs/
│   └── raw/
│       └── {case_id}/
│           ├── timestamp_01_RFQ_Document.pdf
│           ├── timestamp_02_Employee_Census.xlsx
│           └── timestamp_03_Addendum_Terms.docx
│
└── outputs/
    └── analysis/
        └── {case_id}/
            ├── quote_extracted_terms.json
            ├── standardized_demography_7col.xlsx
            ├── gmc_quote_summary_sheet.xlsx
            ├── sublimit_matching_report.json
            ├── exceptions_and_anomalies.json
            └── audit_trail_changelog.json
```

### 5.1 Storage Provider Contract (`services/backend/app/services/storage.py`)
```python
import abc
import io
import os
import boto3
from botocore.config import Config
from app.core.config import settings

class BaseStorageProvider(abc.ABC):
    @abc.abstractmethod
    def save_raw_input(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        pass

    @abc.abstractmethod
    def get_raw_input_stream(self, file_key: str) -> io.BytesIO:
        pass

    @abc.abstractmethod
    def save_analysis_output(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        pass

class LocalStorageProvider(BaseStorageProvider):
    """Used in Stage 1: 100% Local Bare-Metal Development."""
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = base_dir

    def save_raw_input(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        path = os.path.join(self.base_dir, "inputs", "raw", case_id, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def get_raw_input_stream(self, file_key: str) -> io.BytesIO:
        with open(file_key, "rb") as f:
            return io.BytesIO(f.read())

    def save_analysis_output(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        path = os.path.join(self.base_dir, "outputs", "analysis", case_id, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

class S3StorageProvider(BaseStorageProvider):
    """Used in Stage 2: AWS EC2 Production Deployment."""
    def __init__(self):
        self.bucket = settings.GMC_S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                proxies={"http": settings.HTTP_PROXY, "https": settings.HTTPS_PROXY} if settings.HTTP_PROXY else None
            )
        )

    def save_raw_input(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        key = f"inputs/raw/{case_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
            ServerSideEncryption="AES256", Metadata={"case_id": case_id, "stage": "raw_upload"}
        )
        return key

    def get_raw_input_stream(self, file_key: str) -> io.BytesIO:
        res = self.client.get_object(Bucket=self.bucket, Key=file_key)
        return io.BytesIO(res["Body"].read())

    def save_analysis_output(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        key = f"outputs/analysis/{case_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
            ServerSideEncryption="AES256", Metadata={"case_id": case_id, "stage": "analyzed_output"}
        )
        return key

def get_storage_provider() -> BaseStorageProvider:
    return S3StorageProvider() if settings.STORAGE_BACKEND == "s3" else LocalStorageProvider()
```

---

## 6. Corporate Forward Proxy Configuration (AWS EC2 Egress)

In production, the EC2 instance resides in a restricted corporate VPC. Outbound requests to `api.openai.com`, Clerk, or external AWS endpoints must route through the corporate HTTP/HTTPS forward proxy.

### 6.1 Host OS Configuration (`/etc/environment`)
```bash
HTTP_PROXY="http://proxy.corporate.internal:8080"
HTTPS_PROXY="http://proxy.corporate.internal:8080"
NO_PROXY="localhost,127.0.0.1,169.254.169.254,local.net,.internal,gmc_internal_network"
```

### 6.2 Docker Daemon Proxy (`/etc/systemd/system/docker.service.d/http-proxy.conf`)
Required so Docker can pull base images during on-server build:
```ini
[Service]
Environment="HTTP_PROXY=http://proxy.corporate.internal:8080"
Environment="HTTPS_PROXY=http://proxy.corporate.internal:8080"
Environment="NO_PROXY=localhost,127.0.0.1,169.254.169.254,local.net,.internal"
```
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 6.3 Docker Client Configuration (`~/.docker/config.json`)
```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://proxy.corporate.internal:8080",
      "httpsProxy": "http://proxy.corporate.internal:8080",
      "noProxy": "localhost,127.0.0.1,169.254.169.254,gmc_internal_network"
    }
  }
}
```

---

## 7. AI Extraction Architecture (`gpt-5.4-mini`)

### 7.1 Single-Context 400k Prompt Ingestion
`gpt-5.4-mini` features a native 400,000-token context window. The parser compiles the entire RFQ package (scanned PDFs, benefit schedules, email threads) into unified Markdown. This eliminates chunk boundary errors, lost cross-clause context, and vector database retrieval latency.

### 7.2 Structured Outputs Implementation
Interactions are enforced via `instructor` and Pydantic v2 schemas. Conversational or unstructured text outputs are strictly disallowed.

```python
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from app.core.config import settings

client = instructor.from_openai(
    AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        http_client=httpx.AsyncClient(
            proxy=settings.HTTPS_PROXY if settings.HTTPS_PROXY else None,
            timeout=60.0
        )
    )
)

class SourceStatusEnum(str, Enum):
    RFQ_DATA = "RFQ Data"
    DEFAULT_DATA = "Default Data"
    AI_DERIVED = "AI Derived"
    DEMOGRAPHY_DERIVED = "Demography Derived"
    MANUAL = "Manual"
    FIXED = "Fixed"
    NOT_FOUND = "Not Found"
    AMBIGUOUS = "Ambiguous"
    CONFLICT = "Conflict"
    REVIEW_REQUIRED = "Review Required"

class ConfidenceLevelEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ExtractedFieldRecord(BaseModel):
    quote_field: str = Field(description="Canonical GMC field registry name")
    coverage_details: Optional[str] = Field(None, description="Current expiring coverage value")
    proposed_details: Optional[str] = Field(None, description="Client proposed/requested coverage value")
    source_status: SourceStatusEnum
    confidence: ConfidenceLevelEnum
    confidence_reason: str = Field(description="Reasoning for assigned confidence level")
    source_filename: str
    page_or_sheet: str
    cell_or_line: str
    verbatim_evidence: str = Field(description="Exact verbatim excerpt from source document")

class GMCQuotePayload(BaseModel):
    case_id: str
    quotation_fields: List[ExtractedFieldRecord]
    hospitalization_fields: List[ExtractedFieldRecord]
    procedure_sublimits: List[ExtractedFieldRecord]
    unmapped_clauses: List[str]

async def extract_rfq_payload(case_id: str, markdown_content: str) -> GMCQuotePayload:
    return await client.chat.completions.create(
        model=settings.OPENAI_MODEL_EXTRACTION, # "gpt-5.4-mini"
        response_model=GMCQuotePayload,
        max_retries=3,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Senior GMC Insurance Underwriter AI. "
                    "Extract current and proposed policy terms strictly grounded in the document text. "
                    "Populate all fields adhering strictly to the GMC Field Registry. "
                    "Break down compound clauses (e.g., Room Rent into Normal and ICU). "
                    "If a field is missing, assign status 'Not Found' and confidence 'Low'. Never hallucinate."
                )
            },
            {"role": "user", "content": f"Case ID: {case_id}\n\nDocument Markdown:\n{markdown_content}"}
        ]
    )
```

### 7.3 Pass 2: Reflection & Verification Agent
A secondary agent pass evaluates the extracted parameters against their cited `verbatim_evidence`:
* Validates whether the verbatim text factually substantiates the assigned value.
* Identifies contradictions between tender addendums and initial schedules.
* Demotes ungrounded values to `Conflict` or `Review Required`.

---

## 8. Frontend Interface & Core Grid Specifications

### 8.1 Quote Form Grid (Strict 5 Columns)
The review table at `/cases/[id]/quote` renders exactly five columns:

$$\begin{array}{|c|c|c|c|c|}
\hline
\textbf{Quote Fields} & \textbf{Coverage Details} & \textbf{Proposed Details} & \textbf{Source Status} & \textbf{Confidence} \\
\hline
\text{Sum Insured} & \text{₹3,00,000} & \text{₹5,00,000} & \text{RFQ Data} & \text{High} \\
\hline
\text{Room Rent (Normal)} & \text{1\% of SI / day} & \text{No Capping} & \text{RFQ Data} & \text{High} \\
\hline
\text{Brokerage \%} & \text{Manual Input} & \text{5.00\%} & \text{Manual} & \text{High} \\
\hline
\end{array}$$

#### In-Flight Editable Fields Architecture
Five fields support direct, inline manual modification on the Quote Form:
1. **`Rater Type`**: Text input (defaults to system placeholder `-`).
2. **`Brokerage %`**: Formatted percentage input (`0.00%` – `15.00%`).
3. **`PINCODE`**: 6-digit postal code input (`^[1-9][0-9]{5}$`).
4. **`State`**: Dropdown / auto-complete text input.
5. **`District`**: Dropdown / auto-complete text input.

*Automatic Zone Derivation Rule:* Mutating `PINCODE`, `State`, or `District` invokes an asynchronous Server Action that resolves the geographical zone (`Zone A`, `Zone B`, `Zone C`, `Zone D`, or `Pan India`) against the Zone Master table and updates the `Zone` field within 250ms.

### 8.2 Standardized Demography Roster Grid (Strict 7 Columns)
The census review table at `/cases/[id]/demography` renders virtualized member data in the approved sequence:

$$\begin{array}{|c|c|c|c|c|c|c|}
\hline
\textbf{Age (Col 1)} & \textbf{DOB (Col 2)} & \textbf{Sum Insured (Col 3)} & \textbf{Relationship (Col 4)} & \textbf{Name (Col 5)} & \textbf{EmpCode (Col 6)} & \textbf{Gender (Col 7)} \\
\hline
34 & \text{14-06-1992} & \text{5,00,000} & \text{Employee} & \text{Amit Verma} & \text{EMP0912} & \text{Male} \\
\hline
31 & \text{22-11-1995} & \text{5,00,000} & \text{Spouse} & \text{Pooja Verma} & \text{EMP0912} & \text{Female} \\
\hline
\end{array}$$

#### Dynamic Age Recalculation Engine
* **Date Formats:** Normalized to `DD-MM-YYYY`.
* **Modes:** `Current Date` (system date) vs. `Policy Proposal Start Date` (user-selected via date-picker).
* **Completed-Year Floor Formula:**
  $$\text{Age} = \left\lfloor \frac{\text{Basis Date} - \text{DOB}}{365.25} \right\rfloor$$
* **Derived Group Metrics:**
  * $\text{Group Size} = \sum \text{Valid Rows}$
  * $\text{Primary Members} = \sum (\text{Relationship} \in \{\text{'Employee'}, \text{'Self'}\})$
  * $\text{SME Flag} = \begin{cases} \text{Yes}, & \text{if Primary Members} \le 250 \\ \text{No}, & \text{if Primary Members} > 250 \end{cases}$

---

## 9. Procedure Sub-Limit Matcher (19 Procedures)

Procedure amounts are extracted, stripped of non-numeric artifacts (`₹`, `INR`, commas, whitespace), and compared against the 4-tier grid:

```
Raw Extracted String (e.g. "INR 1,20,000/- per eye")
               │
               ▼ Deterministic Regex Sanitization
Integer Token: 120000
               │
               ▼ Master Grid Lookup (e.g. CABG)
┌────────────────────────────────────────────────────────┐
│  Option 1: 150000  │  Option 2: 120000  │  Option 3: 80000  │  Option 4: 65000  │
└────────────────────────────────────────────────────────┘
               │ Match Found: Option 2
               ▼
State: Matched Option 2 | Status: RFQ Data
(If unmatched: Retain 120000 | Status: Unmatched / Review Required)
```

The 19 procedures evaluated:
1. CABG | 2. Valve Replacement | 3. PTCA | 4. Total Knee Replacement | 5. Total Hip Replacement | 6. Arthroscopic Surgeries | 7. Cholecystectomy | 8. Kidney Stone Removal (incl. DJ Stent) | 9. Appendectomy | 10. Hysterectomy | 11. Fistulectomy | 12. Septoplasty | 13. Hernia Repair | 14. Haemorrhoidectomy | 15. Tympanoplasty | 16. Arthroscopy | 17. Cataract (one eye) | 18. Tonsillectomy | 19. Dialysis (per session).

---

## 10. Database Schema (Drizzle ORM TypeScript Definitions)

Defined in `apps/web/src/db/schema.ts`:

```typescript
import { pgTable, uuid, text, timestamp, boolean, integer, numeric, jsonb, index } from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// 1. USERS & IDENTITY BRIDGE
export const users = pgTable("users", {
  id: uuid("id").defaultRandom().primaryKey(),
  clerkUserId: text("clerk_user_id").notNull().unique(),
  email: text("email").notNull().unique(),
  fullName: text("full_name").notNull(),
  role: text("role", { enum: ["admin", "senior_underwriter", "sales_rm", "ops_analyst"] }).notNull().default("sales_rm"),
  branch: text("branch"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

// 2. QUOTATION CASES
export const cases = pgTable("cases", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseNumber: text("case_number").notNull().unique(), // e.g. "CASE-2026-9021"
  clientName: text("client_name").notNull(),
  proposalType: text("proposal_type", { enum: ["New Business", "Roll Over", "Own Renewal"] }).notNull(),
  status: text("status", { enum: ["ingesting", "processing", "review_required", "ready", "exported"] }).notNull().default("ingesting"),
  
  // In-Flight Editable Parameters
  raterType: text("rater_type").default("-"),
  brokeragePct: numeric("brokerage_pct", { precision: 5, scale: 2 }).default("0.00"),
  pincode: text("pincode"),
  state: text("state"),
  district: text("district"),
  zone: text("zone", { enum: ["Zone A", "Zone B", "Zone C", "Zone D", "Pan India"] }).default("Pan India"),
  
  // Demography Aggregates
  groupSize: integer("group_size").default(0),
  primaryMembers: integer("primary_members").default(0),
  smeFlag: boolean("sme_flag").default(false),
  ageBasisMode: text("age_basis_mode", { enum: ["current_date", "proposal_date"] }).default("current_date"),
  proposalStartDate: text("proposal_start_date"),
  
  createdById: uuid("created_by_id").references(() => users.id).notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}, (table) => ({
  statusIdx: index("cases_status_idx").on(table.status),
  createdByIdx: index("cases_created_by_idx").on(table.createdById),
}));

// 3. CASE INGESTED FILES
export const caseFiles = pgTable("case_files", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  filename: text("filename").notNull(),
  storageKey: text("storage_key").notNull(), // Local relative path or S3 key
  fileCategory: text("file_category", { enum: ["rfq_document", "demography_file", "supporting_info"] }).notNull(),
  isEncrypted: boolean("is_encrypted").default(false),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// 4. RFQ 5-COLUMN EXTRACTIONS
export const rfqExtractions = pgTable("rfq_extractions", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  section: text("section").notNull(), // e.g. "quotation", "hospitalization", "maternity"
  quoteField: text("quote_field").notNull(),
  coverageDetails: text("coverage_details"),
  proposedDetails: text("proposed_details"),
  sourceStatus: text("source_status").notNull(),
  confidence: text("confidence").notNull(), // "High", "Medium", "Low"
  confidenceReason: text("confidence_reason"),
  evidenceQuote: text("evidence_quote"),
  sourceFile: text("source_file"),
  pageOrSheet: text("page_or_sheet"),
  cellOrLine: text("cell_or_line"),
  isOverridden: boolean("is_overridden").default(false),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (table) => ({
  caseFieldIdx: index("rfq_case_field_idx").on(table.caseId, table.quoteField),
}));

// 5. PROCEDURE SUB-LIMITS MATCHES
export const procedureSublimits = pgTable("procedure_sublimits", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  procedureName: text("procedure_name").notNull(),
  extractedAmount: numeric("extracted_amount", { precision: 12, scale: 2 }),
  matchedOption: text("matched_option"), // "Option 1", "Option 2", "Option 3", "Option 4", null
  status: text("status").notNull(), // "Matched", "Unmatched / Review Required"
  evidenceQuote: text("evidence_quote"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// 6. STANDARDIZED DEMOGRAPHY (7 COLUMNS)
export const demographyRecords = pgTable("demography_records", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  age: integer("age").notNull(),                           // Col 1
  dateOfBirth: text("date_of_birth").notNull(),           // Col 2 (DD-MM-YYYY)
  sumInsured: numeric("sum_insured", { precision: 12, scale: 2 }).notNull(), // Col 3
  relationship: text("relationship").notNull(),           // Col 4
  name: text("name").notNull(),                           // Col 5
  empCode: text("emp_code").notNull(),                    // Col 6
  gender: text("gender").notNull(),                       // Col 7
  hasException: boolean("has_exception").default(false),
  exceptionNote: text("exception_note"),
}, (table) => ({
  caseEmpIdx: index("demo_case_emp_idx").on(table.caseId, table.empCode),
}));

// 7. IMMUTABLE AUDIT LOGS
export const auditLogs = pgTable("audit_logs", {
  id: uuid("id").defaultRandom().primaryKey(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  userEmail: text("user_email").notNull(),
  targetEntity: text("target_entity").notNull(), // "rfq_extractions", "cases.brokeragePct"
  fieldModified: text("field_modified").notNull(),
  originalValue: text("original_value"),
  newValue: text("new_value").notNull(),
  justificationReason: text("justification_reason"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (table) => ({
  caseAuditIdx: index("audit_case_idx").on(table.caseId, table.createdAt),
}));
```

---

## 11. Complete API Endpoint Catalog

All routes are mounted at `/api/v1/*` on the FastAPI backend:

| Method | Endpoint Path | Functionality | Auth Guard |
| :--- | :--- | :--- | :--- |
| `POST` | `/cases` | Initialize a new quotation case | RM, Underwriter, Admin |
| `POST` | `/cases/{id}/upload` | Stream raw files to storage (`inputs/raw/`) | RM, Underwriter, Admin |
| `POST` | `/cases/{id}/decrypt` | Decrypt locked file in transient memory buffer | RM, Underwriter, Admin |
| `POST` | `/cases/{id}/process` | Trigger Celery task for OCR, AI extraction, and Polars math | RM, Underwriter, Admin |
| `GET` | `/cases/{id}/status` | Server-Sent Events (SSE) live pipeline progress stream | Authenticated User |
| `GET` | `/cases/{id}/quote` | Retrieve 5-column Quote Form data | Authenticated User |
| `PATCH`| `/cases/{id}/quote/fields/{fieldId}` | Apply underwriter override to quote field with audit reason | Underwriter, Admin |
| `PATCH`| `/cases/{id}/parameters` | Update editable fields (`brokeragePct`, `raterType`, `pincode`, `state`, `district`) & trigger auto-zone resolution | RM, Underwriter, Admin |
| `GET` | `/cases/{id}/demography` | Retrieve virtualized 7-column member roster | Authenticated User |
| `POST` | `/cases/{id}/demography/recalculate` | Re-run Polars age calculation with updated basis date | Ops, Underwriter, Admin |
| `GET` | `/cases/{id}/sublimits` | Retrieve 19 surgical sub-limit Option 1–4 matches | Authenticated User |
| `POST` | `/cases/{id}/sublimits/{id}/resolve`| Map unmatched sub-limit to an approved Option tier | Underwriter, Admin |
| `GET` | `/cases/{id}/audit` | Retrieve complete chronological case audit trail | Authenticated User |
| `POST` | `/cases/{id}/export/quote` | Generate reviewed Quote Summary Excel and save to `outputs/analysis/` | RM, Underwriter, Admin |
| `POST` | `/cases/{id}/export/demography` | Generate standardized 7-column census Excel and save to `outputs/analysis/` | RM, Underwriter, Admin |
| `GET` | `/health` | Production orchestration probe (DB, Redis, RAM buffer, proxy) | Public / Monitoring |

---

## 12. Complete Environment Variable Catalog

```ini
# ==============================================================================
# RUNTIME & ENVIRONMENT MODE
# ==============================================================================
ENVIRONMENT=development           # "development" (local) or "production" (EC2)
PORT=3000
NODE_ENV=development

# ==============================================================================
# STORAGE DRIVER (LOCAL-FIRST TO S3 MIGRATION)
# ==============================================================================
STORAGE_BACKEND=local             # "local" for Stage 1; "s3" for Stage 2
LOCAL_STORAGE_PATH=./storage      # Local directory root for inputs/ and outputs/
GMC_S3_BUCKET_NAME=gmc-quote-automation-prod
AWS_REGION=ap-south-1

# ==============================================================================
# AUTHENTICATION (CLERK)
# ==============================================================================
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_placeholder_example_key
CLERK_SECRET_KEY=sk_test_placeholder_example_key
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

# ==============================================================================
# DATABASE (NEON POSTGRESQL & DRIZZLE ORM)
# ==============================================================================
DATABASE_URL=postgresql://user:password@ep-sample.ap-southeast-1.aws.neon.tech/gmc_db?sslmode=require
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=5

# ==============================================================================
# TASK QUEUE & IN-MEMORY CACHE (REDIS & CELERY)
# ==============================================================================
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1

# ==============================================================================
# AI INFERENCE (OPENAI GPT-5.4 MINI)
# ==============================================================================
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL_EXTRACTION=gpt-5.4-mini
OPENAI_MODEL_VERIFICATION=gpt-5.4-mini
OPENAI_ZERO_DATA_RETENTION=true
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=3

# ==============================================================================
# CORPORATE FORWARD PROXY (STAGE 2 PRODUCTION - EC2 ONLY)
# ==============================================================================
HTTP_PROXY=                       # e.g., "http://proxy.corporate.internal:8080"
HTTPS_PROXY=                      # e.g., "http://proxy.corporate.internal:8080"
NO_PROXY=localhost,127.0.0.1,169.254.169.254,local.net,.internal,gmc_internal_network

# ==============================================================================
# BACKEND API & CLIENT CONFIGURATION
# ==============================================================================
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## 13. Production Dockerization Runbook (AWS EC2)

When local verification is 100% complete, code is transferred to the EC2 server where Docker builds and launches all services natively.

### 13.1 `deploy/docker-compose.prod.yml`
```yaml
version: '3.9'

services:
  caddy:
    image: caddy:2.8-alpine
    container_name: gmc_prod_caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - web
      - api
    networks:
      - gmc_internal_network

  web:
    build:
      context: ../
      dockerfile: deploy/Dockerfile.web
      args:
        HTTP_PROXY: ${HTTP_PROXY}
        HTTPS_PROXY: ${HTTPS_PROXY}
        NO_PROXY: ${NO_PROXY}
    container_name: gmc_prod_web
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - PORT=3000
      - NEXT_PUBLIC_API_URL=https://${DOMAIN_NAME}/api/v1
      - NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
      - CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
      - HTTP_PROXY=${HTTP_PROXY}
      - HTTPS_PROXY=${HTTPS_PROXY}
      - NO_PROXY=${NO_PROXY}
    networks:
      - gmc_internal_network
    expose:
      - "3000"

  api:
    build:
      context: ../
      dockerfile: deploy/Dockerfile.backend
      args:
        HTTP_PROXY: ${HTTP_PROXY}
        HTTPS_PROXY: ${HTTPS_PROXY}
        NO_PROXY: ${NO_PROXY}
    container_name: gmc_prod_api
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
    environment:
      - ENVIRONMENT=production
      - STORAGE_BACKEND=s3
      - GMC_S3_BUCKET_NAME=${GMC_S3_BUCKET_NAME}
      - AWS_REGION=${AWS_REGION}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL_EXTRACTION=gpt-5.4-mini
      - HTTP_PROXY=${HTTP_PROXY}
      - HTTPS_PROXY=${HTTPS_PROXY}
      - NO_PROXY=${NO_PROXY}
    volumes:
      - ephemeral_ram_buffer:/tmp/gmc_ephemeral
    depends_on:
      - redis
    networks:
      - gmc_internal_network
    expose:
      - "8000"

  worker:
    build:
      context: ../
      dockerfile: deploy/Dockerfile.backend
      args:
        HTTP_PROXY: ${HTTP_PROXY}
        HTTPS_PROXY: ${HTTPS_PROXY}
        NO_PROXY: ${NO_PROXY}
    container_name: gmc_prod_worker
    restart: unless-stopped
    command: celery -A app.tasks.worker worker --loglevel=INFO --concurrency=4 -Q rfq_processing,demography_calc
    environment:
      - ENVIRONMENT=production
      - STORAGE_BACKEND=s3
      - GMC_S3_BUCKET_NAME=${GMC_S3_BUCKET_NAME}
      - AWS_REGION=${AWS_REGION}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL_EXTRACTION=gpt-5.4-mini
      - HTTP_PROXY=${HTTP_PROXY}
      - HTTPS_PROXY=${HTTPS_PROXY}
      - NO_PROXY=${NO_PROXY}
    volumes:
      - ephemeral_ram_buffer:/tmp/gmc_ephemeral
    depends_on:
      - redis
    networks:
      - gmc_internal_network

  redis:
    image: redis:7.2-alpine
    container_name: gmc_prod_redis
    restart: unless-stopped
    command: redis-server --save 60 1 --loglevel warning --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_prod_data:/data
    networks:
      - gmc_internal_network
    expose:
      - "6379"

volumes:
  caddy_data:
  caddy_config:
  redis_prod_data:
  ephemeral_ram_buffer:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: "size=2G,mode=1777" # 2GB RAM tmpfs buffer for zero-disk decrypts

networks:
  gmc_internal_network:
    driver: bridge
```

### 13.2 EC2 Deployment Execution Commands
```bash
# 1. Connect to EC2 Host and Pull Code Artifacts
cd /opt/gmc-quote-automation
git pull origin main

# 2. Build Multi-Container Images On-Server (respecting proxy args)
cd deploy
docker compose -f docker-compose.prod.yml --env-file .env build --no-cache

# 3. Launch Application Stack
docker compose -f docker-compose.prod.yml --env-file .env up -d --remove-orphans

# 4. Execute Database Migrations
docker compose -f docker-compose.prod.yml exec web bun drizzle-kit migrate

# 5. Verify Orchestration Health Probe
curl -f http://127.0.0.1:8000/api/v1/health
```
