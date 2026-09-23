"""22-A2 -- the frozen-value evidence class (tier-2): the preflight, the
four-part conjunction, the seventh-column blob and the read-time replay.

F4 (CHARC, ruled in the brief): this module performs NO DB WRITE and opens NO
TRANSACTION, module-wide; its callers are enumerated by test (A2-75).

This file is built across the 22-A2 task ladder.  ``FROZEN_VALUE_EVIDENCE_VERSION``
landed with migration 0039 (Task 3) because the citation trigger binds the
seventh-column blob's version to it and the #11 drift test compares the two
in the SAME commit as the schema.

THE PREFLIGHT (Task 4).  The operator supplies a SELECTION, never a value (F9):
an evidence file carrying exactly ``artifact_path``, ``artifact_commit_sha`` and
``quoted_text``.  ``run_preflight`` loads it and reads the artifact at that sha
from git -- every git call under ``GIT_TIMEOUT_SECONDS``, with ``cwd`` the
evidence repo, output captured as BYTES (the cp1252 decode gotcha: text is
decoded ``utf-8`` explicitly, and the quoted text is matched as bytes), and
never inside a SQLite transaction (S12.1 #9).  It NEVER raises (encoding E-6):
every outcome is a ``PreflightResult``.  Failure classes (E-10): a PROCESS
failure (timeout, git missing, no ``REMOTE_REF``, an unexpected git exit) is
``tier2_unverifiable``; git ANSWERING negatively about the selection (object or
path missing, quoted text absent or multi-line) is a named selection refusal.
Ancestry is a FACT here (``is_ancestor``); criterion 1's verdict is the
conjunction's (Task 5).
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# CHARC G-T7F item 3: TWO versions, because the blob carries two quantities.
#
# (A) The GRAMMAR version -- ``$.evidence_version`` of
# ``cited_frozen_value_evidence_json``: the key roster, the types, the
# bindings.  Migration 0039's citation trigger pins it by LITERAL (a drift test
# reads the literal out of the HEAD trigger), so it moves only with a trigger
# edit, which is a migration by nature -- and that migration must DECLARE how
# the rows already written replay (0039's reversibility header, D60).
FROZEN_VALUE_EVIDENCE_VERSION = "2026-09-23.1"

# (B) The DERIVATION version -- ``$.derivation_version``: the code the blob's
# values are a function of.  Bound to the AST digest of that code through
# ``FROZEN_VALUE_EVIDENCE_HISTORY`` (bottom of this module); a behaviour edit
# to any member fails the suite until this moves.  SQL asserts only that the
# stored value is TEXT (a derivation change is invisible to SQL by
# construction), and the read-time replay compares it to this constant as an
# OBSERVATION, never as a verdict (G-T7F-AMEND).  Deliberately a DIFFERENT
# string from (A), so a builder writing one constant under the other's key is
# visible to every literal comparison.
FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION = "2026-09-23.3"

# Every git call's own timeout (seconds).  The replay uses the same name.
GIT_TIMEOUT_SECONDS = 10.0

# F5 (CHARC): the LOCAL remote-tracking ref, read as-is -- never fetched; its
# age is recorded, never verdict-bearing.
REMOTE_REF = "refs/remotes/origin/main"

# E-11: the evidence repo is the package's own repo root; overridable by
# keyword so tests run against a temp repo with a bare "remote".
EVIDENCE_REPO_DIR = Path(__file__).resolve().parents[2]

# F9: the evidence file's CLOSED key set, in this order.
EVIDENCE_FILE_KEYS: tuple[str, ...] = ("artifact_path", "artifact_commit_sha", "quoted_text")

# Selection refusals and the process class (plan section 1 vocabulary).
FAILURE_EVIDENCE_FILE_MALFORMED = "evidence_file_malformed"
FAILURE_ARTIFACT_UNREADABLE = "artifact_unreadable"
FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT = "quoted_text_not_in_artifact"
FAILURE_QUOTED_TEXT_NOT_ONE_LINE = "quoted_text_not_one_line"
FAILURE_TIER2_UNVERIFIABLE = "tier2_unverifiable"

# The preflight functions and their git helpers: A2-41 pins that none of them
# names a DB handle (the conjunction half READS one; the preflight never does).
PREFLIGHT_FUNCTIONS: tuple[str, ...] = (
    "load_evidence_selection", "read_artifact_facts", "run_preflight",
    "_run_git", "_parse_reflog_instant",
    # G-T9 item 2: the per-invocation ref resolution and its stages.
    "resolve_remote_ref", "_budgeted_git", "_ref_stage", "_reflog_stage",
)

_SHA_RE = re.compile(r"[0-9a-f]{40}")

# --------------------------------------------------------------------------
# The conjunction's constants (plan section 1; the seventh-column blob roster
# of section 2).  The three texts are MODULE CONSTANTS, never operator input
# (F9 sub-choice).
# --------------------------------------------------------------------------
RULING_CITATION = (
    "22-A plan S12.1 (the settled tier-2 doctrine) + RD ruling 2026-08-24 + "
    "22-A2 rulings R0.7-R0.12 (F6-F13)")
VERIFICATION_METHOD = (
    "four-part conjunction: (1) the artifact commit is an ancestor of "
    "refs/remotes/origin/main; (2) the author instant's America/New_York date "
    "strictly precedes the fill session; (3) the quoted text contains the cited "
    "candidate's ticker, action session, pivot and initial_stop as "
    "service-rendered tokens; (4) the record is strictly after the fire's pipeline "
    "finished_ts")
ANCHOR_STRENGTH = "remote_replicated_ancestry"
TIME_ANCHOR_RESIDUAL = (
    "author and committer dates are caller-settable; origin/main ancestry is "
    "the anchor (S12.1 #7)")
COMPARE_DP = 2
ET_ZONE = ZoneInfo("America/New_York")

# Refusal vocabulary of criteria 1, 2 and 4 (criterion 3 names its FIELD).
REASON_NOT_ANCESTOR = "not_ancestor_of_origin_main"
REASON_RECORDED_ON_FILL_SESSION = "recorded_on_fill_session"
REASON_RECORDED_AFTER_FILL_SESSION = "recorded_after_fill_session"
REASON_WINDOW_NEGATIVE = "window_negative"
REASON_WINDOW_INDETERMINATE = "window_indeterminate"
CRITERION3_FIELDS: tuple[str, ...] = ("ticker", "action_session", "pivot", "invalidation")

# The seventh-column blob's CLOSED key roster (plan section 2), in order.
FROZEN_VALUE_BLOB_KEYS: tuple[str, ...] = (
    "evidence_version", "derivation_version", "ruling_citation",
    "verification_method", "evaluated_at", "artifact_path", "artifact_commit_sha",
    "quoted_text", "quoted_ticker_text",
    "quoted_action_session_text", "quoted_pivot_text", "quoted_invalidation_text",
    "live_pivot_raw", "live_invalidation_raw", "pivot_equal_at_dp",
    "invalidation_equal_at_dp", "compare_dp", "author_instant", "author_date_et",
    "committer_instant", "fill_session_date", "resolved_remote_ref_sha",
    "descendant_count", "remote_ref_updated_at", "remote_ref_age_seconds",
    "anchor_strength", "time_anchor_residual", "interval", "uncovered_window_prose",
)
INTERVAL_ENDPOINTS: tuple[str, ...] = (
    "fire_lo", "fire_hi", "record_at", "barrier_armed_at", "read_at")
_ENDPOINT_KEYS = ("raw", "utc", "clock_domain", "source")
_ENDPOINT_DOMAIN_SOURCE: dict[str, tuple[str, str]] = {
    "fire_lo": ("naive_local_pipeline", "evaluation_runs.run_ts"),
    "fire_hi": ("naive_local_pipeline", "pipeline_runs.finished_ts"),
    "record_at": ("iso_offset", "git_author_instant"),
    "barrier_armed_at": ("utc_z", "candidates_immutability_epoch.applied_at"),
    "read_at": ("naive_utc_ms", "provenance_corrections.applied_at"),
}
SEGMENT_KINDS: tuple[str, ...] = ("fire", "writer_absence_only", "match_only")
SEGMENT_COVERED = "covered"
SEGMENT_UNCOVERED_BARRIER_ABSENT = "uncovered_barrier_absent"
# RD's F2.I-NEG + CHARC's G-NEG: where record_at sits relative to
# barrier_armed_at, recorded inside ``interval`` (a verdict-bearing key).
RECORD_POSITION_BEFORE_BARRIER = "before_barrier"
RECORD_POSITION_INSIDE_COVERAGE = "inside_coverage"
RECORD_POSITIONS: tuple[str, ...] = (
    RECORD_POSITION_BEFORE_BARRIER, RECORD_POSITION_INSIDE_COVERAGE)

# E-15: the keys the replay COMPARES (dotted paths into the blob).  Everything
# else is RECORDED only -- evaluated_at, the resolved sha, the descendant
# count, the ref age, the committer instant, the segments -- and never compared.
VERDICT_BEARING_KEYS: frozenset[str] = frozenset({
    "artifact_path", "artifact_commit_sha", "quoted_text",
    "quoted_ticker_text", "quoted_action_session_text", "quoted_pivot_text",
    "quoted_invalidation_text", "live_pivot_raw", "live_invalidation_raw",
    "author_instant", "author_date_et", "fill_session_date",
    *(f"interval.endpoints.{e}.{k}" for e in INTERVAL_ENDPOINTS for k in ("raw", "utc")),
    "interval.record_position",
})

# --------------------------------------------------------------------------
# The read-time replay's vocabulary (Task 9; plan section 1).
# --------------------------------------------------------------------------
VERDICT_ADMIT = "ADMIT"
VERDICT_STALE = "tier2_evidence_stale"
VERDICT_UNVERIFIABLE = FAILURE_TIER2_UNVERIFIABLE
REPLAY_VERDICTS: tuple[str, ...] = (VERDICT_ADMIT, VERDICT_STALE, VERDICT_UNVERIFIABLE)
# CHARC R4.2 ruling 1: the TOTAL wall-clock replay budget, per invocation of
# ``tier2_cohort_exclusions``, that every WEB caller of a cohort reader passes
# (G-T10-1 (2): the dashboard VM, the trade-entry prefill, the tier and
# deviation VMs, the card route and the metrics index); the CLI and the drift
# reader pass none.
WEB_REPLAY_BUDGET_SECONDS = 2.0
REASON_WEB_BUDGET_EXHAUSTED = "web_budget_exhausted"
# S12.1 #9 at the replay (CHARC's G-T7 Q1 principle): no git subprocess runs
# inside a transaction the caller holds.
REASON_CALLER_HOLDS_TRANSACTION = "caller_holds_transaction"
REASON_STORED_EVIDENCE_MALFORMED = "stored_evidence_malformed"
REASON_FILL_SESSION_MALFORMED = "entry_fill_session_date_malformed"
REASON_AUTHOR_INSTANT_CHANGED = "author_instant_changed"


@dataclass(frozen=True)
class EvidenceSelection:
    """The operator's SELECTION (F9): where the record is, never what it says."""

    artifact_path: str
    artifact_commit_sha: str
    quoted_text: str


