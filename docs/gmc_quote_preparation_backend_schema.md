# DOCUMENT 05: BACKEND SCHEMA — DATA MODEL & AUTH ARCHITECTURE
## Application Name: QuotePulse GMC (AI-Driven Quote Preparation & Demography Workbench)

| Specification Field | Architecture Standard & Specification |
| :--- | :--- |
| **Document Version** | 4.0 (Master Engineering Baseline) |
| **Document Type** | Backend Schema, Data Model & Auth Architecture Specification |
| **Date** | 29 October 2026 |
| **Parent Documents** | `BRD v3.0`, `PRD v2.0`, `TRD v4.0`, `App Flow v4.0`, `UI/UX Brief v4.0` |
| **Database Provider** | **Neon** (Serverless PostgreSQL 16 with native connection pooling, auto-suspend, and branch isolation). |
| **ORM / Query Engine** | **Drizzle ORM** (`drizzle-orm/pg-core`) written in 100% strict TypeScript with zero runtime overhead and end-to-end type safety. |
| **Auth Provider** | **Clerk** (Enterprise SSO / SAML / OIDC, MFA, organization-level RBAC). Public registration is disabled; users are synced to DB via Clerk webhooks. |
| **Dual Storage Strategy** | **Local Filesystem** (`./storage/inputs/raw/` & `./storage/outputs/analysis/`) during Phase 1 local development, transitioning to **AWS S3** (`s3://.../inputs/raw/` and `s3://.../outputs/analysis/`) in Phase 2 on AWS EC2. |

---

## 1. Relational Entity Relationship Diagram (ERD)

```
┌─────────────────────────┐
│         users           │
├─────────────────────────┤
│ id (PK, UUID)           │
│ clerk_user_id (UNIQUE)  │◀──┐
│ email (UNIQUE)          │   │
│ role (ENUM)             │   │
└────────────┬────────────┘   │
             │ 1              │
             │                │
             │ N              │
┌────────────▼────────────┐   │
│         cases           │   │
├─────────────────────────┤   │
│ id (PK, UUID)           │   │
│ case_number (UNIQUE)    │   │
│ assigned_user_id (FK)───┼───┘
│ company_name            │
│ rater_type (MANUAL)     │
│ brokerage_pct (MANUAL)  │
│ pincode (MANUAL)        │
│ state (MANUAL)          │
│ district (MANUAL)       │
│ zone (AI DERIVED)       │
│ age_basis_mode          │
│ proposal_start_date     │
│ group_size, sme_flag    │
└────────────┬────────────┘
             │ 1
             ├──────────────────────────┬─────────────────────────┬─────────────────────────┐
             │ N                        │ N                       │ N                       │ N
┌────────────▼────────────┐┌────────────▼───────────┐┌────────────▼──────────┐┌─────────────▼──────────┐
│       case_files        ││     rfq_extractions     ││ procedure_sublimits    ││   demography_records    │
├─────────────────────────┤├─────────────────────────┤├────────────────────────┤├─────────────────────────┤
│ id (PK, UUID)           ││ id (PK, UUID)           ││ id (PK, UUID)          ││ id (PK, UUID)           │
│ case_id (FK)            ││ case_id (FK)            ││ case_id (FK)           ││ case_id (FK)            │
│ original_filename       ││ field_name (CANONICAL)  ││ procedure_name (CANON) ││ calculated_age (COL 1)  │
│ file_type, category     ││ coverage_details (CURR) ││ extracted_amount_raw   ││ dob (COL 2)             │
│ is_encrypted, is_open   ││ proposed_details (PROP) ││ cleaned_amount_numeric ││ sum_insured (COL 3)     │
│ storage_path (S3/Local) ││ source_status (ENUM)    ││ matched_option (1-4)   ││ relationship (COL 4)    │
└─────────────────────────┘│ confidence_score        ││ status (ENUM)          ││ member_name (COL 5)     │
                           │ is_manual_override      │└────────────────────────┘│ employee_code (COL 6)   │
                           │ evidence_page, excerpt  │                          │ gender (COL 7)          │
                           └─────────────────────────┘                          │ under18_flag, is_orphan │
                                                                                └───────────┬─────────────┘
                                                                                            │ 1
                                                                                            │ N
                                                                                ┌───────────▼─────────────┐
                                                                                │  demography_exceptions  │
                                                                                ├─────────────────────────┤
                                                                                │ id (PK, UUID)           │
                                                                                │ record_id (FK)          │
                                                                                │ exception_type          │
                                                                                │ severity, message       │
                                                                                └─────────────────────────┘
```

