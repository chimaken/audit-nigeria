"""SQS-triggered Lambda: download staging object, run finalize_sheet_upload, persist job outcome."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text

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
    tg_arn = (os.environ.get("LAMBDA_TELEGRAM_BOT_SECRET_ARN") or "").strip()
    if tg_arn:
        os.environ["TELEGRAM_BOT_TOKEN"] = sm.get_secret_value(SecretId=tg_arn)["SecretString"]


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
            # Consensus + optional Telegram HIL alert run inside finalize_sheet_upload.
            cluster_id = result.get("cluster_id")
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
    except Exception as e:
        logger.exception("upload worker: job_id=%s unexpected error", job_id)
        msg = (str(e) or type(e).__name__).strip()
        detail: dict[str, str] = {
            "exception": type(e).__name__,
            "message": msg[:2000],
        }
        low = msg.lower()
        if "human_review_alert" in low or (
            "column" in low and "does not exist" in low
        ):
            detail["hint"] = (
                "Missing DB column? Apply backend/sql/patch_human_review_alert.sql "
                "(or set apply_human_review_sql_migration in Terraform once from a host that can reach RDS)."
            )
        await _mark_failed(
            job_id,
            f"Internal error during finalize_sheet_upload: {type(e).__name__}",
            detail,
        )
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


async def _run_human_review_alert_sql_patch() -> dict[str, Any]:
    """Execute backend/sql/patch_human_review_alert.sql (bundled as ./sql in the Lambda image)."""
    root = Path(__file__).resolve().parent.parent
    path = root / "sql" / "patch_human_review_alert.sql"
    if not path.is_file():
        raise FileNotFoundError(f"patch SQL missing at {path}")
    sql_body = path.read_text(encoding="utf-8")
    from app.db.session import engine

    verify_sql = text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'result_clusters' "
        "AND column_name = 'human_review_alert_sent_at'"
    )
    async with engine.begin() as conn:
        await conn.execute(text(sql_body))
        check = (await conn.execute(verify_sql)).scalar_one_or_none()
    if check != 1:
        raise RuntimeError(
            "Patch SQL ran but column human_review_alert_sent_at is still missing "
            "(wrong database or migration did not apply)."
        )
    logger.info("human_review_alert SQL patch applied and column verified (%s)", path.name)
    return {"executed": path.name, "column_verified": True}


async def _direct_invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    aws lambda invoke --function-name ... --payload '{"action":"patch_human_review_alert","admin_token":"..."}'
    Use when RDS is not reachable from your laptop (public subnet / SG / ISP) but Lambda VPC can reach RDS.

    Auth: if LAMBDA_ADMIN_PATCH_TOKEN is set on the function (Terraform upload_worker_admin_patch_token),
    admin_token in the payload must match. If unset, a non-empty admin_token is still required and
    access is enforced by IAM (lambda:InvokeFunction) — e.g. GitHub Actions with LAMBDA_ADMIN_PATCH_TOKEN secret.
    """
    try:
        if event.get("action") != "patch_human_review_alert":
            return {"ok": False, "error": "unknown_action"}
        expected = (os.environ.get("LAMBDA_ADMIN_PATCH_TOKEN") or "").strip()
        token_from_event = (str(event.get("admin_token") or "")).strip()
        if not token_from_event:
            return {"ok": False, "error": "forbidden"}
        if expected:
            if token_from_event != expected:
                return {"ok": False, "error": "forbidden"}
        else:
            logger.warning(
                "patch_human_review_alert: LAMBDA_ADMIN_PATCH_TOKEN unset on function; "
                "using payload token only (caller must be IAM-authorized to invoke). "
                "Set upload_worker_admin_patch_token in Terraform to require a matching env token."
            )
        out = await _run_human_review_alert_sql_patch()
        return {"ok": True, **out}
    except Exception as e:
        logger.exception("upload worker: direct admin patch failed")
        return {
            "ok": False,
            "error": type(e).__name__,
            "message": (str(e) or "")[:1500],
        }
    finally:
        try:
            from app.db.session import engine

            await engine.dispose()
        except Exception:
            logger.exception("upload worker: engine.dispose() after direct invoke failed")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    _bootstrap_secrets_from_arns()
    if event.get("Records"):
        asyncio.run(_async_handler_with_db_teardown(event))
        return {"ok": True}
    return asyncio.run(_direct_invoke_handler(event))
