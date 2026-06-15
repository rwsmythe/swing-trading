"""Task 1 -- research-health envelope dataclasses + imported contract constants.

Mirrors tests/monitoring/test_tool_health_envelope shape; encodes the §3-locked
contract: frozenset status validation (REJECT grey, the 18-F render-only state),
the overall==worst_of(checks) invariant, the non-empty-checks reject (Codex R5
MAJOR #1), worst_of severity ordering (NOT lexical), the to_dict envelope, the
imported monitor id (LOCK C1), and the aware-UTC default generated_ts (the 18-F
host-tz-independent staleness fix, Codex R1 MAJOR #1).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    worst_of,
)
from swing.monitoring.stoplights import RESEARCH_MONITOR_ID


def test_check_rejects_grey() -> None:
    with pytest.raises(ValueError):
        ResearchHealthCheck(key="x", status="grey", summary="s")


def test_check_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        ResearchHealthCheck(key="x", status="purple", summary="s")


def test_check_rejects_empty_key_and_summary() -> None:
    with pytest.raises(ValueError):
        ResearchHealthCheck(key="", status="green", summary="s")
    with pytest.raises(ValueError):
        ResearchHealthCheck(key="k", status="green", summary="")


def test_status_rejects_unknown_overall() -> None:
    with pytest.raises(ValueError):
        ResearchHealthStatus(
            overall="purple",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
        )


def test_status_enforces_overall_equals_worst_of() -> None:
    # Both overall="green" AND check status "red" are VALID enum values; an
    # enum-only impl does NOT raise here. worst_of(["red"]) == "red" != "green".
    with pytest.raises(ValueError, match="worst_of"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="red", summary="s")],
        )


def test_status_rejects_empty_checks() -> None:
    # The 18-F reader greys an empty-checks artifact; worst_of([]) == "green"
    # would otherwise construct a green-LOOKING envelope the reader greys.
    with pytest.raises(ValueError, match="non-empty"):
        ResearchHealthStatus(overall="green", checks=[])


def test_worst_of() -> None:
    assert worst_of([]) == "green"
    assert worst_of(["green", "green"]) == "green"
    assert worst_of(["green", "yellow"]) == "yellow"
    # NOT lexical: max("yellow","red","green") == "yellow" lexically (wrong).
    assert worst_of(["yellow", "red", "green"]) == "red"


def test_worst_of_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        worst_of(["grey"])


def test_to_dict_matches_envelope() -> None:
    status = ResearchHealthStatus(
        overall="yellow",
        checks=[
            ResearchHealthCheck(
                key="temporal_log_finiteness",
                status="yellow",
                summary="3 non-finite OHLC observations",
                detail="oldest 2026-06-10",
            ),
            ResearchHealthCheck(
                key="structural_integrity",
                status="green",
                summary="0 orphans, 0 look-ahead",
            ),
        ],
        # a FRESH aware-UTC stamp (the __post_init__ freshness gate rejects an
        # already-stale construction -- Codex R3 MAJOR #2).
        generated_ts=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    fresh_ts = status.generated_ts
    d = status.to_dict()
    assert d == {
        "monitor": "research_measurement",
        "generated_ts": fresh_ts,
        "overall": "yellow",
        "checks": [
            {
                "key": "temporal_log_finiteness",
                "status": "yellow",
                "summary": "3 non-finite OHLC observations",
                "detail": "oldest 2026-06-10",
            },
            {
                "key": "structural_integrity",
                "status": "green",
                "summary": "0 orphans, 0 look-ahead",
                "detail": None,
            },
        ],
    }
    # round-trips through json (no NaN / non-serializable values)
    assert json.loads(json.dumps(d)) == d
    # envelope stability: `detail` key present even when None (gate 5 allows None)
    assert "detail" in d["checks"][1]


def test_monitor_field_is_research_measurement() -> None:
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
    )
    assert status.to_dict()["monitor"] == "research_measurement"
    # sourced from the IMPORTED constant, not a redeclared literal (LOCK C1)
    assert status.to_dict()["monitor"] == RESEARCH_MONITOR_ID


def test_status_rejects_naive_generated_ts() -> None:
    # Codex R2 MAJOR #3: a naive (tz-less) stamp would false-grey on a non-Hawaii
    # host -> the envelope is non-conformant -> must be unconstructable.
    with pytest.raises(ValueError, match="aware-UTC"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
            generated_ts="2026-06-14T20:31:00",
        )


def test_status_rejects_aware_non_utc_generated_ts() -> None:
    # Codex R3 MAJOR #3: an aware but NON-UTC offset violates the aware-UTC lock.
    now_hst = datetime.now(ZoneInfo("Pacific/Honolulu")).isoformat(timespec="seconds")
    with pytest.raises(ValueError, match="aware-UTC"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
            generated_ts=now_hst,
        )


def test_status_rejects_stale_generated_ts() -> None:
    # Codex R3 MAJOR #2: an already-stale (>7d) stamp would grey through the 18-F
    # reader -> must be unconstructable (the by-construction freshness gate).
    stale = (datetime.now(UTC) - timedelta(days=8)).isoformat(timespec="seconds")
    with pytest.raises(ValueError, match="stale"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
            generated_ts=stale,
        )


def test_check_rejects_non_str_key_summary_detail() -> None:
    # Codex R3 MAJOR #4: non-string key/summary/detail must be rejected by type.
    with pytest.raises(ValueError, match="str"):
        ResearchHealthCheck(key=123, status="green", summary="s")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="str"):
        ResearchHealthCheck(key="k", status="green", summary={"x": 1})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="str"):
        ResearchHealthCheck(key="k", status="green", summary="s", detail=[1])  # type: ignore[arg-type]


def test_status_rejects_unparseable_generated_ts() -> None:
    with pytest.raises(ValueError, match="ISO"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
            generated_ts="not-a-timestamp",
        )


def test_status_rejects_future_generated_ts() -> None:
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat(timespec="seconds")
    with pytest.raises(ValueError, match="future"):
        ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
            generated_ts=future,
        )


def test_generated_ts_default_is_aware_utc() -> None:
    # Omit generated_ts -> the default factory stamps aware-UTC ("...+00:00").
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
    )
    parsed = datetime.fromisoformat(status.generated_ts)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
