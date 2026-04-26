"""Clear collated results for one election (uploads, clusters, rollups) for demo / QA re-ingestion."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import (
    Election,
    LgaResultTally,
    NationalResultTally,
    ResultCluster,
    StateResultTally,
    Upload,
)
from app.services import object_storage

logger = logging.getLogger(__name__)


async def reset_collated_votes_for_election(session: AsyncSession, election_id: int) -> dict[str, int]:
    """
    Delete proof uploads (DB + storage), result clusters, and national/state/LGA rollups for the election.
    Leaves elections, geography, and polling_units unchanged.
    """
    election = await session.get(Election, election_id)
    if election is None:
        raise ValueError(f"Election {election_id} not found")

    cluster_ids_subq = select(ResultCluster.id).where(ResultCluster.election_id == election_id)
    paths_result = await session.execute(
        select(Upload.image_path).where(Upload.cluster_id.in_(cluster_ids_subq))
    )
    paths = [row[0] for row in paths_result.all() if row[0]]

    r_uploads = await session.execute(
        delete(Upload).where(Upload.cluster_id.in_(cluster_ids_subq))
    )
    r_clusters = await session.execute(
        delete(ResultCluster).where(ResultCluster.election_id == election_id)
    )
    r_nat = await session.execute(
        delete(NationalResultTally).where(NationalResultTally.election_id == election_id)
    )
    r_state = await session.execute(
        delete(StateResultTally).where(StateResultTally.election_id == election_id)
    )
    r_lga = await session.execute(
        delete(LgaResultTally).where(LgaResultTally.election_id == election_id)
    )

    await session.flush()

    deleted_files = 0
    for rel in paths:
        try:
            if settings.use_s3_uploads:
                await object_storage.adelete_bytes(
                    use_s3=True,
                    local_base=settings.uploads_dir,
                    bucket=settings.AWS_S3_BUCKET.strip(),
                    relative_key=rel,
                )
            else:
                await object_storage.adelete_bytes(
                    use_s3=False,
                    local_base=settings.uploads_dir,
                    bucket="",
                    relative_key=rel,
                )
            deleted_files += 1
        except Exception as e:  # noqa: BLE001 — best-effort cleanup (S3/local, missing keys)
            logger.warning("Could not delete proof file %r: %s", rel, e)

    return {
        "election_id": election_id,
        "upload_rows_deleted": r_uploads.rowcount or 0,
        "cluster_rows_deleted": r_clusters.rowcount or 0,
        "national_tally_rows_deleted": r_nat.rowcount or 0,
        "state_tally_rows_deleted": r_state.rowcount or 0,
        "lga_tally_rows_deleted": r_lga.rowcount or 0,
        "proof_files_removed": deleted_files,
    }
