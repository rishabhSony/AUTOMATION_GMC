"""
Case processing pipeline (Backend Schema v4.0 §8.1 `/process` and `/pipeline-status`).

`POST /cases/{id}/process` inspects every uploaded file synchronously: encrypted files are
decrypted in RAM with the passwords in the request (423 lists files still locked, 422 a
wrong password). The passwords are dropped before the response; only the decrypted
in-memory buffers are handed to the background run, which works through four stages:

  1. intake      File upload & in-memory decryption (done during the request)
  2. demography  Vectorized demography processing & exception triage
  3. extraction  AI RFQ extraction (Pass 1) & reflection grounding (Pass 2)
  4. matching    Sub-limit matching & proposal-type derivation, then persistence

Celery/Redis aren't available locally, so the run uses FastAPI BackgroundTasks in the API
process and progress lives in process memory (`_RUNS`). That is enough for a single local
API process; `process_case_pipeline` on Celery replaces it on EC2 (TRD §3).
"""

import io
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr

from app.api.v1 import cases as cases_api
from app.api.v1.cases import ALL_ROLES, CASE_WRITERS, _audit, _lock_case
from app.core.auth import CurrentUser, require_roles
from app.core.db import rls_transaction
from app.services import demography, extractor, parser
from app.services.storage import (
    InvalidPasswordException,
    PasswordRequiredException,
    get_storage_provider,
    open_decrypted,
)

router = APIRouter(prefix="/cases", tags=["pipeline"])
log = logging.getLogger(__name__)

StageKey = Literal["intake", "demography", "extraction", "matching"]
StageState = Literal["pending", "running", "done", "skipped", "failed"]
STAGES: list[tuple[StageKey, str]] = [
    ("intake", "File Upload & In-Memory Decryption"),
    ("demography", "Vectorized Demography Processing & Exception Triage"),
    ("extraction", "AI RFQ Extraction (Pass 1) & Reflection Grounding (Pass 2)"),
    ("matching", "Sub-Limit Matching & Proposal Type Derivation"),
]
# Case statuses that end a run; the workbench opens on any of them except `failed`.
TERMINAL_STATUSES = {"review_required", "ready_for_quote", "completed", "failed"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Stage:
    key: StageKey
    label: str
    state: StageState = "pending"
    detail: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class PipelineRun:
    case_id: str
    stages: list[Stage] = field(default_factory=lambda: [Stage(k, label) for k, label in STAGES])
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    error: str | None = None

    def stage(self, key: StageKey) -> Stage:
        return next(s for s in self.stages if s.key == key)

    def start(self, key: StageKey, detail: str | None = None) -> None:
        s = self.stage(key)
        s.state, s.started_at, s.detail = "running", _now(), detail

    def finish(self, key: StageKey, state: StageState = "done", detail: str | None = None):
        s = self.stage(key)
        s.state, s.finished_at = state, _now()
        if detail is not None:
            s.detail = detail


_RUNS: dict[str, PipelineRun] = {}
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/process
# ---------------------------------------------------------------------------


class ProcessRequest(BaseModel):
    # file_id → password for encrypted uploads; used in RAM during this request only.
    passwords: dict[str, SecretStr] = Field(default_factory=dict)
    basis_mode: demography.AgeBasisMode | None = Field(
        default=None,
        description="Defaults to the proposal start date basis when the case has one",
    )


@dataclass
class _Inputs:
    census: dict | None
    census_stream: io.BytesIO | None
    rfq_files: list[dict]
    rfq_plaintext: dict[str, bytes]  # file_id → decrypted bytes (RAM only)


def _inspect(files: list[dict], passwords: dict[str, SecretStr]) -> _Inputs:
    """Decrypts every file that will be processed; raises 423/422 like the other endpoints."""
    storage = get_storage_provider()
    census = next((f for f in files if f["file_category"] == "demography_census"), None)
    rfq = [
        f
        for f in files
        if f["file_category"] == "rfq_document" and f["file_extension"] in cases_api.RFQ_EXTENSIONS
    ]
    plaintext: dict[str, bytes] = {}
    locked = []
    for f in ([census] if census else []) + rfq:
        secret = passwords.get(f["id"])
        password = secret.get_secret_value() if secret else None
        raw = storage.get_raw_input_stream(f["storage_path"]).getvalue()
        try:
            plaintext[f["id"]] = open_decrypted(raw, f["original_filename"], password).getvalue()
        except PasswordRequiredException:
            locked.append({"file_id": f["id"], "filename": f["original_filename"]})
        except InvalidPasswordException as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"code": "invalid_password", "file_id": f["id"],
                 "filename": f["original_filename"], "message": str(exc)},
            ) from None  # fmt: skip
        finally:
            password = None
    if locked:
        raise HTTPException(status.HTTP_423_LOCKED, {"code": "password_required", "files": locked})
    return _Inputs(
        census=census,
        census_stream=io.BytesIO(plaintext.pop(census["id"])) if census else None,
        rfq_files=rfq,
        rfq_plaintext=plaintext,
    )


