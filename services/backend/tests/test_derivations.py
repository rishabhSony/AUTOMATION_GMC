import pytest

from app.services.derivations import derive_proposal_type, derive_tpa_name, split_room_rent


@pytest.mark.parametrize(
    ("insurer", "expected"),
    [
        ("Bajaj Allianz General Insurance", "Own Renewal"),
        ("BAJAJ ALLIANZ", "Own Renewal"),
        ("ICICI Lombard", "Roll Over"),
        ("Star Health", "Roll Over"),
        (None, "New Business"),
        ("", "New Business"),
        ("N/A", "New Business"),
    ],
)
def test_proposal_type(insurer, expected):
    assert derive_proposal_type(insurer) == expected


def test_tpa_rule():
    assert derive_tpa_name("In House", "Medi Assist") == (
        "In House Administration Team",
        "ai_derived",
    )
    assert derive_tpa_name(None, None)[1] == "ai_derived"  # In House is the BRD default
    assert derive_tpa_name("TPA", "Medi Assist") == ("Medi Assist", "rfq_data")
    assert derive_tpa_name("TPA", None) == (None, "review_required")


@pytest.mark.parametrize(
    ("clause", "normal", "icu"),
    [
        (
            "Room rent is capped at 1% of SI for normal room and 2% of SI for ICU per day.",
            "1% of SI",
            "2% of SI",
        ),
        ("Single private AC room up to Rs. 5,000 per day; ICU Rs. 10,000 per day",
         "Rs. 5,000 per day", "Rs. 10,000 per day"),
        ("ICU charges at actuals, normal room 2% of sum insured", "2% of sum insured", "actuals"),
        ("No capping on room rent", "No capping", None),
        ("Room as per eligibility", None, None),
        (None, None, None),
    ],
)  # fmt: skip
def test_compound_room_rent_split(clause, normal, icu):
    split = split_room_rent(clause)
    assert (split.normal, split.icu) == (normal, icu)
