"""
Two-pass RFQ extraction (TRD §7, Plan Phase 5) with `gpt-5.4-mini` via `instructor`.

Pass 1 extracts every EXTRACT field in the registry from the whole RFQ Markdown in one
call (400k-token context; no chunking, no RAG), keeping Current (`coverage_details`) and
Proposed (`proposed_details`) apart, with verbatim evidence and page citations.

Pass 2 reflects over Pass 1 against the same text and returns a verdict and confidence
per field. Its verdict is combined with a deterministic grounding check: the cited
verbatim evidence must occur in the parsed text, otherwise the field is demoted to
Review Required / Low whatever the model says.

`assemble_rows` (pure, no I/O) turns both passes into Quote Review Grid rows and applies
Default Data, the TPA rule, the room-rent splitter fallback and value validators.
"""

import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import httpx2
import instructor
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.services import derivations
from app.services.field_registry import (
    CLAIM_SERVICING,
    EXTRACT_FIELDS,
    INCUMBENT_INSURER,
    ROOM_RENT_ICU,
    ROOM_RENT_NORMAL,
    ROOM_RENT_PARENT,
    TPA_NAME,
    TYPE_OF_PROPOSAL,
    ExtractFieldName,
    ProcedureName,
    registry_prompt,
)
from app.services.mock_llm import MockLLMClient

SCHEMA_VERSION = "rfq-extraction/1"
CONFIDENCE_SCORES = {"high": "0.950", "medium": "0.750", "low": "0.400"}


class LLMNotConfiguredError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Structured output schemas. OpenAI strict mode needs every key required (nullable when
# absent) and `additionalProperties: false` on every object, hence extra="forbid".
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedField(_Strict):
    field_name: ExtractFieldName
    coverage_details: str | None = Field(
        description="Value under the CURRENT/expiring policy. Null if the RFQ states none."
    )
    proposed_details: str | None = Field(
        description="Value REQUESTED for the new/proposed policy. Null if not requested."
    )
    verbatim_evidence: str | None = Field(
        description="Exact text copied character-for-character from the document."
    )
    source_file: str | None = Field(description="File name from the nearest [[File: …]] marker")
    source_page: str | None = Field(description="Page number from the nearest [[… Page N]] marker")


class ExtractedSublimit(_Strict):
    procedure_name: ProcedureName
    raw_amount_text: str = Field(
        description="Limit exactly as written, e.g. 'Rs. 1,20,000/-' or '10% of SI'"
    )
    verbatim_evidence: str
    source_file: str | None
    source_page: str | None


class Pass1Extraction(_Strict):
    fields: list[ExtractedField]
    sublimits: list[ExtractedSublimit]
    unmapped_clauses: list[str] = Field(
        description="Material clauses that fit no registry field (for underwriter review)"
    )


class FieldVerdict(_Strict):
    field_name: ExtractFieldName
    verdict: Literal["supported", "ambiguous", "conflict", "unsupported"]
    confidence: Literal["High", "Medium", "Low"]
    explanation: str


class Pass2Verification(_Strict):
    verdicts: list[FieldVerdict]


# ---------------------------------------------------------------------------
# Client & prompts
# ---------------------------------------------------------------------------


def use_mock_ai() -> bool:
    """USE_MOCK_AI, or no key in development. Production without a key fails loudly instead."""
    settings = get_settings()
    return settings.USE_MOCK_AI or (
        not settings.OPENAI_API_KEY and settings.ENVIRONMENT == "development"
    )


def get_llm_client():
    if use_mock_ai():
        return MockLLMClient()  # fresh per extraction: it carries Pass 1 into Pass 2
    return _openai_client()


@lru_cache
def _openai_client() -> instructor.Instructor:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise LLMNotConfiguredError(
            "OPENAI_API_KEY is not set (services/backend/.env.backend.local)"
        )
    # openai>=3 is built on httpx2 (not httpx); pass a client of the same library.
    http_client = httpx2.Client(
        proxy=settings.HTTPS_PROXY or None, timeout=settings.OPENAI_TIMEOUT_SECONDS
    )
    openai_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        max_retries=settings.OPENAI_MAX_RETRIES,
        http_client=http_client,
    )
    # instructor ≥1.17 folds TOOLS_STRICT into TOOLS; strictness is requested per call.
    return instructor.from_openai(openai_client, mode=instructor.Mode.TOOLS)


