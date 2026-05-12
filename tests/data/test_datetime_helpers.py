"""Phase 9 T-A.0 — naive-UTC millisecond-precision datetime helpers.

Per spec §9.3 + §3.1.3 R3 Major #1 + R4 Minor #1: TEXT datetime columns
store naive-UTC ISO datetimes with millisecond precision
(YYYY-MM-DDTHH:MM:SS.SSS). Lexicographic ordering is preserved when inputs
are naive + uniform precision. The ``now_ms`` helper performs a single
``datetime.utcnow()`` bind so the seconds and millisecond fragment come from
the same instant (avoids second-boundary skew between two utcnow calls).
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from swing.data.datetime_helpers import now_ms, validate_ms_iso

_MS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")


class _FixedDatetime:
    """Stand-in for ``datetime`` exposing only ``utcnow()``."""

    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def utcnow(self) -> datetime:
        return self._fixed


def test_now_ms_format_conformance() -> None:
    s = now_ms()
    assert _MS_RE.match(s) is not None, f"now_ms() returned non-conforming {s!r}"


def test_now_ms_bind_once_idempotence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two calls backed by the SAME utcnow() must produce the SAME string."""
    fixed = datetime(2026, 5, 11, 14, 30, 45, 123456)
    monkeypatch.setattr("swing.data.datetime_helpers.datetime", _FixedDatetime(fixed))
    a = now_ms()
    b = now_ms()
    assert a == b == "2026-05-11T14:30:45.123"


def test_now_ms_truncates_microseconds_to_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Microsecond ``999999`` truncates (not rounds) to ``999``."""
    fixed = datetime(2026, 5, 11, 14, 30, 45, 999999)
    monkeypatch.setattr("swing.data.datetime_helpers.datetime", _FixedDatetime(fixed))
    assert now_ms() == "2026-05-11T14:30:45.999"


def test_now_ms_zero_microseconds_pads_to_three_digits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Microsecond ``0`` renders as ``.000`` (3-digit zero pad)."""
    fixed = datetime(2026, 5, 11, 14, 30, 45, 0)
    monkeypatch.setattr("swing.data.datetime_helpers.datetime", _FixedDatetime(fixed))
    assert now_ms() == "2026-05-11T14:30:45.000"


def test_now_ms_cross_day_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Day rollover at 00:00:00.001 renders correctly."""
    fixed = datetime(2026, 5, 12, 0, 0, 0, 1000)
    monkeypatch.setattr("swing.data.datetime_helpers.datetime", _FixedDatetime(fixed))
    assert now_ms() == "2026-05-12T00:00:00.001"


def test_validate_ms_iso_accepts_valid() -> None:
    s = "2026-05-11T14:30:45.123"
    assert validate_ms_iso(s) == s


def test_validate_ms_iso_rejects_second_precision() -> None:
    with pytest.raises(ValueError, match="millisecond precision"):
        validate_ms_iso("2026-05-11T14:30:45")


def test_validate_ms_iso_rejects_microsecond_precision() -> None:
    with pytest.raises(ValueError, match="millisecond precision"):
        validate_ms_iso("2026-05-11T14:30:45.123456")


def test_validate_ms_iso_rejects_tz_aware_offset() -> None:
    with pytest.raises(ValueError, match="naive"):
        validate_ms_iso("2026-05-11T14:30:45.123+00:00")


def test_validate_ms_iso_rejects_tz_aware_z_suffix() -> None:
    with pytest.raises(ValueError, match="naive"):
        validate_ms_iso("2026-05-11T14:30:45.123Z")


def test_validate_ms_iso_rejects_non_string() -> None:
    with pytest.raises(ValueError, match="expected str"):
        validate_ms_iso(12345)  # type: ignore[arg-type]
