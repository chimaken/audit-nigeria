from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.upload_finalize import finalize_sheet_upload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["uploads"])


@router.post("/upload")
async def create_upload(
    session: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    election_id: int = Form(...),
    pu_id: int | None = Form(None),
    metadata: str | None = Form(None),
) -> dict:
    image_bytes_original = await file.read()
    return await finalize_sheet_upload(
        session,
        image_bytes_original=image_bytes_original,
        election_id=election_id,
        pu_id=pu_id,
        metadata=metadata,
        original_filename=file.filename,
    )
