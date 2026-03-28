# app/routers/scans.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlmodel import select

from app.core.db import get_session
from app.core.scan_parser import parse_scan_bytes
from app.models.case import RepairCase

router = APIRouter(tags=["scans"])


@router.post("/cases/{case_id}/scan-import")
async def import_scan(case_id: int, scan_file: UploadFile = File(...)) -> dict[str, Any]:
    content = await scan_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")

    parsed = parse_scan_bytes(scan_file.filename, content)

    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        # Merge DTCs into case
        dtc_set = set([d.upper() for d in (case.dtcs or [])])
        for d in parsed.dtcs:
            dtc_set.add(d.upper())
        case.dtcs = sorted(dtc_set)

        case.scan_metadata = {
            "uploaded_filename": scan_file.filename,
            "content_type": scan_file.content_type,
            "parsed": parsed.raw_summary,
        }
        case.updated_at = datetime.utcnow()
        session.add(case)
        session.commit()
        session.refresh(case)

        return {"case": case.model_dump(), "parsed_dtcs": parsed.dtcs}


@router.get("/dtc-scan")
def extract_dtcs_from_text(text: str) -> dict[str, Any]:
    # convenience endpoint for quick paste-in scans
    parsed = parse_scan_bytes("paste.txt", text.encode("utf-8", errors="ignore"))
    return {"dtcs": parsed.dtcs, "summary": parsed.raw_summary}


@router.get("/cases/by-dtc/{dtc}")
def cases_by_dtc(dtc: str, limit: int = 50) -> dict[str, Any]:
    dtc = dtc.strip().upper()
    limit = max(1, min(200, limit))

    with get_session() as session:
        stmt = select(RepairCase).order_by(RepairCase.created_at.desc()).limit(limit)
        rows = session.exec(stmt).all()
        matched = [c for c in rows if dtc in (c.dtcs or [])]
        return {"dtc": dtc, "cases": [c.model_dump() for c in matched]}
