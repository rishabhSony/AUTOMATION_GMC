"""
End-to-end API test against the local Postgres in DATABASE_URL (skipped if unreachable).
Clerk is bypassed by overriding `get_current_user` with the seeded admin user; the test
creates its own case and removes it, its rows, and its storage folders afterwards.
"""

import io
import shutil

import openpyxl
import psycopg
import pytest
from fastapi.testclient import TestClient
from msoffcrypto.format.ooxml import OOXMLFile

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.db import SYSTEM_CONTEXT, rls_transaction
from app.main import app


def _seed_admin() -> CurrentUser | None:
    try:
        with rls_transaction(SYSTEM_CONTEXT) as conn:
            row = conn.execute(
                "select id::text, clerk_user_id, email, role::text from users"
                " where clerk_user_id = 'seed_admin'"
            ).fetchone()
    except (psycopg.OperationalError, RuntimeError):
        return None
    return CurrentUser(row["id"], row["clerk_user_id"], row["email"], row["role"]) if row else None


ADMIN = _seed_admin()
pytestmark = pytest.mark.skipif(ADMIN is None, reason="local DB or seeded admin unavailable")

PASSWORD = "Apex@2026"


def locked_census() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Emp ID", "Insured Name", "Relation", "D.O.B.", "Age", "Sex", "SI"])
    ws.append(["E1", "Amit Verma", "Self", "14/06/1992", None, "M", "5,00,000"])
    ws.append(["E1", "Pooja Verma", "Wife", "22/11/1995", None, "F", "5,00,000"])
    ws.append(["E2", "Teen", "Self", "01/01/2012", None, "M", "3,00,000"])
    ws.append(["E9", "Orphan", "Son", "01/01/2015", None, "M", None])
    ws.append(["E3", "No Age", "Self", None, None, "F", None])
    plain, locked = io.BytesIO(), io.BytesIO()
    wb.save(plain)
    OOXMLFile(io.BytesIO(plain.getvalue())).encrypt(PASSWORD, locked)
    return locked.getvalue()


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def case_id(client):
    res = client.post("/api/v1/cases", json={"company_name": "Pytest Logistics"})
    assert res.status_code == 201, res.text
    case_id = res.json()["id"]
    yield case_id
    with rls_transaction(SYSTEM_CONTEXT) as conn:
        conn.execute("delete from cases where id = %s", (case_id,))
    root = get_settings().storage_root
    for sub in ("inputs/raw", "outputs/analysis"):
        shutil.rmtree(root / sub / case_id, ignore_errors=True)


def test_upload_and_process_locked_census(client, case_id):
    res = client.post(
        f"/api/v1/cases/{case_id}/upload",
        files=[("files", ("Apex_Census_Locked.xlsx", locked_census()))],
    )
    assert res.status_code == 201, res.text
    (uploaded,) = res.json()["files"]
    assert uploaded["file_category"] == "demography_census"
    assert uploaded["is_encrypted"] is True

    url = f"/api/v1/cases/{case_id}/demography/process"
    body = {"basis_mode": "policy_proposal_start_date", "proposal_start_date": "2026-10-29"}

    res = client.post(url, json=body)
    assert res.status_code == 423
    assert res.json()["detail"]["code"] == "password_required"

    res = client.post(url, json={**body, "password": "wrong"})
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_password"
    assert "wrong" not in res.text

    res = client.post(url, json={**body, "password": PASSWORD})
    assert res.status_code == 200, res.text
    out = res.json()
    assert PASSWORD not in res.text
    assert (out["group_size"], out["primary_members_count"], out["sme_flag"]) == (4, 2, True)
    assert out["exception_counts"] == {
        "missing_age_and_dob": 1,
        "orphan_dependent": 1,
        "under18_employee": 1,
    }
    assert (get_settings().storage_root / out["export_path"]).is_file()

    with rls_transaction(ADMIN.rls) as conn:
        case = conn.execute(
            "select group_size, primary_members_count, sme_flag from cases where id = %s",
            (case_id,),
        ).fetchone()
        records = conn.execute(
            "select calculated_age, dob, relationship::text, member_name from demography_records"
            " where case_id = %s order by source_row_number",
            (case_id,),
        ).fetchall()
        exceptions = conn.execute(
            "select exception_type, record_id is null as unlinked from demography_exceptions"
            " where case_id = %s order by exception_type",
            (case_id,),
        ).fetchall()
        decrypted = conn.execute(
            "select is_decrypted_successfully from case_files where case_id = %s", (case_id,)
        ).fetchone()

    assert case == {"group_size": 4, "primary_members_count": 2, "sme_flag": True}
    assert records[0] == {
        "calculated_age": 34,
        "dob": "14-06-1992",
        "relationship": "employee",
        "member_name": "Amit Verma",
    }
    assert exceptions == [
        {"exception_type": "missing_age_and_dob", "unlinked": True},
        {"exception_type": "orphan_dependent", "unlinked": False},
        {"exception_type": "under18_employee", "unlinked": False},
    ]
    assert decrypted["is_decrypted_successfully"] is True

    # Reprocessing replaces the previous run instead of duplicating rows.
    res = client.post(url, json={**body, "password": PASSWORD})
    assert res.status_code == 200
    with rls_transaction(ADMIN.rls) as conn:
        count = conn.execute(
            "select count(*) as n from demography_records where case_id = %s", (case_id,)
        ).fetchone()
    assert count["n"] == 4


def test_case_invisible_to_unassigned_sales_rm(client, case_id):
    rm = CurrentUser("00000000-0000-0000-0000-0000000000ff", "x", "rm@x", "sales_rm")
    app.dependency_overrides[get_current_user] = lambda: rm
    res = client.post(
        f"/api/v1/cases/{case_id}/upload", files=[("files", ("c.csv", b"Emp ID\nE1\n"))]
    )
    assert res.status_code == 404


def test_rejects_unsupported_extension(client, case_id):
    res = client.post(f"/api/v1/cases/{case_id}/upload", files=[("files", ("evil.exe", b"MZ"))])
    assert res.status_code == 415
