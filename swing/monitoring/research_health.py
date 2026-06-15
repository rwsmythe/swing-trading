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

import json
import math
import re
import sqlite3  # noqa: F401  (used in the per-check signatures below)
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
_ZERO_OFFSET = timedelta(0)


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
        # Codex R3 MAJOR #4: enforce the 18-F per-check render schema BY TYPE
        # (key/summary non-empty STR; detail None-or-str), not just truthiness --
        # a non-string key/summary/detail would serialize into an envelope the
        # 18-F _worst_check_severity gate then greys.
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("ResearchHealthCheck.key must be a non-empty str")
        if not isinstance(self.summary, str) or not self.summary:
            raise ValueError("ResearchHealthCheck.summary must be a non-empty str")
        if self.detail is not None and not isinstance(self.detail, str):
            raise ValueError("ResearchHealthCheck.detail must be None or a str")

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
        # Codex R2 MAJOR #3 + R3 MAJORs #2/#3: generated_ts must be ISO-parseable,
        # aware-UTC (offset == 0), NOT future-dated, AND NOT already stale at
        # construction (within RESEARCH_ARTIFACT_MAX_AGE_DAYS). The 18-F reader
        # greys a malformed/naive/non-UTC/future/stale stamp, so a green-LOOKING
        # envelope carrying one is non-conformant and must be UNCONSTRUCTABLE (the
        # "by construction" gate). The aggregator always stamps NOW, so a real
        # envelope is always fresh-aware-UTC; the on-disk artifact legitimately
        # ages AFTER it is written (that ageing is on the FILE, not a
        # re-construction -- the reader greys the stale file). Enforcing freshness
        # here only forbids constructing an already-stale envelope, never the
        # legitimate write-then-age path.
        try:
            parsed = datetime.fromisoformat(self.generated_ts)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"ResearchHealthStatus.generated_ts must be ISO-8601;"
                f" got {self.generated_ts!r}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() != _ZERO_OFFSET:
            raise ValueError(
                "ResearchHealthStatus.generated_ts must be aware-UTC"
                f" (offset +00:00, the 18-F host-tz-independent gate); got"
                f" {self.generated_ts!r}"
            )
        age = datetime.now(UTC) - parsed
        if age < _ZERO_OFFSET:
            raise ValueError(
                "ResearchHealthStatus.generated_ts must not be future-dated;"
                f" got {self.generated_ts!r}"
            )
        if age > timedelta(days=RESEARCH_ARTIFACT_MAX_AGE_DAYS):
            raise ValueError(
                "ResearchHealthStatus.generated_ts must not be already stale at"
                f" construction (> {RESEARCH_ARTIFACT_MAX_AGE_DAYS}d); got"
                f" {self.generated_ts!r}"
            )

    def to_dict(self) -> dict:
        return {
            "monitor": RESEARCH_MONITOR_ID,
            "generated_ts": self.generated_ts,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }


# --------------------------------------------------------------------------
# Shared degradation helper (mirror 18-E tool_health._schema_unavailable).
# --------------------------------------------------------------------------


def _schema_unavailable(exc: sqlite3.OperationalError) -> bool:
    """True iff `exc` is a missing-table/column error (degrade-to-yellow). Any
    OTHER OperationalError re-raises (do not mask real defects -- mirror 18-E)."""
    msg = str(exc)
    return "no such table" in msg or "no such column" in msg


# --------------------------------------------------------------------------
# Per-check helpers (lazy-import the reused readers/predicate; NO pandas here).
# --------------------------------------------------------------------------


_OHLC_KEYS = ("open", "high", "low", "close")


def _check_temporal_log_finiteness(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """Data-USABILITY authority (brief §6.2 #1): scan
    pattern_forward_observations.ohlc_today_json for ANY non-finite OHLC -> RED.

    The check that would have caught the 2026-06-10 NaN-Close defect on the day
    it entered. Reuses the shared is_finite_ohlc predicate (NaN/inf), with a
    None/missing/non-numeric GUARD before it (the predicate RAISES TypeError on
    None -- the brief's "reuse the predicate" applies to NaN/inf only). Volume is
    EXEMPT (Arc-8). Missing table -> yellow; empty table -> green (the log
    legitimately starts empty); any non-finite hit -> red.
    """
    from swing.data.ohlcv_finiteness import is_finite_ohlc

    key = "temporal_log_finiteness"
    try:
        rows = conn.execute(
            "SELECT o.observation_id, o.observation_date, o.ohlc_today_json,"
            " d.ticker"
            " FROM pattern_forward_observations o"
            " LEFT JOIN pattern_detection_events d"
            " ON d.detection_id = o.detection_id"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="temporal-log schema unavailable",
                detail="pattern_forward_observations table missing;"
                       " run swing db-migrate")]
        raise

    total = len(rows)
    if total == 0:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no temporal-log observations yet (0 non-finite)")]

    non_finite = 0
    sample: list[str] = []
    for _obs_id, obs_date, ohlc_json, ticker in rows:
        bad = False
        try:
            bar = json.loads(ohlc_json)
        except (TypeError, ValueError):
            bad = True
        else:
            vals = []
            for k in _OHLC_KEYS:
                v = bar.get(k) if isinstance(bar, dict) else None
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    # missing / None / non-numeric -> non-finite hit WITHOUT
                    # calling the predicate (it raises TypeError on None).
                    bad = True
                    break
                vals.append(float(v))
            if not bad and not is_finite_ohlc(*vals):
                bad = True
        if bad:
            non_finite += 1
            if len(sample) < 3:
                sample.append(f"{ticker or '?'}@{obs_date}")

    if non_finite == 0:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary=f"0 non-finite OHLC observations (of {total})")]
    detail = "; ".join(sample) if sample else None
    return [ResearchHealthCheck(
        key=key, status="red",
        summary=f"{non_finite} non-finite OHLC observation(s) of {total}",
        detail=detail)]


