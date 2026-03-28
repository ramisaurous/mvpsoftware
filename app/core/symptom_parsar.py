# app/core/symptom_parser.py
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ParsedSymptoms:
    """
    Broad symptom parser.

    - tags: normalized categories (vibration, noise, rough_idle, etc.)
    - attrs: structured attributes (speed_min_mph, contexts, etc.)
    - evidence: strings you can display to explain matching
    """

    tags: List[str]
    attrs: Dict[str, Any]
    evidence: List[str]


_TAG_SYNONYMS: Dict[str, List[str]] = {
    "vibration": ["vibration", "vibrate", "shudder", "shake", "shimmy", "buzz"],
    "noise": ["noise", "whine", "clunk", "rattle", "squeal", "grind", "hum", "humming", "growl"],
    "rough_idle": ["rough idle", "idles rough", "idle rough", "idle is rough"],
    "misfire": ["misfire", "misfiring", "missing", "running rough"],
    "hesitation": ["hesitation", "bog", "bogging", "stumble", "flat spot"],
    "surging": ["surging", "hunts", "hunting idle"],
    "pulling": ["pulling", "pulls", "drifts", "steers to one side"],
    "brake_pulsation": ["brake pulsation", "pulsing brake", "brake shake", "warped rotor"],
    "overheating": ["overheat", "overheating", "temp high", "runs hot"],
    "hard_start": ["hard start", "long crank", "extended crank"],
    "no_start": ["no start", "won't start", "will not start", "crank no start", "cranks but won't start"],
}


_CONTEXT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("when_braking", re.compile(r"\b(when|while)\s+brak(ing|e)\b", re.I)),
    ("when_accelerating", re.compile(r"\b(when|while)\s+accelerat(ing|e)\b", re.I)),
    ("when_decelerating", re.compile(r"\b(when|while)\s+decelerat(ing|e)\b", re.I)),
    ("when_turning", re.compile(r"\b(when|while)\s+turn(ing|s)?\b", re.I)),
    ("at_idle", re.compile(r"\b(at\s+idle|idling)\b", re.I)),
    ("cold_start", re.compile(r"\b(cold\s+start|first\s+start|morning)\b", re.I)),
]


_SPEED_RE = re.compile(
    r"""
    (?:
        over|above|at|around|about|>=|greater\s+than|more\s+than
    )?\s*
    (?P<speed>\d{1,3})
    \s*
    (?P<unit>mph|kph|km/h)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _to_mph(value: int, unit: Optional[str]) -> int:
    if not unit:
        return value
    u = unit.lower()
    if u == "mph":
        return value
    if u in {"kph", "km/h"}:
        return int(round(value * 0.621371))
    return value


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _contains_phrase(text: str, phrase: str) -> bool:
    t = text.lower()
    p = phrase.lower()
    if p in t:
        return True

    # fuzzy window match for short phrases
    words = re.findall(r"[a-z0-9']+", t)
    p_words = re.findall(r"[a-z0-9']+", p)
    if not words or not p_words:
        return False
    window = max(1, len(p_words))
    for i in range(0, len(words) - window + 1):
        chunk = " ".join(words[i : i + window])
        if _similar(chunk, p) >= 0.86:
            return True
    return False


def parse_symptoms(text: str) -> ParsedSymptoms:
    text = (text or "").strip()
    if not text:
        return ParsedSymptoms(tags=[], attrs={}, evidence=[])

    tags: List[str] = []
    evidence: List[str] = []
    attrs: Dict[str, Any] = {}

    for tag, phrases in _TAG_SYNONYMS.items():
        for phrase in phrases:
            if _contains_phrase(text, phrase):
                tags.append(tag)
                evidence.append(f"tag:{tag} via '{phrase}'")
                break

    contexts: List[str] = []
    for ctx, pat in _CONTEXT_PATTERNS:
        if pat.search(text):
            contexts.append(ctx)
            evidence.append(f"context:{ctx}")
    if contexts:
        attrs["contexts"] = sorted(set(contexts))

    speeds_mph: List[int] = []
    for m in _SPEED_RE.finditer(text):
        speed = int(m.group("speed"))
        speeds_mph.append(_to_mph(speed, m.group("unit")))
    if speeds_mph:
        attrs["speed_min_mph"] = max(speeds_mph)
        evidence.append(f"attr:speed_min_mph={attrs['speed_min_mph']}")

    if re.search(r"\bhighway\b", text, re.I):
        attrs.setdefault("speed_min_mph", 55)
        evidence.append("attr:speed_min_mph>=55 via 'highway'")

    return ParsedSymptoms(tags=sorted(set(tags)), attrs=attrs, evidence=evidence)
