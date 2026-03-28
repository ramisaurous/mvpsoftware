# app/core/triage.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from sqlmodel import select

from app.core.db import get_session
from app.core.official_data import get_official_signals
from app.models.triage_rule import TriageRule


@dataclass
class TriageHit:
    rule_id: str
    name: str
    score: float
    likely_causes: list[str]
    checks: list[str]
    matched: list[str]


@dataclass
class LocalRule:
    rule_id: str
    name: str
    category: str
    required_tags: set[str]
    optional_tags: set[str]
    dtcs_any: set[str]
    platforms_any: set[str]
    engines_any: set[str]
    base_weight: float
    likely_causes: list[str]
    checks: list[str]


# These are intentionally more specific than generic starter rules.
LOCAL_RULES: list[LocalRule] = [
    LocalRule(
        rule_id="gm_stall_stop_idle_airfuel",
        name="GM V8 stall at stop / unstable idle air-fuel control pattern",
        category="engine",
        required_tags={"stall", "at_stop"},
        optional_tags={"rough_idle", "hard_start", "hesitation"},
        dtcs_any={"P0171", "P0174", "P050D", "P0101", "P0068"},
        platforms_any={"gmt1yc"},
        engines_any={"L84", "L87"},
        base_weight=1.38,
        likely_causes=[
            "Unmetered air / intake leak affecting idle fuel control",
            "Throttle body airflow control issue or learned idle issue",
            "Low-side fuel delivery weakness showing up at hot idle / stop events",
            "PCV / vacuum-related imbalance causing unstable idle and stall-at-stop behavior",
        ],
        checks=[
            "Review fuel trims at hot idle and during decel-to-stop.",
            "Smoke test intake tract and brake-booster / PCV / vacuum connections.",
            "Inspect throttle body, commanded vs actual airflow, and idle relearn status.",
            "Check low-side fuel pressure stability during the stall event.",
        ],
    ),
    LocalRule(
        rule_id="gm_v8_rough_idle_misfire_mech",
        name="GM V8 rough idle / misfire mechanical valvetrain pattern",
        category="engine",
        required_tags={"rough_idle"},
        optional_tags={"misfire", "vibration", "tick", "low_power"},
        dtcs_any={"P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0307", "P0308"},
        platforms_any={"gmt1yc"},
        engines_any={"L84", "L87"},
        base_weight=1.42,
        likely_causes=[
            "Valvetrain fault affecting cylinder contribution under idle load",
            "Injector imbalance or cylinder-specific fueling issue",
            "Ignition-side misfire on one or more cylinders",
            "Compression or mechanical sealing issue on the affected cylinder",
        ],
        checks=[
            "Identify if one cylinder dominates the misfire counter or if the event is random.",
            "Compare cylinder contribution, injector balance, and ignition performance.",
            "Check for abnormal valvetrain noise alongside misfire data.",
            "Run relative compression / mechanical integrity checks if misfire follows one hole.",
        ],
    ),
    LocalRule(
        rule_id="gm_v8_stall_hot_restart",
        name="GM V8 intermittent stall / hard restart hot-soak pattern",
        category="engine_control",
        required_tags={"stall"},
        optional_tags={"hard_start", "no_start", "after_warmup"},
        dtcs_any={"P0335", "P062B", "P0606", "P0191"},
        platforms_any={"gmt1yc"},
        engines_any={"L84", "L87"},
        base_weight=1.30,
        likely_causes=[
            "Crank / engine-speed signal dropout causing stall and restart delay",
            "Fuel rail pressure reporting or delivery issue during hot restart",
            "Control module logic or calibration-related intermittent stall behavior",
        ],
        checks=[
            "Capture the event hot with RPM, crank signal, rail pressure, and sync status.",
            "Watch if tach drops instantly during the stall.",
            "Compare desired vs actual fuel pressure during restart.",
            "Check for calibration updates and repeatable heat-related patterns.",
        ],
    ),
    LocalRule(
        rule_id="gm_v8_vibration_afm_dfm_misfire",
        name="GM V8 vibration / shudder combustion quality pattern",
        category="engine",
        required_tags={"vibration"},
        optional_tags={"misfire", "rough_idle", "shudder"},
        dtcs_any={"P0300"},
        platforms_any={"gmt1yc"},
        engines_any={"L84", "L87"},
        base_weight=1.26,
        likely_causes=[
            "Combustion quality issue presenting as idle/load vibration",
            "Cylinder contribution imbalance rather than chassis vibration",
            "Torque-management / engine load transition exaggerating the complaint",
        ],
        checks=[
            "Separate engine-origin vibration from driveline or road-speed vibration.",
            "Check misfire counters under the exact complaint condition.",
            "Correlate the complaint to engine load, cylinder contribution, and RPM.",
        ],
    ),
]