---

## 2. Complete Drizzle ORM TypeScript Schema (`src/db/schema.ts`)

```typescript
import { 
  pgTable, 
  uuid, 
  text, 
  varchar, 
  integer, 
  numeric, 
  boolean, 
  timestamp, 
  jsonb, 
  pgEnum, 
  index, 
  uniqueIndex 
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// =============================================================================
// ENUMS
// =============================================================================

export const userRoleEnum = pgEnum("user_role", [
  "admin", 
  "underwriter", 
  "sales_rm", 
  "ops_analyst"
]);

export const caseStatusEnum = pgEnum("case_status", [
  "draft", 
  "uploaded", 
  "processing", 
  "review_required", 
  "ready_for_quote", 
  "completed", 
  "failed"
]);

export const fileCategoryEnum = pgEnum("file_category", [
  "rfq_document", 
  "demography_census", 
  "supporting_info"
]);

export const sourceStatusEnum = pgEnum("source_status", [
  "rfq_data", 
  "default_data", 
  "ai_derived", 
  "demography_derived", 
  "manual", 
  "fixed", 
  "not_found", 
  "ambiguous", 
  "conflict", 
  "review_required"
]);

export const confidenceRatingEnum = pgEnum("confidence_rating", [
  "high", 
  "medium", 
  "low"
]);

export const matchedOptionEnum = pgEnum("matched_option", [
  "option_1", 
  "option_2", 
  "option_3", 
  "option_4", 
  "unmatched"
]);

export const ageBasisModeEnum = pgEnum("age_basis_mode", [
  "current_date", 
  "policy_proposal_start_date"
]);

export const relationshipEnum = pgEnum("relationship_type", [
  "employee", 
  "spouse", 
  "child", 
  "parent", 
  "parent_in_law"
]);

// =============================================================================
// 1. USERS TABLE (Linked to Clerk via clerk_user_id)
// =============================================================================

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  clerkUserId: varchar("clerk_user_id", { length: 255 }).notNull().unique(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  fullName: varchar("full_name", { length: 255 }).notNull(),
  role: userRoleEnum("role").notNull().default("sales_rm"),
  branch: varchar("branch", { length: 100 }).default("Corporate"),
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  uniqueIndex("users_clerk_id_idx").on(table.clerkUserId),
  index("users_email_idx").on(table.email),
  index("users_role_idx").on(table.role)
]);

// =============================================================================
// 2. CASES TABLE (Header, Manual Inputs & Group Summaries)
// =============================================================================

export const cases = pgTable("cases", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseNumber: varchar("case_number", { length: 64 }).notNull().unique(),
  assignedUserId: uuid("assigned_user_id").references(() => users.id, { onDelete: "set null" }),
  status: caseStatusEnum("status").notNull().default("draft"),
  companyName: varchar("company_name", { length: 255 }).notNull(),
  proposalType: varchar("proposal_type", { length: 50 }).default("New Business"),
  
  // IN-FLIGHT MANUAL INPUTS & AUTO-DERIVED PARAMETERS
  raterType: varchar("rater_type", { length: 100 }).default("-"), // Manual override
  brokeragePct: numeric("brokerage_pct", { precision: 5, scale: 2 }).default("0.00"), // Manual override
  pincode: varchar("pincode", { length: 10 }), // Manual override (6-digit)
  state: varchar("state", { length: 100 }), // Manual override
  district: varchar("district", { length: 100 }), // Manual override
  zone: varchar("zone", { length: 50 }), // Auto-derived from PIN/District
  
  // DEMOGRAPHY CONFIGURATION & DERIVED METRICS
  ageBasisMode: ageBasisModeEnum("age_basis_mode").notNull().default("current_date"),
  proposalStartDate: timestamp("proposal_start_date", { withTimezone: true }),
  groupSize: integer("group_size").default(0), // Total valid rows
  primaryMembersCount: integer("primary_members_count").default(0), // Total Employee/Self lives
  smeFlag: boolean("sme_flag").default(false), // True if primary members <= 250
  
  // PIPELINE PERFORMANCE METRICS
  pipelineDurationMs: integer("pipeline_duration_ms"),
  modelVersion: varchar("model_version", { length: 50 }).default("gpt-5.4-mini"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  uniqueIndex("cases_case_number_idx").on(table.caseNumber),
  index("cases_status_idx").on(table.status),
  index("cases_assigned_user_idx").on(table.assignedUserId),
  index("cases_pincode_zone_idx").on(table.pincode, table.zone),
  index("cases_created_at_desc_idx").on(table.createdAt)
]);

// =============================================================================
// 3. CASE FILES TABLE (Storage Tracker: Local / S3)
// =============================================================================

export const caseFiles = pgTable("case_files", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  originalFilename: varchar("original_filename", { length: 255 }).notNull(),
  fileExtension: varchar("file_extension", { length: 20 }).notNull(),
  fileSize: integer("file_size").notNull(),
  fileCategory: fileCategoryEnum("file_category").notNull(),
  
  // Encryption state
  isEncrypted: boolean("is_encrypted").notNull().default(false),
  isDecryptedSuccessfully: boolean("is_decrypted_successfully").notNull().default(false),
  
  // Storage reference (Local path or S3 key)
  // Phase 1 Local: storage/inputs/raw/{case_id}/{filename}
  // Phase 2 EC2:   inputs/raw/{case_id}/{filename}
  storagePath: text("storage_path").notNull(),
  storageDriver: varchar("storage_driver", { length: 20 }).notNull().default("local"), // 'local' | 's3'
  
  uploadedAt: timestamp("uploaded_at", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  index("case_files_case_id_idx").on(table.caseId),
  index("case_files_category_idx").on(table.fileCategory)
]);

// =============================================================================
// 4. RFQ EXTRACTIONS TABLE (5-Column Quote Review Grid)
// =============================================================================

export const rfqExtractions = pgTable("rfq_extractions", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  section: varchar("section", { length: 100 }).notNull(), // 'quotation', 'medical_expenses', 'maternity', etc.
  
  // COL 1: Quote Fields
  fieldName: varchar("field_name", { length: 150 }).notNull(),
  
  // COL 2: Coverage Details (Current/Expiring)
  coverageDetails: text("coverage_details"),
  
  // COL 3: Proposed Details (Requested)
  proposedDetails: text("proposed_details"),
  
  // COL 4: Source Status
  sourceStatus: sourceStatusEnum("source_status").notNull().default("rfq_data"),
  
  // COL 5: Confidence
  confidenceRating: confidenceRatingEnum("confidence_rating").notNull().default("high"),
  confidenceScore: numeric("confidence_score", { precision: 4, scale: 3 }).default("0.950"), // 0.000 to 1.000
  
  // MANUAL OVERRIDE TRACKING
  isManualOverride: boolean("is_manual_override").notNull().default(false),
  overriddenByUserId: uuid("overridden_by_user_id").references(() => users.id, { onDelete: "set null" }),
  overrideReason: text("override_reason"),
  
  // CITATION & VERIFICATION EVIDENCE
  sourceFileId: uuid("source_file_id").references(() => caseFiles.id, { onDelete: "set null" }),
  sourcePageOrSheet: varchar("source_page_or_sheet", { length: 100 }),
  verbatimExcerpt: text("verbatim_excerpt"),
  reflectionExplanation: text("reflection_explanation"), // Pass 2 verification note
  
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  index("rfq_extractions_case_id_idx").on(table.caseId),
  index("rfq_extractions_section_field_idx").on(table.section, table.fieldName),
  index("rfq_extractions_status_idx").on(table.sourceStatus),
  uniqueIndex("rfq_extractions_case_field_uniq_idx").on(table.caseId, table.fieldName)
]);

// =============================================================================
// 5. PROCEDURE SUBLIMITS TABLE (19 Procedures Option 1–4 Matcher)
// =============================================================================

export const procedureSublimits = pgTable("procedure_sublimits", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  procedureName: varchar("procedure_name", { length: 150 }).notNull(),
  
  // Numerical Matching Pipeline
  extractedAmountRaw: varchar("extracted_amount_raw", { length: 100 }).notNull(), // Raw string from RFQ
  cleanedAmountNumeric: numeric("cleaned_amount_numeric", { precision: 12, scale: 2 }), // Cleaned integer/decimal
  matchedOption: matchedOptionEnum("matched_option").notNull().default("unmatched"),
  
  // Status & Manual Overrides
  status: sourceStatusEnum("status").notNull().default("rfq_data"),
  isUnderwriterApproved: boolean("is_underwriter_approved").notNull().default(false),
  approvedByUserId: uuid("approved_by_user_id").references(() => users.id, { onDelete: "set null" }),
  approvalJustification: text("approval_justification"),
  
  // Source citation
  sourcePage: varchar("source_page", { length: 50 }),
  verbatimSnippet: text("verbatim_snippet")
}, (table) => [
  index("procedure_sublimits_case_id_idx").on(table.caseId),
  index("procedure_sublimits_matched_option_idx").on(table.matchedOption),
  uniqueIndex("procedure_sublimits_case_proc_uniq_idx").on(table.caseId, table.procedureName)
]);

// =============================================================================
// 6. DEMOGRAPHY RECORDS TABLE (Strict 7-Column Roster)
// =============================================================================

export const demographyRecords = pgTable("demography_records", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  
  // STRICT 7-COLUMN SCHEMA SPECIFICATION
  calculatedAge: integer("calculated_age").notNull(), // COL 1: Floor completed age
  dob: varchar("dob", { length: 20 }),                // COL 2: Standardized DD-MM-YYYY
  sumInsured: numeric("sum_insured", { precision: 14, scale: 2 }), // COL 3: Member SI
  relationship: relationshipEnum("relationship").notNull(), // COL 4: Canonical category
  memberName: varchar("member_name", { length: 255 }).notNull(), // COL 5: Full Name
  employeeCode: varchar("employee_code", { length: 100 }).notNull(), // COL 6: EmpCode
  gender: varchar("gender", { length: 20 }).notNull(), // COL 7: Gender
  
  // INTERNAL INTEGRITY VALIDATION FLAGS
  sourceAgeRaw: integer("source_age_raw"),
  isUnder18Employee: boolean("is_under18_employee").notNull().default(false),
  isOrphanDependent: boolean("is_orphan_dependent").notNull().default(false),
  isDuplicateRecord: boolean("is_duplicate_record").notNull().default(false),
  hasValidationException: boolean("has_validation_exception").notNull().default(false),
  sourceRowNumber: integer("source_row_number").notNull()
}, (table) => [
  index("demography_records_case_id_idx").on(table.caseId),
  index("demography_records_emp_code_idx").on(table.caseId, table.employeeCode),
  index("demography_records_exceptions_idx").on(table.caseId, table.hasValidationException),
  index("demography_records_relationship_idx").on(table.relationship)
]);

// =============================================================================
// 7. DEMOGRAPHY EXCEPTIONS TABLE (Exception Triage Queue)
// =============================================================================

export const demographyExceptions = pgTable("demography_exceptions", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  recordId: uuid("record_id").references(() => demographyRecords.id, { onDelete: "cascade" }).notNull(),
  exceptionType: varchar("exception_type", { length: 100 }).notNull(), // 'under18_employee', 'orphan_dependent', 'age_dob_mismatch'
  severity: varchar("severity", { length: 20 }).notNull().default("warning"), // 'critical' | 'warning'
  errorMessage: text("error_message").notNull(),
  isResolved: boolean("is_resolved").notNull().default(false),
  resolvedByUserId: uuid("resolved_by_user_id").references(() => users.id, { onDelete: "set null" }),
  resolutionAction: text("resolution_action"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  index("demography_exceptions_case_id_idx").on(table.caseId),
  index("demography_exceptions_record_id_idx").on(table.recordId),
  index("demography_exceptions_resolved_idx").on(table.isResolved)
]);

// =============================================================================
// 8. AUDIT LOGS TABLE (Strictly Immutable, Append-Only)
// =============================================================================

export const auditLogs = pgTable("audit_logs", {
  id: uuid("id").primaryKey().defaultRandom(),
  caseId: uuid("case_id").references(() => cases.id, { onDelete: "cascade" }).notNull(),
  userId: uuid("user_id").references(() => users.id, { onDelete: "set null" }),
  userEmail: varchar("user_email", { length: 255 }).notNull(),
  action: varchar("action", { length: 100 }).notNull(), // 'field_override', 'sublimit_override', 'age_basis_recalc', 'case_export'
  targetEntity: varchar("target_entity", { length: 100 }).notNull(), // e.g., 'rfq_extractions.brokerage_pct'
  oldValue: jsonb("old_value"),
  newValue: jsonb("new_value"),
  justificationReason: text("justification_reason"),
  ipAddress: varchar("ip_address", { length: 45 }),
  userAgent: text("user_agent"),
  timestamp: timestamp("timestamp", { withTimezone: true }).defaultNow().notNull()
}, (table) => [
  index("audit_logs_case_id_idx").on(table.caseId),
  index("audit_logs_user_id_idx").on(table.userId),
  index("audit_logs_action_idx").on(table.action),
  index("audit_logs_timestamp_desc_idx").on(table.timestamp)
]);

// =============================================================================
// RELATIONS DEFINITIONS (Drizzle Relational Queries)
// =============================================================================

export const usersRelations = relations(users, ({ many }) => ({
  cases: many(cases),
  auditLogs: many(auditLogs)
}));

export const casesRelations = relations(cases, ({ one, many }) => ({
  assignedUser: one(users, {
    fields: [cases.assignedUserId],
    references: [users.id]
  }),
  files: many(caseFiles),
  extractions: many(rfqExtractions),
  sublimits: many(procedureSublimits),
  demography: many(demographyRecords),
  exceptions: many(demographyExceptions),
  auditLogs: many(auditLogs)
}));

export const caseFilesRelations = relations(caseFiles, ({ one }) => ({
  case: one(cases, {
    fields: [caseFiles.caseId],
    references: [cases.id]
  })
}));

export const rfqExtractionsRelations = relations(rfqExtractions, ({ one }) => ({
  case: one(cases, {
    fields: [rfqExtractions.caseId],
    references: [cases.id]
  }),
  sourceFile: one(caseFiles, {
    fields: [rfqExtractions.sourceFileId],
    references: [caseFiles.id]
  }),
  overriddenByUser: one(users, {
    fields: [rfqExtractions.overriddenByUserId],
    references: [users.id]
  })
}));

export const procedureSublimitsRelations = relations(procedureSublimits, ({ one }) => ({
  case: one(cases, {
    fields: [procedureSublimits.caseId],
    references: [cases.id]
  }),
  approvedByUser: one(users, {
    fields: [procedureSublimits.approvedByUserId],
    references: [users.id]
  })
}));

export const demographyRecordsRelations = relations(demographyRecords, ({ one, many }) => ({
  case: one(cases, {
    fields: [demographyRecords.caseId],
    references: [cases.id]
  }),
  exceptions: many(demographyExceptions)
}));

export const demographyExceptionsRelations = relations(demographyExceptions, ({ one }) => ({
  record: one(demographyRecords, {
    fields: [demographyExceptions.recordId],
    references: [demographyRecords.id]
  }),
  case: one(cases, {
    fields: [demographyExceptions.caseId],
    references: [cases.id]
  }),
  resolvedByUser: one(users, {
    fields: [demographyExceptions.resolvedByUserId],
    references: [users.id]
  })
}));

export const auditLogsRelations = relations(auditLogs, ({ one }) => ({
  case: one(cases, {
    fields: [auditLogs.caseId],
    references: [cases.id]
  }),
  user: one(users, {
    fields: [auditLogs.userId],
    references: [users.id]
  })
}));
```

