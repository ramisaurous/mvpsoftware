from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import select

from app.core.db import get_session


@dataclass
class TriageHit:
    rule_id: str
    name: str
    score: float
    likely_causes: list[str]
    checks: list[str]
    matched: list[str]


# ----------------------------
# Fallback rules (no DB needed)
# ----------------------------

_FALLBACK_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "fallback_stalls_at_stop",
        "name": "Stalls at stop / dies when braking to a stop",
        "keywords": [
            "stalls at stop",
            "stall at stop",
            "dies at stop",
            "dies when braking",
            "cuts off at stop",
            "stalls when braking to a stop",
        ],
        "dtc_prefixes": ["P017", "P010", "P049", "P050"],
        "likely_causes": [
            "Vacuum leak / unmetered air",
            "Throttle body deposits / idle airflow issue",
            "EVAP purge valve stuck open",
            "MAF contamination / skewed airflow reading",
            "Brake booster vacuum leak",
        ],
        "checks": [
            "Scan STFT/LTFT at idle and during decel to stop; look for large trim swings.",
            "Inspect for intake/vacuum leaks and brake booster leak.",
            "Inspect/clean throttle body; verify idle airflow behavior.",
            "Check EVAP purge valve for stuck-open condition.",
            "Inspect/clean MAF and verify ducting is sealed.",
        ],
        "base_weight": 1.35,
    },
    {
        "rule_id": "fallback_misfire_rough_idle",
        "name": "Misfire / rough idle",
        "keywords": ["rough idle", "misfire", "stumble", "hesitation", "shaking at idle"],
        "dtc_prefixes": ["P030", "P017", "P010", "P011"],
        "likely_causes": [
            "Ignition: plugs/coils",
            "Vacuum leak / unmetered air",
            "MAF contamination",
            "Fuel trim issue / weak fuel delivery",
        ],
        "checks": [
            "Scan fuel trims STFT/LTFT at idle and 2500 RPM; look for big delta (vacuum leak signature).",
            "Check misfire counters by cylinder; swap coil to see if misfire follows.",
            "Inspect intake/vacuum lines; smoke test if trims high.",
            "Inspect/clean MAF; verify air filter and ducting sealed.",
        ],
        "base_weight": 1.2,
    },
    {
        "rule_id": "fallback_no_start_crank",
        "name": "Crank/no-start",
        "keywords": ["cranks but wont start", "cranks but won't start", "no start", "won't start", "dead"],
        "dtc_prefixes": ["P06", "P0A", "U0", "P033"],
        "likely_causes": [
            "Battery/voltage issue",
            "Fuel delivery issue",
            "Security/immobilizer",
            "Crank/cam signal issue",
        ],
        "checks": [
            "Check battery voltage and cranking voltage drop.",
            "Verify fuel pressure (spec) and injector pulse.",
            "Check for security indicator / immobilizer faults.",
            "Look for RPM signal while cranking; check CKP/CMP related DTCs.",
        ],
        "base_weight": 1.1,
    },
    {
        "rule_id": "fallback_vibration_highway",
        "name": "Highway speed vibration",
        "keywords": ["vibration", "shake", "shudder", "steering wheel shakes", "vibrate"],
        "dtc_prefixes": [],
        "likely_causes": [
            "Wheel/tire imbalance",
            "Tire belt separation / out
