"""Sheet total consistency (party sum vs total_valid, valid+rejected vs cast)."""

from app.services.sheet_arithmetic import evaluate_sheet_arithmetic, sheet_arithmetic_ok


def test_ok_when_figures_align() -> None:
    parties = {"APC": 40, "PDP": 35, "LP": 5}
    summary = {"total_valid": 80, "rejected": 2, "total_cast": 82}
    assert sheet_arithmetic_ok(parties, summary)
    ev = evaluate_sheet_arithmetic(parties, summary)
    assert ev["ok"] is True
    assert ev["reason"] is None


def test_fail_when_sum_parties_not_total_valid() -> None:
    parties = {"APC": 40, "PDP": 35}
    summary = {"total_valid": 80, "rejected": 0, "total_cast": 80}
    assert not sheet_arithmetic_ok(parties, summary)
    ev = evaluate_sheet_arithmetic(parties, summary)
    assert ev["ok"] is False
    assert "party columns sum" in (ev.get("reason") or "")


def test_fail_when_valid_plus_rejected_not_cast() -> None:
    parties = {"APC": 50}
    summary = {"total_valid": 50, "rejected": 3, "total_cast": 50}
    assert not sheet_arithmetic_ok(parties, summary)
    ev = evaluate_sheet_arithmetic(parties, summary)
    assert ev["ok"] is False
    assert "total_cast" in (ev.get("reason") or "")


def test_missing_summary() -> None:
    assert not sheet_arithmetic_ok({"A": 1}, None)
    ev = evaluate_sheet_arithmetic({"A": 1}, None)
    assert ev["reason"] == "missing_summary"
