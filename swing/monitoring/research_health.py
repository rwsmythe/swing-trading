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

import contextlib
import importlib.util
import json
import logging
import math
import os
import re
import sqlite3  # noqa: F401  (used in the per-check signatures below)
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
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

log = logging.getLogger(__name__)

_STATUS_VALUES = frozenset({"green", "yellow", "red"})
_ZERO_OFFSET = timedelta(0)
# ANCHORED full-match (Codex R13 MAJOR #1): a bare `.search` with only a trailing
# `$` would accept a crafted name embedding a valid timestamp at the end (e.g.
# `shadow-expectancy-z-shadow-expectancy-20260613T000000Z`). fullmatch + ^...$
# rejects anything but the exact canonical dir name.
_DIR_TS_RE = re.compile(r"^shadow-expectancy-(\d{8}T\d{6})Z$")


def _parse_artifact_dir_ts(name: str) -> datetime | None:
    """Parse a shadow-expectancy-* dir NAME to its aware-UTC timestamp, or None
    when the name is not a VALID artifact timestamp (Codex R14 MAJOR -- centralize
    the parse so BOTH _read_newest_manifest and _newest_artifact_age_days agree).

    The regex `\\d{8}T\\d{6}` validates DIGIT SHAPE only; a digit-shaped but
    invalid-CALENDAR name (e.g. shadow-expectancy-20261399T999999Z: month 13, day
    99, hour 99) passes fullmatch yet datetime.strptime RAISES ValueError. So the
    strptime is wrapped here: a name that fails EITHER the regex OR the calendar
    parse returns None -> the manifest arm reports corrupt + the age arm reports
    None (the malformed-name yellow), never an uncaught crash or a false-green."""
    m = _DIR_TS_RE.fullmatch(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


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
        # Codex R11 MAJOR #2: every check MUST be a ResearchHealthCheck (whose
        # __post_init__ enforces the per-check render schema). A bare duck-typed
        # object with a .status could otherwise pass worst_of yet serialize a
        # check payload the 18-F reader greys -> a non-conformant envelope IS
        # constructable. Reject non-ResearchHealthCheck entries by construction.
        for c in self.checks:
            if not isinstance(c, ResearchHealthCheck):
                raise ValueError(
                    "ResearchHealthStatus.checks entries must be"
                    f" ResearchHealthCheck; got {type(c).__name__}"
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
# The SINGLE-SOURCE atomic artifact writer (C-NH4): both scripts/research_health.py
# AND the nightly pipeline step (swing/pipeline/runner.py:_step_research_health)
# call THIS -- there is NO second copy of the atomic write. Relocated verbatim
# from the script's former local _write_latest_json_atomic + _resolve_out_path
# (the same os.replace-same-filesystem gotcha: the tmp lives in the DEST dir).
# --------------------------------------------------------------------------


def write_research_health_artifact(
    status: ResearchHealthStatus, out_path: Path | None = None,
    *, extra: dict | None = None,
) -> Path:
    """Atomically write `status`'s §3 envelope to `out_path` and return it.

    `out_path=None` resolves via the SHARED accessor
    stoplights.research_health_artifact_path() (NOT the bare constant -- so a test
    monkeypatch of the accessor is honored, mirroring the script's
    _resolve_out_path). Consumes `status.to_dict()` as-is; the dataclass
    __post_init__ already enforced the envelope contract at construction (LOCK 2 --
    never re-validate here).

    `extra` (19-B Task 5) is an OPTIONAL top-level merge (e.g.
    `{"detection_count": N}`) applied AFTER `status.to_dict()` -- an ADDITIVE
    extension of THIS single writer (never a second writer; the single-source LOCK
    preserved). The 18-F reader gates only on monitor/overall/generated_ts/checks,
    so an extra top-level key is ignored on read (the machine-readable guard
    witness for the NEXT run). Atomic: tmp in the SAME directory (os.replace
    requires same filesystem -- the Windows OSError 18 gotcha) then os.replace; on
    ANY BaseException the partial tmp is unlinked and the error re-raised (the prior
    artifact is never clobbered).
    """
    if out_path is None:
        from swing.monitoring.stoplights import research_health_artifact_path
        out_path = research_health_artifact_path()
    payload = status.to_dict()
    if extra:
        payload = {**payload, **extra}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(out_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, out_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return out_path


# --------------------------------------------------------------------------
# 18-H.7: the edge-triggered research-health RED -> role_mail push to RD.
# Additive functions (NO new module): the edge detection + message composition +
# the path-resilient role_mail post all live here. The nightly _step_research_
# health reads the PRIOR latest.json's overall (via the SHARED accessor) BEFORE
# the new write, then calls push_research_health_red_to_rd(current, prior); the
# push fires only on the green/yellow->red (or absent->red) edge. Best-effort:
# any failure is swallowed + logged, never raised (the writer must still run).
# --------------------------------------------------------------------------

# The GUI research-stoplight pointer + the latest.json pointer surfaced in the
# push body (ASCII; the live web nav path to the research drill-down, grounded
# against swing/web/routes/health.py's GET /health/research). Module constants so
# the message text has a single source.
_RESEARCH_STOPLIGHT_URL = "/health/research"
_LATEST_JSON_POINTER = "exports/research/health/latest.json"


def _default_comms_root() -> Path:
    """The repo comms/ root (the role_mail mailbox). A MODULE FUNCTION (not an
    inline expression) so tests can monkeypatch it to a tmp dir -- the seam the
    runner-wiring end-to-end test drives the REAL helper through without touching
    the live comms/ tree. <repo> = parents[2] (this module is swing/monitoring/...;
    matches stoplights.py:28's parents[2])."""
    return Path(__file__).resolve().parents[2] / "comms"


def _effective_comms_root(comms_root: Path | None) -> Path:
    """The ONE comms-root seam EVERY push path consults (19-B Task 1, Codex R2
    CRITICAL). An explicit `comms_root` wins; else `_default_comms_root()`. A
    single monkeypatch of THIS function closes ALL push paths (the default
    `comms_root=None` path AND an explicit `comms_root=`), so the autouse suite
    fixture can guarantee no test ever resolves a push to the REAL comms/ tree.
    Production is unchanged (explicit cfg-derived root, or the __file__ default)."""
    return comms_root if comms_root is not None else _default_comms_root()


def _comms_root_for(cfg) -> Path:
    """The config-derived comms root (19-B Task 4): ``cfg.project_root/comms``.
    Derived from the EXPLICIT ``cfg.project_root`` (= config_path.parent.resolve()
    stored on Config at load()) via ``config_project_root`` -- NOT the fragile
    ``exports_dir.parent`` inference, so a relocated/absolute exports_dir cannot
    re-split the anchor. A worktree run's cfg carries the worktree root; a MAIN
    run's carries MAIN -> comms tracks the true launch context."""
    from swing.config import config_project_root
    return config_project_root(cfg) / "comms"


def _read_prior_overall(out_path: Path | None = None) -> str | None:
    """Read the PRIOR latest.json's `overall` BEFORE it is overwritten.

    `out_path=None` resolves via stoplights.research_health_artifact_path() (the
    SAME accessor write_research_health_artifact uses, so a test monkeypatch is
    honored). Returns the prior `overall` string, or None when the artifact is
    ABSENT or UNPARSEABLE or carries no/non-str `overall` (or is not a dict) ->
    the caller treats None as non-red, so an absent/corrupt->red is a valid
    first-ever edge. NEVER raises (best-effort; a read failure must not break the
    step). The whole body is guarded (Codex R1 MAJOR): a deeply-nested malformed
    latest.json can make json.loads raise RecursionError -- a RuntimeError, NOT an
    OSError/ValueError -- which would escape BEFORE _step_research_health writes
    the new artifact, skipping the writer. Catch broadly -> degrade to None."""
    try:
        if out_path is None:
            from swing.monitoring.stoplights import research_health_artifact_path
            out_path = research_health_artifact_path()
        env = json.loads(Path(out_path).read_text(encoding="utf-8"))
        if not isinstance(env, dict):
            return None
        overall = env.get("overall")
        return overall if isinstance(overall, str) else None
    except Exception:
        return None


def _read_prior_env(out_path: Path | None = None) -> dict | None:
    """Read the PRIOR latest.json as a raw dict BEFORE it is overwritten (19-B
    Task 5 -- the guard's machine-readable witness source). Mirrors
    `_read_prior_overall`'s broad guard: returns the parsed dict, or None when the
    artifact is ABSENT / UNPARSEABLE / not a dict. NEVER raises (best-effort; incl.
    a deeply-nested RecursionError -> None), so it can run before the writer in
    _step_research_health without ever skipping the write."""
    try:
        if out_path is None:
            from swing.monitoring.stoplights import research_health_artifact_path
            out_path = research_health_artifact_path()
        env = json.loads(Path(out_path).read_text(encoding="utf-8"))
        return env if isinstance(env, dict) else None
    except Exception:
        return None


def _ascii(text: str) -> str:
    """Backslash-escape any non-ASCII so the composed mail stays ASCII-only (the
    cp1252 gotcha). Codex R1 MINOR: a red check's `key`/`summary`/`detail` is only
    type-constrained to str -- a DB-backed value (e.g. a ticker) is NOT
    ASCII-constrained at the schema, so a future/non-canonical value could put a
    non-ASCII glyph into the subject/body. Sanitize the COMPOSED strings."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _compose_red_push(status: ResearchHealthStatus, run_id: int | None) -> tuple[str, str]:
    """Build the (subject, body) for the RED push. ASCII-only (the cp1252
    gotcha): no em-dash, no section glyph, no arrows; interpolated check fields
    are backslash-escaped via _ascii. The per-check `detail` line is LOAD-BEARING
    (RD's regression-vs-accepted discriminator) -- always emitted, substituting
    `(none)` when a red check's detail is None."""
    red_checks = [c for c in status.checks if c.status == "red"]
    red_keys = [c.key for c in red_checks]
    subject = "research-health RED: " + (", ".join(red_keys) if red_keys else "(unnamed)")
    lines = ["overall=red", "", "RED checks:"]
    for c in red_checks:
        lines.append(f"- {c.key}: {c.summary}")
        lines.append(f"  detail: {c.detail if c.detail is not None else '(none)'}")
    lines += [
        "",
        f"run id: {run_id if run_id is not None else 'unknown'}",
        f"artifact: {_LATEST_JSON_POINTER}",
        f"GUI: {_RESEARCH_STOPLIGHT_URL}",
    ]
    return _ascii(subject), _ascii("\n".join(lines))


def push_research_health_red_to_rd(
    status: ResearchHealthStatus,
    *,
    run_id: int | None,
    prior_overall: str | None,
    lease_verified: bool = False,
    comms_root: Path | None = None,
) -> bool:
    """Edge-triggered RED notify to RD. Returns True iff a message was posted.

    LEASE-OR-SILENT (19-B Task 2, RD's rule -- DEFAULT-DENY): posts NOTHING unless
    the caller explicitly asserts `lease_verified=True` AND `run_id is not None`.
    `lease_verified` defaults to False, so ANY caller (current, direct, or future)
    that does not prove the run is a genuine leased `pipeline_runs` row posts
    nothing + logs a WARNING. The ONLY opt-in caller is the runner, which computes
    `lease_verified=pipeline_run_exists(conn, run_id)` while its ro conn is open.
    This structurally kills the `run id: unknown` / suite-leak push class (the 3
    leaked pushes were `run_id is None`; a forged int fails the runner's DB check).

    Edge = `status.overall == "red"` AND `prior_overall != "red"` (covers
    green/yellow->red AND the absent/corrupt(None)->red first-ever-RED case). On a
    non-edge -> return False, post nothing. On the edge -> compose + post ONE
    `status` message --from pipeline --to rd, return True.

    `comms_root=None` -> `_effective_comms_root(None)` -> `_default_comms_root()`
    (the repo comms/); tests pass a tmp dir, OR the autouse suite fixture wraps
    `_effective_comms_root` so they never touch the live comms.

    BEST-EFFORT: any exception (import failure, MailError, IO) is swallowed +
    logged; returns False. The function owns its own try/except so a push failure
    never reaches the writer call that follows it in _step_research_health
    (write-latest.json must still happen)."""
    if not lease_verified or run_id is None:
        log.warning(
            "research-health RD push skipped: unverified/unleased context "
            "(lease_verified=%s, run_id=%s)", lease_verified, run_id)
        return False
    if status.overall != "red" or prior_overall == "red":
        return False
    try:
        root = _effective_comms_root(comms_root)
        # Path-resilient role_mail import (scripts/ is not on swing's import path;
        # the comms-hook precedent). Lazy + inside the try so a missing/edited
        # scripts tree degrades to a logged no-post, never an import-time crash.
        rm_path = Path(__file__).resolve().parents[2] / "scripts" / "role_mail.py"
        spec = importlib.util.spec_from_file_location("role_mail", rm_path)
        role_mail = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(role_mail)
        subject, body = _compose_red_push(status, run_id)
        role_mail.post_message(root, "pipeline", ["rd"], "status", subject, body)
    except Exception as exc:
        log.warning("research-health RD push failed: %s", exc)
        return False
    log.info("research-health RED edge: posted status to rd (run id %s)", run_id)
    return True


# --------------------------------------------------------------------------
# Shared degradation helper (mirror 18-E tool_health._schema_unavailable).
# --------------------------------------------------------------------------


def _schema_unavailable(exc: sqlite3.OperationalError) -> bool:
    """True iff `exc` is a missing-table/column error (degrade-to-yellow). Any
    OTHER OperationalError re-raises (do not mask real defects -- mirror 18-E)."""
    msg = str(exc)
    return "no such table" in msg or "no such column" in msg


def pipeline_run_exists(conn: sqlite3.Connection, run_id: int | None) -> bool:
    """True iff `run_id` is a real `pipeline_runs` row (a genuine leased run) --
    the lease-or-silent PROOF (19-B Task 2). A forged/stale/nonexistent run_id is
    not in the DB -> False -> the runner passes `lease_verified=False` -> no push.

    NOTE the PK column is `pipeline_runs.id` (== `lease.run_id`), NOT a `run_id`
    column. Degrade-gracefully: `run_id is None` -> False; a missing `pipeline_runs`
    table (pre-schema DB) -> False. Any OTHER OperationalError re-raises."""
    if run_id is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM pipeline_runs WHERE id = ? LIMIT 1", (run_id,)
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return False
        raise


# --------------------------------------------------------------------------
# 19-B Task 5: the broken-context write-suppression guard (RD-reviewed
# distinguisher). Machine-readable signals ONLY -- a direct DB COUNT for the
# current read + a machine-readable `detection_count` stamped into the prior
# artifact envelope for the "the live system had data" witness. NO English-string
# coupling; the measurement computation (compute_research_health) is untouched.
# --------------------------------------------------------------------------


def db_detection_count(conn: sqlite3.Connection) -> int:
    """Machine-readable current-empty signal: COUNT of the detection log. Zero
    detections is the canonical empty-DB signal (a forward observation cannot
    exist without a parent detection via the FK, so zero detections => zero
    observations). Degrade-gracefully: a missing table (schema not yet applied) ->
    -1 (a sentinel the caller's `== 0` treats as False -> NEVER suppress on a
    pre-schema DB). Any OTHER OperationalError re-raises."""
    try:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM pattern_detection_events").fetchone()
        return int(n)
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return -1
        raise


def _prior_env_had_detections(prior_env) -> bool:
    """The machine-readable 'the live system had data' witness (19-B Task 5). True
    iff the prior valid research_measurement envelope carries a machine-readable
    `detection_count` int > 0. A missing/None/non-int/bool `detection_count` (an
    OLD pre-19-B artifact, or a non-conformant envelope) -> False -> CONSERVATIVE
    no-suppress (never false-suppress a genuinely-fresh system). The prior artifact
    lives under the config-anchored exports (decoupled from the HOME-anchored DB),
    so on a wrong-HOME empty-DB read with a correct cwd the good prior artifact
    witnesses the loss."""
    if not isinstance(prior_env, dict) or prior_env.get("monitor") != RESEARCH_MONITOR_ID:
        return False
    dc = prior_env.get("detection_count")
    return isinstance(dc, int) and not isinstance(dc, bool) and dc > 0


def should_suppress_broken_context_write(
    *, current_detection_count, exports_root, shadow_manifest_path, prior_env,
) -> tuple[bool, str | None]:
    """Return (suppress, reason). Suppress the write when the read looks broken-
    context-empty on EITHER signal (19-B Task 5). A PURE function of machine-
    readable inputs (an int count + a dir-scan + the prior envelope dict); the
    caller queries db_detection_count(conn) while the conn is open and passes it
    as current_detection_count.

    Signal (i) -- anchor divergence: shadow SUCCEEDED this run (wrote a manifest)
    but the health scan root shows NO engine artifacts -> read/write anchors
    diverged or the just-written manifest is invisible. Gated on shadow SUCCESS
    (manifest_path not None) so a genuine shadow FAILURE / first-ever run still
    writes its honest drumbeat-RED (a real never-ran / engine-down state is NOT
    hidden).

    Signal (ii) -- wrong-HOME empty read: the CURRENT DB read is detection-empty
    (a machine COUNT == 0) AND a prior valid artifact witnesses the system
    PREVIOUSLY HAD detections (its machine-readable detection_count > 0) -> the DB
    lost its data (db_path is HOME-anchored). The append-only invariant (no DELETE
    FROM pattern_detection_events in swing/) makes a >0 -> 0 transition on the SAME
    correct DB impossible by construction, so this fires only on a different
    (wrong-HOME) DB or a deliberate research-log reset (for which leave-prior +
    staleness-grey is the correct self-healing outcome)."""
    if shadow_manifest_path is not None and _newest_artifact_dir(exports_root) is None:
        return True, (
            "shadow wrote a manifest but the health scan root is empty "
            "(anchor divergence)")
    if current_detection_count == 0 and _prior_env_had_detections(prior_env):
        return True, (
            "DB read is detection-empty but the prior artifact recorded "
            "detections>0 (wrong-HOME empty read?)")
    return False, None


# --------------------------------------------------------------------------
# Per-check helpers (lazy-import the reused readers/predicate; NO pandas here).
# --------------------------------------------------------------------------


_OHLC_KEYS = ("open", "high", "low", "close")

# FIX 1 (18-D, brief §1): the finiteness BASELINE cutoff = the 18-A writer-fix
# merge boundary (`c45d8752`, 2026-06-13 -- the temporal-log NaN-writer fix +
# the shared ohlcv_finiteness predicate). Any non-finite OHLC WRITTEN AFTER that
# barrier is a GENUINE regression (the writer should never emit one now) -> RED.
# Any non-finite observation_date <= this cutoff is ACCEPTED-HISTORICAL: the
# pre-fix backlog the writer-fix could not retro-heal (the withdrawn 06-10
# NaN-Close cohort) -> surfaced in the detail, but does NOT drive red.
# GROUNDED against the live DB: the full 1287-row temporal-log scan shows ALL
# known non-finite is the single 2026-06-10 session, so any cutoff in
# (06-10, 06-13] isolates exactly that accepted cohort.
_FINITENESS_BASELINE_CUTOFF = date(2026, 6, 13)
# Canonical ISO date shape `YYYY-MM-DD` (Codex R1 MAJOR). date.fromisoformat on
# Python 3.11+ ALSO accepts compact (`20260610`) and ISO week-date
# (`2026-W24-3`) forms -- a non-finite row carrying such a non-canonical date
# would parse to a value and could land in the ACCEPTED-historical cohort,
# defeating the conservative "an undatable non-finite drives red" rule. The
# observation_date column is `TEXT NOT NULL` with NO format CHECK (migration
# 0022), so a non-canonical string is NOT write-prevented -> require the exact
# `YYYY-MM-DD` shape BEFORE trusting the parse; anything else is treated as
# post-cutoff (a red driver), never silently accepted-historical.
_CANONICAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_temporal_log_finiteness(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """Data-USABILITY authority (brief §6.2 #1): scan
    pattern_forward_observations.ohlc_today_json for non-finite OHLC. RED only on
    a non-finite observation whose observation_date is STRICTLY AFTER the 18-A
    writer-fix baseline (_FINITENESS_BASELINE_CUTOFF) -- a genuine post-fix
    regression. Non-finite at-or-before the cutoff is ACCEPTED-HISTORICAL (the
    pre-fix backlog the writer-fix could not retro-heal): SURFACED in the detail
    but NOT a red driver.

    The check that would have caught the 2026-06-10 NaN-Close defect on the day
    it entered (any NEW such defect post-cutoff -> RED). Reuses the shared
    is_finite_ohlc predicate (NaN/inf), with a None/missing/non-numeric GUARD
    before it (the predicate RAISES TypeError on None -- the brief's "reuse the
    predicate" applies to NaN/inf only). Volume is EXEMPT (Arc-8). Missing table
    -> yellow; empty table -> green (the log legitimately starts empty). A
    non-finite row with a malformed/None observation_date is treated as
    post-cutoff (conservative: an undatable non-finite is a red driver, never
    silently absorbed into the accepted cohort).
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

    post_cutoff = 0          # genuine post-baseline regressions -> drive red
    accepted_historical = 0  # non-finite OHLC at-or-before the baseline -> surfaced
    sample: list[str] = []   # the red-driver sample (post-cutoff only)
    for _obs_id, obs_date, ohlc_json, ticker in rows:
        # TWO distinct failure classes (Codex R2 MAJOR): the accepted-historical
        # carve-out covers ONLY the known pre-fix NON-FINITE-OHLC backlog (the
        # 06-10 NaN cohort the 18-A writer fix could not retro-heal). CORRUPT
        # data -- unparseable JSON or a non-dict bar -- is NOT that backlog and
        # is ALWAYS a red driver regardless of date (never absorbed as historical).
        corrupt = False
        non_finite_ohlc = False
        try:
            bar = json.loads(ohlc_json)
        except (TypeError, ValueError):
            corrupt = True
        else:
            if not isinstance(bar, dict):
                corrupt = True
            else:
                vals = []
                for k in _OHLC_KEYS:
                    v = bar.get(k)
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        # missing / None / non-numeric OHLC value -> a non-finite
                        # hit WITHOUT calling the predicate (it raises on None).
                        non_finite_ohlc = True
                        break
                    vals.append(float(v))
                if not non_finite_ohlc and not is_finite_ohlc(*vals):
                    non_finite_ohlc = True
        if not corrupt and not non_finite_ohlc:
            continue
        # Corrupt-data rows ALWAYS drive red (never eligible for the carve-out).
        # A genuine non-finite-OHLC row is classified by its observation_date vs
        # the baseline. A malformed / None / non-canonical observation_date cannot
        # be proven historical -> treat as post-cutoff (conservative; an undatable
        # non-finite drives red). Require the EXACT canonical `YYYY-MM-DD` shape
        # BEFORE trusting date.fromisoformat (Codex R1 MAJOR -- it would else
        # accept `20260610` / ISO week-dates and could mis-classify a regression
        # as accepted-historical).
        if corrupt:
            is_post_cutoff = True
        elif isinstance(obs_date, str) and _CANONICAL_DATE_RE.match(obs_date):
            try:
                is_post_cutoff = (
                    date.fromisoformat(obs_date) > _FINITENESS_BASELINE_CUTOFF
                )
            except ValueError:
                # canonical shape but an invalid calendar date (e.g. 2026-13-40)
                is_post_cutoff = True
        else:
            is_post_cutoff = True
        if is_post_cutoff:
            post_cutoff += 1
            if len(sample) < 3:
                label = f"{ticker or '?'}@{obs_date}"
                if corrupt:
                    label += " (corrupt)"
                sample.append(label)
        else:
            accepted_historical += 1

    cutoff_iso = _FINITENESS_BASELINE_CUTOFF.isoformat()
    accepted_note = (
        f"accepted historical: {accepted_historical} non-finite @ <={cutoff_iso}"
        " (pre-18A-boundary backfill)"
        if accepted_historical else ""
    )

    if post_cutoff == 0:
        # No post-baseline regression -> GREEN. Surface the accepted-historical
        # cohort (if any) in the detail so it stays visible without driving red.
        summary = f"0 post-baseline non-finite OHLC observations (of {total})"
        return [ResearchHealthCheck(
            key=key, status="green", summary=summary,
            detail=accepted_note or None)]

    # A post-baseline non-finite IS a genuine regression -> RED. Name the
    # post-cutoff red driver(s) AND surface the accepted-historical cohort.
    driver = "; ".join(sample) if sample else None
    detail_parts = [p for p in (driver, accepted_note) if p]
    detail = "; ".join(detail_parts) if detail_parts else None
    return [ResearchHealthCheck(
        key=key, status="red",
        summary=f"{post_cutoff} post-baseline non-finite OHLC observation(s)"
                f" of {total} (cutoff {cutoff_iso})",
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
# CALIBRATION B (18-D §6.7): invalid_ohlc reflects the engine rejecting the SAME
# 06-10 non-finite cohort FIX 1 baselined in check #1 -- a known, accepted,
# PERMANENT ceiling (the immutable temporal log + the 18-B.1 write-barrier mean no
# NEW non-finite can enter; the count only dilutes as unique_signals grows).
# GROUNDED against the newest live manifest (shadow-expectancy-20260613T091809Z:
# invalid_ohlc=23 of 77 unique_signals; plateaued 22->23->23->23 across
# 06-12..06-13). Red ONLY on a count STRICTLY ABOVE this baseline (a new event = a
# write-barrier regression). SCOPE LOCK: baselined ONLY for invalid_ohlc; the
# other two reasons keep their raw _EXCL_*_PCT thresholds.
_INVALID_OHLC_BASELINE_COUNT = 23


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


def _newest_artifact_dir(exports_root):
    """The single newest shadow-expectancy-* dir by name across ALL such dirs
    (Codex R11 MAJOR #1 -- the SHARED selection both the manifest read and the age
    read use, so they never disagree about which artifact is "newest"). None when
    no shadow-expectancy-* dir exists at all."""
    from pathlib import Path

    root = Path(exports_root)
    if not root.exists():
        return None
    dirs = sorted(
        (p for p in root.glob("shadow-expectancy-*") if p.is_dir()),
        key=lambda p: p.name, reverse=True,
    )
    return dirs[0] if dirs else None


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

    The newest dir is selected across ALL shadow-expectancy-* dirs by name (Codex
    R11 MAJOR #1 -- the SAME selection _newest_artifact_age_days uses, so both
    arms agree on the SINGLE newest artifact). ABSENT means NO shadow-expectancy-*
    dir at all; if the newest dir's NAME is not timestamp-parseable (a stray /
    malformed-name artifact) it is CORRUPT (a dir exists -> not "absent" -> must
    escalate). Never crashes on the read.
    """
    newest = _newest_artifact_dir(exports_root)
    if newest is None:
        return ("absent", None)
    if _parse_artifact_dir_ts(newest.name) is None:
        # the newest artifact dir exists but its name is not a parseable timestamp
        # -- a stray name OR a digit-shaped invalid-CALENDAR name (Codex R14 MAJOR)
        # -> a malformed/stray latest artifact, NOT "absent" -> corrupt.
        return ("corrupt", None)
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
        if reason == "invalid_ohlc":
            # CALIBRATION B (the PINNED curve): red ONLY on a count STRICTLY ABOVE
            # the permanent baseline ceiling; below/at -> green; any excess is
            # mapped through the SAME thresholds applied to the EXCESS, with a
            # yellow floor (an excess above a permanent ceiling is never green).
            over = max(0, count - _INVALID_OHLC_BASELINE_COUNT)
            parts.append(
                f"{reason}={count} ({pct:.1f}%, baseline"
                f" {_INVALID_OHLC_BASELINE_COUNT})")
            if over == 0:
                reason_status = "green"
            else:
                # > _EXCL_RED_PCT -> red; otherwise yellow (covers > _EXCL_YELLOW_PCT
                # AND the yellow floor 0 < excess <= 10 -> never green when over>0).
                excess_pct = 100.0 * over / unique_signals
                reason_status = "red" if excess_pct > _EXCL_RED_PCT else "yellow"
        else:
            # SCOPE LOCK: the other two reasons keep their existing RAW-count
            # pct thresholds (NOT baselined).
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
# CALIBRATION A (18-D §6.7): tolerate a TRAILING tail of length <= this many
# sessions -- i.e. only the single NEWEST expected session unobserved is the
# benign post-close -> pre-nightly window (the nightly observe step has not run
# yet for that session). A trailing->=2 lag OR ANY interior/leading gap is a real
# signal and still counts. GROUNDED against the live DB on 2026-06-15: 383
# detections had a pure trailing-1 hole (the recurring nightly false-red) vs 2
# real trailing->=2 lags + 0 interior gaps.
_COVERAGE_TRAILING_GRACE_SESSIONS = 1


def _graced_missing_count(missing: set[str], expected: set[str]) -> int:
    """Return the gap count for one detection after applying the trailing-<=N
    grace (CALIBRATION A). `missing` = expected-but-unobserved sessions;
    `expected` = the full expected session set for the detection.

    A detection is GRACED (returns 0) iff its missing set is EXACTLY the single
    newest expected session and is no longer than the grace bound -- i.e. the only
    hole is the newest expected session and it is a pure trailing-<=N tail. Any
    interior/leading hole, OR a trailing tail of length > N, returns the full
    `len(missing)` (a real signal). When there are no missing sessions -> 0.
    """
    if not missing:
        return 0
    # GRACED iff the ONLY missing session is the newest expected session and the
    # hole is no longer than the trailing grace bound (a pure trailing-<=N tail).
    if (
        len(missing) <= _COVERAGE_TRAILING_GRACE_SESSIONS
        and expected
        and missing == {max(expected)}
    ):
        return 0
    return len(missing)


class _OutOfCalendarError(ValueError):
    """Raised when a degraded-but-ISO-parseable date falls outside the NYSE
    calendar bounds (Codex R13 MAJOR #2). A ValueError subclass so the existing
    malformed-date handling in _check_coverage_gaps treats it as a data-shape
    defect, not a crash."""
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

# CALIBRATION C (coverage-gaps current-vs-historical, brief sec1/sec2;
# watch-standard sec3.1): red ONLY on a CURRENT/ongoing coverage failure (a
# trailing lag beyond CALIBRATION A's grace, an UNEXPLAINED interior observe
# hole, or a zero-observation observe failure). ACCEPT (surface in detail, do
# NOT drive red) a hole that is benign-explained by EITHER:
#   (2a) a WHOLE-SESSION MISSED RUN, ACCEPTED ONLY when the drumbeat has
#        provably moved PAST it (a later session for THAT detection IS observed):
#        the session has ZERO observations anywhere AND no completed
#        pipeline_runs row named it (keyed on the RUN LEDGER's data_asof_date,
#        NOT the mere absence of observations -- runner.py writes
#        observation_date == data_asof_date). BOTH signals are required (the
#        zero-global-observations AND the no-completed-run-ledger-row): the
#        run-ledger half keeps a zero-observation observe failure (a run named S
#        but wrote zero rows) RED; the global-observations half keeps an
#        unexplained hole at a session another detection WAS observed RED.
#   (2b) a per-detection hole explained by a recorded pattern_observe
#        skip-warning (no bar for observation_date / non_finite_ohlc), tied to
#        the (ticker, session) and to the run that observed that session. This is
#        DIRECT evidence of a benign no-bar and is accepted whether the hole is
#        interior, leading, OR TRAILING -- it is NOT gated by the "drumbeat moved
#        past" test (19-A: the delisting fix; a delisted/acquired ticker's holes
#        are trailing, so 2b must fire independent of a later observation).
# An UNEXPLAINED interior hole (the run RAN, the bar existed, the row was
# dropped with no skip-warning) STAYS RED -- the real observe-step-bug signal.
# Conservative-degrade: a dropped/empty/unavailable pipeline_runs ledger ->
# _run_observed_sessions returns None -> clause 2a is FALSE for every session ->
# nothing is missed-run-accepted (never accept-everything-false-green).
_OBSERVE_SKIP_REASONS = ("no bar for observation_date", "non_finite_ohlc")


def _canonical_session(value: object) -> str | None:
    """Return the canonical YYYY-MM-DD isoformat for a session date string, or
    None if it is not an ISO-parseable date (Codex R1 MAJOR). date.fromisoformat
    accepts non-canonical forms (compact 20260611 / week 2026-W24-4); the
    CALIBRATION C session sets MUST all be canonical so membership/comparison
    against the canonical `expected` sessions is apples-to-apples and a degraded
    row cannot masquerade as a later observation / missed-run signal."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _observe_skip_index(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    """Return the set of (ticker, observation_date) pairs explained by a
    recorded `pattern_observe` skip-warning in a COMPLETED pipeline run
    (CALIBRATION C clause 2b). Reads pipeline_runs.warnings_json (migration
    0003; runner.py writes the entries at run completion).

    ONLY state='complete' runs (MAJOR-R2-2: a failed/non-complete/stale run's
    warnings must not explain a hole), and ONLY warnings whose `step` is
    'pattern_observe', `reason` is in _OBSERVE_SKIP_REASONS, AND whose
    `observation_date` equals THAT row's data_asof_date (MAJOR-R2-2: tie the
    free-text warning to the session the run actually observed). DEFENSIVE
    (read-only monitor, the schema-boundary discipline): a missing pipeline_runs
    table -> empty set (no explanations -> unexplained holes COUNT, never crash,
    never false-green). A NULL/non-JSON/non-list/non-dict warnings_json row is
    skipped gracefully (a general parse-guard, NOT per-value-shape branches).
    """
    try:
        rows = conn.execute(
            "SELECT data_asof_date, warnings_json FROM pipeline_runs"
            " WHERE state = 'complete'"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return set()
        raise
    index: set[tuple[str, str]] = set()
    for asof, warnings_json in rows:
        if not warnings_json:
            continue
        try:
            items = json.loads(warnings_json)
        except (ValueError, TypeError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("step") != "pattern_observe":
                continue
            if item.get("reason") not in _OBSERVE_SKIP_REASONS:
                continue
            ticker = item.get("ticker")
            obs_date = item.get("observation_date")
            if not isinstance(ticker, str) or not isinstance(obs_date, str):
                continue
            # Canonicalize both dates before comparing/indexing (Codex R1 MAJOR):
            # date.fromisoformat accepts non-canonical forms; comparing raw
            # strings could both mis-tie the warning AND index a key that never
            # matches the canonical (ticker, session) lookup. A non-parseable
            # date on either side -> skip the entry (no explanation, conservative).
            obs_c = _canonical_session(obs_date)
            asof_c = _canonical_session(asof)
            if obs_c is None or asof_c is None:
                continue
            # Tie the warning to the session the run actually observed: the
            # observe step writes observation_date == data_asof_date, so a
            # date-mismatched warning attached to the wrong run must not explain
            # a hole at an arbitrary session (MAJOR-R2-2).
            if obs_c != asof_c:
                continue
            index.add((ticker, obs_c))
    return index


def _global_observed_sessions(conn: sqlite3.Connection) -> set[str]:
    """Return the set of sessions that have AT LEAST ONE observation anywhere
    (DISTINCT observation_date), the FIRST half of the whole-session-miss AND
    (CALIBRATION C clause 2a; MAJOR-R2-1). The parent _check_coverage_gaps has
    already opened the observations table successfully under its own
    _schema_unavailable guard, so this read is inside that guarded region; an
    empty table -> empty set (every session is globally unobserved, which only
    matters paired with the run-ledger half -> never accepts on its own).
    """
    rows = conn.execute(
        "SELECT DISTINCT observation_date FROM pattern_forward_observations"
    ).fetchall()
    # Canonicalize (Codex R1 MAJOR): a non-canonical/unparseable observation_date
    # is dropped from the global set. Dropping it is the conservative direction
    # for clause 2a's FIRST half -- a session that ONLY had a degraded-date
    # observation is treated as globally-unobserved, but acceptance still
    # requires the run-ledger half (which a true missed run also fails), so a
    # degraded row never independently drives a false-green accept.
    sessions: set[str] = set()
    for (raw,) in rows:
        canon = _canonical_session(raw)
        if canon is not None:
            sessions.add(canon)
    return sessions


def _run_observed_sessions(conn: sqlite3.Connection) -> set[str] | None:
    """Return the set of sessions a COMPLETED pipeline run actually observed
    (DISTINCT data_asof_date of state='complete' runs; the observe step writes
    observation_date == data_asof_date, runner.py). The AUTHORITATIVE missed-run
    signal (MAJOR-R1-4): a benign whole-session miss is `S NOT IN` this set.

    Returns None (NOT an empty set) when pipeline_runs is UNAVAILABLE
    (_schema_unavailable) OR when there are zero completed runs -- the
    CONSERVATIVE-DEGRADE sentinel. With no proven run ledger, clause 2a is FALSE
    for every S (a missed run cannot be proven), so an interior hole must be
    skip-warning-explained or it COUNTS. Returning an empty set instead would
    make `S not in set()` TRUE for every S -> accept-everything false-green.
    DELIBERATELY NOT the weaker DISTINCT observation_date predicate, which would
    false-green a genuine zero-observation observe failure (a run that ran for S
    but wrote zero rows) the moment any later session is observed.
    """
    try:
        rows = conn.execute(
            "SELECT DISTINCT data_asof_date FROM pipeline_runs"
            " WHERE state = 'complete'"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return None
        raise
    # Canonicalize the ledger (Codex R1 MAJOR). If ANY completed-run
    # data_asof_date is non-canonical/unparseable, the ledger is untrustworthy
    # for the missed-run test -> return None (disable clause 2a entirely, the
    # conservative-degrade: an unprovable ledger never accepts a missed run).
    sessions: set[str] = set()
    for (raw,) in rows:
        canon = _canonical_session(raw)
        if canon is None:
            return None
        sessions.add(canon)
    return sessions or None


def _calibration_c_partition(
    missing_set: set[str],
    observed: set[str],
    ticker: str | None,
    global_observed_sessions: set[str],
    run_observed_sessions: set[str] | None,
    skip_index: set[tuple[str, str]],
) -> tuple[set[str], set[str]]:
    """Partition a detection's missing sessions into (accepted, residual) per
    CALIBRATION C. A session S in `missing_set` is ACCEPTED iff:
        skip_explained (clause-2b, INDEPENDENT of clause1)
        OR (clause1 AND is_whole_session_miss (clause-2a)).
      clause-2b = ((ticker, S) in skip_index): a per-(ticker, S) recorded
                pattern_observe skip-warning is DIRECT evidence of a benign
                no-bar (e.g. a delisted/acquired ticker with no further bars),
                so it is accepted whether the hole is interior, leading, OR
                TRAILING -- it is NOT gated by clause1 (19-A: the delisting fix;
                a trailing OR never-observed hole is accepted when, and only
                when, it is skip-warning-explained).
      clause1 = bool(observed) and max(observed) > S  (the drumbeat moved PAST
                the hole; a TRAILING/never-observed hole has no later
                observation -> clause1 False). clause1 gates ONLY clause-2a: a
                trailing whole-session miss with NO skip-warning stays COUNTED
                (a real drumbeat-behind failure -- the T2/T3 safety locks).
      clause-2a = is_whole_session_miss, requiring BOTH (S not in
                global_observed_sessions) AND (run_observed_sessions is not None
                and S not in run_observed_sessions) (MAJOR-R2-1: the BOTH-signals
                AND). The `is not None` guard is the conservative-degrade -- a
                degraded run-ledger never accepts a missed-run hole.
    `residual = missing_set - accepted` (the caller then applies CALIBRATION A
    on the residual). A non-str ticker simply never matches skip_index -> the
    hole falls through to COUNTED (defensive)."""
    accepted: set[str] = set()
    has_later = bool(observed)
    latest_observed = max(observed) if observed else None
    for session in missing_set:
        # clause-2b (skip-warning-explained): DIRECT per-(ticker, session)
        # evidence of a benign no-bar (delisting / no-quote), legitimate whether
        # the hole is interior, leading, OR trailing -> evaluated INDEPENDENT of
        # clause-1. (19-A: a delisted ticker's holes are trailing, so clause-1 is
        # False and 2b must not be gated behind it.)
        skip_explained = (
            isinstance(ticker, str) and (ticker, session) in skip_index
        )
        if skip_explained:
            accepted.add(session)
            continue
        # clause-2a (whole-session missed run) STAYS clause-1-gated: a trailing
        # whole-session miss (no later observation) is a real drumbeat-behind
        # failure and must stay COUNTED (RED). clause1 = the drumbeat moved PAST
        # this hole (a later session for THIS detection is observed).
        clause1 = has_later and latest_observed is not None and latest_observed > session
        if not clause1:
            continue
        is_whole_session_miss = (
            session not in global_observed_sessions
            and run_observed_sessions is not None
            and session not in run_observed_sessions
        )
        if is_whole_session_miss:
            accepted.add(session)
    residual = missing_set - accepted
    return accepted, residual


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
            "SELECT d.detection_id, d.data_asof_date, d.ticker,"
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

    # CALIBRATION C globals (computed ONCE; read-only). ticker carried per
    # detection (MAJOR-R1-1: needed for the (ticker, S) skip-warning join).
    global_observed_sessions = _global_observed_sessions(conn)
    run_observed_sessions = _run_observed_sessions(conn)
    skip_index = _observe_skip_index(conn)

    # Group per detection (preserving obs date order); record the asof + ticker.
    per_det: dict[int, dict] = {}
    for det_id, asof, ticker, obs_date, status, _obs_id in rows:
        entry = per_det.setdefault(det_id, {"asof": asof, "ticker": ticker, "obs": []})
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
        # date.fromisoformat ACCEPTS out-of-calendar dates (e.g. 0001-01-01 / a
        # far-future year); sessions_in_range then raises OUTSIDE the exchange
        # calendar bounds (Codex R13 MAJOR #2). Catch + re-raise a typed signal so
        # the per-detection loop counts it as a malformed-date defect, not a crash.
        if start > end:
            return set()
        try:
            idx = _NYSE.sessions_in_range(start, end)
        except (ValueError, KeyError, OverflowError) as exc:
            raise _OutOfCalendarError(str(exc)) from exc
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
    accepted_historical = 0
    accepted_sample: list[str] = []
    for det_id, entry in per_det.items():
        obs = entry["obs"]
        det_ticker = entry["ticker"]
        # The detector cutoff drives the WHOLE expected window -- if IT is
        # malformed/NULL the window is undefined, so the detection is a pure
        # malformed defect (Codex R4 MAJOR #1: no-crash on a degraded DB).
        try:
            asof = _date.fromisoformat(entry["asof"])
        except (TypeError, ValueError):
            malformed += 1
            if len(sample) < 3:
                sample.append(f"det{det_id}: malformed data_asof_date")
            continue
        # Partition observed dates into VALID + count malformed rows (Codex R12
        # MAJOR #1): a malformed OBSERVED row must NOT skip the whole detection
        # (that could downgrade a RED missing-tail to a mere yellow malformed) --
        # count it AND still compute gaps/tail from the VALID observed dates.
        observed: set[str] = set()
        # CANONICAL (date, seq, status) for the VALID-dated rows (Codex R2 MAJOR):
        # the latest-status selection must filter/compare on the SAME canonical
        # dates as `observed`, not the raw strings (a non-canonical raw date would
        # be excluded -> wrong/older status chosen, or max() on empty). `seq` is a
        # stable tie-breaker mirroring the SQL ORDER BY observation_id ASC.
        valid_obs: list[tuple[str, int, object]] = []
        row_malformed = 0
        for seq, (d, status) in enumerate(obs):
            try:
                parsed = _date.fromisoformat(d)
            except (TypeError, ValueError):
                row_malformed += 1
            else:
                # Canonicalize to YYYY-MM-DD (Codex R1 MAJOR): date.fromisoformat
                # accepts compact/week ISO forms (20260611 / 2026-W24-4); the raw
                # string would not match the canonical `expected` sessions nor the
                # canonical CALIBRATION C global/run sets -> a degraded row could
                # masquerade as a "later observation" and drive a false-green
                # accept. Store the canonical isoformat so all comparisons are
                # apples-to-apples.
                canon = parsed.isoformat()
                observed.add(canon)
                valid_obs.append((canon, seq, status))
        if row_malformed:
            malformed += 1
            if len(sample) < 3:
                sample.append(f"det{det_id}: {row_malformed} malformed obs date(s)")
        # Codex R10 MAJOR #1: a DUPLICATE observation_date (impossible under the
        # schema UNIQUE but possible on a degraded DB) is a data-shape defect; a
        # late terminal duplicate could otherwise suppress a missing tail. Count
        # it but DON'T skip the gap computation from the valid distinct dates.
        n_valid_rows = len(obs) - row_malformed
        if n_valid_rows != len(observed):
            malformed += 1
            if len(sample) < 3:
                sample.append(f"det{det_id}: duplicate observation_date")
        # Maturity applied in PYTHON after the parse (Codex R6 MAJOR #3): mature =
        # at least one tradable session since the cutoff. (A SQL string predicate
        # would have lexically dropped a malformed/NULL asof before this point.)
        if asof >= last_completed:
            continue  # not mature -- no completed session since the cutoff
        # The gap/tail computation calls the NYSE calendar, which raises
        # _OutOfCalendarError on a degraded but ISO-parseable out-of-bounds date (Codex
        # R13 MAJOR #2) -- count it as a malformed defect, never crash.
        try:
            if not observed:
                # mature detection with ZERO valid observations: every expected
                # session (first-after-cutoff .. last_completed) is missing.
                first = _first_session_after(asof)
                if first is None:
                    continue  # too fresh -- no session yet to observe
                expected = _sessions(first, last_completed)
                # CALIBRATION C first: observed is EMPTY -> clause-1 is FALSE for
                # every session, so clause-2a accepts nothing -- BUT clause-2b can
                # still fire per-session (a never-observed detection whose expected
                # sessions carry recorded skip-warnings: the immediate-delisting-
                # after-detection case, 19-A consequence #2). residual == expected
                # ONLY when NO expected session is skip-explained. Then CALIBRATION
                # A on the residual (a never-observed detection whose ONLY residual
                # session is the single newest one is benign pre-nightly).
                accepted, residual = _calibration_c_partition(
                    expected, observed, det_ticker,
                    global_observed_sessions, run_observed_sessions, skip_index)
                if accepted:
                    accepted_historical += len(accepted)
                    if len(accepted_sample) < 3:
                        accepted_sample.append(
                            f"det{det_id}: {len(accepted)} accepted"
                            f" ({', '.join(sorted(accepted)[:3])})")
                missing = _graced_missing_count(residual, expected)
                if missing:
                    total_missing += missing
                    if len(sample) < 3:
                        sample.append(
                            f"det{det_id}: {missing} missing (never observed)")
                continue
            # latest status from the VALID-dated rows (Codex R12 MAJOR #1),
            # selected on the CANONICAL date with the seq tie-breaker (Codex R2
            # MAJOR: filtering raw obs by `oc[0] in observed` would exclude a
            # canonicalized non-canonical row -> wrong/older status or max() on
            # empty). valid_obs is non-empty here (the not-observed arm handled
            # the zero-valid case above).
            latest_status = max(valid_obs, key=lambda x: (x[0], x[1]))[2]
            max_obs = _date.fromisoformat(max(observed))
            # The expected window STARTS at the first session after the cutoff
            # (Codex R3 MAJOR #1 -- a LATE first observation is a real leading
            # gap). Upper bound by latest status: a KNOWN TERMINAL status stopped
            # -> max_obs (no tail); OPEN or an UNKNOWN/NULL status -> last_completed
            # (Codex R6 MAJOR #4: unknown != terminal, else a tail is suppressed).
            first = _first_session_after(asof)
            if first is None:
                continue  # too fresh -- no session yet to observe
            is_terminal = latest_status in _TERMINAL_STATUSES
            upper = max_obs if is_terminal else last_completed
            expected = _sessions(first, upper)
            # CALIBRATION C first: accept interior/leading holes the drumbeat
            # moved past that are whole-session missed-runs (clause-2a,
            # clause-1-gated) OR any skip-warning-explained hole (clause-2b,
            # interior/leading/TRAILING -- not gated by clause-1). Then
            # CALIBRATION A on the residual (18-D sec6.7: grace a pure trailing-<=1
            # newest-session tail). C-FIRST-A-ON-RESIDUAL is required: A graces
            # only when missing == {max(expected)}, so a detection with an
            # accepted interior hole PLUS the benign trailing-1 hole would not be
            # graced if A ran first. Interior/leading holes + trailing->=2 that
            # are NOT accepted still count.
            missing_set = expected - observed
            accepted, residual = _calibration_c_partition(
                missing_set, observed, det_ticker,
                global_observed_sessions, run_observed_sessions, skip_index)
            if accepted:
                accepted_historical += len(accepted)
                if len(accepted_sample) < 3:
                    accepted_sample.append(
                        f"det{det_id}: {len(accepted)} accepted"
                        f" ({', '.join(sorted(accepted)[:3])})")
            missing = _graced_missing_count(residual, expected)
        except _OutOfCalendarError:
            malformed += 1
            if len(sample) < 3:
                sample.append(f"det{det_id}: out-of-calendar date")
            continue
        if missing:
            total_missing += missing
            if len(sample) < 3:
                sample.append(f"det{det_id}: {missing} missing")

    # CALIBRATION C audit (#27 silent-skip discipline): accepted historical gaps
    # NEVER silently dropped -- they surface in the summary (count) + detail
    # (sample) in EVERY return path below, including the malformed branch
    # (MINOR-R1-5). accepted_sample is built in detection-id iteration order so
    # the detail is order-stable for tests.
    accepted_note = (
        f"; {accepted_historical} accepted historical (missed-run/skip)"
        if accepted_historical else ""
    )
    detail_parts = list(sample)
    if accepted_sample:
        detail_parts.append("accepted: " + ", ".join(accepted_sample))
    combined_detail = "; ".join(detail_parts) if detail_parts else None

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
                    f" {malformed} malformed-date detection(s){accepted_note}",
            detail=combined_detail)]

    if total_missing == 0:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary=f"0 observation-coverage gaps{accepted_note}",
            detail=combined_detail)]
    if total_missing > _COVERAGE_RED_GAPS:
        status = "red"
    elif total_missing >= _COVERAGE_YELLOW_GAPS:
        status = "yellow"
    else:
        status = "green"
    return [ResearchHealthCheck(
        key=key, status=status,
        summary=f"{total_missing} observation-coverage gap(s){accepted_note}",
        detail=combined_detail)]


def _check_structural_integrity(
    conn: sqlite3.Connection,
) -> list[ResearchHealthCheck]:
    """Two probes, RED on ANY hit (a structural-integrity violation is never
    tolerable; brief §6.2 #4):
      - orphan observations (LEFT JOIN with no parent detection);
      - look-ahead: a detection whose FIRST observation precedes its
        detection_date (strict `<`).
    The look-ahead comparison is done in PYTHON after date.fromisoformat (Codex
    R10 MAJOR #2): a lexical SQL `first_obs < detection_date` would silently miss
    a violation when either date is MALFORMED on a degraded DB -> a malformed
    date is counted as a data-shape defect (yellow), consistent with the
    coverage check. Missing table -> yellow schema-unavailable.
    """
    from datetime import date as _date

    key = "structural_integrity"
    try:
        orphans = conn.execute(
            "SELECT COUNT(*) FROM pattern_forward_observations o"
            " LEFT JOIN pattern_detection_events d"
            " ON d.detection_id = o.detection_id"
            " WHERE d.detection_id IS NULL"
        ).fetchone()[0]
        # Fetch EVERY (observation_date, detection_date) pair (Codex R12 MAJOR #2):
        # a SQL MIN(observation_date) is LEXICAL, so on a degraded DB a malformed
        # lexicographically-earlier row could mask a real look-ahead in a later
        # valid row, or a malformed non-min row would never be seen. Parse + check
        # look-ahead per ROW in Python; count malformed rows.
        rows = conn.execute(
            "SELECT o.observation_date, d.detection_date"
            " FROM pattern_forward_observations o"
            " JOIN pattern_detection_events d"
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

    look_ahead = 0
    malformed = 0
    for obs_date, detection_date in rows:
        try:
            if _date.fromisoformat(obs_date) < _date.fromisoformat(detection_date):
                look_ahead += 1  # an observation BEFORE its detection_date
        except (TypeError, ValueError):
            malformed += 1

    if not orphans and not look_ahead and malformed:
        return [ResearchHealthCheck(
            key=key, status="yellow",
            summary=f"{malformed} malformed-date detection(s) in the temporal log",
            detail="degraded date shape; cannot verify look-ahead for these rows")]

    if orphans or look_ahead:
        extra = f", {malformed} malformed-date" if malformed else ""
        return [ResearchHealthCheck(
            key=key, status="red",
            summary=f"{orphans} orphan observation(s),"
                    f" {look_ahead} look-ahead violation(s){extra}",
            detail="structural-integrity violation in the temporal log")]
    return [ResearchHealthCheck(
        key=key, status="green",
        summary="0 orphans, 0 look-ahead violations")]


# --------------------------------------------------------------------------
# Drumbeat liveness (artifact age + total_unattributed) + candidate
# completeness (sentinel-filtered null pivots + error-bucket).
# --------------------------------------------------------------------------

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
    """Age in (floored) days of the SINGLE newest shadow-expectancy-* dir vs
    `now`, by the dir-name UTC timestamp (the weekly_glance.py:74-78 idiom). Uses
    the SHARED _newest_artifact_dir selection (Codex R11 MAJOR #1) so the age arm
    and the manifest arm agree on which dir is "newest". None when no dir exists
    at all OR the newest dir's NAME is not timestamp-parseable (a stray/malformed
    newest -- the manifest arm reports that as corrupt). The age is read from the
    dir NAME, so it is available even when the manifest CONTENT is corrupt (a
    fresh-but-corrupt dir is NOT stale)."""
    newest = _newest_artifact_dir(exports_root)
    if newest is None:
        return None
    parsed = _parse_artifact_dir_ts(newest.name)
    if parsed is None:
        # newest dir name unparseable (stray OR digit-shaped invalid-calendar,
        # Codex R14 MAJOR) -> the manifest arm reports corrupt; never strptime-crash.
        return None
    return (_now_to_utc(now) - parsed).days


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
        # Distinguish NO artifact dir at all (red, never ran) from a newest dir
        # whose NAME is unparseable (a stray/malformed newest -> the manifest arm
        # reports corrupt -> yellow), Codex R11 MAJOR #1.
        if _newest_artifact_dir(exports_root) is None:
            return [ResearchHealthCheck(
                key=key, status="red",
                summary="drumbeat never ran (no engine artifacts on disk)")]
        return [ResearchHealthCheck(
            key=key, status="yellow",
            summary="newest engine artifact has a malformed name",
            detail="cannot read the artifact timestamp; latest run is corrupt")]

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
        # The in_flight detail tally MUST be inside the SAME guard (Codex R12
        # MAJOR #3): a mid-read schema change would otherwise crash here instead
        # of degrading to yellow "schema unavailable".
        n_in_flight = conn.execute(
            "SELECT COUNT(*) FROM ("
            " SELECT call_id FROM yfinance_calls WHERE status = 'in_flight'"
            " ORDER BY ts DESC, call_id DESC LIMIT ?)",
            (_TRANSPORT_RECENT_WINDOW,),
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return [ResearchHealthCheck(
                key=key, status="yellow",
                summary="yfinance_calls schema unavailable",
                detail="yfinance_calls table missing; run swing db-migrate")]
        raise

    # in_flight is EXCLUDED from the rate denominator (stale = unknown, not hung
    # -- the 18-C LOCK), but its count is SURFACED in the detail (Codex R9 MAJOR)
    # so an all-/mostly-in_flight table is not silently "no fetch audit". NOT a
    # census, NOT a denominator input, NEVER drives the color.
    in_flight_note = f"; {n_in_flight} in_flight (excluded)" if n_in_flight else ""

    if not rows:
        return [ResearchHealthCheck(
            key=key, status="green",
            summary="n/a (no terminal fetch audit yet)",
            detail=f"0 terminal rows{in_flight_note}")]

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
                   f"{in_flight_note} (below sample floor)")]

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
        # in_flight surfaced consistently on the normal-rate path too (Codex R10
        # MINOR #1) -- still denominator-excluded, never color-driving.
        detail=f"{n_error} error, {n_empty} empty of {n} terminal rows"
               f"{in_flight_note}")]


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
