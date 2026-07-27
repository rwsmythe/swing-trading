"""One-shot 21-D migration: file the retired per-generation orchestrator comms.

The 21-D convention change makes ``comms/orchestrator/`` a SINGULAR mailbox
(``{inbox,read}``). The historical per-generation trees
(``comms/orchestrator/<session_id>/{inbox,read}``) are the record of everything
that was ever said to an orchestrator generation, so they are MOVED, never
deleted: each one becomes ``comms/orchestrator/_archive/<session_id>/...``.

    **HISTORY IS NEVER DELETED (binding).** Nothing here unlinks a file. The
    only removals are EMPTY directory shells left behind after their files have
    been relocated -- reported line by line, and only when the directory really
    is empty.

**DRY RUN IS THE DEFAULT.** A bare run prints exactly what it would move and
changes nothing; ``--execute`` performs the moves and then VERIFIES the result
(every relocated file present at its planned destination with an unchanged
sha256, and no file lost). ``comms/`` is gitignored, so this migration is a
LOCAL DATA operation the operator runs deliberately -- it does not travel with
the merge, and the suite never runs it against the real tree.

The generation list is ENUMERATED FROM DISK at run time, never hard-coded: a
hard-coded list orphans every generation it forgot (the brief named five; the
live tree held eight) and rots further with each new session.

The LIVE generation (``--live-session <session_id>``) is NOT history. Its
``inbox/`` and ``read/`` messages are adopted into the singular
``comms/orchestrator/{inbox,read}`` so the current orchestrator keeps its own
mail; anything else it carries is archived like the rest.

Usage (from the repo root):
    python scripts/archive_comms_generations.py                      # dry run
    python scripts/archive_comms_generations.py --live-session <sid> # dry run
    python scripts/archive_comms_generations.py --live-session <sid> --execute

ASCII-only console output (Windows cp1252 stdout gotcha); files are moved
byte-for-byte and never rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Names directly under comms/orchestrator/ that are NOT generations: the two
# singular mailbox dirs and the archive itself. Anything else that is a
# directory is a retired generation.
RESERVED_NAMES = ("inbox", "read", "_archive")

# The adopted-into-the-singular-mailbox subdirectories of the LIVE generation.
ADOPTED_SUBDIRS = ("inbox", "read")

# A session_id becomes a directory name, so it must be a safe single path
# segment. INTENTIONAL COPY of comms_session_registry.is_valid_session_id's rule
# -- kept local so this one-shot helper has no import dependency on the registry
# (which 21-D narrowed to role presence); keep the two in sync if the rule moves.
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9._-]+")


def is_safe_session_id(session_id: str) -> bool:
    """True iff session_id is a safe single path segment (no traversal/seps)."""
    if not isinstance(session_id, str) or not session_id:
        return False
    if session_id in (".", ".."):
        return False
    if "/" in session_id or "\\" in session_id:
        return False
    if session_id != Path(session_id).name:
        return False
    return bool(_SESSION_ID_RE.fullmatch(session_id))


@dataclass
class Plan:
    """What the migration WOULD do (the dry-run product)."""

    orchestrator_dir: Path
    generations: list[str] = field(default_factory=list)
    # (src, dest, kind) where kind is 'archive' or 'adopt'
    moves: list[tuple[Path, Path, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.moves and not self.generations


def _nonclobbering_dest(dest: Path, taken: set[Path]) -> Path:
    """A destination path that collides with NOTHING (on disk or in this plan).

    Suffixes ``-2``, ``-3``, ... before the extension. An existing archived file
    of the same name is NEVER overwritten -- the same discipline role_mail's ack
    uses (_unique_dest): relocating history must not destroy history.
    """
    if not dest.exists() and dest not in taken:
        return dest
    stem, ext = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}-{n}{ext}")
        if not candidate.exists() and candidate not in taken:
            return candidate
        n += 1


def _generation_dirs(orchestrator_dir: Path) -> list[Path]:
    """Every per-generation directory ON DISK right now (sorted, run-time)."""
    if not orchestrator_dir.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(orchestrator_dir.iterdir()):
        if not child.is_dir():
            continue  # a stray file is not a generation
        if child.name in RESERVED_NAMES:
            continue
        out.append(child)
    return out


def build_plan(comms_root: Path, live_session: str | None = None) -> Plan:
    """Enumerate the tree and compute every (src -> dest) move. Pure/read-only."""
    orchestrator_dir = Path(comms_root) / "orchestrator"
    plan = Plan(orchestrator_dir=orchestrator_dir)
    archive_dir = orchestrator_dir / "_archive"
    taken: set[Path] = set()
    for gen_dir in _generation_dirs(orchestrator_dir):
        sid = gen_dir.name
        plan.generations.append(sid)
        for src in sorted(p for p in gen_dir.rglob("*") if p.is_file()):
            rel = src.relative_to(gen_dir)
            kind = "archive"
            dest_base = archive_dir / sid / rel
            if (live_session is not None and sid == live_session
                    and len(rel.parts) == 2 and rel.parts[0] in ADOPTED_SUBDIRS):
                # the LIVE generation's own mail is not history -- it joins the
                # singular mailbox the orchestrator now drains.
                kind = "adopt"
                dest_base = orchestrator_dir / rel.parts[0] / rel.parts[1]
            dest = _nonclobbering_dest(dest_base, taken)
            taken.add(dest)
            plan.moves.append((src, dest, kind))
    return plan


def _digests(paths: list[Path]) -> dict[Path, str]:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _prune_empty_dirs(gen_dir: Path) -> list[Path]:
    """Remove directory shells left EMPTY after the moves (never a file).

    Bottom-up, and each rmdir is guarded by "the directory is empty" -- so a
    file that failed to move keeps its whole parent chain alive rather than
    being silently orphaned.
    """
    removed: list[Path] = []
    for path in sorted((p for p in gen_dir.rglob("*") if p.is_dir()),
                       key=lambda p: len(p.parts), reverse=True):
        try:
            if not any(path.iterdir()):
                path.rmdir()
                removed.append(path)
        except OSError:
            continue
    try:
        if gen_dir.is_dir() and not any(gen_dir.iterdir()):
            gen_dir.rmdir()
            removed.append(gen_dir)
    except OSError:
        pass
    return removed


def _rel(path: Path, comms_root: Path) -> str:
    try:
        return path.relative_to(comms_root).as_posix()
    except ValueError:
        return str(path)


def run(comms_root: Path, live_session: str | None, execute: bool,
        out=None, err=None) -> int:
    """Print the plan; perform + verify it only when execute is True.

    ``out``/``err`` default to None and are resolved to sys.stdout/sys.stderr
    HERE, not in the signature -- a default bound at import time would capture
    the pre-redirect streams (invisible to pytest's capsys and to any caller
    that redirects).
    """
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    comms_root = Path(comms_root)
    if live_session is not None and not is_safe_session_id(live_session):
        print(f"error: refusing unsafe --live-session {live_session!r}; it must "
              "be a plain session_id path segment. Nothing was moved.", file=err)
        return 1

    plan = build_plan(comms_root, live_session)

    if live_session is not None and live_session not in plan.generations:
        print(f"error: --live-session {live_session!r} is not a generation "
              f"directory under {_rel(plan.orchestrator_dir, comms_root)}/ "
              f"(found: {', '.join(plan.generations) or 'none'}). Nothing was "
              "moved.", file=err)
        return 1

    header = "EXECUTE" if execute else "DRY RUN"
    print(f"[archive-comms-generations] {header} over {comms_root}", file=out)
    if plan.is_empty:
        print("  nothing to migrate: no per-generation orchestrator "
              "directories on disk.", file=out)
        return 0

    print(f"  generations on disk ({len(plan.generations)}): "
          f"{', '.join(plan.generations)}", file=out)
    if live_session is not None:
        print(f"  live generation: {live_session} -- its inbox/ + read/ mail is "
              "ADOPTED into the singular comms/orchestrator/{inbox,read} "
              "(the live generation is not history).", file=out)
    else:
        print("  no --live-session given: EVERY generation is treated as "
              "history.", file=out)
    print(f"  {len(plan.moves)} file(s) to move:", file=out)
    for src, dest, kind in plan.moves:
        print(f"    [{kind}] {_rel(src, comms_root)}  ->  "
              f"{_rel(dest, comms_root)}", file=out)

    if not execute:
        print("  DRY RUN: nothing was moved. Re-run with --execute to perform "
              "it.", file=out)
        return 0

    before = _digests([src for src, _dest, _kind in plan.moves])
    for src, dest, _kind in plan.moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(src), str(dest))

    # D3 verification: every relocated file is present at its destination with
    # an UNCHANGED sha256 (intact), and readable. Reported, not assumed.
    problems: list[str] = []
    for src, dest, _kind in plan.moves:
        if not dest.is_file():
            problems.append(f"missing after move: {_rel(dest, comms_root)}")
            continue
        try:
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        except OSError as exc:
            problems.append(f"unreadable after move: {_rel(dest, comms_root)} "
                            f"({exc})")
            continue
        if digest != before[src]:
            problems.append(f"content changed: {_rel(dest, comms_root)}")
        if src.exists():
            problems.append(f"source still present: {_rel(src, comms_root)}")

    for sid in plan.generations:
        for removed in _prune_empty_dirs(plan.orchestrator_dir / sid):
            print(f"  removed empty shell {_rel(removed, comms_root)}/",
                  file=out)

    if problems:
        print("  VERIFICATION FAILED -- " + "; ".join(problems), file=err)
        return 1
    print(f"  VERIFIED: {len(plan.moves)} file(s) relocated intact "
          "(sha256-matched, readable); zero files deleted.", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Archive the retired per-generation orchestrator comms "
                    "trees (21-D). Dry run by default.")
    p.add_argument("--comms-root", default=None,
                   help="mailbox root (default: <repo>/comms)")
    p.add_argument("--live-session", default=None,
                   help="the CURRENTLY LIVE orchestrator session_id; its mail "
                        "is adopted into the singular inbox/read instead of "
                        "being archived")
    p.add_argument("--execute", action="store_true",
                   help="actually perform the moves (default: dry run)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.comms_root) if args.comms_root else _REPO_ROOT / "comms"
    return run(root, args.live_session, args.execute)


if __name__ == "__main__":
    sys.exit(main())
