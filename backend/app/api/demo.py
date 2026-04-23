from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

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
