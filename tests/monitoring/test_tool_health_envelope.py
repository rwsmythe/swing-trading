"""Task 1 -- the tool-health envelope dataclasses + JSON serialization."""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from swing.monitoring.tool_health import (
    ToolHealthCheck,
    ToolHealthStatus,
    worst_of,
)


def test_check_rejects_unknown_status():
    # grey is a render-only 18-F state, never monitor-emitted (brief sec 3).
    # Pre-fix (no __post_init__ validation): constructs fine.
    # Post-fix: raises ValueError.
    with pytest.raises(ValueError):
        ToolHealthCheck(key="x", status="grey", summary="s")


def test_status_rejects_unknown_overall():
    with pytest.raises(ValueError):
        ToolHealthStatus(overall="purple", checks=[])


def test_worst_of():
    # red > yellow > green; NOT lexical (lexically max(["yellow","red","green"])
    # == "yellow", since "red" < "yellow"). The rank impl returns "red".
    assert worst_of([]) == "green"
    assert worst_of(["green", "green"]) == "green"
    assert worst_of(["green", "yellow"]) == "yellow"
    assert worst_of(["yellow", "red", "green"]) == "red"


def test_to_dict_matches_envelope():
    status = ToolHealthStatus(
        overall="yellow",
        checks=[
            ToolHealthCheck(
                key="schwab_token_ttl",
                status="yellow",
                summary="Schwab token expires in 2 days",
                detail="refresh by ...",
            )
        ],
        generated_ts="2026-06-14T20:31:00",
    )
    d = status.to_dict()
    assert d == {
        "monitor": "tool_health",
        "generated_ts": "2026-06-14T20:31:00",
        "overall": "yellow",
        "checks": [
            {
                "key": "schwab_token_ttl",
                "status": "yellow",
                "summary": "Schwab token expires in 2 days",
                "detail": "refresh by ...",
            }
        ],
    }
    # round-trips through json without exception, parses back equal.
    assert json.loads(json.dumps(d)) == d
    # detail=None serializes WITH the key (envelope stability).
    none_detail = ToolHealthStatus(
        overall="green",
        checks=[ToolHealthCheck(key="k", status="green", summary="ok")],
        generated_ts="2026-06-14T20:31:00",
    ).to_dict()
    assert "detail" in none_detail["checks"][0]
    assert none_detail["checks"][0]["detail"] is None


def test_monitor_field_is_tool_health():
    d = ToolHealthStatus(overall="green", checks=[]).to_dict()
    assert d["monitor"] == "tool_health"


def test_generated_ts_default_is_naive_iso():
    status = ToolHealthStatus(overall="green", checks=[])
    ts = status.generated_ts
    # parses as a naive ISO-8601 string, no tz suffix (project convention).
    datetime.fromisoformat(ts)
    assert "T" in ts and "+" not in ts and not ts.endswith("Z")


def test_worst_of_rejects_unknown_status():
    # Codex R1 MINOR #1: unknown status -> ValueError, NOT a bare KeyError.
    with pytest.raises(ValueError):
        worst_of(["grey"])


def test_status_checks_coerced_to_immutable_tuple():
    # Codex R1 MINOR (R1 of the executing review): the locked envelope must not be
    # mutable post-construction. checks is coerced to a tuple in __post_init__.
    src = [ToolHealthCheck(key="k", status="green", summary="ok")]
    status = ToolHealthStatus(overall="green", checks=src)
    assert isinstance(status.checks, tuple)
    # mutating the source list after construction does NOT leak into the envelope.
    src.append(ToolHealthCheck(key="k2", status="red", summary="bad"))
    assert len(status.checks) == 1
    # the envelope itself exposes no .append (it's a tuple).
    with pytest.raises(AttributeError):
        status.checks.append(ToolHealthCheck(key="k3", status="red", summary="x"))
