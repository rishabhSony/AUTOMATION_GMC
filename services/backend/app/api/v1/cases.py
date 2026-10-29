import io
import json
import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

import polars as pl
import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, SecretStr

from app.core.auth import CurrentUser, require_roles
from app.core.config import get_settings
from app.core.db import rls_transaction
from app.services import (
    demography,
    derivations,
    extractor,
    field_registry,
    parser,
    sublimits,
)
from app.services.storage import (
    InvalidPasswordException,
    PasswordRequiredException,
    get_storage_provider,
    is_password_protected,
    open_decrypted,
    safe_filename,
)

router = APIRouter(prefix="/cases", tags=["cases"])

# Role sets from Backend Schema v4.0 §8 (API catalog).
CASE_WRITERS = ("sales_rm", "underwriter", "admin")
DEMOGRAPHY_PROCESSORS = ("sales_rm", "underwriter", "admin", "ops_analyst")
ALL_ROLES = DEMOGRAPHY_PROCESSORS

FileCategory = Literal["rfq_document", "demography_census", "supporting_info"]

ALLOWED_EXTENSIONS = {
    "pdf", "docx", "msg", "txt", "md", "xlsx", "xls", "csv", "png", "jpg", "jpeg",
}  # fmt: skip
CENSUS_EXTENSIONS = {"xlsx", "xls", "csv"}
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
}
EXPORT_FILENAME = "standardized_demography_7col.xlsx"


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


_CASE_COLUMNS = (
    "id::text, company_name, proposal_type, age_basis_mode::text, proposal_start_date,"
    " group_size, primary_members_count, sme_flag, rater_type, brokerage_pct, pincode, state,"
    " district, zone"
)


def _lock_case(conn: psycopg.Connection, case_id: str, *, lock: bool = True) -> dict:
    """Reads (and by default locks) the case; RLS hides inaccessible cases, so those 404."""
    row = conn.execute(
        f"select {_CASE_COLUMNS} from cases where id = %s" + (" for update" if lock else ""),
        (case_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return row


# ---------------------------------------------------------------------------
# POST /cases
# ---------------------------------------------------------------------------


class CaseCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    proposal_type: str = Field(default="New Business", max_length=50)
    assigned_user_id: str | None = None
    # Optional intake metadata (/cases/new step 1). Location and commercial inputs are the
    # same columns PATCH /manual-inputs edits; the policy period sets the age basis.
    proposal_start_date: date | None = None
    policy_tenure: str | None = Field(default=None, max_length=50)
    incumbent_insurer: str | None = Field(default=None, max_length=255)
    rater_type: str | None = Field(default=None, max_length=100)
    brokerage_pct: Decimal | None = Field(default=None, ge=0, le=15, decimal_places=2)
    pincode: str | None = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)


INTAKE_REASON = "Entered at case intake"
# Intake values kept as manual Quote Review Grid rows (never overwritten by extraction).
_INTAKE_GRID_FIELDS = {
    "incumbent_insurer": ("quotation", field_registry.INCUMBENT_INSURER, "coverage_details"),
    "policy_tenure": ("quotation", "Policy Tenure", "proposed_details"),
}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreate, user: CurrentUser = Depends(require_roles(*CASE_WRITERS))
) -> dict:
    # Sales RMs only see cases assigned to them (RLS), so they always own what they create.
    assignee = user.id if user.role == "sales_rm" else (body.assigned_user_id or user.id)
    case_number = f"CASE-{datetime.now():%y%m%d}-{secrets.token_hex(3).upper()}"
    insurer = (body.incumbent_insurer or "").strip() or None
    proposal_type = (
        derivations.derive_proposal_type(insurer)
        if "incumbent_insurer" in body.model_fields_set
        else body.proposal_type
    )
    with rls_transaction(user.rls) as conn:
        zone, matched_by = derivations.resolve_zone(conn, body.pincode, body.state, body.district)
        row = conn.execute(
            "insert into cases (case_number, company_name, proposal_type, assigned_user_id,"
            " proposal_start_date, age_basis_mode, rater_type, brokerage_pct, pincode, state,"
            " district, zone)"
            " values (%s, %s, %s, %s, %s, %s, coalesce(%s, '-'), coalesce(%s, 0), %s, %s, %s, %s)"
            " returning id::text, case_number",
            (case_number, body.company_name, proposal_type, assignee, body.proposal_start_date,
             "policy_proposal_start_date" if body.proposal_start_date else "current_date",
             body.rater_type, body.brokerage_pct, body.pincode, body.state, body.district,
             zone if (body.pincode or body.district) else None),
        ).fetchone()  # fmt: skip
        values = {"policy_tenure": body.policy_tenure, "incumbent_insurer": insurer}
        for key, (section, name, column) in _INTAKE_GRID_FIELDS.items():
            if values[key]:
                conn.execute(
                    f"insert into rfq_extractions (case_id, section, field_name, {column},"
                    " source_status, confidence_rating, confidence_score, is_manual_override,"
                    " overridden_by_user_id, override_reason)"
                    " values (%s, %s, %s, %s, 'manual', 'high', 1, true, %s, %s)",
                    (row["id"], section, name, values[key], user.id, INTAKE_REASON),
                )
        intake = body.model_dump(
            exclude={"company_name", "proposal_type", "assigned_user_id"}, exclude_none=True
        )
        if intake:
            _audit(conn, user, row["id"], "case_intake", "cases",
                   None, {k: _jsonable(v) for k, v in intake.items()}
                   | {"zone": zone, "zone_matched_by": matched_by, "proposal_type": proposal_type},
                   INTAKE_REASON)  # fmt: skip
    return row


