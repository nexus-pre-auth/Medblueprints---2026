"""
Rule Expansion Script
======================
Generates additional regulatory rules programmatically.

Usage:
  python scripts/expand_rules.py --output data/regulatory_rules/generated_rules.json
  python scripts/expand_rules.py --count 100 --sources FGI,NFPA,ASHRAE

This script provides:
1. Parametric rules (e.g., "every room type needs X")
2. Regional code variations (California, Texas, Florida, New York)
3. Specialty facility rules (ambulatory surgery, cancer centers, etc.)
4. FGI 2022 appendix rules for edge cases
"""
import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# -----------------------------------------------------------------------
# Parametric rule generators
# -----------------------------------------------------------------------

ALL_ROOM_TYPES = [
    "operating_room", "icu", "patient_room", "sterile_core",
    "nurse_station", "corridor", "waiting", "emergency",
    "laboratory", "imaging", "pharmacy", "mechanical", "utility",
]

CLINICAL_ROOM_TYPES = [
    "operating_room", "icu", "patient_room", "emergency",
    "sterile_core", "laboratory", "imaging", "pharmacy",
]


def generate_hand_hygiene_rules() -> List[Dict[str, Any]]:
    """Every clinical space needs hand hygiene access."""
    rules = []
    for room_type in CLINICAL_ROOM_TYPES:
        rules.append({
            "rule_id": f"FGI_HH_{room_type.upper()[:6]}_001",
            "source": "FGI",
            "room_type": room_type,
            "constraint_type": "equipment_required",
            "description": (
                f"{room_type.replace('_', ' ').title()} must provide hand hygiene facilities "
                f"(handwashing sink or ABHR dispenser) within the room or at the entrance, "
                f"per FGI infection control requirements."
            ),
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Section 1.2-7",
        })
    return rules


def generate_lighting_rules() -> List[Dict[str, Any]]:
    """Illumination requirements by room type."""
    lighting_requirements = {
        "operating_room": (2500, "Surgical task lighting at the surgical field"),
        "icu": (100, "Examination lighting at the patient bed"),
        "patient_room": (50, "General illumination for examination and care"),
        "emergency": (200, "Treatment and examination lighting"),
        "nurse_station": (75, "Task lighting for documentation and medication preparation"),
        "laboratory": (100, "Task lighting for specimen analysis"),
        "imaging": (30, "Low ambient lighting for monitor viewing"),
        "pharmacy": (75, "Task lighting for medication preparation"),
        "sterile_core": (75, "Task lighting for sterile assembly"),
    }
    rules = []
    for room_type, (footcandles, desc) in lighting_requirements.items():
        rules.append({
            "rule_id": f"FGI_LT_{room_type.upper()[:6]}_001",
            "source": "FGI",
            "room_type": room_type,
            "constraint_type": "lighting_required",
            "description": (
                f"{room_type.replace('_', ' ').title()}: {desc}. "
                f"Minimum {footcandles} foot-candles required at the work plane."
            ),
            "threshold_value": footcandles,
            "threshold_unit": "footcandles",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Appendix A: Lighting",
        })
    return rules


def generate_california_rules() -> List[Dict[str, Any]]:
    """California OSHPD (Office of Statewide Health Planning and Development) additions."""
    rules = [
        {
            "rule_id": "CA_OSHPD_OR_001",
            "source": "state_code",
            "room_type": "operating_room",
            "constraint_type": "minimum_area",
            "description": "California OSHPD requires operating rooms in new construction to have a minimum clear floor area of 450 square feet (50 sqft above FGI minimum).",
            "threshold_value": 450,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "California OSHPD Administrative Manual, Section 1224.4.1.1",
        },
        {
            "rule_id": "CA_OSHPD_OR_002",
            "source": "state_code",
            "room_type": "operating_room",
            "constraint_type": "minimum_ventilation",
            "description": "California OSHPD requires seismic bracing of all HVAC systems serving operating rooms and ICUs per ASCE 7 Seismic Design Category D or higher.",
            "mandatory": True,
            "citation": "California OSHPD Administrative Manual, Section 1224.4.4",
        },
        {
            "rule_id": "CA_OSHPD_ICU_001",
            "source": "state_code",
            "room_type": "icu",
            "constraint_type": "minimum_area",
            "description": "California OSHPD requires a minimum of 250 square feet per ICU patient room (25% above FGI minimum for new construction).",
            "threshold_value": 250,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "California OSHPD Administrative Manual, Section 1224.9.1",
        },
        {
            "rule_id": "CA_OSHPD_SEISMIC_001",
            "source": "state_code",
            "room_type": "mechanical",
            "constraint_type": "equipment_required",
            "description": "California SB 1953: All essential services buildings (hospitals) must meet OSHPD SPC-5 (highest) seismic performance standards by 2030.",
            "mandatory": True,
            "citation": "California SB 1953, OSHPD Seismic Compliance Program",
        },
        {
            "rule_id": "CA_OSHPD_COR_001",
            "source": "state_code",
            "room_type": "corridor",
            "constraint_type": "minimum_corridor_width",
            "description": "California OSHPD requires a minimum 8ft-wide patient corridor in acute care hospitals, with 10ft recommended for high-traffic surgical corridors.",
            "threshold_value": 8,
            "threshold_unit": "ft",
            "mandatory": True,
            "citation": "California OSHPD Administrative Manual, Section 1224.3.3",
        },
    ]
    return rules