# --------------------------------------------------------------------------
# Engine-manifest reader (shared by check #2 + #5; LOCK §4.2 -- READ, never
# recompute attribution).
# --------------------------------------------------------------------------


_ATTRIBUTED_EXCLUDED_REASONS = (
    "invalid_ohlc", "insufficient_forward_depth", "missing_observations",
)
# The per-hypothesis terminal counters the engine emits (run.py / funnel.py).
# Validated as non-negative integer counts for shape-drift defense (Codex R8
# MAJOR #1, narrow part) -- NOT summed/recomputed (LOCK §4.2 no funnel-fork).
_PER_HYP_TERMINAL_CARDS = (
    "closed", "open_at_horizon", "never_triggered",
)
# Excluded-reason rate (% of unique_signals) escalation. invalid_ohlc has run
# ~30% on the live manifest (the 06-10 NaN backlog the engine's belt rejects);
# these are CONSERVATIVE V1 floors -- the RD tunes them post-build.
_EXCL_YELLOW_PCT = 10.0   # any one reason >10% of unique_signals -> yellow
_EXCL_RED_PCT = 25.0      # any one reason >25% -> red


def _is_nonneg_count(v: object) -> bool:
    """True iff v is a non-negative INTEGER count (NOT bool, NOT NaN/inf, NOT a
    FRACTIONAL float).

    Manifest counts are producer-owned integer counters. Codex R2 MAJOR #1: JSON
    NaN/Infinity parse to floats that pass an isinstance check + make every
    threshold compare False (false-green). Codex R5 MAJOR #2: a FRACTIONAL float
    (e.g. invalid_ohlc=10.9) would be int()-truncated to 10, dropping it below a
    boundary -> false-green. So accept an int, or an integer-VALUED float (77.0),
    and reject NaN/inf/negative/fractional -> shape-drift escalates to corrupt.
    """
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v >= 0
    if isinstance(v, float):
        return math.isfinite(v) and v >= 0 and v.is_integer()
    return False


def _excluded_is_well_shaped(excluded: object) -> bool:
    """An `excluded` sub-dict (if present) must be a dict whose CONSUMED reason
    counts are non-negative integer counts (Codex R2 MAJOR #1 + R5 MAJOR #2). A
    list, a non-numeric value, a NaN, or a fractional count -> shape-drift."""
    if excluded is None:
        return True  # absent excluded -> 0 for every reason (legitimate)
    if not isinstance(excluded, dict):
        return False
    for reason in _ATTRIBUTED_EXCLUDED_REASONS:
        if reason in excluded and not _is_nonneg_count(excluded[reason]):
            return False
    return True


