"""Source-document preview (GET /cases/{id}/files/{file_id}/view) and export audit headers."""

from pathlib import Path

import pymupdf
import pytest

from app.core.auth import CurrentUser, get_current_user
from app.main import app

from .test_api_cases import ADMIN, case_id, client, locked_census  # noqa: F401

SAMPLES = Path(__file__).parents[3] / "samples"
pytestmark = pytest.mark.skipif(ADMIN is None, reason="local DB or seeded admin unavailable")


def two_page_pdf() -> bytes:
    doc = pymupdf.open()
    for text in ("Page one: Sum Insured 5,00,000", "Page two: Robotic Surgeries: Upto 50% SI"):
        doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def upload(client, case_id, *files):  # noqa: F811
    res = client.post(f"/api/v1/cases/{case_id}/upload", files=[("files", f) for f in files])
    assert res.status_code == 201, res.text
    return {f["original_filename"]: f["id"] for f in res.json()["files"]}


def test_view_pdf_inline_and_text_as_plain(client, case_id):  # noqa: F811
    ids = upload(
        client, case_id,
        ("rfq.pdf", two_page_pdf()),
        ("rfq_apex.md", (SAMPLES / "rfq_apex.md").read_bytes()),
    )  # fmt: skip
    res = client.get(f"/api/v1/cases/{case_id}/files/{ids['rfq.pdf']}/view")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'inline; filename="rfq.pdf"'
    assert res.content.startswith(b"%PDF-")

    res = client.get(f"/api/v1/cases/{case_id}/files/{ids['rfq_apex.md']}/view")
    assert res.headers["content-type"].startswith("text/plain")  # never rendered as HTML
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "Request for Quotation" in res.text


def test_view_refuses_encrypted_and_foreign_files(client, case_id):  # noqa: F811
    ids = upload(client, case_id, ("census.xlsx", locked_census()))
    res = client.get(f"/api/v1/cases/{case_id}/files/{ids['census.xlsx']}/view")
    assert res.status_code == 423
    assert res.json()["detail"]["code"] == "encrypted_at_rest"

    base = f"/api/v1/cases/{case_id}/files"
    assert client.get(f"{base}/00000000-0000-0000-0000-000000000000/view").status_code == 404
    assert client.get(f"{base}/not-a-uuid/view").status_code == 404

    rm = CurrentUser("00000000-0000-0000-0000-0000000000ff", "x", "rm@x", "sales_rm")
    app.dependency_overrides[get_current_user] = lambda: rm  # RLS: not their case
    assert client.get(f"{base}/{ids['census.xlsx']}/view").status_code == 404


def test_extraction_evidence_carries_file_id(client, case_id):  # noqa: F811
    from app.api.v1 import cases as cases_api
    from app.services.mock_llm import MockLLMClient

    ids = upload(client, case_id, ("rfq_apex.md", (SAMPLES / "rfq_apex.md").read_bytes()))
    original = cases_api._llm_client
    cases_api._llm_client = MockLLMClient
    try:
        assert client.post(f"/api/v1/cases/{case_id}/extract/rfq", json={}).status_code == 200
    finally:
        cases_api._llm_client = original
    rows = {r["quote_field"]: r for r in client.get(f"/api/v1/cases/{case_id}/extractions")
            .json()["rows"]}  # fmt: skip
    evidence = rows["Sum Insured (SI)"]["evidence"]
    assert (evidence["file_id"], evidence["file_extension"]) == (ids["rfq_apex.md"], "md")


def test_export_reports_its_audit_row(client, case_id):  # noqa: F811
    upload(client, case_id, ("census.csv", (SAMPLES / "apex_census.csv").read_bytes()))
    client.post(f"/api/v1/cases/{case_id}/demography/process", json={})
    res = client.get(f"/api/v1/cases/{case_id}/export/demography-excel")
    assert res.status_code == 200
    audit = client.get(f"/api/v1/cases/{case_id}/audit").json()["rows"]
    export = next(a for a in audit if a["action"] == "case_export")
    assert res.headers["x-audit-log-id"] == export["id"]
    assert export["new_value"]["download"] in res.headers["content-disposition"]
