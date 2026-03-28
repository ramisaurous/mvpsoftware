# app/models/case.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from sqlmodel import SQLModel, Field, Column, JSON


class RepairCase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    vin: str = Field(index=True)
    year: Optional[int] = Field(default=None, index=True)
    make: Optional[str] = Field(default=None, index=True)
    model_family: Optional[str] = Field(default=None, index=True)
    platform: Optional[str] = Field(default=None, index=True)

    engine: Optional[str] = Field(default=None, index=True)  # L84/L87/etc
    mileage: Optional[int] = None

    dtcs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    symptoms: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    scan_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    triage_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    outcome: Optional[str] = None  # e.g., "fixed", "recheck", "no_fault_found"
    confirmed_cause: Optional[str] = None
    notes: Optional[str] = None


class ServiceAction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, foreign_key="repaircase.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    action_type: str = Field(index=True)  # "diagnostic", "programming", "repair", "inspection"
    title: str
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Approval gate
    status: str = Field(default="draft", index=True)  # draft -> pending_approval -> approved -> completed/rejected
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class UploadedAsset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: Optional[int] = Field(default=None, index=True, foreign_key="repaircase.id")

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    kind: str = Field(default="screenshot", index=True)  # screenshot placeholder