def _manifest_is_well_shaped(parsed: object) -> bool:
    """The nested funnel schema gate (Codex R2 MAJOR #3 + R2-rev MAJOR #1 --
    shape-drift defense, STRICT on every CONSUMED field).

    Well-shaped requires: funnel is a dict; funnel.detection_level.unique_signals
    is a non-negative integer count; funnel.per_hypothesis is a dict each of whose
    values is a dict whose `excluded` (if present) is a well-shaped reason dict;
    funnel.unattributed is PRESENT (Codex R5 MAJOR #1 -- a consumed field; a
    missing one is shape-drift, not green) and a dict whose values are
    non-negative integer counts. Anything else -> the caller maps it to "corrupt"
    (NOT "ok"-then-.get-zeros, which would mask a broken latest run as healthy or
    crash on a list/non-numeric value).
    """
    if not isinstance(parsed, dict):
        return False
    funnel = parsed.get("funnel")
    if not isinstance(funnel, dict):
        return False
    detection_level = funnel.get("detection_level")
    if not isinstance(detection_level, dict):
        return False
    if not _is_nonneg_count(detection_level.get("unique_signals")):
        return False
    per_hypothesis = funnel.get("per_hypothesis")
    if not isinstance(per_hypothesis, dict):
        return False
    for hyp in per_hypothesis.values():
        if not isinstance(hyp, dict):
            return False
        if not _excluded_is_well_shaped(hyp.get("excluded")):
            return False
        # Codex R8 MAJOR #1 (narrow part): the per-hypothesis terminal counters
        # (closed / open_at_horizon / never_triggered), when present, must be
        # non-negative integer counts -- a TYPE/SHAPE check (consistent with the
        # _is_nonneg_count discipline), NOT a funnel-sum recompute (that would be
        # the LOCK §4.2 funnel-fork this monitor must never do). The funnel-sum
        # invariant + the empty-per_hypothesis "100 signals, 0 attributed" shape
        # are the ENGINE's accounting, deliberately NOT re-derived here.
        for card_key in _PER_HYP_TERMINAL_CARDS:
            if card_key in hyp and not _is_nonneg_count(hyp[card_key]):
                return False
    # unattributed is a CONSUMED field (drumbeat reads it) -> REQUIRE it present
    # + a dict of integer counts (Codex R5 MAJOR #1).
    unattributed = funnel.get("unattributed")
    if not isinstance(unattributed, dict):
        return False
    return all(_is_nonneg_count(v) for v in unattributed.values())


def _read_newest_manifest(exports_root) -> tuple[str, dict | None]:
    """Read the NEWEST shadow-expectancy-* manifest.json. 3-state result (Codex
    R1 MAJOR #3 -- distinguish ABSENT from CORRUPT):

      - ("absent", None)  -- NO shadow-expectancy-* dir exists at all (the ONLY
        absent case; the engine has never produced an artifact).
      - ("corrupt", None) -- the newest dir EXISTS but has NO manifest.json
        (crashed-mid-write), OR the manifest is unparseable / not a dict /
        shape-drifted (a real degraded state -> >= yellow; never masked as n-a).
      - ("ok", <dict>)    -- parsed successfully AND the nested funnel schema is
        present (so downstream sums can rely on those keys).

    Newest by dir-name reverse-sort (the weekly_glance.py:49-51 precedent). Never
    crashes on the read.
    """
    from pathlib import Path

    root = Path(exports_root)
    if not root.exists():
        return ("absent", None)
    dirs = sorted(
        (p for p in root.glob("shadow-expectancy-*") if p.is_dir()),
        reverse=True,
    )
    if not dirs:
        return ("absent", None)
    newest = dirs[0]
    manifest_path = newest / "manifest.json"
    if not manifest_path.exists():
        return ("corrupt", None)  # crashed-mid-write latest run -- NOT absent
    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # ValueError covers json.JSONDecodeError AND UnicodeDecodeError (Codex R6
        # MAJOR #1: a non-UTF-8 manifest must escalate to corrupt, not crash).
        return ("corrupt", None)
    if not _manifest_is_well_shaped(parsed):
        return ("corrupt", None)
    return ("ok", parsed)


def _check_excluded_reason_breakdown(*, exports_root) -> list[ResearchHealthCheck]:
    """Read the NEWEST engine manifest; report invalid_ohlc /
    insufficient_forward_depth / missing_observations each as a count + % of
    unique_signals (brief §6.2 #2). SUMS each reason across ALL hypotheses'
    funnel.per_hypothesis.*.excluded sub-dicts / funnel.detection_level
    .unique_signals (the LIVE shape -- NOT a top-level breakdown). READ, never
    recompute attribution (LOCK §4.2).
    """
    key = "excluded_reason_breakdown"
    state, manifest = _read_newest_manifest(exports_root)
    if state == "absent":
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no engine manifest yet (n/a)")]
    if state == "corrupt":
        return [ResearchHealthCheck(
            key=key, status="yellow",
            summary="newest engine manifest unreadable",
            detail="the latest shadow-expectancy run is partial/corrupt/"
                   "shape-drifted")]

    funnel = manifest["funnel"]  # _manifest_is_well_shaped guarantees the shape
    unique_signals = funnel["detection_level"]["unique_signals"]
    per_hypothesis = funnel["per_hypothesis"]

    summed: dict[str, int] = {r: 0 for r in _ATTRIBUTED_EXCLUDED_REASONS}
    for hyp in per_hypothesis.values():
        excluded = hyp.get("excluded", {}) if isinstance(hyp, dict) else {}
        for reason in _ATTRIBUTED_EXCLUDED_REASONS:
            summed[reason] += int(excluded.get(reason, 0) or 0)

    if not unique_signals:  # 0 -> avoid div-by-zero
        # Codex R4 MAJOR #2: 0 signals + NONZERO attributed excluded is an
        # internally-inconsistent manifest (you cannot attribute exclusions
        # against zero signals) -> yellow, NOT a green n/a false-green.
        if any(summed.values()):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="inconsistent manifest: 0 signals but"
                        f" {sum(summed.values())} attributed excluded",
                detail="; ".join(f"{r}={summed[r]}"
                                 for r in _ATTRIBUTED_EXCLUDED_REASONS
                                 if summed[r]))]
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="n/a (zero signals)")]

    if not per_hypothesis:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no attributed hypotheses yet (n/a)")]

    worst_status = "green"
    parts: list[str] = []
    for reason in _ATTRIBUTED_EXCLUDED_REASONS:
        count = summed[reason]
        pct = 100.0 * count / unique_signals
        parts.append(f"{reason}={count} ({pct:.1f}%)")
        if pct > _EXCL_RED_PCT:
            reason_status = "red"
        elif pct > _EXCL_YELLOW_PCT:
            reason_status = "yellow"
        else:
            reason_status = "green"
        worst_status = worst_of([worst_status, reason_status])

    return [ResearchHealthCheck(
        key=key, status=worst_status,
        summary=f"excluded reasons vs {unique_signals} signals",
        detail="; ".join(parts))]


