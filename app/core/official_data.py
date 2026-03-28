# app/core/official_data.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

NHTSA_API_BASE = "https://api.nhtsa.gov"
USER_AGENT = "gm-suv-shop-grade/1.0"

_COMPONENT_MAP = {
    "ENGINE": "engine",
    "ENGINE AND ENGINE COOLING": "engine",
    "FUEL/PROPULSION SYSTEM": "fuel",
    "ELECTRICAL SYSTEM": "electrical",
    "POWER TRAIN": "powertrain",
    "SERVICE BRAKES": "brakes",
    "UNKNOWN OR OTHER": "other",
}

_SYMPTOM_KEYWORDS = {
    "stall": ["stall", "stalls", "stalled", "shut off", "shuts off", "dies", "died"],
    "idle": ["idle", "rough idle", "unstable idle"],
    "misfire": ["misfire", "misfiring"],
    "vibration": ["vibration", "shake", "shudder"],
    "hard_start": ["hard start", "long crank", "extended crank", "crank no start"],
    "no_start": ["no start", "won't start", "will not start"],
    "hesitation": ["hesitation", "hesitate", "bog", "bogging"],
    "low_power": ["lack of power", "no power", "reduced power", "low power"],
}

@dataclass
class OfficialSignal:
    label: str
    score_boost: float
    evidence: list[str]
    matched_terms: list[str]


def _safe_get_json(url: str, timeout: int = 5) -> dict[str, Any] | list[Any] | None:
    try:
        req = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)
    except Exception:
        return None


def _clean_model_name(model_family: str | None) -> str | None:
    if not model_family:
        return None

    raw = model_family.strip().lower()
    aliases = {
        "suburban": "Suburban",
        "tahoe": "Tahoe",
        "yukon": "Yukon",
        "yukon xl": "Yukon XL",
        "escalade": "Escalade",
        "escalade esv": "Escalade ESV",
    }
    return aliases.get(raw, model_family.strip())


def _normalize_make(make: str | None) -> str | None:
    if not make:
        return None
    make = make.strip().lower()
    aliases = {
        "gm": "CHEVROLET",
        "chevy": "CHEVROLET",
        "chevrolet": "CHEVROLET",
        "gmc": "GMC",
        "cadillac": "CADILLAC",
    }
    return aliases.get(make, make.upper())


def _extract_complaint_matches(summary: str) -> set[str]:
    text = (summary or "").lower()
    matched: set[str] = set()
    for label, terms in _SYMPTOM_KEYWORDS.items():
        if any(term in text for term in terms):
            matched.add(label)
    return matched


def _component_bucket(component: str | None) -> str:
    if not component:
        return "other"
    return _COMPONENT_MAP.get(component.strip().upper(), "other")


def get_official_signals(
    *,
    year: int | None,
    make: str | None,
    model_family: str | None,
    dtcs: list[str],
    symptom_tags: set[str],
) -> list[OfficialSignal]:
    """
    Pull lightweight public signals from NHTSA.
    This is enrichment, not the primary diagnosis source.
    """
    if not year or not make or not model_family:
        return []

    clean_make = _normalize_make(make)
    clean_model = _clean_model_name(model_family)
    if not clean_make or not clean_model:
        return []

    recalls_url = (
        f"{NHTSA_API_BASE}/recalls/recallsByVehicle"
        f"?make={quote(clean_make)}&model={quote(clean_model)}&modelYear={year}"
    )
    complaints_url = (
        f"{NHTSA_API_BASE}/complaints/complaintsByVehicle"
        f"?make={quote(clean_make)}&model={quote(clean_model)}&modelYear={year}"
    )

    recalls_payload = _safe_get_json(recalls_url) or {}
    complaints_payload = _safe_get_json(complaints_url) or []

    recalls = recalls_payload.get("results", []) if isinstance(recalls_payload, dict) else []
    complaints = complaints_payload if isinstance(complaints_payload, list) else []

    signals: list[OfficialSignal] = []

    # Recall summary signal
    if recalls:
        recent_recalls = recalls[:3]
        evidence = []
        for r in recent_recalls:
            campaign = (r.get("NHTSACampaignNumber") or "").strip()
            summary = re.sub(r"\s+", " ", (r.get("Summary") or "").strip())
            if campaign and summary:
                evidence.append(f"NHTSA recall {campaign}: {summary[:180]}")
        if evidence:
            signals.append(
                OfficialSignal(
                    label="official_recall_context",
                    score_boost=0.08,
                    evidence=evidence,
                    matched_terms=[],
                )
            )

    # Complaint trend signal
    matched_complaints = []
    component_counter: Counter[str] = Counter()
    symptom_counter: Counter[str] = Counter()

    for item in complaints[:250]:
        summary = (item.get("summary") or item.get("SUMMARY") or "").strip()
        component = item.get("components") or item.get("COMPONENTS") or ""
        matches = _extract_complaint_matches(summary)

        if matches & symptom_tags:
            matched_complaints.append(item)

        component_counter[_component_bucket(component)] += 1
        for m in matches:
            symptom_counter[m] += 1

    if matched_complaints:
        top_components = ", ".join(
            [name for name, _ in component_counter.most_common(3) if name != "other"][:2]
        ) or "engine"
        top_symptoms = ", ".join([name for name, _ in symptom_counter.most_common(3)])

        evidence = [
            (
                f"NHTSA complaints for {year} {clean_make} {clean_model} include "
                f"{len(matched_complaints)} reports matching this symptom pattern."
            ),
            f"Most common complaint buckets: {top_components}.",
        ]
        if top_symptoms:
            evidence.append(f"Repeated complaint keywords: {top_symptoms}.")

        signals.append(
            OfficialSignal(
                label="official_complaint_pattern",
                score_boost=min(0.18, 0.04 + (len(matched_complaints) / 100.0)),
                evidence=evidence,
                matched_terms=sorted(symptom_tags),
            )
        )

    # DTC-specific hinting from public context: weak but useful.
    if dtcs:
        dtc_evidence = [f"Input DTCs: {', '.join(sorted(set(dtcs)))}."]
        signals.append(
            OfficialSignal(
                label="dtc_context",
                score_boost=0.03,
                evidence=dtc_evidence,
                matched_terms=sorted(set(dtcs)),
            )
        )

    return signals
