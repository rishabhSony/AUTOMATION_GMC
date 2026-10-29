"""
Offline-mode features: the deterministic mock AI, dev mock auth headers, case intake,
the zone lookup, and the /process → /pipeline-status flow with an encrypted census.
API tests run against the local Postgres (skipped if unavailable).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import cases as cases_api
from app.core import config
from app.core.db import SYSTEM_CONTEXT, rls_transaction
from app.main import app
from app.services import extractor, parser
from app.services.mock_llm import MODEL_NAME, MockLLMClient

from .test_api_cases import ADMIN, PASSWORD, case_id, client, locked_census  # noqa: F401

SAMPLES = Path(__file__).parents[3] / "samples"
needs_db = pytest.mark.skipif(ADMIN is None, reason="local DB or seeded admin unavailable")


def _md(name: str) -> str:
    return parser.parse_document((SAMPLES / name).read_bytes(), name).markdown


# ---------------------------------------------------------------------------
# Mock AI
# ---------------------------------------------------------------------------


def test_mock_ai_returns_baked_answers_for_the_sample_rfq():
    outcome = extractor.extract_rfq(_md("rfq_apex.md"), [], client=MockLLMClient())
    rows = {r.field_name: r for r in outcome.rows}
    assert outcome.model == MODEL_NAME
    si = rows["Sum Insured (SI)"]
    assert (si.coverage_details, si.proposed_details, si.source_status) == (
        "3,00,000 floater",
        "5,00,000 floater",
        "rfq_data",
    )
    # Baked answers, not the row scanner: the fixture's ungrounded citation is demoted.
    assert rows["Post-Hospitalization"].source_status == "review_required"
    assert rows["Incumbent Insurer"].coverage_details == "ICICI Lombard General Insurance"


def test_mock_ai_reads_labelled_rows_of_any_rfq():
    outcome = extractor.extract_rfq(_md("rfq_nimbus.md"), [], client=MockLLMClient())
    rows = {r.field_name: r for r in outcome.rows}
    robotic = rows["Robotic Surgeries"]
    assert (robotic.coverage_details, robotic.proposed_details) == ("Not Covered", "Upto 50% SI")
    assert robotic.source_status == "rfq_data"  # evidence is the verbatim table row
    assert rows["Stem Cell Therapy / Treatment"].coverage_details is None  # "–" is empty
    subs = {s.procedure_name: s.raw_amount_text for s in outcome.pass1.sublimits}
    assert subs == {
        "Cataract (one eye)": "Rs. 25,000",
        "Hernia Repair": "Rs. 27,500",
        "Appendectomy": "Rs. 25,000",
    }


def test_mock_ai_toggle(monkeypatch):
    settings = config.get_settings()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "USE_MOCK_AI", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert isinstance(extractor.get_llm_client(), MockLLMClient)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")  # no silent mock in prod
    with pytest.raises(extractor.LLMNotConfiguredError):
        extractor.get_llm_client()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "USE_MOCK_AI", True)
    assert isinstance(extractor.get_llm_client(), MockLLMClient)


# ---------------------------------------------------------------------------
# Dev mock auth
# ---------------------------------------------------------------------------


@needs_db
def test_dev_mock_auth_headers(monkeypatch):
    settings = config.get_settings()
    app.dependency_overrides.clear()
    raw = TestClient(app)
    headers = {"X-Dev-User-Id": ADMIN.id, "X-Dev-User-Role": "admin"}

    monkeypatch.setattr(settings, "ENABLE_DEV_MOCK_AUTH", False)
    assert raw.get("/api/v1/cases", headers=headers).status_code == 401

    monkeypatch.setattr(settings, "ENABLE_DEV_MOCK_AUTH", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert raw.get("/api/v1/cases", headers=headers).status_code == 200
    # The DB role wins: claiming another role is rejected, not escalated.
    res = raw.get("/api/v1/cases", headers={**headers, "X-Dev-User-Role": "underwriter"})
    assert res.status_code == 403
    bogus = {"X-Dev-User-Id": "not-a-uuid"}
    assert raw.get("/api/v1/cases", headers=bogus).status_code == 403

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert raw.get("/api/v1/cases", headers=headers).status_code == 401


# ---------------------------------------------------------------------------
# Intake, zone lookup
# ---------------------------------------------------------------------------


@needs_db
def test_create_case_with_intake_fields(client):  # noqa: F811
    res = client.post(
        "/api/v1/cases",
        json={
            "company_name": "Intake Pytest Ltd",
            "proposal_start_date": "2026-12-01",
            "policy_tenure": "1 Year",
            "incumbent_insurer": "ICICI Lombard General Insurance",
            "brokerage_pct": "7.5",
            "rater_type": "Floater Rater v2",
            "pincode": "400051",
        },
    )
    assert res.status_code == 201, res.text
    new_id = res.json()["id"]
    try:
        c = client.get(f"/api/v1/cases/{new_id}").json()
        assert (c["proposal_type"], c["brokerage_pct"], c["pincode"], c["zone"]) == (
            "Roll Over",
            "7.50",
            "400051",
            "Review Required",  # zone_master is empty until Underwriting Ops sign-off
        )
        assert (c["proposal_start_date"], c["age_basis_mode"]) == (
            "2026-12-01",
            "policy_proposal_start_date",
        )
        rows = {
            r["quote_field"]: r
            for r in client.get(f"/api/v1/cases/{new_id}/extractions").json()["rows"]
        }
        insurer = rows["Incumbent Insurer"]
        assert (insurer["coverage_details"], insurer["source_status"]) == (
            "ICICI Lombard General Insurance",
            "Manual",
        )
        assert rows["Policy Tenure"]["proposed_details"] == "1 Year"
        audit = client.get(f"/api/v1/cases/{new_id}/audit").json()["rows"]
        assert [a["action"] for a in audit] == ["case_intake"]
    finally:
        with rls_transaction(SYSTEM_CONTEXT) as conn:
            conn.execute("delete from cases where id = %s", (new_id,))

    bad = client.post("/api/v1/cases", json={"company_name": "X", "pincode": "012345"})
    assert bad.status_code == 422


@needs_db
def test_zone_reference(client):  # noqa: F811
    res = client.get("/api/v1/reference/zone", params={"pincode": "560001"})
    assert res.json() == {"zone": "Review Required", "matched_by": "none"}
    assert client.get("/api/v1/reference/zone", params={"pincode": "12"}).status_code == 422


# ---------------------------------------------------------------------------
# /process → /pipeline-status
# ---------------------------------------------------------------------------


@needs_db
def test_process_pipeline_with_locked_census(client, case_id, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cases_api, "_llm_client", MockLLMClient)  # never call OpenAI here
    base = f"/api/v1/cases/{case_id}"
    assert client.post(f"{base}/process", json={}).status_code == 404  # nothing uploaded

    res = client.post(
        f"{base}/upload",
        files=[
            ("files", ("Apex_Census_Locked.xlsx", locked_census())),
            ("files", ("rfq_apex.md", (SAMPLES / "rfq_apex.md").read_bytes())),
        ],
    )
    census_id = next(f["id"] for f in res.json()["files"] if f["is_encrypted"])

    status = client.get(f"{base}/pipeline-status").json()
    assert (status["status"], status["can_start"], status["terminal"]) == (
        "uploaded",
        True,
        False,
    )

    res = client.post(f"{base}/process", json={})
    assert res.status_code == 423
    assert res.json()["detail"]["files"] == [
        {"file_id": census_id, "filename": "Apex_Census_Locked.xlsx"}
    ]
    res = client.post(f"{base}/process", json={"passwords": {census_id: "wrong"}})
    assert res.status_code == 422 and res.json()["detail"]["code"] == "invalid_password"

    # TestClient runs the background pipeline before returning.
    res = client.post(f"{base}/process", json={"passwords": {census_id: PASSWORD}})
    assert res.status_code == 202, res.text
    assert PASSWORD not in res.text

    status = client.get(f"{base}/pipeline-status").json()
    assert status["error"] is None
    assert [(s["key"], s["state"]) for s in status["stages"]] == [
        ("intake", "done"),
        ("demography", "done"),
        ("extraction", "done"),
        ("matching", "done"),
    ]
    assert (status["status"], status["terminal"]) == ("review_required", True)
    assert "1 decrypted in memory" in status["stages"][0]["detail"]

    case = client.get(base).json()
    assert (case["group_size"], case["model_version"], case["proposal_type"]) == (
        4,
        MODEL_NAME,
        "Roll Over",
    )
    actions = {a["action"] for a in client.get(f"{base}/audit").json()["rows"]}
    assert {"pipeline_started", "ai_extraction"} <= actions


@needs_db
def test_process_failure_marks_case_failed(client, case_id, monkeypatch):  # noqa: F811
    def boom(*args, **kwargs):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(parser, "parse_document", boom)
    client.post(
        f"/api/v1/cases/{case_id}/upload",
        files=[("files", ("rfq_apex.md", (SAMPLES / "rfq_apex.md").read_bytes()))],
    )
    assert client.post(f"/api/v1/cases/{case_id}/process", json={}).status_code == 202
    status = client.get(f"/api/v1/cases/{case_id}/pipeline-status").json()
    assert (status["status"], status["terminal"], status["can_start"]) == ("failed", True, True)
    states = {s["key"]: s["state"] for s in status["stages"]}
    assert states["extraction"] == "failed" and "parser exploded" in status["error"]
