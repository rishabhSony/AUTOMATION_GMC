"""
Vectorized census standardization engine (BRD §9, Plan Phase 6).

Pipeline: read (CSV/XLSX/XLS, all cells as text) → resolve header aliases → normalize
values → compute ages for the chosen basis date → integrity rules → group metrics.
Every row-level step is a Polars expression; Python loops only run over columns and
rule definitions, never over rows.

Internal relationship values match the Postgres `relationship_type` enum
(`employee`, `spouse`, `child`, `parent`, `parent_in_law`). Display labels
("Employee", "Parent-in-law") are applied only by the 7-column export.
"""

import io
import re
import warnings
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

import polars as pl

SME_PRIMARY_MEMBER_THRESHOLD = 250
DAYS_PER_YEAR = 365.25
AGE_MISMATCH_TOLERANCE_YEARS = 1


class AgeBasisMode(StrEnum):
    CURRENT_DATE = "current_date"
    POLICY_PROPOSAL_START_DATE = "policy_proposal_start_date"


class ExceptionType(StrEnum):
    UNDER18_EMPLOYEE = "under18_employee"
    ORPHAN_DEPENDENT = "orphan_dependent"
    DUPLICATE_MEMBER = "duplicate_member"
    AGE_DOB_MISMATCH = "age_dob_mismatch"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_DOB = "invalid_dob"
    MISSING_AGE_AND_DOB = "missing_age_and_dob"  # BRD §9.3 CRITICAL_ERROR
    UNMAPPED_RELATIONSHIP = "unmapped_relationship"


class CensusFormatError(ValueError):
    """The file can't be read as a census (unsupported type or no usable headers)."""


# ---------------------------------------------------------------------------
# Header alias resolution (BRD §9.1 plus common variants). Order is priority:
# e.g. "Member Name" wins over "Employee Name" when a sheet has both.
# ---------------------------------------------------------------------------

HEADER_ALIASES: dict[str, list[str]] = {
    "employee_code": [
        "empcode", "emp code", "employee code", "emp id", "employee id", "staff id",
        "staff code", "ecode", "employee no", "emp no", "member id", "token no",
        "associate id",
    ],
    "member_name": [
        "member name", "name of insured", "insured name", "beneficiary name", "beneficiary",
        "patient name", "full name", "name", "employee name",
    ],
    "relationship": [
        "relationship", "relation", "rel", "relationship with emp", "dep relationship",
        "dep relation", "family relation", "member type", "category",
    ],
    "dob": [
        "member dob", "date of birth", "dob", "d o b", "birth date", "dob dd mm yyyy",
        "emp dob",
    ],
    "age": ["age", "member age", "completed age", "age in years", "age yrs", "years"],
    "gender": ["gender", "sex", "m f", "male female"],
    "sum_insured": [
        "sum insured", "si", "base si", "si opted", "medical si", "cover",
        "coverage amount", "sum assured",
    ],
}  # fmt: skip

CANONICAL_FIELDS = list(HEADER_ALIASES)
REQUIRED_TEXT_FIELDS = ["employee_code", "member_name", "gender"]

RELATIONSHIP_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(["self", "primary", "employee", "emp", "worker", "e"], "employee"),
    **dict.fromkeys(["spouse", "wife", "husband", "partner", "s"], "spouse"),
    **dict.fromkeys(
        ["child", "children", "son", "daughter", "kid", "dependent child", "dependant child",
         "c"],
        "child",
    ),
    **dict.fromkeys(["parent", "parents", "father", "mother", "p"], "parent"),
    **dict.fromkeys(
        ["parent in law", "parents in law", "father in law", "mother in law", "fil", "mil"],
        "parent_in_law",
    ),
}  # fmt: skip

RELATIONSHIP_LABELS = {
    "employee": "Employee",
    "spouse": "Spouse",
    "child": "Child",
    "parent": "Parent",
    "parent_in_law": "Parent-in-law",
}

GENDER_SYNONYMS = {
    **dict.fromkeys(["m", "male", "man"], "Male"),
    **dict.fromkeys(["f", "female", "woman"], "Female"),
    **dict.fromkeys(["o", "other", "t", "transgender"], "Other"),
}

# Day-first formats are tried before month-first (Indian census convention); MM/DD/YYYY
# only applies when the day-first reading is impossible (e.g. 12/25/1990).
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%m/%d/%Y",
]
EXCEL_EPOCH = date(1899, 12, 30)

