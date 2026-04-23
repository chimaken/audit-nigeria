"""Background consensus processing (run worker: celery -A app.celery_app worker -l info)."""

from __future__ import annotations

import asyncio

from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.consensus_engine import process_cluster_consensus


@celery_app.task(name="consensus.process_cluster")
def process_cluster_consensus_task(cluster_id: int) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            try:
                out = await process_cluster_consensus(session, cluster_id)
                await session.commit()
                return out
            except Exception:
                await session.rollback()
                raise

    return asyncio.run(_run())