# ---------------------------------------------------------------------------
# GET /cases — paginated case list with status filter (Doc 05 §8.1)
# ---------------------------------------------------------------------------

CaseStatus = Literal[
    "draft", "uploaded", "processing", "review_required", "ready_for_quote", "completed", "failed",
]  # fmt: skip
CASE_STATUS_LABELS = {
    "draft": "Draft",
    "uploaded": "Uploaded",
    "processing": "Processing",
    "review_required": "Needs Review",
    "ready_for_quote": "Ready for Quote",
    "completed": "Completed",
    "failed": "Failed",
}


@router.get("")
def list_cases(
    status_filter: Annotated[list[CaseStatus] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    user: CurrentUser = Depends(require_roles(*ALL_ROLES)),
) -> dict:
    # RLS limits sales RMs to their assigned cases; filters narrow further.
    where = ["(%(statuses)s::case_status[] is null or c.status = any(%(statuses)s::case_status[]))"]
    params: dict = {"statuses": status_filter or None, "limit": page_size,
                    "offset": (page - 1) * page_size}  # fmt: skip
    if q and q.strip():
        where.append("(c.company_name ilike %(q)s or c.case_number ilike %(q)s)")
        params["q"] = f"%{q.strip()}%"
    clause = " and ".join(where)

    with rls_transaction(user.rls) as conn:
        rows = conn.execute(
            "select c.id::text, c.case_number, c.company_name, c.status::text,"
            " c.proposal_type, c.group_size, c.primary_members_count, c.sme_flag, c.zone,"
            " c.created_at, c.updated_at, u.full_name as assignee_name,"
            " (select count(*) from demography_exceptions e"
            "   where e.case_id = c.id and not e.is_resolved) as open_exceptions,"
            " count(*) over () as total"
            f" from cases c left join users u on u.id = c.assigned_user_id where {clause}"
            " order by c.created_at desc limit %(limit)s offset %(offset)s",
            params,
        ).fetchall()
        summary = conn.execute(
            "select count(*) as total,"
            " count(*) filter (where status = 'review_required') as needs_review,"
            " count(*) filter (where status in ('ready_for_quote', 'completed')) as prepared,"
            " avg(pipeline_duration_ms)::int as avg_pipeline_ms from cases"
        ).fetchone()

    total = rows[0]["total"] if rows else 0
    if not rows and page > 1:  # past the last page: report the real total
        with rls_transaction(user.rls) as conn:
            total = conn.execute(
                f"select count(*) as n from cases c where {clause}", params
            ).fetchone()["n"]
    return {
        "items": [
            {k: v for k, v in r.items() if k != "total"}
            | {"status_label": CASE_STATUS_LABELS[r["status"]]}
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# GET /cases/{case_id} — case header, manual inputs, derived metrics
# ---------------------------------------------------------------------------


@router.get("/{case_id}")
def get_case(case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))) -> dict:
    with rls_transaction(user.rls) as conn:
        case = conn.execute(
            "select c.id::text, c.case_number, c.company_name, c.status::text, c.proposal_type,"
            " c.rater_type, c.brokerage_pct, c.pincode, c.state, c.district, c.zone,"
            " c.age_basis_mode::text, c.proposal_start_date, c.group_size,"
            " c.primary_members_count, c.sme_flag, c.pipeline_duration_ms, c.model_version,"
            " c.created_at, c.updated_at, c.assigned_user_id::text, u.full_name as assignee_name,"
            " u.email as assignee_email"
            " from cases c left join users u on u.id = c.assigned_user_id where c.id = %s",
            (case_id,),
        ).fetchone()
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
        files = conn.execute(
            "select id::text, original_filename, file_extension, file_size,"
            " file_category::text, is_encrypted, is_decrypted_successfully, uploaded_at"
            " from case_files where case_id = %s order by uploaded_at",
            (case_id,),
        ).fetchall()
        counts = conn.execute(
            "select"
            " (select count(*) from demography_records where case_id = %(id)s) as members,"
            " (select count(*) from demography_exceptions"
            "   where case_id = %(id)s and not is_resolved) as open_exceptions,"
            " (select count(*) from rfq_extractions where case_id = %(id)s) as fields,"
            " (select count(*) from rfq_extractions where case_id = %(id)s"
            "   and source_status in ('review_required', 'conflict', 'ambiguous'))"
            "   as fields_needing_review,"
            " (select count(*) from procedure_sublimits where case_id = %(id)s"
            "   and matched_option = 'unmatched' and not is_underwriter_approved)"
            "   as unmatched_sublimits",
            {"id": case_id},
        ).fetchone()

    start = case["proposal_start_date"]
    return case | {
        "status_label": CASE_STATUS_LABELS[case["status"]],
        "brokerage_pct": _jsonable(case["brokerage_pct"]),
        "proposal_start_date": start.date().isoformat() if start else None,
        "files": files,
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/upload
# ---------------------------------------------------------------------------


@router.post("/{case_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_files(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="RFQ documents and census sheets")],
    file_category: Annotated[FileCategory | None, Form()] = None,
    user: CurrentUser = Depends(require_roles(*CASE_WRITERS)),
) -> dict:
    settings = get_settings()
    storage = get_storage_provider()

    payloads: list[tuple[str, str, bytes]] = []
    for upload in files:
        name = safe_filename(upload.filename or "upload")
        ext = _ext(name)
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"'{name}': .{ext} is not supported"
            )
        data = await upload.read(settings.MAX_UPLOAD_BYTES + 1)
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"'{name}' is too large")
        payloads.append((name, ext, data))

    saved = []
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id)
        for name, ext, data in payloads:
            category = file_category or (
                "demography_census" if ext in CENSUS_EXTENSIONS else "rfq_document"
            )
            encrypted = is_password_protected(data)
            key = storage.save_raw_input(
                case_id, name, data, CONTENT_TYPES.get(ext, "application/octet-stream")
            )
            row = conn.execute(
                "insert into case_files (case_id, original_filename, file_extension, file_size,"
                " file_category, is_encrypted, storage_path, storage_driver)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s)"
                " returning id::text, original_filename, file_category::text, is_encrypted",
                (case_id, name, ext, len(data), category, encrypted, key,
                 settings.STORAGE_BACKEND),
            ).fetchone()  # fmt: skip
            saved.append(row)
        conn.execute(
            "update cases set status = 'uploaded', updated_at = now()"
            " where id = %s and status = 'draft'",
            (case_id,),
        )
    return {"files": saved}


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/demography/process
# ---------------------------------------------------------------------------