@dataclass(frozen=True)
class ArtifactFacts:
    """What git says about a selection.  Instants are offset-AWARE."""

    selection: EvidenceSelection
    author_instant: datetime
    committer_instant: datetime
    is_ancestor: bool
    resolved_remote_ref_sha: str
    descendant_count: int | None
    remote_ref_updated_at: datetime | None
    remote_ref_age_seconds: int | None


@dataclass(frozen=True)
class PreflightResult:
    """Exactly one of ``facts`` / ``failure`` is set; ``detail`` names why."""

    facts: ArtifactFacts | None
    failure: str | None
    detail: str


@dataclass(frozen=True)
class Tier2Request:
    """What the correction path hands rung 9's escape seam (Task 6).

    ``preflight`` ran BEFORE the transaction (S12.1 #9; git never runs inside
    ``BEGIN IMMEDIATE``); ``applied_at`` is the ONE stamp the row's column, the
    blob's ``evaluated_at`` and the interval's ``read_at`` share (E-7).  The
    entry path never constructs one (A2-65 pins the caller).
    """

    preflight: PreflightResult
    applied_at: str


class _GitProcessError(Exception):
    """A git PROCESS failure -> ``tier2_unverifiable`` (E-10)."""


class _BudgetExhaustedError(_GitProcessError):
    """The caller's TOTAL replay budget ran out before a git call started
    (CHARC R4.2 ruling 1): checked BETWEEN calls, never by killing one."""