_SYNONYM_MAP = {
    "stalls at stop": {"stall", "at_stop"},
    "stalls when stopping": {"stall", "at_stop"},
    "stall at stop": {"stall", "at_stop"},
    "dies at stop": {"stall", "at_stop"},
    "rough idle": {"rough_idle"},
    "vibration": {"vibration"},
    "shake": {"vibration"},
    "shudder": {"shudder", "vibration"},
    "misfire": {"misfire"},
    "hard start": {"hard_start"},
    "long crank": {"hard_start"},
    "no start": {"no_start"},
    "hesitation": {"hesitation"},
    "lack of power": {"low_power"},
    "low power": {"low_power"},
    "ticking": {"tick"},
    "tick": {"tick"},
    "warm": {"after_warmup"},
    "hot": {"after_warmup"},
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _symptom_tags(symptoms: list[str]) -> set[str]:
    tags: set[str] = set()

    for raw in symptoms or []:
        clean = _norm(raw)
        if not clean:
            continue

        for phrase, mapped in _SYNONYM_MAP.items():
            if phrase in clean:
                tags.update(mapped)

        # catch obvious one-word fallbacks
        if "stall" in clean:
            tags.add("stall")
        if "stop" in clean and "stall" in clean:
            tags.add("at_stop")
        if "idle" in clean and "rough" in clean:
            tags.add("rough_idle")
        if "misfire" in clean:
            tags.add("misfire")
        if "vibration" in clean or "shake" in clean:
            tags.add("vibration")

    return tags


def _normalize_dtcs(dtcs: list[str]) -> set[str]:
    return {d.strip().upper() for d in (dtcs or []) if d and d.strip()}


def _load_db_rules() -> list[TriageRule]:
    try:
        with get_session() as session:
            return list(session.exec(select(TriageRule)).all())
    except Exception:
        return []


def _score_local_rule(
    rule: LocalRule,
    *,
    dtcs: set[str],
    tags: set[str],
    platform: str | None,
    engine: str | None,
    learned_weights: dict[str, float] | None,
) -> TriageHit | None:
    if rule.required_tags and not rule.required_tags.issubset(tags):
        return None

    score = rule.base_weight
    matched: list[str] = []

    if rule.platforms_any and (platform or "").lower() in {p.lower() for p in rule.platforms_any}:
        score += 0.18
        matched.append(f"platform:{platform}")

    if rule.engines_any and (engine or "").upper() in {e.upper() for e in rule.engines_any}:
        score += 0.22
        matched.append(f"engine:{engine}")

    tag_hits = sorted(rule.optional_tags & tags)
    if tag_hits:
        score += min(0.36, 0.12 * len(tag_hits))
        matched.extend([f"tag:{x}" for x in tag_hits])

    dtc_hits = sorted(rule.dtcs_any & dtcs)
    if dtc_hits:
        score += min(0.55, 0.18 * len(dtc_hits))
        matched.extend([f"dtc:{x}" for x in dtc_hits])

    if rule.required_tags:
        matched.extend([f"required:{x}" for x in sorted(rule.required_tags)])

    if learned_weights:
        score *= learned_weights.get(rule.rule_id, 1.0)

    return TriageHit(
        rule_id=rule.rule_id,
        name=rule.name,
        score=round(score, 4),
        likely_causes=list(rule.likely_causes),
        checks=list(rule.checks),
        matched=matched,
    )


def _score_db_rule(
    rule: TriageRule,
    *,
    dtcs: set[str],
    tags: set[str],
    learned_weights: dict[str, float] | None,
) -> TriageHit | None:
    required_tags = {x.strip().lower() for x in (rule.required_tags or []) if x}
    optional_tags = {x.strip().lower() for x in (rule.optional_tags or []) if x}
    rule_dtcs = {x.strip().upper() for x in (rule.dtcs_any or []) if x}

    if required_tags and not required_tags.issubset(tags):
        return None

    score = float(rule.base_weight or 1.0)
    matched: list[str] = []

    tag_hits = sorted(optional_tags & tags)
    if tag_hits:
        score += min(0.30, 0.10 * len(tag_hits))
        matched.extend([f"tag:{x}" for x in tag_hits])

    dtc_hits = sorted(rule_dtcs & dtcs)
    if dtc_hits:
        score += min(0.45, 0.15 * len(dtc_hits))
        matched.extend([f"dtc:{x}" for x in dtc_hits])

    if required_tags:
        matched.extend([f"required:{x}" for x in sorted(required_tags)])

    rule_id = f"db_rule_{rule.id}"
    if learned_weights:
        score *= learned_weights.get(rule_id, 1.0)

    # require at least some signal so random generic rows don't float to top
    if not matched and score <= 1.0:
        return None

    return TriageHit(
        rule_id=rule_id,
        name=rule.name,
        score=round(score, 4),
        likely_causes=list(rule.likely_causes or []),
        checks=list(rule.checks or []),
        matched=matched,
    )


def _apply_official_enrichment(
    hits: list[TriageHit],
    *,
    year: int | None,
    make: str | None,
    model_family: str | None,
    dtcs: set[str],
    tags: set[str],
) -> list[TriageHit]:
    signals = get_official_signals(
        year=year,
        make=make,
        model_family=model_family,
        dtcs=sorted(dtcs),
        symptom_tags=tags,
    )

    if not signals:
        return hits

    for hit in hits:
        # small score bump
        total_boost = sum(s.score_boost for s in signals[:2])
        hit.score = round(hit.score + total_boost, 4)

        # inject evidence so current UI shows it without HTML changes
        for sig in signals[:2]:
            for line in sig.evidence[:2]:
                bullet = f"Official signal: {line}"
                if bullet not in hit.checks:
                    hit.checks.append(bullet)

            if sig.matched_terms:
                hit.matched.append(f"official:{sig.label}")

    return hits


def triage(
    dtcs: list[str],
    symptoms: list[str],
    platform: str | None = None,
    engine: str | None = None,
    *,
    year: int | None = None,
    make: str | None = None,
    model_family: str | None = None,
    learned_weights: dict[str, float] | None = None,
) -> list[TriageHit]:
    dtc_set = _normalize_dtcs(dtcs)
    tag_set = _symptom_tags(symptoms)

    hits: list[TriageHit] = []

    for rule in LOCAL_RULES:
        hit = _score_local_rule(
            rule,
            dtcs=dtc_set,
            tags=tag_set,
            platform=platform,
            engine=engine,
            learned_weights=learned_weights,
        )
        if hit:
            hits.append(hit)

    for rule in _load_db_rules():
        hit = _score_db_rule(
            rule,
            dtcs=dtc_set,
            tags=tag_set,
            learned_weights=learned_weights,
        )
        if hit:
            hits.append(hit)

    if not hits:
        hits.append(
            TriageHit(
                rule_id="generic_fallback",
                name="No strong pattern match yet",
                score=0.75,
                likely_causes=[
                    "Not enough matched evidence from current DTCs / symptom text",
                    "Complaint may need a more exact symptom phrase or scan data snapshot",
                ],
                checks=[
                    "Add exact wording such as 'stalls at stop', 'rough idle hot', 'long crank cold', or cylinder-specific misfire.",
                    "Add any DTCs and whether the event happens hot, cold, braking, stopping, cruising, or under load.",
                ],
                matched=[],
            )
        )

    hits = _apply_official_enrichment(
        hits,
        year=year,
        make=make,
        model_family=model_family,
        dtcs=dtc_set,
        tags=tag_set,
    )

    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:5]
