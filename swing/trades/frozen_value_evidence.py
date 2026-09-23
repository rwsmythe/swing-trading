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
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