class DemographyProcessRequest(BaseModel):
    file_id: str | None = Field(
        default=None, description="Census file; defaults to the latest uploaded census"
    )
    # Used in RAM only for this request; never stored, logged, or echoed back.
    password: SecretStr | None = None
    basis_mode: demography.AgeBasisMode | None = None
    proposal_start_date: date | None = None


_RECORD_COLUMNS = [
    "calculated_age", "dob", "sum_insured", "relationship", "member_name", "employee_code",
    "gender", "source_age_raw", "is_under18_employee", "is_orphan_dependent",
    "is_duplicate_record", "has_validation_exception", "source_row_number",
]  # fmt: skip
_NULL = r"\N"


def _copy_csv(conn: psycopg.Connection, table: str, columns: list[str], df: pl.DataFrame):
    """
    Bulk-loads a frame with COPY; `\\N` marks NULL so empty strings stay empty strings.
    Postgres refuses COPY into RLS tables, so callers COPY into a temp staging table.
    """
    buf = io.BytesIO()
    df.select(columns).write_csv(buf, include_header=False, null_value=_NULL)
    with conn.cursor().copy(
        f"copy {table} ({', '.join(columns)}) from stdin with (format csv, null '{_NULL}')"
    ) as copy:
        copy.write(buf.getvalue())


def _persist(conn: psycopg.Connection, case_id: str, result: demography.DemographyResult):
    conn.execute("delete from demography_exceptions where case_id = %s", (case_id,))
    conn.execute("delete from demography_records where case_id = %s", (case_id,))

    records = result.records.with_columns(
        pl.lit(case_id).alias("case_id"),
        pl.col("dob").dt.strftime("%d-%m-%Y"),  # Doc 05: dob stored as DD-MM-YYYY text
    )
    columns = ", ".join(["case_id", *_RECORD_COLUMNS])
    conn.execute(
        "create temp table _demography_rec (like demography_records including defaults)"
        " on commit drop"
    )
    _copy_csv(conn, "_demography_rec", ["case_id", *_RECORD_COLUMNS], records)
    # Set-based insert from staging; RLS policies are checked here.
    conn.execute(
        f"insert into demography_records ({columns}) select {columns} from _demography_rec"
    )

    conn.execute(
        "create temp table _demography_exc (source_row_number int, exception_type text,"
        " severity text, error_message text) on commit drop"
    )
    _copy_csv(
        conn,
        "_demography_exc",
        ["source_row_number", "exception_type", "severity", "error_message"],
        result.exceptions,
    )
    conn.execute(
        "insert into demography_exceptions"
        " (case_id, record_id, exception_type, severity, error_message)"
        " select %(case_id)s, r.id, e.exception_type, e.severity, e.error_message"
        " from _demography_exc e left join demography_records r"
        "   on r.case_id = %(case_id)s and r.source_row_number = e.source_row_number",
        {"case_id": case_id},
    )

    m = result.metrics
    conn.execute(
        "update cases set group_size = %s, primary_members_count = %s, sme_flag = %s,"
        " updated_at = now() where id = %s",
        (m.group_size, m.primary_members_count, m.sme_flag, case_id),
    )


def demography_from_stream(
    conn: psycopg.Connection, case_id: str, file: dict, stream: io.BytesIO, basis_date: date
) -> demography.DemographyResult:
    """Decrypted census stream → stored records, exceptions and group metrics."""
    try:
        census = demography.read_census(stream, file["original_filename"])
        result = demography.process_census(census, basis_date)
    finally:
        stream.close()  # plaintext buffer released; never written to disk
    _persist(conn, case_id, result)
    if file["is_encrypted"]:
        conn.execute(
            "update case_files set is_decrypted_successfully = true where id = %s", (file["id"],)
        )
    return result


def save_demography_export(case_id: str, result: demography.DemographyResult) -> str:
    return get_storage_provider().save_analysis_output(
        case_id,
        EXPORT_FILENAME,
        demography.seven_column_excel_bytes(result.records),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def exception_counts(result: demography.DemographyResult) -> dict[str, int]:
    counts = result.exceptions.group_by("exception_type").len().sort("exception_type")
    return dict(counts.iter_rows())


@router.post("/{case_id}/demography/process")
def process_demography(
    case_id: str,
    body: DemographyProcessRequest,
    user: CurrentUser = Depends(require_roles(*DEMOGRAPHY_PROCESSORS)),
) -> dict:
    storage = get_storage_provider()

    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id)
        file = conn.execute(
            "select id::text, original_filename, storage_path, is_encrypted from case_files"
            " where case_id = %s and file_category = 'demography_census'"
            " and (%s::uuid is null or id = %s::uuid)"
            " order by uploaded_at desc limit 1",
            (case_id, body.file_id, body.file_id),
        ).fetchone()
        if file is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No demography census file found")

        mode = body.basis_mode or demography.AgeBasisMode(case["age_basis_mode"])
        start = body.proposal_start_date or (
            case["proposal_start_date"].date() if case["proposal_start_date"] else None
        )
        try:
            basis_date = demography.resolve_basis_date(mode, start)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

        raw = storage.get_raw_input_stream(file["storage_path"]).getvalue()
        password = body.password.get_secret_value() if body.password else None
        try:
            stream = open_decrypted(raw, file["original_filename"], password)
        except PasswordRequiredException as exc:
            raise HTTPException(
                status.HTTP_423_LOCKED,
                {"code": "password_required", "file_id": file["id"], "message": str(exc)},
            ) from None
        except InvalidPasswordException as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"code": "invalid_password", "file_id": file["id"], "message": str(exc)},
            ) from None
        finally:
            password = None  # drop the only reference we hold
            body.password = None

        try:
            result = demography_from_stream(conn, case_id, file, stream, basis_date)
        except demography.CensusFormatError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        finally:
            del stream
        if body.basis_mode or body.proposal_start_date:
            conn.execute(
                "update cases set age_basis_mode = %s,"
                " proposal_start_date = coalesce(%s::date, proposal_start_date) where id = %s",
                (mode.value, body.proposal_start_date, case_id),
            )

    export_key = save_demography_export(case_id, result)
    return {
        "file_id": file["id"],
        "basis_mode": mode.value,
        "basis_date": basis_date.isoformat(),
        "group_size": result.metrics.group_size,
        "primary_members_count": result.metrics.primary_members_count,
        "sme_flag": result.metrics.sme_flag,
        "exception_counts": exception_counts(result),
        "header_mapping": result.header_mapping,
        "unmapped_columns": result.unmapped_columns,
        "export_path": export_key,
    }


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/extract/rfq — parse → Pass 1 → Pass 2 → sub-limit matcher
# ---------------------------------------------------------------------------

