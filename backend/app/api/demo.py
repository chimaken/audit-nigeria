from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.services.election_reset import reset_collated_votes_for_election
from app.services.sheet_generator import generate_sample_sheet_png

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/sample-sheet")
async def download_sample_sheet(
    variant: int = Query(0, ge=0, le=9999, description="Seed for vote totals / layout variety"),
    state: str = Query("Lagos", max_length=128),
    lga: str = Query("Ikeja", max_length=128),
    pu_name: str = Query("Demo Polling Unit 001", max_length=255),
    pu_code: str = Query("DEMO-PU-001", max_length=64),
) -> Response:
    """
    Returns a PNG that resembles an EC8A-style unit result sheet for demos.
    Save the file and POST it to `/upload` with your `election_id` and `pu_id`.
    """
    png = generate_sample_sheet_png(
        variant=variant,
        state=state,
        lga=lga,
        pu_name=pu_name,
        pu_code=pu_code,
    )
    filename = f"sample-ec8a-v{variant}.png"
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reset-collated-votes")
async def reset_collated_votes(
    election_id: int = Query(..., ge=1, description="Election whose uploads, clusters, and rollups are cleared"),
    session: AsyncSession = Depends(get_db),
    x_dashboard_reset_token: str | None = Header(None, alias="X-Dashboard-Reset-Token"),
) -> dict[str, int]:
    """
    Deletes uploads (and proof files), result_clusters, and national/state/LGA tallies for one election.
    Disabled unless DASHBOARD_RESET_TOKEN is set; requires matching X-Dashboard-Reset-Token header.
    """
    expected = (settings.DASHBOARD_RESET_TOKEN or "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    got = (x_dashboard_reset_token or "").strip()
    if got != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Dashboard-Reset-Token")
    try:
        out = await reset_collated_votes_for_election(session, election_id)
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        await session.rollback()
        raise
    return out
