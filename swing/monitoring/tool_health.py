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

# Pipeline freshness: how many action-sessions behind the last COMPLETE run may
# be before escalating. Calibrated against the dashboard stale-banner (which
# flags at >=1 session behind). 1 session behind -> yellow; >=2 -> red.
_PIPELINE_FRESH_YELLOW_SESSIONS = 1
_PIPELINE_FRESH_RED_SESSIONS = 2
# Recent-runs window for the failure tally.
_PIPELINE_RECENT_RUNS_WINDOW = 5
# Pipeline run states counted as a recent failure.
_PIPELINE_FAILURE_STATES = ("failed", "force_cleared")


def _schema_unavailable(exc: sqlite3.OperationalError) -> bool:
    """True iff `exc` is a missing-table/column error (degrade-to-yellow), so a
    pre-schema / degraded DB does not crash the monitor. Any OTHER
    OperationalError re-raises (Codex R2 MINOR #1 -- do not mask real defects)."""
    msg = str(exc)
    return "no such table" in msg or "no such column" in msg


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


# --------------------------------------------------------------------------
# Per-check helpers (lazy-import the reused readers/helpers; NO pandas here).
# --------------------------------------------------------------------------


def _check_pipeline_run(
    conn: sqlite3.Connection, *, cfg, now: datetime
) -> list[ToolHealthCheck]:
    """Pipeline-run health via the documented two-read pattern.

    Emits up to three checks (all key-prefixed `pipeline_`):
      - pipeline_freshness: most-recent COMPLETE run's action_session_date vs
        action_session_for_run(now) (the dashboard stale-banner anchor), counted
        in NYSE sessions via sessions_behind. 0 -> green; 1 -> yellow; >=2 -> red;
        no completed run -> red.
      - pipeline_wedged: a running run whose heartbeat + step-progress are both
        stale (is_stale_eligible) -> red; running-but-fresh -> green; no running
        row -> green; cfg None -> green (degraded skip; heartbeat thresholds need
        cfg).
      - pipeline_failures: count of recent failed/force_cleared runs -> yellow if
        >=1, else green.

    A missing pipeline_runs table degrades to a single yellow "schema
    unavailable" check (Codex R1 MAJOR #4); any other OperationalError re-raises.
    """
    from datetime import date as _date

    from swing.data.repos.pipeline import (
        find_active_run,
        list_recent_runs,
    )
    from swing.evaluation.dates import action_session_for_run, sessions_behind
    from swing.web.chart_scope import latest_completed_pipeline_run

    try:
        binding = latest_completed_pipeline_run(conn)
        active = find_active_run(conn)
        recent = list_recent_runs(conn, limit=_PIPELINE_RECENT_RUNS_WINDOW)
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [
                ToolHealthCheck(
                    key="pipeline_schema",
                    status="yellow",
                    summary="pipeline schema unavailable",
                    detail="pipeline_runs table missing; run swing db-migrate",
                )
            ]
        raise

    checks: list[ToolHealthCheck] = []

    # (a) freshness
    if binding is None:
        checks.append(
            ToolHealthCheck(
                key="pipeline_freshness",
                status="red",
                summary="no completed pipeline run recorded",
                detail="the collection apparatus has never completed a run",
            )
        )
    else:
        anchor = action_session_for_run(now)
        behind = sessions_behind(anchor, _date.fromisoformat(binding.action_session_date))
        if behind <= 0:
            status = "green"
        elif behind <= _PIPELINE_FRESH_YELLOW_SESSIONS:
            status = "yellow"
        else:
            status = "red"
        checks.append(
            ToolHealthCheck(
                key="pipeline_freshness",
                status=status,
                summary=(
                    f"last complete run covers session {binding.action_session_date}"
                    f" ({behind} session(s) behind)"
                ),
                detail=f"finished_ts {binding.finished_ts}",
            )
        )

    # (b) wedged
    if active is None:
        checks.append(
            ToolHealthCheck(
                key="pipeline_wedged",
                status="green",
                summary="no active pipeline run",
            )
        )
    elif cfg is None:
        checks.append(
            ToolHealthCheck(
                key="pipeline_wedged",
                status="green",
                summary="pipeline running (wedged-check skipped; cfg n/a)",
            )
        )
    else:
        from swing.pipeline.staleness import is_stale_eligible

        if is_stale_eligible(active, cfg, now=now):
            checks.append(
                ToolHealthCheck(
                    key="pipeline_wedged",
                    status="red",
                    summary="pipeline run wedged: heartbeat + step-progress stale",
                    detail=(
                        f"run {active.id} step {active.current_step!r};"
                        " consider swing pipeline force-clear"
                    ),
                )
            )
        else:
            checks.append(
                ToolHealthCheck(
                    key="pipeline_wedged",
                    status="green",
                    summary="pipeline running",
                    detail=f"run {active.id} step {active.current_step!r}",
                )
            )

    # (c) recent failures
    n_failures = sum(1 for r in recent if r.state in _PIPELINE_FAILURE_STATES)
    if n_failures >= 1:
        checks.append(
            ToolHealthCheck(
                key="pipeline_failures",
                status="yellow",
                summary=f"{n_failures} recent pipeline failure(s)",
                detail=f"within the last {_PIPELINE_RECENT_RUNS_WINDOW} runs",
            )
        )
    else:
        checks.append(
            ToolHealthCheck(
                key="pipeline_failures",
                status="green",
                summary="no recent pipeline failures",
            )
        )

    return checks