QUOTE_EXPORT = "quote_extracted_terms.json"
SUBLIMIT_EXPORT = "sublimit_matching_report.json"
RFQ_EXTENSIONS = {"pdf", "docx", "txt", "md"}


class RfqExtractRequest(BaseModel):
    # file_id → password for locked RFQs; used in RAM for this request only.
    passwords: dict[str, SecretStr] = Field(default_factory=dict)


def _registry(conn: psycopg.Connection) -> dict[str, sublimits.RegistryRow]:
    rows = conn.execute(
        "select procedure_name, option_1_amount, option_2_amount, option_3_amount,"
        " option_4_amount from sublimit_registry order by display_order"
    ).fetchall()
    return {
        r["procedure_name"]: sublimits.RegistryRow(
            r["procedure_name"],
            tuple(r[f"option_{i}_amount"].normalize() for i in range(1, 5)),
        )
        for r in rows
    }


def _audit(
    conn, user: CurrentUser, case_id: str, action: str, target: str, old, new,
    justification: str | None = None,
) -> None:  # fmt: skip
    conn.execute(
        "insert into audit_logs (case_id, user_id, user_email, action, target_entity,"
        " old_value, new_value, justification_reason) values (%s, %s, %s, %s, %s, %s, %s, %s)",
        (case_id, user.id, user.email, action, target, Jsonb(old), Jsonb(new), justification),
    )


def _parse_rfq_files(files: list[dict], passwords: dict[str, SecretStr]):
    storage = get_storage_provider()
    parsed, locked = [], []
    for f in files:
        secret = passwords.get(f["id"])
        password = secret.get_secret_value() if secret else None
        raw = storage.get_raw_input_stream(f["storage_path"]).getvalue()
        try:
            parsed.append(parser.parse_document(raw, f["original_filename"], password))
        except PasswordRequiredException:
            locked.append({"file_id": f["id"], "filename": f["original_filename"]})
        except InvalidPasswordException as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"code": "invalid_password", "file_id": f["id"], "message": str(exc)},
            ) from None
        finally:
            password = None
    if locked:
        raise HTTPException(status.HTTP_423_LOCKED, {"code": "password_required", "files": locked})
    return parsed


_EXTRACTION_UPSERT = """
insert into rfq_extractions (case_id, section, field_name, coverage_details, proposed_details,
  source_status, confidence_rating, confidence_score, source_file_id, source_page_or_sheet,
  verbatim_excerpt, reflection_explanation, updated_at)
values (%(case_id)s, %(section)s, %(field_name)s, %(coverage)s, %(proposed)s, %(status)s,
  %(rating)s, %(score)s, %(file_id)s, %(page)s, %(excerpt)s, %(explanation)s, now())
on conflict (case_id, field_name) do update set
  section = excluded.section, coverage_details = excluded.coverage_details,
  proposed_details = excluded.proposed_details, source_status = excluded.source_status,
  confidence_rating = excluded.confidence_rating, confidence_score = excluded.confidence_score,
  source_file_id = excluded.source_file_id, source_page_or_sheet = excluded.source_page_or_sheet,
  verbatim_excerpt = excluded.verbatim_excerpt,
  reflection_explanation = excluded.reflection_explanation, updated_at = now()
where rfq_extractions.is_manual_override = false
"""

_SUBLIMIT_UPSERT = """
insert into procedure_sublimits (case_id, procedure_name, extracted_amount_raw,
  cleaned_amount_numeric, matched_option, status, source_page, verbatim_snippet)
values (%(case_id)s, %(procedure)s, %(raw)s, %(cleaned)s, %(option)s, %(status)s, %(page)s,
  %(snippet)s)
on conflict (case_id, procedure_name) do update set
  extracted_amount_raw = excluded.extracted_amount_raw,
  cleaned_amount_numeric = excluded.cleaned_amount_numeric,
  matched_option = excluded.matched_option, status = excluded.status,
  source_page = excluded.source_page, verbatim_snippet = excluded.verbatim_snippet
where procedure_sublimits.is_underwriter_approved = false
"""


