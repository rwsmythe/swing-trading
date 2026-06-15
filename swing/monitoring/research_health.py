"""Research data-collection-health monitor (Phase 18 Arc 18-D, SCRIPT-FIRST).

Read-only, aggregating monitor over EXISTING research data-collection signals --
the temporal-log finiteness, the engine funnel manifest, observation coverage +
structural integrity, the drumbeat liveness, candidate completeness, and the
yfinance fetch-transport indicator. Aggregates; instruments nothing. Returns the
CHARC-owned §3 status envelope (monitor="research_measurement",
overall=worst_of(checks), a fresh aware-UTC generated_ts) that 18-F's research
stoplight consumes at the shared artifact path. stdlib only in this module's own
code; NO pandas; ASCII only; never writes the DB.

The session-arithmetic + repo readers + finiteness predicate + engine manifest
JSON it reuses are LAZY-imported inside the check functions (the no-pandas-in-
monitor mandate + the import-hazard precedent). The 3 research-artifact contract
constants are IMPORTED from swing.monitoring.stoplights (LOCK C1 -- single
source; never redeclared). Mirrors 18-E's swing/monitoring/tool_health.py.

generated_ts DIVERGES from 18-E's naive-local stamp: it is AWARE-UTC (Codex R1
MAJOR #1). 18-E's envelope is consumed in-process; 18-D's round-trips through the
18-F reader's staleness gate, which compares against the HOST wall clock -- a
naive-Hawaii stamp would false-grey on a non-Hawaii host. Aware-UTC makes the
reader take its aware branch (datetime.now(parsed.tzinfo)) -> host-independent.
Do NOT consistency-fix it back to naive-local.
"""
from __future__ import annotations

import sqlite3  # noqa: F401  (used in the per-check signatures below)
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

# LOCK C1 (brief §3 / §6.1): IMPORT the 3 contract constants -- never redeclare.
# No circular-import risk: stoplights.py lazy-imports tool_health and does NOT
# import research_health at module top (verified stoplights.py:13-19,124).
from swing.monitoring.stoplights import (  # noqa: F401
    RESEARCH_ARTIFACT_MAX_AGE_DAYS,
    RESEARCH_HEALTH_ARTIFACT_PATH,
    RESEARCH_MONITOR_ID,
)

# worst_of is the canonical red>yellow>green helper (single source); import it
# rather than redeclaring a second source of truth (plan Task 1, Codex watch).
from swing.monitoring.tool_health import worst_of  # noqa: F401

_STATUS_VALUES = frozenset({"green", "yellow", "red"})


def _research_now_iso(now_naive_local: datetime | None = None) -> str:
    """Aware-UTC ISO-8601 stamp (Codex R1 MAJOR #1). `now_naive_local` is the
    aggregator's normalized naive-Hawaii-local clock; None -> the Hawaii wall
    clock. Attach Pacific/Honolulu then convert to UTC (NOT replace(tzinfo=UTC),
    which mis-shifts a Hawaii instant by ~10h) -> a `...+00:00` string the 18-F
    reader parses as aware -> host-tz-independent staleness compare."""
    if now_naive_local is None:
        return datetime.now(UTC).isoformat(timespec="seconds")
    return (
        now_naive_local.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
        .astimezone(UTC)
        .isoformat(timespec="seconds")
    )


@dataclass(frozen=True)
class ResearchHealthCheck:
    key: str
    status: str
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(
                f"ResearchHealthCheck.status must be one of {sorted(_STATUS_VALUES)};"
                f" got {self.status!r} (grey is an 18-F render-only state, not"
                " monitor-emitted)"
            )
        if not self.key:
            raise ValueError("ResearchHealthCheck.key must be non-empty")
        if not self.summary:
            raise ValueError("ResearchHealthCheck.summary must be non-empty")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ResearchHealthStatus:
    overall: str
    checks: list[ResearchHealthCheck]
    generated_ts: str = field(default_factory=_research_now_iso)

    def __post_init__(self) -> None:
        if self.overall not in _STATUS_VALUES:
            raise ValueError(
                f"ResearchHealthStatus.overall must be one of"
                f" {sorted(_STATUS_VALUES)}; got {self.overall!r}"
            )
        # Coerce checks to a tuple so a caller cannot mutate it post-construction
        # and desync overall from checks (the frozen dataclass keeps the locked
        # contract immutable).
        if not isinstance(self.checks, tuple):
            object.__setattr__(self, "checks", tuple(self.checks))
        # Codex R5 MAJOR #1 (gate 5 empty-list): the 18-F reader greys an
        # empty-checks artifact (stoplights.py:65); worst_of([]) == "green" would
        # otherwise let ResearchHealthStatus(overall="green", checks=[])
        # serialize a green-LOOKING envelope the reader then greys -> a
        # non-conformant envelope IS constructible. Reject empty BEFORE the
        # worst-of compare (which would PASS for overall="green").
        if not self.checks:
            raise ValueError(
                "ResearchHealthStatus.checks must be non-empty (the 18-F reader"
                " greys an empty-checks artifact)"
            )
        # Enforce the locked invariant overall == worst_of(checks) (gate 4 by
        # construction) so an inconsistent false-green envelope is unconstructable.
        expected = worst_of([c.status for c in self.checks])
        if self.overall != expected:
            raise ValueError(
                f"ResearchHealthStatus.overall {self.overall!r} != worst_of(checks)"
                f" {expected!r}; the envelope contract requires overall=worst-of"
            )

    def to_dict(self) -> dict:
        return {
            "monitor": RESEARCH_MONITOR_ID,
            "generated_ts": self.generated_ts,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }
