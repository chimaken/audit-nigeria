"""
Test DB: file-backed SQLite (reliable across async connections).
PostgreSQL JSONB columns are swapped to JSON before metadata is used.

DATABASE_URL must be set before any import of `app.db.session` (which builds the engine).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_fd, _tmp_path = tempfile.mkstemp(suffix=".pytest.sqlite")
os.close(_fd)
TEST_SQLITE_PATH = Path(_tmp_path)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_SQLITE_PATH.as_posix()}"
os.environ.setdefault("PUBLIC_BASE_URL", "http://test")

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Base

for _table in Base.metadata.tables.values():
    for _col in _table.columns:
        if isinstance(_col.type, JSONB):
            _col.type = JSON()
