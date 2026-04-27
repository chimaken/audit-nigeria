"""One-off safe database fixes for columns that older databases might lack."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_ensured_hil_alert_at: bool = False


async def ensure_result_clusters_hil_alert_column(engine: AsyncEngine) -> None:
    """Add human_review_alert_sent_at if missing; no-op after first success in this process."""
    global _ensured_hil_alert_at
    if _ensured_hil_alert_at:
        return
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE result_clusters "
                "ADD COLUMN IF NOT EXISTS human_review_alert_sent_at TIMESTAMPTZ"
            )
        )
    _ensured_hil_alert_at = True
    logger.debug("Schema: ensured result_clusters.human_review_alert_sent_at")
