from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import (
    Election,
    LGA,
    LgaResultTally,
    NationalResultTally,
    PollingUnit,
    ResultCluster,
    State,
    StateResultTally,
)
from app.services import ingestion_logic
from app.services.aggregator import refresh_election_rollups
from app.services.ai_service import ExtractionResult, extraction_to_consensus_dict
from app.services.consensus_engine import process_cluster_consensus
from app.services.ingestion_logic import format_ai_detected_location_line, normalize_pu_code
from app.services.sheet_arithmetic import sheet_arithmetic_ok

router = APIRouter(prefix="/results", tags=["results"])


def _normalize_party_results(raw: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for k, v in raw.items():
        key = str(k).strip().upper()
        try:
            out[key] = int(v)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail=f"Invalid vote count for party {key!r}"
            ) from None
    return out


def _compute_math_ok(party_results: dict[str, int], summary: dict) -> bool:
    if not isinstance(summary, dict):
        return False
    try:
        summary_ints = {k: int(summary[k]) for k in ("total_valid", "rejected", "total_cast")}
    except (KeyError, TypeError, ValueError):
        return False
    return sheet_arithmetic_ok(party_results, summary_ints)


def _normalize_party_words(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, val in raw.items():
        key = str(k).strip().upper()
        out[key] = "" if val is None else str(val).strip()
    return out


class ManualConsensusBody(BaseModel):
    """Replace stored consensus after human review (models can agree and still be wrong on handwriting)."""

    party_results: dict[str, int | str] = Field(default_factory=dict)
    party_in_words: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, int | str] = Field(default_factory=dict)
    summary_in_words: dict[str, str] = Field(default_factory=dict)
    is_math_correct: bool | None = None

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary_ints(cls, v: object) -> dict:
        if not isinstance(v, dict):
            raise ValueError("summary must be an object")
        out: dict[str, int] = {}
        for key in ("total_valid", "rejected", "total_cast"):
            if key not in v:
                raise ValueError(f"summary must include {key}")
            out[key] = int(v[key])
        return out

    @field_validator("party_results", mode="before")
    @classmethod
    def _coerce_party(cls, v: object) -> dict:
        if not isinstance(v, dict):
            raise ValueError("party_results must be an object")
        return v

    @field_validator("party_in_words", "summary_in_words", mode="before")
    @classmethod
    def _coerce_words_dict(cls, v: object) -> dict:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("must be an object")
        return v


def _file_public_url(relative_path: str) -> str:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/files/{quote(relative_path, safe='/')}"


async def _require_election(session: AsyncSession, election_id: int) -> Election:
    el = await session.get(Election, election_id)
    if el is None:
        raise HTTPException(status_code=404, detail="Election not found")
    return el


@router.get("/states")
async def list_states(session: AsyncSession = Depends(get_db)) -> list[dict]:
    """All states (for dashboard navigation). FCT aliases merge to one `Federal Capital Territory` row."""
    rows = (
        await session.execute(select(State).order_by(State.name))
    ).scalars().all()
    groups: dict[str, list[State]] = {}
    for s in rows:
        raw = ingestion_logic.normalize_state_name(s.name)
        key = "fct" if ingestion_logic.is_fct_state_name(raw) else f"other:{raw.lower()}"
        groups.setdefault(key, []).append(s)

    out: list[dict] = []
    for key, lst in groups.items():
        if key == "fct":
            primary = await ingestion_logic.prefer_state_with_tallies(session, lst)
            out.append(
                {
                    "state_id": primary.id,
                    "state_name": ingestion_logic.FCT_STATE_LABEL,
                },
            )
        else:
            for s in lst:
                out.append({"state_id": s.id, "state_name": s.name})
    out.sort(key=lambda r: r["state_name"].lower())
    return out


@router.get("/national")
async def national_totals(
    session: AsyncSession = Depends(get_db),
    election_id: int = Query(..., description="Election to aggregate"),
) -> dict:
    await _require_election(session, election_id)
    disputed_provisional_ct = await session.scalar(
        select(func.count(ResultCluster.id)).where(
            ResultCluster.election_id == election_id,
            ResultCluster.consensus_status == "DISPUTED",
            ResultCluster.party_results.is_not(None),
        )
    )
    includes_provisional = int(disputed_provisional_ct or 0) > 0
    row = await session.get(NationalResultTally, election_id)
    if row is None:
        return {
            "election_id": election_id,
            "party_results": {},
            "updated_at": None,
            "includes_provisional_disputed": includes_provisional,
        }
    return {
        "election_id": election_id,
        "party_results": dict(row.party_results),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "includes_provisional_disputed": includes_provisional,
    }