def _check_schwab_token(*, cfg, now: datetime) -> list[ToolHealthCheck]:
    """Schwab refresh-token TTL via the cli_schwab severity tiers (no re-derive).

    LAZY-imports the TTL + threshold constants + readers from swing.cli_schwab
    (the schwabdev-import hazard). The tokens file writes aware-UTC timestamps,
    so `_parse_iso_datetime` returns an AWARE dt; `now` is naive-Hawaii-local.
    The two operands need DIFFERENT normalize rules (a naive `now` is NOT UTC --
    treating it as UTC mis-shifts by ~10h and can flip the 24h/2h boundary):
      - now -> UTC: attach Pacific/Honolulu then convert (NOT replace(tzinfo=UTC)).
      - issued -> UTC: replace(tzinfo=UTC) for naive (token timestamps ARE UTC).
    Absence of Schwab (no cfg, empty client_id, or no tokens DB) is green/"n/a".
    """
    from datetime import UTC, timedelta
    from zoneinfo import ZoneInfo

    from swing.cli_schwab import (
        _REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS,
        _REFRESH_TOKEN_TTL_SECONDS,
        _REFRESH_TOKEN_WARN_THRESHOLD_SECONDS,
        _parse_iso_datetime,
        _read_tokens_metadata,
    )
    from swing.config_user import _user_home

    key = "schwab_token_ttl"

    if cfg is None or cfg.integrations.schwab.client_id == "":
        return [ToolHealthCheck(key=key, status="green",
                                summary="Schwab not configured (n/a)")]

    env = cfg.integrations.schwab.environment
    tokens_path = _user_home() / "swing-data" / f"schwab-tokens.{env}.db"
    if not tokens_path.exists():
        return [ToolHealthCheck(key=key, status="green",
                                summary="Schwab tokens not present (n/a)")]

    meta, error_message = _read_tokens_metadata(tokens_path)
    if meta is None and error_message is None:
        return [ToolHealthCheck(key=key, status="green",
                                summary="Schwab tokens not present (n/a)")]
    if meta is None:
        return [ToolHealthCheck(key=key, status="yellow",
                                summary="Schwab tokens unreadable",
                                detail=str(error_message))]

    issued_iso = meta.get("refresh_token_issued")
    issued_dt = _parse_iso_datetime(issued_iso) if issued_iso else None
    if issued_dt is None:
        return [ToolHealthCheck(
            key=key, status="yellow",
            summary="Schwab token issue date unknown; run swing schwab status")]

    def _now_to_utc(n: datetime) -> datetime:
        if n.tzinfo is not None:
            return n.astimezone(UTC)
        return n.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(UTC)

    def _issued_to_utc(i: datetime) -> datetime:
        if i.tzinfo is not None:
            return i.astimezone(UTC)
        return i.replace(tzinfo=UTC)

    now_utc = _now_to_utc(now)
    expires_utc = _issued_to_utc(issued_dt) + timedelta(
        seconds=_REFRESH_TOKEN_TTL_SECONDS)
    delta_seconds = (expires_utc - now_utc).total_seconds()

    if delta_seconds <= 0:
        days_ago = int((-delta_seconds) // 86400)
        return [ToolHealthCheck(
            key=key, status="red",
            summary=f"Schwab token EXPIRED {days_ago} day(s) ago; swing schwab setup")]
    if delta_seconds <= _REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS:
        return [ToolHealthCheck(
            key=key, status="red",
            summary="Schwab token expires in <2h; swing schwab setup")]
    if delta_seconds <= _REFRESH_TOKEN_WARN_THRESHOLD_SECONDS:
        return [ToolHealthCheck(
            key=key, status="yellow",
            summary="Schwab token expires in <1 day; swing schwab setup")]
    days = int(delta_seconds // 86400)
    return [ToolHealthCheck(
        key=key, status="green", summary=f"Schwab token valid for {days} day(s)")]
