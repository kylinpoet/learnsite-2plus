from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a UTC timestamp normalized to naive UTC for SQLite DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)
