"""object_storage path safety and local I/O."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.object_storage import get_bytes_local, put_bytes_local


def test_put_rejects_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        with pytest.raises(ValueError):
            put_bytes_local(base, "../etc/passwd", b"x")


def test_put_and_get_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        put_bytes_local(base, "a/b/c.bin", b"hello")
        assert get_bytes_local(base, "a/b/c.bin") == b"hello"
        assert get_bytes_local(base, "missing") is None
