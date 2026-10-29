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
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// =============================================================================
// ENUMS
// =============================================================================

export const userRoleEnum = pgEnum("user_role", [
  "admin",
  "underwriter",
  "sales_rm",
  "ops_analyst",
]);

export const caseStatusEnum = pgEnum("case_status", [
  "draft",
  "uploaded",
  "processing",
  "review_required",
  "ready_for_quote",
  "completed",
  "failed",
]);

export const fileCategoryEnum = pgEnum("file_category", [
  "rfq_document",
  "demography_census",
  "supporting_info",
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
  "review_required",
]);

export const confidenceRatingEnum = pgEnum("confidence_rating", [
  "high",
  "medium",
  "low",
]);

export const matchedOptionEnum = pgEnum("matched_option", [
  "option_1",
  "option_2",
  "option_3",
  "option_4",
  "unmatched",
]);

export const ageBasisModeEnum = pgEnum("age_basis_mode", [
  "current_date",
  "policy_proposal_start_date",
]);

export const relationshipEnum = pgEnum("relationship_type", [
  "employee",
  "spouse",
  "child",
  "parent",
  "parent_in_law",
]);

// =============================================================================
// 1. USERS TABLE (Linked to Clerk via clerk_user_id)
// =============================================================================

export const users = pgTable(
  "users",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    clerkUserId: varchar("clerk_user_id", { length: 255 }).notNull().unique(),
    email: varchar("email", { length: 255 }).notNull().unique(),
    fullName: varchar("full_name", { length: 255 }).notNull(),
    role: userRoleEnum("role").notNull().default("sales_rm"),
    branch: varchar("branch", { length: 100 }).default("Corporate"),
    isActive: boolean("is_active").notNull().default(true),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    uniqueIndex("users_clerk_id_idx").on(table.clerkUserId),
    index("users_email_idx").on(table.email),
    index("users_role_idx").on(table.role),
  ],
);

// =============================================================================
// 2. CASES TABLE (Header, Manual Inputs & Group Summaries)
// =============================================================================

export const cases = pgTable(
  "cases",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseNumber: varchar("case_number", { length: 64 }).notNull().unique(),
    assignedUserId: uuid("assigned_user_id").references(() => users.id, {
      onDelete: "set null",
    }),
    status: caseStatusEnum("status").notNull().default("draft"),
    companyName: varchar("company_name", { length: 255 }).notNull(),
    proposalType: varchar("proposal_type", { length: 50 }).default(
      "New Business",
    ),

    // IN-FLIGHT MANUAL INPUTS & AUTO-DERIVED PARAMETERS
    raterType: varchar("rater_type", { length: 100 }).default("-"), // Manual override
    brokeragePct: numeric("brokerage_pct", { precision: 5, scale: 2 }).default(
      "0.00",
    ), // Manual override
    pincode: varchar("pincode", { length: 10 }), // Manual override (6-digit)
    state: varchar("state", { length: 100 }), // Manual override
    district: varchar("district", { length: 100 }), // Manual override
    zone: varchar("zone", { length: 50 }), // Auto-derived from PIN/District

    // DEMOGRAPHY CONFIGURATION & DERIVED METRICS
    ageBasisMode: ageBasisModeEnum("age_basis_mode")
      .notNull()
      .default("current_date"),
    proposalStartDate: timestamp("proposal_start_date", { withTimezone: true }),
    groupSize: integer("group_size").default(0), // Total valid rows
    primaryMembersCount: integer("primary_members_count").default(0), // Total Employee/Self lives
    smeFlag: boolean("sme_flag").default(false), // True if primary members <= 250

    // PIPELINE PERFORMANCE METRICS
    pipelineDurationMs: integer("pipeline_duration_ms"),
    modelVersion: varchar("model_version", { length: 50 }).default(
      "gpt-5.4-mini",
    ),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    uniqueIndex("cases_case_number_idx").on(table.caseNumber),
    index("cases_status_idx").on(table.status),
    index("cases_assigned_user_idx").on(table.assignedUserId),
    index("cases_pincode_zone_idx").on(table.pincode, table.zone),
    index("cases_created_at_desc_idx").on(table.createdAt),
  ],
);

// =============================================================================
// 3. CASE FILES TABLE (Storage Tracker: Local / S3)
// =============================================================================

