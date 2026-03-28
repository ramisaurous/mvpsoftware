# app/core/triage.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlmodel import Session, select

from app.core.db import engine
from app.core.symptom_parser import ParsedSymptoms, parse_symptoms
from app.models.triage_rule import TriageRule

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
    """
    Returns up to 8 ranked triage hits.

    - Keeps legacy heuristic rules.
    - Adds DB-backed KB rules (TriageRule) using broad symptom parsing.
    """
    dtc_set = {d.upper().strip() for d in (dtcs or []) if d and d.strip()}
    symptom_list = [s.strip() for s in (symptoms or []) if s and s.strip()]
    symptom_set = {s.lower() for s in symptom_list}
    learned_weights = learned_weights or {}

    hits: list[TriageHit] = []

    # -------------------------
    # Legacy heuristic rules
    # -------------------------
    for rule in _RULES:
        dtc_match = any(code in dtc_set for code in rule["dtc_any"])
        symptom_match = any(k in symptom_set for k in rule["symptoms_any"])
        if not (dtc_match or symptom_match):
            continue

        base = 0.40
        base += 0.35 if dtc_match else 0.0
        base += 0.20 if symptom_match else 0.0

        if platform:
            base += 0.03
        if engine and engine.strip():
            base += 0.02

        base *= learned_weights.get(rule["id"], 1.0)
        base = max(0.05, min(0.98, base))

        causes = [{"cause": name, "weight": w} for (name, w) in rule["causes"]]
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

    # -------------------------
    # KB rules from DB
    # -------------------------
    parsed = _parse_symptom_input(symptom_list)
    kb_hits = _triage_with_kb(dtcs=list(dtc_set), parsed=parsed, platform=platform, engine=engine)
    hits.extend(kb_hits)

    hits.sort(key=lambda h: h.confidence, reverse=True)
    return hits[:8]


def _parse_symptom_input(symptom_list: list[str]) -> ParsedSymptoms:
    # Your UI currently sends a list; joining makes "vibration over 60 mph" work well.
    text = " ".join(symptom_list)
    return parse_symptoms(text)


def _triage_with_kb(
    dtcs: list[str],
    parsed: ParsedSymptoms,
    platform: str | None,
    engine: str | None,
) -> list[TriageHit]:
    """
    Loads KB rules from DB and returns scored hits mapped into existing TriageHit shape.
    """
    dtc_set = {d.upper().strip() for d in (dtcs or []) if d and d.strip()}
    tags = {t.lower() for t in (parsed.tags or [])}
    contexts = set((parsed.attrs.get("contexts") or []))
    speed_min_mph = parsed.attrs.get("speed_min_mph")

    with Session(engine) as session:
        rules = session.exec(select(TriageRule)).all()

    out: list[tuple[float, TriageHit]] = []

    for r in rules:
        req = {t.lower() for t in (r.required_tags or []) if t and t.strip()}
        if req and not req.issubset(tags):
            continue

        score = 0.40
        why_boost = 0.0

        # Required tags (strong signal)
        if req:
            why_boost += 0.18 + 0.03 * len(req)

        # Optional tags
        opt = {t.lower() for t in (r.optional_tags or []) if t and t.strip()}
        opt_hit = len(opt.intersection(tags))
        if opt_hit:
            why_boost += 0.05 * opt_hit

        # Context
        ctx_any = set(r.contexts_any or [])
        ctx_hit = len(ctx_any.intersection(contexts))
        if ctx_hit:
            why_boost += 0.04 * ctx_hit

        # Speed threshold
        if r.min_speed_mph is not None and speed_min_mph is not None:
            if int(speed_min_mph) >= int(r.min_speed_mph):
                why_boost += 0.08

        # DTC overlap
        dtc_any = {d.upper().strip() for d in (r.dtcs_any or []) if d and d.strip()}
        dtc_hit = len(dtc_any.intersection(dtc_set))
        if dtc_hit:
            why_boost += 0.12 + 0.03 * dtc_hit

        score += why_boost

        # Slight bump if platform/engine given (keeps parity with legacy logic)
        if platform:
            score += 0.02
        if engine and engine.strip():
            score += 0.01

        score *= float(r.base_weight or 1.0)
        score = max(0.05, min(0.98, score))

        probable_causes = [{"cause": c, "weight": round(1.0 / max(1, len(r.likely_causes or [])), 3)} for c in (r.likely_causes or [])]
        hit = TriageHit(
            rule_id=f"kb:{r.id}",
            title=f"{r.name} (KB)",
            confidence=round(score, 3),
            probable_causes=probable_causes,
            programming_recommendation=[],
            preflight_checklist=_merge_unique(list(r.checks or []), _GENERIC_PRECHECK),
        )
        out.append((score, hit))

    out.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in out[:8]]


def _merge_unique(a: Iterable[str], b: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in list(a or []) + list(b or []):
        x2 = (x or "").strip()
        if x2 and x2 not in seen:
            seen.add(x2)
            out.append(x2)
    return out