PASS1_SYSTEM = """You are a senior Group Medical Cover (GMC) underwriter extracting terms from an \
Indian corporate RFQ/tender. Rules:
1. Ground every value in the document. Never guess or use market norms; if a field is not \
stated, set its values and evidence to null.
2. Separate CURRENT vs PROPOSED: `coverage_details` is the existing/expiring policy term; \
`proposed_details` is what the client requests for the new policy. If the RFQ states a term \
once without saying it changes, put it in `proposed_details`.
3. Split compound clauses. Room rent: put the whole narrative in "Room Rent (Parent \
Clause)", the normal-room limit only in "Room Rent for Normal Room", and the ICU/ICCU/\
specialty limit only in "Room Rent for ICU & Specialty Rooms".
4. `verbatim_evidence` must be copied exactly from the document (no paraphrase, no \
ellipsis), short enough to be specific. Cite file and page from the [[File: … | Page N]] \
markers.
5. Procedure sub-limits: for each of the listed procedures the RFQ caps, return the limit \
exactly as written (amounts or percentage terms). Do not convert or round.
6. Return one entry per registry field, at most once each."""

PASS2_SYSTEM = """You verify a GMC RFQ extraction against the source document. For every \
extracted field decide:
- supported: the evidence states exactly these values, Current/Proposed are assigned correctly.
- ambiguous: the document is unclear or allows more than one reading.
- conflict: different parts of the document (e.g. an addendum vs the schedule) disagree.
- unsupported: the evidence does not substantiate the value, or the value is mis-assigned.
Give confidence High/Medium/Low and a one-sentence explanation. Judge only from the document."""


def _create(client, model: str, response_model, system: str, user: str):
    settings = get_settings()
    return client.chat.completions.create_with_completion(
        model=model,
        response_model=response_model,
        max_retries=2,
        strict=True,  # OpenAI strict structured outputs on the forced tool call
        store=not settings.OPENAI_ZERO_DATA_RETENTION,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )


def _usage(completion) -> dict:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return {}
    return {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}


def run_pass1(client, markdown: str, procedures: list[str]) -> tuple[Pass1Extraction, dict]:
    user = (
        f"GMC FIELD REGISTRY (field name: allowed values)\n{registry_prompt()}\n\n"
        f"PROCEDURES WITH SUB-LIMITS\n" + "\n".join(f"- {p}" for p in procedures) + "\n\n"
        f"RFQ DOCUMENT (Markdown)\n{markdown}"
    )
    model = get_settings().OPENAI_MODEL_EXTRACTION
    result, completion = _create(client, model, Pass1Extraction, PASS1_SYSTEM, user)
    return result, _usage(completion)


def run_pass2(client, markdown: str, pass1: Pass1Extraction) -> tuple[Pass2Verification, dict]:
    extracted = [f.model_dump() for f in pass1.fields if f.coverage_details or f.proposed_details]
    user = (
        f"EXTRACTION TO VERIFY (JSON)\n{json.dumps(extracted, ensure_ascii=False)}\n\n"
        f"RFQ DOCUMENT (Markdown)\n{markdown}"
    )
    model = get_settings().OPENAI_MODEL_VERIFICATION
    result, completion = _create(client, model, Pass2Verification, PASS2_SYSTEM, user)
    return result, _usage(completion)


