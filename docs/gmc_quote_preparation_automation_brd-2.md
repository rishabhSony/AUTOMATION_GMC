# BUSINESS REQUIREMENTS DOCUMENT (BRD)
## GMC Quote Preparation Automation Platform
### Completely AI-Driven RFQ/RFP Processing with Structured Demography Normalization (GPT-5.4 mini Enterprise Edition)

---

## Document Control

| Document Attribute | Specification |
| :--- | :--- |
| **Document Type** | Business Requirements Document (BRD) — Master Single Source of Truth |
| **Document Version** | 3.0 (GPT-5.4 mini Enterprise Baseline) |
| **Date of Creation** | 28 October 2026 |
| **Last Updated** | 29 October 2026 |
| **Domain** | Group Mediclaim (GMC) Underwriting & Quotation Automation |
| **Target Stakeholders** | Business, Sales/RM, Underwriting, Operations, QA, and Engineering Teams |
| **AI Inference Engine** | OpenAI `gpt-5.4-mini` (Native 400,000-Token Context, Strict Structured Outputs) |
| **Document Status** | Approved Master Business & Functional Specification |

### Revision History

| Version | Date | Author / Role | Summary of Changes |
| :--- | :--- | :--- | :--- |
| 1.0 | 28 Oct 2026 | Product & Solutions Team | Initial draft synthesizing guidebook, RFQ dictionary, and preliminary scope. |
| 2.0 | 29 Oct 2026 | Enterprise Architecture | Added sub-limit grids, age calculation algorithms, and multi-file security specs. |
| 3.0 | 29 Oct 2026 | Principal AI Architect & Underwriting | **Upgraded AI Inference Source to `gpt-5.4-mini`**: integrated 400k context ingestion (zero chunking), two-agent schema-enforced extraction and reflection verification, Enterprise Zero Data Retention (ZDR) governance, and sharpened hybrid AI-deterministic operational boundaries. |

---

## 1. Executive Summary & Business Background

### 1.1 Executive Summary
The **GMC Quote Preparation Automation Platform** is an enterprise-grade AI system designed to ingest heterogeneous Request for Quotation (RFQ) / Request for Proposal (RFP) packages and employee census/demography files. The system automatically reads, interprets, cross-references, validates, and normalizes unstructured and semi-structured insurance documents into standardized quote structures and verified member schedules.

Powered natively by **OpenAI `gpt-5.4-mini`**, the platform ingests massive multi-file tender packages (up to 400,000 tokens) in a single unified prompt context without document chunking or vector search loss. The platform isolates **Current Coverage** from **Proposed/Requested Terms**, enforces strict source evidence tracing for every populated field, matches procedure sub-limits deterministically against an approved 4-tier matrix, standardizes employee census data into a strict 7-column schema, and yields audited, client-ready quotation artifacts.

### 1.2 Business Background & Problem Statement
Underwriting Group Mediclaim policies currently requires intensive manual labor:
1. **Unstandardized RFQ Packs:** RFQ documents arrive across disparate channels as PDFs (digital and scanned), multi-tab Excel files, emails (`.eml`/`.msg`), and Word files with arbitrary naming conventions and non-standard terminology.
2. **Complex Compound Clauses:** Critical policy terms (such as room rent limits combined with ICU caps, or maternity waiting period waivers linked to corporate buffers) are buried inside lengthy narrative clauses.
3. **Dirty Demography Data:** Client census sheets contain non-uniform headers, missing dates of birth, inverted dates, duplicate entries, invalid relationship tags, and uncalculated or conflicting ages.
4. **Latency & Errors:** Manual transcribing from RFQ packs to rating sheets takes between 4 to 8 hours per quote, creates human error risks, and impedes underwriting turnaround times (TAT).

### 1.3 Business Objectives & Success Metrics
* **Cycle Time Reduction:** Reduce quotation preparation TAT from 4–8 hours to under 3 minutes per case.
* **Extraction Precision:** Achieve $\ge 98\%$ accuracy across core RFQ fields backed by verifiable evidence spans.
* **Cost Efficiency:** Leverage `gpt-5.4-mini` structured extraction to achieve under \$0.08 per 100-page case extraction, avoiding expensive self-hosted multi-GPU clusters.
* **Zero PII Leakage:** Ensure password decryption and demographic parsing respect data privacy without storing sensitive credentials or unmasked PII in server logs, backed by Enterprise Zero Data Retention (ZDR).
* **Standardized Demography Normalization:** Process, clean, validate, and recalculate demography censuses of up to 100,000 lives in $<2$ seconds.
* **Human-in-the-Loop Control:** Provide an interactive verification workbench where underwriter modifications are logged with an immutable audit trail.

---

## 2. Project Scope & System Boundaries

### 2.1 In-Scope Capabilities
* **Multi-Format Ingestion:** Concurrent intake of RFQ/RFP documents and demography census sheets (`.xlsx`, `.xls`, `.csv`, `.pdf`, `.docx`, `.msg`, `.eml`, `.png`/`.jpg`).
* **Secure Document Decryption:** Zero-persistence, in-memory decryption of password-protected files.
* **Document Layout Classification:** Semantic separation of RFQ packs, demography rosters, and endorsements.
* **AI Extraction via `gpt-5.4-mini`:** Extraction of Quotation, Policyholder, Group, and Coverage terms across 400,000 tokens of native context.
* **Dual-State Capture:** Discrete tracking of *Coverage Details (Current)* vs. *Proposed Details (Requested)*.
* **Procedure Sub-Limit Engine:** Exact matching against the 4-tier sub-limit registry and handling of non-standard amounts.
* **Demography Engine:** 7-column export normalization, header fuzzy mapping, date-basis age calculation, family-tier linking, and under-18 worker validation.
* **Audit & Evidence Layer:** Direct line/page/cell traceability for every populated field.
* **Export Artifacts:** Automated generation of Quote Excel and Clean Demography Excel files.