---

## 3. Row Level Security (RLS) SQL Script (`migrations/0001_rls.sql`)

PostgreSQL Row Level Security ensures tenant data isolation and immutable audit logs:

```sql
-- 1. Enable RLS on all sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE rfq_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE procedure_sublimits ENABLE ROW LEVEL SECURITY;
ALTER TABLE demography_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE demography_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- 2. Create helper functions to extract session user identity from Clerk JWT claims
CREATE OR REPLACE FUNCTION current_app_user_id() RETURNS uuid AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_user_id', true), '')::uuid;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION current_app_user_role() RETURNS text AS $$
BEGIN
  RETURN COALESCE(current_setting('app.current_user_role', true), 'sales_rm');
END;
$$ LANGUAGE plpgsql STABLE;

-- 3. Policy: Cases visibility
-- Admins and Underwriters can view all cases. Sales RMs can view assigned cases.
CREATE POLICY cases_select_policy ON cases
  FOR SELECT
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    assigned_user_id = current_app_user_id()
  );

CREATE POLICY cases_modify_policy ON cases
  FOR ALL
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    assigned_user_id = current_app_user_id()
  );

-- 4. Policy: Cascade access for related child tables
CREATE POLICY rfq_extractions_policy ON rfq_extractions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = rfq_extractions.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );

CREATE POLICY procedure_sublimits_policy ON procedure_sublimits
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = procedure_sublimits.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );

CREATE POLICY demography_records_policy ON demography_records
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = demography_records.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );

-- 5. Policy: IMMUTABLE AUDIT LOG (Strict Append-Only)
-- Users can insert audit entries and read logs; UPDATE and DELETE are completely blocked.
CREATE POLICY audit_logs_insert_policy ON audit_logs
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY audit_logs_select_policy ON audit_logs
  FOR SELECT
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = audit_logs.case_id 
        AND cases.assigned_user_id = current_app_user_id()
    )
  );

-- Strictly REVOKE UPDATE and DELETE permissions on audit_logs from all roles
REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM PUBLIC;
```

