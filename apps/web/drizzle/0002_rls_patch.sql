-- RLS patch: policies for users, case_files, demography_exceptions (none in Backend Schema v4.0 §3),
-- and FORCE RLS so policies also bind the table owner (the app connects as the owning role).
CREATE OR REPLACE FUNCTION current_app_clerk_user_id() RETURNS text AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_clerk_user_id', true), '');
END;
$$ LANGUAGE plpgsql STABLE;
--> statement-breakpoint
-- users: admins/underwriters see everyone; others see their own row, matched by internal id or by
-- the Clerk id of the verified session (used to resolve the internal user). Only admins write.
CREATE POLICY users_select_policy ON users
  FOR SELECT
  USING (
    current_app_user_role() IN ('admin', 'underwriter') OR
    id = current_app_user_id() OR
    clerk_user_id = current_app_clerk_user_id()
  );
--> statement-breakpoint
CREATE POLICY users_admin_modify_policy ON users
  FOR ALL
  USING (current_app_user_role() = 'admin')
  WITH CHECK (current_app_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY case_files_policy ON case_files
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases
      WHERE cases.id = case_files.case_id
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );
--> statement-breakpoint
CREATE POLICY demography_exceptions_policy ON demography_exceptions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM cases
      WHERE cases.id = demography_exceptions.case_id
        AND (current_app_user_role() IN ('admin', 'underwriter') OR cases.assigned_user_id = current_app_user_id())
    )
  );
--> statement-breakpoint
ALTER TABLE users FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE cases FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE case_files FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE rfq_extractions FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE procedure_sublimits FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE demography_records FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE demography_exceptions FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
