# app/core/kb_seed.py
from __future__ import annotations

from sqlmodel import Session, select

from app.models.triage_rule import TriageRule


def seed_kb(session: Session) -> None:
    """Idempotent: seed starter KB rules only if table is empty."""
    exists = session.exec(select(TriageRule).limit(1)).first()
    if exists:
        return

    rules = [
        TriageRule(
            name="Wheel/tire imbalance (vibration over highway speeds)",
            category="tires_wheels",
            required_tags=["vibration"],
            min_speed_mph=55,
            checks=[
                "Road test: confirm speed range; note if changes with throttle.",
                "Inspect tire wear (cupping/feathering), bulges, separated belts.",
                "Balance wheels; road-force balance if available.",
            ],
            likely_causes=["Wheel/tire imbalance", "Tire belt separation", "Cupped tires"],
            base_weight=1.2,
        ),
        TriageRule(
            name="Brake-related vibration (only when braking at speed)",
            category="brakes",
            required_tags=["vibration"],
            contexts_any=["when_braking"],
            min_speed_mph=45,
            checks=[
                "Confirm vibration only during braking (not steady cruise).",
                "Measure rotor runout/thickness variation; inspect caliper slides/pins.",
            ],
            likely_causes=["Rotor thickness variation", "Rotor runout", "Sticking caliper"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Wheel bearing noise (hum/growl that changes with load)",
            category="tires_wheels",
            required_tags=["noise"],
            optional_tags=["vibration"],
            min_speed_mph=35,
            checks=[
                "Road test: steer left/right to shift load; listen for change.",
                "Check play/roughness; compare hub temps after drive.",
            ],
            likely_causes=["Wheel bearing wear", "Hub assembly wear"],
            base_weight=1.0,
        ),
    ]

    for r in rules:
        session.add(r)
    session.commit()
