# app/core/triage.py
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
        "dtc_prefixes": ["P06", "P0A", "U0"],
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
            "Tire belt separation / out-of-round",
            "Driveline/prop shaft imbalance",
        ],
        "checks": [
            "Confirm speed range (55–75 mph) and whether it changes under throttle/coast.",
            "Inspect tires for cupping/bulges; rotate front↔rear and retest.",
            "Balance/road-force balance; check wheel runout.",
            "If load-dependent, inspect driveline angles / prop shaft.",
        ],
        "base_weight": 1.0,
    },
    {
        "rule_id": "fallback_overheat",
        "name": "Overheating / high temp",
        "keywords": ["overheat", "hot", "temperature high", "temp high", "coolant boiling"],
        "dtc_prefixes": ["P012", "P021", "P148"],
        "likely_causes": [
            "Low coolant / air pocket",
            "Thermostat issue",
            "Cooling fan control issue",
            "Radiator restriction",
        ],
        "checks": [
            "Check coolant level and bleed air; pressure test for leaks.",
            "Verify thermostat operation (temp rise behavior).",
            "Command fans on with scan tool; verify relays/fuses.",
            "Check radiator/condenser airflow and external blockage.",
        ],
        "base_weight": 1.1,
    },
]


# ----------------------------
# Public API
# ----------------------------

def triage(
    dtcs: list[str] | None,
    symptoms: list[str] | None,
    platform: str | None,
    engine: str | None,
    learned_weights: dict[str, float] | None = None,
) -> list[TriageHit]:
    """
    Returns ranked triage hits.

    - First attempts KB-based triage using DB rules (TriageRule table).
    - If DB/K B query fails for ANY reason, falls back to static rules.
    """
    learned_weights = learned_weights or {}

    dtc_set = {(_norm(d) or "") for d in (dtcs or []) if _norm(d)}
    sym_text = " | ".join([_norm(s) for s in (symptoms or []) if _norm(s)])
    sym_lower = sym_text.lower()

    # 1) Try KB triage (DB)
    kb_hits = _triage_with_kb_safe(
        dtc_set=dtc_set,
        symptom_text=sym_lower,
        platform=_norm(platform),
        engine=_norm(engine),
        learned_weights=learned_weights,
    )
    if kb_hits:
        return kb_hits

    # 2) Fallback triage (no DB)
    return _triage_with_fallback(
        dtc_set=dtc_set,
        symptom_text=sym_lower,
        learned_weights=learned_weights,
    )


# ----------------------------
# KB triage (safe)
# ----------------------------

def _triage_with_kb_safe(
    dtc_set: set[str],
    symptom_text: str,
    platform: str | None,
    engine: str | None,
    learned_weights: dict[str, float],
) -> list[TriageHit]:
    """
    Safe wrapper that will NEVER raise; returns [] if KB can’t be queried.
    This avoids 500s when the KB session/model isn’t bound correctly.
    """
    try:
        # Import inside try so missing model doesn’t crash startup/requests
        from app.models.triage_rule import TriageRule  # type: ignore
    except Exception:
        return []

    try:
        with get_session() as session:
            rules = session.exec(select(TriageRule)).all()
    except Exception:
        # This is where you were blowing up with UnboundExecutionError
        return []

    hits: list[TriageHit] = []
    for r in rules:
        # Be defensive: DB rows might not have all fields populated
        rule_id = getattr(r, "id", None) or getattr(r, "rule_id", None) or getattr(r, "name", "rule")
        name = getattr(r, "name", str(rule_id))

        required_dtcs = set([_norm(x) for x in (getattr(r, "required_dtcs", None) or []) if _norm(x)])
        required_tags = set([_norm(x) for x in (getattr(r, "required_tags", None) or []) if _norm(x)])
        optional_tags = set([_norm(x) for x in (getattr(r, "optional_tags", None) or []) if _norm(x)])

        # Quick keyword tagging from symptom_text
        tags = _infer_tags(symptom_text)

        # Required gates
        if required_dtcs and not (required_dtcs & dtc_set):
            continue
        if required_tags and not (required_tags <= tags):
            continue

        # Platform/engine gates (if rule specifies)
        rule_platforms = set([_norm(x) for x in (getattr(r, "platforms", None) or []) if _norm(x)])
        rule_engines = set([_norm(x) for x in (getattr(r, "engines", None) or []) if _norm(x)])
        if rule_platforms and platform and platform not in rule_platforms:
            continue
        if rule_engines and engine and engine not in rule_engines:
            continue

        base_weight = float(getattr(r, "base_weight", 1.0) or 1.0)
        learned_mult = float(learned_weights.get(str(rule_id), 1.0))
        bonus = 0.0
        if optional_tags:
            bonus += 0.15 * len(optional_tags & tags)

        score = round(base_weight * learned_mult + bonus, 4)

        likely_causes = list(getattr(r, "likely_causes", None) or [])
        checks = list(getattr(r, "checks", None) or [])

        hits.append(
            TriageHit(
                rule_id=str(rule_id),
                name=str(name),
                score=score,
                likely_causes=[str(x) for x in likely_causes],
                checks=[str(x) for x in checks],
                matched=sorted(list((required_tags | optional_tags) & tags)),
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:20]


# ----------------------------
# Fallback triage
# ----------------------------

def _triage_with_fallback(
    dtc_set: set[str],
    symptom_text: str,
    learned_weights: dict[str, float],
) -> list[TriageHit]:
    hits: list[TriageHit] = []

    for r in _FALLBACK_RULES:
        matched: list[str] = []

        # Symptom keyword match
        kw = r.get("keywords") or []
        if any(k.lower() in symptom_text for k in kw):
            matched.append("symptoms")

        # DTC prefix match
        prefixes = r.get("dtc_prefixes") or []
        if prefixes:
            for d in dtc_set:
                if any(d.startswith(p) for p in prefixes):
                    matched.append("dtc")
                    break

        if not matched:
            continue

        base = float(r.get("base_weight") or 1.0)
        learned_mult = float(learned_weights.get(str(r["rule_id"]), 1.0))
        score = round(base * learned_mult + (0.2 if "dtc" in matched else 0.0), 4)

        hits.append(
            TriageHit(
                rule_id=str(r["rule_id"]),
                name=str(r["name"]),
                score=score,
                likely_causes=list(r.get("likely_causes") or []),
                checks=list(r.get("checks") or []),
                matched=matched,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:10]


# ----------------------------
# Helpers
# ----------------------------

def _norm(x: Any) -> str:
    return str(x).strip()


def _infer_tags(symptom_text: str) -> set[str]:
    t = symptom_text.lower()
    tags: set[str] = set()
    if any(w in t for w in ["noise", "whine", "hum", "growl", "squeal", "rattle", "clunk", "knock"]):
        tags.add("noise")
    if any(w in t for w in ["vibration", "vibrate", "shake", "shudder"]):
        tags.add("vibration")
    if any(w in t for w in ["rough idle", "misfire", "stumble", "hesitation"]):
        tags.add("misfire")
    if any(w in t for w in ["overheat", "temperature high", "temp high", "hot"]):
        tags.add("overheat")
    if any(w in t for w in ["no start", "won't start", "wont start", "cranks but"]):
        tags.add("no_start")
    if any(w in t for w in ["stall", "stalls", "dies at stop", "dies"]):
        tags.add("stall")
    return tags
