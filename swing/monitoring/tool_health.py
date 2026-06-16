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
# OHLCV archive WRITE recency (calendar days; 4 tolerates a normal weekend,
# matching weekly_glance.T1_MAX_AGE_DAYS). >4 -> yellow; >7 -> red.
_OHLCV_FRESH_YELLOW_DAYS = 4
_OHLCV_FRESH_RED_DAYS = 7
# Weather freshness in NYSE sessions behind last_completed_session.
_WEATHER_FRESH_YELLOW_SESSIONS = 1
_WEATHER_FRESH_RED_SESSIONS = 2


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
        # Codex R1 MINOR: the envelope is the locked contract -- coerce checks to
        # a tuple so a caller cannot mutate it post-construction and desync
        # `overall` from `checks`. The dataclass is frozen, so set via
        # object.__setattr__.
        if not isinstance(self.checks, tuple):
            object.__setattr__(self, "checks", tuple(self.checks))
        # Codex R2 MINOR: enforce the locked invariant overall == worst_of(checks)
        # so an inconsistent envelope cannot be constructed/serialized.
        expected = worst_of([c.status for c in self.checks])
        if self.overall != expected:
            raise ValueError(
                f"ToolHealthStatus.overall {self.overall!r} != worst_of(checks)"
                f" {expected!r}; the envelope contract requires overall=worst-of"
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
    key = "schwab_token_ttl"

    # n/a short-circuit BEFORE importing cli_schwab (Codex R3 MINOR -- keep the
    # schwabdev stack off the bare-call / unconfigured path; LOCK #4).
    if cfg is None or cfg.integrations.schwab.client_id == "":
        return [ToolHealthCheck(key=key, status="green",
                                summary="Schwab not configured (n/a)")]

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

    env = cfg.integrations.schwab.environment
    tokens_path = _user_home() / "swing-data" / f"schwab-tokens.{env}.db"
    _not_authed_summary = "Schwab configured but not authenticated; run swing schwab setup"
    if not tokens_path.exists():
        return [ToolHealthCheck(key=key, status="yellow",
                                summary=_not_authed_summary,
                                detail="no tokens DB on disk")]

    meta, error_message = _read_tokens_metadata(tokens_path)
    if meta is None and error_message is None:
        return [ToolHealthCheck(key=key, status="yellow",
                                summary=_not_authed_summary,
                                detail="tokens DB present but empty")]
    if meta is None:
        return [ToolHealthCheck(key=key, status="yellow",
                                summary="Schwab tokens unreadable",
                                detail=str(error_message))]

    # Codex R3 MAJOR: a present row with empty refresh_token bytes means Schwab
    # CANNOT refresh -- data-present-but-broken, NOT config-absence -> red. The
    # signal already exists in meta (computed in SQL by _read_tokens_metadata).
    if not meta.get("refresh_token_present"):
        return [ToolHealthCheck(
            key=key, status="red",
            summary="Schwab refresh token missing/empty; swing schwab setup")]

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
            summary="Schwab token expires in <=2h; swing schwab setup")]
    if delta_seconds <= _REFRESH_TOKEN_WARN_THRESHOLD_SECONDS:
        return [ToolHealthCheck(
            key=key, status="yellow",
            summary="Schwab token expires in <=1 day; swing schwab setup")]
    days = int(delta_seconds // 86400)
    return [ToolHealthCheck(
        key=key, status="green", summary=f"Schwab token valid for {days} day(s)")]


def _check_data_freshness(
    conn: sqlite3.Connection, *, cfg, prices_cache_dir, now: datetime
) -> list[ToolHealthCheck]:
    """OHLCV archive WRITE-recency + weather asof_date freshness.

    OHLCV: the newest *.parquet mtime in prices_cache_dir (stdlib os.stat; NO
    pandas -- this is WRITE-recency, "is the archive being written", NOT bar
    freshness). The mtime (an absolute POSIX timestamp) is converted to
    naive-Hawaii-local BEFORE subtracting from the naive-Hawaii-local `now`
    (Codex R5 MAJOR #1 -- host-tz independence). A missing cache dir / no parquet
    degrades to green/"n/a". `cfg` is unused by the OHLCV sub-check.

    Weather: get_latest(conn, ticker=cfg.rs.benchmark_ticker).asof_date (a
    DATA-session date -- the weather-keyed-by-data_asof_date gotcha) vs
    last_completed_session(now), counted in NYSE sessions via sessions_behind.
    The live system records weather under the BENCHMARK ticker
    (cfg.rs.benchmark_ticker == "SPY"), NOT get_latest's "QQQ" default -- a
    bare get_latest(conn) returns None on the live DB and false-REDs a current
    system (the QA-caught live false-RED). cfg None -> the benchmark ticker is
    unknown, so weather degrades to green/"n/a" (a missing CONFIG input is
    green/n/a, NOT red -- the ratified degradation; keeps the bare-call
    compute_tool_health(conn) valid). No weather row -> red; a missing
    weather_runs table -> yellow schema-unavailable (any other OperationalError
    re-raises).
    """
    from zoneinfo import ZoneInfo

    from swing.evaluation.dates import last_completed_session, sessions_behind

    checks: list[ToolHealthCheck] = []
    hst = ZoneInfo("Pacific/Honolulu")

    # (a) OHLCV archive write-recency
    if prices_cache_dir is None or not prices_cache_dir.exists():
        checks.append(ToolHealthCheck(
            key="ohlcv_freshness", status="green",
            summary="OHLCV archive freshness n/a (cache dir unavailable)"))
    else:
        parquets = list(prices_cache_dir.glob("*.parquet"))
        if not parquets:
            checks.append(ToolHealthCheck(
                key="ohlcv_freshness", status="green",
                summary="OHLCV archive freshness n/a (no archives written yet)"))
        else:
            newest = max(p.stat().st_mtime for p in parquets)
            mtime_dt = datetime.fromtimestamp(newest, hst).replace(tzinfo=None)
            age_days = (now - mtime_dt).total_seconds() / 86400
            if age_days <= _OHLCV_FRESH_YELLOW_DAYS:
                status = "green"
            elif age_days <= _OHLCV_FRESH_RED_DAYS:
                status = "yellow"
            else:
                status = "red"
            checks.append(ToolHealthCheck(
                key="ohlcv_freshness", status=status,
                summary=f"OHLCV archive last WRITTEN {age_days:.1f} day(s) ago",
                detail=f"newest parquet mtime {mtime_dt.isoformat(timespec='seconds')}"))

    # (b) weather asof_date freshness
    if cfg is None:
        checks.append(ToolHealthCheck(
            key="weather_freshness", status="green",
            summary="weather freshness n/a (benchmark ticker unknown; cfg n/a)"))
        return checks

    try:
        from swing.data.repos.weather import get_latest
        latest = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            checks.append(ToolHealthCheck(
                key="weather_freshness", status="yellow",
                summary="weather schema unavailable",
                detail="weather_runs table missing; run swing db-migrate"))
            return checks
        raise

    if latest is None:
        checks.append(ToolHealthCheck(
            key="weather_freshness", status="red",
            summary="no weather run recorded"))
    else:
        from datetime import date as _date
        anchor = last_completed_session(now)
        behind = sessions_behind(anchor, _date.fromisoformat(latest.asof_date))
        if behind <= 0:
            status = "green"
        elif behind <= _WEATHER_FRESH_YELLOW_SESSIONS:
            status = "yellow"
        else:
            status = "red"
        checks.append(ToolHealthCheck(
            key="weather_freshness", status=status,
            summary=(f"weather current as of {latest.asof_date}"
                     f" ({behind} session(s) behind)"),
            detail=f"pipeline ran {latest.run_ts}"))

    return checks


# --------------------------------------------------------------------------
# Aggregator
# --------------------------------------------------------------------------


def _normalize_now_to_naive_local(now: datetime | None) -> datetime:
    """Normalize `now` to NAIVE Hawaii-local at the compute_tool_health boundary.

    Codex R3 MAJOR #1: the session helpers (action_session_for_run /
    last_completed_session) do now_local.replace(tzinfo=Pacific/Honolulu), which
    RELABELS (not converts) an aware datetime -> mis-anchored sessions. Normalize
    ONCE here so EVERY downstream consumer (the session helpers AND the schwab
    _now_to_utc) receives a naive-Hawaii-local `now`.
      - None -> datetime.now(Pacific/Honolulu) naive (Codex R4 MAJOR #1: the
        Hawaii wall clock, NOT bare datetime.now() which is host-local and
        mis-anchors on a non-Hawaii box).
      - aware -> CONVERT the instant to Hawaii-local THEN strip tzinfo.
      - naive -> pass through (already treated as Hawaii-local by the helpers).
    """
    from zoneinfo import ZoneInfo

    if now is None:
        return datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    return now


def compute_tool_health(
    conn: sqlite3.Connection,
    *,
    cfg=None,
    prices_cache_dir=None,
    now: datetime | None = None,
) -> ToolHealthStatus:
    """Read-only roll-up of the three data-collection-enabling check families.

    The sec-3 envelope contract; the bare-call compute_tool_health(conn) stays
    valid (18-F's consumption point). Never writes the DB. A missing CONFIG input
    degrades a dependent check to green/"n/a"; a missing-TABLE schema degrades to
    yellow "schema unavailable"; missing operational DATA fires red.
    """
    now = _normalize_now_to_naive_local(now)
    checks: list[ToolHealthCheck] = []
    checks += _check_pipeline_run(conn, cfg=cfg, now=now)
    checks += _check_schwab_token(cfg=cfg, now=now)
    checks += _check_data_freshness(
        conn, cfg=cfg, prices_cache_dir=prices_cache_dir, now=now)
    overall = worst_of([c.status for c in checks])
    return ToolHealthStatus(
        overall=overall, checks=checks,
        generated_ts=now.isoformat(timespec="seconds"))
