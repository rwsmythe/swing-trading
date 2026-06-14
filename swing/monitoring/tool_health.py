"""Operational tool-health monitor (Phase 18 Arc 18-E).

Read-only roll-up of EXISTING data-collection-enabling signals -- pipeline-run
health, Schwab token TTL, OHLCV + weather freshness. Aggregates; instruments
nothing. Returns the CHARC-owned monitor-status envelope (the contract 18-F's
stoplight + 18-D's research monitor consume). stdlib only in this module's own
code; ASCII only; never writes the DB.

The session-arithmetic + schwab-TTL + repo readers it reuses are LAZY-imported
inside the check functions (the schwabdev-import hazard + the no-pandas-in-
monitor-code mandate -- see LOCK #4 in the plan).
"""
from __future__ import annotations

import sqlite3  # noqa: F401  (used in compute_tool_health signature later)
from dataclasses import dataclass, field
from datetime import datetime

_STATUS_VALUES = frozenset({"green", "yellow", "red"})
_SEVERITY_RANK = {"green": 0, "yellow": 1, "red": 2}
_MONITOR_ID = "tool_health"


def worst_of(statuses: list[str]) -> str:
    """red > yellow > green; empty -> green. NOT lexical order.

    Codex R1 MINOR #1: validate each status against _STATUS_VALUES so an
    unknown value raises a contract-shaped ValueError (not a bare KeyError
    from the rank lookup) -- belt-and-suspenders since ToolHealthCheck
    already validates at construction.
    """
    worst = "green"
    for s in statuses:
        if s not in _STATUS_VALUES:
            raise ValueError(
                f"worst_of: unknown status {s!r}; must be one of"
                f" {sorted(_STATUS_VALUES)}"
            )
        if _SEVERITY_RANK[s] > _SEVERITY_RANK[worst]:
            worst = s
    return worst


@dataclass(frozen=True)
class ToolHealthCheck:
    key: str
    status: str
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(
                f"ToolHealthCheck.status must be one of {sorted(_STATUS_VALUES)};"
                f" got {self.status!r} (grey is an 18-F render-only state, not"
                " monitor-emitted)"
            )
        if not self.key:
            raise ValueError("ToolHealthCheck.key must be non-empty")
        if not self.summary:
            raise ValueError("ToolHealthCheck.summary must be non-empty")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "detail": self.detail,
        }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class ToolHealthStatus:
    overall: str
    checks: list[ToolHealthCheck]
    generated_ts: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.overall not in _STATUS_VALUES:
            raise ValueError(
                f"ToolHealthStatus.overall must be one of {sorted(_STATUS_VALUES)};"
                f" got {self.overall!r}"
            )

    def to_dict(self) -> dict:
        return {
            "monitor": _MONITOR_ID,
            "generated_ts": self.generated_ts,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }
