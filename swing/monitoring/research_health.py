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
import re
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
# Excluded-reason rate (% of unique_signals) escalation. invalid_ohlc has run
# ~30% on the live manifest (the 06-10 NaN backlog the engine's belt rejects);
# these are CONSERVATIVE V1 floors -- the RD tunes them post-build.
_EXCL_YELLOW_PCT = 10.0   # any one reason >10% of unique_signals -> yellow
_EXCL_RED_PCT = 25.0      # any one reason >25% -> red


def _manifest_is_well_shaped(parsed: object) -> bool:
    """The nested funnel schema gate (Codex R2 MAJOR #3 -- shape-drift defense).

    A parsed dict is well-shaped ONLY when funnel is a dict AND
    funnel.detection_level.unique_signals is numeric AND funnel.per_hypothesis
    is a dict. Anything else is shape-drift -> the caller maps it to "corrupt"
    (NOT "ok"-then-.get-zeros, which would mask a broken latest run as healthy).
    """
    if not isinstance(parsed, dict):
        return False
    funnel = parsed.get("funnel")
    if not isinstance(funnel, dict):
        return False
    detection_level = funnel.get("detection_level")
    if not isinstance(detection_level, dict):
        return False
    unique_signals = detection_level.get("unique_signals")
    if not isinstance(unique_signals, (int, float)) or isinstance(unique_signals, bool):
        return False
    return isinstance(funnel.get("per_hypothesis"), dict)


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
    except (OSError, json.JSONDecodeError):
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
    if not unique_signals:  # 0 or missing -> avoid div-by-zero
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="n/a (zero signals)")]

    per_hypothesis = funnel["per_hypothesis"]
    if not per_hypothesis:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no attributed hypotheses yet (n/a)")]

    summed: dict[str, int] = {r: 0 for r in _ATTRIBUTED_EXCLUDED_REASONS}
    for hyp in per_hypothesis.values():
        excluded = hyp.get("excluded", {}) if isinstance(hyp, dict) else {}
        for reason in _ATTRIBUTED_EXCLUDED_REASONS:
            summed[reason] += int(excluded.get(reason, 0) or 0)

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
# A detection whose latest-observation status is in this OPEN set is still in
# the forward walk (mirror pattern_detection_events._OPEN_STATUSES); a TERMINAL
# status (invalidated/expired/triggered_closed_*) legitimately stopped.
_OPEN_STATUSES = ("pending", "triggered_open")


