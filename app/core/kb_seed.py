# app/core/kb_seed.py
from __future__ import annotations

from sqlmodel import Session, select
from app.models.triage_rule import TriageRule


def _rule_data() -> list[dict]:
    return [
        # -------------------------
        # STALL / IDLE / START
        # -------------------------
        {
            "name": "Stalls at stop / stalls when braking to a stop",
            "category": "engine_idle",
            "required_tags": ["stalling"],
            "optional_tags": ["rough_idle", "hesitation"],
            "contexts_any": ["when_braking", "at_stop", "idle"],
            "dtcs_any": ["P0171", "P0174", "P0101", "P0506", "P0507", "P0496"],
            "checks": [
                "Check STFT/LTFT at idle and while decelerating to stop.",
                "Inspect for vacuum leaks, brake booster leak, PCV issues.",
                "Check throttle body cleanliness and idle airflow control behavior.",
                "Check EVAP purge valve for stuck-open condition.",
                "Verify MAF plausibility and intake duct sealing.",
            ],
            "likely_causes": [
                "Vacuum leak",
                "Throttle body deposits / airflow issue",
                "Purge valve stuck open",
                "MAF sensor issue",
                "Brake booster vacuum leak",
            ],
            "base_weight": 1.25,
        },
        {
            "name": "Hard start / extended crank / intermittent no-start",
            "category": "starting",
            "required_tags": ["hard_start"],
            "optional_tags": ["stalling", "hesitation"],
            "dtcs_any": ["P0087", "P0191", "P0335", "P0627"],
            "checks": [
                "Verify fuel pressure during crank and after key cycle.",
                "Check low-side/high-side fuel performance if supported.",
                "Inspect crank sensor signal and RPM during crank.",
                "Check battery voltage drop and grounds.",
            ],
            "likely_causes": [
                "Fuel delivery issue",
                "Crank sensor issue",
                "Low voltage / weak battery",
                "Fuel pump control issue",
            ],
            "base_weight": 1.15,
        },

        # -------------------------
        # IDLE / MISFIRE / AIR / FUEL
        # -------------------------
        {
            "name": "Surge / hunting idle",
            "category": "engine_idle",
            "required_tags": ["surging"],
            "optional_tags": ["rough_idle", "hesitation"],
            "dtcs_any": ["P0171", "P0174", "P0101", "P0507"],
            "checks": [
                "Watch idle airflow and trims for oscillation.",
                "Smoke test intake and PCV system.",
                "Check throttle body and MAF contamination.",
            ],
            "likely_causes": [
                "Vacuum leak",
                "Throttle body contamination",
                "MAF contamination",
                "Idle control strategy issue",
            ],
            "base_weight": 1.1,
        },
        {
            "name": "Rough idle with no MIL",
            "category": "engine_idle",
            "required_tags": ["rough_idle"],
            "optional_tags": ["misfire", "surging"],
            "checks": [
                "Check fuel trims, misfire counters, and engine mounts.",
                "Inspect intake leaks and throttle body.",
                "Check plugs/coils if counters rise.",
            ],
            "likely_causes": [
                "Vacuum leak",
                "Minor ignition issue",
                "Throttle body deposits",
                "Engine mount concern",
            ],
            "base_weight": 1.05,
        },

        # -------------------------
        # DRIVABILITY
        # -------------------------
        {
            "name": "Hesitation on acceleration / bog / flat takeoff",
            "category": "drivability",
            "required_tags": ["hesitation"],
            "optional_tags": ["lack_of_power", "surging"],
            "contexts_any": ["when_accelerating"],
            "dtcs_any": ["P0101", "P0121", "P0171", "P0300"],
            "checks": [
                "Check APP vs throttle correlation.",
                "Verify fuel trims and MAF under load.",
                "Check misfire counters and fuel pressure.",
            ],
            "likely_causes": [
                "Airflow metering issue",
                "Throttle body / pedal correlation issue",
                "Lean condition",
                "Misfire under load",
            ],
            "base_weight": 1.12,
        },
        {
            "name": "Lack of power / reduced performance",
            "category": "drivability",
            "required_tags": ["lack_of_power"],
            "optional_tags": ["hesitation", "misfire"],
            "dtcs_any": ["P0299", "P0300", "P0101", "P0420", "P0430"],
            "checks": [
                "Check for airflow restriction and catalyst restriction clues.",
                "Check misfire counters and fuel trims.",
                "Verify throttle opening and load calculation.",
            ],
            "likely_causes": [
                "Misfire / ignition issue",
                "Airflow metering issue",
                "Exhaust restriction",
                "Fuel delivery issue",
            ],
            "base_weight": 1.08,
        },

        # -------------------------
        # BRAKES / CHASSIS
        # -------------------------
        {
            "name": "Pulls while braking",
            "category": "brakes",
            "required_tags": ["pulling"],
            "contexts_any": ["when_braking"],
            "checks": [
                "Check rotor temp side-to-side after short drive.",
                "Inspect caliper slides, hose restriction, pad condition.",
            ],
            "likely_causes": [
                "Sticking caliper",
                "Brake hose restriction",
                "Uneven pad friction",
            ],
            "base_weight": 1.08,
        },
        {
            "name": "Clunk on takeoff / clunk on stop",
            "category": "chassis",
            "required_tags": ["clunk"],
            "optional_tags": ["noise"],
            "contexts_any": ["when_accelerating", "at_stop"],
            "checks": [
                "Inspect driveline lash, mounts, and suspension joints.",
                "Check control arm bushings, sway links, and driveshaft play.",
            ],
            "likely_causes": [
                "Engine/trans mount wear",
                "Suspension joint play",
                "Driveshaft lash / U-joint issue",
            ],
            "base_weight": 1.0,
        },

        # -------------------------
        # ELECTRICAL / NETWORK
        # -------------------------
        {
            "name": "Intermittent crank-no-start / dash lights / comm weirdness",
            "category": "electrical",
            "required_tags": ["no_start"],
            "optional_tags": ["electrical_issue"],
            "dtcs_any": ["U0100", "U0140", "U0151", "B1325"],
            "checks": [
                "Battery load test and voltage drop on major grounds.",
                "Check module communication and wake-up behavior.",
                "Inspect fuse block power/ground feeds.",
            ],
            "likely_causes": [
                "Low voltage / battery issue",
                "Ground issue",
                "Network communication issue",
                "Fuse block / power distribution issue",
            ],
            "base_weight": 1.18,
        },
    ]


def seed_kb(session: Session, force_refresh: bool = False) -> None:
    existing = {
        r.name: r
        for r in session.exec(select(TriageRule)).all()
    }

    for data in _rule_data():
        row = existing.get(data["name"])
        if row and not force_refresh:
            continue

        if row:
            for k, v in data.items():
                setattr(row, k, v)
            session.add(row)
        else:
            session.add(TriageRule(**data))

    session.commit()
