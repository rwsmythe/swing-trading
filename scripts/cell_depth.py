"""cell_depth.py -- read a dispatched cell's context depth from its own
transcript.

A cell cannot see its own context depth: the `[ctx]` line printed by the
`UserPromptSubmit` hook never fires for a subagent. A dispatcher reads a
cell's depth from the cell's own transcript file instead -- this is that
reader. Generic transcript reader; no application vocabulary.

Discovery: a cell's transcript is a JSONL file named
`agent-a<name>-<hash>.jsonl` (a NAMED cell) or `agent-a<hash>.jsonl` (an
ANONYMOUS cell, dispatched with no distinguishing name -- reported under its
hash, the only identifier it has) under `<project>/<session>/subagents/`.
Every API response the cell's session received carries a `message.usage`
object; a single response can appear as several usage-bearing JSONL records
sharing one `message.id` (separate thinking / text / tool-use blocks) -- this
reader folds those back into ONE request before summing three of its usage
fields into a depth-in-tokens figure, read straight through the file, never
writing to it.

Selectors: --all (the default) reads every discovered cell; --live HOURS
reads fresh cells plus older cells whose parent main transcript is fresh
(flagged parked); repeatable --agent ID reads an exact cell identity at any age:
its parsed name (or anonymous hash) must equal ID, or its filename stem must
equal agent-a<ID>. Prefix siblings are excluded, and an empty ID is invalid.
These three selectors are mutually exclusive. --sessions switches to direct
<project>/<session-id>.jsonl main transcripts, named by session id; it works
with --all or --live, but not --agent. --session restricts discovery literally
in either mode, and the positional substring filters the reported names.
The --live window must be nonnegative and not NaN; positive infinity is also
accepted to include transcripts of every age.

Every row appends age=<hours to one decimal>h and flag=ok, OVER, parked, or
OVER,parked. The PEAK cap applies to all selected rows, including parked ones.
Exit codes: 0 clean (also a nonempty discovery with an empty live window);
1 no transcripts discovered, loudly reported as NO CELLS FOUND; 2 PEAK over
cap; 3 incomplete measurement; 4 usage/configuration error, including unknown
agent IDs after a clean listing. A failed listing that prevents an agent
lookup exits 3. If any requested ID is missing after a clean listing, exit 4
without measuring the other requested IDs. Exit 2 wins over 3 for measured
rows. An empty live window prints one stdout line:
no cells written in the last <H>h (cap <N>); nothing to check
(sessions instead of cells in --sessions mode).

STDLIB ONLY. Read-only: this script never creates, deletes, or modifies a
transcript.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
import json
import re
from collections.abc import Iterator
from pathlib import Path

# A NAMED cell: agent-a<name>-<16 hex char hash>.jsonl. An ANONYMOUS cell (no
# name given at dispatch): agent-a<16 hex char hash>.jsonl, with no separating
# hyphen before the hash. The hash width (16 hex chars) is the one observed
# across every transcript in this clone. Tried as two alternatives rather than
# one `(?:...)?` group so an all-hex NAME can never be misread as the hash
# (e.g. a cell literally named "cell-depth" contains no such ambiguity, but a
# hypothetical all-hex-digit cell name would; the named alternative is tried
# first and is unambiguous because it requires the trailing hyphen).
_NAMED_RE = re.compile(r"^agent-a(?P<name>.+)-(?P<hash>[0-9a-f]{16})\.jsonl$")
_ANON_RE = re.compile(r"^agent-a(?P<hash>[0-9a-f]{16})\.jsonl$")

DEFAULT_CAP = 400_000

# The usage-object fields summed into one request's depth.
_DEPTH_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

#: rung-a item (d). A transcript's `version` value is ACCEPTED as a CLI version only if
#: it looks like one -- a dotted numeric version, optionally suffixed. **Reviewer A r1
#: (MINOR) reproduced the reason this is not merely tidiness:** an "any nonempty
#: string" test let a record carrying `"2.1.266\nFORGED"` both MANUFACTURE a span (two
#: distinct strings where the binary never moved) and inject its own lines into the
#: printed report, which is rendered verbatim to whoever reads a cell's depth. The
#: anchors matter as much as the shape: `re.match` alone would accept the forged value
#: on its first line.
_CLI_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+.][0-9A-Za-z.\-+]*)?\Z")


def default_project_dir(claude_home: Path | None = None) -> Path:
    """This clone's own transcript directory under ~/.claude/projects.

    Best-effort: the harness names a project directory after the working
    directory it was launched from, with path separators and the drive-letter
    colon collapsed to '-'. Because that name is fixed at the FIRST session
    opened from a given shell, a different launching shell for the same clone
    can produce a differently-cased or differently-rooted slug than this
    guess -- pass --project explicitly whenever the guess does not match.
    """
    home = claude_home if claude_home is not None else Path.home() / ".claude"
    slug = re.sub(r"[\\/:]", "-", str(Path.cwd()))
    return home / "projects" / slug


def cell_name_from_filename(filename: str) -> str | None:
    """The cell name embedded in an `agent-a<name>-<hash>.jsonl` filename; for
    an anonymous `agent-a<hash>.jsonl` file the hash itself is returned (the
    only identifier such a cell has -- it is still discoverable and reportable,
    just not attributable to a dispatch-time name). None if `filename` matches
    neither shape."""
    match = _NAMED_RE.match(filename)
    if match is not None:
        return match.group("name")
    match = _ANON_RE.match(filename)
    if match is not None:
        return match.group("hash")
    return None


class _Malformed(Exception):
    """Raised internally when a usage-bearing record's shape or values are
    unusable (wrong type, non-finite number) -- caught by the reader's single
    malformed-line handler so a freak value never aborts the whole read."""


def _request_depth(usage: dict) -> int:
    """Depth on one request: input + cache-read + cache-creation tokens.

    Raises `_Malformed` for a present-but-unusable field: wrong type; a
    non-finite float (`1e309` decodes to infinity, which would otherwise
    raise `OverflowError` deep inside `int()`); a FRACTIONAL float (a token
    count is a whole quantity -- `400000.9` truncating to `400000` would
    silently shave a supplied depth down, in the worst case from just over
    `--cap` to exactly the cap); or a NEGATIVE value (a token count can
    never legitimately be negative, and summing one can UNDER-report a
    positive component -- e.g. `-200000` alongside a real `500001` reads as
    `300001`, hiding both the true magnitude and the corruption). A missing
    or `None` field contributes 0, which is normal (not every request uses
    every token class).
    """
    total = 0
    for key in _DEPTH_FIELDS:
        value = usage.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _Malformed(f"non-numeric {key}: {value!r}")
        if isinstance(value, float):
            if not math.isfinite(value):
                raise _Malformed(f"non-finite {key}: {value!r}")
            if not value.is_integer():
                raise _Malformed(f"non-integer {key}: {value!r}")
        if value < 0:
            raise _Malformed(f"negative {key}: {value!r}")
        total += int(value)
    return total


class TranscriptStats:
    """current/peak/turns for one cell transcript, plus the malformed-line
    count encountered while reading it (never fatal, always reported), plus
    the SET of CLI versions the transcript's records were written under.

    **``cli_versions`` IS A SET, AND A SET OF SIZE > 1 IS A SPAN** (rung-a item
    (d), 2026-09-13). The harness stamps each transcript record with the CLI
    version that wrote it (the top-level ``version`` key). A cell whose
    transcript carries two of them ran across a binary change -- a REGIME
    VARIABLE, not noise, and the same class of event that went unrecorded
    inside one long run. Reported rather than judged: this reader
    says WHAT it read; the `[ctx]` consumer decides what to do about it."""

    __slots__ = ("current", "peak", "turns", "malformed", "cli_versions")

    def __init__(self, current: int = 0, peak: int = 0, turns: int = 0,
                 malformed: int = 0, cli_versions: set | None = None) -> None:
        self.current = current
        self.peak = peak
        self.turns = turns
        self.malformed = malformed
        self.cli_versions = set() if cli_versions is None else set(cli_versions)


# Sentinel distinguishing "no request seen yet" / "this record carries no
# message id" from any real id string (which could theoretically be falsy-ish,
# though Claude Code ids never are) -- see the dedup comment in read_transcript.
_NO_ID = object()

# Sentinel distinguishing a GENUINELY MISSING "usage" key (not a usage-bearing
# record at all -- skip silently) from a key that is PRESENT but null (a
# corrupted/incomplete record -- malformed). `dict.get(key, default)` cannot
# use `None` as that default, since a present `"usage": null` IS `None` too.
_NO_USAGE_KEY = object()


def read_transcript(path: Path) -> TranscriptStats:
    """Read one transcript file straight through (read-only).

    One API response can be written as SEVERAL usage-bearing JSONL records
    that share one `message.id` (separate thinking / text / tool-use content
    blocks, each carrying the same request's usage figures), possibly with
    OTHER, non-usage-bearing lines interleaved (418 such interleavings were
    observed across this clone's 73 real transcripts) -- consecutive
    USAGE-BEARING records sharing an id are the SAME request and are folded
    into one turn (a non-usage-bearing line in between does not break the
    fold, since it never touches the last-seen id); `current` is the depth of
    the last DISTINCT request in the file and `peak` is the max depth seen
    across distinct requests. A record with no `message.id` is always treated
    as its own request (never folded).

    A line that fails to parse as JSON, or whose usage object is unusable
    (present but null or wrong-typed; a token count that is non-numeric,
    non-finite, fractional, or negative), is SKIPPED and counted in
    `.malformed` -- never fatal to the read. A GENUINELY MISSING `usage` key
    is different: that is simply not a usage-bearing record, not malformed.
    Malformed-shape detection runs BEFORE the duplicate-id fold check, so a
    duplicate whose OWN usage is unusable is still counted malformed rather
    than silently absorbed by the fold.
    """
    stats = TranscriptStats()
    last_id: object = _NO_ID
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                # rung-a item (d): the CLI VERSION SET, collected off EVERY
                # well-formed record -- deliberately BEFORE the usage-bearing
                # filters below, because a version span is a fact about the
                # WHOLE transcript and most of its records carry no usage. A
                # non-string version is ignored rather than counted (it would
                # manufacture a span out of a malformed record).
                if isinstance(record, dict):
                    version = record.get("version")
                    if isinstance(version, str) and _CLI_VERSION_RE.match(version):
                        stats.cli_versions.add(version)
                message = record.get("message") if isinstance(record, dict) else None
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage", _NO_USAGE_KEY)
                if usage is _NO_USAGE_KEY:
                    continue  # no usage key at all -- not a usage-bearing record
                if usage is None or not isinstance(usage, dict):
                    # PRESENT but null or wrong-shaped (e.g. a list) --
                    # unlike a genuinely MISSING key, this is a corrupted
                    # record, not an ordinary non-usage one. A present-null
                    # `"usage": null` is an ordinary API shape whose silent
                    # omission would report the PREVIOUS request's depth as
                    # a clean, complete reading of the NEWEST one -- counted
                    # malformed like any other unusable shape, never
                    # conflated with the missing-key case above.
                    raise _Malformed(f"unusable usage: {usage!r}")
                depth = _request_depth(usage)  # validated BEFORE the fold check
                message_id = message.get("id")
            except (json.JSONDecodeError, ValueError, _Malformed):
                stats.malformed += 1
                continue
            if message_id is not None and message_id == last_id:
                continue  # another content block of the SAME request
            last_id = message_id if message_id is not None else _NO_ID
            stats.current = depth
            stats.peak = max(stats.peak, depth)
            stats.turns += 1
    return stats


class BadSession(ValueError):
    """`--session` named something other than a single directory segment."""


def _is_single_segment(name: str) -> bool:
    """True iff `name` is a plain, non-empty directory-NAME segment that
    `project / name` can never resolve outside `project`, on POSIX OR
    Windows path semantics.

    Rejects: an empty string; `.`/`..`; any `/` or `\\`; and any `:` --
    Windows interprets a DRIVE-QUALIFIED RELATIVE path like `D:foo` (no
    separator at all) relative to drive D's own remembered current
    directory, not as a child of `project` -- `(project / "D:foo")` silently
    resolves OUTSIDE `project` with no separator present to catch. A colon
    can never appear in a real session id (a UUID), so banning it costs
    nothing real.
    """
    if not name or name in (".", ".."):
        return False
    return not any(ch in name for ch in ("/", "\\", ":"))


class DiscoveryError(Exception):
    """A filesystem error while enumerating sessions/transcripts under a
    project directory, OR a file that matched the `agent-a*.jsonl` discovery
    glob but that neither filename pattern could parse.

    `Path.glob()` (and `Path.is_dir()` on some runtimes) can absorb a
    permission error or a transient filesystem error into a silent
    empty-result / False rather than raising -- exactly the class of defect
    this whole instrument exists to prevent (a session vanishing from the
    report with no sign anything went wrong). Discovery below is routed
    through `os.scandir()` instead, whose errors are never swallowed, and
    raises/reports this type rather than reproducing that silent loss.
    """


def _scan_dir_entries(path: Path) -> list[os.DirEntry]:
    """Sorted `os.DirEntry` list for `path`. Raises `OSError` verbatim if the
    directory cannot be opened or read -- unlike `Path.glob()`, `os.scandir()`
    has no built-in behavior that swallows a permission/transient error."""
    with os.scandir(path) as it:
        return sorted(it, key=lambda entry: entry.name)


def _is_definitely_nonexistent(exc: OSError) -> bool:
    """True for an OSError that means "this path can never exist", beyond the
    plain `FileNotFoundError`/`NotADirectoryError` cases callers already
    catch directly. On Windows, a path segment containing a character the
    filesystem forbids (e.g. a literal `*` from a `--session` value matched
    LITERALLY, never as a glob) raises `OSError` with `winerror == 123`
    (ERROR_INVALID_NAME) rather than a not-found error -- a STRONGER
    statement of nonexistence (the name could never be valid at all), not a
    permission or transient problem to surface as a `DiscoveryError`."""
    return getattr(exc, "winerror", None) == 123


def discover_cells(project: Path, session: str | None,
                    errors: list[DiscoveryError] | None = None):
    """Yield (cell_name, session_id, path) for every matching transcript
    under `project`, restricted to one session id when `session` is given.

    A cell's transcript is any `agent-a*.jsonl` file directly under
    `<project>/<session>/subagents/` -- the `subagents/` directory is
    REQUIRED; a naive glob of the project directory that omits it misses
    every cell and would silently report "no cells" while cells exist -- see
    test 2 for the positive control on this trap. `session` is matched
    LITERALLY, never as a glob pattern -- a caller-supplied id containing
    `*`/`?`/`[...]` selects exactly that literal directory name (or
    nothing), never an unintended sibling -- and it must be a single,
    NON-EMPTY path SEGMENT (see `_is_single_segment`: no `/`, `\\`, `:`,
    `..`, or `""`), raising `BadSession` otherwise. An empty string is
    rejected explicitly: `Path(x) / ""` is `Path(x)` unchanged in pathlib,
    so an unrejected `""` would silently skip the whole session-directory
    layer and search `<project>/subagents/` directly. A colon is rejected
    because Windows resolves a drive-qualified relative segment like
    `D:foo` against drive D's own remembered current directory rather than
    as a child of `project` -- `project / "D:foo"` can land OUTSIDE
    `project` with no `/`/`\\`/`..` present to catch it.

    A directory that cannot be LISTED (permissions, a transient filesystem
    error) and a filename that matches the glob but that NEITHER
    `cell_name_from_filename` pattern can parse are both real problems, never
    silently skipped: each becomes a `DiscoveryError`. When `errors` is
    given, it is APPENDED to and enumeration CONTINUES with the next
    directory/file (so one bad directory or one odd filename never blinds
    the rest of the sweep); when `errors` is None (the default), the FIRST
    such problem is raised immediately -- useful for a caller that wants
    strict, fail-fast behavior.
    """
    if session is not None:
        if not _is_single_segment(session):
            raise BadSession(
                f"--session must be a single directory name, not {session!r}")
        session_dirs = [project / session]
    else:
        try:
            top_entries = _scan_dir_entries(project)
        except OSError as exc:
            error = DiscoveryError(f"cannot list sessions under {project}: {exc}")
            if errors is not None:
                errors.append(error)
                return
            raise error from exc
        session_dirs = []
        for entry in top_entries:
            try:
                is_dir = entry.is_dir()
            except OSError as exc:
                error = DiscoveryError(f"cannot stat {entry.path}: {exc}")
                if errors is not None:
                    errors.append(error)
                    continue
                raise error from exc
            if is_dir:
                session_dirs.append(Path(entry.path))

    for session_dir in session_dirs:
        subagents_dir = session_dir / "subagents"
        try:
            file_entries = _scan_dir_entries(subagents_dir)
        except (FileNotFoundError, NotADirectoryError):
            continue  # no subagents/ here -- the normal, expected case
        except OSError as exc:
            if _is_definitely_nonexistent(exc):
                continue  # e.g. a literal --session containing a character
                          # (Windows: '*') that can never form a real path --
                          # a STRONGER form of "doesn't exist", not a real
                          # problem to report.
            error = DiscoveryError(f"cannot list {subagents_dir}: {exc}")
            if errors is not None:
                errors.append(error)
                continue
            raise error from exc

        session_id = session_dir.name
        for entry in file_entries:
            if not (entry.name.startswith("agent-a") and entry.name.endswith(".jsonl")):
                continue
            name = cell_name_from_filename(entry.name)
            if name is None:
                error = DiscoveryError(
                    f"{entry.path}: matched the agent-a*.jsonl discovery "
                    "glob but neither filename pattern could parse it")
                if errors is not None:
                    errors.append(error)
                    continue
                raise error
            yield name, session_id, Path(entry.path)


_Transcript = tuple[str, str, Path]


def discover_sessions(project: Path, session: str | None,
                      errors: list[DiscoveryError] | None = None) -> Iterator[_Transcript]:
    """Yield main transcripts directly under a project, named by session id.

    Match an optional session literally, with the same single-segment guard
    as cell discovery. Scandir/stat failures raise DiscoveryError in strict
    mode or accumulate in errors while healthy entries remain discoverable.
    A main transcript does not require a corresponding session directory.
    """
    if session is not None and not _is_single_segment(session):
        raise BadSession(f"--session must be a single directory name, not {session!r}")
    try:
        entries = _scan_dir_entries(project)
    except OSError as exc:
        error = DiscoveryError(f"cannot list sessions under {project}: {exc}")
        if errors is not None:
            errors.append(error)
            return
        raise error from exc
    for entry in entries:
        if not entry.name.endswith(".jsonl"):
            continue
        name = entry.name[:-6]
        if session is not None and name != session:
            continue
        try:
            is_file = entry.is_file()
        except OSError as exc:
            error = DiscoveryError(f"cannot stat {entry.path}: {exc}")
            if errors is not None:
                errors.append(error)
                continue
            raise error from exc
        if is_file:
            yield name, name, Path(entry.path)


def find_agents(cells: list[_Transcript], project: Path, session: str | None,
                agent_ids: list[str]) -> tuple[list[_Transcript], list[str]]:
    """Select exact cell identities at any age and report missing search forms.

    Reuse already discovered cells so named/anonymous parsing and scandir
    failures retain the cell reader's contract. Each path is returned once,
    even when requested IDs repeat. A parsed name (or anonymous hash) must
    equal the ID, or its filename stem must equal agent-a<ID>; a longer
    sibling's name does not match. No additional filesystem glob is run.
    """
    selected: set[Path] = set()
    missing: list[str] = []
    noted: set[tuple[str, str]] = set()
    cross_session_noted: set[str] = set()
    for agent_id in agent_ids:
        matches = [(session_id, path) for name, session_id, path in cells
                   if name == agent_id or path.stem == f"agent-a{agent_id}"]
        if not matches:
            directory = project / (session if session is not None else "*") / "subagents"
            missing.append(f"{directory / f'agent-a{agent_id}.jsonl'} or "
                           f"{directory / f'agent-a{agent_id}-<16hex>.jsonl'} "
                           "(exact parsed name or filename stem)")
        session_counts: dict[str, int] = {}
        for session_id, path in matches:
            selected.add(path)
            session_counts[session_id] = session_counts.get(session_id, 0) + 1
        for session_id, count in session_counts.items():
            if count > 1 and (agent_id, session_id) not in noted:
                print(f"NOTE: --agent {agent_id} matched {count} transcripts in session "
                      f"{session_id[:8]}; use the full name-hash stem to read one",
                      file=sys.stderr)
                noted.add((agent_id, session_id))
        if session is None and len(session_counts) > 1 and agent_id not in cross_session_noted:
            print(f"NOTE: --agent {agent_id} matched transcripts in {len(session_counts)} "
                  "sessions; pass --session=<session-id> to read one", file=sys.stderr)
            cross_session_noted.add(agent_id)
    return [cell for cell in cells if cell[2] in selected], missing


def session_transcript_path(cell_path: Path) -> Path:
    """Return the parent main transcript derived only from the cell's own path.

    A cell at project/session/subagents/agent-a*.jsonl has its parent main
    transcript at project/session.jsonl, always within that same project.
    """
    session_dir = cell_path.parent.parent
    return session_dir.parent / f"{session_dir.name}.jsonl"


def _transcript_age_hours(path: Path, *, now: float) -> float:
    """Measure transcript age with one stat, clamping future mtimes to zero."""
    return max(0.0, (now - path.stat().st_mtime) / 3600.0)


def session_transcript_age_hours(cell_path: Path, *, now: float | None = None) -> float | None:
    """Return the parent transcript's age, or None if it has disappeared.

    One guarded stat avoids an existence-check/stat race. Other filesystem
    failures propagate so a failed parent lookup cannot look like a clean
    exclusion from a live census.
    """
    stamp = time.time() if now is None else now
    try:
        return _transcript_age_hours(session_transcript_path(cell_path), now=stamp)
    except FileNotFoundError:
        return None


def select_live(cells: list[_Transcript], live_hours: float, *,
                ages: dict[Path, float], now: float | None = None,
                errors: list[DiscoveryError] | None = None) -> tuple[list[_Transcript], set[Path]]:
    """Select fresh cells and older cells parked under a fresh parent session.

    Return selected cells and the parked subset's paths. Missing parents do
    not retain old cells. Other parent stat failures raise DiscoveryError,
    or accumulate in errors while selection continues for healthy cells.
    """
    stamp = time.time() if now is None else now
    kept: list[_Transcript] = []
    parked: set[Path] = set()
    for cell in cells:
        _, _, path = cell
        if ages[path] <= live_hours:
            kept.append(cell)
            continue
        try:
            parent_age = session_transcript_age_hours(path, now=stamp)
        except OSError as exc:
            error = DiscoveryError(f"cannot stat parent transcript for {path}: {exc}")
            if errors is not None:
                errors.append(error)
                continue
            raise error from exc
        if parent_age is not None and parent_age <= live_hours:
            kept.append(cell)
            parked.add(path)
    return kept, parked


class _ConfigError(Exception):
    """Raised in place of `ArgumentParser`'s default `sys.exit(2)` on a usage
    error (bad `--cap`, an unknown argument, a missing option value) so
    `main()` can map EVERY configuration/usage failure to the SAME exit code
    (4) -- without this, argparse's own built-in `exit(2)` on a malformed
    invocation would collide with PAST-CAP's exit 2, reproducing the exact
    ambiguity `main()`'s exit-4 mapping exists to remove."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - trivial
        raise _ConfigError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="cell_depth.py",
        description="Read a dispatched cell's context depth from its own "
                     "transcript (message.usage) -- a cell cannot self-report "
                     "this, so a dispatcher reads it here.")
    parser.add_argument(
        "cell", nargs="?", default=None,
        help="only report cells or sessions whose name contains this substring")
    parser.add_argument(
        "--project", type=Path, default=None,
        help="project transcript directory (default: this clone's own "
             "~/.claude/projects/<slug>; see default_project_dir())")
    parser.add_argument(
        "--session", default=None,
        help="restrict to one session id: a single directory-name segment "
             "under --project, matched literally, never as a glob pattern")
    parser.add_argument(
        "--cap", type=int, default=DEFAULT_CAP,
        help=f"depth cap in tokens (default {DEFAULT_CAP}); a cell whose "
             "PEAK depth exceeds it is marked PAST-CAP -- PEAK, not current, "
             "because the binding rule requires re-dispatch from a FRESH "
             "context, and a compacted cell's current depth looks cheap "
             "again while carrying the same degraded context")
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument(
        "--live", type=float, metavar="HOURS",
        help="report transcripts written within HOURS; cell mode also includes "
             "older cells with fresh parent transcripts, flagged parked; "
             "HOURS must be >= 0 and not NaN (positive infinity is accepted)")
    selectors.add_argument(
        "--all", action="store_true", help="report every discovered transcript (the default)")
    selectors.add_argument(
        "--agent", action="append", metavar="ID",
        help="read an exact parsed cell name/anonymous hash or filename stem agent-a<ID> "
             "at any age; no prefix match; nonempty and repeatable; incompatible with --sessions")
    parser.add_argument(
        "--sessions", action="store_true",
        help="read main <project>/<session-id>.jsonl transcripts instead of cells; "
             "--live uses only their own mtime")
    parser.epilog = (
        "Exit codes: 0 clean (including a nonempty discovery with an empty "
        "--live window, reported as 'nothing to check'); 1 no transcripts "
        "found (NO CELLS FOUND on stderr); 2 a transcript's PEAK depth exceeds "
        "--cap; 3 the sweep ran but is INCOMPLETE (an unreadable transcript, "
        "an unparsed filename, a directory-listing error, skipped malformed "
        "lines, or a cell with zero usage-bearing requests yet -- 2 always "
        "wins over 3 when both apply); 4 usage/configuration error (bad "
        "--project, bad --session, an invalid --cap, an unknown --agent ID, "
        "--agent with --sessions, or any other argument "
        "error -- the measurement never ran). If agent lookup fails with "
        "discovery errors, exit 3 instead: absence cannot be established. "
        "If any requested agent ID is missing after a clean listing, exit 4 "
        "without measuring the other requested IDs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        if args.agent and args.sessions:
            raise _ConfigError("--agent reads cells; it cannot be combined with --sessions")
        if args.agent and any(not agent_id for agent_id in args.agent):
            raise _ConfigError("--agent ID must not be empty")
        if args.live is not None and (math.isnan(args.live) or args.live < 0):
            raise _ConfigError("--live HOURS must be >= 0 and not NaN")
        if args.live == 0:
            args.live = 0.0
    except _ConfigError as exc:
        print(f"USAGE ERROR: {exc}", file=sys.stderr)
        return 4

    project = args.project if args.project is not None else default_project_dir()
    # VISIBLE ON EVERY RUN, explicit or guessed: a guessed project directory
    # that happens to EXIST (just the wrong one) must never masquerade as an
    # authoritative --project the way an explicit one is -- the missing-
    # directory guard below cannot catch that case, so this line is the one
    # that can.
    project_source = ("explicit --project" if args.project is not None
                       else "guessed default -- pass --project to override")
    print(f"project ({project_source}): {project}", file=sys.stderr)

    if not project.is_dir():
        print(f"NO PROJECT DIRECTORY at {project} -- pass --project to point "
              "at the right transcript directory", file=sys.stderr)
        return 4

    rows = []
    unreadable = []
    discovery_errors: list[DiscoveryError] = []
    try:
        discover = discover_sessions if args.sessions else discover_cells
        cells = list(discover(project, args.session, errors=discovery_errors))
    except BadSession as exc:
        print(f"BAD --session: {exc}", file=sys.stderr)
        return 4

    if args.agent:
        cells, missing = find_agents(cells, project, args.session, args.agent)
        if missing:
            for error in discovery_errors:
                print(f"DISCOVERY ERROR: {error}", file=sys.stderr)
            prefix = "INCOMPLETE" if discovery_errors else "USAGE ERROR"
            for pattern in missing:
                print(f"{prefix}: no cell transcript found; searched: {pattern}",
                      file=sys.stderr)
            return 3 if discovery_errors else 4
    positional_miss = False
    if args.cell:
        had_cells = bool(cells)
        cells = [cell for cell in cells if args.cell in cell[0]]
        positional_miss = had_cells and not cells
    discovered = bool(cells)
    ages: dict[Path, float] = {}
    stamp = time.time()
    measurable: list[_Transcript] = []
    for cell in cells:
        name, _, path = cell
        try:
            ages[path] = _transcript_age_hours(path, now=stamp)
        except OSError as exc:
            unreadable.append((name, path, exc))
            continue
        measurable.append(cell)
    cells = measurable
    parked: set[Path] = set()
    if args.live is not None:
        if args.sessions:
            cells = [cell for cell in cells if ages[cell[2]] <= args.live]
        else:
            cells, parked = select_live(cells, args.live, ages=ages, now=stamp,
                                       errors=discovery_errors)
        if not cells and discovered and not unreadable and not discovery_errors:
            kind = "sessions" if args.sessions else "cells"
            print(f"no {kind} written in the last {args.live:g}h (cap {args.cap:,}); "
                  "nothing to check")
            return 0
    for name, session_id, path in cells:
        try:
            stats = read_transcript(path)
        except (OSError, UnicodeDecodeError) as exc:
            # One unreadable transcript must not blind the rest of the sweep.
            unreadable.append((name, path, exc))
            continue
        rows.append((name, session_id, path, stats))

    for error in discovery_errors:
        print(f"DISCOVERY ERROR: {error}", file=sys.stderr)
    for name, path, exc in unreadable:
        print(f"UNREADABLE transcript for {name} at {path}: {exc}", file=sys.stderr)

    if not rows and not unreadable and not discovery_errors:
        session_desc = args.session if args.session else "*"
        # LOUD, on purpose (spec Sec 3, test 2): silently printing nothing here
        # is the exact defect this script exists to prevent -- a naive glob
        # that misses subagents/ once undercounted a real arc's spend by 42.9%
        # while reporting "no cells" as if that were a clean negative result.
        if args.sessions:
            pattern = f"{args.session}.jsonl" if args.session is not None else "*.jsonl"
        else:
            pattern = f"{session_desc}/subagents/agent-a*.jsonl"
        advice = ("verify the project directory and session id" if args.sessions else
                  "verify the project directory and session id; a directory "
                  "without a subagents/ subdirectory will always report this")
        filter_desc = (f" (positional filter {args.cell!r} matched none)"
                       if positional_miss else "")
        print(f"NO CELLS FOUND under {project} (glob: {pattern}){filter_desc} -- {advice}",
              file=sys.stderr)
        return 1

    any_past_cap = False
    any_incomplete_row = False
    for name, session_id, path, stats in rows:
        # PEAK, not current (CRITICAL fix): the binding rule re-dispatches a
        # past-cap cell from a FRESH context; a compacted cell's CURRENT
        # depth can look cheap again while still carrying the degraded
        # context the rule exists to catch. Both figures are still reported.
        past_cap = stats.peak > args.cap
        any_past_cap = any_past_cap or past_cap
        if stats.malformed or stats.turns == 0:
            any_incomplete_row = True
        marker = "  PAST-CAP" if past_cap else ""
        flag = "OVER" if past_cap else "ok"
        if path in parked:
            flag = "OVER,parked" if past_cap else "parked"
        # rung-a item (d): the CLI version SET, on the row itself. Sorted so the
        # line is stable, and SPAN is called out by name -- a set of size > 1 IS a
        # span, and the reader says so rather than leaving a comma to be noticed.
        versions = sorted(stats.cli_versions)
        if not versions:
            cli = "  cli=none-recorded"
        elif len(versions) == 1:
            cli = f"  cli={versions[0]}"
        else:
            cli = f"  cli=SPAN[{','.join(versions)}]"
        print(f"{name}  current={stats.current}  peak={stats.peak}  "
              f"turns={stats.turns}  session={session_id[:8]}{cli}{marker}  "
              f"age={ages[path]:.1f}h  flag={flag}")
        if stats.malformed:
            print(f"  ({stats.malformed} malformed line(s) skipped in "
                  f"{path.name})", file=sys.stderr)
        if stats.turns == 0:
            # A discovered transcript with NO usage-bearing request yet (the
            # normal shape right after dispatch, before the first response
            # lands) reads as current=0/peak=0 -- accurate as far as it
            # goes, but indistinguishable from "nothing usable could be
            # measured here" unless flagged; never presented as a clean,
            # complete reading.
            print(f"  (0 turns recorded for {name} -- no usage-bearing "
                  f"request yet in {path.name})", file=sys.stderr)

    if any_past_cap:
        return 2
    if unreadable or discovery_errors or any_incomplete_row:
        # A sweep with an unreadable transcript, an unparsed filename, a
        # directory-listing error, skipped malformed lines, or a zero-turn
        # row must never look like a clean (0) measurement -- 3 is the
        # distinct "incomplete" signal, separate from PAST-CAP (2, which
        # always wins when both conditions hold -- the dispatch-recipe's
        # fill pins that contract).
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