### 2.2 Out-of-Scope (Boundaries)
* Actuarial risk rating, loss-ratio projection algorithms, and final premium pricing calculations.
* Automated binding and binding policy issuance in core insurance policy administration systems (PAS).
* Downstream claim settlement adjudication.

---

## 3. High-Level Architecture & End-to-End Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CASE INTAKE & UPLOAD                            │
│  User uploads multi-format files (.xlsx, .pdf, .docx, .msg, scans)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    ZERO-PERSISTENCE DECRYPTION                         │
│  Prompts for password if locked; decrypts stream in memory (no disk)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   AI DOCUMENT CLASSIFICATION ROUTER                    │
│  Classifies into: RFQ Document, Demography Census, or Supporting Info  │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐ ┌──────────────────────────────┐
│        RFQ EXTRACTION ENGINE         │ │      DEMOGRAPHY ENGINE       │
│ • OCR & Table Layout (Docling/PyMu)  │ │ • Column Header Synonym Map  │
│ • gpt-5.4-mini Schema Extraction     │ │ • 7-Column Standardizer      │
│   (Single-pass 400k token context)   │ │ • Age Engine (Ref/Curr Date) │
│ • Dual-State Split (Current/Proposed)│ │ • Relationship Normalizer    │
│ • Compound Clause Disaggregation     │ │ • Integrity & Under-18 Check │
│ • Sub-limit Matching (Option 1-4)    │ │ • Derived Metrics (SME Flag) │
│ • gpt-5.4-mini Reflection Verifier   │ │                              │
└───────────────────┬──────────────────┘ └──────────────┬───────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                RECONCILIATION & VERIFICATION WORKBENCH                 │
│  • View Dual-State Terms, Evidence Coordinates, Confidence Scores      │
│  • Highlight Exceptions: 'Not Found', 'Conflict', 'Review Required'    │
│  • Human-in-the-Loop Review, Field Overrides & Acceptance              │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      AUDITED EXPORT ENGINE                             │
│  • Reviewed Quote Excel File    • Standardized 7-Column Demography     │
│  • Complete JSON Audit Log with Traceability Coordinates               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Input Documents, Security & Ingestion Layer

### 4.1 Supported File Formats & Ingestion Matrix

| File Type | Extensions | Parsing Mechanism | Ingestion Constraints |
| :--- | :--- | :--- | :--- |
| **Spreadsheets** | `.xlsx`, `.xls`, `.csv` | High-performance columnar parser (`python-calamine`, `openpyxl`) | Handles multiple tabs, merged cells, hidden sheets, formatted numbers. |
| **Digital PDF** | `.pdf` | Native text & layout engine (`pdfplumber`, `PyMuPDF`) | Extracts text with character/word bounding boxes. |
| **Scanned PDF / Images** | `.pdf`, `.png`, `.jpg`, `.jpeg` | OCR & layout analysis (`Surya OCR`, `Tesseract`) | Minimum 200 DPI recommended; auto-deskewing. |
| **Word Documents** | `.docx` | Native XML/document AST reader (`python-docx`) | Extracts paragraphs, embedded tables, headers/footers. |
| **Email Packages** | `.msg`, `.eml` | RFC 822 / MAPI parser (`extract-msg`, `mail-parser`) | Extracts email body (HTML/plain) and unrolls attachments. |

### 4.2 Zero-Persistence Password Decryption Protocol (FR-05)
1. **Detection:** When a file stream is read, the file header is inspected for encryption flags (`StandardEncryption`, AES-128/256).
2. **Challenge UI:** The system triggers an immediate modal requesting the user to provide the decryption key.
3. **Decryption Execution:** The key is held exclusively in transient application RAM (`tmpfs`) to decrypt the file stream.
4. **Zero Footprint:** The password string is zeroed from memory immediately following stream decryption. The password must **never** be logged to application telemetry, cached in persistent storage, or written to disk.

### 4.3 Automated Document Classification (FR-03)
Every uploaded document is scanned by an initial classification classifier:
* **`RFQ_DOCUMENT`:** Contains benefit tables, coverage narrative clauses, terms of trade, eligibility requirements.
* **`DEMOGRAPHY_FILE`:** Tabular file containing member lists, birth dates, employee codes, dependent relationships.
* **`SUPPORTING_INFO`:** Mandate letters, prior claims dumps, broker authorization notes, network lists.

---

## 5. AI-Driven Solution Principles (GPT-5.4 mini Core)

### 5.1 Single-Context 400k Ingestion Principle
Rather than relying on vector databases, semantic chunking, or RAG (Retrieval-Augmented Generation) pipelines that lose context across sprawling policy schedules, the extraction engine exploits the **400,000-token native context window of `gpt-5.4-mini`**. Complete multi-document tender packages, policy schedules, endorsement wordings, and email trails are compiled into a layout-preserved Markdown document representation and submitted in a single, coherent extraction context.