export const caseFiles = pgTable(
  "case_files",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),
    originalFilename: varchar("original_filename", { length: 255 }).notNull(),
    fileExtension: varchar("file_extension", { length: 20 }).notNull(),
    fileSize: integer("file_size").notNull(),
    fileCategory: fileCategoryEnum("file_category").notNull(),

    // Encryption state
    isEncrypted: boolean("is_encrypted").notNull().default(false),
    isDecryptedSuccessfully: boolean("is_decrypted_successfully")
      .notNull()
      .default(false),

    // Storage reference (Local path or S3 key)
    // Phase 1 Local: storage/inputs/raw/{case_id}/{filename}
    // Phase 2 EC2:   inputs/raw/{case_id}/{filename}
    storagePath: text("storage_path").notNull(),
    storageDriver: varchar("storage_driver", { length: 20 })
      .notNull()
      .default("local"), // 'local' | 's3'

    uploadedAt: timestamp("uploaded_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("case_files_case_id_idx").on(table.caseId),
    index("case_files_category_idx").on(table.fileCategory),
  ],
);

// =============================================================================
// 4. RFQ EXTRACTIONS TABLE (5-Column Quote Review Grid)
// =============================================================================

export const rfqExtractions = pgTable(
  "rfq_extractions",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),
    section: varchar("section", { length: 100 }).notNull(), // 'quotation', 'medical_expenses', 'maternity', etc.

    // COL 1: Quote Fields
    fieldName: varchar("field_name", { length: 150 }).notNull(),

    // COL 2: Coverage Details (Current/Expiring)
    coverageDetails: text("coverage_details"),

    // COL 3: Proposed Details (Requested)
    proposedDetails: text("proposed_details"),

    // COL 4: Source Status
    sourceStatus: sourceStatusEnum("source_status")
      .notNull()
      .default("rfq_data"),

    // COL 5: Confidence
    confidenceRating: confidenceRatingEnum("confidence_rating")
      .notNull()
      .default("high"),
    confidenceScore: numeric("confidence_score", {
      precision: 4,
      scale: 3,
    }).default("0.950"), // 0.000 to 1.000

    // MANUAL OVERRIDE TRACKING
    isManualOverride: boolean("is_manual_override").notNull().default(false),
    overriddenByUserId: uuid("overridden_by_user_id").references(
      () => users.id,
      { onDelete: "set null" },
    ),
    overrideReason: text("override_reason"),

    // CITATION & VERIFICATION EVIDENCE
    sourceFileId: uuid("source_file_id").references(() => caseFiles.id, {
      onDelete: "set null",
    }),
    sourcePageOrSheet: varchar("source_page_or_sheet", { length: 100 }),
    verbatimExcerpt: text("verbatim_excerpt"),
    reflectionExplanation: text("reflection_explanation"), // Pass 2 verification note

    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("rfq_extractions_case_id_idx").on(table.caseId),
    index("rfq_extractions_section_field_idx").on(
      table.section,
      table.fieldName,
    ),
    index("rfq_extractions_status_idx").on(table.sourceStatus),
    uniqueIndex("rfq_extractions_case_field_uniq_idx").on(
      table.caseId,
      table.fieldName,
    ),
  ],
);

// =============================================================================
// 5. PROCEDURE SUBLIMITS TABLE (19 Procedures Option 1–4 Matcher)
// =============================================================================

export const procedureSublimits = pgTable(
  "procedure_sublimits",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),
    procedureName: varchar("procedure_name", { length: 150 }).notNull(),

    // Numerical Matching Pipeline
    extractedAmountRaw: varchar("extracted_amount_raw", {
      length: 100,
    }).notNull(), // Raw string from RFQ
    cleanedAmountNumeric: numeric("cleaned_amount_numeric", {
      precision: 12,
      scale: 2,
    }), // Cleaned integer/decimal
    matchedOption: matchedOptionEnum("matched_option")
      .notNull()
      .default("unmatched"),

    // Status & Manual Overrides
    status: sourceStatusEnum("status").notNull().default("rfq_data"),
    isUnderwriterApproved: boolean("is_underwriter_approved")
      .notNull()
      .default(false),
    approvedByUserId: uuid("approved_by_user_id").references(() => users.id, {
      onDelete: "set null",
    }),
    approvalJustification: text("approval_justification"),

    // Source citation
    sourcePage: varchar("source_page", { length: 50 }),
    verbatimSnippet: text("verbatim_snippet"),
  },
  (table) => [
    index("procedure_sublimits_case_id_idx").on(table.caseId),
    index("procedure_sublimits_matched_option_idx").on(table.matchedOption),
    uniqueIndex("procedure_sublimits_case_proc_uniq_idx").on(
      table.caseId,
      table.procedureName,
    ),
  ],
);