def _refuse(failure: str, detail: str) -> PreflightResult:
    return PreflightResult(facts=None, failure=failure, detail=detail)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def load_evidence_selection(path: Path | str) -> EvidenceSelection | PreflightResult:
    """Parse the evidence file; anything but the closed F9 shape is ``evidence_file_malformed``.

    Returns the selection, or a failed ``PreflightResult``.  Never raises.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return _refuse(FAILURE_EVIDENCE_FILE_MALFORMED,
                       f"evidence file unreadable: {type(exc).__name__}")
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        return _refuse(FAILURE_EVIDENCE_FILE_MALFORMED,
                       f"evidence file is not a UTF-8 JSON object: {exc}")
    if not isinstance(payload, dict):
        return _refuse(FAILURE_EVIDENCE_FILE_MALFORMED, "evidence file is not a JSON object")
    if set(payload) != set(EVIDENCE_FILE_KEYS):
        return _refuse(
            FAILURE_EVIDENCE_FILE_MALFORMED,
            f"evidence file keys must be exactly {list(EVIDENCE_FILE_KEYS)}; "
            f"got {sorted(payload)}")
    for key in EVIDENCE_FILE_KEYS:
        value = payload[key]
        if not isinstance(value, str) or value == "":
            return _refuse(FAILURE_EVIDENCE_FILE_MALFORMED,
                           f"{key} must be a non-empty string")
    sha = payload["artifact_commit_sha"]
    if not _SHA_RE.fullmatch(sha):
        return _refuse(FAILURE_EVIDENCE_FILE_MALFORMED,
                       "artifact_commit_sha must be 40 lowercase hex characters")
    return EvidenceSelection(
        artifact_path=payload["artifact_path"],
        artifact_commit_sha=sha,
        quoted_text=payload["quoted_text"],
    )


def _run_git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """One git call: BYTES captured, the named timeout, ``cwd`` the evidence repo.

    A timeout or a missing git binary raises ``_GitProcessError``; the exit code
    is the caller's to interpret.
    """
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo_dir), capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise _GitProcessError(
            f"git {args[0]} timed out after {GIT_TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise _GitProcessError(f"git could not be run: {type(exc).__name__}") from exc


def _stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stderr.decode("utf-8", errors="replace").strip()


def _parse_reflog_instant(stdout: bytes) -> datetime | None:
    """``<ref>@{<iso-strict>}`` -> the aware instant; empty output -> None."""
    line = stdout.decode("utf-8").strip()
    if not line:
        return None
    marker = line.rfind("@{")
    if marker < 0 or not line.endswith("}"):
        raise _GitProcessError(f"unparseable reflog selector {line!r}")
    instant = datetime.fromisoformat(line[marker + 2:-1])
    if instant.utcoffset() is None:
        raise _GitProcessError(f"reflog instant carries no offset: {line!r}")
    return instant


def _budgeted_git(repo_dir: Path, deadline: float | None):
    """``_run_git`` bound to ``repo_dir`` under the replay budget, checked
    BEFORE each call starts (never by killing one mid-flight; each is already
    bounded by its own timeout)."""
    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        if deadline is not None and time.monotonic() >= deadline:
            raise _BudgetExhaustedError(REASON_WEB_BUDGET_EXHAUSTED)
        return _run_git(repo_dir, *args)
    return git


def _failure_detail(exc: Exception) -> str:
    """The ``tier2_unverifiable`` detail an exception reads as (E-6: every
    outcome is a value, never a raise)."""
    if isinstance(exc, _BudgetExhaustedError):
        return REASON_WEB_BUDGET_EXHAUSTED
    if isinstance(exc, _GitProcessError):
        return str(exc)
    return f"preflight could not complete: {type(exc).__name__}: {exc}"


def _ref_stage(git, repo_dir: Path) -> tuple[str | None, str | None]:
    """``REMOTE_REF``'s commit: ``(sha, None)``, or ``(None, detail)`` when it
    does not resolve.  A process failure RAISES (the caller maps it)."""
    ref = git("rev-parse", "--verify", "--quiet", f"{REMOTE_REF}^{{commit}}")
    if ref.returncode != 0:
        return None, (f"{REMOTE_REF} does not resolve in {repo_dir} "
                      f"(exit {ref.returncode}) {_stderr(ref)}".strip())
    return ref.stdout.decode("ascii").strip(), None


def _reflog_stage(git) -> tuple[datetime | None, str | None]:
    """The ref's last reflog instant: ``(instant or None, None)``, or
    ``(None, detail)`` on a git exit.  A process failure RAISES."""
    log = git("log", "-g", "-1", "--date=iso-strict", "--format=%gD",
              REMOTE_REF, "--")
    if log.returncode != 0:
        return None, f"git log -g exited {log.returncode}: {_stderr(log)}"
    return _parse_reflog_instant(log.stdout), None


@dataclass(frozen=True)
class RemoteRefResolution:
    """ONE read of ``REMOTE_REF`` in ``repo_dir`` -- one ``rev-parse`` and one
    reflog read -- for every row of ONE replay invocation (CHARC G-T9 item 2:
    a per-invocation resolution, never a cache; each invocation resolves
    afresh).  Each stage is its value or the ``tier2_unverifiable`` detail
    ``read_artifact_facts`` would have produced at that stage, applied at the
    SAME point of each row's read, so a row's verdict is the one a
    self-resolving read gives.  ``reflog_failure`` is None when the ref did
    not resolve (the reflog is never read then)."""

    repo_dir: Path
    resolved_sha: str | None
    ref_failure: str | None
    updated_at: datetime | None
    reflog_failure: str | None


def resolve_remote_ref(repo_dir: Path, *,
                       deadline: float | None = None) -> RemoteRefResolution:
    """Resolve ``REMOTE_REF`` once.  Never raises; budget-checked per call."""
    git = _budgeted_git(repo_dir, deadline)
    try:
        resolved, failure = _ref_stage(git, repo_dir)
    except Exception as exc:  # noqa: BLE001 -- E-6: a value, never a raise
        resolved, failure = None, _failure_detail(exc)
    if failure is not None:
        return RemoteRefResolution(repo_dir, None, failure, None, None)
    try:
        updated_at, reflog_failure = _reflog_stage(git)
    except Exception as exc:  # noqa: BLE001 -- E-6: a value, never a raise
        updated_at, reflog_failure = None, _failure_detail(exc)
    return RemoteRefResolution(repo_dir, resolved, None, updated_at, reflog_failure)


def read_artifact_facts(selection: EvidenceSelection, *, repo_dir: Path,
                        now_utc: datetime,
                        deadline: float | None = None,
                        resolution: RemoteRefResolution | None = None,
                        ) -> PreflightResult:
    """Read what git says about ``selection``.  Never raises.

    Order: the ref (process), the commit and its dates, the blob, the quoted
    text (byte-substring, then one line), ancestry, descendants, the reflog.
    ``deadline`` is the replay budget's (``None`` at write and on the CLI):
    once past it no further git call starts and the result is
    ``tier2_unverifiable`` with detail ``web_budget_exhausted``.
    ``resolution`` is a replay invocation's ONE ref read (G-T9 item 2): its
    stages stand in for the ``rev-parse`` and the reflog read at the same
    points; ``None`` (the write path, the preflight, a direct replay) reads
    the ref here, in the order above.  A resolution for another repo is
    refused, never used.
    """
    try:
        if now_utc.utcoffset() is None:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE, "now_utc must be offset-aware")
        sha = selection.artifact_commit_sha
        git = _budgeted_git(repo_dir, deadline)

        if resolution is None:
            resolved, failure = _ref_stage(git, repo_dir)
        elif resolution.repo_dir != repo_dir:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                           f"the ref resolution is for {resolution.repo_dir}, "
                           f"not {repo_dir}")
        else:
            resolved, failure = resolution.resolved_sha, resolution.ref_failure
        if failure is not None:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE, failure)

        dates = git("show", "-s", "--format=%aI%n%cI", f"{sha}^{{commit}}")
        if dates.returncode != 0:
            return _refuse(FAILURE_ARTIFACT_UNREADABLE,
                           f"commit {sha} is not readable: {_stderr(dates)}")
        date_lines = dates.stdout.decode("utf-8").split("\n")
        author_instant = datetime.fromisoformat(date_lines[0].strip())
        committer_instant = datetime.fromisoformat(date_lines[1].strip())

        blob = git("cat-file", "blob", f"{sha}:{selection.artifact_path}")
        if blob.returncode != 0:
            return _refuse(FAILURE_ARTIFACT_UNREADABLE,
                           f"{selection.artifact_path} at {sha} is not a readable file: "
                           f"{_stderr(blob)}")
        if selection.quoted_text.encode("utf-8") not in blob.stdout:
            return _refuse(FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT,
                           f"quoted_text is not a byte-substring of "
                           f"{selection.artifact_path} at {sha}")
        if "\n" in selection.quoted_text or "\r" in selection.quoted_text:
            return _refuse(FAILURE_QUOTED_TEXT_NOT_ONE_LINE,
                           "quoted_text must be ONE line (no line break)")

        anc = git("merge-base", "--is-ancestor", sha, resolved)
        if anc.returncode not in (0, 1):
            return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                           f"git merge-base exited {anc.returncode}: {_stderr(anc)}")
        is_ancestor = anc.returncode == 0

        descendant_count: int | None = None
        if is_ancestor:
            count = git("rev-list", "--count", f"{sha}..{resolved}")
            if count.returncode != 0:
                return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                               f"git rev-list exited {count.returncode}: {_stderr(count)}")
            descendant_count = int(count.stdout.decode("ascii").strip())

        if resolution is None:
            updated_at, failure = _reflog_stage(git)
        else:
            updated_at, failure = resolution.updated_at, resolution.reflog_failure
        if failure is not None:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE, failure)
        age = None if updated_at is None else int((now_utc - updated_at).total_seconds())

        return PreflightResult(
            facts=ArtifactFacts(
                selection=selection,
                author_instant=author_instant,
                committer_instant=committer_instant,
                is_ancestor=is_ancestor,
                resolved_remote_ref_sha=resolved,
                descendant_count=descendant_count,
                remote_ref_updated_at=updated_at,
                remote_ref_age_seconds=age,
            ),
            failure=None,
            detail="",
        )
    except Exception as exc:  # noqa: BLE001 -- E-6: the preflight never raises; fail closed
        return _refuse(FAILURE_TIER2_UNVERIFIABLE, _failure_detail(exc))


def run_preflight(evidence_file: Path | str, *, repo_dir: Path | None = None,
                  now_utc: datetime) -> PreflightResult:
    """Load the evidence file, then read the artifact facts.  Never raises."""
    try:
        loaded = load_evidence_selection(evidence_file)
        if isinstance(loaded, PreflightResult):
            return loaded
        return read_artifact_facts(
            loaded, repo_dir=EVIDENCE_REPO_DIR if repo_dir is None else repo_dir,
            now_utc=now_utc)
    except Exception as exc:  # noqa: BLE001 -- E-6: fail closed, never raise
        return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                       f"preflight could not complete: {type(exc).__name__}: {exc}")


# ==========================================================================
# THE CONJUNCTION (Task 5).  Reached ONLY through rung 9's escape seam on the
# correction path (E-16; A2-75 pins the caller).  READS the DB -- the cited
# candidate, its evaluation run, the run's one complete pipeline row and the
# epoch row -- and never writes, never opens a transaction.
# ==========================================================================

@dataclass(frozen=True)
class ConjunctionVerdict:
    """``admitted`` -> ``evidence`` is the seventh-column blob.  Otherwise the
    first failing criterion speaks: ``criterion`` 1-4 with its ``reason``
    (criterion 3 names its FIELD in both ``reason`` and ``field``), or
    ``criterion`` None with ``reason`` ``tier2_unverifiable`` and ``field``
    naming the trigger predicate whose service-side mirror refused the built
    blob (authorize-then-abort: the service refuses legibly first)."""

    admitted: bool
    criterion: int | None
    reason: str | None
    field: str | None
    evidence: dict | None


def render_price(value: float) -> str:
    """THE one rounding authority (S4.3a): Python's half-even ``round`` at 2 dp."""
    return f"{round(value, COMPARE_DP):.{COMPARE_DP}f}"


_TOKEN_CLASS = {"ticker": "A-Za-z0-9", "session": "0-9.", "numeral": "0-9."}


def find_token(text: str, token: str, *, kind: str) -> str | None:
    """``token`` as a WHOLE token of ``text``, or None.

    ``ticker`` is bounded by non-``[A-Za-z0-9]``; ``session`` and ``numeral``
    by non-``[0-9.]`` (RD's F13).  Containment proves MENTION, never
    exclusivity (AL2-2).
    """
    cls = _TOKEN_CLASS[kind]
    pattern = rf"(?<![{cls}]){re.escape(token)}(?![{cls}])"
    return token if re.search(pattern, text) else None


def _utc_text(instant: datetime) -> str:
    """An aware instant as naive-UTC ISO text with a literal ``Z``."""
    return instant.astimezone(UTC).replace(tzinfo=None).isoformat() + "Z"


def _local_naive_utc(raw: str) -> datetime:
    """A naive LOCAL pipeline stamp -> aware UTC, via THE conversion authority
    (``cohort_provenance_correction._to_utc_naive``; imported at call time
    because that module imports this one)."""
    from swing.trades.cohort_provenance_correction import _to_utc_naive

    parsed = datetime.fromisoformat(raw)
    if parsed.utcoffset() is not None:
        raise ValueError(f"pipeline stamp {raw!r} carries an offset")
    return _to_utc_naive(parsed).replace(tzinfo=UTC)


def _seconds(start: datetime, end: datetime) -> int | float:
    delta = (end - start).total_seconds()
    return int(delta) if delta == int(delta) else delta


