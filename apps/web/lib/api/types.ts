// Response shapes of the FastAPI workbench API (services/backend/app/api/v1).

export type UserRole = "admin" | "underwriter" | "sales_rm" | "ops_analyst";

export const CASE_STATUSES = [
  "draft",
  "uploaded",
  "processing",
  "review_required",
  "ready_for_quote",
  "completed",
  "failed",
] as const;
export type CaseStatus = (typeof CASE_STATUSES)[number];

export type CaseListItem = {
  id: string;
  case_number: string;
  company_name: string;
  status: CaseStatus;
  status_label: string;
  proposal_type: string | null;
  group_size: number | null;
  primary_members_count: number | null;
  sme_flag: boolean | null;
  zone: string | null;
  created_at: string;
  updated_at: string;
  assignee_name: string | null;
  open_exceptions: number;
};

export type CaseList = {
  items: CaseListItem[];
  total: number;
  page: number;
  page_size: number;
  summary: {
    total: number;
    needs_review: number;
    prepared: number;
    avg_pipeline_ms: number | null;
  };
};

export type CaseFile = {
  id: string;
  original_filename: string;
  file_extension: string;
  file_size: number;
  file_category: "rfq_document" | "demography_census" | "supporting_info";
  is_encrypted: boolean;
  is_decrypted_successfully: boolean;
  uploaded_at: string;
};

export type AgeBasisMode = "current_date" | "policy_proposal_start_date";

export type CaseDetail = {
  id: string;
  case_number: string;
  company_name: string;
  status: CaseStatus;
  status_label: string;
  proposal_type: string | null;
  rater_type: string | null;
  brokerage_pct: string | null;
  pincode: string | null;
  state: string | null;
  district: string | null;
  zone: string | null;
  age_basis_mode: AgeBasisMode;
  proposal_start_date: string | null;
  group_size: number | null;
  primary_members_count: number | null;
  sme_flag: boolean | null;
  pipeline_duration_ms: number | null;
  model_version: string | null;
  created_at: string;
  updated_at: string;
  assignee_name: string | null;
  assignee_email: string | null;
  files: CaseFile[];
  counts: {
    members: number;
    open_exceptions: number;
    fields: number;
    fields_needing_review: number;
    unmatched_sublimits: number;
  };
};

export type SourceStatusLabel =
  | "RFQ Data"
  | "Default Data"
  | "AI Derived"
  | "Demography Derived"
  | "Manual"
  | "Fixed"
  | "Not Found"
  | "Ambiguous"
  | "Conflict"
  | "Review Required";

export type QuoteRow = {
  id: string;
  section: string;
  quote_field: string;
  coverage_details: string | null;
  proposed_details: string | null;
  source_status: SourceStatusLabel;
  confidence: "High" | "Medium" | "Low";
  confidence_score: number;
  is_manual_override: boolean;
  evidence: {
    file: string | null;
    /** case_files.id of the cited document (for the inline preview); absent if unknown. */
    file_id?: string | null;
    file_extension?: string | null;
    page: string | null;
    excerpt: string | null;
    verification: string | null;
  };
};

export type QuoteGrid = { columns: string[]; rows: QuoteRow[] };

export type SublimitRow = {
  procedure_name: string;
  options: Record<"Option 1" | "Option 2" | "Option 3" | "Option 4", number>;
  extracted_amount_raw: string | null;
  cleaned_amount: number | null;
  matched_option: string | null;
  match_status: "Matched" | "Unmatched / Review Required" | "Not Found";
  source_status: SourceStatusLabel | null;
  is_underwriter_approved: boolean;
  approval_justification: string | null;
  evidence: { page: string | null; excerpt: string | null };
};

export type ManualInputs = {
  rater_type: string | null;
  brokerage_pct: string | null;
  pincode: string | null;
  state: string | null;
  district: string | null;
};

export type ManualInputsResult = ManualInputs & {
  zone: string;
  zone_matched_by: "pincode" | "district" | "none";
  changed: string[];
};

export type DemographyRow = {
  id: string;
  source_row_number: number;
  age: number;
  date_of_birth: string | null;
  sum_insured: number | null;
  relationship: string;
  name: string;
  emp_code: string;
  gender: string;
  source_age: number | null;
  flags: {
    under18_employee: boolean;
    orphan_dependent: boolean;
    duplicate: boolean;
    has_exception: boolean;
  };
};

export type DemographyPage = {
  columns: string[];
  rows: DemographyRow[];
  total: number;
  page: number;
  page_size: number;
  metrics: {
    group_size: number | null;
    primary_members_count: number | null;
    sme_flag: boolean | null;
    age_basis_mode: AgeBasisMode;
    proposal_start_date: string | null;
  };
};

export type RecalculateResult = {
  basis_mode: AgeBasisMode;
  basis_date: string;
  members: number;
  ages_changed: number;
  under18_employees: number;
  open_exception_counts: Record<string, number>;
};

export type DemographyException = {
  id: string;
  exception_type: string;
  exception_label: string;
  severity: "critical" | "warning";
  error_message: string;
  is_resolved: boolean;
  resolution_action: string | null;
  created_at: string;
  record_id: string | null;
  source_row_number: number | null;
  member_name: string | null;
  employee_code: string | null;
  relationship: string | null;
  resolved_by: string | null;
};

export type ExceptionQueue = {
  rows: DemographyException[];
  total: number;
  page: number;
  page_size: number;
  counts: {
    exception_type: string;
    label: string | null;
    open: number;
    total: number;
  }[];
};

export type AuditEntry = {
  id: string;
  timestamp: string;
  user_email: string;
  action: string;
  target_entity: string;
  old_value: unknown;
  new_value: unknown;
  justification_reason: string | null;
};

export type AuditTrail = {
  rows: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type SublimitOption =
  "option_1" | "option_2" | "option_3" | "option_4" | "unmatched";

export type CaseIntake = {
  company_name: string;
  proposal_start_date?: string | null;
  policy_tenure?: string | null;
  incumbent_insurer?: string | null;
  brokerage_pct?: string | null;
  rater_type?: string | null;
  pincode?: string | null;
};

export type UploadedFile = {
  id: string;
  original_filename: string;
  file_category: CaseFile["file_category"];
  is_encrypted: boolean;
};

export type LockedFile = { file_id: string; filename: string };

export type PipelineStageState =
  "pending" | "running" | "done" | "skipped" | "failed";

export type PipelineStage = {
  key: "intake" | "demography" | "extraction" | "matching";
  label: string;
  state: PipelineStageState;
  detail: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type PipelineStatus = {
  case_id: string;
  status: CaseStatus;
  stages: PipelineStage[];
  terminal: boolean;
  can_start: boolean;
  error: string | null;
  in_memory_run: boolean;
  started_at?: string;
  finished_at?: string | null;
};

export type ZoneLookup = {
  zone: string;
  matched_by: "pincode" | "district" | "none";
};

export type ExportResult = {
  filename: string;
  /** audit_logs.id of the `case_export` row the API wrote for this download. */
  auditLogId: string | null;
};
