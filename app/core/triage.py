# app/core/triage.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Shop-grade heuristics for 5.3 L84 / 6.2 L87 common patterns.
# Extend as you learn your fleet.
_RULES: list[dict[str, Any]] = [
    {
        "id": "misfire_fuel_air",
        "title": "Misfire / Fuel / Air / Ignition",
        "dtc_any": ["P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0307", "P0308"],
        "symptoms_any": ["rough idle", "misfire", "shake", "stumble", "lack of power"],
        "causes": [
            ("Ignition coil / plug / wire issue", 0.42),
            ("Injector issue / fueling imbalance", 0.28),
            ("Vacuum leak / unmetered air", 0.18),
            ("AFM/DFM lifter/cam concern (platform-specific)", 0.12),
        ],
        "programming": [
            "Verify ECM calibration is current; check for misfire-related updated calibrations if available."
        ],
        "preflight": [
            "Battery support 13.2–14.2V, 70A+",
            "Record freeze frame / mode $06",
            "Check for aftermarket tune; document before changes",
        ],
    },
    {
        "id": "o2_fuel_trim",
        "title": "Fuel Trim / O2 / Intake Leaks",
        "dtc_any": ["P0171", "P0174", "P0131", "P0151", "P0137", "P0157"],
        "symptoms_any": ["poor mpg", "lean", "hesitation", "surge"],
        "causes": [
            ("Unmetered air / intake leak", 0.40),
            ("Exhaust leak upstream of O2", 0.20),
            ("A/F sensor or O2 sensor issue", 0.25),
            ("Fuel delivery issue (pump/filter/reg)", 0.15),
        ],
        "programming": ["Check for ECM updates affecting fuel trim / sensor rationality."],
        "preflight": ["Smoke test intake", "Verify MAF cleanliness / plausibility", "Fuel pressure under load"],
    },
    {
        "id": "evap",
        "title": "EVAP System",
        "dtc_any": ["P0442", "P0455", "P0456", "P0496"],
        "symptoms_any": ["check engine", "fuel smell"],
        "causes": [
            ("Loose/failed gas cap or seal", 0.25),
            ("EVAP purge valve stuck/leaking", 0.35),
            ("EVAP vent valve / canister issue", 0.25),
            ("Leak in EVAP lines", 0.15),
        ],
        "programming": ["No programming typically required; verify no bulletin requiring ECM logic update."],
        "preflight": ["Run EVAP service bay test if supported", "Inspect purge command vs STFT response"],
    },
    {
        "id": "network_uds",
        "title": "Network / U-Codes / Module Comms",
        "dtc_any": ["U0100", "U0121", "U0140", "U0151", "U0184", "U0401", "U0415"],
        "symptoms_any": ["no start", "multiple lights", "loss of comm", "service safety", "service stabilitrak"],
        "causes": [
            ("Low voltage / battery / grounds", 0.45),
            ("CAN bus wiring/connectors", 0.25),
            ("Module reset / software anomaly", 0.20),
            ("Failed module (confirm with pinpoint tests)", 0.10),
        ],
        "programming": [
            "If symptoms intermittent and voltage stable: consider module reprogram/update path with human approval."
        ],
        "preflight": ["Battery & grounds load test", "Network health check / topology if tool supports"],
    },
    {
        "id": "trans_tcc",
        "title": "Transmission / TCC / Shift Quality",
        "dtc_any": ["P0741", "P0796", "P07A3", "P07A5"],
        "symptoms_any": ["shudder", "flare", "hard shift", "slip"],
        "causes": [
            ("Fluid condition / wrong fluid / aeration", 0.35),
            ("Valve body / solenoid concern", 0.30),
            ("Converter clutch issue", 0.20),
            ("Software / adapts (needs procedure)", 0.15),
        ],
        "programming": [
            "If supported: perform TCM update and relearn procedure with battery maintainer."
        ],
        "preflight": ["Document fluid level/condition", "Road test with data log", "Check for service bulletins"],
    },
]

_GENERIC_PRECHECK = [
    "Stable power supply (programming): 13.2–14.2V, 70A+",
    "Internet stable; disable sleep/hibernation on laptop",
    "Record existing module IDs / calibrations before changes",
    "Confirm customer authorization + RO notes",
]


@dataclass(frozen=True)
class TriageHit:
    rule_id: str
    title: str
    confidence: float
    probable_causes: list[dict[str, Any]]
    programming_recommendation: list[str]
    preflight_checklist: list[str]


def triage(
    dtcs: list[str],
    symptoms: list[str],
    platform: str | None,
    engine: str | None,
    learned_weights: dict[str, float] | None = None,
) -> list[TriageHit]:
    dtc_set = {d.upper().strip() for d in (dtcs or []) if d}
    symptom_set = {s.strip().lower() for s in (symptoms or []) if s and s.strip()}
    learned_weights = learned_weights or {}

    hits: list[TriageHit] = []
    for rule in _RULES:
        dtc_match = any(code in dtc_set for code in rule["dtc_any"])
        symptom_match = any(k in symptom_set for k in rule["symptoms_any"])

        if not (dtc_match or symptom_match):
            continue

        base = 0.40
        base += 0.35 if dtc_match else 0.0
        base += 0.20 if symptom_match else 0.0

        # Slight bump if platform/engine given (placeholder for future specificity)
        if platform:
            base += 0.03
        if engine and engine.strip():
            base += 0.02

        # Learning bump/damp by rule_id (stored from outcomes)
        base *= learned_weights.get(rule["id"], 1.0)
        base = max(0.05, min(0.98, base))

        causes = []
        for (name, w) in rule["causes"]:
            causes.append({"cause": name, "weight": w})

        hits.append(
            TriageHit(
                rule_id=rule["id"],
                title=rule["title"],
                confidence=round(base, 3),
                probable_causes=sorted(causes, key=lambda x: x["weight"], reverse=True),
                programming_recommendation=list(rule["programming"]),
                preflight_checklist=_merge_unique(rule["preflight"], _GENERIC_PRECHECK),
            )
        )

    hits.sort(key=lambda h: h.confidence, reverse=True)
    return hits[:8]


def _merge_unique(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in (a or []) + (b or []):
        x2 = (x or "").strip()
        if x2 and x2 not in seen:
            seen.add(x2)
            out.append(x2)
    return out
