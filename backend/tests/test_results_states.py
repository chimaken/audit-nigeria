"""API behaviour for `/results/states` (FCT dedupe + tally preference).

Uses a minimal FastAPI app (results router only) so tests do not import the full
`app.main` stack (uploads → OpenCV, Celery, etc.).
"""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.results import router as results_router
from app.db.models import Base, Election, ElectionType, LGA, LgaResultTally, State
from app.db.session import AsyncSessionLocal, engine


@pytest_asyncio.fixture(autouse=True)
async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    app = FastAPI()
    app.include_router(results_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def fct_duplicate_states_scenario(client: AsyncClient) -> dict[str, int]:
    """
    Two FCT-alias states; only the 'FCT' state has an LGA tally.
    API should expose a single row labelled Federal Capital Territory with that state's id.
    """
    _ = client
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                State(name="Federal Capital Territory"),
                State(name="FCT"),
            ]
        )
        await session.flush()
        states = list((await session.execute(select(State).order_by(State.id))).scalars().all())
        fct_long = next(s for s in states if s.name == "Federal Capital Territory")
        fct_short = next(s for s in states if s.name == "FCT")

        session.add_all(
            [
                LGA(name="Abaji", state_id=fct_long.id),
                LGA(name="Bwari", state_id=fct_short.id),
            ]
        )
        await session.flush()
        lgas = list((await session.execute(select(LGA))).scalars().all())
        lga_short = next(l for l in lgas if l.state_id == fct_short.id)

        el = Election(name="Test", type=ElectionType.NATIONAL)
        session.add(el)
        await session.flush()

        session.add(
            LgaResultTally(
                election_id=el.id,
                lga_id=lga_short.id,
                party_results={"A": 10},
            )
        )
        await session.commit()

        return {
            "election_id": el.id,
            "expected_state_id": fct_short.id,
            "other_state_id": fct_long.id,
        }


async def test_list_states_empty(client: AsyncClient) -> None:
    r = await client.get("/results/states")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_states_merges_fct_prefers_tally_state(
    client: AsyncClient,
    fct_duplicate_states_scenario: dict[str, int],
) -> None:
    r = await client.get("/results/states")
    assert r.status_code == 200
    body = r.json()
    fct_rows = [row for row in body if row["state_name"] == "Federal Capital Territory"]
    assert len(fct_rows) == 1
    assert fct_rows[0]["state_id"] == fct_duplicate_states_scenario["expected_state_id"]


async def test_prefer_state_with_tallies_direct(
    fct_duplicate_states_scenario: dict[str, int],
) -> None:
    from app.services import ingestion_logic

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(State).where(State.name.in_(("FCT", "Federal Capital Territory")))
        )
        states = list(res.scalars().all())
        chosen = await ingestion_logic.prefer_state_with_tallies(session, states)
        assert chosen.id == fct_duplicate_states_scenario["expected_state_id"]