@router.post("/{case_id}/process", status_code=status.HTTP_202_ACCEPTED)
def process_case(
    case_id: str,
    body: ProcessRequest,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_roles(*CASE_WRITERS)),
) -> dict:
    with rls_transaction(user.rls) as conn:
        case = _lock_case(conn, case_id)  # row lock serialises concurrent starts
        active = _RUNS.get(case_id)
        if active is not None and active.finished_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This case is already processing")
        files = conn.execute(
            "select id::text, original_filename, file_extension, file_category::text,"
            " storage_path, is_encrypted from case_files where case_id = %s"
            " order by uploaded_at desc",
            (case_id,),
        ).fetchall()
        if not files:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload an RFQ or census file first")

        inputs = _inspect(files, body.passwords)
        body.passwords = {}  # passwords end here; only decrypted buffers go on
        if inputs.census is None and not inputs.rfq_files:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "No census (CSV/XLS/XLSX) or RFQ (PDF/DOCX/TXT/MD) file to process",
            )

        start = case["proposal_start_date"].date() if case["proposal_start_date"] else None
        mode = body.basis_mode or (
            demography.AgeBasisMode.POLICY_PROPOSAL_START_DATE
            if start
            else demography.AgeBasisMode(case["age_basis_mode"])
        )
        try:
            basis_date = demography.resolve_basis_date(mode, start)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

        conn.execute(
            "update cases set status = 'processing', age_basis_mode = %s, updated_at = now()"
            " where id = %s",
            (mode.value, case_id),
        )
        encrypted = [f["id"] for f in files if f["is_encrypted"]]
        if encrypted:
            conn.execute(
                "update case_files set is_decrypted_successfully = true where id = any(%s::uuid[])",
                (encrypted,),
            )
        _audit(conn, user, case_id, "pipeline_started", "cases.status", None,
               {"files": len(files), "decrypted_in_memory": len(encrypted),
                "basis_mode": mode.value, "basis_date": basis_date.isoformat()})  # fmt: skip

    run = PipelineRun(case_id)
    run.finish(
        "intake",
        detail=f"{len(files)} file(s) read; {len(encrypted)} decrypted in memory",
    )
    with _LOCK:
        _RUNS[case_id] = run
    background.add_task(_run_pipeline, run, user, inputs, basis_date)
    return {"case_id": case_id, "status": "processing", "stages": _stages(run)}


