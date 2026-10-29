CREATE TYPE "public"."age_basis_mode" AS ENUM('current_date', 'policy_proposal_start_date');--> statement-breakpoint
CREATE TYPE "public"."case_status" AS ENUM('draft', 'uploaded', 'processing', 'review_required', 'ready_for_quote', 'completed', 'failed');--> statement-breakpoint
CREATE TYPE "public"."confidence_rating" AS ENUM('high', 'medium', 'low');--> statement-breakpoint
CREATE TYPE "public"."file_category" AS ENUM('rfq_document', 'demography_census', 'supporting_info');--> statement-breakpoint
CREATE TYPE "public"."matched_option" AS ENUM('option_1', 'option_2', 'option_3', 'option_4', 'unmatched');--> statement-breakpoint
CREATE TYPE "public"."relationship_type" AS ENUM('employee', 'spouse', 'child', 'parent', 'parent_in_law');--> statement-breakpoint
CREATE TYPE "public"."source_status" AS ENUM('rfq_data', 'default_data', 'ai_derived', 'demography_derived', 'manual', 'fixed', 'not_found', 'ambiguous', 'conflict', 'review_required');--> statement-breakpoint
CREATE TYPE "public"."user_role" AS ENUM('admin', 'underwriter', 'sales_rm', 'ops_analyst');--> statement-breakpoint
CREATE TYPE "public"."zone_tier" AS ENUM('Zone A', 'Zone B', 'Zone C', 'Zone D', 'Pan India');--> statement-breakpoint
CREATE TABLE "audit_logs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"user_id" uuid,
	"user_email" varchar(255) NOT NULL,
	"action" varchar(100) NOT NULL,
	"target_entity" varchar(100) NOT NULL,
	"old_value" jsonb,
	"new_value" jsonb,
	"justification_reason" text,
	"ip_address" varchar(45),
	"user_agent" text,
	"timestamp" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "case_files" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"original_filename" varchar(255) NOT NULL,
	"file_extension" varchar(20) NOT NULL,
	"file_size" integer NOT NULL,
	"file_category" "file_category" NOT NULL,
	"is_encrypted" boolean DEFAULT false NOT NULL,
	"is_decrypted_successfully" boolean DEFAULT false NOT NULL,
	"storage_path" text NOT NULL,
	"storage_driver" varchar(20) DEFAULT 'local' NOT NULL,
	"uploaded_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "cases" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_number" varchar(64) NOT NULL,
	"assigned_user_id" uuid,
	"status" "case_status" DEFAULT 'draft' NOT NULL,
	"company_name" varchar(255) NOT NULL,
	"proposal_type" varchar(50) DEFAULT 'New Business',
	"rater_type" varchar(100) DEFAULT '-',
	"brokerage_pct" numeric(5, 2) DEFAULT '0.00',
	"pincode" varchar(10),
	"state" varchar(100),
	"district" varchar(100),
	"zone" varchar(50),
	"age_basis_mode" "age_basis_mode" DEFAULT 'current_date' NOT NULL,
	"proposal_start_date" timestamp with time zone,
	"group_size" integer DEFAULT 0,
	"primary_members_count" integer DEFAULT 0,
	"sme_flag" boolean DEFAULT false,
	"pipeline_duration_ms" integer,
	"model_version" varchar(50) DEFAULT 'gpt-5.4-mini',
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "cases_case_number_unique" UNIQUE("case_number")
);
--> statement-breakpoint
CREATE TABLE "demography_exceptions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"record_id" uuid NOT NULL,
	"exception_type" varchar(100) NOT NULL,
	"severity" varchar(20) DEFAULT 'warning' NOT NULL,
	"error_message" text NOT NULL,
	"is_resolved" boolean DEFAULT false NOT NULL,
	"resolved_by_user_id" uuid,
	"resolution_action" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "demography_records" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"calculated_age" integer NOT NULL,
	"dob" varchar(20),
	"sum_insured" numeric(14, 2),
	"relationship" "relationship_type" NOT NULL,
	"member_name" varchar(255) NOT NULL,
	"employee_code" varchar(100) NOT NULL,
	"gender" varchar(20) NOT NULL,
	"source_age_raw" integer,
	"is_under18_employee" boolean DEFAULT false NOT NULL,
	"is_orphan_dependent" boolean DEFAULT false NOT NULL,
	"is_duplicate_record" boolean DEFAULT false NOT NULL,
	"has_validation_exception" boolean DEFAULT false NOT NULL,
	"source_row_number" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE "procedure_sublimits" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"procedure_name" varchar(150) NOT NULL,
	"extracted_amount_raw" varchar(100) NOT NULL,
	"cleaned_amount_numeric" numeric(12, 2),
	"matched_option" "matched_option" DEFAULT 'unmatched' NOT NULL,
	"status" "source_status" DEFAULT 'rfq_data' NOT NULL,
	"is_underwriter_approved" boolean DEFAULT false NOT NULL,
	"approved_by_user_id" uuid,
	"approval_justification" text,
	"source_page" varchar(50),
	"verbatim_snippet" text
);
--> statement-breakpoint
CREATE TABLE "rfq_extractions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"case_id" uuid NOT NULL,
	"section" varchar(100) NOT NULL,
	"field_name" varchar(150) NOT NULL,
	"coverage_details" text,
	"proposed_details" text,
	"source_status" "source_status" DEFAULT 'rfq_data' NOT NULL,
	"confidence_rating" "confidence_rating" DEFAULT 'high' NOT NULL,
	"confidence_score" numeric(4, 3) DEFAULT '0.950',
	"is_manual_override" boolean DEFAULT false NOT NULL,
	"overridden_by_user_id" uuid,
	"override_reason" text,
	"source_file_id" uuid,
	"source_page_or_sheet" varchar(100),
	"verbatim_excerpt" text,
	"reflection_explanation" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sublimit_registry" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"procedure_name" varchar(150) NOT NULL,
	"option_1_amount" numeric(12, 2) NOT NULL,
	"option_2_amount" numeric(12, 2) NOT NULL,
	"option_3_amount" numeric(12, 2) NOT NULL,
	"option_4_amount" numeric(12, 2) NOT NULL,
	"display_order" integer NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "sublimit_registry_procedure_name_unique" UNIQUE("procedure_name")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clerk_user_id" varchar(255) NOT NULL,
	"email" varchar(255) NOT NULL,
	"full_name" varchar(255) NOT NULL,
	"role" "user_role" DEFAULT 'sales_rm' NOT NULL,
	"branch" varchar(100) DEFAULT 'Corporate',
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_clerk_user_id_unique" UNIQUE("clerk_user_id"),
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "zone_master" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"state" varchar(100) NOT NULL,
	"district" varchar(100) NOT NULL,
	"pincode" varchar(10),
	"zone" "zone_tier" NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "case_files" ADD CONSTRAINT "case_files_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "cases" ADD CONSTRAINT "cases_assigned_user_id_users_id_fk" FOREIGN KEY ("assigned_user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "demography_exceptions" ADD CONSTRAINT "demography_exceptions_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "demography_exceptions" ADD CONSTRAINT "demography_exceptions_record_id_demography_records_id_fk" FOREIGN KEY ("record_id") REFERENCES "public"."demography_records"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "demography_exceptions" ADD CONSTRAINT "demography_exceptions_resolved_by_user_id_users_id_fk" FOREIGN KEY ("resolved_by_user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "demography_records" ADD CONSTRAINT "demography_records_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "procedure_sublimits" ADD CONSTRAINT "procedure_sublimits_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "procedure_sublimits" ADD CONSTRAINT "procedure_sublimits_approved_by_user_id_users_id_fk" FOREIGN KEY ("approved_by_user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rfq_extractions" ADD CONSTRAINT "rfq_extractions_case_id_cases_id_fk" FOREIGN KEY ("case_id") REFERENCES "public"."cases"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rfq_extractions" ADD CONSTRAINT "rfq_extractions_overridden_by_user_id_users_id_fk" FOREIGN KEY ("overridden_by_user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rfq_extractions" ADD CONSTRAINT "rfq_extractions_source_file_id_case_files_id_fk" FOREIGN KEY ("source_file_id") REFERENCES "public"."case_files"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "audit_logs_case_id_idx" ON "audit_logs" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "audit_logs_user_id_idx" ON "audit_logs" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "audit_logs_action_idx" ON "audit_logs" USING btree ("action");--> statement-breakpoint
CREATE INDEX "audit_logs_timestamp_desc_idx" ON "audit_logs" USING btree ("timestamp");--> statement-breakpoint
CREATE INDEX "case_files_case_id_idx" ON "case_files" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "case_files_category_idx" ON "case_files" USING btree ("file_category");--> statement-breakpoint
CREATE UNIQUE INDEX "cases_case_number_idx" ON "cases" USING btree ("case_number");--> statement-breakpoint
CREATE INDEX "cases_status_idx" ON "cases" USING btree ("status");--> statement-breakpoint
CREATE INDEX "cases_assigned_user_idx" ON "cases" USING btree ("assigned_user_id");--> statement-breakpoint
CREATE INDEX "cases_pincode_zone_idx" ON "cases" USING btree ("pincode","zone");--> statement-breakpoint
CREATE INDEX "cases_created_at_desc_idx" ON "cases" USING btree ("created_at");--> statement-breakpoint
CREATE INDEX "demography_exceptions_case_id_idx" ON "demography_exceptions" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "demography_exceptions_record_id_idx" ON "demography_exceptions" USING btree ("record_id");--> statement-breakpoint
CREATE INDEX "demography_exceptions_resolved_idx" ON "demography_exceptions" USING btree ("is_resolved");--> statement-breakpoint
CREATE INDEX "demography_records_case_id_idx" ON "demography_records" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "demography_records_emp_code_idx" ON "demography_records" USING btree ("case_id","employee_code");--> statement-breakpoint
CREATE INDEX "demography_records_exceptions_idx" ON "demography_records" USING btree ("case_id","has_validation_exception");--> statement-breakpoint
CREATE INDEX "demography_records_relationship_idx" ON "demography_records" USING btree ("relationship");--> statement-breakpoint
CREATE INDEX "procedure_sublimits_case_id_idx" ON "procedure_sublimits" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "procedure_sublimits_matched_option_idx" ON "procedure_sublimits" USING btree ("matched_option");--> statement-breakpoint
CREATE UNIQUE INDEX "procedure_sublimits_case_proc_uniq_idx" ON "procedure_sublimits" USING btree ("case_id","procedure_name");--> statement-breakpoint
CREATE INDEX "rfq_extractions_case_id_idx" ON "rfq_extractions" USING btree ("case_id");--> statement-breakpoint
CREATE INDEX "rfq_extractions_section_field_idx" ON "rfq_extractions" USING btree ("section","field_name");--> statement-breakpoint
CREATE INDEX "rfq_extractions_status_idx" ON "rfq_extractions" USING btree ("source_status");--> statement-breakpoint
CREATE UNIQUE INDEX "rfq_extractions_case_field_uniq_idx" ON "rfq_extractions" USING btree ("case_id","field_name");--> statement-breakpoint
CREATE UNIQUE INDEX "users_clerk_id_idx" ON "users" USING btree ("clerk_user_id");--> statement-breakpoint
CREATE INDEX "users_email_idx" ON "users" USING btree ("email");--> statement-breakpoint
CREATE INDEX "users_role_idx" ON "users" USING btree ("role");--> statement-breakpoint
CREATE UNIQUE INDEX "zone_master_pincode_idx" ON "zone_master" USING btree ("pincode");--> statement-breakpoint
CREATE INDEX "zone_master_state_district_idx" ON "zone_master" USING btree ("state","district");