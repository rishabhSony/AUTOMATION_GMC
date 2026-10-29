"""
Deterministic procedure sub-limit matcher (BRD §8, CLAUDE.md invariant 6). The LLM only
locates the raw amount text; cleaning and Option 1–4 matching never involve it.

DB mapping (Backend Schema v4.0): `matched_option` ∈ option_1..option_4 | unmatched, and
`status` (source_status enum) is `rfq_data` for a match, `review_required` otherwise.
API labels: "Matched" / "Unmatched / Review Required" / "Not Found".
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

OPTION_KEYS = ("option_1", "option_2", "option_3", "option_4")
OPTION_LABELS = {
    "option_1": "Option 1",
    "option_2": "Option 2",
    "option_3": "Option 3",
    "option_4": "Option 4",
    "unmatched": "Unmatched",
}
MATCHED, UNMATCHED, NOT_FOUND = "Matched", "Unmatched / Review Required", "Not Found"

# Currency noise: ₹, Rs/Rs./INR, "/-", thousands separators and whitespace.
_NOISE = re.compile(r"₹|\brs\.?|\binr\b|/-|,|\s", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class RegistryRow:
    procedure_name: str
    options: tuple[Decimal, Decimal, Decimal, Decimal]


@dataclass(frozen=True)
class SublimitMatch:
    procedure_name: str
    extracted_amount_raw: str
    cleaned_amount: Decimal | None
    matched_option: str  # option_1..option_4 | unmatched
    status: str  # rfq_data | review_required

    @property
    def match_label(self) -> str:
        return MATCHED if self.matched_option != "unmatched" else UNMATCHED


def clean_amount(raw: str) -> Decimal | None:
    """
    "₹1,20,000/-" → 120000; "Rs. 35,000.00" → 35000. Returns None for anything that isn't
    a plain amount once currency noise is stripped (e.g. "10% of SI", "1.2 lakh",
    "Actuals"), so non-standard clauses stay unmatched.
    """
    stripped = _NOISE.sub("", raw)
    if not _NUMBER.fullmatch(stripped):
        return None
    try:
        return Decimal(stripped).normalize()
    except InvalidOperation:
        return None


def match_sublimit(
    procedure_name: str, raw: str, registry: dict[str, RegistryRow]
) -> SublimitMatch:
    amount = clean_amount(raw)
    row = registry.get(procedure_name)
    option = "unmatched"
    if amount is not None and row is not None:
        # Exact equality only. Where tiers share an amount (e.g. Cholecystectomy Options 3
        # and 4 are both ₹20,000) the lowest option number wins.
        option = next((k for k, v in zip(OPTION_KEYS, row.options, strict=True) if v == amount),
                      "unmatched")  # fmt: skip
    return SublimitMatch(
        procedure_name=procedure_name,
        extracted_amount_raw=raw.strip()[:100],
        cleaned_amount=amount,
        matched_option=option,
        status="rfq_data" if option != "unmatched" else "review_required",
    )