# --------------------------------------------------------------------------
# Coverage gaps (NYSE-aware observation holes incl. missing tail) + structural
# integrity (orphans + look-ahead). Self-contained in this module (Codex R1
# MAJOR #2): lazy-import the EXISTING _NYSE/last_completed_session read-only;
# NEVER edit swing/evaluation/dates.py.
# --------------------------------------------------------------------------

_COVERAGE_YELLOW_GAPS = 1   # any hole -> yellow (a missing forward bar is a real signal)
_COVERAGE_RED_GAPS = 10     # a large hole count -> red (systemic observe-step failure)
# The known TERMINAL observation statuses (the walk legitimately stopped -> no
# tail expected; the complement of pattern_detection_events._OPEN_STATUSES
# {pending,triggered_open}). An UNKNOWN/NULL latest status is NOT silently
# treated as terminal (Codex R6 MAJOR #4: that would suppress a missing tail ->
# false green); it is treated as OPEN (tail-expected, conservative) so a degraded
# status row surfaces a gap rather than hiding one.
_TERMINAL_STATUSES = (
    "invalidated", "expired",
    "triggered_closed_at_target", "triggered_closed_at_stop",
)


def _check_coverage_gaps(
    conn: sqlite3.Connection, *, now: datetime,
) -> list[ResearchHealthCheck]:
    """A MATURE detection whose forward-observation date sequence has HOLES vs
    the NYSE trading calendar -- including a MISSING TAIL (the observe step
    stopped early) AND a mature detection with ZERO observations (Codex R2-rev
    MAJOR #4 -- driven from DETECTIONS, not observations, so a never-observed
    mature detection is visible); not just interior gaps (Codex R4 MAJOR #2;
    brief §6.2 #3).

    Upper bound by latest-observation STATUS: OPEN (or no observation yet) ->
    last_completed_session(now) (catches the missing tail + the never-observed
    detection); TERMINAL -> the detection's own max_obs (it legitimately stopped;
    no tail expected). The forward walk starts the first session AFTER
    data_asof_date. The weekend is NOT a gap (calendar-aware). Mature =
    data_asof_date < last_completed_session.isoformat(). Missing table -> yellow;
    no mature detections -> green.
    """
    from datetime import date as _date

    from swing.evaluation.dates import _NYSE, last_completed_session

    key = "coverage_gaps"
    last_completed = last_completed_session(now)

    try:
        # Drive from ALL DETECTIONS, LEFT JOIN observations (Codex R2-rev MAJOR
        # #4: a never-observed detection still appears). NO SQL date predicate
        # (Codex R6 MAJOR #3): a string `WHERE data_asof_date < ?` would lexically
        # DROP a malformed/NULL data_asof_date BEFORE the Python guard runs ->
        # false-green on degraded data. Maturity is applied in Python after the
        # date parse so a malformed date is counted, not silently excluded.
        rows = conn.execute(
            "SELECT d.detection_id, d.data_asof_date,"
            " o.observation_date, o.status, o.observation_id"
            " FROM pattern_detection_events d"
            " LEFT JOIN pattern_forward_observations o"
            " ON o.detection_id = d.detection_id"
            " ORDER BY d.detection_id,"
            " o.observation_date ASC, o.observation_id ASC",
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="temporal-log schema unavailable",
                detail="pattern_forward_observations table missing;"
                       " run swing db-migrate")]
        raise

    # Group per detection (preserving obs date order); record the asof.
    per_det: dict[int, dict] = {}
    for det_id, asof, obs_date, status, _obs_id in rows:
        entry = per_det.setdefault(det_id, {"asof": asof, "obs": []})
        if obs_date is not None:  # NULL when the LEFT JOIN found no observation
            entry["obs"].append((obs_date, status))

    if not per_det:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no mature detections yet (n/a)")]

    def _sessions(start: _date, end: _date) -> set[str]:
        # sessions_in_range accepts stdlib date / ISO strings directly -- NO
        # pandas in the monitor's own code (Codex R1 MAJOR: no monitor-owned
        # pandas). The returned elements are Timestamps; we only read .date().
        if start > end:
            return set()
        idx = _NYSE.sessions_in_range(start, end)
        return {ts.date().isoformat() for ts in idx}

    def _first_session_after(asof: _date) -> _date | None:
        # The forward walk starts the first NYSE session strictly after the
        # detector's data cutoff. None when no session has occurred up to
        # last_completed (the detection is too fresh to expect any observation).
        window = _sessions(asof, last_completed)
        after = sorted(s for s in window if s > asof.isoformat())
        return _date.fromisoformat(after[0]) if after else None

    total_missing = 0
    malformed = 0
    sample: list[str] = []
    for det_id, entry in per_det.items():
        obs = entry["obs"]
        # Codex R4 MAJOR #1: a malformed/NULL date on a degraded/legacy DB must
        # NOT crash the whole monitor -- count it as a data-shape defect and
        # continue. (The schema is NOT NULL, but a degraded DB is the brief's
        # explicit no-crash contract.)
        try:
            asof = _date.fromisoformat(entry["asof"])
            observed = {d for d, _s in obs}
            min_max = (
                (_date.fromisoformat(min(observed)),
                 _date.fromisoformat(max(observed)))
                if observed else None
            )
        except (TypeError, ValueError):
            malformed += 1
            if len(sample) < 3:
                sample.append(f"det{det_id}: malformed date")
            continue
        # Maturity applied in PYTHON after the parse (Codex R6 MAJOR #3): mature =
        # at least one tradable session since the cutoff. (A SQL string predicate
        # would have lexically dropped a malformed/NULL asof before this point.)
        if asof >= last_completed:
            continue  # not mature -- no completed session since the cutoff
        if not observed:
            # mature detection with ZERO observations: every expected session
            # (first-after-cutoff .. last_completed) is missing.
            first = _first_session_after(asof)
            if first is None:
                continue  # too fresh -- no session yet to observe (not a defect)
            missing = len(_sessions(first, last_completed))
            if missing:
                total_missing += missing
                if len(sample) < 3:
                    sample.append(f"det{det_id}: {missing} missing (never observed)")
            continue
        latest_status = obs[-1][1]  # last by date order
        max_obs = min_max[1]
        # The expected window STARTS at the first session after the detector's
        # data cutoff (Codex R3 MAJOR #1 -- a LATE first observation, skipping the
        # first expected session, is a real leading/head gap; starting at min_obs
        # would mask it). Upper bound by latest status: a KNOWN TERMINAL status
        # legitimately stopped -> max_obs (no tail expected); OPEN *or an
        # UNKNOWN/NULL status* -> last_completed (Codex R6 MAJOR #4: an unknown
        # status must NOT be silently treated as terminal, which would suppress a
        # missing tail -> false green).
        first = _first_session_after(asof)
        if first is None:
            continue  # too fresh -- no session yet to observe (not a defect)
        is_terminal = latest_status in _TERMINAL_STATUSES
        upper = max_obs if is_terminal else last_completed
        expected = _sessions(first, upper)
        missing = len(expected - observed)
        if missing:
            total_missing += missing
            if len(sample) < 3:
                sample.append(f"det{det_id}: {missing} missing")

    if malformed:
        # a malformed-date data-shape defect is a real (yellow) integrity signal,
        # worst-of'd with the gap count below.
        gap_status = (
            "red" if total_missing > _COVERAGE_RED_GAPS
            else "yellow" if total_missing >= _COVERAGE_YELLOW_GAPS else "green"
        )
        return [ResearchHealthCheck(
            key=key, status=worst_of([gap_status, "yellow"]),
            summary=f"{total_missing} coverage gap(s),"
                    f" {malformed} malformed-date detection(s)",
            detail="; ".join(sample) if sample else None)]

    if total_missing == 0:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="0 observation-coverage gaps")]
    if total_missing > _COVERAGE_RED_GAPS:
        status = "red"
    elif total_missing >= _COVERAGE_YELLOW_GAPS:
        status = "yellow"
    else:
        status = "green"
    return [ResearchHealthCheck(
        key=key, status=status,
        summary=f"{total_missing} observation-coverage gap(s)",
        detail="; ".join(sample) if sample else None)]


