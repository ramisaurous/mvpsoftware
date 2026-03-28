# app/routers/uploads.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlmodel import select

from app.core.config import settings
from app.core.db import get_session
from app.models.case import RepairCase, UploadedAsset

router = APIRouter(tags=["uploads"])


def _safe_filename(name: str) -> str:
    keep = []
    for ch in (name or ""):
        if ch.isalnum() or ch in (".", "-", "_"):
            keep.append(ch)
    out = "".join(keep).strip("._")
    return out or "upload.bin"


@router.post("/cases/{case_id}/screenshots")
async def upload_screenshot(case_id: int, file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty_file")

    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(status_code=413, detail=f"file_too_large>{settings.max_upload_mb}MB")

    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        os.makedirs(settings.storage_dir, exist_ok=True)
        fname = _safe_filename(file.filename)
        stamped = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_path = os.path.join(settings.storage_dir, f"case_{case_id}_{stamped}_{fname}")

        with open(storage_path, "wb") as f:
            f.write(raw)

        asset = UploadedAsset(
            case_id=case_id,
            filename=fname,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(raw),
            storage_path=storage_path,
            kind="screenshot",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return {"asset": asset.model_dump()}


@router.get("/cases/{case_id}/assets")
def list_assets(case_id: int) -> dict[str, Any]:
    with get_session() as session:
        case = session.get(RepairCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case_not_found")

        stmt = select(UploadedAsset).where(UploadedAsset.case_id == case_id).order_by(UploadedAsset.created_at.desc())
        rows = session.exec(stmt).all()
        return {"assets": [r.model_dump() for r in rows]}
