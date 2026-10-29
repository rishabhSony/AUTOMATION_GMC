-- ops_analyst is "system-wide (demography focused)" in the Backend Schema v4.0 §4 role matrix,
-- but Doc 05 §3's policies only let it see cases assigned to it. Policies are permissive
-- (OR-ed), so these add access on top of 0001/0002 without loosening other roles:
--   * read every case and its review data (files, quote fields, sub-limits, audit trail)
--   * update cases and case_files (age basis, group metrics, decryption flag set by the
--     demography endpoints) and fully manage demography records and exceptions.
-- Which endpoints ops may call is still enforced by the API's role sets (Doc 05 §8).
DROP POLICY IF EXISTS cases_select_policy ON cases;
--> statement-breakpoint
CREATE POLICY cases_select_policy ON cases
  FOR SELECT
  USING (
    current_app_user_role() IN ('admin', 'underwriter', 'ops_analyst') OR
    assigned_user_id = current_app_user_id()
  );
--> statement-breakpoint
CREATE POLICY cases_ops_analyst_update_policy ON cases
  FOR UPDATE
  USING (current_app_user_role() = 'ops_analyst')
  WITH CHECK (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY case_files_ops_analyst_select_policy ON case_files
  FOR SELECT
  USING (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY case_files_ops_analyst_update_policy ON case_files
  FOR UPDATE
  USING (current_app_user_role() = 'ops_analyst')
  WITH CHECK (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY rfq_extractions_ops_analyst_select_policy ON rfq_extractions
  FOR SELECT
  USING (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY procedure_sublimits_ops_analyst_select_policy ON procedure_sublimits
  FOR SELECT
  USING (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY demography_records_ops_analyst_policy ON demography_records
  FOR ALL
  USING (current_app_user_role() = 'ops_analyst')
  WITH CHECK (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY demography_exceptions_ops_analyst_policy ON demography_exceptions
  FOR ALL
  USING (current_app_user_role() = 'ops_analyst')
  WITH CHECK (current_app_user_role() = 'ops_analyst');
--> statement-breakpoint
CREATE POLICY audit_logs_ops_analyst_select_policy ON audit_logs
  FOR SELECT
  USING (current_app_user_role() = 'ops_analyst');
