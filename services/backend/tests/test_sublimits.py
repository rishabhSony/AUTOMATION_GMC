from decimal import Decimal

import pytest

from app.services.sublimits import RegistryRow, clean_amount, match_sublimit

REGISTRY = {
    name: RegistryRow(name, tuple(Decimal(v) for v in options))
    for name, options in {
        "Coronary Artery Bypass Grafting (CABG)": (150000, 120000, 80000, 65000),
        "Appendectomy": (30000, 25000, 20000, 15000),
        "Cholecystectomy": (35000, 25000, 20000, 20000),
        "Cataract (one eye)": (35000, 25000, 20000, 15000),
    }.items()
}
CABG = "Coronary Artery Bypass Grafting (CABG)"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("₹1,20,000", Decimal(120000)),
        ("Rs. 1,20,000/-", Decimal(120000)),
        ("INR 35,000.00", Decimal(35000)),
        ("  80000 ", Decimal(80000)),
        ("10% of SI", None),
        ("1.2 lakh", None),
        ("Actuals", None),
        ("", None),
    ],
)
def test_clean_amount(raw, expected):
    assert clean_amount(raw) == expected


@pytest.mark.parametrize(
    ("procedure", "raw", "option"),
    [
        (CABG, "Rs. 1,50,000.00/-", "option_1"),
        (CABG, "₹1,20,000", "option_2"),  # Plan Phase 5 done criterion
        (CABG, "80,000", "option_3"),
        (CABG, "65000", "option_4"),
        ("Cholecystectomy", "20,000", "option_3"),  # tie between Options 3 and 4
    ],
)
def test_exact_tier_match(procedure, raw, option):
    m = match_sublimit(procedure, raw, REGISTRY)
    assert (m.matched_option, m.status, m.match_label) == (option, "rfq_data", "Matched")


@pytest.mark.parametrize(
    ("procedure", "raw", "cleaned"),
    [
        ("Appendectomy", "Rs. 33,000/-", Decimal(33000)),  # BRD AC-05: unmatched
        (CABG, "1,00,000", Decimal(100000)),  # never rounded to the nearest option
        (CABG, "1,20,000.50", Decimal("120000.5")),
        ("Cataract (one eye)", "10% of SI per eye", None),  # non-standard clause
        ("Unknown Procedure", "20,000", Decimal(20000)),
    ],
)
def test_unmatched_keeps_raw_and_needs_review(procedure, raw, cleaned):
    m = match_sublimit(procedure, raw, REGISTRY)
    assert m.matched_option == "unmatched"
    assert m.status == "review_required"
    assert m.match_label == "Unmatched / Review Required"
    assert m.extracted_amount_raw == raw
    assert m.cleaned_amount == cleaned
