"""2-of-3 consensus over vision extractions per result cluster."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.models import ResultCluster, Upload
from app.services import ai_service, object_storage
from app.services.aggregator import refresh_election_rollups
from app.services.ai_service import ExtractionResult
from app.services.ingestion_logic import format_ai_detected_location_line


def _mime_for_path(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    if p.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def _signature(r: ExtractionResult) -> tuple[str, str]:
    party = json.dumps(r.party_results, sort_keys=True, ensure_ascii=True)
    summary_keys = ("total_valid", "rejected", "total_cast")
    sm = {k: r.summary.get(k) for k in summary_keys if k in r.summary}
    summary = json.dumps(sm, sort_keys=True, ensure_ascii=True)
    return party, summary


async def _try_extract_upload(u: Upload) -> tuple[ExtractionResult | None, str | None]:
    """Load one upload from storage and vision-extract; return (result, error_token)."""
    data = await object_storage.aget_bytes(
        use_s3=settings.use_s3_uploads,
        local_base=settings.uploads_dir,
        bucket=settings.AWS_S3_BUCKET.strip(),
        relative_key=u.image_path,
    )
    if data is None:
        return None, f"missing_file:{u.id}"
    mime = _mime_for_path(u.image_path)
    try:
        ext = await ai_service.extract_results_from_image_bytes(data, mime=mime)
        return ext, None
    except Exception as e:  # noqa: BLE001
        msg = str(e).strip() or repr(e)
        return None, f"upload_{u.id}:{msg}"


def _pick_majority(results: list[ExtractionResult]) -> tuple[ExtractionResult | None, int]:
    """Return (winning extraction, agreement count) if any signature appears >= 2 times."""
    if len(results) < 2:
        return None, 0
    keys = [_signature(r) for r in results]
    cnt = Counter(keys)
    (party_s, sum_s), n = cnt.most_common(1)[0]
    if n < 2:
        return None, n
    for r in results:
        if _signature(r) == (party_s, sum_s):
            return r, n
    return None, n


async def process_cluster_consensus(
    session: AsyncSession, cluster_id: int
) -> dict[str, Any]:
    """
    Top-N uploads by blur_score, vision-extract each, 2-of-3 majority -> VERIFIED.

    Refreshes hierarchical rollups when figures are stored: on VERIFIED, and on
    DISPUTED when a best-effort `party_results` is kept (single proof, failed
    majority, or figures/words mismatch after agreement).
    """
    cluster = await session.get(ResultCluster, cluster_id)
    if cluster is None:
        raise ValueError(f"ResultCluster {cluster_id} not found")

    stmt = (
        select(Upload)
        .where(Upload.cluster_id == cluster_id)
        .order_by(Upload.blur_score.desc().nulls_last(), Upload.id.desc())
        .limit(3)
    )
    uploads = (await session.execute(stmt)).scalars().all()
    if len(uploads) < 2:
        cluster.consensus_status = "DISPUTED"
        cluster.current_consensus_json = {
            "reason": "insufficient_uploads",
            "count": len(uploads),
        }
        cluster.party_results = None
        cluster.confidence_score = 0.0
        await session.flush()
        return {
            "cluster_id": cluster_id,
            "status": cluster.consensus_status,
            "reason": "Need at least two uploads to run consensus",
        }

    extractions: list[ExtractionResult] = []
    errors: list[str] = []
    for u in uploads:
        data = await object_storage.aget_bytes(
            use_s3=settings.use_s3_uploads,
            local_base=settings.uploads_dir,
            bucket=settings.AWS_S3_BUCKET.strip(),
            relative_key=u.image_path,
        )
        if data is None:
            errors.append(f"missing_file:{u.id}")
            continue
        mime = _mime_for_path(u.image_path)
        try:
            ext = await ai_service.extract_results_from_image_bytes(data, mime=mime)
            extractions.append(ext)
        except Exception as e:  # noqa: BLE001
            msg = str(e).strip() or repr(e)
            errors.append(f"upload_{u.id}:{msg}")

    if len(extractions) < 2:
        cluster.consensus_status = "DISPUTED"
        cluster.current_consensus_json = {
            "reason": "extraction_failed",
            "errors": errors,
        }
        cluster.party_results = None
        cluster.confidence_score = 0.0
        await session.flush()
        return {
            "cluster_id": cluster_id,
            "status": "DISPUTED",
            "errors": errors,
        }

    winner, agree_n = _pick_majority(extractions)
    if winner is None:
        cluster.consensus_status = "DISPUTED"
        cluster.current_consensus_json = {
            "reason": "high_variance",
            "extractions": [ai_service.extraction_to_consensus_dict(r) for r in extractions],
            "errors": errors,
        }
        cluster.party_results = None
        cluster.confidence_score = agree_n / max(len(extractions), 1)
        await session.flush()
        return {
            "cluster_id": cluster_id,
            "status": "DISPUTED",
            "reason": "No two extractions matched exactly",
        }

    payload = ai_service.extraction_to_consensus_dict(winner)
    fw = payload.get("figures_words_verification") or {}
    party_mm = fw.get("party_mismatches") or []
    summary_mm = fw.get("summary_mismatches") or []
    if party_mm or summary_mm:
        cluster.consensus_status = "DISPUTED"
        cluster.party_results = dict(winner.party_results)
        cluster.confidence_score = agree_n / max(len(extractions), 1)
        cluster.current_consensus_json = {
            "reason": "figures_words_mismatch",
            "provisional": True,
            **payload,
        }
        await session.flush()
        await refresh_election_rollups(session, cluster.election_id)
        fh = payload.get("form_header")
        loc_line = (
            format_ai_detected_location_line(fh)
            if isinstance(fh, dict)
            else ""
        )
        return {
            "cluster_id": cluster_id,
            "status": "DISPUTED",
            "reason": "figures_words_mismatch",
            "confidence_score": cluster.confidence_score,
            "consensus": cluster.current_consensus_json,
            "ai_detected_location_line": loc_line or None,
            "figures_words_verification": fw,
            "errors": errors,
        }

    cluster.consensus_status = "VERIFIED"
    cluster.current_consensus_json = payload
    cluster.party_results = dict(winner.party_results)
    cluster.confidence_score = agree_n / max(len(extractions), 1)
    await session.flush()

    await refresh_election_rollups(session, cluster.election_id)

    fh_v = payload.get("form_header")
    loc_v = (
        format_ai_detected_location_line(fh_v)
        if isinstance(fh_v, dict)
        else ""
    )
    return {
        "cluster_id": cluster_id,
        "status": "VERIFIED",
        "confidence_score": cluster.confidence_score,
        "consensus": payload,
        "ai_detected_location_line": loc_v or None,
        "errors": errors,
    }
