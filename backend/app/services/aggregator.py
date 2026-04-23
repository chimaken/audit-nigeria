"""Recompute hierarchical party totals when clusters are verified."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    LGA,
    LgaResultTally,
    NationalResultTally,
    PollingUnit,
    ResultCluster,
    StateResultTally,
)


def _merge_party_dict(target: dict[str, int], source: dict[str, Any]) -> None:
    for k, v in source.items():
        key = str(k).strip().upper()
        try:
            iv = int(v)
        except (TypeError, ValueError):
            continue
        target[key] = target.get(key, 0) + iv


async def refresh_election_rollups(session: AsyncSession, election_id: int) -> None:
    """
    Atomically rebuild national / state / LGA JSONB tallies for one election
    from all VERIFIED clusters with party_results.
    """
    stmt = (
        select(ResultCluster.party_results, PollingUnit.lga_id, LGA.state_id)
        .join(PollingUnit, ResultCluster.pu_id == PollingUnit.id)
        .join(LGA, PollingUnit.lga_id == LGA.id)
        .where(
            ResultCluster.election_id == election_id,
            ResultCluster.consensus_status == "VERIFIED",
            ResultCluster.party_results.is_not(None),
        )
    )
    rows = (await session.execute(stmt)).all()

    national: dict[str, int] = defaultdict(int)
    by_lga: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_state: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for party_results, lga_id, state_id in rows:
        if not isinstance(party_results, dict):
            continue
        _merge_party_dict(national, party_results)
        _merge_party_dict(by_lga[lga_id], party_results)
        _merge_party_dict(by_state[state_id], party_results)

    now = datetime.now(UTC)

    await session.execute(
        delete(NationalResultTally).where(NationalResultTally.election_id == election_id)
    )
    await session.execute(
        delete(StateResultTally).where(StateResultTally.election_id == election_id)
    )
    await session.execute(
        delete(LgaResultTally).where(LgaResultTally.election_id == election_id)
    )
    await session.flush()

    session.add(
        NationalResultTally(
            election_id=election_id,
            party_results=dict(national),
            updated_at=now,
        )
    )
    for sid, parties in by_state.items():
        session.add(
            StateResultTally(
                election_id=election_id,
                state_id=sid,
                party_results=dict(parties),
                updated_at=now,
            )
        )
    for lid, parties in by_lga.items():
        session.add(
            LgaResultTally(
                election_id=election_id,
                lga_id=lid,
                party_results=dict(parties),
                updated_at=now,
            )
        )
    await session.flush()