def _check_structural_integrity(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """Two SQL probes, RED on ANY hit (a structural-integrity violation is never
    tolerable; brief §6.2 #4):
      - orphan observations (LEFT JOIN with no parent detection);
      - look-ahead: a detection whose FIRST observation precedes its
        detection_date (strict `<`).
    Missing table -> yellow schema-unavailable.
    """
    key = "structural_integrity"
    try:
        orphans = conn.execute(
            "SELECT COUNT(*) FROM pattern_forward_observations o"
            " LEFT JOIN pattern_detection_events d"
            " ON d.detection_id = o.detection_id"
            " WHERE d.detection_id IS NULL"
        ).fetchone()[0]
        look_ahead = conn.execute(
            "SELECT COUNT(*) FROM ("
            " SELECT o.detection_id, MIN(o.observation_date) AS first_obs,"
            " d.detection_date"
            " FROM pattern_forward_observations o"
            " JOIN pattern_detection_events d"
            " ON d.detection_id = o.detection_id"
            " GROUP BY o.detection_id"
            ") WHERE first_obs < detection_date"
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="temporal-log schema unavailable",
                detail="pattern_forward_observations table missing;"
                       " run swing db-migrate")]
        raise

    if orphans or look_ahead:
        return [ResearchHealthCheck(
            key=key, status="red",
            summary=f"{orphans} orphan observation(s),"
                    f" {look_ahead} look-ahead violation(s)",
            detail="structural-integrity violation in the temporal log")]
    return [ResearchHealthCheck(
        key=key, status="green",
        summary="0 orphans, 0 look-ahead violations")]


