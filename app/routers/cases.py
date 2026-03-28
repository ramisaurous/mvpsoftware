# app/routers/cases.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field as PField

from sqlmodel import select

from app.core.db import get_session
from app.core.vin import decode_vin
from app.core.triage import triage
from app.models.case import RepairCase

router = APIRouter(tags=["cases"])


class CaseCreateIn(BaseModel):
    vin: str
    engine: str | None = PField(default=None, description="e.g., L84 or L87")
    mileage: int | None = None
    dtcs: list[str] = PField(default_factory=list)
    symptoms: list[str] = PField(default_factory=list)
    notes: str | None = None


class CaseUpdateIn(BaseModel):
    engine: str | None = None
    mileage: int | None = None
    dtcs: list[str] | None = None
    symptoms: list[str] | None = None
    notes: str | None = None
    outcome: str | None = None
    confirmed_cause: str | None = None


@router.post("/cases")
def create_case(payload: CaseCreateIn) -> dict[str, Any]:
    vin_info = decode_vin(payload.vin)

    if vin_info.year is None and "VIN must be 17 chars" in vin_info.notes:
        raise HTTPException(status_code=400, detail={"error": "invalid_vin", "notes": vin_info.notes})

    with get_session() as session:
        case = RepairCase(
            vin=vin_info.vin,
            year=vin_info.year,
            make=vin_info.make,
            model_family=vin_info.model_family,
            platform=vin_info.platform,
            engine=(payload.engine or "").upper() or None,
            mileage=payload.mileage,
            dtcs=[d.upper() for d in payload.dtcs],
            symptoms=[s.strip() for s in payload.symptoms],
            notes=payload.notes,
        )
        session.add(case)
        session.commit()
        session.refresh(case)

        # initial triage snapshot
        learned = _load_learning_weights(session)
        hits = triage(case.dtcs, case.symptoms, case.platform, case.engine, learned_weights=learned)
        case.triage_snapshot = {"hits": [h.__dict__ for h in hits]}
        case.updated_at = datetime.utcnow()
        session.add(case)
        session.commit()
        session.refresh(case)

        return {"case": case.model_dump()}


@router.get("/cases/{case_id}")
def get_case(case_id: int) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")
        return {"case": case.model_dump()}


@router.get("/cases")
def list_cases(limit: int = 50, offset: int = 0, vin: str | None = None) -> dict[str, Any]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    with get_session() as session:
        stmt = select(RepairCase).order_by(RepairCase.created_at.desc()).offset(offset).limit(limit)
        if vin:
            stmt = stmt.where(RepairCase.vin == vin.strip().upper())
        rows = session.exec(stmt).all()
        return {"cases": [r.model_dump() for r in rows], "limit": limit, "offset": offset}


@router.post("/cases/{case_id}/triage")
def run_triage(case_id: int) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        learned = _load_learning_weights(session)
        hits = triage(case.dtcs, case.symptoms, case.platform, case.engine, learned_weights=learned)
        case.triage_snapshot = {"hits": [h.__dict__ for h in hits]}
        case.updated_at = datetime.utcnow()
        session.add(case)
        session.commit()
        session.refresh(case)
        return {"triage": case.triage_snapshot, "case": case.model_dump()}


@router.patch("/cases/{case_id}")
def update_case(case_id: int, payload: CaseUpdateIn) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        if payload.engine is not None:
            case.engine = payload.engine.upper() or None
        if payload.mileage is not None:
            case.mileage = payload.mileage
        if payload.dtcs is not None:
            case.dtcs = [d.upper() for d in payload.dtcs]
        if payload.symptoms is not None:
            case.symptoms = [s.strip() for s in payload.symptoms]
        if payload.notes is not None:
            case.notes = payload.notes
        if payload.outcome is not None:
            case.outcome = payload.outcome
        if payload.confirmed_cause is not None:
            case.confirmed_cause = payload.confirmed_cause

        case.updated_at = datetime.utcnow()
        session.add(case)
        session.commit()
        session.refresh(case)

        # Update “learning” when outcome + confirmed cause are set
        if case.outcome and case.confirmed_cause:
            _apply_learning(session, case)
            session.commit()

        return {"case": case.model_dump()}


def _load_learning_weights(session) -> dict[str, float]:
    """
    Lightweight “learning”: derive per-rule multipliers from historical cases
    where outcome == "fixed" and triage hits included the rule_id.
    """
    stmt = select(RepairCase).where(RepairCase.outcome == "fixed")
    fixed = session.exec(stmt).all()

    totals: dict[str, int] = {}
    wins: dict[str, int] = {}
    for c in fixed:
        hits = (c.triage_snapshot or {}).get("hits") or []
        if not isinstance(hits, list):
            continue
        for h in hits:
            rid = (h or {}).get("rule_id")
            if not rid:
                continue
            totals[rid] = totals.get(rid, 0) + 1
            # if confirmed cause text is non-empty, count as “win” for top 2 hits only
            # to avoid boosting every matched rule
            pass

        # Boost only top 2 rules when fixed
        top2 = [h.get("rule_id") for h in hits[:2] if isinstance(h, dict) and h.get("rule_id")]
        for rid in top2:
            wins[rid] = wins.get(rid, 0) + 1

    weights: dict[str, float] = {}
    for rid, t in totals.items():
        w = wins.get(rid, 0)
        # Laplace-smoothed win-rate -> multiplier in ~[0.85, 1.25]
        rate = (w + 1) / (t + 2)
        mult = 0.85 + 0.4 * rate
        weights[rid] = round(mult, 4)
    return weights


def _apply_learning(session, case: RepairCase) -> None:
    """
    No persistent model table; learning is computed dynamically.
    This hook exists for future expansion and to validate inputs now.
    """
    _ = session
    if not case.triage_snapshot:
        return
    # Nothing to store; dynamic computation reads case history.
    return
