-- Row Level Security from Backend Schema v4.0 §3 (docs/gmc_quote_preparation_backend_schema.md)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE case_files ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE rfq_extractions ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE procedure_sublimits ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE demography_records ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE demography_exceptions ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION current_app_user_id() RETURNS uuid AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_user_id', true), '')::uuid;
END;
$$ LANGUAGE plpgsql STABLE;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION current_app_user_role() RETURNS text AS $$
BEGIN
  RETURN COALESCE(current_setting('app.current_user_role', true), 'sales_rm');
END;
$$ LANGUAGE plpgsql STABLE;
--> statement-breakpoint
CREATE POLICY cases_select_policy ON cases
  FOR SELECT
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    assigned_user_id = current_app_user_id()
  );
--> statement-breakpoint
CREATE POLICY cases_modify_policy ON cases
  FOR ALL
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    assigned_user_id = current_app_user_id()
  );
--> statement-breakpoint
CREATE POLICY rfq_extractions_policy ON rfq_extractions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = rfq_extractions.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );
--> statement-breakpoint
CREATE POLICY procedure_sublimits_policy ON procedure_sublimits
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = procedure_sublimits.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );
--> statement-breakpoint
CREATE POLICY demography_records_policy ON demography_records
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases 
      WHERE cases.id = demography_records.case_id 
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );
--> statement-breakpoint
CREATE POLICY audit_logs_insert_policy ON audit_logs
  FOR INSERT
  WITH CHECK (true);
--> statement-breakpoint
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
--> statement-breakpoint
REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM PUBLIC;
