"""Naive-UTC millisecond-precision datetime helpers for Phase 9 audit tables.

Per Phase 9 spec §9.3 + §3.1.3 R3 Major #1 + R4 Minor #1: TEXT datetime
columns store naive-UTC ISO datetimes with millisecond precision
(``YYYY-MM-DDTHH:MM:SS.SSS``). Lexicographic ordering on TEXT columns is
preserved when inputs are naive AND uniform precision.

``now_ms()`` does a SINGLE bind to ``datetime.utcnow()`` so the seconds and
millisecond fragment come from the same instant — two ``utcnow()`` calls
straddling a second boundary would otherwise produce a stamp whose
millisecond fragment belongs to a different second than its ``HH:MM:SS``
prefix (R4 Minor #1). The module-level ``datetime`` import is the binding
seam tests monkeypatch to inject a fixed clock.
"""
from __future__ import annotations

import re
from datetime import datetime

_MS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")


def now_ms() -> str:
    """Return naive-UTC millisecond-precision ISO datetime string.

    Single bind to ``datetime.utcnow()`` ensures the seconds and millisecond
    fragment come from the same instant (Phase 9 spec §3.1.3 R4 Minor #1).
    Microseconds truncate (not round) via integer division to match SQLite
    ``strftime('%f', 'now')`` semantics.
    """
    n = datetime.utcnow()
    return n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}"


def validate_ms_iso(s: str) -> str:
    """Validate that ``s`` matches the naive-UTC millisecond-precision form.

    Returns ``s`` unchanged on success so callers can chain
    ``column = validate_ms_iso(value)``.

    Raises:
        ValueError: when input is non-string, second-precision-only,
        microsecond-precision, or carries a timezone suffix
        (``+NN:NN`` / ``Z``).
    """
    if not isinstance(s, str):
        raise ValueError(f"expected str; got {type(s).__name__}")
    if "+" in s or s.endswith("Z"):
        raise ValueError(
            f"datetime must be naive (no tz suffix +HH:MM or Z); got {s!r}"
        )
    if not _MS_PATTERN.match(s):
        raise ValueError(
            "datetime must be millisecond precision "
            f"(YYYY-MM-DDTHH:MM:SS.SSS); got {s!r}"
        )
    return s
