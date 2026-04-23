"""Pure unit tests for ingestion helpers (no database)."""

from __future__ import annotations

import pytest

from app.services import ingestion_logic


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Lagos State  ", "Lagos"),
        ("FCT", "FCT"),
        ("", ""),
    ],
)
def test_normalize_state_name(raw: str, expected: str) -> None:
    assert ingestion_logic.normalize_state_name(raw) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("fct", True),
        ("F.C.T.", True),
        ("Federal Capital Territory", True),
        ("federal capital territory (abuja)", True),
        ("Lagos", False),
        ("", False),
    ],
)
def test_is_fct_state_name(name: str, expected: bool) -> None:
    norm = ingestion_logic.normalize_state_name(name)
    assert ingestion_logic.is_fct_state_name(norm) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("24-11-03-001", "24-11-03-001"),
        ("241103001", "24-11-03-001"),
        ("24/11/03/001", "24-11-03-001"),
    ],
)
def test_normalize_pu_code_ok(raw: str, expected: str) -> None:
    assert ingestion_logic.normalize_pu_code(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "abc", "12-34-56"])
def test_normalize_pu_code_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        ingestion_logic.normalize_pu_code(raw)
