# app/core/models.py
from __future__ import annotations

from sqlmodel import SQLModel

# Import all SQLModel(table=True) models so they register with SQLModel.metadata
from app.models.case import Case  # noqa: F401
from app.models.action import Action  # noqa: F401
from app.models.scan import Scan  # noqa: F401

# ADD this for the Knowledge Base:
from app.models.triage_rule import TriageRule  # noqa: F401