// =============================================================================
// 6. DEMOGRAPHY RECORDS TABLE (Strict 7-Column Roster)
// =============================================================================

export const demographyRecords = pgTable(
  "demography_records",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),

    // STRICT 7-COLUMN SCHEMA SPECIFICATION
    calculatedAge: integer("calculated_age").notNull(), // COL 1: Floor completed age
    dob: varchar("dob", { length: 20 }), // COL 2: Standardized DD-MM-YYYY
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
    hasValidationException: boolean("has_validation_exception")
      .notNull()
      .default(false),
    sourceRowNumber: integer("source_row_number").notNull(),
  },
  (table) => [
    index("demography_records_case_id_idx").on(table.caseId),
    index("demography_records_emp_code_idx").on(
      table.caseId,
      table.employeeCode,
    ),
    index("demography_records_exceptions_idx").on(
      table.caseId,
      table.hasValidationException,
    ),
    index("demography_records_relationship_idx").on(table.relationship),
  ],
);

// =============================================================================
// 7. DEMOGRAPHY EXCEPTIONS TABLE (Exception Triage Queue)
// =============================================================================

export const demographyExceptions = pgTable(
  "demography_exceptions",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),
    // Nullable (deviation from Doc 05): rows that can't be stored as a record
    // (missing Age and DOB, unmapped relationship) still get an exception.
    recordId: uuid("record_id").references(() => demographyRecords.id, {
      onDelete: "cascade",
    }),
    exceptionType: varchar("exception_type", { length: 100 }).notNull(), // 'under18_employee', 'orphan_dependent', 'age_dob_mismatch'
    severity: varchar("severity", { length: 20 }).notNull().default("warning"), // 'critical' | 'warning'
    errorMessage: text("error_message").notNull(),
    isResolved: boolean("is_resolved").notNull().default(false),
    resolvedByUserId: uuid("resolved_by_user_id").references(() => users.id, {
      onDelete: "set null",
    }),
    resolutionAction: text("resolution_action"),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("demography_exceptions_case_id_idx").on(table.caseId),
    index("demography_exceptions_record_id_idx").on(table.recordId),
    index("demography_exceptions_resolved_idx").on(table.isResolved),
  ],
);

// =============================================================================
// 8. AUDIT LOGS TABLE (Strictly Immutable, Append-Only)
// =============================================================================

export const auditLogs = pgTable(
  "audit_logs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    caseId: uuid("case_id")
      .references(() => cases.id, { onDelete: "cascade" })
      .notNull(),
    userId: uuid("user_id").references(() => users.id, {
      onDelete: "set null",
    }),
    userEmail: varchar("user_email", { length: 255 }).notNull(),
    action: varchar("action", { length: 100 }).notNull(), // 'field_override', 'sublimit_override', 'age_basis_recalc', 'case_export'
    targetEntity: varchar("target_entity", { length: 100 }).notNull(), // e.g., 'rfq_extractions.brokerage_pct'
    oldValue: jsonb("old_value"),
    newValue: jsonb("new_value"),
    justificationReason: text("justification_reason"),
    ipAddress: varchar("ip_address", { length: 45 }),
    userAgent: text("user_agent"),
    timestamp: timestamp("timestamp", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("audit_logs_case_id_idx").on(table.caseId),
    index("audit_logs_user_id_idx").on(table.userId),
    index("audit_logs_action_idx").on(table.action),
    index("audit_logs_timestamp_desc_idx").on(table.timestamp),
  ],
);

// =============================================================================
// REFERENCE: SUB-LIMIT REGISTRY (BRD §8.1, 19 Procedures × Option 1–4)
// Not in Backend Schema v4.0; added for the Master Registry (Plan Phase 2 seed).
// =============================================================================

