"""Shared sheet upload finalization (blur, vision, S3, DB) for sync POST /upload and async Lambda workers."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Election, LGA, PollingUnit, ResultCluster, Upload
from app.services import ai_service, image_service, ingestion_logic, object_storage
from app.services.post_upload_consensus import run_consensus_after_upload

logger = logging.getLogger(__name__)


def slugify_fs(name: str) -> str:
    s = name.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_.-]", "", s)
    return s or "unknown"


def mime_from_filename(filename: str | None) -> str:
    p = (filename or "").lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    if p.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


async def finalize_sheet_upload(
    session: AsyncSession,
    *,
    image_bytes_original: bytes,
    election_id: int,
    pu_id: int | None,
    metadata: str | None,
    original_filename: str | None,
) -> dict:
    """
    Run the full upload pipeline after the raw file bytes are available.
    Raises HTTPException for client errors and OpenRouter failures (same as POST /upload).
    """
    if not image_bytes_original:
        raise HTTPException(status_code=400, detail="Empty file")

    image_bytes_original = image_service.normalize_image_orientation_bytes(
        image_bytes_original
    )

    _side, _bytes = (1400, 1_400_000) if pu_id is None else (2000, 2_200_000)
    analysis_bytes, analysis_mime_override = image_service.bytes_bounded_for_analysis(
        image_bytes_original,
        max_side=_side,
        max_bytes=_bytes,
    )
    vision_mime = analysis_mime_override or mime_from_filename(original_filename)

    try:
        blur = image_service.assess_blur_with_zoom(analysis_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not blur.passed:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Image too blurry after original + zoom checks",
                "minimum": blur.minimum,
                "effective_score": round(blur.effective_score, 2),
                "original_score": round(blur.original_score, 2),
                "best_strategy": blur.winning_strategy,
                "scores_by_strategy": {
                    name: round(score, 2) for name, score in blur.breakdown
                },
            },
        )

    try:
        phash_str = image_service.calculate_phash(image_bytes_original)
    except OSError as e:
        raise HTTPException(status_code=400, detail="Invalid image file") from e

    metadata_obj: dict | None = None
    if metadata is not None and metadata.strip():
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="metadata must be valid JSON") from e
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="metadata JSON must be an object")
        metadata_obj = parsed

    election = await session.get(Election, election_id)
    if election is None:
        raise HTTPException(status_code=404, detail="Election not found")

    if pu_id is None:
        if not settings.OPENROUTER_API_KEY:
            raise HTTPException(
                status_code=400,
                detail=(
                    "pu_id is required unless OPENROUTER_API_KEY is set "
                    "(AI reads the form header to resolve state, LGA, and polling unit)."
                ),
            )
        try:
            extraction = await ai_service.extract_results_from_image_bytes(
                analysis_bytes,
                mime=vision_mime,
            )
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            msg = ai_service.openrouter_connectivity_message(e)
            logger.warning(
                "OpenRouter vision extraction failed (election_id=%s): %s",
                election_id,
                msg,
                exc_info=False,
            )
            raise HTTPException(
                status_code=503,
                detail=f"Vision extraction failed (required for AI location): {msg}",
            ) from None
        except Exception as e:  # noqa: BLE001
            mod = getattr(e.__class__, "__module__", "") or ""
            if mod == "httpcore" or mod.startswith("httpcore."):
                msg = ai_service.openrouter_connectivity_message(e)
            else:
                msg = (str(e) or "").strip() or f"{type(e).__name__} (no message)"
            logger.warning(
                "OpenRouter vision extraction failed (election_id=%s): %s",
                election_id,
                msg,
                exc_info=False,
            )
            raise HTTPException(
                status_code=503,
                detail=f"Vision extraction failed (required for AI location): {msg}",
            ) from None
        fh = extraction.form_header
        if not fh.pu_code.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Could not read polling unit code from form header",
                    "form_header": fh.model_dump(),
                },
            )
        if not fh.state.strip() or not fh.lga.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "VLM must extract state and LGA from form header",
                    "form_header": fh.model_dump(),
                },
            )
        try:
            pu, ingest_warns = await ingestion_logic.resolve_pu_from_form_header(
                session,
                fh,
                metadata=metadata_obj,
                claimed_pu_code_from_db=None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        await session.flush()
        pu_id = pu.id
        merged: dict = dict(metadata_obj or {})
        merged["ai_form_header"] = fh.model_dump()
        if ingest_warns:
            merged.setdefault("ingestion_warnings", []).extend(ingest_warns)
            merged["ingestion_warnings"] = list(dict.fromkeys(merged["ingestion_warnings"]))
        metadata_obj = merged
        pu_stmt = (
            select(PollingUnit)
            .where(PollingUnit.id == pu_id)
            .options(selectinload(PollingUnit.lga).selectinload(LGA.state))
        )
        pu_for_path = (await session.execute(pu_stmt)).scalar_one()
    else:
        pu_stmt = (
            select(PollingUnit)
            .where(PollingUnit.id == pu_id)
            .options(selectinload(PollingUnit.lga).selectinload(LGA.state))
        )
        pu_for_path = (await session.execute(pu_stmt)).scalar_one_or_none()
        if pu_for_path is None:
            raise HTTPException(status_code=404, detail="Polling unit not found")
        if metadata_obj:
            try:
                nw = ingestion_logic.geospatial_mismatch_warnings(
                    metadata_obj,
                    ingestion_logic.normalize_pu_code(pu_for_path.pu_code),
                )
                if nw:
                    metadata_obj = dict(metadata_obj)
                    metadata_obj.setdefault("ingestion_warnings", []).extend(nw)
                    metadata_obj["ingestion_warnings"] = list(
                        dict.fromkeys(metadata_obj["ingestion_warnings"])
                    )
            except ValueError:
                pass

    match_stmt = (
        select(Upload)
        .join(ResultCluster, Upload.cluster_id == ResultCluster.id)
        .where(
            ResultCluster.pu_id == pu_id,
            ResultCluster.election_id == election_id,
        )
    )
    existing_uploads = (await session.execute(match_stmt)).scalars().all()

    cluster_id: int | None = None
    for row in existing_uploads:
        if image_service.phash_hamming(phash_str, row.phash) < 5:
            cluster_id = row.cluster_id
            break

    if cluster_id is None:
        cluster = ResultCluster(
            pu_id=pu_id,
            election_id=election_id,
            current_consensus_json=None,
            confidence_score=None,
        )
        session.add(cluster)
        await session.flush()
        cluster_id = cluster.id

    ext = Path(original_filename or "image").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"

    type_part = slugify_fs(election.type.value)
    state_part = slugify_fs(pu_for_path.lga.state.name)
    lga_part = slugify_fs(pu_for_path.lga.name)
    relative_dir = Path(type_part) / state_part / lga_part / str(pu_id)
    relative_image_path = (relative_dir / filename).as_posix()
    mime = mime_from_filename(original_filename)
    await object_storage.aput_bytes(
        use_s3=settings.use_s3_uploads,
        local_base=settings.uploads_dir,
        bucket=settings.AWS_S3_BUCKET.strip(),
        relative_key=relative_image_path,
        data=image_bytes_original,
        content_type=mime,
    )

    upload_status = "received"
    if metadata_obj and metadata_obj.get("ingestion_warnings"):
        if ingestion_logic.GEOSPATIAL_MISMATCH in metadata_obj["ingestion_warnings"]:
            upload_status = "geospatial_mismatch_review"

    upload_row = Upload(
        cluster_id=cluster_id,
        image_path=relative_image_path,
        phash=phash_str,
        metadata_json=metadata_obj,
        is_blurry=False,
        status=upload_status,
        blur_score=round(blur.effective_score, 4),
    )
    session.add(upload_row)
    await session.flush()

    out: dict = {
        "upload_id": upload_row.id,
        "cluster_id": cluster_id,
        "resolved_pu_id": pu_id,
        "image_path": relative_image_path,
        "blur_score": round(blur.effective_score, 2),
        "blur_score_original": round(blur.original_score, 2),
        "blur_best_strategy": blur.winning_strategy,
        "blur_scores_by_strategy": {
            name: round(score, 2) for name, score in blur.breakdown
        },
        "phash": phash_str,
    }
    if metadata_obj:
        fh_obj = metadata_obj.get("ai_form_header")
        if isinstance(fh_obj, dict):
            out["form_header"] = fh_obj
            line = ingestion_logic.format_ai_detected_location_line(fh_obj)
            if line:
                out["ai_detected_location_line"] = line
        if metadata_obj.get("ingestion_warnings"):
            out["ingestion_warnings"] = list(metadata_obj["ingestion_warnings"])

    co = await run_consensus_after_upload(
        session,
        cluster_id=cluster_id,
        election_id=election_id,
        pu_id=pu_id,
    )
    if isinstance(co, dict):
        st = co.get("status")
        if st is not None:
            out["consensus_status"] = st
        if "confidence_score" in co and co["confidence_score"] is not None:
            out["consensus_confidence"] = co["confidence_score"]
        if co.get("status") == "ERROR":
            out["consensus_error"] = co.get("error")

    return out