### 5.2 Strict Structured Outputs via JSON Schema
All interactions with `gpt-5.4-mini` enforce programmatic Structured Outputs (`response_format={"type": "json_schema"}`) mapped directly to strongly typed Pydantic models via `instructor`. Free-form conversational text output is prohibited; the model must output valid, syntactically guaranteed JSON adhering strictly to the GMC Field Registry.

### 5.3 Dual-Pass Agent Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        INGESTED RFQ MARKDOWN                           │
│                 (Full tender text up to 400k tokens)                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│           PASS 1: STRUCTURED EXTRACTION AGENT (gpt-5.4-mini)           │
│  • Reads complete document context in one shot                         │
│  • Disaggregates Current vs. Proposed terms                            │
│  • Splits compound clauses (e.g., Parent Room Rent -> Normal + ICU)    │
│  • Cites exact source evidence (file, page, row/cell, verbatim quote)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│           PASS 2: REFLECTION & VERIFICATION AGENT (gpt-5.4-mini)       │
│  • Cross-checks extracted value strictly against cited verbatim quote  │
│  • Eliminates hallucinations or contextual overreach                   │
│  • Sets Status: RFQ Data (Confirmed), Ambiguous, Conflict, or Not Found│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 DETERMINISTIC POST-PROCESSING LAYER                    │
│  • Procedure Sub-Limit Normalizer (Option 1–4 grid matching)           │
│  • Polars Demography Engine (Age recalculation, SME classification)    │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Pass 1 — Structured Extraction Agent (`gpt-5.4-mini`):**
   * Processes the entire unified document payload.
   * Extracts every registry attribute, isolating `coverage_details` (current) from `proposed_details` (requested).
   * Extracts verbatim citations: `file_name`, `page_or_sheet`, `location_reference`, and `verbatim_excerpt`.
2. **Pass 2 — Reflection & Verification Agent (`gpt-5.4-mini`):**
   * Evaluates the extracted value strictly against the cited `verbatim_excerpt`.
   * Verifies semantic grounding: *"Does the excerpt explicitly justify the extracted value without extraneous assumption?"*
   * Assigns confidence scores (`High`, `Medium`, `Low`) and tags ungrounded outputs as `Conflict` or `Review Required`.

### 5.4 Hybrid AI-Deterministic Separation Matrix
To ensure predictable underwriting operations and zero hallucinations, system responsibilities are partitioned strictly between generative AI and deterministic code:

| Responsibility | Engine / Component | Operational Justification |
| :--- | :--- | :--- |
| **RFQ Natural Language Understanding** | `gpt-5.4-mini` | Handles arbitrary client terminology, complex legal narratives, and layout variance. |
| **Current vs. Proposed Separation** | `gpt-5.4-mini` | Contextual understanding required to distinguish active policy terms from quote requests. |
| **Compound Clause Decomposition** | `gpt-5.4-mini` | Disaggregates nested conditions (e.g., Normal vs. ICU room rent caps). |
| **Sub-Limit Currency Matching** | **Deterministic Python Engine** | Strips currency noise (`₹`, commas) and executes exact equality matching against Options 1–4. Never allows LLM rounding. |
| **Demography Cleaning & Age Recalculation** | **Polars / DuckDB (Vectorized)** | Processes 100k+ member rows in $<2$ seconds in-memory with exact mathematical precision. Zero token cost. |
| **Group Size, Primary Lives & SME Flag** | **Deterministic Python Engine** | Strict mathematical formulas ($\text{Primary Members} \le 250 \rightarrow \text{YES}$). |
| **Zone Tiering Resolution** | **Deterministic Lookup Engine** | Exact PIN/District resolution against internal master dictionary. |

### 5.5 Enterprise AI Governance & Data Privacy (Zero Data Retention)
1. **Zero Data Retention (ZDR):** All API calls to `gpt-5.4-mini` are executed under enterprise agreements mandating Zero Data Retention. Prompts, documents, and completions are processed in volatile memory and are never persisted by OpenAI or utilized for foundation model training.
2. **PII Masking at Ingestion:** Demography census files containing employee names, dates of birth, and identity codes are routed **exclusively** to the vectorized Polars engine and are **never** passed into LLM prompt contexts.
3. **Audit Immutability:** Every AI extraction event stores the exact model identifier (`gpt-5.4-mini`), prompt schema version, latency, token usage, and citation coordinates.

---

## 6. Complete RFQ Field Registry & Business Logic

### 6.1 Section 1: Quotation Details

