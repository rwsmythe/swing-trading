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
from datetime import datetime, timedelta

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
        generated_ts="2026-06-14T20:31:00",
    )
    d = status.to_dict()
    assert d == {
        "monitor": "research_measurement",
        "generated_ts": "2026-06-14T20:31:00",
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


def test_generated_ts_default_is_aware_utc() -> None:
    # Omit generated_ts -> the default factory stamps aware-UTC ("...+00:00").
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s")],
    )
    parsed = datetime.fromisoformat(status.generated_ts)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