---

## 4. User Roles & Permission Matrix

| Role | Access Scope | Can Upload Cases | Can Edit Manual Inputs (Brokerage, PIN, etc.) | Can Resolve Sub-Limit Exceptions | Can Recalculate Demography | Can Invite Users | Can Modify Master Registry |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`admin`** | System-wide (all cases) | Yes | Yes | Yes | Yes | **Yes** | **Yes** |
| **`underwriter`** | System-wide (all cases) | Yes | Yes | **Yes (Authorize)** | Yes | No | Read-only |
| **`sales_rm`** | Assigned cases only | **Yes** | **Yes** | View-only | Yes | No | Read-only |
| **`ops_analyst`** | System-wide (demography focused) | Yes | Read-only | View-only | **Yes** | No | Read-only |

---

## 5. Storage Contract: Local Filesystem to AWS S3 Promotion

To satisfy the **Local-First Build Mandate**, the application implements an abstraction layer (`StorageService`) with identical path structures across environments:

```
STORAGE ROOT
├── inputs/
│   └── raw/
│       └── {case_id}/
│           ├── 1730200000_RFQ_Apex_2026.pdf
│           └── 1730200001_Apex_Census_Locked.xlsx
│
└── outputs/
    └── analysis/
        └── {case_id}/
            ├── quote_extracted_5col.json
            ├── standardized_demography_7col.xlsx
            ├── gmc_quote_summary_sheet.xlsx
            ├── sublimits_matching_report.json
            └── exceptions_anomalies.json
```

### Storage Driver Abstraction (`services/backend/app/services/storage.py`)
```python
import os
import io
from abc import ABC, abstractmethod
from app.core.config import settings

class StorageDriver(ABC):
    @abstractmethod
    def save_raw_input(self, case_id: str, filename: str, content: bytes) -> str:
        pass

    @abstractmethod
    def read_stream(self, path: str) -> io.BytesIO:
        pass

    @abstractmethod
    def save_analysis_output(self, case_id: str, filename: str, content: bytes) -> str:
        pass

class LocalStorageDriver(StorageDriver):
    """Used in Phase 1: Local development with zero Docker/cloud blockers."""
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = base_dir

    def save_raw_input(self, case_id: str, filename: str, content: bytes) -> str:
        rel_path = f"inputs/raw/{case_id}/{filename}"
        full_path = os.path.join(self.base_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return full_path

    def read_stream(self, path: str) -> io.BytesIO:
        with open(path, "rb") as f:
            return io.BytesIO(f.read())

    def save_analysis_output(self, case_id: str, filename: str, content: bytes) -> str:
        rel_path = f"outputs/analysis/{case_id}/{filename}"
        full_path = os.path.join(self.base_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return full_path

class S3StorageDriver(StorageDriver):
    """Used in Phase 2: Production on AWS EC2 behind corporate egress proxy."""
    def __init__(self):
        import boto3
        from botocore.config import Config
        self.bucket = settings.GMC_S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            config=Config(
                proxies={
                    "http": settings.HTTP_PROXY, 
                    "https": settings.HTTPS_PROXY
                } if settings.HTTP_PROXY else None
            )
        )

    def save_raw_input(self, case_id: str, filename: str, content: bytes) -> str:
        key = f"inputs/raw/{case_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket, 
            Key=key, 
            Body=content, 
            ServerSideEncryption="AES256"
        )
        return key

    def read_stream(self, path: str) -> io.BytesIO:
        res = self.client.get_object(Bucket=self.bucket, Key=path)
        return io.BytesIO(res["Body"].read())

    def save_analysis_output(self, case_id: str, filename: str, content: bytes) -> str:
        key = f"outputs/analysis/{case_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket, 
            Key=key, 
            Body=content, 
            ServerSideEncryption="AES256"
        )
        return key

def get_storage() -> StorageDriver:
    if settings.STORAGE_DRIVER == "s3":
        return S3StorageDriver()
    return LocalStorageDriver(base_dir=settings.LOCAL_STORAGE_DIR)
```

---

## 6. Sensitive Fields & PII Exclusion Policy

To comply with data privacy policies and prevent data leaks:

1. **Passwords (Zero-Persistence Guarantee):**
   * Decryption passwords for locked Excel or PDF files are **never** stored in database tables, session caches, Redis keys, or system log streams.
   * Passwords exist exclusively in volatile memory for the duration of the in-memory `tmpfs` decryption operation and are explicitly overwritten with null bytes after stream ingestion.
2. **Member Demographic PII Exclusion from AI Models:**
   * Employee names, dates of birth, employee codes, and medical sums insured are processed **exclusively** within the vectorized Polars engine in backend memory.
   * Demographic data rows are **never** passed into OpenAI prompt contexts or vector indexes.
3. **Log Sanitization:**
   * Backend logs must pass through an automated PII-scrubber interceptor to redact employee identification codes and Indian mobile numbers matching regex `^[6-9][0-9]{9}$`.

---

## 7. Vector Embeddings Architecture (Explicit Assessment)

* **Decision: Vector Embeddings Table Excluded (`pgvector` NOT Used).**
* **Technical Justification:**
  * Rather than splitting complex insurance RFQ packages into fragmented chunks, computing vector embeddings, and running semantic similarity search (which loses spatial context across multi-page tables), the architecture utilizes the **native 400,000-token context window of `gpt-5.4-mini`**.
  * The entire layout-parsed Markdown representation of multi-document tender packages is ingested in a single unified prompt context. This guarantees that interconnected clauses (e.g., room rent parent clauses, corporate buffer caps, and maternity waivers) are evaluated in full document context with zero retrieval-induced hallucinations.
  * Eliminating `pgvector` reduces database compute overhead, removes embedding model latency, and prevents vector index synchronization drift.

