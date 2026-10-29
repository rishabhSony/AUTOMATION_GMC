# Offline dry-run samples

Synthetic files for exercising `/cases/new` → pipeline → workbench with mock auth and
mock AI (no Clerk or OpenAI keys). Names and numbers are made up.

| File | Use |
| --- | --- |
| `rfq_apex.md` | RFQ that the mock AI recognises: returns the pre-baked Pass 1/Pass 2 answers (same as the test fixtures). |
| `rfq_nimbus.md` | Any other RFQ: the mock AI reads labelled table rows deterministically. |
| `apex_census.csv` | 444-row census with an under-18 employee, an orphan dependant, a duplicate with an age/DOB mismatch, and a row missing both age and DOB. |
| `apex_census_locked.xlsx` | The same census, password-protected. Password: `Apex@2026`. |