# ---------------------------------------------------------------------------
# Deterministic assembly
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[‘’`´]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"[|*#_]", " ", text)  # Markdown table/emphasis markup
    return re.sub(r"\s+", " ", text).strip()


def evidence_found(evidence: str | None, normalized_source: str) -> bool:
    return bool(evidence and evidence.strip()) and _normalize(evidence) in normalized_source


@dataclass
class GridRow:
    section: str
    field_name: str
    coverage_details: str | None
    proposed_details: str | None
    source_status: str  # source_status enum value (rfq_data, default_data, …)
    confidence_rating: str  # high | medium | low
    source_file: str | None = None
    source_page: str | None = None
    verbatim_excerpt: str | None = None
    reflection_explanation: str | None = None

    @property
    def confidence_score(self) -> str:
        return CONFIDENCE_SCORES[self.confidence_rating]


_VERDICT_STATUS = {
    "supported": "rfq_data",
    "ambiguous": "ambiguous",
    "conflict": "conflict",
    "unsupported": "review_required",
}


def _value_problem(name: str, value: str | None) -> str | None:
    """BRD value rules that reject an otherwise-grounded value."""
    if not value:
        return None
    if name == "Policy Co-Payment Factor" and "%" not in value:
        return "Co-payment factor must be a percentage (BRD §6.4)"
    if name == "PIN Code" and not derivations.PINCODE_RE.match(value.strip()):
        return "PIN code must be 6 digits and not start with 0"
    return None


def assemble_rows(
    pass1: Pass1Extraction, pass2: Pass2Verification, source_markdown: str
) -> list[GridRow]:
    normalized_source = _normalize(source_markdown)
    extracted = {}
    for f in pass1.fields:
        extracted.setdefault(f.field_name, f)
    verdicts = {v.field_name: v for v in pass2.verdicts}

    rows: dict[str, GridRow] = {}
    for spec in EXTRACT_FIELDS:
        f = extracted.get(spec.name)
        if f is None or not (f.coverage_details or f.proposed_details):
            if spec.default is not None:
                rows[spec.name] = GridRow(
                    spec.section, spec.name, None, spec.default, "default_data", "medium",
                    reflection_explanation="Not stated in RFQ; BRD default applied",
                )  # fmt: skip
            else:
                rows[spec.name] = GridRow(spec.section, spec.name, None, None, "not_found", "low")
            continue

        row = GridRow(
            spec.section, spec.name, f.coverage_details, f.proposed_details, "review_required",
            "low", f.source_file, f.source_page, f.verbatim_evidence,
        )  # fmt: skip
        verdict = verdicts.get(spec.name)
        problem = _value_problem(spec.name, f.proposed_details) or _value_problem(
            spec.name, f.coverage_details
        )
        if not evidence_found(f.verbatim_evidence, normalized_source):
            row.reflection_explanation = "Verbatim evidence not found in the parsed RFQ text"
        elif problem:
            row.reflection_explanation = problem
        elif verdict is None:
            row.confidence_rating = "medium"
            row.reflection_explanation = "No Pass 2 verdict returned"
        else:
            row.source_status = _VERDICT_STATUS[verdict.verdict]
            row.confidence_rating = verdict.confidence.lower()
            row.reflection_explanation = verdict.explanation
        rows[spec.name] = row

    _apply_room_rent_split(rows)
    _apply_tpa_rule(rows)
    return list(rows.values())


def _apply_room_rent_split(rows: dict[str, GridRow]) -> None:
    parent = rows[ROOM_RENT_PARENT]
    if parent.source_status in {"not_found", "default_data"}:
        return
    current = derivations.split_room_rent(parent.coverage_details)
    proposed = derivations.split_room_rent(parent.proposed_details)
    for name, attr in ((ROOM_RENT_NORMAL, "normal"), (ROOM_RENT_ICU, "icu")):
        row = rows[name]
        if row.source_status != "not_found":
            continue
        cov, prop = getattr(current, attr), getattr(proposed, attr)
        if cov or prop:
            rows[name] = GridRow(
                parent.section, name, cov, prop, "ai_derived", "medium", parent.source_file,
                parent.source_page, parent.verbatim_excerpt,
                "Split from the parent room-rent clause by the deterministic splitter",
            )  # fmt: skip


def _apply_tpa_rule(rows: dict[str, GridRow]) -> None:
    servicing = rows[CLAIM_SERVICING]
    tpa = rows[TPA_NAME]
    value, status = derivations.derive_tpa_name(
        servicing.proposed_details or servicing.coverage_details,
        tpa.proposed_details or tpa.coverage_details,
    )
    if status == "rfq_data":
        return  # keep the extracted, verified TPA row as-is
    tpa.proposed_details = value
    tpa.source_status = status
    tpa.confidence_rating = "high" if status == "ai_derived" else "low"
    tpa.reflection_explanation = (
        "Claim Servicing is In House"
        if status == "ai_derived"
        else "TPA servicing but no TPA named"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class ExtractionOutcome:
    rows: list[GridRow]
    pass1: Pass1Extraction
    model: str
    latency_ms: int
    usage: dict = field(default_factory=dict)


def extract_rfq(markdown: str, procedures: list[str], client=None) -> ExtractionOutcome:
    client = client or get_llm_client()
    start = time.perf_counter()
    pass1, usage1 = run_pass1(client, markdown, procedures)
    pass2, usage2 = run_pass2(client, markdown, pass1)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return ExtractionOutcome(
        rows=assemble_rows(pass1, pass2, markdown),
        pass1=pass1,
        model=getattr(client, "model_name", get_settings().OPENAI_MODEL_EXTRACTION),
        latency_ms=latency_ms,
        usage={"pass1": usage1, "pass2": usage2, "schema_version": SCHEMA_VERSION},
    )


# ---------------------------------------------------------------------------
# Rows that come from case data rather than the LLM (BRD §6.1 / §6.3)
# ---------------------------------------------------------------------------

SOURCE_STATUS_LABELS = {
    "rfq_data": "RFQ Data",
    "default_data": "Default Data",
    "ai_derived": "AI Derived",
    "demography_derived": "Demography Derived",
    "manual": "Manual",
    "fixed": "Fixed",
    "not_found": "Not Found",
    "ambiguous": "Ambiguous",
    "conflict": "Conflict",
    "review_required": "Review Required",
}
CONFIDENCE_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}


def derived_rows(case: dict, extracted: list[GridRow]) -> list[GridRow]:
    by_name = {r.field_name: r for r in extracted}
    incumbent = by_name[INCUMBENT_INSURER]
    insurer = incumbent.coverage_details or incumbent.proposed_details
    proposal_type = derivations.derive_proposal_type(insurer)
    if incumbent.source_status in {"ambiguous", "conflict", "review_required"}:
        proposal = GridRow(
            "quotation",
            TYPE_OF_PROPOSAL,
            None,
            proposal_type,
            "review_required",
            "low",
            reflection_explanation="Incumbent insurer is uncertain",
        )
    else:
        proposal = GridRow(
            "quotation", TYPE_OF_PROPOSAL, None, proposal_type, "ai_derived",
            "high" if insurer else "medium", incumbent.source_file, incumbent.source_page,
            incumbent.verbatim_excerpt,
            f"Derived from incumbent insurer: {insurer}" if insurer else "No prior insurer stated",
        )  # fmt: skip

    zone = case["zone"]
    zone_status = (
        "review_required" if not zone or zone == derivations.ZONE_REVIEW_REQUIRED else "ai_derived"
    )
    rows = [
        proposal,
        GridRow("quotation", "Brokerage %", None, str(case["brokerage_pct"] or "0.00"), "manual",
                "high"),
        GridRow("quotation", "Rater Type", None, case["rater_type"] or "-", "fixed", "high"),
        GridRow("quotation", "Zone", None, zone or derivations.ZONE_REVIEW_REQUIRED, zone_status,
                "high" if zone_status == "ai_derived" else "low"),
    ]  # fmt: skip
    if case["group_size"]:
        rows += [
            GridRow("group_details", "Group Size", None, str(case["group_size"]),
                    "demography_derived", "high"),
            GridRow("group_details", "Number of Primary Members", None,
                    str(case["primary_members_count"]), "demography_derived", "high"),
            GridRow("group_details", "Flagging SME", None, "Yes" if case["sme_flag"] else "No",
                    "demography_derived", "high"),
        ]  # fmt: skip
    else:
        rows += [
            GridRow("group_details", name, None, None, "not_found", "low",
                    reflection_explanation="Demography census not processed yet")
            for name in ("Group Size", "Number of Primary Members", "Flagging SME")
        ]  # fmt: skip
    return rows
