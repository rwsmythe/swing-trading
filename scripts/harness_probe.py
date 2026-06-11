"""Harness-hygiene probe (CHARC charter section 4.2, v1).

Read-only measurement of the team-harness artifacts: CLAUDE.md weight,
live charter/context-doc weight, docs/ brief-corpus size, root session
artifacts, exports/ dated dirs, and the auto-memory dir. Prints an ASCII
report; exits 1 if any ATTENTION threshold fires, else 0.

This probe REPORTS form (weight, age, count). It never deletes and it
makes no content judgments -- disposal/compaction are phase-boundary
proposals routed to the owning role per the charter's custodian-of-form
boundary. Thresholds are calibrated in docs/tool-director-context.md
section 4.2; amend them there (dated) before changing them here.

Usage: python scripts/harness_probe.py [--root PATH] [--memory-dir PATH]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# v1 thresholds -- keep in sync with tool-director-context.md section 4.2.
CLAUDE_MD_TOTAL_CHARS_MAX = 100_000
CLAUDE_MD_LINE3_CHARS_MAX = 9_000
CONTEXT_DOC_CHARS_MAX = 120_000
DOCS_MD_COUNT_MAX = 600
SESSION_ARTIFACT_AGE_DAYS_MAX = 14
MEMORY_FILE_COUNT_MAX = 80

CONTEXT_DOCS = (
    "docs/orchestrator-context.md",
    "docs/research-director-context.md",
    "docs/tool-director-context.md",
    "docs/research-director-watch-standard.md",
)
SESSION_ARTIFACT_GLOBS = (".copowers*", ".codex-review*")


def _chars(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    parser.add_argument(
        "--memory-dir",
        default=str(
            Path.home()
            / ".claude/projects/c--Users-rwsmy-swing-trading/memory"
        ),
        help="auto-memory dir (skipped with INFO if missing)",
    )
    args = parser.parse_args()
    root = Path(args.root)
    now = datetime.now()
    attention: list[str] = []

    def report(level: str, line: str) -> None:
        print(f"[{level}] {line}")
        if level == "ATTENTION":
            attention.append(line)

    print(f"harness probe v1 -- {now:%Y-%m-%d %H:%M} -- root={root.resolve()}")
    print("-" * 72)

    # CLAUDE.md weight
    claude_md = root / "CLAUDE.md"
    if claude_md.is_file():
        total = _chars(claude_md)
        lines = claude_md.read_text(encoding="utf-8", errors="replace").splitlines()
        line3 = len(lines[2]) if len(lines) >= 3 else 0
        level = "ATTENTION" if total > CLAUDE_MD_TOTAL_CHARS_MAX else "OK"
        report(level, f"CLAUDE.md total chars: {total:,} (max {CLAUDE_MD_TOTAL_CHARS_MAX:,})")
        level = "ATTENTION" if line3 > CLAUDE_MD_LINE3_CHARS_MAX else "OK"
        report(level, f"CLAUDE.md line-3 chars: {line3:,} (max {CLAUDE_MD_LINE3_CHARS_MAX:,})")
    else:
        report("ATTENTION", "CLAUDE.md missing")

    # Live charter / context docs
    for rel in CONTEXT_DOCS:
        doc = root / rel
        if not doc.is_file():
            report("INFO", f"{rel}: missing (skipped)")
            continue
        size = _chars(doc)
        level = "ATTENTION" if size > CONTEXT_DOC_CHARS_MAX else "OK"
        report(level, f"{rel}: {size:,} chars (max {CONTEXT_DOC_CHARS_MAX:,})")

    # docs/ corpus
    docs_dir = root / "docs"
    md_files = sorted(docs_dir.glob("*.md")) if docs_dir.is_dir() else []
    briefs = [p for p in md_files if "brief" in p.name.lower()]
    total_mb = sum(p.stat().st_size for p in md_files) / 1_048_576
    level = "ATTENTION" if len(md_files) > DOCS_MD_COUNT_MAX else "OK"
    report(
        level,
        f"docs/*.md corpus: {len(md_files)} files ({len(briefs)} brief-named, "
        f"{total_mb:.1f} MB; max {DOCS_MD_COUNT_MAX} files)",
    )

    # Root session artifacts
    artifacts = [p for g in SESSION_ARTIFACT_GLOBS for p in root.glob(g)]
    stale_cutoff = now - timedelta(days=SESSION_ARTIFACT_AGE_DAYS_MAX)
    stale = [
        p for p in artifacts
        if datetime.fromtimestamp(p.stat().st_mtime) < stale_cutoff
    ]
    if stale:
        names = ", ".join(p.name for p in stale[:5])
        report(
            "ATTENTION",
            f"root session artifacts: {len(stale)} older than "
            f"{SESSION_ARTIFACT_AGE_DAYS_MAX}d of {len(artifacts)} total ({names})",
        )
    else:
        report("OK", f"root session artifacts: {len(artifacts)}, none stale")

    # exports/ dated dirs (register item D3 -- count only, no threshold)
    exports_dir = root / "exports"
    if exports_dir.is_dir():
        dated = [p for p in exports_dir.iterdir() if p.is_dir() and p.name != "research"]
        research_dir = exports_dir / "research"
        research = (
            [p for p in research_dir.iterdir() if p.is_dir()]
            if research_dir.is_dir()
            else []
        )
        report("INFO", f"exports/ dated dirs: {len(dated)} (+{len(research)} research) -- D3")
    else:
        report("INFO", "exports/: missing (skipped)")

    # Auto-memory dir
    memory_dir = Path(args.memory_dir)
    if memory_dir.is_dir():
        mem_files = [p for p in memory_dir.iterdir() if p.is_file()]
        level = "ATTENTION" if len(mem_files) > MEMORY_FILE_COUNT_MAX else "OK"
        report(level, f"memory dir: {len(mem_files)} files (max {MEMORY_FILE_COUNT_MAX})")
    else:
        report("INFO", f"memory dir not found at {memory_dir} (skipped)")

    print("-" * 72)
    if attention:
        print(f"ATTENTION items: {len(attention)} -- phase-boundary action required")
        return 1
    print("all checks within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
