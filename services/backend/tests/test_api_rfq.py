"""
End-to-end RFQ extraction against the local Postgres, with OpenAI replaced by the fake
instructor client (canned Pass 1 / Pass 2 fixtures). Skipped when the DB is unavailable.
"""

import pytest

from app.api.v1 import cases as cases_api
from app.core.db import SYSTEM_CONTEXT, rls_transaction

from .llm_fakes import FIXTURES, fake_client
from .test_api_cases import ADMIN, case_id, client  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(ADMIN is None, reason="local DB or seeded admin unavailable")


@pytest.fixture
def fake_llm(monkeypatch):
    fake = fake_client()
    monkeypatch.setattr(cases_api, "_llm_client", lambda: fake)
    return fake


@pytest.fixture
def zone_row():
    with rls_transaction(SYSTEM_CONTEXT) as conn:
        conn.execute(
            "insert into zone_master (state, district, pincode, zone)"
            " values ('Maharashtra', 'Mumbai', '400051', 'Zone A')"
        )
    yield
    with rls_transaction(SYSTEM_CONTEXT) as conn:
        conn.execute("delete from zone_master where pincode = '400051'")


def upload_rfq(client, case_id):  # noqa: F811
    res = client.post(
        f"/api/v1/cases/{case_id}/upload",
        files=[("files", ("rfq_apex.md", (FIXTURES / "rfq_apex.md").read_bytes()))],
    )
    assert res.status_code == 201, res.text


def test_extract_rfq_end_to_end(client, case_id, fake_llm, zone_row):  # noqa: F811
    upload_rfq(client, case_id)

    res = client.post(f"/api/v1/cases/{case_id}/extract/rfq", json={})
    assert res.status_code == 200, res.text
    summary = res.json()
    assert summary["proposal_type"] == "Roll Over"
    assert (summary["sublimits_matched"], summary["sublimits_review_required"]) == (1, 2)
    assert summary["model"] == "gpt-5.4-mini"

    # 5-column Quote Review Grid
    grid = client.get(f"/api/v1/cases/{case_id}/extractions").json()
    assert grid["columns"] == [
        "Quote Fields", "Coverage Details", "Proposed Details", "Source Status", "Confidence",
    ]  # fmt: skip
    rows = {r["quote_field"]: r for r in grid["rows"]}
    assert grid["rows"][0]["quote_field"] == "Sum Insured (SI)"  # registry order
    si = rows["Sum Insured (SI)"]
    assert (si["coverage_details"], si["proposed_details"]) == (
        "3,00,000 floater",
        "5,00,000 floater",
    )
    assert (si["source_status"], si["confidence"]) == ("RFQ Data", "High")
    assert si["evidence"]["file"] == "rfq_apex.md" and si["evidence"]["page"] == "1"
    assert rows["Policy Tenure"]["source_status"] == "Default Data"
    assert rows["Post-Hospitalization"]["source_status"] == "Review Required"
    assert rows["Room Rent for ICU & Specialty Rooms"]["proposed_details"] == "2% of SI"
    assert rows["Type of Proposal"]["proposed_details"] == "Roll Over"
    assert rows["Zone"]["source_status"] == "Review Required"  # 400093 not in zone_master

    # Procedure sub-limit grid: all 19 registry procedures
    subs = client.get(f"/api/v1/cases/{case_id}/sublimits").json()["rows"]
    assert len(subs) == 19
    by_proc = {s["procedure_name"]: s for s in subs}
    cabg = by_proc["Coronary Artery Bypass Grafting (CABG)"]
    assert (cabg["matched_option"], cabg["match_status"]) == ("Option 2", "Matched")
    appendix = by_proc["Appendectomy"]
    assert appendix["match_status"] == "Unmatched / Review Required"
    assert (appendix["extracted_amount_raw"], appendix["cleaned_amount"]) == (
        "Rs. 33,000/-",
        33000.0,
    )
    assert by_proc["Cataract (one eye)"]["cleaned_amount"] is None
    assert by_proc["Hernia Repair"]["match_status"] == "Not Found"

    # Location prefilled from the RFQ (only grounded rfq_data values; District was ambiguous)
    with rls_transaction(ADMIN.rls) as conn:
        case = conn.execute(
            "select pincode, state, district, zone, proposal_type, status::text, model_version"
            " from cases where id = %s",
            (case_id,),
        ).fetchone()
    assert case == {
        "pincode": "400093", "state": "Maharashtra", "district": None,
        "zone": "Review Required", "proposal_type": "Roll Over", "status": "review_required",
        "model_version": "gpt-5.4-mini",
    }  # fmt: skip

    # Manual inputs → Zone recalculation and audit trail
    res = client.patch(
        f"/api/v1/cases/{case_id}/manual-inputs",
        json={"pincode": "400051", "brokerage_pct": "7.50", "district": "Mumbai"},
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert (out["zone"], out["zone_matched_by"]) == ("Zone A", "pincode")
    assert out["brokerage_pct"] == "7.50"

    rows = {
        r["quote_field"]: r
        for r in client.get(f"/api/v1/cases/{case_id}/extractions").json()["rows"]
    }
    assert rows["Brokerage %"]["proposed_details"] == "7.50"
    assert rows["Brokerage %"]["source_status"] == "Manual"
    assert (rows["Zone"]["proposed_details"], rows["Zone"]["source_status"]) == (
        "Zone A",
        "AI Derived",
    )

    with rls_transaction(ADMIN.rls) as conn:
        actions = [
            (r["action"], r["target_entity"])
            for r in conn.execute(
                "select action, target_entity from audit_logs where case_id = %s"
                " order by timestamp, id",
                (case_id,),
            ).fetchall()
        ]
    assert ("ai_extraction", "rfq_extractions") in actions
    assert ("manual_input_update", "cases.brokerage_pct") in actions
    assert ("zone_recalc", "cases.zone") in actions

    # Re-extraction keeps manual overrides
    assert client.post(f"/api/v1/cases/{case_id}/extract/rfq", json={}).status_code == 200
    rows = {
        r["quote_field"]: r
        for r in client.get(f"/api/v1/cases/{case_id}/extractions").json()["rows"]
    }
    assert rows["PIN Code"]["proposed_details"] == "400051"
    assert rows["PIN Code"]["is_manual_override"] is True


def test_manual_inputs_validation(client, case_id):  # noqa: F811
    url = f"/api/v1/cases/{case_id}/manual-inputs"
    assert client.patch(url, json={"pincode": "012345"}).status_code == 422
    assert client.patch(url, json={"brokerage_pct": "15.01"}).status_code == 422
    assert client.patch(url, json={}).status_code == 422
    res = client.patch(url, json={"state": "Karnataka", "district": "Bengaluru Urban"})
    assert res.json()["zone"] == "Review Required"  # zone_master has no mapping


def test_extract_without_rfq_file_404(client, case_id, fake_llm):  # noqa: F811
    assert client.post(f"/api/v1/cases/{case_id}/extract/rfq", json={}).status_code == 404