| Field Identifier | Processing Mode | Standard Allowed Options / Value Type | Default / Fallback Rule | Detailed Business Logic & Derivation |
| :--- | :--- | :--- | :--- | :--- |
| **Sum Insured (SI)** | `EXTRACT` | Numeric Currency / Tiered List (e.g., `3,00,000`, `5,00,000`) | Flag `Not Available` if missing | Capture base sum insured, family tiers, and executive designations. |
| **Policy Tenure** | `EXTRACT` | Duration (e.g., `1 Year`, `12 Months`) | `1 Year` | Defaults to `1 Year` if unstated in RFQ. |
| **Group Category** | `EXTRACT` | `Employer-Employee`, `Non-Employer-Employee` | `Employer-Employee` | Defaults to `Employer-Employee` unless explicit non-employer affinity is stated. |
| **Type of Proposal** | `EXTRACT / DERIVED` | `New Business`, `Roll Over`, `Own Renewal` | Flag `Review Required` if ambiguous | **Derivation Logic:**<br>1. If incumbent insurer contains `"Bajaj"` $\rightarrow$ `Own Renewal`<br>2. If incumbent insurer is present and $\neq$ `"Bajaj"` $\rightarrow$ `Roll Over`<br>3. If no prior policy/insurer context $\rightarrow$ `New Business`. |
| **Brokerage %** | `MANUAL` | Percentage (`0.00%` to `15.00%`) | Editable blank | Maintained as an open input field for Sales/RM entry; never extracted automatically. |
| **Premium Payer** | `EXTRACT` | `GroupManager`, `Insured` | `GroupManager` | If RFQ does not state employee-paid premium, assign default `GroupManager`. |
| **Beneficiary** | `EXTRACT` | `Employee/Nominee`, `Corporate Entity` | `Employee/Nominee` | Defaults to `Employee/Nominee` unless policy is key-man or corporate-benefit structured. |
| **Plan** | `EXTRACT` | `Individual`, `Floater` | Flag `Not Available` | Must be explicitly stated or inferred from sum insured tiers; do not force a default if ambiguous. |
| **Rater Type** | `FIXED` | Constant string: `-` | `-` | Fixed placeholder required for downstream rating engines. |
| **Zone** | `AI DERIVED` | `Zone A`, `Zone B`, `Zone C`, `Zone D`, `Pan India` | `Pan India` (if location unresolved) | Derived from client postal PIN code / Registered Office District against the internal Zone Master. |
| **Policy Type** | `EXTRACT` | `Base IPD`, `Base OPD`, `Corporate Buffer`, `Critical Illness`, `Dependent Only`, `Parental IPD`, `Parental Top Up`, `Wellness` | `Base IPD` | Product coverage type. Defaults to `Base IPD` if standard hospitalization is requested. |
| **Claim Servicing** | `EXTRACT` | `In House`, `TPA` | `In House` | Identifies claim administration route. Defaults to `In House`. |
| **TPA Name** | `CONDITIONAL` | Entity Name / Organization String | Conditional logic | **Conditional Logic:**<br>1. If `Claim Servicing == 'In House'`, force `In House Administration Team`.<br>2. If `Claim Servicing == 'TPA'`, extract Third-Party Administrator name from RFQ. If missing, flag `Review Required`. |

### 6.2 Section 2: Group Policy Holder Details

| Field Identifier | Processing Mode | Value Type | Parsing & Validation Rules |
| :--- | :--- | :--- | :--- |
| **Company Name** | `EXTRACT` | Full Legal String | Insured company or entity name. Verified against quotation header. |
| **PIN Code** | `EXTRACT` | 6-Digit Integer | Indian postal code. Validated via regex `^[1-9][0-9]{5}$`. |
| **State** | `EXTRACT` | Canonical State Name | Validated against Indian State/UT standard dictionary. |
| **District** | `EXTRACT` | Canonical District Name | Validated against Ministry of Home Affairs District Master. |
| **Client Industry Type** | `EXTRACT` | Industry Category | Extracted industry sector (e.g., IT/ITES, Manufacturing, Banking). Fallback to `'Others'` if unmatched. |

### 6.3 Section 3: Group Details (Derived from Demography)

| Field Identifier | Processing Mode | Data Type | Deterministic Calculation Specification |
| :--- | :--- | :--- | :--- |
| **Group Size** | `DERIVED` | Integer | Total valid member records parsed from the demography census sheet: $$\text{Group Size} = \sum \text{Valid Demography Rows}$$ |
| **Number of Primary Members** | `DERIVED` | Integer | Total count of principal employees: $$\text{Primary Members} = \sum \left[ \text{Relationship} \in \{\text{'Employee'}, \text{'Self'}\} \right]$$ |
| **Flagging SME** | `DERIVED` | Boolean (`Yes` / `No`) | Threshold logic: $$\text{SME Flag} = \begin{cases} \text{Yes}, & \text{if Primary Members} \le 250 \\ \text{No}, & \text{if Primary Members} > 250 \end{cases}$$ |

### 6.4 Section 4: Medical Expenses Insurance Coverages