def _prefill_location(conn, case: dict, rows: list[extractor.GridRow]) -> None:
    """Fills empty PINCODE/State/District from grounded RFQ values and re-derives Zone."""
    found = {
        r.field_name: (r.proposed_details or r.coverage_details or "").strip()
        for r in rows
        if r.field_name in {"PIN Code", "State", "District"} and r.source_status == "rfq_data"
    }
    updates = {
        col: found[name]
        for col, name in (("pincode", "PIN Code"), ("state", "State"), ("district", "District"))
        if not case[col] and found.get(name)
    }
    if updates.get("pincode") and not derivations.PINCODE_RE.match(updates["pincode"]):
        updates.pop("pincode")
    if not updates:
        return
    case.update(updates)
    case["zone"], _ = derivations.resolve_zone(
        conn, case["pincode"], case["state"], case["district"]
    )
    conn.execute(
        "update cases set pincode = %s, state = %s, district = %s, zone = %s where id = %s",
        (case["pincode"], case["state"], case["district"], case["zone"], case["id"]),
    )


@router.post("/{case_id}/extract/rfq")
def extract_rfq(
    case_id: str,
    body: RfqExtractRequest,
    user: CurrentUser = Depends(require_roles(*CASE_WRITERS)),
) -> dict:
    # 1. Read inputs (short transaction; the LLM calls run outside any DB transaction).
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        files = conn.execute(
            "select id::text, original_filename, storage_path from case_files"
            " where case_id = %s and file_category = 'rfq_document'"
            " and file_extension = any(%s) order by uploaded_at",
            (case_id, list(RFQ_EXTENSIONS)),
        ).fetchall()
        registry = _registry(conn)
    if not files:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No RFQ document (PDF/DOCX/TXT) uploaded")

    # 2. Parse in RAM, then two-pass extraction over the combined Markdown.
    documents = _parse_rfq_files(files, body.passwords)
    body.passwords = {}
    try:
        return run_extraction(user, case_id, files, documents, registry)
    except extractor.LLMNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


def run_extraction(
    user: CurrentUser,
    case_id: str,
    files: list[dict],
    documents: list,
    registry: dict[str, sublimits.RegistryRow],
    on_extracted=None,
) -> dict:
    """
    Pass 1 → Pass 2 over the parsed documents, then the deterministic sub-limit matcher,
    derived fields and persistence. `on_extracted` fires between the LLM passes and the
    matching/persistence step (pipeline progress).
    """
    markdown = parser.combine(documents)
    outcome = extractor.extract_rfq(markdown, list(registry), client=_llm_client())
    if on_extracted:
        on_extracted(outcome)

    matches: dict[str, tuple[sublimits.SublimitMatch, object]] = {}
    for s in outcome.pass1.sublimits:
        if s.procedure_name not in matches:
            matches[s.procedure_name] = (
                sublimits.match_sublimit(s.procedure_name, s.raw_amount_text, registry),
                s,
            )

    # 3. Persist (manual overrides and underwriter-approved sub-limits are preserved).
    file_ids = {f["original_filename"].lower(): f["id"] for f in files}
    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id)
        _prefill_location(conn, case, outcome.rows)
        # Manual values (e.g. Incumbent Insurer entered at intake) drive the derived fields.
        manual = {
            r["field_name"]: r
            for r in conn.execute(
                "select field_name, coverage_details, proposed_details from rfq_extractions"
                " where case_id = %s and is_manual_override",
                (case_id,),
            ).fetchall()
        }
        base = [
            extractor.GridRow(r.section, r.field_name, m["coverage_details"],
                              m["proposed_details"], "manual", "high")
            if (m := manual.get(r.field_name)) else r
            for r in outcome.rows
        ]  # fmt: skip
        rows = base + extractor.derived_rows(case, base)
        with conn.cursor() as cur:
            cur.executemany(
                _EXTRACTION_UPSERT,
                [
                    {
                        "case_id": case_id, "section": r.section, "field_name": r.field_name,
                        "coverage": r.coverage_details, "proposed": r.proposed_details,
                        "status": r.source_status, "rating": r.confidence_rating,
                        "score": r.confidence_score,
                        "file_id": file_ids.get((r.source_file or "").lower()),
                        "page": (r.source_page or "")[:100] or None,
                        "excerpt": r.verbatim_excerpt, "explanation": r.reflection_explanation,
                    }
                    for r in rows
                ],
            )  # fmt: skip
            conn.execute(
                "delete from procedure_sublimits where case_id = %s"
                " and is_underwriter_approved = false and procedure_name <> all(%s)",
                (case_id, list(matches)),
            )
            if matches:
                cur.executemany(
                    _SUBLIMIT_UPSERT,
                    [
                        {
                            "case_id": case_id, "procedure": m.procedure_name,
                            "raw": m.extracted_amount_raw, "cleaned": m.cleaned_amount,
                            "option": m.matched_option, "status": m.status,
                            "page": (src.source_page or "")[:50] or None,
                            "snippet": src.verbatim_evidence,
                        }
                        for m, src in matches.values()
                    ],
                )  # fmt: skip
        proposal_type = next(r for r in rows if r.field_name == "Type of Proposal")
        needs_review = any(
            r.source_status in {"review_required", "conflict", "ambiguous"} for r in rows
        ) or any(m.matched_option == "unmatched" for m, _ in matches.values())
        conn.execute(
            "update cases set proposal_type = %s, status = %s, model_version = %s,"
            " pipeline_duration_ms = %s, updated_at = now() where id = %s",
            (proposal_type.proposed_details,
             "review_required" if needs_review else "ready_for_quote",
             outcome.model, outcome.latency_ms, case_id),
        )  # fmt: skip
        _audit(
            conn, user, case_id, "ai_extraction", "rfq_extractions", None,
            {"model": outcome.model, "latency_ms": outcome.latency_ms, "usage": outcome.usage,
             "files": [d.filename for d in documents]},
        )  # fmt: skip

    # 4. Archive verified outputs.
    storage = get_storage_provider()
    storage.save_analysis_output(
        case_id, QUOTE_EXPORT,
        json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=2).encode(),
        "application/json",
    )  # fmt: skip
    storage.save_analysis_output(
        case_id, SUBLIMIT_EXPORT,
        json.dumps(
            [{"procedure_name": m.procedure_name, "raw": m.extracted_amount_raw,
              "cleaned": str(m.cleaned_amount) if m.cleaned_amount is not None else None,
              "matched_option": m.matched_option, "match": m.match_label}
             for m, _ in matches.values()],
            ensure_ascii=False, indent=2,
        ).encode(),
        "application/json",
    )  # fmt: skip

    counts: dict[str, int] = {}
    for r in rows:
        counts[r.source_status] = counts.get(r.source_status, 0) + 1
    return {
        "proposal_type": proposal_type.proposed_details,
        "fields": len(rows),
        "source_status_counts": counts,
        "sublimits_matched": sum(m.matched_option != "unmatched" for m, _ in matches.values()),
        "sublimits_review_required": sum(
            m.matched_option == "unmatched" for m, _ in matches.values()
        ),
        "model": outcome.model,
        "latency_ms": outcome.latency_ms,
        "usage": outcome.usage,
    }


