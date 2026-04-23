from __future__ import annotations

import pytest

from app.services.number_words import parse_english_int


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("  ", None),
        ("42", 42),
        ("Forty two", 42),
        ("One hundred and twenty three", 123),
        ("fourty two", 42),  # common misspelling
    ],
)
def test_parse_english_int(text: str, expected: int | None) -> None:
    assert parse_english_int(text) == expected