def build_interval(*, fire_lo_raw: str, fire_hi_raw: str, author_instant: datetime,
                   barrier_armed_raw: str, read_at: str,
                   barrier_installed: bool) -> dict:
    """F2.I (I-1 + s1): five endpoints -- each its raw source value, its UTC
    rendering, clock domain and source column -- and the segments the ORDERED
    endpoints induce (RD's F2.I-NEG): ``fire`` [fire_lo, fire_hi];
    ``writer_absence_only`` [fire_hi, min(record_at, barrier_armed_at));
    ``match_only`` [record_at, barrier_armed_at); ``covered`` (or
    ``uncovered_barrier_absent``) [barrier_armed_at, read_at].  A segment of
    zero or negative length is NOT EMITTED -- so a record authored at or after
    the barrier has no ``match_only`` and ``record_position`` reads
    ``inside_coverage`` (else ``before_barrier``).  The durations are the
    SERVICE's record; SQL binds only the raws (AL2-9)."""
    fire_lo = _local_naive_utc(fire_lo_raw)
    fire_hi = _local_naive_utc(fire_hi_raw)
    record_at = author_instant.astimezone(UTC)
    barrier = datetime.fromisoformat(barrier_armed_raw)
    if barrier.utcoffset() is None:
        raise ValueError(f"barrier_armed_at {barrier_armed_raw!r} carries no offset")
    barrier = barrier.astimezone(UTC)
    read = datetime.fromisoformat(read_at)
    if read.utcoffset() is not None:
        raise ValueError(f"read_at {read_at!r} must be naive UTC")
    read = read.replace(tzinfo=UTC)
    utc = {
        "fire_lo": _utc_text(fire_lo), "fire_hi": _utc_text(fire_hi),
        "record_at": _utc_text(record_at), "barrier_armed_at": _utc_text(barrier),
        "read_at": read_at + "Z",
    }
    raws = {
        "fire_lo": fire_lo_raw, "fire_hi": fire_hi_raw,
        "record_at": author_instant.isoformat(), "barrier_armed_at": barrier_armed_raw,
        "read_at": read_at,
    }
    endpoints = {
        e: {"raw": raws[e], "utc": utc[e], "clock_domain": _ENDPOINT_DOMAIN_SOURCE[e][0],
            "source": _ENDPOINT_DOMAIN_SOURCE[e][1]}
        for e in INTERVAL_ENDPOINTS
    }
    instants = {"fire_lo": fire_lo, "fire_hi": fire_hi, "record_at": record_at,
                "barrier_armed_at": barrier, "read_at": read}
    # writer_absence_only ENDS at min(record_at, barrier_armed_at): one
    # formula, no branch (F2.I-NEG consequence (iv)).
    wao_end = "record_at" if record_at <= barrier else "barrier_armed_at"
    spans = (("fire", "fire_lo", "fire_hi"),
             ("writer_absence_only", "fire_hi", wao_end),
             ("match_only", "record_at", "barrier_armed_at"),
             (SEGMENT_COVERED if barrier_installed else SEGMENT_UNCOVERED_BARRIER_ABSENT,
              "barrier_armed_at", "read_at"))
    segments = [
        {"kind": kind, "from": utc[a], "to": utc[b],
         "seconds": _seconds(instants[a], instants[b])}
        for kind, a, b in spans
        if instants[b] > instants[a]
    ]
    position = (RECORD_POSITION_BEFORE_BARRIER if record_at < barrier
                else RECORD_POSITION_INSIDE_COVERAGE)
    return {"endpoints": endpoints, "segments": segments, "record_position": position}


def render_uncovered_window_prose(interval: dict) -> str:
    """F9: the service renders the prose; nobody types it.  A record authored
    inside coverage names itself (RD's F2.I-NEG consequence (ii))."""
    parts = []
    for seg in interval["segments"]:
        if seg["kind"] in ("writer_absence_only", "match_only"):
            parts.append(f"{seg['kind']} {seg['seconds'] / 86400:.2f} days "
                         f"({seg['from']} to {seg['to']})")
        elif seg["kind"] in (SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT):
            parts.append(f"{seg['kind']} from {seg['from']}")
    if interval["record_position"] == RECORD_POSITION_INSIDE_COVERAGE:
        parts.append("record authored inside coverage at "
                     f"{interval['endpoints']['record_at']['utc']}")
    return "; ".join(parts)


def _refused(criterion: int | None, reason: str,
             field: str | None = None) -> ConjunctionVerdict:
    return ConjunctionVerdict(admitted=False, criterion=criterion, reason=reason,
                              field=field, evidence=None)


def _criterion3(quoted: str, ctx: dict, author_date_et: str) -> tuple[str | None, dict]:
    """Ticker -> action_session -> pivot -> invalidation; the first miss speaks."""
    found: dict[str, str] = {}
    ticker = find_token(quoted, ctx["ticker"], kind="ticker")
    if ticker is None:
        return "ticker", found
    found["ticker"] = ticker
    session_iso = ctx["action_session_date"]
    session = find_token(quoted, session_iso, kind="session")
    if session is None and author_date_et[:4] == session_iso[:4]:
        # RD's F13 year rule: MM-DD borrows the ET author year, only when equal.
        session = find_token(quoted, session_iso[5:], kind="session")
    if session is None:
        return "action_session", found
    found["action_session"] = session
    pivot = find_token(quoted, render_price(ctx["pivot"]), kind="numeral")
    if pivot is None:
        return "pivot", found
    found["pivot"] = pivot
    invalidation = find_token(quoted, render_price(ctx["initial_stop"]), kind="numeral")
    if invalidation is None:
        return "invalidation", found
    found["invalidation"] = invalidation
    return None, found


def _read_context(conn: sqlite3.Connection, candidate_id: int) -> dict:
    """SELECT-only reads of the rows the conjunction and the trigger bind."""
    from swing.data.repos.candidates_immutability_epoch import epoch_boundary
    from swing.data.repos.pipeline import evaluation_run_persistence_bound

    row = conn.execute(
        "SELECT ca.ticker, ca.pivot, ca.initial_stop, ca.evaluation_run_id, "
        "er.run_ts, er.action_session_date FROM candidates ca "
        "JOIN evaluation_runs er ON er.id = ca.evaluation_run_id WHERE ca.id = ?",
        (candidate_id,)).fetchone()
    if row is None:
        raise LookupError(f"candidate {candidate_id} (or its evaluation run) does not exist")
    bound = evaluation_run_persistence_bound(conn, evaluation_run_id=int(row[3]))
    armed = None
    if epoch_boundary(conn) is not None:
        armed = conn.execute(
            "SELECT applied_at FROM candidates_immutability_epoch WHERE epoch_id = 1"
        ).fetchone()[0]
    return {
        "ticker": row[0], "pivot": row[1], "initial_stop": row[2],
        "evaluation_run_id": int(row[3]), "run_ts": row[4],
        "action_session_date": row[5],
        "finished_ts": None if bound is None else bound.finished_ts,
        "barrier_armed_at": armed,
    }


def evaluate_conjunction(conn: sqlite3.Connection, facts: ArtifactFacts, *,
                         candidate_id: int, fill_session: date, read_at: str,
                         barrier_installed: bool) -> ConjunctionVerdict:
    """S12.1 #3: ADMIT iff ALL FOUR hold, evaluated in order; the first failure speaks.

    (1) the artifact commit is an ancestor of ``REMOTE_REF``; (2) the author
    instant's America/New_York DATE strictly precedes ``fill_session`` (F7;
    the committer instant is never verdict-bearing); (3) the quoted text
    contains the cited candidate's ticker, action session, pivot and
    initial_stop as service-rendered whole tokens (F13); (4) the record is
    STRICTLY after the fire's upper bound ``pipeline_runs.finished_ts`` (F6 ii
    as amended by RD's G-U1: the fire bracket is CLOSED on both ends and
    ``finished_ts`` is second-truncated, so equality is order-indeterminate).
    On admit the seventh-column blob is built and checked against every
    trigger predicate's service-side mirror before it is returned.
    """
    ctx = _read_context(conn, candidate_id)

    # Criterion 1.
    if not facts.is_ancestor:
        return _refused(1, REASON_NOT_ANCESTOR)

    # Criterion 2 -- the ET DATE of the AUTHOR instant, at the session grain.
    author_date_et = facts.author_instant.astimezone(ET_ZONE).date()
    if author_date_et == fill_session:
        return _refused(2, REASON_RECORDED_ON_FILL_SESSION)
    if author_date_et > fill_session:
        return _refused(2, REASON_RECORDED_AFTER_FILL_SESSION)

    # Criterion 3.
    missing, found = _criterion3(facts.selection.quoted_text, ctx,
                                 author_date_et.isoformat())
    if missing is not None:
        return _refused(3, missing, missing)

    # Criterion 4 -- the fire is a CLOSED BRACKET [run_ts, finished_ts] (R8-01;
    # RD's G-U1): < fire_lo negative; fire_lo..fire_hi inclusive indeterminate.
    try:
        if ctx["run_ts"] is None or ctx["finished_ts"] is None:
            raise ValueError("fire bracket unresolvable")
        fire_lo = _local_naive_utc(ctx["run_ts"])
        fire_hi = _local_naive_utc(ctx["finished_ts"])
    except (TypeError, ValueError):
        return _refused(4, REASON_WINDOW_INDETERMINATE)
    record_at = facts.author_instant.astimezone(UTC)
    if record_at < fire_lo:
        return _refused(4, REASON_WINDOW_NEGATIVE)
    if record_at <= fire_hi:
        return _refused(4, REASON_WINDOW_INDETERMINATE)

    # ADMIT: build the blob, then run every trigger predicate's mirror.
    try:
        blob = _build_frozen_value_blob(
            facts, ctx, found=found, author_date_et=author_date_et.isoformat(),
            fill_session=fill_session, read_at=read_at,
            barrier_installed=barrier_installed)
    except (TypeError, ValueError):
        return _refused(None, FAILURE_TIER2_UNVERIFIABLE, "blob_unbuildable")
    failed = _first_failing_mirror(blob, ctx, read_at=read_at, fill_session=fill_session)
    if failed is not None:
        return _refused(None, FAILURE_TIER2_UNVERIFIABLE, failed)
    return ConjunctionVerdict(admitted=True, criterion=None, reason=None, field=None,
                              evidence=blob)