# --------------------------------------------------------------------------
# Drumbeat liveness (artifact age + total_unattributed) + candidate
# completeness (sentinel-filtered null pivots + error-bucket).
# --------------------------------------------------------------------------

_DIR_TS_RE = re.compile(r"shadow-expectancy-(\d{8}T\d{6})Z$")
_DRUMBEAT_YELLOW_AGE_DAYS = 4   # mirrors weekly_glance.T1_MAX_AGE_DAYS (weekend-tolerant)
_DRUMBEAT_RED_AGE_DAYS = 8      # >1 week with no run -> red


def _now_to_utc(n: datetime) -> datetime:
    """Convert the aggregator's naive-Hawaii-local now to UTC (the 18-E idiom,
    tool_health.py:347-350). NOT replace(tzinfo=UTC), which mis-shifts a Hawaii
    instant by ~10h."""
    if n.tzinfo is not None:
        return n.astimezone(UTC)
    return n.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(UTC)


def _newest_artifact_age_days(exports_root, now: datetime) -> int | None:
    """Newest shadow-expectancy-* dir age in (floored) days vs `now`, by the
    dir-name UTC timestamp (the weekly_glance.py:74-78 idiom). None when no dir
    with a parseable timestamp exists. The age is read from the dir NAME, so it
    is available even when the manifest is corrupt (a fresh-but-corrupt dir is
    NOT stale)."""
    from pathlib import Path

    root = Path(exports_root)
    if not root.exists():
        return None
    dirs = sorted(
        (p for p in root.glob("shadow-expectancy-*") if p.is_dir()),
        key=lambda p: p.name, reverse=True,
    )
    for d in dirs:
        m = _DIR_TS_RE.search(d.name)
        if m:
            newest = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(
                tzinfo=UTC)
            return (_now_to_utc(now) - newest).days
    return None


def _check_drumbeat_liveness(
    *, exports_root, now: datetime,
) -> list[ResearchHealthCheck]:
    """Engine drumbeat from the artifacts (brief §6.2 #5): (a) newest-artifact
    age; (b) total_unattributed in the NEWEST manifest. Returns the WORST of the
    age-color and the manifest-state/unattributed-color. No artifacts -> red
    "never ran". A CORRUPT newest manifest escalates the unattributed signal to
    >= yellow (do NOT treat corrupt as unattributed==0/green)."""
    key = "drumbeat_liveness"
    age_days = _newest_artifact_age_days(exports_root, now)

    if age_days is None:
        return [ResearchHealthCheck(
            key=key, status="red",
            summary="drumbeat never ran (no engine artifacts on disk)")]

    if age_days < 0:
        # Codex R7 MAJOR #2: a FUTURE-dated artifact dir (negative age) is NOT
        # fresh -- it signals producer clock-skew / a tz-frame bug. Escalate
        # rather than treating it as green (the false-green liveness vector).
        return [ResearchHealthCheck(
            key=key, status="yellow",
            summary="newest engine artifact is future-dated",
            detail=f"artifact age {age_days} day(s) -- producer clock skew?")]

    if age_days > _DRUMBEAT_RED_AGE_DAYS:
        age_status = "red"
    elif age_days > _DRUMBEAT_YELLOW_AGE_DAYS:
        age_status = "yellow"
    else:
        age_status = "green"

    # The manifest-content signal (total_unattributed) -- read the 3-state.
    state, manifest = _read_newest_manifest(exports_root)
    manifest_note = ""
    if state == "corrupt":
        manifest_status = "yellow"
        manifest_note = "; newest manifest unreadable (unattributed unknown)"
    elif state == "ok":
        # _manifest_is_well_shaped guarantees unattributed is a dict of
        # non-negative integer counts (Codex R5 MAJOR #1/#2).
        unattributed = manifest["funnel"]["unattributed"]
        total_unattributed = sum(int(v) for v in unattributed.values())
        if total_unattributed > 0:
            manifest_status = "yellow"
            manifest_note = f"; {total_unattributed} unattributed signal(s)"
        else:
            manifest_status = "green"
    else:  # "absent"
        # Codex R8 MAJOR #2: a non-None age means a parseable artifact dir EXISTED
        # for the age read, yet _read_newest_manifest now sees NO dir -- the
        # artifact VANISHED between the two filesystem reads (a concurrent prune/
        # delete). "absent after a fresh age" is NOT a healthy green; escalate to
        # yellow (the manifest arm cannot confirm a live drumbeat).
        manifest_status = "yellow"
        manifest_note = "; newest artifact vanished mid-read (pruned?)"

    status = worst_of([age_status, manifest_status])
    return [ResearchHealthCheck(
        key=key, status=status,
        summary=f"newest engine artifact {age_days} day(s) old",
        detail=f"age->{age_status}{manifest_note}")]