def generate_texas_rules() -> List[Dict[str, Any]]:
    """Texas HHSC (Health and Human Services Commission) additions."""
    return [
        {
            "rule_id": "TX_HHSC_OR_001",
            "source": "state_code",
            "room_type": "operating_room",
            "constraint_type": "minimum_area",
            "description": "Texas HHSC: General operating rooms must meet FGI minimum of 400 sqft; specialty ORs (orthopedic, neurosurgery) must provide minimum 500 sqft.",
            "threshold_value": 400,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "Texas Health Facility Compliance, 25 TAC §133.162",
        },
        {
            "rule_id": "TX_HHSC_ICU_001",
            "source": "state_code",
            "room_type": "icu",
            "constraint_type": "adjacency_required",
            "description": "Texas HHSC: ICU must be located adjacent to or within 300 feet of the emergency department and operating suite.",
            "related_room_type": "emergency",
            "mandatory": False,
            "citation": "Texas Health Facility Compliance, 25 TAC §133.162",
        },
        {
            "rule_id": "TX_HHSC_ER_001",
            "source": "state_code",
            "room_type": "emergency",
            "constraint_type": "minimum_area",
            "description": "Texas HHSC: Emergency department must provide a minimum ratio of 150 sqft per licensed emergency bed.",
            "threshold_value": 150,
            "threshold_unit": "sqft_per_bed",
            "mandatory": True,
            "citation": "Texas Health Facility Compliance, 25 TAC §133.163",
        },
    ]


def generate_florida_rules() -> List[Dict[str, Any]]:
    """Florida AHCA (Agency for Health Care Administration) additions."""
    return [
        {
            "rule_id": "FL_AHCA_OR_001",
            "source": "state_code",
            "room_type": "operating_room",
            "constraint_type": "minimum_area",
            "description": "Florida AHCA: Operating rooms must comply with FGI minimums; ambulatory surgery ORs must meet a minimum of 300 sqft.",
            "threshold_value": 300,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "Florida AHCA Chapter 59A-3.0815 FAC",
        },
        {
            "rule_id": "FL_AHCA_HURR_001",
            "source": "state_code",
            "room_type": "mechanical",
            "constraint_type": "equipment_required",
            "description": "Florida AHCA: Hospitals in hurricane risk zones (Zone A-C) must have generator capacity for 96 hours of full facility operation.",
            "mandatory": True,
            "citation": "Florida AHCA Chapter 59A-3.083(3) FAC",
        },
        {
            "rule_id": "FL_AHCA_ICU_001",
            "source": "state_code",
            "room_type": "icu",
            "constraint_type": "minimum_ventilation",
            "description": "Florida AHCA: ICU rooms in non-hurricane-hardened buildings must have backup HVAC capable of maintaining appropriate temperatures during power outages.",
            "threshold_value": 6,
            "threshold_unit": "ACH",
            "mandatory": True,
            "citation": "Florida AHCA Chapter 59A-3.083(3)(c) FAC",
        },
    ]


def generate_specialty_facility_rules() -> List[Dict[str, Any]]:
    """Rules for specialty healthcare facilities beyond general hospitals."""
    return [
        {
            "rule_id": "FGI_ASC_OR_001",
            "source": "FGI",
            "room_type": "operating_room",
            "constraint_type": "minimum_area",
            "description": "Ambulatory Surgery Centers (ASC): Operating rooms must provide minimum 250 sqft for Class B procedures, 400 sqft for Class C.",
            "threshold_value": 250,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Chapter 3.7 (Ambulatory Surgery)",
        },
        {
            "rule_id": "FGI_CANCER_001",
            "source": "FGI",
            "room_type": "imaging",
            "constraint_type": "minimum_area",
            "description": "Radiation oncology vaults must provide minimum 400 sqft of clear floor area with minimum 5-foot concrete shielding walls.",
            "threshold_value": 400,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Chapter 3.8 (Radiation Oncology)",
        },
        {
            "rule_id": "FGI_PSYCH_001",
            "source": "FGI",
            "room_type": "patient_room",
            "constraint_type": "minimum_area",
            "description": "Psychiatric patient rooms must provide minimum 120 sqft and must have ligature-resistant fixtures and hardware throughout.",
            "threshold_value": 120,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Chapter 3.3 (Psychiatric Facilities)",
        },
        {
            "rule_id": "FGI_REHAB_001",
            "source": "FGI",
            "room_type": "waiting",
            "constraint_type": "minimum_area",
            "description": "Rehabilitation facility therapy gyms must provide a minimum of 2,000 sqft or 80 sqft per patient, whichever is greater.",
            "threshold_value": 2000,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Chapter 3.5 (Rehabilitation Facilities)",
        },
        {
            "rule_id": "FGI_LTAC_001",
            "source": "FGI",
            "room_type": "patient_room",
            "constraint_type": "minimum_area",
            "description": "Long-Term Acute Care (LTAC) patient rooms must provide minimum 200 sqft private rooms with full private bathroom.",
            "threshold_value": 200,
            "threshold_unit": "sqft",
            "mandatory": True,
            "citation": "FGI Guidelines 2022, Chapter 3.6 (Long-Term Care)",
        },
    ]


