"""
Workbench review endpoints (Backend Schema v4.0 §8.2–8.4): the demography roster, age
recalculation, the exceptions queue, quote-field and sub-limit overrides, and the audit
trail. Every user override writes an append-only `audit_logs` row in the same transaction.
"""

from datetime import date
from typing import Annotated, Literal

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.v1.cases import (
    ALL_ROLES,
    CASE_WRITERS,
    _audit,
    _copy_csv,
    _jsonable,
    _lock_case,
)
from app.core.auth import CurrentUser, require_roles
from app.core.db import rls_transaction
from app.services import demography, extractor, field_registry, sublimits

router = APIRouter(prefix="/cases", tags=["workbench"])

# Role sets from Backend Schema v4.0 §8.3–8.4.
DEMOGRAPHY_RECALCULATORS = ("ops_analyst", "underwriter", "admin")
SUBLIMIT_APPROVERS = ("underwriter", "admin")

Justification = Annotated[str, Field(min_length=5, max_length=2000)]


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/demography — paginated 7-column roster
# ---------------------------------------------------------------------------

DEMOGRAPHY_COLUMNS = demography.SEVEN_COLUMN_ORDER


@router.get("/{case_id}/demography")
def get_demography(
    case_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=1000)] = 500,
    flagged_only: bool = False,
    user: CurrentUser = Depends(require_roles(*ALL_ROLES)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id, lock=False)
        rows = conn.execute(
            "select id::text, source_row_number, calculated_age, dob, sum_insured,"
            " relationship::text, member_name, employee_code, gender, source_age_raw,"
            " is_under18_employee, is_orphan_dependent, is_duplicate_record,"
            " has_validation_exception"
            " from demography_records where case_id = %s"
            " and (not %s or has_validation_exception)"
            " order by source_row_number limit %s offset %s",
            (case_id, flagged_only, page_size, (page - 1) * page_size),
        ).fetchall()
        total = conn.execute(
            "select count(*) as n from demography_records where case_id = %s"
            " and (not %s or has_validation_exception)",
            (case_id, flagged_only),
        ).fetchone()["n"]

    start = case["proposal_start_date"]
    return {
        "columns": DEMOGRAPHY_COLUMNS,
        "rows": [
            {
                "id": r["id"],
                "source_row_number": r["source_row_number"],
                # The 7 grid columns, in BRD §9.2 order.
                "age": r["calculated_age"],
                "date_of_birth": r["dob"],
                "sum_insured": float(r["sum_insured"]) if r["sum_insured"] is not None else None,
                "relationship": demography.RELATIONSHIP_LABELS[r["relationship"]],
                "name": r["member_name"],
                "emp_code": r["employee_code"],
                "gender": r["gender"],
                "source_age": r["source_age_raw"],
                "flags": {
                    "under18_employee": r["is_under18_employee"],
                    "orphan_dependent": r["is_orphan_dependent"],
                    "duplicate": r["is_duplicate_record"],
                    "has_exception": r["has_validation_exception"],
                },
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "metrics": {
            "group_size": case["group_size"],
            "primary_members_count": case["primary_members_count"],
            "sme_flag": case["sme_flag"],
            "age_basis_mode": case["age_basis_mode"],
            "proposal_start_date": start.date().isoformat() if start else None,
        },
    }


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/demography/recalculate-age
# ---------------------------------------------------------------------------

# Exceptions whose outcome depends on the basis date. `invalid_dob` only does so when the
# DOB parsed (it was after the basis date); an unparseable DOB stays invalid either way.
AGE_DEPENDENT_EXCEPTIONS = (
    demography.ExceptionType.UNDER18_EMPLOYEE,
    demography.ExceptionType.AGE_DOB_MISMATCH,
    demography.ExceptionType.INVALID_DOB,
)


class RecalculateAgeRequest(BaseModel):
    basis_mode: demography.AgeBasisMode
    proposal_start_date: date | None = Field(
        default=None, description="Required for policy_proposal_start_date unless already set"
    )


def _roster_frame(rows: list[dict]) -> pl.DataFrame:
    """Stored records → the canonical columns `apply_ages` and `_build_exceptions` read."""
    schema = {
        "id": pl.String, "source_row_number": pl.Int32, "calculated_age": pl.Int32,
        "dob_raw": pl.String, "source_age_raw": pl.Int32, "relationship": pl.String,
        "member_name": pl.String, "employee_code": pl.String, "gender": pl.String,
    }  # fmt: skip
    df = pl.DataFrame(rows, schema=schema, orient="row")
    return df.with_columns(
        pl.col("dob_raw").str.strptime(pl.Date, "%d-%m-%Y", strict=False).alias("dob"),
        pl.col("calculated_age").alias("_previous_age"),
    )


@router.post("/{case_id}/demography/recalculate-age")
def recalculate_age(
    case_id: str,
    body: RecalculateAgeRequest,
    user: CurrentUser = Depends(require_roles(*DEMOGRAPHY_RECALCULATORS)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id)
        stored_start = case["proposal_start_date"].date() if case["proposal_start_date"] else None
        start = body.proposal_start_date or stored_start
        try:
            basis_date = demography.resolve_basis_date(body.basis_mode, start)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

        rows = conn.execute(
            "select id::text, source_row_number, calculated_age, dob as dob_raw, source_age_raw,"
            " relationship::text, member_name, employee_code, gender"
            " from demography_records where case_id = %s",
            (case_id,),
        ).fetchall()
        if not rows:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Demography census not processed yet")

        # Vectorized recalculation with the same engine as /demography/process.
        df = demography.apply_ages(_roster_frame(rows), basis_date).with_columns(
            # A DOB now after the basis date with no source age has no computable age;
            # keep the previous one (the row is flagged invalid_dob below).
            pl.col("calculated_age").fill_null(pl.col("_previous_age")),
            pl.lit(True).alias("_storable"),
            pl.lit(False).alias("is_orphan_dependent"),
            pl.lit(False).alias("is_duplicate_record"),
            pl.lit(False).alias("_missing_required"),
            pl.col("relationship").alias("relationship_raw"),
        )
        new_exc = (
            demography._build_exceptions(df)
            .filter(pl.col("exception_type").is_in([str(t) for t in AGE_DEPENDENT_EXCEPTIONS]))
            .join(df.select("source_row_number", "id"), on="source_row_number")
        )
        changed = df.filter(pl.col("calculated_age") != pl.col("_previous_age")).height

        conn.execute(
            "create temp table _ages (id uuid, calculated_age int, is_under18_employee bool)"
            " on commit drop"
        )
        _copy_csv(conn, "_ages", ["id", "calculated_age", "is_under18_employee"], df)
        conn.execute(
            "update demography_records r set calculated_age = a.calculated_age,"
            " is_under18_employee = a.is_under18_employee from _ages a where r.id = a.id"
            " and (r.calculated_age, r.is_under18_employee)"
            "   is distinct from (a.calculated_age, a.is_under18_employee)"
        )

        # Replace open age-dependent exceptions; resolved ones stay as the audit history
        # and suppress an identical new one.
        conn.execute(
            "delete from demography_exceptions e where e.case_id = %s and not e.is_resolved"
            " and (e.exception_type in ('under18_employee', 'age_dob_mismatch')"
            "   or (e.exception_type = 'invalid_dob' and exists (select 1 from"
            "     demography_records r where r.id = e.record_id and r.dob is not null)))",
            (case_id,),
        )
        conn.execute(
            "create temp table _exc (id uuid, exception_type text, severity text,"
            " error_message text) on commit drop"
        )
        _copy_csv(conn, "_exc", ["id", "exception_type", "severity", "error_message"], new_exc)
        conn.execute(
            "insert into demography_exceptions"
            " (case_id, record_id, exception_type, severity, error_message)"
            " select %(case_id)s, x.id, x.exception_type, x.severity, x.error_message from _exc x"
            " where not exists (select 1 from demography_exceptions e where e.case_id ="
            "   %(case_id)s and e.record_id = x.id and e.exception_type = x.exception_type)",
            {"case_id": case_id},
        )
        conn.execute(
            "update demography_records r set has_validation_exception = x.flagged from ("
            "  select r2.id, exists (select 1 from demography_exceptions e"
            "    where e.record_id = r2.id) as flagged"
            "  from demography_records r2 where r2.case_id = %s) x"
            " where r.id = x.id and r.has_validation_exception <> x.flagged",
            (case_id,),
        )

        conn.execute(
            "update cases set age_basis_mode = %s, proposal_start_date = %s, updated_at = now()"
            " where id = %s",
            (body.basis_mode.value, start, case_id),
        )
        _audit(
            conn, user, case_id, "age_basis_recalc", "demography_records.calculated_age",
            {"basis_mode": case["age_basis_mode"], "proposal_start_date": _iso(stored_start)},
            {"basis_mode": body.basis_mode.value, "proposal_start_date": _iso(start),
             "basis_date": basis_date.isoformat(), "ages_changed": changed},
        )  # fmt: skip
        open_counts = conn.execute(
            "select exception_type, count(*) as n from demography_exceptions"
            " where case_id = %s and not is_resolved group by 1 order by 1",
            (case_id,),
        ).fetchall()

    return {
        "basis_mode": body.basis_mode.value,
        "basis_date": basis_date.isoformat(),
        "members": df.height,
        "ages_changed": changed,
        "under18_employees": int(df["is_under18_employee"].sum()),
        "open_exception_counts": {r["exception_type"]: r["n"] for r in open_counts},
    }


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/demography/exceptions — triage queue
# PATCH /cases/{case_id}/demography/exceptions/{exc_id} — resolve with audit action
# ---------------------------------------------------------------------------

EXCEPTION_LABELS = {
    "under18_employee": "Under-18 Employee",
    "orphan_dependent": "Orphan Dependant",
    "duplicate_member": "Duplicate Member",
    "age_dob_mismatch": "Age / DOB Mismatch",
    "missing_required_field": "Missing Required Field",
    "invalid_dob": "Invalid DOB",
    "missing_age_and_dob": "Missing Age and DOB",
    "unmapped_relationship": "Unmapped Relationship",
}

_EXCEPTION_SELECT = (
    "select e.id::text, e.exception_type, e.severity, e.error_message, e.is_resolved,"
    " e.resolution_action, e.created_at, e.record_id::text, r.source_row_number,"
    " r.member_name, r.employee_code, r.relationship::text, u.email as resolved_by"
    " from demography_exceptions e"
    " left join demography_records r on r.id = e.record_id"
    " left join users u on u.id = e.resolved_by_user_id"
)


def _exception_out(r: dict) -> dict:
    return r | {
        "exception_label": EXCEPTION_LABELS.get(r["exception_type"], r["exception_type"]),
        "relationship": demography.RELATIONSHIP_LABELS.get(r["relationship"]),
    }


@router.get("/{case_id}/demography/exceptions")
def get_demography_exceptions(
    case_id: str,
    resolved: bool | None = None,
    exception_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 100,
    user: CurrentUser = Depends(require_roles(*ALL_ROLES)),
) -> dict:
    params = {"case_id": case_id, "resolved": resolved, "type": exception_type,
              "limit": page_size, "offset": (page - 1) * page_size}  # fmt: skip
    where = (
        " where e.case_id = %(case_id)s"
        " and (%(resolved)s::bool is null or e.is_resolved = %(resolved)s::bool)"
        " and (%(type)s::text is null or e.exception_type = %(type)s::text)"
    )
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        rows = conn.execute(
            _EXCEPTION_SELECT + where + " order by e.is_resolved,"
            " case e.severity when 'critical' then 0 else 1 end,"
            " r.source_row_number nulls first, e.exception_type"
            " limit %(limit)s offset %(offset)s",
            params,
        ).fetchall()
        total = conn.execute(
            "select count(*) as n from demography_exceptions e" + where, params
        ).fetchone()["n"]
        counts = conn.execute(
            "select exception_type, count(*) filter (where not is_resolved) as open,"
            " count(*) as total from demography_exceptions where case_id = %s"
            " group by 1 order by 1",
            (case_id,),
        ).fetchall()
    return {
        "rows": [_exception_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": [c | {"label": EXCEPTION_LABELS.get(c["exception_type"])} for c in counts],
    }


class ExceptionResolution(BaseModel):
    resolution_action: Justification
    is_resolved: bool = True


@router.patch("/{case_id}/demography/exceptions/{exc_id}")
def resolve_demography_exception(
    case_id: str,
    exc_id: str,
    body: ExceptionResolution,
    user: CurrentUser = Depends(require_roles(*DEMOGRAPHY_RECALCULATORS)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        before = conn.execute(
            "select is_resolved, resolution_action from demography_exceptions"
            " where id = %s and case_id = %s for update",
            (exc_id, case_id),
        ).fetchone()
        if before is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Exception not found")
        conn.execute(
            "update demography_exceptions set is_resolved = %s, resolution_action = %s,"
            " resolved_by_user_id = %s where id = %s",
            (body.is_resolved, body.resolution_action, user.id, exc_id),
        )
        _audit(
            conn, user, case_id,
            "exception_resolved" if body.is_resolved else "exception_reopened",
            f"demography_exceptions.{exc_id}", before,
            {"is_resolved": body.is_resolved, "resolution_action": body.resolution_action},
            body.resolution_action,
        )  # fmt: skip
        row = conn.execute(_EXCEPTION_SELECT + " where e.id = %s", (exc_id,)).fetchone()
    return _exception_out(row)


# ---------------------------------------------------------------------------
# PATCH /cases/{case_id}/extractions/{field_name} — manual override with justification
# ---------------------------------------------------------------------------

_FIELDS = {f.name: f for f in field_registry.FIELDS}
# These live as columns on `cases`; PATCH /manual-inputs keeps the column, the grid row and
# the derived Zone in sync, so they can't be overridden here.
_MANUAL_INPUT_FIELDS = {"Rater Type", "Brokerage %", "PIN Code", "State", "District", "Zone"}
_UNSET = object()


class ExtractionOverride(BaseModel):
    coverage_details: str | None = Field(default=None, max_length=5000)
    proposed_details: str | None = Field(default=None, max_length=5000)
    justification: Justification


@router.patch("/{case_id}/extractions/{field_name:path}")
def override_extraction(
    case_id: str,
    field_name: str,
    body: ExtractionOverride,
    user: CurrentUser = Depends(require_roles(*CASE_WRITERS)),
) -> dict:
    spec = _FIELDS.get(field_name)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown quote field '{field_name}'")
    if field_name in _MANUAL_INPUT_FIELDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"'{field_name}' is a manual input; use PATCH /cases/{{id}}/manual-inputs",
        )
    values = body.model_dump(
        include={"coverage_details", "proposed_details"} & body.model_fields_set
    )
    if not values:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Send coverage_details and/or proposed_details"
        )

    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id)
        before = conn.execute(
            "select coverage_details, proposed_details, source_status::text,"
            " confidence_rating::text from rfq_extractions"
            " where case_id = %s and field_name = %s for update",
            (case_id, field_name),
        ).fetchone()
        merged = {
            "coverage_details": values.get(
                "coverage_details", before["coverage_details"] if before else None
            ),
            "proposed_details": values.get(
                "proposed_details", before["proposed_details"] if before else None
            ),
        }
        # Upsert: a field the extraction never produced can still be filled in manually.
        conn.execute(
            "insert into rfq_extractions (case_id, section, field_name, coverage_details,"
            " proposed_details, source_status, confidence_rating, confidence_score,"
            " is_manual_override, overridden_by_user_id, override_reason, updated_at)"
            " values (%(case_id)s, %(section)s, %(field)s, %(coverage)s, %(proposed)s, 'manual',"
            " 'high', 1, true, %(user)s, %(reason)s, now())"
            " on conflict (case_id, field_name) do update set"
            " coverage_details = excluded.coverage_details,"
            " proposed_details = excluded.proposed_details, source_status = 'manual',"
            " confidence_rating = 'high', confidence_score = 1, is_manual_override = true,"
            " overridden_by_user_id = excluded.overridden_by_user_id,"
            " override_reason = excluded.override_reason, updated_at = now()",
            {"case_id": case_id, "section": spec.section, "field": field_name,
             "coverage": merged["coverage_details"], "proposed": merged["proposed_details"],
             "user": user.id, "reason": body.justification},
        )  # fmt: skip
        _audit(
            conn, user, case_id, "field_override", f"rfq_extractions.{field_name}", before,
            merged | {"source_status": "manual"}, body.justification,
        )  # fmt: skip
    return {
        "quote_field": field_name,
        "coverage_details": merged["coverage_details"],
        "proposed_details": merged["proposed_details"],
        "source_status": extractor.SOURCE_STATUS_LABELS["manual"],
        "confidence": extractor.CONFIDENCE_LABELS["high"],
        "is_manual_override": True,
        "override_reason": body.justification,
    }


# ---------------------------------------------------------------------------
# PATCH /cases/{case_id}/sublimits/{proc_name} — underwriter approval with justification
# ---------------------------------------------------------------------------


class SublimitApproval(BaseModel):
    matched_option: Literal["option_1", "option_2", "option_3", "option_4", "unmatched"] = Field(
        description="Approved Option tier, or `unmatched` to approve the exact RFQ amount as-is"
    )
    justification: Justification


@router.patch("/{case_id}/sublimits/{proc_name:path}")
def approve_sublimit(
    case_id: str,
    proc_name: str,
    body: SublimitApproval,
    user: CurrentUser = Depends(require_roles(*SUBLIMIT_APPROVERS)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id)
        registry = conn.execute(
            "select option_1_amount, option_2_amount, option_3_amount, option_4_amount"
            " from sublimit_registry where procedure_name = %s",
            (proc_name,),
        ).fetchone()
        if registry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown procedure '{proc_name}'")
        before = conn.execute(
            "select extracted_amount_raw, cleaned_amount_numeric, matched_option::text,"
            " status::text, is_underwriter_approved, approval_justification"
            " from procedure_sublimits where case_id = %s and procedure_name = %s for update",
            (case_id, proc_name),
        ).fetchone()
        if before is None and body.matched_option == "unmatched":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "The RFQ states no amount for this procedure; approve an Option tier instead",
            )

        tier_amount = (
            registry[f"{body.matched_option}_amount"]
            if body.matched_option != "unmatched"
            else None
        )
        # A procedure missing from the RFQ gets the approved tier's amount as its value.
        raw = before["extracted_amount_raw"] if before else _format_inr(tier_amount)
        cleaned = before["cleaned_amount_numeric"] if before else tier_amount
        conn.execute(
            "insert into procedure_sublimits (case_id, procedure_name, extracted_amount_raw,"
            " cleaned_amount_numeric, matched_option, status, is_underwriter_approved,"
            " approved_by_user_id, approval_justification)"
            " values (%(case_id)s, %(proc)s, %(raw)s, %(cleaned)s, %(option)s, 'manual', true,"
            " %(user)s, %(reason)s)"
            " on conflict (case_id, procedure_name) do update set"
            " matched_option = excluded.matched_option, status = 'manual',"
            " is_underwriter_approved = true, approved_by_user_id = excluded.approved_by_user_id,"
            " approval_justification = excluded.approval_justification",
            {"case_id": case_id, "proc": proc_name, "raw": raw, "cleaned": cleaned,
             "option": body.matched_option, "user": user.id, "reason": body.justification},
        )  # fmt: skip
        _audit(
            conn, user, case_id, "sublimit_override", f"procedure_sublimits.{proc_name}",
            before and {k: _jsonable(v) for k, v in before.items()},
            {"matched_option": body.matched_option, "approved_amount": _jsonable(tier_amount),
             "is_underwriter_approved": True},
            body.justification,
        )  # fmt: skip
    return {
        "procedure_name": proc_name,
        "extracted_amount_raw": raw,
        "cleaned_amount": float(cleaned) if cleaned is not None else None,
        "matched_option": sublimits.OPTION_LABELS[body.matched_option],
        "approved_amount": float(tier_amount) if tier_amount is not None else None,
        "is_underwriter_approved": True,
        "approval_justification": body.justification,
        "source_status": extractor.SOURCE_STATUS_LABELS["manual"],
    }


def _format_inr(amount) -> str:
    """Indian digit grouping, e.g. 125000 → '1,25,000'."""
    digits = str(int(amount))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        head, groups = head[:-2], [head[-2:], *groups]
    return ",".join([g for g in [head, *groups] if g] + [tail])


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/audit — chronological audit trail (TRD §11; read-only)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/audit")
def get_audit_trail(
    case_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 100,
    user: CurrentUser = Depends(require_roles(*ALL_ROLES)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        rows = conn.execute(
            "select id::text, timestamp, user_email, action, target_entity, old_value,"
            " new_value, justification_reason, count(*) over () as total"
            " from audit_logs where case_id = %s order by timestamp desc, id"
            " limit %s offset %s",
            (case_id, page_size, (page - 1) * page_size),
        ).fetchall()
    return {
        "rows": [{k: v for k, v in r.items() if k != "total"} for r in rows],
        "total": rows[0]["total"] if rows else 0,
        "page": page,
        "page_size": page_size,
    }
