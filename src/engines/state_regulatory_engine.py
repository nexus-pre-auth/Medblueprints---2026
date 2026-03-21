"""
State Regulatory Engine
========================
Manages per-state healthcare construction regulations on top of federal baselines.

Each US state may layer additional requirements over federal standards (FGI, NFPA,
ASHRAE, ADA).  This engine:

  1. Loads state-specific rule JSON files from data/regulatory_rules/states/<state_abbr>.json
  2. Merges them with the federal RegulatoryKnowledgeGraph for full compliance stacks
  3. Exposes state-aware rule lookup and feed endpoints so every project knows
     exactly which state's rules apply — powering the "one feed per state" vision

State Authority Hierarchy:
  Federal baseline  (FGI 2022, NFPA 101, ASHRAE 170, ADA)
      ↓ + overrides
  State regulations (OSHPD/CA, DSHS/TX, DOH/NY, AHCA/FL, IDPH/IL, …)
      ↓ + local amendments
  Local AHJ         (Authority Having Jurisdiction)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.models.compliance import RegulatoryRule, RuleSource, ConstraintType

logger = logging.getLogger(__name__)

# Root directory for state-specific rule files
STATE_RULES_DIR = Path(__file__).parent.parent.parent / "data" / "regulatory_rules" / "states"

# Canonical list of all 50 US states + DC
ALL_STATES: Dict[str, str] = {
    "AL": "Alabama",        "AK": "Alaska",         "AZ": "Arizona",
    "AR": "Arkansas",       "CA": "California",     "CO": "Colorado",
    "CT": "Connecticut",    "DE": "Delaware",        "FL": "Florida",
    "GA": "Georgia",        "HI": "Hawaii",          "ID": "Idaho",
    "IL": "Illinois",       "IN": "Indiana",         "IA": "Iowa",
    "KS": "Kansas",         "KY": "Kentucky",        "LA": "Louisiana",
    "ME": "Maine",          "MD": "Maryland",        "MA": "Massachusetts",
    "MI": "Michigan",       "MN": "Minnesota",       "MS": "Mississippi",
    "MO": "Missouri",       "MT": "Montana",         "NE": "Nebraska",
    "NV": "Nevada",         "NH": "New Hampshire",   "NJ": "New Jersey",
    "NM": "New Mexico",     "NY": "New York",        "NC": "North Carolina",
    "ND": "North Dakota",   "OH": "Ohio",            "OK": "Oklahoma",
    "OR": "Oregon",         "PA": "Pennsylvania",    "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota",    "TN": "Tennessee",
    "TX": "Texas",          "UT": "Utah",            "VT": "Vermont",
    "VA": "Virginia",       "WA": "Washington",      "WV": "West Virginia",
    "WI": "Wisconsin",      "WY": "Wyoming",         "DC": "District of Columbia",
}

# Regulatory authority per state (the agency that enforces healthcare construction)
STATE_AUTHORITIES: Dict[str, Dict[str, str]] = {
    "CA": {"agency": "OSHPD", "full_name": "Office of Statewide Health Planning and Development",
           "url": "https://oshpd.ca.gov"},
    "TX": {"agency": "DSHS", "full_name": "Texas Department of State Health Services",
           "url": "https://www.dshs.texas.gov"},
    "NY": {"agency": "NYSDOH", "full_name": "New York State Department of Health",
           "url": "https://www.health.ny.gov"},
    "FL": {"agency": "AHCA", "full_name": "Agency for Health Care Administration",
           "url": "https://ahca.myflorida.com"},
    "IL": {"agency": "IDPH", "full_name": "Illinois Department of Public Health",
           "url": "https://www.dph.illinois.gov"},
    "PA": {"agency": "PA DOH", "full_name": "Pennsylvania Department of Health",
           "url": "https://www.health.pa.gov"},
    "OH": {"agency": "ODH", "full_name": "Ohio Department of Health",
           "url": "https://odh.ohio.gov"},
    "GA": {"agency": "GDCH", "full_name": "Georgia Department of Community Health",
           "url": "https://dch.georgia.gov"},
    "NC": {"agency": "NCDHHS", "full_name": "NC Department of Health and Human Services",
           "url": "https://www.ncdhhs.gov"},
    "MI": {"agency": "LARA", "full_name": "Michigan Dept of Licensing and Regulatory Affairs",
           "url": "https://www.michigan.gov/lara"},
    "NJ": {"agency": "NJDOH", "full_name": "New Jersey Department of Health",
           "url": "https://www.state.nj.us/health"},
    "VA": {"agency": "VDH", "full_name": "Virginia Department of Health",
           "url": "https://www.vdh.virginia.gov"},
    "WA": {"agency": "WSDOH", "full_name": "Washington State Department of Health",
           "url": "https://www.doh.wa.gov"},
    "AZ": {"agency": "ADHS", "full_name": "Arizona Department of Health Services",
           "url": "https://www.azdhs.gov"},
    "TN": {"agency": "TDOH", "full_name": "Tennessee Department of Health",
           "url": "https://www.tn.gov/health"},
    "CO": {"agency": "CDPHE", "full_name": "Colorado Dept of Public Health and Environment",
           "url": "https://cdphe.colorado.gov"},
    "MD": {"agency": "MOSH", "full_name": "Maryland Office of Health Care Quality",
           "url": "https://health.maryland.gov"},
    "MA": {"agency": "MDPH", "full_name": "Massachusetts Department of Public Health",
           "url": "https://www.mass.gov/orgs/department-of-public-health"},
    "MN": {"agency": "MDH", "full_name": "Minnesota Department of Health",
           "url": "https://www.health.state.mn.us"},
    "WI": {"agency": "DHS", "full_name": "Wisconsin Department of Health Services",
           "url": "https://www.dhs.wisconsin.gov"},
}


class StateRegulatoryEngine:
    """
    Loads and serves per-state healthcare construction rules.

    Usage:
        engine = StateRegulatoryEngine()
        rules = engine.get_rules_for_state("CA")
        stack = engine.get_full_compliance_stack("CA")
        feed = engine.get_state_feed_summary("CA")
    """

    def __init__(self, state_rules_dir: Optional[Path] = None):
        self._state_rules_dir = state_rules_dir or STATE_RULES_DIR
        self._state_rules_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, List[RegulatoryRule]] = {}
        self._loaded_states: set[str] = set()
        self._load_all_available_states()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all_available_states(self) -> None:
        for json_file in self._state_rules_dir.glob("*.json"):
            state_abbr = json_file.stem.upper()
            self._load_state_file(state_abbr, json_file)
        logger.info(
            "StateRegulatoryEngine: loaded rules for %d states: %s",
            len(self._loaded_states),
            sorted(self._loaded_states),
        )

    def _load_state_file(self, state_abbr: str, json_file: Path) -> None:
        try:
            raw = json.loads(json_file.read_text())
            rules = [RegulatoryRule(**item) for item in raw]
            self._cache[state_abbr] = rules
            self._loaded_states.add(state_abbr)
        except Exception as exc:
            logger.error("Failed to load state rules %s: %s", json_file, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available_states(self) -> List[str]:
        """States that have rule files loaded."""
        return sorted(self._loaded_states)

    def all_states(self) -> Dict[str, str]:
        """All 50 states + DC with names."""
        return ALL_STATES

    def get_rules_for_state(self, state_abbr: str) -> List[RegulatoryRule]:
        """Return state-specific rules only (not the federal baseline)."""
        return self._cache.get(state_abbr.upper(), [])

    def get_state_authority(self, state_abbr: str) -> Optional[Dict[str, str]]:
        """Return regulatory authority metadata for a state."""
        return STATE_AUTHORITIES.get(state_abbr.upper())

    def get_full_compliance_stack(
        self,
        state_abbr: str,
        federal_rules: Optional[List[RegulatoryRule]] = None,
    ) -> Dict[str, Any]:
        """
        Return the complete compliance rule stack for a state:
          federal_rules (passed in) + state-specific rules

        This is what powers per-state analysis feeding Medblueprints.com.
        """
        state = state_abbr.upper()
        state_rules = self.get_rules_for_state(state)
        federal = federal_rules or []

        return {
            "state": state,
            "state_name": ALL_STATES.get(state, state),
            "authority": self.get_state_authority(state),
            "federal_rule_count": len(federal),
            "state_rule_count": len(state_rules),
            "total_rules": len(federal) + len(state_rules),
            "federal_rules": [r.model_dump() for r in federal],
            "state_rules": [r.model_dump() for r in state_rules],
        }

    def get_state_feed_summary(self, state_abbr: str) -> Dict[str, Any]:
        """
        Lightweight summary for the Medblueprints.com data feed dashboard.
        Shows rule counts by constraint type and source.
        """
        state = state_abbr.upper()
        rules = self.get_rules_for_state(state)
        authority = self.get_state_authority(state)

        by_constraint: Dict[str, int] = {}
        for rule in rules:
            ct = rule.constraint_type.value
            by_constraint[ct] = by_constraint.get(ct, 0) + 1

        by_room: Dict[str, int] = {}
        for rule in rules:
            by_room[rule.room_type] = by_room.get(rule.room_type, 0) + 1

        return {
            "state": state,
            "state_name": ALL_STATES.get(state, state),
            "authority": authority,
            "total_state_rules": len(rules),
            "rules_by_constraint_type": by_constraint,
            "top_room_types_covered": dict(
                sorted(by_room.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "has_data_file": state in self._loaded_states,
            "feed_status": "live" if state in self._loaded_states else "pending_integration",
        }

    def get_national_feed_summary(self) -> Dict[str, Any]:
        """
        Summary across all states — the high-level Medblueprints.com dashboard view.
        Shows which states are live, pending, and total rule coverage.
        """
        live_states = []
        pending_states = []

        for abbr in ALL_STATES:
            if abbr in self._loaded_states:
                rules = self._cache[abbr]
                live_states.append({
                    "state": abbr,
                    "state_name": ALL_STATES[abbr],
                    "rule_count": len(rules),
                    "authority": STATE_AUTHORITIES.get(abbr, {}).get("agency", "State Agency"),
                    "status": "live",
                })
            else:
                pending_states.append({
                    "state": abbr,
                    "state_name": ALL_STATES[abbr],
                    "authority": STATE_AUTHORITIES.get(abbr, {}).get("agency", "State Agency"),
                    "status": "pending_integration",
                })

        total_rules = sum(len(v) for v in self._cache.values())

        return {
            "platform": "MedBlueprints.com",
            "vision": "One regulatory feed per state — all 50 states + DC",
            "total_states": len(ALL_STATES),
            "live_state_count": len(live_states),
            "pending_state_count": len(pending_states),
            "total_state_rules": total_rules,
            "live_states": live_states,
            "pending_states": pending_states,
        }

    def search_rules(
        self,
        state_abbr: str,
        room_type: Optional[str] = None,
        constraint_type: Optional[str] = None,
    ) -> List[RegulatoryRule]:
        """Filter state rules by room type and/or constraint type."""
        rules = self.get_rules_for_state(state_abbr)
        if room_type:
            rules = [r for r in rules if r.room_type.lower() == room_type.lower()]
        if constraint_type:
            rules = [r for r in rules if r.constraint_type.value == constraint_type]
        return rules
