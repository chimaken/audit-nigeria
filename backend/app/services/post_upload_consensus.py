"""Run 2-of-3 consensus after a new upload + optional human-review Telegram alert."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Upload
from app.services.consensus_engine import process_cluster_consensus
from app.services.human_review_alerts import maybe_telegram_low_confidence_after_multi_upload

logger = logging.getLogger(__name__)


async def run_consensus_after_upload(
    session: AsyncSession,
    *,
    cluster_id: int,
    election_id: int,
    pu_id: int,
) -> dict[str, Any] | None:
    """
    Run consensus for the cluster (safe with 1 upload — stays DISPUTED / insufficient).
    Then maybe Telegram if ≥2 uploads and confidence is below threshold.
    Returns the consensus engine dict, or None on unexpected failure (upload still saved).
    """
    try:
        out = await process_cluster_consensus(session, cluster_id)
        cnt = (
            await session.execute(
                select(func.count()).select_from(Upload).where(Upload.cluster_id == cluster_id)
            )
        ).scalar_one()
        n = int(cnt or 0)
        await maybe_telegram_low_confidence_after_multi_upload(
            session,
            cluster_id=cluster_id,
            election_id=election_id,
            pu_id=pu_id,
            upload_count=n,
        )
        return out
    except Exception as e:  # noqa: BLE001
        logger.exception(
            "post_upload_consensus: failed cluster_id=%s election_id=%s pu_id=%s",
            cluster_id,
            election_id,
            pu_id,
        )
        return {"cluster_id": cluster_id, "status": "ERROR", "error": str(e)[:500]}
