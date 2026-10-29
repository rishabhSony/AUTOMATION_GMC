"""
GMC RFQ field registry (BRD §6 and §7): the single source for the extraction schema,
Default Data fallbacks, and Quote Review Grid ordering.

Fields that are MANUAL (Brokerage %), FIXED (Rater Type) or DERIVED (Zone, Group
Details, Type of Proposal) are listed with their mode so the grid can show them, but only
EXTRACT fields are requested from the LLM.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Mode(StrEnum):
    EXTRACT = "extract"
    DERIVED = "derived"
    MANUAL = "manual"
    FIXED = "fixed"


@dataclass(frozen=True)
class FieldSpec:
    section: str
    name: str
    mode: Mode = Mode.EXTRACT
    allowed: str = ""  # guidance for the LLM (BRD allowed options / value type)
    default: str | None = None  # BRD "Default / Fallback" → Default Data


_E, _D, _M, _F = Mode.EXTRACT, Mode.DERIVED, Mode.MANUAL, Mode.FIXED

# Room rent is a compound clause: the parent narrative plus the two split limits.
ROOM_RENT_PARENT = "Room Rent (Parent Clause)"
ROOM_RENT_NORMAL = "Room Rent for Normal Room"
ROOM_RENT_ICU = "Room Rent for ICU & Specialty Rooms"
INCUMBENT_INSURER = "Incumbent Insurer"
TYPE_OF_PROPOSAL = "Type of Proposal"
CLAIM_SERVICING = "Claim Servicing"
TPA_NAME = "TPA Name"

FIELDS: list[FieldSpec] = [
    # 6.1 Quotation Details
    FieldSpec("quotation", "Sum Insured (SI)", _E,
              "Currency / tiered list, e.g. 3,00,000; 5,00,000"),
    FieldSpec("quotation", "Policy Tenure", _E, "Duration, e.g. 1 Year", "1 Year"),
    FieldSpec("quotation", "Group Category", _E, "Employer-Employee | Non-Employer-Employee",
              "Employer-Employee"),
    FieldSpec("quotation", INCUMBENT_INSURER, _E,
              "Name of the current/expiring insurer, if the RFQ mentions an existing policy"),
    FieldSpec("quotation", TYPE_OF_PROPOSAL, _D, "New Business | Roll Over | Own Renewal"),
    FieldSpec("quotation", "Brokerage %", _M),
    FieldSpec("quotation", "Premium Payer", _E, "GroupManager | Insured", "GroupManager"),
    FieldSpec("quotation", "Beneficiary", _E, "Employee/Nominee | Corporate Entity",
              "Employee/Nominee"),
    FieldSpec("quotation", "Plan", _E, "Individual | Floater"),
    FieldSpec("quotation", "Rater Type", _F, "", "-"),
    FieldSpec("quotation", "Zone", _D, "Zone A | Zone B | Zone C | Zone D | Pan India"),
    FieldSpec("quotation", "Policy Type", _E,
              "Base IPD | Base OPD | Corporate Buffer | Critical Illness | Dependent Only | "
              "Parental IPD | Parental Top Up | Wellness", "Base IPD"),
    FieldSpec("quotation", CLAIM_SERVICING, _E, "In House | TPA", "In House"),
    FieldSpec("quotation", TPA_NAME, _E, "Third-Party Administrator name when servicing is TPA"),
    # 6.2 Group Policy Holder Details
    FieldSpec("policyholder", "Company Name", _E, "Full legal name of the insured entity"),
    FieldSpec("policyholder", "PIN Code", _E, "6-digit Indian PIN code"),
    FieldSpec("policyholder", "State", _E, "Indian State/UT"),
    FieldSpec("policyholder", "District", _E, "District name"),
    FieldSpec("policyholder", "Client Industry Type", _E,
              "Industry sector, e.g. IT/ITES, Manufacturing, Banking; otherwise Others"),
    # 6.3 Group Details (from the demography engine)
    FieldSpec("group_details", "Group Size", _D),
    FieldSpec("group_details", "Number of Primary Members", _D),
    FieldSpec("group_details", "Flagging SME", _D),
    # 6.4 Medical Expenses Insurance Coverages
    FieldSpec("medical_expenses", "Pre-Existing & Specified Disease (PED)", _E,
              "Covered | Waived Off | Applicable | Not Covered | Not Applicable"),
    FieldSpec("medical_expenses", "Initial Waiting Period", _E,
              "Covered | Waived Off | 15 Days | 30 Days | Applicable | Not Covered"),
    FieldSpec("medical_expenses", ROOM_RENT_PARENT, _E, "Complete room eligibility narrative"),
    FieldSpec("medical_expenses", ROOM_RENT_NORMAL, _E,
              "Normal room limit only, e.g. 1% of SI, 5000/day, No Capping"),
    FieldSpec("medical_expenses", ROOM_RENT_ICU, _E,
              "ICU/ICCU/specialty room limit only, e.g. 2% of SI, 10000/day, No Capping"),
    FieldSpec("medical_expenses", "Road Ambulance", _E, "Amount per event or Actuals"),
    FieldSpec("medical_expenses", "Air Ambulance", _E, "Limit or condition, e.g. Up to 10% of SI"),
    FieldSpec("medical_expenses", "Pre-Hospitalization", _E, "Days: 0 | 15 | 30 | 60 | 90 | 120"),
    FieldSpec("medical_expenses", "Post-Hospitalization", _E,
              "Days: 0 | 30 | 60 | 90 | 120 | 180"),
    FieldSpec("medical_expenses", "Medical Advancement Surgery", _E,
              "Upto 25% SI | Upto 50% SI | Upto SI | Not Covered"),
    FieldSpec("medical_expenses", "Maternity Expenses / Benefits", _E,
              "Covered | Waived Off | Not Covered | Not Applicable"),
    FieldSpec("medical_expenses", "No. of Deliveries / Kids Covered", _E,
              "1 | 2 | 3 | Restricted to 2 Children"),
    FieldSpec("medical_expenses", "Maternity Limit – Normal Delivery", _E, "Currency",
              "50,000"),
    FieldSpec("medical_expenses", "Maternity Limit – C-Section Delivery", _E, "Currency",
              "50,000"),
    FieldSpec("medical_expenses", "Maternity Waiting Period", _E,
              "9 Months Waiting Period | Waived Off | No Waiting Period | Covered"),
    FieldSpec("medical_expenses", "AYUSH Treatment", _E, "Currency limit or Upto SI", "25,000"),
    FieldSpec("medical_expenses", "Co-Payment Type", _E,
              "All Claims | Non-Network Hospitals | Co-pay on Parents Only | Not Applicable"),
    FieldSpec("medical_expenses", "Policy Co-Payment Factor", _E,
              "Percentage only: 0% | 5% | 10% | 15% | 20% | 25% | 30%"),
    FieldSpec("medical_expenses", "Waiver of Cataract Sublimit", _E,
              "Covered | Waived Off | Applicable | Not Covered"),
    FieldSpec("medical_expenses", "Cataract Limit", _E, "Limit per eye or per family"),
    FieldSpec("medical_expenses", "Corporate Buffer", _E, "Total limit and allocation rules"),
    FieldSpec("medical_expenses", "Cover Not Available / UW Referral", _E,
              "Summary of non-standard or risky terms needing underwriter sign-off"),
]  # fmt: skip

_TREATMENT_SECTIONS: dict[str, list[str]] = {
    # 7.1 Modern Treatments
    "modern_treatments": [
        "Uterine Artery Embolization and HIFU",
        "Balloon Sinuplasty",
        "Deep Brain Stimulation",
        "Oral Chemotherapy",
        "Immunotherapy including Monoclonal Antibody Injection",
        "Intravitreal Injections except Lucentis",
        "Intravitreal Injections",
        "Robotic Surgeries",
        "Vaporisation of the Prostate (Green Laser / Holmium Laser)",
        "Bronchial Thermoplasty",
        "Stereotactic Radiosurgery",
        "Intraoperative Neuro Monitoring (IONM)",
        "Stem Cell Therapy / Treatment",
        "Gamma Knife / CyberKnife Surgery",
        "Remicade / Avastin Injection",
        "Biodegradable Stent",
        "Cochlear Implant Treatment",
        "Lucentis Injection",
        "Functional Endoscopic Sinus Surgery (FESS)",
        "Ayurvedic Treatment (Inpatient Modern Administration)",
    ],
    # 7.2 Medical Coverage Scope
    "medical_coverage": [
        "Day Care Expenses / Procedures",
        "Domiciliary Hospitalisation",
        "Dental Treatment",
        "LASIK Surgery / Correction",
        "Refractive Error Correction",
        "Psychiatric Ailments / Mental Illness",
        "Organ Donor Expenses",
        "Covid-19 Treatment",
        "Hospitalisation following Terrorism",
        "Internal Congenital Diseases",
        "External Congenital Diseases",
    ],
    # 7.3 Maternity and Newborn
    "maternity_newborn": [
        "Newborn Baby Coverage",
        "Newborn Baby Cover from Day One within Family Floater SI",
        "Maternity Complication Coverage",
        "Pre and Post Natal Treatment up to Maternity Limit",
        "Twin Delivery / Multiple Birth Benefit",
    ],
    # 7.4 Hospital Expenses & Allowances
    "hospital_expenses": [
        "Anaesthesia Charges",
        "Charges of Surgeon's Own Instruments",
        "Assistant Surgeon / Doctor / Consultant / Attendant Charges",
        "Nursing Allowance",
        "Hospital Cash Benefit",
    ],
    # 7.5 Health and Wellness
    "wellness": [
        "Wellness Programmes",
        "Health Check-Up",
        "Master Health Check-Up for Employees",
        "Health Card Type",
    ],
    # 7.6 General Policy Conditions
    "policy_conditions": [
        "Claim Submission and Intimation Clause",
        "Proportionate Clause",
        "Portability Rights & Continuity Benefit",
        "Terrorism and Epidemic Outbreak Conditions",
        "Correction Endorsements Terms",
        "Special Clause / Bespoke Endorsements",
    ],
}

FIELDS += [
    FieldSpec(section, name, _E, "Coverage status, limit, co-pay % and qualifiers")
    for section, names in _TREATMENT_SECTIONS.items()
    for name in names
]

BY_NAME: dict[str, FieldSpec] = {f.name: f for f in FIELDS}
EXTRACT_FIELDS: list[FieldSpec] = [f for f in FIELDS if f.mode is Mode.EXTRACT]

# Literal used in the strict JSON schema so the model can only name registry fields.
ExtractFieldName = Literal[tuple(f.name for f in EXTRACT_FIELDS)]  # type: ignore[valid-type]

# BRD §8.1 procedure names (identical to sublimit_registry.procedure_name seed values).
PROCEDURES: list[str] = [
    "Coronary Artery Bypass Grafting (CABG)",
    "Valve Replacement",
    "PTCA (per event hospitalisation)",
    "Total Knee Replacement (per event)",
    "Total Hip Replacement",
    "Arthroscopic Surgeries",
    "Cholecystectomy",
    "Kidney Stone Removal (incl. DJ Stent)",
    "Appendectomy",
    "Hysterectomy",
    "Fistulectomy",
    "Septoplasty",
    "Hernia Repair",
    "Haemorrhoidectomy",
    "Tympanoplasty",
    "Arthroscopy",
    "Cataract (one eye)",
    "Tonsillectomy",
    "Dialysis (per session)",
]
ProcedureName = Literal[tuple(PROCEDURES)]  # type: ignore[valid-type]


def registry_prompt() -> str:
    """Compact registry listing for the extraction prompt, grouped by section."""
    lines: list[str] = []
    section = None
    for f in EXTRACT_FIELDS:
        if f.section != section:
            section = f.section
            lines.append(f"\n[{section}]")
        lines.append(f"- {f.name}" + (f": {f.allowed}" if f.allowed else ""))
    return "\n".join(lines).strip()
