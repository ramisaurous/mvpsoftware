# app/models/triage_rule.py
from __future__ import annotations

from typing import List, Optional

from sqlmodel import SQLModel, Field, Column, JSON


class TriageRule(SQLModel, table=True):
    """
    KB rule stored in DB.

    required_tags: must all match for rule to be considered.
    optional_tags: boosts score if present.
    contexts_any: boosts if any context matches (e.g. when_braking).
    min_speed_mph: boosts if extracted speed_min_mph >= threshold.
    dtcs_any: boosts if any DTC overlaps.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    category: str = "general"

    required_tags: List[str] = Field(sa_column=Column(JSON), default_factory=list)
    optional_tags: List[str] = Field(sa_column=Column(JSON), default_factory=list)
    contexts_any: List[str] = Field(sa_column=Column(JSON), default_factory=list)

    min_speed_mph: Optional[int] = None
    dtcs_any: List[str] = Field(sa_column=Column(JSON), default_factory=list)

    checks: List[str] = Field(sa_column=Column(JSON), default_factory=list)
    likely_causes: List[str] = Field(sa_column=Column(JSON), default_factory=list)

    base_weight: float = 1.0
