import pytest
from pydantic import ValidationError

from app.services import extractor
from app.services.extractor import Pass1Extraction, assemble_rows, derived_rows
from app.services.field_registry import EXTRACT_FIELDS, PROCEDURES

from .llm_fakes import FIXTURES, fake_client, load_fixture_models

SOURCE = (FIXTURES / "rfq_apex.md").read_text()


@pytest.fixture
def rows():
    pass1, pass2 = load_fixture_models()
    return {r.field_name: r for r in assemble_rows(pass1, pass2, SOURCE)}


def test_schema_parses_fixture_and_rejects_unknown_fields():
    pass1, pass2 = load_fixture_models()
    assert len(pass1.fields) == 18 and len(pass1.sublimits) == 3
    with pytest.raises(ValidationError):
        Pass1Extraction.model_validate(
            {
                "fields": [
                    {"field_name": "Made Up Field", "coverage_details": None,
                     "proposed_details": "x", "verbatim_evidence": None, "source_file": None,
                     "source_page": None}
                ],
                "sublimits": [],
                "unmapped_clauses": [],
            }
        )  # fmt: skip


def test_every_registry_field_gets_exactly_one_row(rows):
    assert set(rows) == {f.name for f in EXTRACT_FIELDS}


def test_current_vs_proposed_and_grounded_status(rows):
    si = rows["Sum Insured (SI)"]
    assert (si.coverage_details, si.proposed_details) == ("3,00,000 floater", "5,00,000 floater")
    assert (si.source_status, si.confidence_rating, si.source_page) == ("rfq_data", "high", "1")


def test_ungrounded_evidence_is_demoted_despite_pass2(rows):
    post = rows["Post-Hospitalization"]  # fixture evidence is not in the RFQ text
    assert (post.source_status, post.confidence_rating) == ("review_required", "low")
    assert "not found" in post.reflection_explanation


def test_pass2_verdicts_map_to_source_status(rows):
    assert rows["District"].source_status == "ambiguous"
    assert rows["Maternity Limit – C-Section Delivery"].source_status == "conflict"


def test_defaults_and_not_found(rows):
    tenure = rows["Policy Tenure"]
    assert (tenure.proposed_details, tenure.source_status) == ("1 Year", "default_data")
    assert rows["Maternity Limit – Normal Delivery"].proposed_details == "50,000"
    assert rows["Balloon Sinuplasty"].source_status == "not_found"


def test_compound_room_rent_split_fallback(rows):
    normal, icu = rows["Room Rent for Normal Room"], rows["Room Rent for ICU & Specialty Rooms"]
    assert (normal.proposed_details, icu.proposed_details) == ("1% of SI", "2% of SI")
    assert normal.source_status == icu.source_status == "ai_derived"


def test_tpa_kept_when_servicing_is_tpa(rows):
    assert rows["TPA Name"].coverage_details == "Medi Assist"
    assert rows["TPA Name"].source_status == "rfq_data"


def test_copay_factor_must_be_percentage():
    pass1, pass2 = load_fixture_models()
    for f in pass1.fields:
        if f.field_name == "Policy Co-Payment Factor":
            f.proposed_details = "Rs. 5,000"
    rows = {r.field_name: r for r in assemble_rows(pass1, pass2, SOURCE)}
    assert rows["Policy Co-Payment Factor"].source_status == "review_required"


def test_derived_rows_proposal_type_zone_and_group(rows):
    case = {"zone": None, "brokerage_pct": None, "rater_type": "-", "group_size": 4,
            "primary_members_count": 2, "sme_flag": True}  # fmt: skip
    derived = {r.field_name: r for r in derived_rows(case, list(rows.values()))}
    assert derived["Type of Proposal"].proposed_details == "Roll Over"  # ICICI incumbent
    assert derived["Zone"].proposed_details == "Review Required"
    assert derived["Flagging SME"].proposed_details == "Yes"
    assert derived["Rater Type"].source_status == "fixed"


def test_single_pass_prompt_and_model_settings():
    client = fake_client()
    outcome = extractor.extract_rfq(SOURCE, PROCEDURES, client=client)
    pass1_call, pass2_call = client.completions.calls
    assert pass1_call["model"] == pass2_call["model"] == "gpt-5.4-mini"
    assert pass1_call["store"] is False  # Zero Data Retention
    assert pass1_call["strict"] is pass2_call["strict"] is True  # OpenAI strict outputs
    # Whole document in one message: no chunking.
    assert SOURCE in pass1_call["messages"][1]["content"]
    assert "Room Rent for ICU & Specialty Rooms" in pass1_call["messages"][1]["content"]
    assert outcome.usage["pass1"] == {"prompt_tokens": 1200, "completion_tokens": 300}
