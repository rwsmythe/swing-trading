"""cell_depth.py -- the DISPATCHER-READ context depth of implementer cells.

A dispatched cell (an Agent-tool subagent) can NEVER see its own context depth:
the UserPromptSubmit hook never fires for it, and it has no ``usage`` view of
its own turns.  The dispatcher CAN see it, because every assistant record in
the cell's transcript carries ``message.usage`` and

    depth = input_tokens + cache_read_input_tokens + cache_creation_input_tokens

is the context presented to the model on that turn.  The last record's value is
the cell's CURRENT depth; the maximum over the file is its high-water mark.
(coa-chess CHARC, 2026-09-07 -- ``docs/cell-depth-finding-coa.md``; reproduced
on this project's 37 cell transcripts: 24 peaked above 400K, 3 above 800K.)

Read-only, stdlib-only, ASCII output.  Transcripts live at
``~/.claude/projects/<project-slug>/<session-id>/subagents/agent-a*.jsonl``;
the slug is derived from the repo root (``C:\\Users\\x\\repo`` ->
``c--Users-x-repo``, matched case-insensitively).  A cell's identity is the
first text of its first record (the dispatch prompt), since older transcript
filenames carry only a hash.

Usage (the orchestrator's PRECONDITION before assigning work to a live cell,
and at every review-round gate):

    python scripts/cell_depth.py --live 12            # cells written in the last 12h
    python scripts/cell_depth.py --cap 400000 --live 6 # exit 1 if any listed cell exceeds the cap
    python scripts/cell_depth.py --all                 # every cell on disk, deepest first

Exit status: 0 = every listed cell is at or under --cap (default 400000);
1 = at least one listed cell exceeds it; 2 = no transcripts found for the repo.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CAP = 400_000
_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class CellDepth:
    path: Path
    peak: int
    current: int
    turns: int
    age_hours: float
    label: str

    @property
    def name(self) -> str:
        return self.path.name


def project_slug(repo_root: Path) -> str:
    """The claude-projects directory name for a repo root.

    ``C:\\Users\\x\\repo`` -> ``c--Users-x-repo``; POSIX ``/home/x/repo`` ->
    ``-home-x-repo``.  Every path separator and the drive colon become ``-``.
    """
    raw = str(repo_root)
    slug = re.sub(r"[:\\/]", "-", raw)
    # the drive letter is lower-cased in observed slugs; the rest keeps its case
    if re.match(r"^[A-Za-z]-", slug):
        slug = slug[0].lower() + slug[1:]
    return slug


def find_project_dirs(projects_dir: Path, repo_root: Path) -> list[Path]:
    """Every projects subdir whose name matches the repo's slug, case-insensitively.

    Case-insensitive because Windows filesystems are, and observed slugs differ
    from the memory-dir spelling only by the drive letter's case.
    """
    want = project_slug(repo_root).lower()
    if not projects_dir.is_dir():
        return []
    return sorted(p for p in projects_dir.iterdir()
                  if p.is_dir() and p.name.lower() == want)


def _first_text(message: dict) -> str | None:
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text
    return None


def read_cell(path: Path, *, now: float | None = None) -> CellDepth:
    """One cell's depth figures from its transcript; tolerant of a mid-write tail."""
    peak = cur = turns = 0
    label = ""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # a partial trailing line while the cell is still writing
            message = rec.get("message") if isinstance(rec, dict) else None
            if not isinstance(message, dict):
                continue
            if not label:
                text = _first_text(message)
                if text:
                    label = " ".join(text.split())[:72]
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            turns += 1
            cur = ((usage.get("input_tokens") or 0)
                   + (usage.get("cache_read_input_tokens") or 0)
                   + (usage.get("cache_creation_input_tokens") or 0))
            peak = max(peak, cur)
    stamp = now if now is not None else time.time()
    age_hours = max(0.0, (stamp - path.stat().st_mtime) / 3600.0)
    return CellDepth(path=path, peak=peak, current=cur, turns=turns,
                     age_hours=age_hours, label=label)


def scan(projects_dir: Path, repo_root: Path, *, now: float | None = None) -> list[CellDepth]:
    """Every cell transcript for the repo, deepest peak first.

    The glob MUST descend into ``subagents/`` -- a project-level glob misses the
    cells entirely (coa-chess undercounted one arc by 43% that way).
    """
    cells: list[CellDepth] = []
    for pdir in find_project_dirs(projects_dir, repo_root):
        for f in glob.glob(os.path.join(str(pdir), "*", "subagents", "agent-a*.jsonl")):
            cells.append(read_cell(Path(f), now=now))
    cells.sort(key=lambda c: c.peak, reverse=True)
    return cells


def format_rows(cells: list[CellDepth], cap: int) -> list[str]:
    rows = [f"{'peak':>9}  {'current':>9}  {'turns':>5}  {'age':>7}  flag  cell / dispatch prompt"]
    for c in cells:
        flag = "OVER" if c.peak > cap else "  ok"
        rows.append(f"{c.peak:>9,}  {c.current:>9,}  {c.turns:>5}  {c.age_hours:>6.1f}h  {flag}  "
                    f"{c.name[:24]}  {c.label}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP,
                        help=f"depth cap in tokens (default {DEFAULT_CAP})")
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument("--live", type=float, metavar="HOURS",
                     help="only cells whose transcript was written in the last HOURS")
    sel.add_argument("--all", action="store_true", help="every cell on disk (the default)")
    parser.add_argument("--projects-dir", default=None,
                        help="override ~/.claude/projects (tests)")
    parser.add_argument("--repo-root", default=None, help="override the repo root (tests)")
    args = parser.parse_args(argv)

    projects_dir = (Path(args.projects_dir) if args.projects_dir
                    else Path.home() / ".claude" / "projects")
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _REPO_ROOT
    cells = scan(projects_dir, repo_root)
    if not cells:
        print(f"no cell transcripts found under {projects_dir} for slug "
              f"{project_slug(repo_root)!r}")
        return 2
    if args.live is not None:
        cells = [c for c in cells if c.age_hours <= args.live]
        if not cells:
            print(f"no cells written in the last {args.live:g}h (cap {args.cap:,}); "
                  "nothing to check")
            return 0
    for row in format_rows(cells, args.cap):
        print(row)
    over = [c for c in cells if c.peak > args.cap]
    print(f"{len(cells)} cell(s); {len(over)} over the {args.cap:,} cap")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