export const sublimitRegistry = pgTable("sublimit_registry", {
  id: uuid("id").primaryKey().defaultRandom(),
  procedureName: varchar("procedure_name", { length: 150 }).notNull().unique(),
  option1Amount: numeric("option_1_amount", {
    precision: 12,
    scale: 2,
  }).notNull(),
  option2Amount: numeric("option_2_amount", {
    precision: 12,
    scale: 2,
  }).notNull(),
  option3Amount: numeric("option_3_amount", {
    precision: 12,
    scale: 2,
  }).notNull(),
  option4Amount: numeric("option_4_amount", {
    precision: 12,
    scale: 2,
  }).notNull(),
  displayOrder: integer("display_order").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});

// =============================================================================
// REFERENCE: ZONE MASTER (PINCODE / District → Zone A–D, Pan India)
// Not in Backend Schema v4.0; mapping data awaits Underwriting Ops sign-off (BRD §10).
// =============================================================================

export const zoneTierEnum = pgEnum("zone_tier", [
  "Zone A",
  "Zone B",
  "Zone C",
  "Zone D",
  "Pan India",
]);

export const zoneMaster = pgTable(
  "zone_master",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    state: varchar("state", { length: 100 }).notNull(),
    district: varchar("district", { length: 100 }).notNull(),
    pincode: varchar("pincode", { length: 10 }), // Null = district-level mapping
    zone: zoneTierEnum("zone").notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    uniqueIndex("zone_master_pincode_idx").on(table.pincode),
    index("zone_master_state_district_idx").on(table.state, table.district),
  ],
);

// =============================================================================
// RELATIONS DEFINITIONS (Drizzle Relational Queries)
// =============================================================================

export const usersRelations = relations(users, ({ many }) => ({
  cases: many(cases),
  auditLogs: many(auditLogs),
}));

export const casesRelations = relations(cases, ({ one, many }) => ({
  assignedUser: one(users, {
    fields: [cases.assignedUserId],
    references: [users.id],
  }),
  files: many(caseFiles),
  extractions: many(rfqExtractions),
  sublimits: many(procedureSublimits),
  demography: many(demographyRecords),
  exceptions: many(demographyExceptions),
  auditLogs: many(auditLogs),
}));

export const caseFilesRelations = relations(caseFiles, ({ one }) => ({
  case: one(cases, {
    fields: [caseFiles.caseId],
    references: [cases.id],
  }),
}));

export const rfqExtractionsRelations = relations(rfqExtractions, ({ one }) => ({
  case: one(cases, {
    fields: [rfqExtractions.caseId],
    references: [cases.id],
  }),
  sourceFile: one(caseFiles, {
    fields: [rfqExtractions.sourceFileId],
    references: [caseFiles.id],
  }),
  overriddenByUser: one(users, {
    fields: [rfqExtractions.overriddenByUserId],
    references: [users.id],
  }),
}));

export const procedureSublimitsRelations = relations(
  procedureSublimits,
  ({ one }) => ({
    case: one(cases, {
      fields: [procedureSublimits.caseId],
      references: [cases.id],
    }),
    approvedByUser: one(users, {
      fields: [procedureSublimits.approvedByUserId],
      references: [users.id],
    }),
  }),
);

export const demographyRecordsRelations = relations(
  demographyRecords,
  ({ one, many }) => ({
    case: one(cases, {
      fields: [demographyRecords.caseId],
      references: [cases.id],
    }),
    exceptions: many(demographyExceptions),
  }),
);

export const demographyExceptionsRelations = relations(
  demographyExceptions,
  ({ one }) => ({
    record: one(demographyRecords, {
      fields: [demographyExceptions.recordId],
      references: [demographyRecords.id],
    }),
    case: one(cases, {
      fields: [demographyExceptions.caseId],
      references: [cases.id],
    }),
    resolvedByUser: one(users, {
      fields: [demographyExceptions.resolvedByUserId],
      references: [users.id],
    }),
  }),
);

export const auditLogsRelations = relations(auditLogs, ({ one }) => ({
  case: one(cases, {
    fields: [auditLogs.caseId],
    references: [cases.id],
  }),
  user: one(users, {
    fields: [auditLogs.userId],
    references: [users.id],
  }),
}));
