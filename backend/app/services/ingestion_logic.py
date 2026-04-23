"""
Dynamic geography from VLM-read EC8A headers: State / LGA / PU upsert by pu_code.

GPS guardrail: compare client `expected_pu_code` (metadata) to VLM `pu_code`.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LGA, LgaResultTally, PollingUnit, State
from app.services.ai_service import FormHeader

GEOSPATIAL_MISMATCH = "Geospatial Mismatch"

_STATE_SUFFIX = re.compile(r"\s+state\s*$", re.IGNORECASE)


def normalize_state_name(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    return _STATE_SUFFIX.sub("", s).strip()


FCT_STATE_LABEL = "Federal Capital Territory"


def is_fct_state_name(normalized: str) -> bool:
    """True for FCT / Federal Capital Territory spellings (after normalize_state_name)."""
    low = normalized.strip().lower()
    if not low:
        return False
    if low in ("fct", "f.c.t."):
        return True
    if "federal capital territory" in low:
        return True
    return False


async def prefer_state_with_tallies(session: AsyncSession, states: list[State]) -> State:
    """When duplicate FCT rows exist, prefer the one that already has LGA result tallies."""
    if len(states) == 1:
        return states[0]
    ids = [s.id for s in states]
    cnt = func.count(LgaResultTally.id).label("tally_cnt")
    stmt = (
        select(LGA.state_id, cnt)
        .join(LgaResultTally, LgaResultTally.lga_id == LGA.id)
        .where(LGA.state_id.in_(ids))
        .group_by(LGA.state_id)
        .order_by(cnt.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row and row[0] is not None:
        sid = int(row[0])
        for s in states:
            if s.id == sid:
                return s
    for s in states:
        if s.name.strip().lower() == FCT_STATE_LABEL.lower():
            return s
    return min(states, key=lambda s: s.id)


def normalize_pu_code(raw: str) -> str:
    """
    INEC-style: SS-LL-WW-UUU (e.g. 24-11-03-001).
    Accepts missing hyphens (9 digits) or slashes.
    """
    s = (raw or "").strip().replace(" ", "").replace("/", "-")
    if not s:
        raise ValueError("pu_code is empty")
    parts = [p for p in s.split("-") if p]
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{int(parts[0]):02d}-{int(parts[1]):02d}-{int(parts[2]):02d}-{int(parts[3]):03d}"
    digits = re.sub(r"\D", "", s)
    if len(digits) == 9 and digits.isdigit():
        return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}-{digits[6:9]}"
    raise ValueError(f"Unrecognized polling unit code format: {raw!r}")


def _metadata_expected_pu_code(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    v = metadata.get("expected_pu_code")
    if isinstance(v, str) and v.strip():
        return v.strip()
    gps = metadata.get("gps")
    if isinstance(gps, dict):
        for key in ("expected_pu_code", "pu_code", "assigned_pu_code"):
            v2 = gps.get(key)
            if isinstance(v2, str) and v2.strip():
                return v2.strip()
    return None


def geospatial_mismatch_warnings(
    metadata: Mapping[str, Any] | None,
    extracted_normalized_pu_code: str,
    *,
    claimed_pu_code_from_db: str | None = None,
) -> list[str]:
    """
    Flag when GPS / client expected PU code disagrees with the sheet-derived code.

    - metadata.expected_pu_code or metadata.gps.expected_pu_code
    - claimed_pu_code_from_db: when the client selected an existing PU (legacy upload)
    """
    warnings: list[str] = []
    expected = _metadata_expected_pu_code(metadata)
    if expected:
        try:
            if normalize_pu_code(expected) != extracted_normalized_pu_code:
                warnings.append(GEOSPATIAL_MISMATCH)
        except ValueError:
            warnings.append(GEOSPATIAL_MISMATCH)
    if claimed_pu_code_from_db:
        try:
            if normalize_pu_code(claimed_pu_code_from_db) != extracted_normalized_pu_code:
                warnings.append(GEOSPATIAL_MISMATCH)
        except ValueError:
            warnings.append(GEOSPATIAL_MISMATCH)
    return warnings


def format_ai_detected_location_line(header: Mapping[str, Any] | FormHeader) -> str:
    """Single-line copy for UI, e.g. 'AI Detected: Ikeja LGA, Ward 3, PU 001 (24-11-03-001)'."""
    if isinstance(header, FormHeader):
        h = header.model_dump()
    else:
        h = dict(header)
    state = (h.get("state") or "").strip()
    lga = (h.get("lga") or "").strip()
    ward = (h.get("ward") or "").strip()
    pu_name = (h.get("pu_name") or "").strip()
    pu_code = (h.get("pu_code") or "").strip()
    et = (h.get("election_type") or "").strip()

    bits: list[str] = []
    if lga:
        bits.append(f"{lga} LGA")
    elif state:
        bits.append(state)
    if ward:
        wl = ward.lower()
        if wl.startswith("ward"):
            bits.append(ward)
        else:
            bits.append(f"Ward {ward}")
    if pu_name:
        bits.append(pu_name)
    if pu_code:
        try:
            bits.append(normalize_pu_code(pu_code))
        except ValueError:
            bits.append(pu_code)
    if et and et != "EC8A":
        bits.append(et)

    if not bits:
        return ""
    return "AI Detected: " + ", ".join(bits)


async def _get_or_create_state(session: AsyncSession, name: str) -> State:
    n = normalize_state_name(name)
    if not n:
        raise ValueError("state name is empty in form header")
    if is_fct_state_name(n):
        stmt = select(State).where(
            or_(
                func.lower(State.name) == "fct",
                func.lower(State.name) == func.lower(FCT_STATE_LABEL),
            )
        )
        rows = list(await session.scalars(stmt))
        if rows:
            return await prefer_state_with_tallies(session, rows)
        st = State(name=FCT_STATE_LABEL)
        session.add(st)
        await session.flush()
        return st
    stmt = select(State).where(func.lower(State.name) == func.lower(n))
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return row
    st = State(name=n)
    session.add(st)
    await session.flush()
    return st


async def _get_or_create_lga(session: AsyncSession, state_id: int, name: str) -> LGA:
    n = (name or "").strip()
    if not n:
        raise ValueError("LGA name is empty in form header")
    stmt = select(LGA).where(
        LGA.state_id == state_id,
        func.lower(LGA.name) == func.lower(n),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return row
    lga = LGA(name=n, state_id=state_id)
    session.add(lga)
    await session.flush()
    return lga


async def resolve_pu_from_form_header(
    session: AsyncSession,
    header: FormHeader,
    *,
    metadata: dict[str, Any] | None,
    claimed_pu_code_from_db: str | None = None,
) -> tuple[PollingUnit, list[str]]:
    """
    Lookup or create State → LGA → PollingUnit (unique pu_code).

    Returns (pu, ingestion_warnings).
    """
    warnings: list[str] = []
    code = normalize_pu_code(header.pu_code)

    warnings.extend(
        geospatial_mismatch_warnings(
            metadata,
            code,
            claimed_pu_code_from_db=claimed_pu_code_from_db,
        )
    )

    state = await _get_or_create_state(session, header.state)
    lga = await _get_or_create_lga(session, state.id, header.lga)

    stmt = select(PollingUnit).where(PollingUnit.pu_code == code)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        if existing.lga_id != lga.id:
            # Same national code reused in wrong LGA is a data conflict; keep existing row.
            warnings.append("PU code exists under a different LGA; using existing record")
        w = (header.ward or "").strip() or None
        if w and not (existing.ward or "").strip():
            existing.ward = w
        name = (header.pu_name or "").strip()
        if name and (not existing.name or existing.name.startswith("PU ")):
            existing.name = name
        return existing, warnings

    pu_name = (header.pu_name or "").strip() or f"PU {code}"
    ward = (header.ward or "").strip() or None
    pu = PollingUnit(
        name=pu_name,
        ward=ward,
        lga_id=lga.id,
        pu_code=code,
    )
    session.add(pu)
    await session.flush()
    return pu, list(dict.fromkeys(warnings))