def _build_frozen_value_blob(facts: ArtifactFacts, ctx: dict, *, found: dict,
                             author_date_et: str, fill_session: date, read_at: str,
                             barrier_installed: bool) -> dict:
    """The section-2 blob.  Every value is COMPUTED except the three selection keys."""
    if ctx["barrier_armed_at"] is None:
        raise ValueError("the candidates_immutability_epoch row is absent")
    interval = build_interval(
        fire_lo_raw=ctx["run_ts"], fire_hi_raw=ctx["finished_ts"],
        author_instant=facts.author_instant, barrier_armed_raw=ctx["barrier_armed_at"],
        read_at=read_at, barrier_installed=barrier_installed)
    sel = facts.selection
    blob = {
        "evidence_version": FROZEN_VALUE_EVIDENCE_VERSION,
        "derivation_version": FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION,
        "ruling_citation": RULING_CITATION,
        "verification_method": VERIFICATION_METHOD,
        "evaluated_at": read_at,
        "artifact_path": sel.artifact_path,
        "artifact_commit_sha": sel.artifact_commit_sha,
        "quoted_text": sel.quoted_text,
        "quoted_ticker_text": found["ticker"],
        "quoted_action_session_text": found["action_session"],
        "quoted_pivot_text": found["pivot"],
        "quoted_invalidation_text": found["invalidation"],
        "live_pivot_raw": ctx["pivot"],
        "live_invalidation_raw": ctx["initial_stop"],
        "pivot_equal_at_dp": 1,
        "invalidation_equal_at_dp": 1,
        "compare_dp": COMPARE_DP,
        "author_instant": facts.author_instant.isoformat(),
        "author_date_et": author_date_et,
        "committer_instant": facts.committer_instant.isoformat(),
        "fill_session_date": fill_session.isoformat(),
        "resolved_remote_ref_sha": facts.resolved_remote_ref_sha,
        "descendant_count": facts.descendant_count,
        "remote_ref_updated_at": (None if facts.remote_ref_updated_at is None
                                  else facts.remote_ref_updated_at.isoformat()),
        "remote_ref_age_seconds": facts.remote_ref_age_seconds,
        "anchor_strength": ANCHOR_STRENGTH,
        "time_anchor_residual": TIME_ANCHOR_RESIDUAL,
        "interval": interval,
        "uncovered_window_prose": render_uncovered_window_prose(interval),
    }
    return {k: blob[k] for k in FROZEN_VALUE_BLOB_KEYS}


# --------------------------------------------------------------------------
# AUTHORIZE-THEN-ABORT (brief 4.4): every ``-- TIER2-PREDICATE`` in the HEAD
# citation trigger names a service-side check.  The blob predicates are
# mirrored below on the BUILT blob, so the service refuses -- legibly, as
# ``tier2_unverifiable`` naming the predicate -- anything the trigger would
# abort.  The three rung-9 predicates are checked where rung 9 lives.  A2-60
# asserts the id set both ways against the migration text.
# --------------------------------------------------------------------------

def _is_text(v: object) -> bool:
    return isinstance(v, str)


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v: object) -> bool:
    if isinstance(v, float):
        return math.isfinite(v)
    return _is_int(v)


def _tp_seventh_present(blob, ctx, **_):
    return isinstance(blob, dict)


def _tp_blob_closed(blob, ctx, **_):
    return set(blob) == set(FROZEN_VALUE_BLOB_KEYS)


def _tp_evidence_version(blob, ctx, **_):
    return blob["evidence_version"] == FROZEN_VALUE_EVIDENCE_VERSION


def _tp_derivation_version(blob, ctx, **_):
    """TYPE ONLY, as the trigger: the value is the replay's to compare."""
    return _is_text(blob["derivation_version"])


_ATTESTATION_TEXT_KEYS = (
    "ruling_citation", "verification_method", "artifact_path", "author_instant",
    "committer_instant", "resolved_remote_ref_sha", "anchor_strength",
    "time_anchor_residual", "uncovered_window_prose")


def _tp_attestation_texts(blob, ctx, **_):
    return all(_is_text(blob[k]) for k in _ATTESTATION_TEXT_KEYS)


def _tp_evaluated_at_is_applied_at(blob, ctx, *, read_at, **_):
    return _is_text(blob["evaluated_at"]) and blob["evaluated_at"] == read_at


def _tp_artifact_commit_sha_shape(blob, ctx, **_):
    return _is_text(blob["artifact_commit_sha"]) and bool(
        _SHA_RE.fullmatch(blob["artifact_commit_sha"]))


def _tp_quoted_text_one_line(blob, ctx, **_):
    q = blob["quoted_text"]
    return _is_text(q) and q != "" and "\n" not in q and "\r" not in q


def _contained(blob, key):
    return _is_text(blob[key]) and blob[key] in blob["quoted_text"]


def _tp_quoted_ticker(blob, ctx, **_):
    return (_contained(blob, "quoted_ticker_text")
            and blob["quoted_ticker_text"] == ctx["ticker"])


def _tp_quoted_action_session(blob, ctx, **_):
    s, iso = blob["quoted_action_session_text"], ctx["action_session_date"]
    return _contained(blob, "quoted_action_session_text") and (
        s == iso or (s == iso[5:] and blob["author_date_et"][:4] == iso[:4]))


def _tp_quoted_pivot(blob, ctx, **_):
    return _contained(blob, "quoted_pivot_text")


def _tp_quoted_invalidation(blob, ctx, **_):
    return _contained(blob, "quoted_invalidation_text")


def _tp_live_pivot_raw(blob, ctx, **_):
    return _is_number(blob["live_pivot_raw"]) and blob["live_pivot_raw"] == ctx["pivot"]


def _tp_live_invalidation_raw(blob, ctx, **_):
    return (_is_number(blob["live_invalidation_raw"])
            and blob["live_invalidation_raw"] == ctx["initial_stop"])


def _tp_equal_at_dp_verdicts(blob, ctx, **_):
    return all(_is_int(blob[k]) and blob[k] == 1
               for k in ("pivot_equal_at_dp", "invalidation_equal_at_dp"))


def _tp_compare_dp(blob, ctx, **_):
    return _is_int(blob["compare_dp"]) and blob["compare_dp"] == COMPARE_DP


def _tp_fill_session_date(blob, ctx, *, fill_session, **_):
    return blob["fill_session_date"] == fill_session.isoformat()


def _tp_author_date_before_fill(blob, ctx, *, fill_session, **_):
    d = blob["author_date_et"]
    if not (_is_text(d) and len(d) == 10):
        return False
    return date.fromisoformat(d).isoformat() == d and d < fill_session.isoformat()


def _tp_remote_ref_attestation(blob, ctx, **_):
    return (_is_int(blob["descendant_count"])
            and (blob["remote_ref_updated_at"] is None
                 or _is_text(blob["remote_ref_updated_at"]))
            and (blob["remote_ref_age_seconds"] is None
                 or _is_int(blob["remote_ref_age_seconds"])))


def _tp_interval_closed(blob, ctx, **_):
    iv = blob["interval"]
    return (isinstance(iv, dict)
            and set(iv) == {"endpoints", "segments", "record_position"}
            and _is_text(iv["record_position"])
            and iv["record_position"] in RECORD_POSITIONS
            and isinstance(iv["endpoints"], dict)
            and set(iv["endpoints"]) == set(INTERVAL_ENDPOINTS))