_ERROR_BUCKET_YELLOW = 5    # a few error-bucket candidates -> yellow
_ERROR_BUCKET_RED = 25      # an error-bucket SPIKE -> red (systemic eval failure)


def _check_candidate_completeness(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """Two signals from `candidates` at the latest evaluation_run (brief §6.2
    #6): (a) null pivots in ACTIONABLE buckets aplus/watch (gotcha #25 -- nulls
    in error/excluded are EXPECTED); (b) error-bucket count. WORST of the two.
    Latest run = MAX(id) FROM evaluation_runs (the ONE source; both sub-signals
    read the ACTUAL candidates rows, not the denormalized error_count). Missing
    table -> yellow; no eval run -> green n/a.
    """
    key = "candidate_completeness"
    try:
        latest = conn.execute(
            "SELECT MAX(id) FROM evaluation_runs").fetchone()[0]
        if latest is None:
            return [ResearchHealthCheck(
                key=key, status="green",
                summary="n/a (no eval run yet)")]
        null_actionable = conn.execute(
            "SELECT COUNT(*) FROM candidates"
            " WHERE evaluation_run_id = ?"
            " AND bucket IN ('aplus','watch') AND pivot IS NULL",
            (latest,),
        ).fetchone()[0]
        error_bucket = conn.execute(
            "SELECT COUNT(*) FROM candidates"
            " WHERE evaluation_run_id = ? AND bucket = 'error'",
            (latest,),
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="candidates schema unavailable",
                detail="candidates/evaluation_runs table missing;"
                       " run swing db-migrate")]
        raise

    null_status = "red" if null_actionable > 0 else "green"
    if error_bucket > _ERROR_BUCKET_RED:
        error_status = "red"
    elif error_bucket > _ERROR_BUCKET_YELLOW:
        error_status = "yellow"
    else:
        error_status = "green"

    status = worst_of([null_status, error_status])
    return [ResearchHealthCheck(
        key=key, status=status,
        summary=(f"run {latest}: {null_actionable} actionable null-pivot(s),"
                 f" {error_bucket} error-bucket"),
        detail=None)]


# --------------------------------------------------------------------------
# Fetch-transport health (yfinance_calls TRANSPORT indicator; NEVER substitutes
# for #1). Transport-health is a SAMPLE/indicator, never a census (18-C
# boundary). Never alarm on a low row count; a stale in_flight row is unknown,
# not hung.
# --------------------------------------------------------------------------

_TRANSPORT_RECENT_WINDOW = 50       # most-recent N terminal rows by ts
_TRANSPORT_MIN_SAMPLE = 10          # < this many terminal rows -> green n/a (low-count guard)
_TRANSPORT_YELLOW_ERROR_PCT = 20.0
_TRANSPORT_RED_ERROR_PCT = 50.0
_TRANSPORT_YELLOW_EMPTY_PCT = 50.0  # empty is looser than error (transient/weekend)