def _llm_client():
    """Seam for tests: overridden to inject a fake instructor client."""
    return None


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/extractions — 5-column Quote Review Grid
# ---------------------------------------------------------------------------

_FIELD_ORDER = {f.name: i for i, f in enumerate(field_registry.FIELDS)}


@router.get("/{case_id}/extractions")
def get_extractions(case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        rows = conn.execute(
            "select e.id::text, e.section, e.field_name, e.coverage_details, e.proposed_details,"
            " e.source_status::text, e.confidence_rating::text, e.confidence_score,"
            " e.is_manual_override, e.override_reason, f.original_filename as source_file,"
            " e.source_page_or_sheet, e.verbatim_excerpt, e.reflection_explanation, e.updated_at"
            " from rfq_extractions e left join case_files f on f.id = e.source_file_id"
            " where e.case_id = %s",
            (case_id,),
        ).fetchall()
    rows.sort(key=lambda r: _FIELD_ORDER.get(r["field_name"], len(_FIELD_ORDER)))
    return {
        "columns": ["Quote Fields", "Coverage Details", "Proposed Details", "Source Status",
                    "Confidence"],
        "rows": [
            {
                "id": r["id"],
                "section": r["section"],
                "quote_field": r["field_name"],
                "coverage_details": r["coverage_details"],
                "proposed_details": r["proposed_details"],
                "source_status": extractor.SOURCE_STATUS_LABELS[r["source_status"]],
                "confidence": extractor.CONFIDENCE_LABELS[r["confidence_rating"]],
                "confidence_score": float(r["confidence_score"] or 0),
                "is_manual_override": r["is_manual_override"],
                "evidence": {
                    "file": r["source_file"],
                    "page": r["source_page_or_sheet"],
                    "excerpt": r["verbatim_excerpt"],
                    "verification": r["reflection_explanation"],
                },
            }
            for r in rows
        ],
    }  # fmt: skip


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/sublimits — 19-procedure grid
# ---------------------------------------------------------------------------


@router.get("/{case_id}/sublimits")
def get_sublimits(case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        rows = conn.execute(
            "select r.procedure_name, r.option_1_amount, r.option_2_amount, r.option_3_amount,"
            " r.option_4_amount, p.extracted_amount_raw, p.cleaned_amount_numeric,"
            " p.matched_option::text, p.status::text, p.is_underwriter_approved,"
            " p.approval_justification, p.source_page, p.verbatim_snippet"
            " from sublimit_registry r left join procedure_sublimits p"
            "   on p.procedure_name = r.procedure_name and p.case_id = %s"
            " order by r.display_order",
            (case_id,),
        ).fetchall()

    def match_label(r: dict) -> str:
        if r["matched_option"] is None:
            return sublimits.NOT_FOUND
        return sublimits.MATCHED if r["matched_option"] != "unmatched" else sublimits.UNMATCHED

    return {
        "rows": [
            {
                "procedure_name": r["procedure_name"],
                "options": {f"Option {i}": float(r[f"option_{i}_amount"]) for i in range(1, 5)},
                "extracted_amount_raw": r["extracted_amount_raw"],
                "cleaned_amount": float(r["cleaned_amount_numeric"])
                if r["cleaned_amount_numeric"] is not None
                else None,
                "matched_option": sublimits.OPTION_LABELS.get(r["matched_option"]),
                "match_status": match_label(r),
                "source_status": extractor.SOURCE_STATUS_LABELS.get(r["status"]),
                "is_underwriter_approved": bool(r["is_underwriter_approved"]),
                "approval_justification": r["approval_justification"],
                "evidence": {"page": r["source_page"], "excerpt": r["verbatim_snippet"]},
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# PATCH /cases/{case_id}/manual-inputs — editable inputs + Zone re-derivation
# ---------------------------------------------------------------------------


class ManualInputsPatch(BaseModel):
    rater_type: str | None = Field(default=None, max_length=100)
    brokerage_pct: Decimal | None = Field(default=None, ge=0, le=15, decimal_places=2)
    pincode: str | None = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)


# Manual input column → Quote Review Grid field it overrides.
_MANUAL_GRID_FIELDS = {
    "rater_type": "Rater Type",
    "brokerage_pct": "Brokerage %",
    "pincode": "PIN Code",
    "state": "State",
    "district": "District",
}


@router.patch("/{case_id}/manual-inputs")
def patch_manual_inputs(
    case_id: str,
    body: ManualInputsPatch,
    user: CurrentUser = Depends(require_roles(*CASE_WRITERS)),
) -> dict:
    sent = body.model_dump(include=body.model_fields_set)
    if not sent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No manual inputs supplied")

    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id)
        changed = {k: v for k, v in sent.items() if v != case[k]}
        for column, value in changed.items():
            conn.execute(
                f"update cases set {column} = %s, updated_at = now() where id = %s",
                (value, case_id),
            )
            _audit(conn, user, case_id, "manual_input_update", f"cases.{column}",
                   {column: _jsonable(case[column])}, {column: _jsonable(value)})  # fmt: skip
            conn.execute(
                "update rfq_extractions set proposed_details = %s, source_status = 'manual',"
                " confidence_rating = 'high', confidence_score = 1, is_manual_override = true,"
                " overridden_by_user_id = %s, updated_at = now()"
                " where case_id = %s and field_name = %s",
                (None if value is None else str(value), user.id, case_id,
                 _MANUAL_GRID_FIELDS[column]),
            )  # fmt: skip
            case[column] = value

        zone, matched_by = derivations.resolve_zone(
            conn, case["pincode"], case["state"], case["district"]
        )
        if zone != case["zone"]:
            conn.execute("update cases set zone = %s where id = %s", (zone, case_id))
            _audit(conn, user, case_id, "zone_recalc", "cases.zone",
                   {"zone": case["zone"]}, {"zone": zone, "matched_by": matched_by})  # fmt: skip
            conn.execute(
                "update rfq_extractions set proposed_details = %s, source_status = %s,"
                " confidence_rating = %s, updated_at = now()"
                " where case_id = %s and field_name = 'Zone'",
                (zone, "review_required" if matched_by == "none" else "ai_derived",
                 "low" if matched_by == "none" else "high", case_id),
            )  # fmt: skip

    return {
        "rater_type": case["rater_type"],
        "brokerage_pct": _jsonable(case["brokerage_pct"]),
        "pincode": case["pincode"],
        "state": case["state"],
        "district": case["district"],
        "zone": zone,
        "zone_matched_by": matched_by,
        "changed": sorted(changed),
    }


def _jsonable(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if isinstance(value, Decimal) else value