def _endpoint_ok(blob, name, raw_expected):
    ep = blob["interval"]["endpoints"].get(name)
    domain, source = _ENDPOINT_DOMAIN_SOURCE[name]
    return (isinstance(ep, dict) and set(ep) == set(_ENDPOINT_KEYS)
            and _is_text(ep["raw"]) and ep["raw"] == raw_expected
            and _is_text(ep["utc"]) and ep["clock_domain"] == domain
            and ep["source"] == source)


def _tp_interval_endpoint_fire_lo(blob, ctx, **_):
    return _endpoint_ok(blob, "fire_lo", ctx["run_ts"])


def _tp_interval_endpoint_fire_hi(blob, ctx, **_):
    return _endpoint_ok(blob, "fire_hi", ctx["finished_ts"])


def _tp_interval_endpoint_record_at(blob, ctx, **_):
    return _endpoint_ok(blob, "record_at", blob["author_instant"])


def _tp_interval_endpoint_barrier_armed_at(blob, ctx, **_):
    return _endpoint_ok(blob, "barrier_armed_at", ctx["barrier_armed_at"])


def _tp_interval_endpoint_read_at(blob, ctx, *, read_at, **_):
    return _endpoint_ok(blob, "read_at", read_at)


def _parse_utc_z(text: str) -> datetime:
    if not (_is_text(text) and text.endswith("Z")):
        raise ValueError(f"not a UTC-Z instant: {text!r}")
    parsed = datetime.fromisoformat(text[:-1])
    if parsed.utcoffset() is not None:
        raise ValueError(f"not a UTC-Z instant: {text!r}")
    return parsed


def _tp_interval_segment_order(blob, ctx, **_):
    """The trigger twin asserts the ORDER only (it never reads a utc value,
    R8-03); this service check adds what SQL cannot: ``match_only`` present
    IFF record_at.utc < barrier_armed_at.utc (RD's F2.I-NEG (i)), and every
    emitted segment has seconds > 0."""
    segs = blob["interval"]["segments"]
    if not (isinstance(segs, list) and len(segs) in (3, 4)):
        return False
    kinds = [s.get("kind") if isinstance(s, dict) else None for s in segs]
    tail = (SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT)
    if kinds[:2] != list(SEGMENT_KINDS[:2]) or kinds[-1] not in tail:
        return False
    has_match_only = len(segs) == 4
    if has_match_only and kinds[2] != SEGMENT_KINDS[2]:
        return False
    if not all(set(s) == {"kind", "from", "to", "seconds"} and _is_text(s["from"])
               and _is_text(s["to"]) and _is_number(s["seconds"]) and s["seconds"] > 0
               for s in segs):
        return False
    endpoints = blob["interval"]["endpoints"]
    record_at = _parse_utc_z(endpoints["record_at"]["utc"])
    barrier = _parse_utc_z(endpoints["barrier_armed_at"]["utc"])
    return has_match_only == (record_at < barrier)


def _tp_record_position_consistent(blob, ctx, **_):
    """CHARC's G-NEG belt, the service twin: 'before_barrier' iff length 4,
    'inside_coverage' iff length 3."""
    iv = blob["interval"]
    n = len(iv["segments"])
    return ((n == 4 and iv["record_position"] == RECORD_POSITION_BEFORE_BARRIER)
            or (n == 3 and iv["record_position"] == RECORD_POSITION_INSIDE_COVERAGE))


# The blob predicates' mirrors, in the trigger's order.  A tuple of NAMED
# functions so the A2-60 walk sees each one referenced from evaluate_conjunction.
_BLOB_MIRRORS = (
    _tp_seventh_present, _tp_blob_closed, _tp_evidence_version, _tp_derivation_version,
    _tp_attestation_texts,
    _tp_evaluated_at_is_applied_at, _tp_artifact_commit_sha_shape,
    _tp_quoted_text_one_line, _tp_quoted_ticker, _tp_quoted_action_session,
    _tp_quoted_pivot, _tp_quoted_invalidation, _tp_live_pivot_raw,
    _tp_live_invalidation_raw, _tp_equal_at_dp_verdicts, _tp_compare_dp,
    _tp_fill_session_date, _tp_author_date_before_fill, _tp_remote_ref_attestation,
    _tp_interval_closed, _tp_interval_endpoint_fire_lo, _tp_interval_endpoint_fire_hi,
    _tp_interval_endpoint_record_at, _tp_interval_endpoint_barrier_armed_at,
    _tp_interval_endpoint_read_at, _tp_interval_segment_order,
    _tp_record_position_consistent,
)

# (predicate id in the HEAD citation trigger, "module:service check").  The
# three rung-9 predicates resolve in the module where rung 9 lives (the
# escape seam is Task 6's); every other id is a blob mirror above.
TIER2_TRIGGER_PREDICATES: tuple[tuple[str, str], ...] = (
    ("rung9_escaped_verdict", "swing.trades.latched_origin:_authorization_block"),
    ("rung9_pre_barrier_input", "swing.trades.latched_origin:authorize_accepted_order"),
    ("rung9_pre_barrier_candidate",
     "swing.data.repos.candidates_immutability_epoch:freeze_tier_for_candidate"),
    *((m.__name__.removeprefix("_tp_"), f"{__name__}:{m.__name__}") for m in _BLOB_MIRRORS),
)


def _first_failing_mirror(blob: dict, ctx: dict, *, read_at: str,
                          fill_session: date) -> str | None:
    """The first trigger predicate the built blob would FAIL, or None."""
    for mirror in _BLOB_MIRRORS:
        try:
            ok = mirror(blob, ctx, read_at=read_at, fill_session=fill_session)
        except (KeyError, TypeError, AttributeError, ValueError):
            ok = False
        if not ok:
            return mirror.__name__.removeprefix("_tp_")
    return None


# ==========================================================================
# THE READ-TIME REPLAY (Task 9).  RD's F10: the stored tier is an ATTESTATION
# of what was verified at write time; the VERDICT is computed at read time by
# THIS function, and every consumer calls it (never ``admission_tier``).
# CHARC's F10-shape: the SAME evaluation as the write path -- the same
# ``read_artifact_facts`` under the same timeout, the same
# ``evaluate_conjunction`` -- so the two cannot drift.  P37: ``conn`` is a
# read-only connection; the replay opens NO transaction and writes nothing.
# ==========================================================================

@dataclass(frozen=True)
class ReplayVerdict:
    """One row's read-time verdict.  ``reason`` is None iff ``ADMIT``.
    ``resolved_origin_main_sha`` is None when git never resolved the ref;
    ``barrier_installed_at_read`` is None when the row was never replayed (an
    exhausted budget).  ``derivation_observation`` is
    ``derivation_version_moved (stored X, current Y)`` when the row's stored
    ``derivation_version`` is not the current constant, else None: CONTEXT
    beside the verdict, never the verdict (G-T7F-AMEND).  Nothing here is
    persisted."""

    verdict: str
    reason: str | None
    evaluated_at: str
    resolved_origin_main_sha: str | None
    barrier_installed_at_read: bool | None
    derivation_observation: str | None = None


_ABSENT = object()


def _at_path(blob: object, dotted: str) -> object:
    node = blob
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return _ABSENT
        node = node[part]
    return node


def _stored_selection(stored: object) -> EvidenceSelection | None:
    """The row's own selection (F9) out of its stored blob, or None."""
    if not isinstance(stored, dict):
        return None
    values = [stored.get(k) for k in EVIDENCE_FILE_KEYS]
    if not all(isinstance(v, str) and v for v in values):
        return None
    if not _SHA_RE.fullmatch(values[1]):
        return None
    return EvidenceSelection(*values)


def _fill_session_of(value: object) -> date | None:
    """The TEXT -> ``date`` boundary: EXTENDED ``YYYY-MM-DD`` round-trip, or None
    (a non-string, an unparseable value and a week date alike)."""
    try:
        parsed = date.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed.isoformat() == value else None