def _run_pipeline(run: PipelineRun, user: CurrentUser, inputs: _Inputs, basis_date) -> None:
    case_id = run.case_id
    current: StageKey = "demography"
    try:
        # 2. Demography
        if inputs.census is not None:
            run.start("demography", inputs.census["original_filename"])
            with rls_transaction(user.rls) as conn:
                result = cases_api.demography_from_stream(
                    conn, case_id, inputs.census, inputs.census_stream, basis_date
                )
            inputs.census_stream = None
            cases_api.save_demography_export(case_id, result)
            m = result.metrics
            open_exc = sum(cases_api.exception_counts(result).values())
            sme = "Yes" if m.sme_flag else "No"
            run.finish(
                "demography",
                detail=f"{m.group_size} members, {m.primary_members_count} primary, "
                f"SME {sme}, {open_exc} exception(s)",
            )
        else:
            run.finish("demography", "skipped", "No census uploaded")

        # 3–4. RFQ extraction, then matching and persistence
        current = "extraction"
        if inputs.rfq_files:
            run.start("extraction", f"{len(inputs.rfq_files)} RFQ document(s)")
            documents = [
                parser.parse_document(inputs.rfq_plaintext.pop(f["id"]), f["original_filename"])
                for f in inputs.rfq_files
            ]
            with rls_transaction(user.rls) as conn:
                registry = cases_api._registry(conn)

            def extracted(outcome: extractor.ExtractionOutcome) -> None:
                nonlocal current
                found = sum(r.source_status not in {"not_found", "default_data"}
                            for r in outcome.rows)  # fmt: skip
                run.finish("extraction", detail=f"{found} fields extracted with {outcome.model}")
                current = "matching"
                run.start("matching", f"{len(outcome.pass1.sublimits)} sub-limit(s) found")

            summary = cases_api.run_extraction(
                user, case_id, inputs.rfq_files, documents, registry, on_extracted=extracted
            )
            run.finish("matching", detail=f"{summary['sublimits_matched']} matched, "
                       f"{summary['sublimits_review_required']} need review; proposal type "
                       f"{summary['proposal_type']}")  # fmt: skip
        else:
            run.finish("extraction", "skipped", "No RFQ document uploaded")
            run.finish("matching", "skipped", "No RFQ document uploaded")
            with rls_transaction(user.rls) as conn:
                # Without an RFQ the quote can't be complete, so the case needs review.
                conn.execute(
                    "update cases set status = 'review_required', updated_at = now() where id = %s",
                    (case_id,),
                )
    except Exception as exc:  # any failure ends the run visibly instead of hanging
        log.exception("Pipeline failed for case %s", case_id)
        run.finish(current, "failed", str(exc)[:500])
        run.error = f"{type(exc).__name__}: {str(exc)[:500]}"
        with rls_transaction(user.rls) as conn:
            conn.execute(
                "update cases set status = 'failed', updated_at = now() where id = %s", (case_id,)
            )
            _audit(conn, user, case_id, "pipeline_failed", "cases.status", None,
                   {"stage": current, "error": run.error})  # fmt: skip
    finally:
        inputs.rfq_plaintext.clear()
        run.finished_at = _now()


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/pipeline-status (polled by the pipeline screen)
# ---------------------------------------------------------------------------


def _stages(run: PipelineRun) -> list[dict]:
    return [s.__dict__.copy() for s in run.stages]


@router.get("/{case_id}/pipeline-status")
def pipeline_status(case_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))) -> dict:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        case_status = conn.execute(
            "select status::text from cases where id = %s", (case_id,)
        ).fetchone()["status"]
    run = _RUNS.get(case_id)
    if run is None:
        # No run in this API process (never started, or the server restarted).
        state: StageState = "done" if case_status in TERMINAL_STATUSES - {"failed"} else "pending"
        stages = [Stage(k, label, state).__dict__ for k, label in STAGES]
        return {
            "case_id": case_id,
            "status": case_status,
            "stages": stages,
            "terminal": case_status in TERMINAL_STATUSES,
            # `processing` without a run means the API restarted mid-run: allow a restart.
            "can_start": case_status in {"draft", "uploaded", "failed", "processing"},
            "error": None,
            "in_memory_run": False,
        }
    return {
        "case_id": case_id,
        "status": case_status,
        "stages": _stages(run),
        "terminal": run.finished_at is not None and case_status in TERMINAL_STATUSES,
        "can_start": run.finished_at is not None,
        "error": run.error,
        "in_memory_run": True,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