@router.get("/state/{state_id}")
async def state_drilldown(
    state_id: int,
    session: AsyncSession = Depends(get_db),
    election_id: int = Query(...),
) -> dict:
    await _require_election(session, election_id)
    st = await session.get(State, state_id)
    if st is None:
        raise HTTPException(status_code=404, detail="State not found")

    tallies = (
        await session.execute(
            select(LgaResultTally)
            .join(LGA, LgaResultTally.lga_id == LGA.id)
            .where(
                LgaResultTally.election_id == election_id,
                LGA.state_id == state_id,
            )
        )
    ).scalars().all()
    by_lga = {t.lga_id: t for t in tallies}

    lgas = (
        await session.execute(select(LGA).where(LGA.state_id == state_id).order_by(LGA.name))
    ).scalars().all()

    lga_payload = []
    for lga in lgas:
        t = by_lga.get(lga.id)
        lga_payload.append(
            {
                "lga_id": lga.id,
                "lga_name": lga.name,
                "party_results": dict(t.party_results) if t else {},
                "updated_at": t.updated_at.isoformat() if t and t.updated_at else None,
            }
        )

    state_row = await session.execute(
        select(StateResultTally).where(
            StateResultTally.election_id == election_id,
            StateResultTally.state_id == state_id,
        )
    )
    st_tally = state_row.scalar_one_or_none()

    return {
        "election_id": election_id,
        "state_id": state_id,
        "state_name": st.name,
        "state_party_results": dict(st_tally.party_results) if st_tally else {},
        "lgas": lga_payload,
    }


@router.get("/lga/{lga_id}")
async def lga_polling_units(
    lga_id: int,
    session: AsyncSession = Depends(get_db),
    election_id: int = Query(...),
) -> dict:
    await _require_election(session, election_id)
    lga = await session.get(LGA, lga_id)
    if lga is None:
        raise HTTPException(status_code=404, detail="LGA not found")

    pus = (
        await session.execute(
            select(PollingUnit).where(PollingUnit.lga_id == lga_id).order_by(PollingUnit.name)
        )
    ).scalars().all()

    clusters = (
        await session.execute(
            select(ResultCluster)
            .join(PollingUnit, ResultCluster.pu_id == PollingUnit.id)
            .where(
                ResultCluster.election_id == election_id,
                PollingUnit.lga_id == lga_id,
            )
        )
    ).scalars().all()
    by_pu: dict[int, list[ResultCluster]] = {}
    for c in clusters:
        by_pu.setdefault(c.pu_id, []).append(c)

    def _status_for_pu(pu_id: int) -> str:
        cs = by_pu.get(pu_id, [])
        if not cs:
            return "NO_CLUSTER"
        if any(x.consensus_status == "VERIFIED" for x in cs):
            return "VERIFIED"
        if any(x.consensus_status == "DISPUTED" for x in cs):
            return "DISPUTED"
        return "PENDING"

    units = [
        {
            "pu_id": pu.id,
            "pu_name": pu.name,
            "pu_code": pu.pu_code,
            "consensus_status": _status_for_pu(pu.id),
        }
        for pu in pus
    ]

    tally = await session.execute(
        select(LgaResultTally).where(
            LgaResultTally.election_id == election_id,
            LgaResultTally.lga_id == lga_id,
        )
    )
    trow = tally.scalar_one_or_none()

    return {
        "election_id": election_id,
        "lga_id": lga_id,
        "lga_name": lga.name,
        "lga_party_results": dict(trow.party_results) if trow else {},
        "polling_units": units,
    }


