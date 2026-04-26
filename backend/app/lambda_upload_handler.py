"""SQS-triggered Lambda: download staging object, run finalize_sheet_upload, persist job outcome."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

JOB_QUEUED = "queued"
JOB_PROCESSING = "processing"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"


def _bootstrap_secrets_from_arns() -> None:
    """Load DATABASE_URL / OPENROUTER_API_KEY from Secrets Manager before importing app settings."""
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    sm = boto3.client("secretsmanager", region_name=region)
    db_arn = (os.environ.get("LAMBDA_DATABASE_SECRET_ARN") or "").strip()
    if db_arn:
        os.environ["DATABASE_URL"] = sm.get_secret_value(SecretId=db_arn)["SecretString"]
    or_arn = (os.environ.get("LAMBDA_OPENROUTER_SECRET_ARN") or "").strip()
    if or_arn:
        os.environ["OPENROUTER_API_KEY"] = sm.get_secret_value(SecretId=or_arn)["SecretString"]


def _detail_to_text(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail)
    except (TypeError, ValueError):
        return str(detail)


async def _mark_failed(job_id: str, message: str, detail: Any | None) -> None:
    from app.db.models import UploadAsyncJob
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = await session.get(UploadAsyncJob, job_id)
        if row is None:
            return
        row.status = JOB_FAILED
        row.error_message = message
        row.result_json = {"detail": detail} if detail is not None else None
        await session.commit()


async def _process_job_id(job_id: str) -> None:
    from fastapi import HTTPException

    from app.core.config import settings
    from app.db.models import UploadAsyncJob
    from app.db.session import AsyncSessionLocal
    from app.services.consensus_engine import process_cluster_consensus
    from app.services import object_storage
    from app.services.upload_finalize import finalize_sheet_upload

    async with AsyncSessionLocal() as session:
        job = await session.get(UploadAsyncJob, job_id)
        if job is None:
            logger.warning("upload worker: unknown job_id=%s", job_id)
            return
        if job.status == JOB_COMPLETED:
            return
        if job.status != JOB_QUEUED:
            logger.info(
                "upload worker: skip job_id=%s status=%s (expected %s)",
                job_id,
                job.status,
                JOB_QUEUED,
            )
            return

        job.status = JOB_PROCESSING
        staging_key = job.staging_key
        election_id = job.election_id
        pu_id = job.pu_id
        original_filename = job.original_filename
        meta_str = json.dumps(job.metadata_json) if job.metadata_json is not None else None
        await session.commit()

    image_bytes = await object_storage.aget_bytes(
        use_s3=True,
        local_base=settings.uploads_dir,
        bucket=settings.AWS_S3_BUCKET.strip(),
        relative_key=staging_key,
    )
    if not image_bytes:
        await _mark_failed(job_id, "Staging object missing or unreadable", None)
        return

    try:
        async with AsyncSessionLocal() as session:
            result = await finalize_sheet_upload(
                session,
                image_bytes_original=image_bytes,
                election_id=election_id,
                pu_id=pu_id,
                metadata=meta_str,
                original_filename=original_filename,
            )
            cluster_id = result.get("cluster_id")
            if isinstance(cluster_id, int):
                try:
                    consensus_out = await process_cluster_consensus(session, cluster_id)
                    result["consensus_status"] = consensus_out.get("status")
                    if "confidence_score" in consensus_out:
                        result["consensus_confidence"] = consensus_out["confidence_score"]
                except Exception as e:  # noqa: BLE001
                    # Do not fail proof ingestion when consensus extraction is flaky; expose in job payload.
                    logger.exception(
                        "upload worker: consensus processing failed for cluster_id=%s job_id=%s",
                        cluster_id,
                        job_id,
                    )
                    result["consensus_status"] = "DISPUTED"
                    result["consensus_error"] = (
                        str(e).strip() or f"{type(e).__name__} (no message)"
                    )
            job_row = await session.get(UploadAsyncJob, job_id)
            if job_row is None:
                await session.rollback()
                return
            job_row.status = JOB_COMPLETED
            job_row.result_json = result
            job_row.error_message = None
            await session.commit()
    except HTTPException as e:
        await _mark_failed(job_id, _detail_to_text(e.detail), e.detail)
        logger.info("upload worker: job_id=%s HTTP %s", job_id, e.status_code)
        return
    except Exception:
        logger.exception("upload worker: job_id=%s unexpected error", job_id)
        await _mark_failed(job_id, "Internal error during finalize_sheet_upload", None)
        return

    try:
        await object_storage.adelete_bytes(
            use_s3=True,
            local_base=settings.uploads_dir,
            bucket=settings.AWS_S3_BUCKET.strip(),
            relative_key=staging_key,
        )
    except Exception:
        logger.exception("upload worker: failed to delete staging key=%s", staging_key)


async def _async_handler(event: dict[str, Any]) -> None:
    records = event.get("Records") or []
    for rec in records:
        body_raw = rec.get("body") or "{}"
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            logger.warning("upload worker: invalid SQS body: %s", body_raw[:200])
            continue
        job_id = body.get("job_id")
        if not job_id or not isinstance(job_id, str):
            logger.warning("upload worker: missing job_id in body")
            continue
        await _process_job_id(job_id.strip())


async def _async_handler_with_db_teardown(event: dict[str, Any]) -> None:
    """Run SQS work then dispose the async engine before the event loop closes."""
    try:
        await _async_handler(event)
    finally:
        try:
            from app.db.session import engine

            await engine.dispose()
        except Exception:
            logger.exception("upload worker: engine.dispose() after invocation failed")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    _bootstrap_secrets_from_arns()
    asyncio.run(_async_handler_with_db_teardown(event))
    return {"ok": True}