---

## 8. Complete REST API Endpoint Catalog

All endpoints are prefixed with `/api/v1` and protected by Clerk Bearer JWT tokens:

### 8.1 Cases & Ingestion API
| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/cases` | All | Fetch paginated case list with status filters. |
| `POST` | `/cases` | `sales_rm`, `underwriter`, `admin` | Create a new GMC quotation case record. |
| `GET` | `/cases/{id}` | All | Fetch single case details, manual inputs, and derived metrics. |
| `POST` | `/cases/{id}/upload` | `sales_rm`, `underwriter`, `admin` | Multipart upload for RFQ packs and census sheets. |
| `POST` | `/cases/{id}/decrypt` | `sales_rm`, `underwriter`, `admin` | Submit ephemeral password for in-memory decryption. |
| `POST` | `/cases/{id}/process` | `sales_rm`, `underwriter`, `admin` | Trigger asynchronous extraction pipeline via Celery. |
| `GET` | `/cases/{id}/pipeline-status` | All | Server-Sent Events (SSE) stream for real-time stepper progress. |

### 8.2 Quote Form & Manual Inputs API
| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/cases/{id}/extractions` | All | Fetch the 5-column quote form review records. |
| `PATCH` | `/cases/{id}/extractions/{field_name}` | `sales_rm`, `underwriter`, `admin` | Apply manual override to a quote field with mandatory justification. |
| `PATCH` | `/cases/{id}/manual-inputs` | `sales_rm`, `underwriter`, `admin` | Update in-flight inputs: `raterType`, `brokeragePct`, `pincode`, `state`, `district`. |
| `POST` | `/cases/{id}/recalculate-zone` | All | Trigger automatic recalculation of `zone` from PIN/District. |