| Field Identifier | Mode | Approved Dropdown / Range Values | Business Rules & Transformation Logic |
| :--- | :--- | :--- | :--- |
| **Pre-Existing & Specified Disease (PED)** | `EXTRACT` | `Covered`, `Waived Off`, `Applicable`, `Not Covered`, `Not Applicable` | Maps terms like "PED covered from Day 1" $\rightarrow$ `Covered` / `Waived Off`. Flag non-standard waiting periods. |
| **Initial Waiting Period** | `EXTRACT` | `Covered`, `Waived Off`, `15 Days`, `30 Days`, `Applicable`, `Not Covered` | Standard 30-day waiting period waiver. 1-30 day exclusions map to exact day ranges. |
| **Room Rent (Parent Clause)** | `EXTRACT` | Free text / Normalized string | Complete room eligibility narrative. Serves as parent clause. |
| **Room Rent for Normal Room** | `EXTRACT` | Currency limit, % of SI (e.g., `1% of SI`, `5000/day`, `No Capping`) | Specific limit for normal room admission. Extracted from parent clause via `gpt-5.4-mini`. |
| **Room Rent for ICU & Specialty Rooms** | `EXTRACT` | Currency limit, % of SI (e.g., `2% of SI`, `10000/day`, `No Capping`) | Specific limit for Intensive Care Unit admission. Extracted from parent clause via `gpt-5.4-mini`. |
| **Road Ambulance** | `EXTRACT` | Amount per event or actuals (e.g., `2000 per hospitalization`, `Actuals`) | Road ambulance emergency transport expense. |
| **Air Ambulance** | `EXTRACT` | Currency limit or condition (e.g., `Up to 10% of SI`, `Not Covered`) | Emergency aero-medical transport coverage. |
| **Pre-Hospitalization** | `EXTRACT` | Number of Days: `0`, `15`, `30`, `60`, `90`, `120` | Pre-admission medical expenses. Defaults to standard 30 days if stated as standard. |
| **Post-Hospitalization** | `EXTRACT` | Number of Days: `0`, `30`, `60`, `90`, `120`, `180` | Post-discharge medical expenses. Defaults to standard 60 days if stated as standard. |
| **Medical Advancement Surgery** | `EXTRACT` | `Upto 25% SI`, `Upto 50% SI`, `Upto SI`, `Not Covered` | Coverage for modern treatment methods and robotic/cyberknife interventions. |
| **Maternity Expenses / Benefits** | `EXTRACT` | `Covered`, `Waived Off`, `Not Covered`, `Not Applicable` | High-level maternity coverage indicator. |
| **No. of Deliveries / Kids Covered** | `EXTRACT` | `1`, `2`, `3`, `Restricted to 2 Children` | Delivery limit per family across policy lifetime. |
| **Maternity Limit – Normal Delivery** | `EXTRACT` | Numeric Currency (Standard default: `50,000`) | Exact monetary cap for normal delivery. |
| **Maternity Limit – C-Section Delivery**| `EXTRACT` | Numeric Currency (Standard default: `50,000`) | Exact monetary cap for Caesarean delivery. |
| **Maternity Waiting Period** | `EXTRACT` | `9 Months Waiting Period`, `Waived Off`, `No Waiting Period`, `Covered` | Waiver of the statutory 9-month waiting period for maternity claims. |
| **AYUSH Treatment** | `EXTRACT` | Currency Limit / `Upto SI` (Standard default: `25,000`) | Inpatient coverage for Ayurveda, Yoga, Unani, Siddha, and Homeopathy. |
| **Co-Payment Type** | `EXTRACT` | `All Claims`, `Non-Network Hospitals`, `Co-pay on Parents Only`, `Not Applicable` | Structural applicability of co-payment deductions. |
| **Policy Co-Payment Factor** | `EXTRACT` | Percentage: `5%`, `10%`, `15%`, `20%`, `25%`, `30% Copay`, `0%` | Extracted numerical co-pay factor. Non-percentage expressions (e.g., rupee amounts) must be rejected. |
| **Waiver of Cataract Sublimit** | `EXTRACT` | `Covered`, `Waived Off`, `Applicable`, `Not Covered` | Indicates whether standard cataract procedure caps are eliminated. |
| **Cataract Limit** | `EXTRACT` | Monetary limit per eye or per family | Specific cataract surgical expense cap. |
| **Corporate Buffer** | `EXTRACT` | Total Currency Limit & Allocation Rules | Employer-maintained pool for critical illness or exhausted sum insured. |
| **Cover Not Available / UW Referral** | `AI GENERATED` | List of non-standard conditions | Summarizes risky or non-standard client terms requiring senior underwriter sign-off. |

---

## 7. Hospitalization and Treatment Master Registries

For every medical treatment, intervention, and policy clause listed in Sections 7.1 through 7.6, `gpt-5.4-mini` outputs:
$$\{\text{Coverage Status (Covered/Not Covered)}, \text{Limit Amount}, \text{Co-Pay \%}, \text{Specific Condition/Qualifier}, \text{Current Value}, \text{Proposed Value}, \text{Evidence Coordinates}\}$$

### 7.1 Modern Treatments (20 Mandatory Procedures)
1. Uterine Artery Embolization and High-Intensity Focused Ultrasound (HIFU)
2. Balloon Sinuplasty
3. Deep Brain Stimulation
4. Oral Chemotherapy
5. Immunotherapy including Monoclonal Antibody Injection
6. Intravitreal Injections except Lucentis
7. Intravitreal Injections
8. Robotic Surgeries
9. Vaporisation of the Prostate (Green Laser / Holmium Laser)
10. Bronchial Thermoplasty
11. Stereotactic Radiosurgery
12. Intraoperative Neuro Monitoring (IONM)
13. Stem Cell Therapy / Treatment
14. Gamma Knife / CyberKnife Surgery
15. Remicade / Avastin Injection
16. Biodegradable Stent
17. Cochlear Implant Treatment
18. Lucentis Injection
19. Functional Endoscopic Sinus Surgery (FESS)
20. Ayurvedic Treatment (Inpatient Modern Administration)

