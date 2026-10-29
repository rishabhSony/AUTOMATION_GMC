"""
Export endpoints (Backend Schema v4.0 §8.5): generate the workbook from the reviewed data,
archive it to outputs/analysis/{case_id}/, log a `case_export` audit row, and stream it.
"""

from datetime import datetime

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.v1.cases import (
    ALL_ROLES,
    EXPORT_FILENAME,
    _audit,
    _jsonable,
    get_extractions,
    get_sublimits,
)
from app.core.auth import CurrentUser, require_roles
from app.core.db import rls_transaction
from app.services import demography, exports
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/cases", tags=["exports"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Actions shown as underwriter notes in the quote workbook.
NOTE_ACTIONS = ["field_override", "sublimit_override", "exception_resolved", "exception_reopened"]


def _case(conn, case_id: str) -> dict:
    row = conn.execute(
        "select id::text, case_number, company_name, proposal_type, rater_type, brokerage_pct,"
        " pincode, state, district, zone, group_size, primary_members_count, sme_flag"
        " from cases where id = %s",
        (case_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return row


def download_name(case_number: str, kind: str) -> str:
    """QuotePulse_{Case_Reference}_{Type}_{YYYYMMDD}.xlsx (generation date, server time)."""
    return f"QuotePulse_{case_number}_{kind}_{datetime.now():%Y%m%d}.xlsx"


def _archive_and_stream(
    user: CurrentUser, case: dict, filename: str, kind: str, data: bytes, details: dict
) -> Response:
    key = get_storage_provider().save_analysis_output(case["id"], filename, data, XLSX)
    download = download_name(case["case_number"], kind)
    with rls_transaction(user.rls) as conn:
        details |= {"path": key, "bytes": len(data), "download": download}
        audit_id = _audit(
            conn, user, case["id"], "case_export", f"exports.{filename}", None, details
        )
    return Response(
        data,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{download}"',
            "X-Archive-Path": key,
            "X-Audit-Log-Id": audit_id,  # the immutable audit_logs row for this export
        },
    )


@router.get("/{case_id}/export/demography-excel")
def export_demography_excel(
    case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))
) -> Response:
    with rls_transaction(user.rls) as conn:
        case = _case(conn, case_id)
        rows = conn.execute(
            "select source_row_number, calculated_age, dob, sum_insured, relationship::text,"
            " member_name, employee_code, gender from demography_records where case_id = %s",
            (case_id,),
        ).fetchall()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demography census not processed yet")

    records = pl.DataFrame(
        rows,
        schema={
            "source_row_number": pl.Int32, "calculated_age": pl.Int32, "dob": pl.String,
            "sum_insured": pl.Float64, "relationship": pl.String, "member_name": pl.String,
            "employee_code": pl.String, "gender": pl.String,
        },
        orient="row",
    ).with_columns(pl.col("dob").str.strptime(pl.Date, "%d-%m-%Y", strict=False))  # fmt: skip
    data = demography.seven_column_excel_bytes(records)
    return _archive_and_stream(
        user, case, EXPORT_FILENAME, "Demography", data, {"members": len(rows)}
    )


@router.get("/{case_id}/export/quote-excel")
def export_quote_excel(
    case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))
) -> Response:
    with rls_transaction(user.rls) as conn:
        case = _case(conn, case_id)
        notes = conn.execute(
            "select timestamp, user_email, action, target_entity, justification_reason"
            " from audit_logs where case_id = %s and action = any(%s)"
            " and justification_reason is not null order by timestamp",
            (case_id, NOTE_ACTIONS),
        ).fetchall()
    grid = get_extractions(case_id, user)["rows"]
    if not grid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RFQ extraction has not run yet")
    subs = get_sublimits(case_id, user)["rows"]

    data = exports.build_quote_workbook(
        case | {"brokerage_pct": _jsonable(case["brokerage_pct"])}, grid, subs, notes
    )
    return _archive_and_stream(
        user,
        case,
        exports.QUOTE_FILENAME,
        "Quote",
        data,
        {"fields": len(grid), "notes": len(notes)},
    )