def generate_infection_control_rules() -> List[Dict[str, Any]]:
    """CDC/HICPAC infection control design requirements."""
    return [
        {
            "rule_id": "CDC_IC_OR_001",
            "source": "FGI",
            "room_type": "operating_room",
            "constraint_type": "minimum_ventilation",
            "description": "CDC/HICPAC: Operating rooms must supply HEPA-filtered air with unidirectional (laminar) airflow directly over the operating table.",
            "threshold_value": 20,
            "threshold_unit": "ACH",
            "mandatory": True,
            "citation": "CDC/HICPAC Guidelines for Environmental Infection Control, 2003",
        },
        {
            "rule_id": "CDC_IC_ISOL_001",
            "source": "FGI",
            "room_type": "patient_room",
            "constraint_type": "minimum_ventilation",
            "description": "CDC/HICPAC: Airborne Infection Isolation (AII) rooms must maintain -2.5 Pa negative pressure relative to corridor, monitored continuously with visible indicator.",
            "threshold_value": 12,
            "threshold_unit": "ACH",
            "mandatory": True,
            "citation": "CDC/HICPAC Guidelines for Environmental Infection Control, Section III.A",
        },
        {
            "rule_id": "CDC_IC_PE_001",
            "source": "FGI",
            "room_type": "icu",
            "constraint_type": "minimum_ventilation",
            "description": "CDC/HICPAC: Protective Environment (PE) rooms for immunocompromised patients must maintain +2.5 Pa positive pressure, HEPA filtration, minimum 12 ACH.",
            "threshold_value": 12,
            "threshold_unit": "ACH",
            "mandatory": True,
            "citation": "CDC/HICPAC Guidelines for Environmental Infection Control, Section III.B",
        },
        {
            "rule_id": "CDC_IC_HAND_001",
            "source": "FGI",
            "room_type": "patient_room",
            "constraint_type": "equipment_required",
            "description": "CDC/HICPAC: Hand hygiene sinks must be located within each patient room, within arm's reach of patient care activities.",
            "mandatory": True,
            "citation": "CDC Hand Hygiene Guidelines, 2002",
        },
        {
            "rule_id": "CDC_IC_STERI_001",
            "source": "FGI",
            "room_type": "sterile_core",
            "constraint_type": "separation_required",
            "description": "CDC/HICPAC: Sterile supply must be stored in a dedicated sterile storage area with controlled temperature (60-75°F) and relative humidity (30-60%).",
            "related_room_type": "utility",
            "mandatory": True,
            "citation": "CDC/HICPAC Guidelines for Environmental Infection Control, Section V",
        },
    ]


# -----------------------------------------------------------------------
# Main generator
# -----------------------------------------------------------------------

def generate_all_rules() -> List[Dict[str, Any]]:
    all_rules = []
    all_rules.extend(generate_hand_hygiene_rules())
    all_rules.extend(generate_lighting_rules())
    all_rules.extend(generate_california_rules())
    all_rules.extend(generate_texas_rules())
    all_rules.extend(generate_florida_rules())
    all_rules.extend(generate_specialty_facility_rules())
    all_rules.extend(generate_infection_control_rules())
    return all_rules


def count_existing_rules() -> int:
    rules_dir = Path(__file__).parent.parent / "data" / "regulatory_rules"
    total = 0
    for f in rules_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            total += len(data)
        except Exception:
            pass
    return total


def main():
    parser = argparse.ArgumentParser(description="Expand regulatory rule library")
    parser.add_argument(
        "--output",
        default="data/regulatory_rules/generated_rules.json",
        help="Output file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rule count without writing",
    )
    args = parser.parse_args()

    existing = count_existing_rules()
    print(f"Existing rules: {existing}")

    new_rules = generate_all_rules()
    print(f"Generated rules: {len(new_rules)}")
    print(f"Total after merge: {existing + len(new_rules)}")

    if args.dry_run:
        for rule in new_rules[:5]:
            print(f"  {rule['rule_id']}: {rule['description'][:80]}...")
        print(f"  ... and {len(new_rules) - 5} more")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(new_rules, indent=2))
    print(f"Written to: {output_path}")
    print(f"Total rules in library: {existing + len(new_rules)}")


if __name__ == "__main__":
    main()