### 8.3 Demography & Age Recalculation API
| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/cases/{id}/demography` | All | Virtualized pagination for the 7-column demography roster. |
| `POST` | `/cases/{id}/demography/recalculate-age` | `ops_analyst`, `underwriter`, `admin` | Recalculate member ages across the roster based on chosen date mode. |
| `GET` | `/cases/{id}/demography/exceptions` | All | Fetch demographic exceptions queue (`under18`, orphans, duplicates). |
| `PATCH` | `/cases/{id}/demography/exceptions/{exc_id}` | `ops_analyst`, `underwriter`, `admin` | Resolve demographic validation exception with audit action. |

### 8.4 Procedure Sub-Limits & Exceptions API
| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/cases/{id}/sublimits` | All | Fetch all 19 procedure sub-limit records with Option 1–4 matches. |
| `PATCH` | `/cases/{id}/sublimits/{proc_name}` | `underwriter`, `admin` | Authorize/override an unmatched sub-limit with justification. |

### 8.5 Export & Audit Trail API
| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/cases/{id}/export/quote-excel` | All | Generate and download the reviewed Quote Excel sheet. |
| `GET` | `/cases/{id}/export/demography-excel`| All | Generate and download the clean 7-column Demography Excel. |
| `GET` | `/cases/{id}/audit-logs` | `underwriter`, `admin` | Fetch chronological audit trail changelog for the case. |