SEVEN_COLUMN_ORDER = [
    "Age",
    "Date of Birth",
    "Sum Insured",
    "Relationship",
    "Name",
    "EmpCode",
    "Gender",
]


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def resolve_headers(columns: list[str]) -> dict[str, str]:
    """Maps canonical field → source column, each source column used at most once."""
    normalized = {col: normalize_header(col) for col in columns}
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            match = next((c for c in columns if c not in used and normalized[c] == alias), None)
            if match is not None:
                mapping[canonical] = match
                used.add(match)
                break
    return mapping


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def read_census(stream: io.BytesIO, filename: str) -> pl.DataFrame:
    """Reads the first sheet / CSV with every cell as text (no type guessing)."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "csv":
        df = pl.read_csv(stream, infer_schema=False, truncate_ragged_lines=True)
    elif ext in {"xlsx", "xlsm", "xls", "xlsb", "ods"}:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)  # polars↔fastexcel arrow notice
            df = pl.read_excel(stream, engine="calamine", infer_schema_length=0)
    else:
        raise CensusFormatError(f"Unsupported census file type: .{ext or '?'}")
    return df.select(pl.all().cast(pl.String))


# ---------------------------------------------------------------------------
# Value normalization expressions
# ---------------------------------------------------------------------------


def _clean_text(col: str) -> pl.Expr:
    cleaned = pl.col(col).str.strip_chars().str.replace_all(r"\s+", " ")
    return pl.when(cleaned == "").then(None).otherwise(cleaned)


def _parse_date(col: str) -> pl.Expr:
    text = pl.col(col).str.strip_chars()
    candidates = [text.str.to_date(fmt, strict=False) for fmt in DATE_FORMATS]
    # calamine renders native Excel dates as "YYYY-MM-DD HH:MM:SS"
    candidates.insert(0, text.str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).dt.date())
    serial = text.str.extract(r"^(\d{4,5})(?:\.0+)?$").cast(pl.Int64, strict=False)
    candidates.append(
        pl.when(serial.is_between(1, 60000))
        .then(pl.lit(EXCEL_EPOCH) + pl.duration(days=serial))
        .otherwise(None)
    )
    return pl.coalesce(candidates)


def _parse_int(col: str) -> pl.Expr:
    return (
        pl.col(col)
        .str.strip_chars()
        .str.extract(r"^(\d{1,3})(?:\.0+)?$")
        .cast(pl.Int32, strict=False)
    )


def _parse_amount(col: str) -> pl.Expr:
    digits = (
        pl.col(col).str.to_lowercase().str.replace_all(r"₹|rs\.?|inr|/-|,|\s", "").str.strip_chars()
    )
    return digits.cast(pl.Float64, strict=False)


def _map_values(col: str, synonyms: dict[str, str]) -> pl.Expr:
    key = pl.col(col).str.to_lowercase().str.replace_all(r"[-_./]+", " ").str.strip_chars()
    key = key.str.replace_all(r"\s+", " ")
    return key.replace_strict(synonyms, default=None, return_dtype=pl.String)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class DemographyMetrics:
    group_size: int
    primary_members_count: int
    sme_flag: bool


@dataclass
class DemographyResult:
    records: pl.DataFrame  # storable rows, canonical columns + flags
    exceptions: pl.DataFrame  # source_row_number, exception_type, severity, error_message
    metrics: DemographyMetrics
    header_mapping: dict[str, str]
    unmapped_columns: list[str] = field(default_factory=list)


def standardize(raw: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, str], list[str]]:
    """Raw text frame → canonical columns. Missing source columns become all-null."""
    mapping = resolve_headers(raw.columns)
    if "relationship" not in mapping or not ({"dob", "age"} & mapping.keys()):
        raise CensusFormatError(
            "Census needs a relationship column and a date-of-birth or age column; "
            f"recognized headers: {sorted(mapping) or 'none'}"
        )
    unmapped = [c for c in raw.columns if c not in mapping.values()]

    renamed = raw.select(
        [pl.col(src).cast(pl.String).alias(canonical) for canonical, src in mapping.items()]
        + [pl.lit(None, pl.String).alias(c) for c in CANONICAL_FIELDS if c not in mapping]
    )
    # Header is spreadsheet row 1, so data rows start at 2.
    df = renamed.with_row_index("source_row_number", offset=2).with_columns(
        pl.col("source_row_number").cast(pl.Int32)
    )
    # Drop rows with no content at all (trailing blanks in spreadsheets).
    df = df.filter(pl.any_horizontal(pl.col(CANONICAL_FIELDS).str.strip_chars() != ""))

    df = df.with_columns(
        _clean_text("employee_code").str.replace(r"\.0+$", "").alias("employee_code"),
        _clean_text("member_name").alias("member_name"),
        _clean_text("relationship").alias("relationship_raw"),
        _map_values("relationship", RELATIONSHIP_SYNONYMS).alias("relationship"),
        _clean_text("gender").alias("gender_raw"),
        _map_values("gender", GENDER_SYNONYMS).alias("gender"),
        _clean_text("dob").alias("dob_raw"),
        _parse_date("dob").alias("dob"),
        _parse_int("age").alias("source_age_raw"),
        _parse_amount("sum_insured").alias("sum_insured"),
    ).drop("age")
    return df, mapping, unmapped


def apply_ages(df: pl.DataFrame, basis_date: date) -> pl.DataFrame:
    """
    Recomputes `calculated_age` and the age-dependent flags for a basis date.
    Age = ⌊(Basis Date − DOB) / 365.25⌋, falling back to the source age when DOB is
    missing, unparseable, or after the basis date. Cheap enough to rerun on toggle.
    """
    dob_valid = pl.col("dob").is_not_null() & (pl.col("dob") <= pl.lit(basis_date))
    dob_age = ((pl.lit(basis_date) - pl.col("dob")).dt.total_days() / DAYS_PER_YEAR).floor()
    return df.with_columns(
        pl.when(dob_valid)
        .then(dob_age.cast(pl.Int32))
        .otherwise(pl.col("source_age_raw"))
        .alias("calculated_age"),
        (pl.col("dob_raw").is_not_null() & ~dob_valid).alias("_invalid_dob"),
        (
            dob_valid
            & pl.col("source_age_raw").is_not_null()
            & ((dob_age - pl.col("source_age_raw")).abs() > AGE_MISMATCH_TOLERANCE_YEARS)
        ).alias("_age_dob_mismatch"),
    ).with_columns(
        ((pl.col("relationship") == "employee") & (pl.col("calculated_age") < 18)).alias(
            "is_under18_employee"
        ),
    )


def _apply_integrity_flags(df: pl.DataFrame) -> pl.DataFrame:
    storable = pl.col("relationship").is_not_null() & pl.col("calculated_age").is_not_null()
    df = df.with_columns(storable.alias("_storable"))

    employee_codes = df.filter(pl.col("_storable") & (pl.col("relationship") == "employee"))[
        "employee_code"
    ].drop_nulls()

    dup_key = [
        pl.col("employee_code").str.to_uppercase(),
        pl.col("member_name").str.to_lowercase(),
        pl.col("relationship"),
    ]
    return df.with_columns(
        (
            pl.col("_storable")
            & (pl.col("relationship") != "employee")
            & ~pl.col("employee_code").is_in(employee_codes.implode()).fill_null(False)
        ).alias("is_orphan_dependent"),
        (
            pl.col("_storable")
            & (pl.len().over(dup_key) > 1)
            & pl.all_horizontal(pl.col("employee_code", "member_name").is_not_null())
        ).alias("is_duplicate_record"),
        pl.any_horizontal(pl.col(REQUIRED_TEXT_FIELDS).is_null()).alias("_missing_required"),
    )


def _build_exceptions(df: pl.DataFrame) -> pl.DataFrame:
    row = pl.col("source_row_number").cast(pl.String)
    missing_list = pl.concat_str(
        [
            pl.when(pl.col(f).is_null()).then(pl.lit(f)).otherwise(None)
            for f in REQUIRED_TEXT_FIELDS
        ],
        separator=", ",
        ignore_nulls=True,
    )
    rules: list[tuple[pl.Expr, ExceptionType, str, pl.Expr]] = [
        (
            pl.col("calculated_age").is_null(),
            ExceptionType.MISSING_AGE_AND_DOB,
            "critical",
            pl.format("Row {}: CRITICAL_ERROR: Missing Age and DOB", row),
        ),
        (
            pl.col("relationship").is_null(),
            ExceptionType.UNMAPPED_RELATIONSHIP,
            "critical",
            pl.format(
                "Row {}: relationship '{}' is not a recognized category",
                row,
                pl.col("relationship_raw").fill_null("<blank>"),
            ),
        ),
        (
            pl.col("_storable") & pl.col("is_under18_employee"),
            ExceptionType.UNDER18_EMPLOYEE,
            "warning",
            pl.format("Row {}: employee aged {} is under 18", row, pl.col("calculated_age")),
        ),
        (
            pl.col("is_orphan_dependent"),
            ExceptionType.ORPHAN_DEPENDENT,
            "warning",
            pl.format(
                "Row {}: dependant has no primary employee with EmpCode '{}'",
                row,
                pl.col("employee_code").fill_null("<blank>"),
            ),
        ),
        (
            pl.col("is_duplicate_record"),
            ExceptionType.DUPLICATE_MEMBER,
            "warning",
            pl.format("Row {}: duplicate EmpCode + Name + Relationship", row),
        ),
        (
            pl.col("_storable") & pl.col("_age_dob_mismatch"),
            ExceptionType.AGE_DOB_MISMATCH,
            "warning",
            pl.format(
                "Row {}: source age {} differs from DOB age {} by more than 1 year",
                row,
                pl.col("source_age_raw"),
                pl.col("calculated_age"),
            ),
        ),
        (
            pl.col("_storable") & pl.col("_invalid_dob"),
            ExceptionType.INVALID_DOB,
            "warning",
            pl.format("Row {}: date of birth '{}' is invalid; source age used", row,
                      pl.col("dob_raw")),
        ),
        (
            pl.col("_storable") & pl.col("_missing_required"),
            ExceptionType.MISSING_REQUIRED_FIELD,
            "warning",
            pl.format("Row {}: missing {}", row, missing_list),
        ),
    ]  # fmt: skip
    return pl.concat(
        [
            df.filter(cond).select(
                "source_row_number",
                pl.lit(str(kind)).alias("exception_type"),
                pl.lit(severity).alias("severity"),
                message.alias("error_message"),
            )
            for cond, kind, severity, message in rules
        ]
    ).sort("source_row_number", maintain_order=True)


def process_census(raw: pl.DataFrame, basis_date: date) -> DemographyResult:
    df, mapping, unmapped = standardize(raw)
    df = _apply_integrity_flags(apply_ages(df, basis_date))
    exceptions = _build_exceptions(df)

    flagged_rows = exceptions["source_row_number"].unique().implode()
    records = (
        df.filter(pl.col("_storable"))
        .with_columns(
            pl.col("source_row_number").is_in(flagged_rows).alias("has_validation_exception")
        )
        .select(
            "source_row_number",
            "calculated_age",
            "dob",
            "sum_insured",
            "relationship",
            pl.col("member_name").fill_null(""),
            pl.col("employee_code").fill_null(""),
            pl.col("gender").fill_null(pl.col("gender_raw")).fill_null(""),
            "source_age_raw",
            "is_under18_employee",
            "is_orphan_dependent",
            "is_duplicate_record",
            "has_validation_exception",
        )
    )
    primary = records.filter(pl.col("relationship") == "employee").height
    metrics = DemographyMetrics(
        group_size=records.height,
        primary_members_count=primary,
        sme_flag=primary <= SME_PRIMARY_MEMBER_THRESHOLD,
    )
    return DemographyResult(records, exceptions, metrics, mapping, unmapped)


def resolve_basis_date(mode: AgeBasisMode, proposal_start_date: date | None) -> date:
    if mode is AgeBasisMode.POLICY_PROPOSAL_START_DATE:
        if proposal_start_date is None:
            raise ValueError("Policy Proposal Start Date basis needs a proposal start date")
        return proposal_start_date
    return date.today()


# ---------------------------------------------------------------------------
# Strict 7-column export (BRD §9.2 / FR-13)
# ---------------------------------------------------------------------------


def to_seven_column(records: pl.DataFrame) -> pl.DataFrame:
    return records.sort("source_row_number").select(
        pl.col("calculated_age").alias("Age"),
        pl.col("dob").dt.strftime("%d-%m-%Y").alias("Date of Birth"),
        pl.col("sum_insured").alias("Sum Insured"),
        pl.col("relationship").replace_strict(RELATIONSHIP_LABELS).alias("Relationship"),
        pl.col("member_name").alias("Name"),
        pl.col("employee_code").alias("EmpCode"),
        pl.col("gender").alias("Gender"),
    )


def seven_column_excel_bytes(records: pl.DataFrame) -> bytes:
    out = io.BytesIO()
    to_seven_column(records).write_excel(out, worksheet="Demography", autofit=True)
    return out.getvalue()