@router.get("/lookup-pu")
async def lookup_pu_by_code(
    session: AsyncSession = Depends(get_db),
    pu_code: str = Query(..., description="INEC PU code, e.g. 24-11-01-001"),
) -> dict:
    """Resolve a polling unit by normalized INEC code (for dashboard search / deep links)."""
    try:
        code = normalize_pu_code(pu_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    pu_stmt = (
        select(PollingUnit)
        .where(PollingUnit.pu_code == code)
        .options(selectinload(PollingUnit.lga).selectinload(LGA.state))
    )
    pu = (await session.execute(pu_stmt)).scalar_one_or_none()
    if pu is None:
        raise HTTPException(status_code=404, detail="Polling unit not found for this code")
    st = pu.lga.state if pu.lga else None
    return {
        "pu_id": pu.id,
        "pu_code": pu.pu_code,
        "pu_name": pu.name,
        "lga_id": pu.lga_id,
        "lga_name": pu.lga.name,
        "state_id": pu.lga.state_id,
        "state_name": st.name if st else None,
    }


@router.get("/pu/{pu_id}")
async def pu_detail(
    pu_id: int,
    session: AsyncSession = Depends(get_db),
    election_id: int = Query(...),
) -> dict:
    await _require_election(session, election_id)
    pu_stmt = (
        select(PollingUnit)
        .where(PollingUnit.id == pu_id)
        .options(selectinload(PollingUnit.lga).selectinload(LGA.state))
    )
    pu = (await session.execute(pu_stmt)).scalar_one_or_none()
    if pu is None:
        raise HTTPException(status_code=404, detail="Polling unit not found")

    stmt = (
        select(ResultCluster)
        .where(
            ResultCluster.pu_id == pu_id,
            ResultCluster.election_id == election_id,
        )
        .options(selectinload(ResultCluster.uploads))
        .order_by(ResultCluster.id)
    )
    clusters = (await session.execute(stmt)).scalars().all()
    if not clusters:
        raise HTTPException(status_code=404, detail="No result cluster for this PU and election")

    def _rank(c: ResultCluster) -> tuple[int, int]:
        prio = {"VERIFIED": 0, "DISPUTED": 1, "PENDING": 2}.get(c.consensus_status, 3)
        return (prio, -c.id)

    primary = sorted(clusters, key=_rank)[0]

    consensus = primary.current_consensus_json
    fh: dict | None = None
    if isinstance(consensus, dict):
        raw_fh = consensus.get("form_header")
        if isinstance(raw_fh, dict):
            fh = raw_fh
    if not fh:
        for cl in clusters:
            for u in cl.uploads:
                meta = u.metadata_json or {}
                cand = meta.get("ai_form_header")
                if isinstance(cand, dict) and any(str(v).strip() for v in cand.values()):
                    fh = cand
                    break
            if fh:
                break

    ai_line = format_ai_detected_location_line(fh) if fh else ""

    proofs: list[dict] = []
    seen: set[str] = set()
    for cl in clusters:
        for u in cl.uploads:
            if u.image_path in seen:
                continue
            seen.add(u.image_path)
            proofs.append(
                {
                    "upload_id": u.id,
                    "cluster_id": cl.id,
                    "image_url": _file_public_url(u.image_path),
                    "blur_score": u.blur_score,
                }
            )

    state_name = pu.lga.state.name if pu.lga.state else ""

    review_reason: str | None = None
    review_errors: list[str] | None = None
    if isinstance(consensus, dict):
        r = consensus.get("reason")
        review_reason = str(r) if r is not None and str(r).strip() else None
        errs = consensus.get("errors")
        if isinstance(errs, list) and errs:
            review_errors = [str(e) for e in errs if str(e).strip()]

    return {
        "election_id": election_id,
        "pu_id": pu.id,
        "pu_name": pu.name,
        "pu_code": pu.pu_code,
        "ward": pu.ward,
        "lga_id": pu.lga_id,
        "lga_name": pu.lga.name,
        "state_id": pu.lga.state_id,
        "state_name": state_name,
        "primary_cluster_id": primary.id,
        "consensus_status": primary.consensus_status,
        "party_results": dict(primary.party_results) if primary.party_results else {},
        "consensus": primary.current_consensus_json,
        "form_header": fh,
        "ai_detected_location_line": ai_line or None,
        "confidence_score": primary.confidence_score,
        "proof_images": proofs,
        "review_reason": review_reason,
        "review_errors": review_errors,
        "collation_source": (
            consensus.get("source")
            if isinstance(consensus, dict) and isinstance(consensus.get("source"), str)
            else None
        ),
    }


@router.post("/clusters/{cluster_id}/process-consensus")
async def trigger_cluster_consensus(
    cluster_id: int,
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await process_cluster_consensus(session, cluster_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.put("/clusters/{cluster_id}/consensus")
async def put_manual_consensus(
    cluster_id: int,
    body: ManualConsensusBody,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Overwrite `party_results` / `summary` after human review (e.g. fix ADC 49 → 42).
    Keeps `VERIFIED`, sets `source` to `manual_correction`, refreshes rollups.
    """
    cluster = await session.get(ResultCluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Result cluster not found")

    parties = _normalize_party_results(body.party_results)
    summary = {k: int(v) for k, v in body.summary.items()}
    piw = _normalize_party_words(body.party_in_words)
    math_ok = (
        body.is_math_correct
        if body.is_math_correct is not None
        else _compute_math_ok(parties, summary)
    )
    prev_consensus = cluster.current_consensus_json
    prev_fh = (
        prev_consensus.get("form_header")
        if isinstance(prev_consensus, dict)
        else None
    )

    er = ExtractionResult.model_validate(
        {
            "party_results": parties,
            "party_in_words": piw,
            "summary": summary,
            "summary_in_words": body.summary_in_words,
            "is_math_correct": math_ok,
        }
    )
    base = extraction_to_consensus_dict(er)
    if isinstance(prev_fh, dict) and any(str(v).strip() for v in prev_fh.values()):
        base["form_header"] = prev_fh
    payload = {**base, "source": "manual_correction"}
    cluster.current_consensus_json = payload
    cluster.party_results = parties
    cluster.consensus_status = "VERIFIED"
    cluster.confidence_score = 1.0
    cluster.human_review_alert_sent_at = None
    await session.flush()
    await refresh_election_rollups(session, cluster.election_id)

    return {
        "cluster_id": cluster_id,
        "status": "VERIFIED",
        "confidence_score": 1.0,
        "consensus": payload,
        "errors": [],
        "server_math_check": _compute_math_ok(parties, summary),
    }
