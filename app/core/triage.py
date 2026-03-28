from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlmodel import Session, select

from app.core.db import engine
from app.core.symptom_parser import ParsedSymptoms, parse_symptoms
from app.models.triage_rule import TriageRule


# Legacy rules still help catch common cases even if DB KB is incomplete.
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
        "programming": [
            "Check for ECM updates affecting fuel trim / sensor rationality."
        ],
        "preflight": [
            "Smoke test intake",
            "Verify MAF cleanliness / plausibility",
            "Fuel pressure under load",
        ],
    },
    {
        "id": "evap",
        "title": "EVAP System",
        "dtc_any": ["P0442", "P0455", "P0456", "P0496"],
        "symptoms_any": ["check engine", "fuel smell", "stall at stop", "stalls at stop"],
        "causes": [
            ("Loose/failed gas cap or seal", 0.25),
            ("EVAP purge valve stuck/leaking", 0.35),
            ("EVAP vent valve / canister issue", 0.25),
            ("Leak in EVAP lines", 0.15),
        ],
        "programming": [
            "No programming typically required; verify no bulletin requiring ECM logic update."
        ],
        "preflight": [
            "Run EVAP service bay test if supported",
            "Inspect purge command vs STFT response",
        ],
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
        "preflight": [
            "Battery & grounds load test",
            "Network health check / topology if tool supports",
        ],
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
        "preflight": [
            "Document fluid level/condition",
            "Road test with data log",
            "Check for service bulletins",
        ],
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
    dtc_set = {d.upper().strip() for d in (dtcs or []) if d and d.strip()}
    symptom_list = [s.strip() for s in (symptoms or []) if s and s.strip()]
    symptom_text = " | ".join(symptom_list).lower()
    learned_weights = learned_weights or {}

    hits: list[TriageHit] = []

    # Legacy rules
    for rule in _RULES:
        dtc_hit_count = len({c.upper() for c in rule["dtc_any"]}.intersection(dtc_set))
        symptom_hit_count = sum(
            1 for phrase in rule["symptoms_any"]
            if phrase.lower() in symptom_text
        )

        if dtc_hit_count == 0 and symptom_hit_count == 0:
            continue

        score = 0.18
        score += min(0.40, 0.18 * dtc_hit_count)
        score += min(0.24, 0.08 * symptom_hit_count)
        if platform:
            score += 0.02
        if engine and engine.strip():
            score += 0.01

        score *= float(learned_weights.get(rule["id"], 1.0))
        score = _clamp_score(score)

        cause_weight_bonus = min(0.15, 0.04 * dtc_hit_count + 0.02 * symptom_hit_count)
        causes = [
            {"cause": name, "weight": round(base_weight + cause_weight_bonus, 3)}
            for (name, base_weight) in rule["causes"]
        ]
        causes.sort(key=lambda x: x["weight"], reverse=True)

        hits.append(
            TriageHit(
                rule_id=rule["id"],
                title=rule["title"],
                confidence=score,
                probable_causes=causes,
                programming_recommendation=list(rule["programming"]),
                preflight_checklist=_merge_unique(rule["preflight"], _GENERIC_PRECHECK),
            )
        )

    # DB KB rules
    parsed = _parse_symptom_input(symptom_list)
    hits.extend(
        _triage_with_kb(
            dtcs=list(dtc_set),
            parsed=parsed,
            symptom_text=symptom_text,
            platform=platform,
            engine=engine,
        )
    )

    # Deduplicate near-identical titles, keeping the highest confidence hit
    best_by_title: dict[str, TriageHit] = {}
    for hit in hits:
        existing = best_by_title.get(hit.title)
        if existing is None or hit.confidence > existing.confidence:
            best_by_title[hit.title] = hit

    final_hits = list(best_by_title.values())
    final_hits.sort(key=lambda h: h.confidence, reverse=True)
    return final_hits[:8]


def _parse_symptom_input(symptom_list: list[str]) -> ParsedSymptoms:
    text = " ".join(symptom_list)
    return parse_symptoms(text)


def _triage_with_kb(
    dtcs: list[str],
    parsed: ParsedSymptoms,
    symptom_text: str,
    platform: str | None,
    engine: str | None,
) -> list[TriageHit]:
    dtc_set = {d.upper().strip() for d in (dtcs or []) if d and d.strip()}
    tags = {t.lower() for t in (parsed.tags or [])}
    contexts = {c.lower() for c in (parsed.attrs.get("contexts") or [])}
    speed_min_mph = parsed.attrs.get("speed_min_mph")

    with Session(engine) as session:
        rules = session.exec(select(TriageRule)).all()

    out: list[TriageHit] = []

    for r in rules:
        required_tags = {t.lower().strip() for t in (r.required_tags or []) if t and t.strip()}
        optional_tags = {t.lower().strip() for t in (r.optional_tags or []) if t and t.strip()}
        contexts_any = {c.lower().strip() for c in (r.contexts_any or []) if c and c.strip()}
        dtcs_any = {d.upper().strip() for d in (r.dtcs_any or []) if d and d.strip()}

        # If rule has required tags, they must all be present.
        if required_tags and not required_tags.issubset(tags):
            continue

        required_tag_hits = len(required_tags.intersection(tags))
        optional_tag_hits = len(optional_tags.intersection(tags))
        context_hits = len(contexts_any.intersection(contexts))
        dtc_hits = len(dtcs_any.intersection(dtc_set))

        # Lightweight text fallback so phrasing variants still catch.
        text_hint_hits = _count_text_hints(
            rule_name=r.name,
            category=r.category,
            likely_causes=r.likely_causes or [],
            symptom_text=symptom_text,
        )

        # Skip dead matches:
        # - if rule has required tags, it already passed
        # - if no required tags, require at least one of dtc/context/optional/text hint
        if not required_tags and (optional_tag_hits + context_hits + dtc_hits + text_hint_hits) == 0:
            continue

        score = 0.12

        # Required tags are strongest
        if required_tag_hits:
            score += 0.34 + min(0.12, 0.04 * required_tag_hits)

        # Optional tags still matter
        if optional_tag_hits:
            score += min(0.20, 0.07 * optional_tag_hits)

        # DTC overlap is strong
        if dtc_hits:
            score += 0.18 + min(0.12, 0.04 * dtc_hits)

        # Context helps narrow it
        if context_hits:
            score += min(0.12, 0.05 * context_hits)

        # Text hint fallback helps catch wording weirdness
        if text_hint_hits:
            score += min(0.12, 0.04 * text_hint_hits)

        # Speed threshold
        if r.min_speed_mph is not None and speed_min_mph is not None:
            try:
                if int(speed_min_mph) >= int(r.min_speed_mph):
                    score += 0.08
            except (TypeError, ValueError):
                pass

        if platform:
            score += 0.02
        if engine and str(engine).strip():
            score += 0.01

        score *= float(r.base_weight or 1.0)
        score = _clamp_score(score)

        probable_causes = _weighted_causes(
            causes=r.likely_causes or [],
            required_tag_hits=required_tag_hits,
            optional_tag_hits=optional_tag_hits,
            dtc_hits=dtc_hits,
            context_hits=context_hits,
            text_hint_hits=text_hint_hits,
        )

        out.append(
            TriageHit(
                rule_id=f"kb:{r.id}",
                title=f"{r.name} (KB)",
                confidence=score,
                probable_causes=probable_causes,
                programming_recommendation=[],
                preflight_checklist=_merge_unique(list(r.checks or []), _GENERIC_PRECHECK),
            )
        )

    out.sort(key=lambda h: h.confidence, reverse=True)
    return out[:8]


def _weighted_causes(
    causes: list[str],
    required_tag_hits: int,
    optional_tag_hits: int,
    dtc_hits: int,
    context_hits: int,
    text_hint_hits: int,
) -> list[dict[str, Any]]:
    clean_causes = [c.strip() for c in causes if c and c.strip()]
    if not clean_causes:
        return []

    signal_bonus = (
        0.03 * required_tag_hits
        + 0.02 * optional_tag_hits
        + 0.04 * dtc_hits
        + 0.02 * context_hits
        + 0.01 * text_hint_hits
    )

    base = max(0.18, round(1.0 / len(clean_causes), 3))
    out = [{"cause": c, "weight": round(base + signal_bonus, 3)} for c in clean_causes]
    out.sort(key=lambda x: x["weight"], reverse=True)
    return out


def _count_text_hints(
    rule_name: str,
    category: str,
    likely_causes: list[str],
    symptom_text: str,
) -> int:
    text = symptom_text.lower()
    bucket = {
        rule_name.lower(),
        category.lower(),
        *[c.lower() for c in likely_causes if c],
    }

    hints = set()

    for item in bucket:
        for token in item.replace("/", " ").replace("-", " ").split():
            token = token.strip(" ,()")
            if len(token) >= 4:
                hints.add(token)

    matched = 0
    for hint in hints:
        if hint in text:
            matched += 1

    # manual synonym catchers for common shop phrasing
    manual_groups = [
        ({"stall", "stalls", "stalling", "dies"}, text),
        ({"vibration", "vibrate", "shake", "shudder"}, text),
        ({"hesitation", "bog", "flat"}, text),
        ({"clunk", "knock"}, text),
        ({"rough", "idle"}, text),
        ({"pull", "pulling", "braking"}, text),
    ]

    for words, body in manual_groups:
        if any(w in body for w in words):
            if any(w in " ".join(bucket) for w in words):
                matched += 1

    return matched


def _clamp_score(value: float) -> float:
    return round(max(0.05, min(0.98, value)), 3)


def _merge_unique(a: Iterable[str], b: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for x in list(a or []) + list(b or []):
        x2 = (x or "").strip()
        if x2 and x2 not in seen:
            seen.add(x2)
            out.append(x2)

    return out
