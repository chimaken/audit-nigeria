"""Deterministic checks that INEC-style sheet figures are internally consistent."""

from __future__ import annotations

from typing import Any


def evaluate_sheet_arithmetic(
    party_results: dict[str, int],
    summary: dict[str, int] | None,
) -> dict[str, Any]:
    """
    EC8-style totals: sum of party valid-vote columns must equal ``total_valid``;
    ``total_valid + rejected`` must equal ``total_cast``.

    This is independent of the model's ``is_math_correct`` flag and of written-English columns.
    """
    out: dict[str, Any] = {
        "ok": False,
        "sum_party_votes": sum(int(v) for v in party_results.values()),
        "total_valid": None,
        "rejected": None,
        "total_cast": None,
        "checks": {
            "sum_equals_total_valid": False,
            "valid_plus_rejected_equals_cast": False,
        },
        "reason": None,
    }
    if not summary:
        out["reason"] = "missing_summary"
        return out
    try:
        tv = int(summary["total_valid"])
        rej = int(summary["rejected"])
        tc = int(summary["total_cast"])
    except (KeyError, TypeError, ValueError):
        out["reason"] = "summary_fields_not_integers"
        return out
    out["total_valid"] = tv
    out["rejected"] = rej
    out["total_cast"] = tc
    s = int(out["sum_party_votes"])
    chk1 = s == tv
    chk2 = tv + rej == tc
    out["checks"]["sum_equals_total_valid"] = chk1
    out["checks"]["valid_plus_rejected_equals_cast"] = chk2
    out["ok"] = bool(chk1 and chk2)
    if not out["ok"]:
        parts = []
        if not chk1:
            parts.append(f"party columns sum to {s}, total_valid is {tv}")
        if not chk2:
            parts.append(f"total_valid ({tv}) + rejected ({rej}) = {tv + rej}, total_cast is {tc}")
        out["reason"] = "; ".join(parts)
    return out


def sheet_arithmetic_ok(party_results: dict[str, int], summary: dict[str, int] | None) -> bool:
    """True iff ``evaluate_sheet_arithmetic`` reports ok."""
    return bool(evaluate_sheet_arithmetic(party_results, summary)["ok"])