def replay_verdict(conn: sqlite3.Connection, row, *, now: datetime,
                   repo_dir: Path | None = None,
                   deadline: float | None = None,
                   resolution: RemoteRefResolution | None = None) -> ReplayVerdict:
    """Re-derive ``row``'s tier-2 verdict at read time.  Never raises for a
    tier-2 row: ignorance is ``tier2_unverifiable``, never ADMIT.

    Order: the barrier observation and the caller-held-transaction refusal
    (before any git) -> the stored selection -> the fill session (TEXT ->
    date) -> ``read_artifact_facts`` (a PROCESS failure is unverifiable; git
    answering negatively is stale, E-10) -> the stored ``author_instant``
    against git's -> ``evaluate_conjunction`` against the CURRENT rows (a
    refusal is stale naming the criterion) -> the ``VERDICT_BEARING_KEYS`` of
    the recomputed blob against the stored blob (the first differing key in
    sorted order is named ``<key>_mismatch``).  Recorded-only keys --
    descendant count, ref age, the resolved sha, the committer instant, the
    segments -- are never compared (doctrine #6, E-15).  The barrier state is
    an observation returned beside the verdict (A2-88), and it is the
    ``barrier_installed`` the recomputation uses.

    A moved DERIVATION version is CONTEXT DRIFT, never divergence
    (G-T7F-AMEND, RD's doctrine #6): the verdict follows the RECOMPUTATION
    under the current code -- every key equal is ADMIT -- and the move is
    returned beside it as ``derivation_observation``.  When the verdict is
    stale, the moved version is appended to the reason line, so a code change
    can never read as an evidence change.  ``deadline`` is the
    caller's budget (``tier2_cohort_exclusions``); ``None`` waits out every
    call's own timeout.  ``resolution`` is the invocation's ONE ref read
    (``tier2_cohort_exclusions`` / ``read_provenance_corrections``, CHARC
    G-T9 item 2); ``None`` -- a direct call -- resolves the ref here.
    """
    from swing.data.models import PROVENANCE_ADMISSION_TIER_LATCH_TIER2
    from swing.data.repos.candidates_immutability_epoch import barrier_installed

    if row.admission_tier != PROVENANCE_ADMISSION_TIER_LATCH_TIER2:
        raise ValueError(
            f"replay_verdict reads tier-2 rows only; correction "
            f"{row.provenance_correction_id} is {row.admission_tier!r}")
    evaluated_at = now.isoformat()
    sha: str | None = None
    barrier: bool | None = None
    observation: str | None = None

    def verdict(kind: str, reason: str | None) -> ReplayVerdict:
        if kind == VERDICT_STALE and observation is not None:
            reason = observation if reason is None else f"{reason}; {observation}"
        return ReplayVerdict(verdict=kind, reason=reason, evaluated_at=evaluated_at,
                             resolved_origin_main_sha=sha,
                             barrier_installed_at_read=barrier,
                             derivation_observation=observation)

    try:
        barrier = barrier_installed(conn)
        if conn.in_transaction:
            return verdict(VERDICT_UNVERIFIABLE, REASON_CALLER_HOLDS_TRANSACTION)
        try:
            stored = json.loads(row.cited_frozen_value_evidence_json)
        except (TypeError, ValueError):
            stored = None
        if isinstance(stored, dict):
            held = stored.get("derivation_version")
            current = FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
            if held != current:
                observation = f"derivation_version_moved (stored {held}, current {current})"
        selection = _stored_selection(stored)
        if selection is None:
            return verdict(VERDICT_STALE, REASON_STORED_EVIDENCE_MALFORMED)
        fill_session = _fill_session_of(row.entry_fill_session_date)
        if fill_session is None:
            return verdict(VERDICT_STALE, REASON_FILL_SESSION_MALFORMED)

        read = read_artifact_facts(
            selection, repo_dir=EVIDENCE_REPO_DIR if repo_dir is None else repo_dir,
            now_utc=now, deadline=deadline, resolution=resolution)
        if read.failure is not None or read.facts is None:
            if read.failure in (None, FAILURE_TIER2_UNVERIFIABLE):
                return verdict(VERDICT_UNVERIFIABLE,
                               read.detail or FAILURE_TIER2_UNVERIFIABLE)
            return verdict(VERDICT_STALE, read.failure)
        facts = read.facts
        sha = facts.resolved_remote_ref_sha
        if stored.get("author_instant") != facts.author_instant.isoformat():
            return verdict(VERDICT_STALE, REASON_AUTHOR_INSTANT_CHANGED)

        conj = evaluate_conjunction(
            conn, facts, candidate_id=row.cited_candidate_id,
            fill_session=fill_session, read_at=row.applied_at,
            barrier_installed=barrier)
        if not conj.admitted or conj.evidence is None:
            if conj.criterion is None:
                return verdict(VERDICT_UNVERIFIABLE, conj.field or conj.reason)
            return verdict(VERDICT_STALE, f"criterion {conj.criterion}: {conj.reason}")
        # Compare in the STORED blob's domain: the recomputed blob through the
        # same JSON round trip the column went through.
        recomputed = json.loads(json.dumps(conj.evidence))
        for key in sorted(VERDICT_BEARING_KEYS):
            if _at_path(recomputed, key) != _at_path(stored, key):
                return verdict(VERDICT_STALE, f"{key}_mismatch")
        return verdict(VERDICT_ADMIT, None)
    except Exception as exc:  # noqa: BLE001 -- ignorance reads unverifiable, never ADMIT
        return verdict(VERDICT_UNVERIFIABLE,
                       f"replay could not complete: {type(exc).__name__}: {exc}")


def _tier2_rows(conn: sqlite3.Connection) -> list:
    """Every ``latch_ladder_tier2`` correction row (one SELECT; no transaction)."""
    from swing.data.models import PROVENANCE_ADMISSION_TIER_LATCH_TIER2
    from swing.data.repos.provenance_corrections import list_provenance_corrections

    return [r for r in list_provenance_corrections(conn)
            if r.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2]


@dataclass(frozen=True)
class Tier2CohortRead:
    """One invocation's read of every tier-2 row, by ``trade_id`` (CHARC
    G-T7FE item C: a NAMED result, never a bare tuple).

    ``exclusions`` is exactly the non-ADMIT set: the rows a cohort read must
    NOT count, each with its verdict and reason (RD's F10 sub-ruling).
    ``observations`` is every ADMITTED row whose verdict carries a non-empty
    observation (today: ``derivation_version_moved``) -- counted, and
    rendered beside the count.  A reader COUNTS from ``exclusions`` only; the
    count logic never reads ``observations``.  Nothing here is persisted."""

    exclusions: dict[int, ReplayVerdict]
    observations: dict[int, ReplayVerdict]

    def excluded_among(self, trade_ids) -> tuple[tuple[int, str, str | None], ...]:
        """``(trade_id, verdict, reason)`` for the ids this read excludes, in
        trade-id order -- the NAMES a cohort's N owes its reader."""
        return tuple((tid, self.exclusions[tid].verdict, self.exclusions[tid].reason)
                     for tid in sorted({t for t in trade_ids if t is not None})
                     if tid in self.exclusions)

    def observed_among(self, trade_ids) -> tuple[tuple[int, str], ...]:
        """``(trade_id, observation)`` for the counted ids carrying one."""
        out: list[tuple[int, str]] = []
        for tid in sorted({t for t in trade_ids if t is not None}):
            v = self.observations.get(tid)
            if v is not None and v.derivation_observation:
                out.append((tid, v.derivation_observation))
        return tuple(out)


def tier2_cohort_lines(excluded, observed) -> tuple[str, ...]:
    """The NAMED lines one cohort renders on the four named surfaces: one per
    excluded trade (verdict + reason), one per counted trade carrying an
    observation.  ASCII (they reach the CLI)."""
    return (
        tuple(f"tier-2 not counted: trade {tid} {verdict} ({reason})"
              for tid, verdict, reason in excluded)
        + tuple(f"tier-2 counted with observation: trade {tid} ({observation})"
                for tid, observation in observed))


def tier2_count_marker(excluded, *, see: str) -> str | None:
    """RD G-T10-2: the compact marker beside a SHOWN cohort N -- the count and
    the canonical surface to open; ``unverifiable`` is never merged with
    ``excluded``; None at zero exclusions."""
    unverifiable = sum(1 for _tid, verdict, _r in excluded
                       if verdict == VERDICT_UNVERIFIABLE)
    stale = len(excluded) - unverifiable
    parts = ([f"{stale} excluded"] if stale else []) + (
        [f"{unverifiable} unverifiable"] if unverifiable else [])
    return f"({', '.join(parts)}: see {see})" if parts else None


