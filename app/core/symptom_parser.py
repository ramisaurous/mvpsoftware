# app/core/symptom_parser.py
"""
Lightweight symptom parsing for triage ranking.

Why:
- `app.core.triage` expects `ParsedSymptoms` + `parse_symptoms()`.
- Railway is crashing because this module does not exist.

This parser is intentionally simple: tags + contexts + a few numeric attrs.
You can expand the keyword maps as you learn your fleet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_SPEED_RE = re.compile(
    r"(?P<num>\d{1,3})\s*(?P<unit>mph|kph|kmh)\b", re.IGNORECASE
)
_OVER_RE = re.compile(
    r"\b(over|above|greater\s+than|gt|>=)\s*(?P<num>\d{1,3})\b", re.IGNORECASE
)
_UNDER_RE = re.compile(
    r"\b(under|below|less\s+than|lt|<=)\s*(?P<num>\d{1,3})\b", re.IGNORECASE
)


_TAG_KEYWORDS: dict[str, list[str]] = {
    "noise": ["noise", "whine", "hum", "growl", "squeal", "rattle", "clunk", "knock"],
    "vibration": ["vibration", "vibrate", "shake", "shudder"],
    "pull": ["pull", "drift", "steer left", "steer right", "wanders"],
    "misfire": ["misfire", "rough idle", "stumble", "hesitation"],
    "no_start": ["no start", "won't start", "won’t start", "cranks but no", "dead"],
    "stall": ["stall", "stalls", "dies"],
    "overheat": ["overheat", "hot", "temp high", "temperature high"],
    "brake": ["brake", "braking", "pedal", "rotor", "caliper"],
}


_CONTEXT_KEYWORDS: dict[str, list[str]] = {
    "idle": ["idle", "at idle", "idling"],
    "accel": ["accel", "accelerat", "throttle", "on gas", "under load"],
    "decel": ["decel", "coast", "off gas", "lift off", "let off"],
    "turning": ["turn", "turning", "corner", "left turn", "right turn"],
    "highway": ["highway", "freeway", "speed", "cruise"],
    "cold": ["cold start", "cold", "first thing", "morning"],
    "hot": ["hot", "warm", "heat soaked"],
}


@dataclass(frozen=True)
class ParsedSymptoms:
    """Normalized symptom signals extracted from free text."""
    tags: list[str]
    attrs: dict[str, Any]


def parse_symptoms(text: str) -> ParsedSymptoms:
    """
    Parse symptoms from free text into:
    - tags: coarse symptom categories (noise/vibration/etc.)
    - attrs: structured hints (contexts, speed_min_mph, speed_max_mph)
    """
    raw = (text or "").strip()
    t = raw.lower()

    tags = _extract_keywords(t, _TAG_KEYWORDS)
    contexts = _extract_keywords(t, _CONTEXT_KEYWORDS)

    attrs: dict[str, Any] = {}
    if contexts:
        attrs["contexts"] = contexts

    speed_min_mph, speed_max_mph = _extract_speed_bounds_mph(t)
    if speed_min_mph is not None:
        attrs["speed_min_mph"] = speed_min_mph
    if speed_max_mph is not None:
        attrs["speed_max_mph"] = speed_max_mph

    return ParsedSymptoms(tags=tags, attrs=attrs)


def _extract_keywords(text: str, mapping: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for key, needles in mapping.items():
        if any(n in text for n in needles):
            out.append(key)
    return out


def _extract_speed_bounds_mph(text: str) -> tuple[int | None, int | None]:
    """
    Extract rough speed bounds in MPH.

    Supports:
    - "vibration over 60 mph"
    - "shakes above 90 kmh"
    - "noise under 30mph"
    """
    min_mph: int | None = None
    max_mph: int | None = None

    for m in _SPEED_RE.finditer(text):
        num = int(m.group("num"))
        unit = m.group("unit").lower()
        mph = num if unit == "mph" else int(round(num * 0.621371))
        # Bare "60 mph" is ambiguous; treat as minimum hint.
        min_mph = mph if min_mph is None else min(min_mph, mph)

    m_over = _OVER_RE.search(text)
    if m_over:
        v = int(m_over.group("num"))
        min_mph = v if min_mph is None else max(min_mph, v)

    m_under = _UNDER_RE.search(text)
    if m_under:
        v = int(m_under.group("num"))
        max_mph = v if max_mph is None else min(max_mph, v)

    return min_mph, max_mph
