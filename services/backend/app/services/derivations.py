"""
Deterministic business rules (BRD §6): proposal type, TPA conditional, Default Data,
room-rent clause splitting fallback, and PINCODE/District → Zone resolution.
"""

import re
from dataclasses import dataclass

import psycopg

ZONE_REVIEW_REQUIRED = "Review Required"  # zone_master has no mapping (yet) for the location
PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")


def derive_proposal_type(incumbent_insurer: str | None) -> str:
    """BRD §6.1: Bajaj incumbent → Own Renewal; any other incumbent → Roll Over; none → New."""
    insurer = (incumbent_insurer or "").strip()
    if not insurer or insurer.lower() in {"none", "n/a", "na", "not applicable", "nil"}:
        return "New Business"
    return "Own Renewal" if "bajaj" in insurer.lower() else "Roll Over"


def derive_tpa_name(
    claim_servicing: str | None, extracted_tpa: str | None
) -> tuple[str | None, str]:
    """BRD §6.1 TPA conditional. Returns (value, source_status)."""
    servicing = (claim_servicing or "In House").strip().lower()
    if servicing.startswith("in house") or servicing.startswith("in-house"):
        return "In House Administration Team", "ai_derived"
    if extracted_tpa and extracted_tpa.strip():
        return extracted_tpa.strip(), "rfq_data"
    return None, "review_required"


# ---------------------------------------------------------------------------
# Compound room-rent clause splitter (fallback when Pass 1 leaves a split field empty)
# ---------------------------------------------------------------------------

_LIMIT = re.compile(
    r"(?:\d+(?:\.\d+)?\s*%\s*of\s*(?:the\s*)?(?:sum\s*insured|si))"
    r"|(?:(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d+)?(?:\s*/-)?(?:\s*(?:per\s*day|/\s*day|p\.?d\.?))?)"
    r"|(?:[\d,]{3,}(?:\s*/-)?\s*(?:per\s*day|/\s*day))"
    r"|(?:no\s*(?:capping|cap|limit|sub-?limit))|(?:actuals?)",
    re.IGNORECASE,
)
_ICU = re.compile(r"\b(icu|iccu|nicu|intensive|critical care|specialty|speciality)\b", re.I)
_NORMAL = re.compile(
    r"\b(normal|single|private|general|standard|semi[- ]private|room rent)\b", re.I
)


@dataclass
class RoomRentSplit:
    normal: str | None
    icu: str | None


def split_room_rent(clause: str | None) -> RoomRentSplit:
    """
    "Room rent capped at 1% of SI for normal room and 2% of SI for ICU" →
    normal="1% of SI", icu="2% of SI". Splits on clause separators, then assigns each
    limit to the segment that names ICU or a normal room.
    """
    if not clause:
        return RoomRentSplit(None, None)
    normal = icu = None
    for segment in re.split(r";|\band\b|,(?=\s*(?:for|icu|iccu|normal))|\n", clause, flags=re.I):
        limit = _LIMIT.search(segment)
        if not limit:
            continue
        value = re.sub(r"\s+", " ", limit.group(0)).strip()
        if _ICU.search(segment):
            icu = icu or value
        elif _NORMAL.search(segment) or normal is None:
            normal = normal or value
    return RoomRentSplit(normal, icu)


# ---------------------------------------------------------------------------
# Zone resolution (zone_master; empty until Underwriting Ops sign-off, BRD §10)
# ---------------------------------------------------------------------------


def resolve_zone(
    conn: psycopg.Connection, pincode: str | None, state: str | None, district: str | None
) -> tuple[str, str]:
    """Returns (zone, matched_by) where matched_by ∈ pincode | district | none."""
    if pincode:
        row = conn.execute(
            "select zone::text from zone_master where pincode = %s", (pincode,)
        ).fetchone()
        if row:
            return row["zone"], "pincode"
    if state and district:
        row = conn.execute(
            "select zone::text from zone_master where pincode is null"
            " and lower(state) = lower(%s) and lower(district) = lower(%s) limit 1",
            (state.strip(), district.strip()),
        ).fetchone()
        if row:
            return row["zone"], "district"
    return ZONE_REVIEW_REQUIRED, "none"
