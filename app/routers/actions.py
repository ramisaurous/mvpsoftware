# app/routers/actions.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import select

from app.core.db import get_session
from app.models.case import RepairCase, ServiceAction

router = APIRouter(tags=["actions"])


class ActionCreateIn(BaseModel):
    action_type: str = PField(description="diagnostic | programming | repair | inspection")
    title: str
    details: dict[str, Any] = PField(default_factory=dict)


class ActionApproveIn(BaseModel):
    approved_by: str


@router.post("/cases/{case_id}/actions")
def create_action(case_id: int, payload: ActionCreateIn) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        action = ServiceAction(
            case_id=case_id,
            action_type=payload.action_type.strip().lower(),
            title=payload.title.strip(),
            details=payload.details or {},
            status="draft",
        )
        session.add(action)
        session.commit()
        session.refresh(action)
        return {"action": action.model_dump()}


@router.post("/actions/{action_id}/submit")
def submit_for_approval(action_id: int) -> dict[str, Any]:
    with get_session() as session:
        action = session.get(ServiceAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="action_not_found")
        if action.status != "draft":
            raise HTTPException(status_code=400, detail="invalid_state")

        action.status = "pending_approval"
        session.add(action)
        session.commit()
        session.refresh(action)
        return {"action": action.model_dump()}


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: int, payload: ActionApproveIn) -> dict[str, Any]:
    with get_session() as session:
        action = session.get(ServiceAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="action_not_found")
        if action.status != "pending_approval":
            raise HTTPException(status_code=400, detail="invalid_state")

        action.status = "approved"
        action.approved_by = payload.approved_by.strip()
        action.approved_at = datetime.utcnow()
        session.add(action)
        session.commit()
        session.refresh(action)
        return {"action": action.model_dump()}


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: int, reason: str = "rejected") -> dict[str, Any]:
    with get_session() as session:
        action = session.get(ServiceAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="action_not_found")
        if action.status not in ("pending_approval", "approved"):
            raise HTTPException(status_code=400, detail="invalid_state")

        action.status = "rejected"
        action.details = {**(action.details or {}), "rejection_reason": reason}
        session.add(action)
        session.commit()
        session.refresh(action)
        return {"action": action.model_dump()}


@router.post("/actions/{action_id}/complete")
def complete_action(action_id: int) -> dict[str, Any]:
    with get_session() as session:
        action = session.get(ServiceAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="action_not_found")
        if action.status != "approved":
            raise HTTPException(status_code=400, detail="must_be_approved")

        action.status = "completed"
        action.completed_at = datetime.utcnow()
        session.add(action)
        session.commit()
        session.refresh(action)
        return {"action": action.model_dump()}


@router.get("/cases/{case_id}/actions")
def list_case_actions(case_id: int) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        stmt = select(ServiceAction).where(ServiceAction.case_id == case_id).order_by(ServiceAction.created_at.desc())
        rows = session.exec(stmt).all()
        return {"actions": [r.model_dump() for r in rows]}
