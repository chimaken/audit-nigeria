"""Idempotent DDL for columns that may be missing if patch SQL was never applied to RDS."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_ensured_hil_alert_at: bool = False


async def ensure_result_clusters_hil_alert_column(engine: AsyncEngine) -> None:
    """
    Ensure human_review_alert_sent_at exists (see backend/sql/patch_human_review_alert.sql).
    Safe to call on every upload path; runs at most once per process after first success.
    """
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
