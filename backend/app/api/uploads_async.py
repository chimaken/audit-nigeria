from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import Election, UploadAsyncJob
from app.services import object_storage
from app.services.upload_finalize import mime_from_filename

logger = logging.getLogger(__name__)
router = APIRouter(tags=["uploads"])

JOB_AWAITING = "awaiting_upload"
JOB_QUEUED = "queued"
JOB_PROCESSING = "processing"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
_AWS_CONNECTIVITY_TIMEOUT_SEC = 10.0


def _async_upload_configured() -> bool:
    return bool(settings.use_s3_uploads and settings.UPLOAD_JOBS_QUEUE_URL.strip())


def _ext_from_filename(name: str | None) -> str:
    ext = Path(name or "image.jpg").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        ext = ".jpg"
    return ext


def _send_sqs_job_message(job_id: str) -> None:
    q = settings.UPLOAD_JOBS_QUEUE_URL.strip()
    cfg = Config(
        connect_timeout=5,
        read_timeout=8,
        retries={"mode": "standard", "max_attempts": 2},
    )
    boto3.client("sqs", region_name=settings.AWS_REGION, config=cfg).send_message(
        QueueUrl=q,
        MessageBody=json.dumps({"job_id": job_id}),
    )


class PresignBody(BaseModel):
    election_id: int
    pu_id: int | None = None
    metadata: Any | None = None
    filename: str | None = Field(default=None, description="Original filename (used for extension / mime).")


class PresignResponse(BaseModel):
    job_id: str
    staging_key: str
    upload_url: str
    headers: dict[str, str]
    expires_in: int


class CompleteBody(BaseModel):
    job_id: str


class CompleteResponse(BaseModel):
    job_id: str
    status: str


def _normalize_metadata(metadata: Any | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if isinstance(metadata, str):
        s = metadata.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="metadata must be valid JSON") from e
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="metadata JSON must be an object")
        return parsed
    if isinstance(metadata, dict):
        return metadata
    raise HTTPException(status_code=400, detail="metadata must be a JSON object or JSON string")


@router.post("/upload/async/presign", response_model=PresignResponse)
async def presign_async_upload(
    body: PresignBody,
    session: AsyncSession = Depends(get_db),
) -> PresignResponse:
    if not _async_upload_configured():
        raise HTTPException(
            status_code=503,
            detail="Async uploads require S3 (AWS_S3_BUCKET) and UPLOAD_JOBS_QUEUE_URL.",
        )
    metadata_obj = _normalize_metadata(body.metadata)
    election = await session.get(Election, body.election_id)
    if election is None:
        raise HTTPException(status_code=404, detail="Election not found")

    job_id = uuid.uuid4().hex
    ext = _ext_from_filename(body.filename)
    staging_key = f"staging/{job_id}/original{ext}"
    content_type = mime_from_filename(body.filename)

    job = UploadAsyncJob(
        id=job_id,
        status=JOB_AWAITING,
        election_id=body.election_id,
        pu_id=body.pu_id,
        staging_key=staging_key,
        original_filename=body.filename,
        metadata_json=metadata_obj,
    )
    session.add(job)

    upload_url = await asyncio.to_thread(
        object_storage.generate_presigned_put_url,
        settings.AWS_S3_BUCKET.strip(),
        staging_key,
        content_type,
        settings.UPLOAD_PRESIGN_EXPIRES_SECONDS,
    )
    return PresignResponse(
        job_id=job_id,
        staging_key=staging_key,
        upload_url=upload_url,
        headers={"Content-Type": content_type},
        expires_in=settings.UPLOAD_PRESIGN_EXPIRES_SECONDS,
    )


@router.post("/upload/async/complete", response_model=CompleteResponse)
async def complete_async_upload(
    body: CompleteBody,
    session: AsyncSession = Depends(get_db),
) -> CompleteResponse:
    if not _async_upload_configured():
        raise HTTPException(
            status_code=503,
            detail="Async uploads require S3 (AWS_S3_BUCKET) and UPLOAD_JOBS_QUEUE_URL.",
        )
    job = await session.get(UploadAsyncJob, body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JOB_AWAITING:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not awaiting upload (current status: {job.status})",
        )

    try:
        exists = await asyncio.wait_for(
            object_storage.aexists(
                use_s3=True,
                local_base=settings.uploads_dir,
                bucket=settings.AWS_S3_BUCKET.strip(),
                relative_key=job.staging_key,
            ),
            timeout=_AWS_CONNECTIVITY_TIMEOUT_SEC,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Timed out checking staging object in S3. "
                "Verify App Runner egress (NAT/route table) and retry."
            ),
        ) from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Failed checking staging object in S3: {type(e).__name__}",
        ) from None
    if not exists:
        raise HTTPException(
            status_code=400,
            detail="Staging object not found; finish the S3 PUT before calling complete.",
        )

    job.status = JOB_QUEUED
    await session.flush()
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_send_sqs_job_message, job.id),
            timeout=_AWS_CONNECTIVITY_TIMEOUT_SEC,
        )
    except TimeoutError:
        job.status = JOB_AWAITING
        await session.flush()
        raise HTTPException(
            status_code=503,
            detail=(
                "Timed out enqueuing upload job to SQS. "
                "Verify App Runner egress (NAT/route table) and retry."
            ),
        ) from None
    except ClientError as e:
        logger.exception("SQS SendMessage failed for job %s", job.id)
        job.status = JOB_AWAITING
        await session.flush()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to enqueue upload job: {e}",
        ) from e

    return CompleteResponse(job_id=job.id, status=JOB_QUEUED)


@router.get("/upload/async/jobs/{job_id}")
async def get_async_upload_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await session.get(UploadAsyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    out: dict[str, Any] = {
        "id": job.id,
        "status": job.status,
        "election_id": job.election_id,
        "pu_id": job.pu_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
    if job.error_message:
        out["error_message"] = job.error_message
    if job.result_json is not None:
        out["result"] = job.result_json
    return out
