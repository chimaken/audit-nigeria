"""
Seed Nigerian States and LGAs (Lagos + Federal Capital Territory) for MVP testing.

Run from the `backend` directory (or `docker compose exec api python -m app.db.seed`).
Creates tables if they do not exist, then inserts Lagos + FCT geography.

    set PYTHONPATH=.   (Windows)
    python -m app.db.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base, LGA, State
from app.db.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)


async def wait_for_postgres_ready(
    max_attempts: int = 45,
    delay_sec: float = 2.0,
) -> None:
    """
    Retry until Postgres accepts queries (not in recovery / startup).
    Helps right after `docker compose up` or `restart db`.
    """
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database ready after %s attempt(s).", attempt)
            return
        except BaseException as e:
            last = e
            logger.warning(
                "Waiting for Postgres (attempt %s/%s): %s",
                attempt,
                max_attempts,
                e,
            )
            await asyncio.sleep(delay_sec)
    raise RuntimeError(
        "Postgres did not become ready in time. Try: "
        "`docker compose logs db` — if recovery hangs or repeats errors, "
        "`docker compose down` then `docker compose up -d db` and wait until healthy "
        "(dev data in the default setup lives in the container; removing the container resets the DB)."
    ) from last


async def ensure_schema() -> None:
    """Create tables if missing (same as FastAPI lifespan). Seed runs in a separate process."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


LAGOS_LGAS: list[str] = [
    "Agege",
    "Ajeromi-Ifelodun",
    "Alimosho",
    "Amuwo-Odofin",
    "Apapa",
    "Badagry",
    "Epe",
    "Eti Osa",
    "Ibeju-Lekki",
    "Ifako-Ijaiye",
    "Ikeja",
    "Ikorodu",
    "Kosofe",
    "Lagos Island",
    "Lagos Mainland",
    "Mushin",
    "Ojo",
    "Oshodi-Isolo",
    "Shomolu",
    "Surulere",
]

FCT_LGAS: list[str] = [
    "Abaji",
    "Abuja Municipal",
    "Bwari",
    "Gwagwalada",
    "Kuje",
    "Kwali",
]


async def _get_or_create_state(session: AsyncSession, name: str) -> State:
    result = await session.execute(select(State).where(State.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    state = State(name=name)
    session.add(state)
    await session.flush()
    return state


async def _ensure_lgas(session: AsyncSession, state: State, lga_names: list[str]) -> None:
    for lga_name in lga_names:
        q = await session.execute(
            select(LGA).where(LGA.state_id == state.id, LGA.name == lga_name)
        )
        if q.scalar_one_or_none() is None:
            session.add(LGA(name=lga_name, state_id=state.id))


async def seed_geography(session: AsyncSession) -> None:
    lagos = await _get_or_create_state(session, "Lagos")
    fct = await _get_or_create_state(session, "Federal Capital Territory")

    await _ensure_lgas(session, lagos, LAGOS_LGAS)
    await _ensure_lgas(session, fct, FCT_LGAS)

    await session.flush()


async def run_seed() -> None:
    logging.basicConfig(level=logging.INFO)
    await wait_for_postgres_ready()
    await ensure_schema()
    async with AsyncSessionLocal() as session:
        try:
            await seed_geography(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    logger.info("Seed completed (Lagos + Federal Capital Territory LGAs).")


def main() -> None:
    asyncio.run(run_seed())


if __name__ == "__main__":
    main()