### 7.2 Medical Coverage Scope (11 Policy Conditions)
1. Day Care Expenses / Procedures (All procedures requiring $<24$ hrs hospitalization due to technological advancement)
2. Domiciliary Hospitalisation (Medical treatment at home due to hospital bed unavailability or patient condition)
3. Dental Treatment (Limited to inpatient treatment arising from accidental trauma)
4. LASIK Surgery / Correction
5. Refractive Error Correction (Typically covered if refractive error $\ge 7.5$ dioptres)
6. Psychiatric Ailments / Mental Illness Inpatient Treatment
7. Organ Donor Expenses (Hospitalization costs for donor harvesting)
8. Covid-19 Treatment (Inpatient, home care, quarantine limits)
9. Hospitalisation following Terrorism
10. Internal Congenital Diseases
11. External Congenital Diseases

### 7.3 Maternity and Newborn Coverages (5 Mandatory Clauses)
1. Newborn Baby Coverage (Standard inclusion terms)
2. Newborn Baby Cover from Day One within Family Floater Sum Insured
3. Maternity Complication Coverage (Ectopic pregnancy, pre-eclampsia, emergency intervention)
4. Pre and Post Natal Treatment up to Maternity Limit
5. Twin Delivery / Multiple Birth Benefit Coverage

### 7.4 Hospital Expenses & Allowances (5 Line Items)
1. Anaesthesia Charges
2. Charges of Surgeon’s Own Instruments used in Surgeries
3. Assistant Surgeon / Doctor / Consultant / Attendant Charges
4. Nursing Allowance
5. Hospital Cash Benefit (Fixed daily stipend for eligible inpatient days)

### 7.5 Health and Wellness Offerings (4 Line Items)
1. Wellness Programmes / Preventative Health Offerings
2. Health Check-Up (Annual general health check-up terms)
3. Master Health Check-Up for Employees (Inbuilt corporate diagnostic package)
4. Health Card Type (E-Card / Physical Card issuing rules)

### 7.6 General Policy Conditions (6 Legal Clauses)
1. Claim Submission and Intimation Clause (Turnaround time for notice: e.g., 48 hrs emergency, 30 days submission)
2. Proportionate Clause (Application of proportionate deductions if room rent exceeds capped threshold)
3. Portability Rights & Continuity Benefit
4. Terrorism and Epidemic Outbreak Conditions
5. Correction Endorsements Terms
6. Special Clause / Bespoke Endorsements

---

## 8. Procedure-Wise Sub-Limit Matching Registry

### 8.1 Registry Matching Matrix & Option Tiers
Extracted procedures are cleaned of non-numeric noise (e.g., `"Rs."`, `"INR"`, `","`, `"/-"`) by the deterministic Python engine and matched against the exact approved schedule:

| Procedure Name | Option 1 (₹) | Option 2 (₹) | Option 3 (₹) | Option 4 (₹) | System Action on Mismatch |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Coronary Artery Bypass Grafting (CABG)** | 1,50,000 | 1,20,000 | 80,000 | 65,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Valve Replacement** | 1,50,000 | 1,20,000 | 80,000 | 65,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **PTCA (per event hospitalisation)** | 1,30,000 | 1,00,000 | 70,000 | 50,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Total Knee Replacement (per event)** | 1,30,000 | 1,00,000 | 70,000 | 50,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Total Hip Replacement** | 1,50,000 | 1,20,000 | 80,000 | 65,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Arthroscopic Surgeries** | 1,50,000 | 1,20,000 | 80,000 | 65,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Cholecystectomy** | 35,000 | 25,000 | 20,000 | 20,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Kidney Stone Removal (incl. DJ Stent)**| 35,000 | 30,000 | 25,000 | 20,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Appendectomy** | 30,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Hysterectomy** | 35,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Fistulectomy** | 35,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Septoplasty** | 35,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Hernia Repair** | 35,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Haemorrhoidectomy** | 25,000 | 20,000 | 15,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Tympanoplasty** | 25,000 | 20,000 | 15,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Arthroscopy** | 25,000 | 20,000 | 10,000 | 10,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Cataract (one eye)** | 35,000 | 25,000 | 20,000 | 15,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Tonsillectomy** | 20,000 | 15,000 | 10,000 | 10,000 | Retain extracted amount; flag `Unmatched / Review Required` |
| **Dialysis (per session)** | 5,000 | 4,000 | 2,000 | 2,000 | Retain extracted amount; flag `Unmatched / Review Required` |

### 8.2 Discrepancy & Ambiguity Handling
* **Exact Match:** When the cleaned amount matches Option 1, 2, 3, or 4, assign the matched option label (e.g., `"Option 2"`).
* **Unmatched Amounts:** If the client RFQ requests an unlisted sub-limit (e.g., Cataract at ₹30,000 or CABG at ₹1,00,000), the system must:
  1. Retain the exact extracted numeric value (`₹30,000`).
  2. Mark the status as `Unmatched / Review Required`.
  3. Attach the verbatim evidence string and cite page/cell coordinates.
  4. Never force-map or round to the nearest option.

---

## 9. Structured Demography Processing Engine

### 9.1 Header Synonym Mapping Dictionary
The ingestion pipeline automatically maps common source column variants to internal canonical targets:

