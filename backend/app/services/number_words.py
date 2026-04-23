"""Parse English vote amounts as written on INEC EC8A \"in words\" columns (0–999,999)."""

from __future__ import annotations

import re

# Common misspellings on handwritten forms
_TOKEN_FIXES = {
    "fourty": "forty",
    "ninty": "ninety",
    "ninteen": "nineteen",
    "thirtee": "thirty",
    "fivety": "fifty",
}

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _tokens(s: str) -> list[str]:
    t = s.lower().strip()
    t = re.sub(r"[-]", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\b(votes?|only|nil|none|no)\b", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return []
    out: list[str] = []
    for w in t.split():
        w = _TOKEN_FIXES.get(w, w)
        if w != "and":
            out.append(w)
    return out


def parse_english_int(text: str) -> int | None:
    """
    Best-effort parse of phrases like \"Forty two\", \"One hundred and twenty three\".
    Returns None if empty or not confidently parseable.
    """
    raw = text.strip()
    if not raw:
        return None
    compact = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"\d+", compact):
        try:
            v = int(compact)
        except ValueError:
            return None
        return v if 0 <= v <= 9_999_999 else None

    words = _tokens(raw)
    if not words:
        return None

    current = 0
    result = 0
    for word in words:
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        elif word == "thousand":
            result += current * 1000
            current = 0
        elif word == "million":
            result += current * 1_000_000
            current = 0
        else:
            return None

    n = result + current
    if n < 0 or n > 9_999_999:
        return None
    return n


def figures_words_party_mismatches(
    party_results: dict[str, int],
    party_in_words: dict[str, str],
) -> list[dict[str, str | int]]:
    """Parties where \"in words\" parses to a different integer than the figures column."""
    out: list[dict[str, str | int]] = []
    for party, fig in party_results.items():
        wraw = (party_in_words or {}).get(party, "")
        if not isinstance(wraw, str):
            continue
        wraw = wraw.strip()
        if not wraw:
            continue
        parsed = parse_english_int(wraw)
        if parsed is None:
            continue
        if parsed != int(fig):
            out.append(
                {
                    "party": party,
                    "figures": int(fig),
                    "words_raw": wraw,
                    "parsed_from_words": parsed,
                }
            )
    return out


def figures_words_summary_mismatches(
    summary: dict[str, int],
    summary_in_words: dict[str, str],
) -> list[dict[str, str | int]]:
    """Totals row: words column vs figures for total_valid / rejected / total_cast."""
    out: list[dict[str, str | int]] = []
    if not summary_in_words:
        return out
    for key in ("total_valid", "rejected", "total_cast"):
        fig = summary.get(key)
        if fig is None:
            continue
        wraw = summary_in_words.get(key, "")
        if not isinstance(wraw, str):
            continue
        wraw = wraw.strip()
        if not wraw:
            continue
        parsed = parse_english_int(wraw)
        if parsed is None:
            continue
        if parsed != int(fig):
            out.append(
                {
                    "field": key,
                    "figures": int(fig),
                    "words_raw": wraw,
                    "parsed_from_words": parsed,
                }
            )
    return out