def _check_coverage_gaps(
    conn: sqlite3.Connection, *, now: datetime,
) -> list[ResearchHealthCheck]:
    """A MATURE detection whose forward-observation date sequence has HOLES vs
    the NYSE trading calendar -- including a MISSING TAIL (the observe step
    stopped early), not just interior gaps (Codex R4 MAJOR #2; brief §6.2 #3).

    Upper bound by latest-observation STATUS: OPEN -> last_completed_session(now)
    (catches the missing tail); TERMINAL -> the detection's own max_obs (it
    legitimately stopped; no tail expected). The weekend is NOT a gap
    (calendar-aware). Mature = data_asof_date < last_completed_session.isoformat().
    Missing table -> yellow; no mature detections -> green.
    """
    from datetime import date as _date

    from swing.evaluation.dates import _NYSE, last_completed_session

    key = "coverage_gaps"
    last_completed = last_completed_session(now)
    last_completed_iso = last_completed.isoformat()

    try:
        rows = conn.execute(
            "SELECT o.detection_id, o.observation_date, o.status,"
            " o.observation_id, d.data_asof_date"
            " FROM pattern_forward_observations o"
            " JOIN pattern_detection_events d"
            " ON d.detection_id = o.detection_id"
            " WHERE d.data_asof_date < ?"
            " ORDER BY o.detection_id,"
            " o.observation_date ASC, o.observation_id ASC",
            (last_completed_iso,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="temporal-log schema unavailable",
                detail="pattern_forward_observations table missing;"
                       " run swing db-migrate")]
        raise

    # Group observations per detection (preserving date order).
    per_det: dict[int, list[tuple[str, str]]] = {}
    for det_id, obs_date, status, _obs_id, _asof in rows:
        per_det.setdefault(det_id, []).append((obs_date, status))

    if not per_det:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="no mature detections with observations yet (n/a)")]

    def _sessions(start: _date, end: _date) -> set[str]:
        # sessions_in_range accepts stdlib date / ISO strings directly -- NO
        # pandas in the monitor's own code (Codex R1 MAJOR: no monitor-owned
        # pandas). The returned elements are Timestamps; we only read .date().
        if start > end:
            return set()
        idx = _NYSE.sessions_in_range(start, end)
        return {ts.date().isoformat() for ts in idx}

    total_missing = 0
    sample: list[str] = []
    for det_id, obs in per_det.items():
        observed = {d for d, _s in obs}
        # <2 observations and no expected-window gap -> skip (immature row).
        latest_status = obs[-1][1]  # last by date order
        min_obs = _date.fromisoformat(min(observed))
        max_obs = _date.fromisoformat(max(observed))
        upper = last_completed if latest_status in _OPEN_STATUSES else max_obs
        expected = _sessions(min_obs, upper)
        missing = len(expected - observed)
        if missing and len(observed) < 2 and upper == max_obs:
            # an immature/just-detected terminal row with a lone obs -- not a defect
            continue
        if missing:
            total_missing += missing
            if len(sample) < 3:
                sample.append(f"det{det_id}: {missing} missing")

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
        unattributed = manifest["funnel"].get("unattributed", {})
        total_unattributed = sum(
            int(v) for v in unattributed.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        )
        if total_unattributed > 0:
            manifest_status = "yellow"
            manifest_note = f"; {total_unattributed} unattributed signal(s)"
        else:
            manifest_status = "green"
    else:  # absent (no dir to read -- but age_days was not None, so a dir with a
        # parseable name exists yet _read_newest_manifest found no shadow dir;
        # treat as green for the manifest arm).
        manifest_status = "green"

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
_TRANSPORT_TERMINAL = ("success", "empty", "error")


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
        rows = conn.execute(
            "SELECT status FROM yfinance_calls ORDER BY ts DESC, call_id DESC"
            " LIMIT ?",
            (_TRANSPORT_RECENT_WINDOW + 200,),  # over-read; filter terminal below
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

    terminal = [r[0] for r in rows if r[0] in _TRANSPORT_TERMINAL]
    terminal = terminal[:_TRANSPORT_RECENT_WINDOW]
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
    compute_research_health(conn) stays valid; `cfg`/`manifest_dir` are accepted
    for signature-parity / future use (V1 checks do not require them).
    """
    now = _normalize_now_to_naive_local(now)
    if exports_root is None:
        # exports/research/ (RESEARCH_HEALTH_ARTIFACT_PATH is .../research/health/
        # latest.json; .parent.parent is .../research/).
        exports_root = RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent
    checks: list[ResearchHealthCheck] = []
    checks += _check_temporal_log_finiteness(conn)
    checks += _check_excluded_reason_breakdown(exports_root=exports_root)
    checks += _check_coverage_gaps(conn, now=now)
    checks += _check_structural_integrity(conn)
    checks += _check_drumbeat_liveness(exports_root=exports_root, now=now)
    checks += _check_candidate_completeness(conn)
    checks += _check_fetch_transport_health(conn)
    overall = worst_of([c.status for c in checks])
    # Codex R1 MAJOR #1: stamp generated_ts AWARE-UTC so the 18-F staleness gate
    # is host-tz-independent (the deliberate divergence from 18-E's naive stamp).
    generated_ts = _research_now_iso(now)
    return ResearchHealthStatus(
        overall=overall, checks=checks, generated_ts=generated_ts)