| Canonical Field | Recognized Header Aliases / Variants |
| :--- | :--- |
| `employee_code` | `Emp ID`, `Staff Code`, `Employee No`, `EmpCode`, `Member ID`, `Emp_No`, `Token No`, `Associate ID` |
| `member_name` | `Employee Name`, `Name of Insured`, `Beneficiary Name`, `Patient Name`, `Member Name`, `Full Name` |
| `relationship` | `Relation`, `Rel`, `Relationship with Emp`, `Dep Relation`, `Family Relation`, `Category` |
| `dob` | `Date of Birth`, `D.O.B.`, `Birth Date`, `DOB (DD/MM/YYYY)`, `EMP DOB`, `Member DOB` |
| `age` | `Member Age`, `Completed Age`, `Age in Years`, `Age (Yrs)` |
| `gender` | `Sex`, `Gender`, `M/F`, `Male/Female` |
| `sum_insured` | `SI`, `Coverage Amount`, `Sum Assured`, `Cover`, `SI Opted`, `Medical SI` |

### 9.2 Strict 7-Column Export Specification (FR-13)
The normalized Demography Excel output must produce these seven columns in this exact sequence:

$$\text{Col 1: Age} \;\vert\; \text{Col 2: Date of Birth} \;\vert\; \text{Col 3: Sum Insured} \;\vert\; \text{Col 4: Relationship} \;\vert\; \text{Col 5: Name} \;\vert\; \text{Col 6: EmpCode} \;\vert\; \text{Col 7: Gender}$$

### 9.3 Age Calculation & Dynamic Recalculation Engine (FR-14)
* **Date Standardization:** Convert diverse input date formats (`MM/DD/YYYY`, `DD.MM.YYYY`, `YYYY-MM-DD`, Excel serial timestamps) to standard `DD-MM-YYYY`.
* **Calculation Modes:**
  * **Mode 1 (Default):** `Current Date` (Execution date timestamp).
  * **Mode 2 (User-Defined):** `Policy Proposal Start Date` (Configured via UI date-picker).
* **Calculation Formula:**
  $$\text{Age} = \left\lfloor \frac{\text{Basis Date} - \text{DOB}}{365.25} \right\rfloor$$
* **Fallback Rule:** If `DOB` is absent but an integer `Age` is provided in the source file, retain the source age. If both `DOB` and `Age` are missing, flag the row with `CRITICAL_ERROR: Missing Age and DOB`.

### 9.4 Relationship Grouping & Integrity Validations
* **Canonical Relationships:** Map input values into five categories:
  * `Employee` (Synonyms: `Self`, `Primary`, `Employee`, `Worker`)
  * `Spouse` (Synonyms: `Wife`, `Husband`, `Partner`)
  * `Child` (Synonyms: `Son`, `Daughter`, `Child`, `Kid`, `Dependent Child`)
  * `Parent` (Synonyms: `Father`, `Mother`)
  * `Parent-in-law` (Synonyms: `Father-in-law`, `Mother-in-law`, `FIL`, `MIL`)
* **Validation Rules:**
  1. **Under-18 Primary Worker Check:** If $\text{Relationship} \in \{\text{'Employee'}, \text{'Self'}\}$ and $\text{Calculated Age} < 18$, set flag `under18_employee = TRUE`.
  2. **Orphan Dependant Check:** Any dependant row whose `EmpCode` does not match an existing primary `Employee` record is flagged as `ORPHAN_DEPENDENT`.
  3. **Duplicate Detection:** Identify records matching on identical `EmpCode` + `Name` + `Relationship`.
  4. **Age-DOB Discrepancy:** If both `Age` and `DOB` exist in the source file, calculate variance. If $\vert \text{Source Age} - \text{Calculated Age} \vert > 1$, flag `AGE_DOB_MISMATCH`.

---

## 10. Verification Workbench & UI/UX Requirements

### 10.1 Multi-Tab Layout Architecture
The frontend verification workbench is structured into 6 views:
1. **Quotation Summary Form:** Key details (Sum Insured, Tenure, Plan, In-House/TPA, Insured Name, Brokerage).
2. **Hospitalization & Treatments Matrix:** Expandable accordion tables for Modern Treatments, Medical Coverages, Maternity, and Hospital Expenses.
3. **Procedure-Wise Sub-Limits Table:** Displays procedure, extracted amount, matched Option (1–4), and discrepancy flags.
4. **Additional / Unmapped Details:** Log of non-standard clauses extracted from RFQ narrative paragraphs.
5. **Standardized Demography Grid:** Virtualized, high-performance table showing the 7-column member schedule with highlighted exceptions.
6. **Audit & Traceability View:** Complete changelog detailing original values, modifications, timestamps, and usernames.

### 10.2 Table Structure & Status Indicators
Every row in the RFQ review table displays four mandatory columns:

$$\text{Field Name} \;\vert\; \text{Coverage Details (Current)} \;\vert\; \text{Proposed Details (Requested)} \;\vert\; \text{Source Status}$$

* **Visual Status Flags:**
  * <span style="color:green">**RFQ Data:**</span> Extracted directly from RFQ with high confidence verified by Pass 2.
  * <span style="color:blue">**Default Data:**</span> Populated via approved default rule.
  * <span style="color:teal">**AI Derived:**</span> Inferred or calculated through secondary logic (e.g., Zone).
  * <span style="color:purple">**Demography Derived:**</span> Calculated directly from demography records (Group Size, SME Flag).
  * <span style="color:orange">**Manual:**</span> Requires underwriter or RM manual entry (e.g., Brokerage %).
  * <span style="color:gray">**Fixed:**</span> System-wide constant placeholder (`-`).
  * <span style="color:red">**Not Found:**</span> Field not discovered in uploaded documents.
  * <span style="color:magenta">**Ambiguous / Conflict:**</span> Conflicting values across sheets/files detected during reflection.
  * <span style="color:brown">**Review Required:**</span> Unmatched sub-limit amount or low confidence score.

