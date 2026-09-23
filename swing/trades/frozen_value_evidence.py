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
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# The seventh-column blob's own version (``$.evidence_version`` of
# ``cited_frozen_value_evidence_json``), mirrored by migration 0039's citation
# trigger literal.  A drift test reads the literal out of the HEAD trigger.
FROZEN_VALUE_EVIDENCE_VERSION = "2026-09-23.1"

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
    "service-rendered tokens; (4) the record is at or after the fire's pipeline "
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
    "evidence_version", "ruling_citation", "verification_method", "evaluated_at",
    "artifact_path", "artifact_commit_sha", "quoted_text", "quoted_ticker_text",
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

# E-15: the keys the replay COMPARES (dotted paths into the blob).  Everything
# else is RECORDED only -- evaluated_at, the resolved sha, the descendant
# count, the ref age, the committer instant, the segments -- and never compared.
VERDICT_BEARING_KEYS: frozenset[str] = frozenset({
    "artifact_path", "artifact_commit_sha", "quoted_text",
    "quoted_ticker_text", "quoted_action_session_text", "quoted_pivot_text",
    "quoted_invalidation_text", "live_pivot_raw", "live_invalidation_raw",
    "author_instant", "author_date_et", "fill_session_date",
    *(f"interval.endpoints.{e}.{k}" for e in INTERVAL_ENDPOINTS for k in ("raw", "utc")),
})


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


def read_artifact_facts(selection: EvidenceSelection, *, repo_dir: Path,
                        now_utc: datetime) -> PreflightResult:
    """Read what git says about ``selection``.  Never raises.

    Order: the ref (process), the commit and its dates, the blob, the quoted
    text (byte-substring, then one line), ancestry, descendants, the reflog.
    """
    try:
        if now_utc.utcoffset() is None:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE, "now_utc must be offset-aware")
        sha = selection.artifact_commit_sha

        ref = _run_git(repo_dir, "rev-parse", "--verify", "--quiet", f"{REMOTE_REF}^{{commit}}")
        if ref.returncode != 0:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                           f"{REMOTE_REF} does not resolve in {repo_dir} "
                           f"(exit {ref.returncode}) {_stderr(ref)}".strip())
        resolved = ref.stdout.decode("ascii").strip()

        dates = _run_git(repo_dir, "show", "-s", "--format=%aI%n%cI", f"{sha}^{{commit}}")
        if dates.returncode != 0:
            return _refuse(FAILURE_ARTIFACT_UNREADABLE,
                           f"commit {sha} is not readable: {_stderr(dates)}")
        date_lines = dates.stdout.decode("utf-8").split("\n")
        author_instant = datetime.fromisoformat(date_lines[0].strip())
        committer_instant = datetime.fromisoformat(date_lines[1].strip())

        blob = _run_git(repo_dir, "cat-file", "blob", f"{sha}:{selection.artifact_path}")
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

        anc = _run_git(repo_dir, "merge-base", "--is-ancestor", sha, resolved)
        if anc.returncode not in (0, 1):
            return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                           f"git merge-base exited {anc.returncode}: {_stderr(anc)}")
        is_ancestor = anc.returncode == 0

        descendant_count: int | None = None
        if is_ancestor:
            count = _run_git(repo_dir, "rev-list", "--count", f"{sha}..{resolved}")
            if count.returncode != 0:
                return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                               f"git rev-list exited {count.returncode}: {_stderr(count)}")
            descendant_count = int(count.stdout.decode("ascii").strip())

        log = _run_git(repo_dir, "log", "-g", "-1", "--date=iso-strict", "--format=%gD",
                       REMOTE_REF, "--")
        if log.returncode != 0:
            return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                           f"git log -g exited {log.returncode}: {_stderr(log)}")
        updated_at = _parse_reflog_instant(log.stdout)
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
    except _GitProcessError as exc:
        return _refuse(FAILURE_TIER2_UNVERIFIABLE, str(exc))
    except Exception as exc:  # noqa: BLE001 -- E-6: the preflight never raises; fail closed
        return _refuse(FAILURE_TIER2_UNVERIFIABLE,
                       f"preflight could not complete: {type(exc).__name__}: {exc}")


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
    rendering, clock domain and source column -- and four segments in order.
    The durations are the SERVICE's record; SQL binds only the raws (AL2-9)."""
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
    spans = (("fire", "fire_lo", "fire_hi"),
             ("writer_absence_only", "fire_hi", "record_at"),
             ("match_only", "record_at", "barrier_armed_at"),
             (SEGMENT_COVERED if barrier_installed else SEGMENT_UNCOVERED_BARRIER_ABSENT,
              "barrier_armed_at", "read_at"))
    segments = [
        {"kind": kind, "from": utc[a], "to": utc[b],
         "seconds": _seconds(instants[a], instants[b])}
        for kind, a, b in spans
    ]
    return {"endpoints": endpoints, "segments": segments}


def render_uncovered_window_prose(interval: dict) -> str:
    """F9: the service renders the prose; nobody types it."""
    parts = []
    for seg in interval["segments"]:
        if seg["kind"] in ("writer_absence_only", "match_only"):
            parts.append(f"{seg['kind']} {seg['seconds'] / 86400:.2f} days "
                         f"({seg['from']} to {seg['to']})")
        elif seg["kind"] in (SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT):
            parts.append(f"{seg['kind']} from {seg['from']}")
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
    initial_stop as service-rendered whole tokens (F13); (4) the record is at
    or after the fire's upper bound ``pipeline_runs.finished_ts`` (F6 ii).
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

    # Criterion 4 -- the fire is a BRACKET [run_ts, finished_ts] (R8-01).
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
    if record_at < fire_hi:
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
    return (isinstance(iv, dict) and set(iv) == {"endpoints", "segments"}
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


def _tp_interval_segment_order(blob, ctx, **_):
    segs = blob["interval"]["segments"]
    if not (isinstance(segs, list) and len(segs) == 4):
        return False
    kinds = [s.get("kind") if isinstance(s, dict) else None for s in segs]
    if kinds[:3] != list(SEGMENT_KINDS) or kinds[3] not in (
            SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT):
        return False
    return all(set(s) == {"kind", "from", "to", "seconds"} and _is_text(s["from"])
               and _is_text(s["to"]) and _is_number(s["seconds"]) for s in segs)


# The blob predicates' mirrors, in the trigger's order.  A tuple of NAMED
# functions so the A2-60 walk sees each one referenced from evaluate_conjunction.
_BLOB_MIRRORS = (
    _tp_seventh_present, _tp_blob_closed, _tp_evidence_version, _tp_attestation_texts,
    _tp_evaluated_at_is_applied_at, _tp_artifact_commit_sha_shape,
    _tp_quoted_text_one_line, _tp_quoted_ticker, _tp_quoted_action_session,
    _tp_quoted_pivot, _tp_quoted_invalidation, _tp_live_pivot_raw,
    _tp_live_invalidation_raw, _tp_equal_at_dp_verdicts, _tp_compare_dp,
    _tp_fill_session_date, _tp_author_date_before_fill, _tp_remote_ref_attestation,
    _tp_interval_closed, _tp_interval_endpoint_fire_lo, _tp_interval_endpoint_fire_hi,
    _tp_interval_endpoint_record_at, _tp_interval_endpoint_barrier_armed_at,
    _tp_interval_endpoint_read_at, _tp_interval_segment_order,
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
