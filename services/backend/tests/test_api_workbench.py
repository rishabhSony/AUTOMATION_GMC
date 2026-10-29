"""
End-to-end workbench API tests against the local Postgres (skipped if unavailable): case
list/detail, the 7-column roster, age recalculation, the exceptions queue, quote-field and
sub-limit overrides, exports and the audit trail. Clerk is bypassed via `get_current_user`.
"""

import io
import re
import shutil
from urllib.parse import quote

import openpyxl
import pytest

from app.api.v1.workbench import _format_inr
from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.db import SYSTEM_CONTEXT, rls_transaction
from app.main import app

from .test_api_cases import ADMIN, case_id, client  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(ADMIN is None, reason="local DB or seeded admin unavailable")


def _seed_user(clerk_user_id: str) -> CurrentUser:
    with rls_transaction(SYSTEM_CONTEXT) as conn:
        row = conn.execute(
            "select id::text, clerk_user_id, email, role::text from users where clerk_user_id = %s",
            (clerk_user_id,),
        ).fetchone()
    return CurrentUser(row["id"], row["clerk_user_id"], row["email"], row["role"])


def act_as(user: CurrentUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


CENSUS = (
    b"Emp ID,Insured Name,Relation,D.O.B.,Age,Sex,SI\n"
    b"E1,Amit Verma,Self,14/06/1992,30,M,500000\n"  # DOB age 34 vs source 30 → mismatch
    b"E1,Pooja Verma,Wife,22/11/1995,,F,500000\n"
    b"E2,Ravi Teen,Self,15/01/2009,,M,300000\n"  # 17 on 29-10-2026, 18 on 01-03-2027
    b"E9,Orphan Kid,Son,01/01/2015,,M,\n"
    b"E3,No Age,Self,,,F,\n"  # CRITICAL_ERROR, not stored as a record
)


@pytest.fixture
def processed_case(client, case_id):  # noqa: F811
    res = client.post(f"/api/v1/cases/{case_id}/upload", files=[("files", ("census.csv", CENSUS))])
    assert res.status_code == 201, res.text
    res = client.post(
        f"/api/v1/cases/{case_id}/demography/process",
        json={"basis_mode": "policy_proposal_start_date", "proposal_start_date": "2026-10-29"},
    )
    assert res.status_code == 200, res.text
    return case_id


def audit_actions(case_id: str) -> list[tuple[str, str, str | None]]:  # noqa: F811
    with rls_transaction(ADMIN.rls) as conn:
        rows = conn.execute(
            "select action, target_entity, justification_reason from audit_logs"
            " where case_id = %s order by timestamp, id",
            (case_id,),
        ).fetchall()
    return [(r["action"], r["target_entity"], r["justification_reason"]) for r in rows]


# ---------------------------------------------------------------------------
# GET /cases, GET /cases/{id}
# ---------------------------------------------------------------------------


def test_list_and_get_case(client, case_id):  # noqa: F811
    res = client.get("/api/v1/cases", params={"status": "draft", "q": "pytest logistics"})
    assert res.status_code == 200, res.text
    body = res.json()
    ids = [c["id"] for c in body["items"]]
    assert case_id in ids
    item = next(c for c in body["items"] if c["id"] == case_id)
    assert (item["status"], item["status_label"], item["open_exceptions"]) == (
        "draft", "Draft", 0,
    )  # fmt: skip
    assert {"total", "needs_review", "prepared", "avg_pipeline_ms"} <= body["summary"].keys()

    assert case_id not in [
        c["id"] for c in client.get("/api/v1/cases", params={"status": "completed"}).json()["items"]
    ]
    assert client.get("/api/v1/cases", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/v1/cases", params={"page_size": 101}).status_code == 422

    detail = client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["company_name"] == "Pytest Logistics"
    assert detail["assignee_email"] == ADMIN.email
    assert detail["brokerage_pct"] == "0.00"
    assert detail["counts"] == {
        "members": 0, "open_exceptions": 0, "fields": 0, "fields_needing_review": 0,
        "unmatched_sublimits": 0,
    }  # fmt: skip


def test_sales_rm_sees_only_assigned_cases(client, case_id):  # noqa: F811
    rm = _seed_user("seed_sales_rm")
    act_as(rm)
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
    assert case_id not in [c["id"] for c in client.get("/api/v1/cases").json()["items"]]

    own = client.post("/api/v1/cases", json={"company_name": "RM Own Case"}).json()["id"]
    try:
        assert own in [c["id"] for c in client.get("/api/v1/cases").json()["items"]]
        assert client.get(f"/api/v1/cases/{own}").json()["assignee_email"] == rm.email
    finally:
        with rls_transaction(SYSTEM_CONTEXT) as conn:
            conn.execute("delete from cases where id = %s", (own,))


# ---------------------------------------------------------------------------
# Demography roster, recalculation and exceptions
# ---------------------------------------------------------------------------


def test_demography_roster_is_seven_columns_and_paginated(client, processed_case):  # noqa: F811
    url = f"/api/v1/cases/{processed_case}/demography"
    body = client.get(url, params={"page_size": 2}).json()
    assert body["columns"] == [
        "Age", "Date of Birth", "Sum Insured", "Relationship", "Name", "EmpCode", "Gender",
    ]  # fmt: skip
    assert (body["total"], len(body["rows"])) == (4, 2)
    first = body["rows"][0]
    assert (first["age"], first["date_of_birth"], first["sum_insured"]) == (34, "14-06-1992", 5e5)
    assert (first["relationship"], first["name"], first["emp_code"], first["gender"]) == (
        "Employee", "Amit Verma", "E1", "Male",
    )  # fmt: skip

    page2 = client.get(url, params={"page_size": 2, "page": 2}).json()["rows"]
    assert [r["name"] for r in page2] == ["Ravi Teen", "Orphan Kid"]
    flagged = client.get(url, params={"flagged_only": True}).json()
    assert [r["name"] for r in flagged["rows"]] == ["Amit Verma", "Ravi Teen", "Orphan Kid"]
    assert flagged["metrics"]["proposal_start_date"] == "2026-10-29"


def test_recalculate_age_updates_ages_and_exceptions(client, processed_case):  # noqa: F811
    base = f"/api/v1/cases/{processed_case}"
    open_types = lambda: {  # noqa: E731
        r["exception_type"]
        for r in client.get(f"{base}/demography/exceptions", params={"resolved": False}).json()[
            "rows"
        ]
    }
    assert open_types() == {
        "age_dob_mismatch", "under18_employee", "orphan_dependent", "missing_age_and_dob",
    }  # fmt: skip

    act_as(_seed_user("seed_sales_rm"))  # sales RMs can't recalculate (Doc 05 §8.3)
    res = client.post(f"{base}/demography/recalculate-age", json={"basis_mode": "current_date"})
    assert res.status_code in (403, 404)
    act_as(ADMIN)

    res = client.post(
        f"{base}/demography/recalculate-age",
        json={"basis_mode": "policy_proposal_start_date", "proposal_start_date": "2027-03-01"},
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert (out["basis_date"], out["members"], out["under18_employees"]) == ("2027-03-01", 4, 0)
    assert out["ages_changed"] >= 1
    assert out["open_exception_counts"] == {
        "age_dob_mismatch": 1, "missing_age_and_dob": 1, "orphan_dependent": 1,
    }  # fmt: skip

    roster = {r["name"]: r for r in client.get(f"{base}/demography").json()["rows"]}
    assert roster["Ravi Teen"]["age"] == 18
    assert roster["Ravi Teen"]["flags"]["under18_employee"] is False
    assert roster["Ravi Teen"]["flags"]["has_exception"] is False
    assert roster["Amit Verma"]["flags"]["has_exception"] is True

    # Missing proposal start date with the proposal basis → 422 (stored date reused otherwise)
    res = client.post(
        f"{base}/demography/recalculate-age", json={"basis_mode": "policy_proposal_start_date"}
    )
    assert res.status_code == 200 and res.json()["basis_date"] == "2027-03-01"
    assert ("age_basis_recalc", "demography_records.calculated_age", None) in audit_actions(
        processed_case
    )


def test_resolve_exception_and_keep_resolution_across_recalc(client, processed_case):  # noqa: F811
    base = f"/api/v1/cases/{processed_case}/demography/exceptions"
    queue = client.get(base).json()
    assert queue["total"] == 4
    assert queue["rows"][0]["severity"] == "critical"  # critical first
    under18 = next(r for r in queue["rows"] if r["exception_type"] == "under18_employee")
    assert (under18["exception_label"], under18["member_name"]) == (
        "Under-18 Employee",
        "Ravi Teen",
    )

    url = f"{base}/{under18['id']}"
    assert client.patch(url, json={"resolution_action": "ok"}).status_code == 422  # too short
    missing = f"{base}/00000000-0000-0000-0000-000000000000"
    assert client.patch(missing, json={"resolution_action": "Verified"}).status_code == 404

    act_as(_seed_user("seed_ops_analyst"))
    # Migration 0004: ops analysts see every case's demography queue (system-wide role).
    assert client.get(base).json()["total"] == 4
    assert client.get(f"/api/v1/cases/{processed_case}/extractions").status_code == 200
    act_as(ADMIN)

    reason = "Apprentice under the 1961 Act; HR confirmed DOB"
    res = client.patch(url, json={"resolution_action": reason})
    assert res.status_code == 200, res.text
    assert (res.json()["is_resolved"], res.json()["resolved_by"]) == (True, ADMIN.email)

    # Same basis date again: the resolved under-18 exception is not recreated as open.
    res = client.post(
        f"/api/v1/cases/{processed_case}/demography/recalculate-age",
        json={"basis_mode": "policy_proposal_start_date", "proposal_start_date": "2026-10-29"},
    )
    assert res.status_code == 200
    assert "under18_employee" not in res.json()["open_exception_counts"]
    resolved = client.get(base, params={"resolved": True}).json()["rows"]
    assert [r["exception_type"] for r in resolved] == ["under18_employee"]
    assert (
        "exception_resolved", f"demography_exceptions.{under18['id']}", reason,
    ) in audit_actions(processed_case)  # fmt: skip


def test_ops_analyst_can_recalculate_assigned_case(client):  # noqa: F811
    ops = _seed_user("seed_ops_analyst")
    case = client.post(
        "/api/v1/cases", json={"company_name": "Ops Case", "assigned_user_id": ops.id}
    ).json()["id"]
    try:
        client.post(f"/api/v1/cases/{case}/upload", files=[("files", ("census.csv", CENSUS))])
        act_as(ops)
        res = client.post(
            f"/api/v1/cases/{case}/demography/recalculate-age",
            json={"basis_mode": "current_date"},
        )
        assert res.status_code == 404  # census uploaded but not processed yet
        assert (
            client.post(
                f"/api/v1/cases/{case}/demography/process", json={"basis_mode": "current_date"}
            ).status_code
            == 200
        )
        res = client.post(
            f"/api/v1/cases/{case}/demography/recalculate-age",
            json={"basis_mode": "current_date"},
        )
        assert res.status_code == 200, res.text
    finally:
        with rls_transaction(SYSTEM_CONTEXT) as conn:
            conn.execute("delete from cases where id = %s", (case,))
        root = get_settings().storage_root
        for sub in ("inputs/raw", "outputs/analysis"):
            shutil.rmtree(root / sub / case, ignore_errors=True)


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def test_extraction_override(client, case_id):  # noqa: F811
    field = "Maternity Expenses / Benefits"  # contains "/" → path parameter
    url = f"/api/v1/cases/{case_id}/extractions/{quote(field, safe='')}"
    reason = "Client email of 12-Oct confirms 50,000 normal / 75,000 C-section"

    assert client.patch(url, json={"proposed_details": "50,000"}).status_code == 422
    assert client.patch(url, json={"justification": reason}).status_code == 422
    res = client.patch(
        f"/api/v1/cases/{case_id}/extractions/Brokerage%20%25",
        json={"proposed_details": "5", "justification": reason},
    )
    assert res.status_code == 422 and "manual-inputs" in res.text
    res = client.patch(
        f"/api/v1/cases/{case_id}/extractions/Not%20A%20Field",
        json={"proposed_details": "x", "justification": reason},
    )
    assert res.status_code == 404

    res = client.patch(url, json={"proposed_details": "50,000 / 75,000", "justification": reason})
    assert res.status_code == 200, res.text
    assert res.json()["source_status"] == "Manual"

    act_as(_seed_user("seed_ops_analyst"))
    assert (
        client.patch(url, json={"proposed_details": "1", "justification": reason}).status_code
        == 403
    )
    act_as(ADMIN)

    rows = {
        r["quote_field"]: r
        for r in client.get(f"/api/v1/cases/{case_id}/extractions").json()["rows"]
    }
    row = rows[field]
    assert (row["proposed_details"], row["source_status"], row["confidence"]) == (
        "50,000 / 75,000", "Manual", "High",
    )  # fmt: skip
    assert row["is_manual_override"] is True
    with rls_transaction(ADMIN.rls) as conn:
        stored = conn.execute(
            "select overridden_by_user_id::text, override_reason from rfq_extractions"
            " where case_id = %s and field_name = %s",
            (case_id, field),
        ).fetchone()
    assert stored == {"overridden_by_user_id": ADMIN.id, "override_reason": reason}
    assert ("field_override", f"rfq_extractions.{field}", reason) in audit_actions(case_id)


def test_sublimit_approval(client, case_id):  # noqa: F811
    proc = "Hernia Repair"  # not in any RFQ → "Not Found"
    url = f"/api/v1/cases/{case_id}/sublimits/{quote(proc, safe='')}"
    reason = "Matches the expiring policy schedule, Option 2 tier"

    act_as(_seed_user("seed_sales_rm"))
    assert (
        client.patch(url, json={"matched_option": "option_2", "justification": reason}).status_code
        == 403
    )
    act_as(ADMIN)

    res = client.patch(url, json={"matched_option": "unmatched", "justification": reason})
    assert res.status_code == 422
    res = client.patch(
        f"/api/v1/cases/{case_id}/sublimits/Unknown%20Procedure",
        json={"matched_option": "option_1", "justification": reason},
    )
    assert res.status_code == 404

    underwriter = _seed_user("seed_underwriter")
    act_as(underwriter)
    res = client.patch(url, json={"matched_option": "option_2", "justification": reason})
    assert res.status_code == 200, res.text
    out = res.json()
    assert (out["matched_option"], out["is_underwriter_approved"]) == ("Option 2", True)
    assert out["extracted_amount_raw"] == _format_inr(out["approved_amount"])  # e.g. "1,25,000"

    subs = {
        s["procedure_name"]: s
        for s in client.get(f"/api/v1/cases/{case_id}/sublimits").json()["rows"]
    }
    hernia = subs[proc]
    assert (hernia["matched_option"], hernia["match_status"]) == ("Option 2", "Matched")
    assert hernia["cleaned_amount"] == hernia["options"]["Option 2"]
    assert (hernia["is_underwriter_approved"], hernia["approval_justification"]) == (True, reason)
    assert ("sublimit_override", f"procedure_sublimits.{proc}", reason) in audit_actions(case_id)


# ---------------------------------------------------------------------------
# Exports and audit trail
# ---------------------------------------------------------------------------


def test_demography_excel_export(client, processed_case):  # noqa: F811
    res = client.get(f"/api/v1/cases/{processed_case}/export/demography-excel")
    assert res.status_code == 200, res.text
    assert re.search(
        r'filename="QuotePulse_CASE-[0-9A-F-]+_Demography_\d{8}\.xlsx"',
        res.headers["content-disposition"],
    )
    assert res.headers["x-archive-path"].endswith("standardized_demography_7col.xlsx")
    ws = openpyxl.load_workbook(io.BytesIO(res.content)).active
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == [
        "Age", "Date of Birth", "Sum Insured", "Relationship", "Name", "EmpCode", "Gender",
    ]  # fmt: skip
    assert rows[1][:2] == (34, "14-06-1992")
    assert len(rows) == 5
    assert (get_settings().storage_root / res.headers["x-archive-path"]).is_file()
    assert any(a[0] == "case_export" for a in audit_actions(processed_case))


def test_quote_excel_export(client, case_id):  # noqa: F811
    url = f"/api/v1/cases/{case_id}/export/quote-excel"
    assert client.get(url).status_code == 404  # nothing extracted yet

    reason = "Confirmed with broker on call"
    client.patch(
        f"/api/v1/cases/{case_id}/extractions/{quote('Policy Tenure', safe='')}",
        json={"proposed_details": "2 Years", "justification": reason},
    )
    res = client.get(url)
    assert res.status_code == 200, res.text
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    assert wb.sheetnames == [
        "Quote Summary", "Hospitalization & Treatments", "Procedure Sub-Limits",
        "Underwriter Notes",
    ]  # fmt: skip
    summary = list(wb["Quote Summary"].iter_rows(values_only=True))
    header = summary.index(
        ("Quote Fields", "Coverage Details", "Proposed Details", "Source Status", "Confidence")
    )
    assert ("Policy Tenure", None, "2 Years", "Manual", "High") in summary[header:]
    assert wb["Procedure Sub-Limits"].max_row == 20  # header + 19 procedures
    notes = list(wb["Underwriter Notes"].iter_rows(values_only=True))
    assert notes[1][2:] == ("field_override", "rfq_extractions.Policy Tenure", reason)
    archive = get_settings().storage_root / res.headers["x-archive-path"]
    assert archive.name == "gmc_quote_summary_sheet.xlsx" and archive.is_file()


def test_audit_trail(client, case_id):  # noqa: F811
    client.patch(f"/api/v1/cases/{case_id}/manual-inputs", json={"brokerage_pct": "7.50"})
    res = client.get(f"/api/v1/cases/{case_id}/audit")
    assert res.status_code == 200
    body = res.json()
    # Brokerage edit + the Zone re-derivation it triggers (empty → "Review Required").
    assert {r["action"] for r in body["rows"]} == {"manual_input_update", "zone_recalc"}
    assert body["total"] == 2
    entry = next(r for r in body["rows"] if r["action"] == "manual_input_update")
    assert (entry["target_entity"], entry["user_email"]) == ("cases.brokerage_pct", ADMIN.email)
    assert (entry["old_value"], entry["new_value"]) == (
        {"brokerage_pct": "0.00"},
        {"brokerage_pct": "7.50"},
    )