def _check_fetch_transport_health(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """yfinance_calls error+empty RATE over a recent window (brief §6.2 #7).
    TRANSPORT indicator ONLY -- `success` is transport-not-usability (the
    all-NaN-Close ragged bar records `success`), so this NEVER substitutes for
    check #1 (the usability authority). EXCLUDE `in_flight` (stale = unknown, not
    hung). NEVER alarm on a LOW row count (the §6.2 #7 LOCK -- BINDING): below
    the sample floor -> green, but the observed rate is SURFACED in the detail
    (Codex R6 MAJOR #2 -- visible without alarming). Missing table -> yellow;
    empty table -> green.
    """
    key = "fetch_transport_health"
    try:
        # Filter TERMINAL in SQL + LIMIT (Codex R2 MAJOR #2): excluding in_flight
        # in Python AFTER an N-row over-read lets a burst of newer in_flight rows
        # STARVE the terminal sample -> false low-sample green. The recent window
        # must be the most-recent N TERMINAL rows, regardless of in_flight volume.
        rows = conn.execute(
            "SELECT status FROM yfinance_calls"
            " WHERE status IN ('success','empty','error')"
            " ORDER BY ts DESC, call_id DESC LIMIT ?",
            (_TRANSPORT_RECENT_WINDOW,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="yfinance_calls schema unavailable",
                detail="yfinance_calls table missing; run swing db-migrate")]
        raise

    if not rows:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="n/a (no fetch audit yet)")]

    terminal = [r[0] for r in rows]
    n = len(terminal)
    n_error = sum(1 for s in terminal if s == "error")
    n_empty = sum(1 for s in terminal if s == "empty")

    if n < _TRANSPORT_MIN_SAMPLE:
        # the LOCK: never alarm on a low count. SURFACE the rate in detail.
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="n/a (insufficient sample)",
            detail=f"{n} terminal rows: {n_error} error, {n_empty} empty"
                   " (below sample floor)")]

    error_pct = 100.0 * n_error / n
    empty_pct = 100.0 * n_empty / n
    if error_pct > _TRANSPORT_RED_ERROR_PCT:
        error_status = "red"
    elif error_pct > _TRANSPORT_YELLOW_ERROR_PCT:
        error_status = "yellow"
    else:
        error_status = "green"
    empty_status = "yellow" if empty_pct > _TRANSPORT_YELLOW_EMPTY_PCT else "green"

    status = worst_of([error_status, empty_status])
    return [ResearchHealthCheck(
        key=key, status=status,
        summary=f"{n} terminal fetches: {error_pct:.0f}% error, {empty_pct:.0f}% empty",
        detail=f"{n_error} error, {n_empty} empty of {n} terminal rows")]


# --------------------------------------------------------------------------
# Aggregator
# --------------------------------------------------------------------------


def _normalize_now_to_naive_local(now: datetime | None) -> datetime:
    """Normalize `now` to NAIVE Hawaii-local at the compute_research_health
    boundary (byte-identical to 18-E tool_health._normalize_now_to_naive_local).

    The session helpers (action_session_for_run / last_completed_session) do
    now_local.replace(tzinfo=Pacific/Honolulu), which RELABELS (not converts) an
    aware datetime -> mis-anchored sessions. Normalize ONCE here so every
    downstream consumer receives a naive-Hawaii-local `now`.
      - None -> datetime.now(Pacific/Honolulu) naive (the Hawaii wall clock, NOT
        bare datetime.now() which mis-anchors on a non-Hawaii box).
      - aware -> CONVERT the instant to Hawaii-local THEN strip tzinfo.
      - naive -> pass through (already treated as Hawaii-local by the helpers).
    """
    if now is None:
        return datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    return now


def compute_research_health(
    conn: sqlite3.Connection,
    *,
    cfg=None,
    exports_root=None,
    manifest_dir=None,
    now: datetime | None = None,
) -> ResearchHealthStatus:
    """Read-only roll-up of the 7 research data-collection-integrity checks into
    the §3 status envelope (monitor="research_measurement", overall=worst_of,
    aware-UTC generated_ts). Never writes the DB. The bare call
    compute_research_health(conn) stays valid; `cfg` is accepted for
    signature-parity / future use (V1 checks do not require it).

    `manifest_dir` (Codex R5 MINOR) is an EXPLICIT override of the engine-artifact
    root the manifest-consuming checks (#2 excluded, #5 drumbeat) scan -- it takes
    precedence over `exports_root` for those checks so the parameter is not a
    silent no-op. When both are None the default is exports/research/.
    """
    now = _normalize_now_to_naive_local(now)
    if exports_root is None:
        # exports/research/ (RESEARCH_HEALTH_ARTIFACT_PATH is .../research/health/
        # latest.json; .parent.parent is .../research/).
        exports_root = RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent
    # manifest_dir, when supplied, is the explicit engine-artifact root for the
    # manifest checks (NOT a silent no-op -- Codex R5 MINOR).
    manifest_root = manifest_dir if manifest_dir is not None else exports_root
    checks: list[ResearchHealthCheck] = []
    checks += _check_temporal_log_finiteness(conn)
    checks += _check_excluded_reason_breakdown(exports_root=manifest_root)
    checks += _check_coverage_gaps(conn, now=now)
    checks += _check_structural_integrity(conn)
    checks += _check_drumbeat_liveness(exports_root=manifest_root, now=now)
    checks += _check_candidate_completeness(conn)
    checks += _check_fetch_transport_health(conn)
    overall = worst_of([c.status for c in checks])
    # Codex R1 MAJOR #1: stamp generated_ts AWARE-UTC so the 18-F staleness gate
    # is host-tz-independent (the deliberate divergence from 18-E's naive stamp).
    generated_ts = _research_now_iso(now)
    return ResearchHealthStatus(
        overall=overall, checks=checks, generated_ts=generated_ts)