---

## 11. Security, Audit Trail & Data Governance

### 11.1 Enterprise Audit Logging
Every modification made on the workbench generates an append-only JSON event recorded in the database:
```json
{
  "event_id": "evt_984372104",
  "case_id": "CASE_GMC_2026_00192",
  "timestamp": "2026-10-29T10:15:30Z",
  "user_id": "underwriter_jdoe@company.com",
  "field_modified": "medical_expenses.maternity_normal_delivery",
  "original_extracted_value": "40000",
  "overridden_value": "50000",
  "previous_status": "Review Required",
  "new_status": "Manual Override",
  "evidence_reference": "RFQ_Pack.pdf#page=12",
  "model_version": "gpt-5.4-mini",
  "registry_version": "GMC_REGISTRY_v3.0"
}
```

### 11.2 PII Redaction & Storage Compliance
* **Data in Transit:** All network traffic encrypted via TLS 1.3.
* **Data at Rest:** Database volumes and S3 storage buckets encrypted using AES-256 with enterprise-managed KMS keys.
* **Log Sanitization:** Application logs must sanitize employee names, mobile numbers, and personal identifiers using regex filters.

---

## 12. Non-Functional Requirements (NFR)

* **NFR-01: Processing Latency:** End-to-end ingestion and extraction for an RFQ pack of up to 100 pages and demography file of 5,000 lives must complete in $\le 45$ seconds.
* **NFR-02: Demography Scale:** The demography engine must handle up to 100,000 member rows without browser UI freeze, using virtualized rendering (TanStack Virtual).
* **NFR-03: Hallucination Prevention:** The secondary reflection pass with `gpt-5.4-mini` must reject extracted fields that lack verbatim support in the source text coordinates.
* **NFR-04: High Availability:** The core application must support $99.9\%$ operational availability during business hours.

---

## 13. Business Acceptance Criteria (AC Matrix)

| ID | Business Acceptance Criterion | Verification Method |
| :--- | :--- | :--- |
| **AC-01** | System accepts multiple heterogeneous files (`.xlsx`, `.pdf`, `.docx`, `.msg`, scans) in a single quotation case. | Upload multi-format package; verify all files parse without error. |
| **AC-02** | Password-protected files prompt the user for credentials, decrypt in memory, and leave no trace of credentials in logs or disk. | Ingest encrypted PDF; inspect database and log sinks to confirm zero credentials persisted. |
| **AC-03** | System extracts Current Coverage and Proposed Coverage into separate columns for all registry fields using `gpt-5.4-mini`. | Compare extraction output against dual-tier RFQ source files. |
| **AC-04** | Compound room rent clauses automatically disaggregate into Parent Room Rent, Normal Room, and ICU limits. | Ingest compound room rent clause; verify three discrete fields populate. |
| **AC-05** | Procedure sub-limits matching Option 1–4 map correctly; non-standard limits are marked `Review Required`. | Run test case with ₹1,20,000 CABG (Option 2) and ₹33,000 Appendectomy (Unmatched). Verify flags. |
| **AC-06** | Demography produces an exact 7-column Excel export in the required sequence: Age, DOB, SI, Relationship, Name, EmpCode, Gender. | Generate demography export; verify column sequence, headers, and date formats. |
| **AC-07** | Age recalculates dynamically when the user toggles between `Current Date` and `Policy Proposal Start Date`. | Switch date mode on UI; confirm all age values update using the completed-year formula. |
| **AC-08** | Group Size, Primary Members, and SME Flag ($\le 250$ lives) update automatically from demography results. | Ingest census with 240 primary workers; verify SME Flag displays `Yes`. Ingest 260 workers; verify `No`. |
| **AC-09** | Under-18 employees, orphan dependants, and age/DOB mismatches are flagged in the Demography Exceptions tab. | Upload erroneous test demography; verify all exceptions appear in the review queue. |
| **AC-10** | Every human modification on the review workbench creates an immutable entry in the audit trail log. | Override a field in the UI; verify old/new value, user email, and timestamp in the audit database. |

---

## 14. Assumptions, Dependencies & Open Items

### 14.1 Assumptions
1. Every RFQ processing run receives the active `GMC Field Registry v3.0` schema definitions.
2. The final underwriting and rate binding decisions remain the responsibility of licensed underwriters.
3. Demography dates follow standard Gregorian calendar formats.

### 14.2 Dependencies
1. Availability of OpenAI `gpt-5.4-mini` endpoint with Zero Data Retention (ZDR) enabled.
2. Corporate egress proxy allowing outbound HTTPS connections to `api.openai.com` and AWS S3.
3. Access to corporate District-to-Zone location masters for geographical tier derivation.

### 14.3 Open Items for Business Confirmation
* **Final Zone Master Table:** Sign-off from Underwriting Operations on the state/district mapping to Zones A, B, C, D.
* **Corporate Buffer Rules:** Finalize standard allocations across family members when corporate buffers are activated.
* **Retention Schedule:** Formal approval of the document retention and purge schedule for uploaded client documents.