def tier2_cohort_exclusions(conn: sqlite3.Connection, *, now: datetime,
                            repo_dir: Path | None = None,
                            budget_seconds: float | None = None,
                            ) -> Tier2CohortRead:
    """Every tier-2 row's read-time verdict for a cohort read, by ``trade_id``:
    the rows it must NOT count, each with its verdict and reason (RD's F10
    sub-ruling: excluded and NAMED), and the admitted rows carrying an
    observation (CHARC G-T7FE item C).  Its callers are exactly the four
    cohort readers (CHARC G-T9 item 1, G-T10-1).

    ONE ``replay_verdict`` per tier-2 row per call, and ONE resolution of the
    remote ref per call (CHARC G-T9 item 2: one ``rev-parse`` + one reflog
    read, passed into every row's replay; the per-row git calls stay per row,
    each row citing its own commit).  Nothing survives the call -- there is
    no cache across calls (F10-shape: a cached verdict is a stored grade),
    and under a caller-held transaction no resolution runs (each row refuses
    before git, S12.1 #9).  ``budget_seconds`` is a TOTAL wall-clock
    budget (CHARC R4.2 ruling 1) checked before each git call starts; past
    it, every row not yet verdicted reads ``tier2_unverifiable`` /
    ``web_budget_exhausted`` -- excluded and named, never admitted.  The rows
    are collected by one SELECT before any git runs; zero tier-2 rows make
    zero git calls.
    """
    deadline = None if budget_seconds is None else time.monotonic() + budget_seconds
    rows = _tier2_rows(conn)
    if not rows:
        return Tier2CohortRead(exclusions={}, observations={})
    repo = EVIDENCE_REPO_DIR if repo_dir is None else repo_dir
    resolution = (None if conn.in_transaction
                  else resolve_remote_ref(repo, deadline=deadline))
    excluded: dict[int, ReplayVerdict] = {}
    observed: dict[int, ReplayVerdict] = {}
    for row in rows:
        if deadline is not None and time.monotonic() >= deadline:
            result = ReplayVerdict(
                verdict=VERDICT_UNVERIFIABLE, reason=REASON_WEB_BUDGET_EXHAUSTED,
                evaluated_at=now.isoformat(), resolved_origin_main_sha=None,
                barrier_installed_at_read=None)
        else:
            result = replay_verdict(conn, row, now=now, repo_dir=repo,
                                    deadline=deadline, resolution=resolution)
        if result.verdict != VERDICT_ADMIT:
            excluded[row.trade_id] = result
        elif result.derivation_observation:
            observed[row.trade_id] = result
    return Tier2CohortRead(exclusions=excluded, observations=observed)


# ==========================================================================
# THE EVIDENCE-SIDE DEPENDENCY PIN (CHARC G-T7 Q2, as corrected by G-T7F).
# ``FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION`` is BOUND to a digest of every
# function the seventh-column blob is a function of, through the pattern
# ``DERIVATION_RULE_HISTORY`` runs for ``_derive``: an append-only
# ``(version, digest)`` history whose CURRENT pair a test asserts, so a
# behaviour edit to any member without a version bump FAILS THE SUITE
# (22A-R14-01's lesson, met on this arc's own version constant).
#
# MEMBERSHIP IS COMPUTED, NOT HAND-LISTED.  The ROOTS below are the members the
# rulings name (G-T7 Q2's six + G-T7F item 2's ``read_artifact_facts``); the
# digest covers their STATIC REFERENCE CLOSURE: every module-level function,
# class and constant a member names, followed transitively, including into
# other ``swing`` modules (a module-level ``from swing... import`` or one
# inside a function body).  Stdlib and third-party names are outside the walk.
# The walk fails LOUD on a name it cannot place.
#
# THE DIGEST HASHES BEHAVIOUR, NOT TEXT (G-T7F item 1).  A function or class
# contributes its ``ast.dump`` with every docstring node removed; a constant
# contributes the ``ast.dump`` of its assigned value.  Comments never reach the
# AST and ``ast.dump`` carries no line numbers, so a docstring, comment or
# layout edit moves nothing -- D59's lesson (comments are not behaviour) on the
# one instrument that would otherwise force a version bump over prose.
# ==========================================================================

FROZEN_VALUE_EVIDENCE_DIGEST_ROOTS: tuple[str, ...] = (
    "swing.trades.cohort_provenance_correction:_to_utc_naive",
    f"{__name__}:build_interval",
    f"{__name__}:render_price",
    f"{__name__}:find_token",
    f"{__name__}:evaluate_conjunction",
    f"{__name__}:_build_frozen_value_blob",
    f"{__name__}:read_artifact_facts",
)

# The derivation version is what the digest PINS, never an input to it.  The
# GRAMMAR version is an ordinary member: the builder emits it.
_DIGEST_EXCLUDED: frozenset[str] = frozenset(
    {f"{__name__}:FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION"})


def _module_definitions(module: object) -> tuple[dict[str, object], dict[str, str]]:
    """``(name -> module-level AST node, name -> "swing.module:attr")`` for one
    module: its own definitions, and the names it imports from ``swing``."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    defs: dict[str, object] = {}
    imported: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    defs[t.id] = node
        elif (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
              and node.module.split(".")[0] == "swing"):
            for alias in node.names:
                imported[alias.asname or alias.name] = f"{node.module}:{alias.name}"
    return defs, imported


def _member_body(node: object) -> str:
    """One member's digested BEHAVIOUR: a function's or class's ``ast.dump``
    with every docstring node removed (its own and any nested definition's),
    or a constant's assigned value's ``ast.dump``.  Works on a COPY; the
    parsed tree is never mutated."""
    import ast
    import copy

    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        if node.value is None:
            raise LookupError("digest closure: an annotation-only name has no value")
        return ast.dump(node.value)
    clone = copy.deepcopy(node)
    for sub in ast.walk(clone):  # type: ignore[arg-type]
        if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and sub.body and isinstance(sub.body[0], ast.Expr)
                and isinstance(sub.body[0].value, ast.Constant)
                and isinstance(sub.body[0].value.value, str)):
            sub.body = sub.body[1:]
    return ast.dump(clone)  # type: ignore[arg-type]


def frozen_value_evidence_digest_parts() -> list[tuple[str, str, str]]:
    """``(kind, "module:attr", body)`` for every member of the closure, sorted by
    spec.  The body is ``_member_body``'s -- behaviour, never text."""
    import ast
    import importlib

    cache: dict[str, tuple[dict[str, object], dict[str, str]]] = {}
    seen: set[str] = set()
    parts: list[tuple[str, str, str]] = []
    stack = list(FROZEN_VALUE_EVIDENCE_DIGEST_ROOTS)
    while stack:
        spec = stack.pop()
        if spec in seen or spec in _DIGEST_EXCLUDED:
            continue
        seen.add(spec)
        mod_name, attr = spec.split(":")
        module = importlib.import_module(mod_name)
        if mod_name not in cache:
            cache[mod_name] = _module_definitions(module)
        defs, imported = cache[mod_name]
        node = defs.get(attr)
        if node is None:
            if attr in imported:   # a re-export: the member is its home definition
                stack.append(imported[attr])
                continue
            raise LookupError(f"digest closure: {spec} is not a module-level definition")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function"
        elif isinstance(node, ast.ClassDef):
            kind = "class"
        else:
            kind = "constant"
        parts.append((kind, spec, _member_body(node)))
        for sub in ast.walk(node):  # type: ignore[arg-type]
            if isinstance(sub, ast.Name):
                if sub.id in defs:
                    stack.append(f"{mod_name}:{sub.id}")
                elif sub.id in imported:
                    stack.append(imported[sub.id])
            elif (isinstance(sub, ast.ImportFrom) and sub.level == 0 and sub.module
                  and sub.module.split(".")[0] == "swing"):
                stack.extend(f"{sub.module}:{alias.name}" for alias in sub.names)
    return sorted(parts, key=lambda p: p[1])


def digest_of_parts(parts: list[tuple[str, str, str]]) -> str:
    """sha256 over the parts, each keyed by its fully-qualified spec (so
    re-pointing a name is a change even when the value is unchanged)."""
    import hashlib

    joined = "\x1e".join(f"{kind}\x1f{spec}\x1f{body}" for kind, spec, body in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def frozen_value_evidence_digest() -> str:
    return digest_of_parts(frozen_value_evidence_digest_parts())


# APPEND-ONLY.  A behaviour change to any member appends a new pair and moves
# ``FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION`` with it in the SAME commit -- NO
# migration: SQL types the stored value and never binds it.  A stored blob
# keeps the derivation version it was written under; the replay returns a
# moved one as an observation beside its verdict (G-T7F-AMEND).
#
# SEEDED 2026-09-23 on the AST digest (G-T7F).  The first entry is ``.2``, not
# ``.1``: ``2026-09-23.1`` is the GRAMMAR version's string, and it was the
# version this history's earlier source-text pair carried on this branch
# (``ee157a28``) -- no version string is ever re-bound to a second digest.
#
# ``.3`` (CHARC G-T9 item 2): ``read_artifact_facts`` takes an optional
# per-invocation ref resolution, its ref and reflog reads factored into
# ``_ref_stage`` / ``_reflog_stage`` (new members, with ``_budgeted_git``,
# ``_failure_detail`` and ``RemoteRefResolution``).  The facts it returns for a
# given repo state are unchanged; the digest records the member edit.
FROZEN_VALUE_EVIDENCE_HISTORY: tuple[tuple[str, str], ...] = (
    ("2026-09-23.2",
     "e098e9cddd4327b545dac89dbc7f017442f016bf9f82c5b9731d4b815fec1c1b"),
    ("2026-09-23.3",
     "f99090619b500e866bf104556bb419b7c26ab85e1cc82ce6e6ddc4b0d1eb5193"),
)
