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
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# v1 thresholds -- keep in sync with tool-director-context.md section 4.2.
CLAUDE_MD_TOTAL_CHARS_MAX = 100_000
CLAUDE_MD_LINE3_CHARS_MAX = 9_000
CONTEXT_DOC_CHARS_MAX = 120_000
DOCS_MD_COUNT_MAX = 600
SESSION_ARTIFACT_AGE_DAYS_MAX = 14
MEMORY_FILE_COUNT_MAX = 80
# Comms mailbox (Stage 1): unread older than this many days -> ATTENTION.
COMMS_UNREAD_AGE_DAYS_MAX = 7
COMMS_ROLES = ("charc", "rd", "operator")

CONTEXT_DOCS = (
    "docs/orchestrator-context.md",
    "docs/research-director-context.md",
    "docs/tool-director-context.md",
    "docs/research-director-watch-standard.md",
    "docs/harness-architecture.md",
)
SESSION_ARTIFACT_GLOBS = (".copowers*", ".codex-review*")


def _chars(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace"))


def _msg_posted(path: Path) -> datetime | None:
    """Posted time from the leading UTC stamp in a role_mail filename.

    Filenames are '<yyyymmddTHHMMSSZ>-<from>-<slug>.md'. Falls back to mtime
    if the stamp cannot be parsed. Returns None only when both fail.
    """
    stamp = path.name.split("-", 1)[0]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            return None


def _scan_comms(comms_dir: Path, now: datetime) -> list[tuple[str, str]]:
    """Report rows (level, line) for the comms mailbox; pure + testable.

    Per-role unread counts are INFO; any unread older than
    COMMS_UNREAD_AGE_DAYS_MAX days fires ATTENTION; a nonzero operator inbox
    always gets its own awaiting-operator line. Missing comms/ -> single INFO.
    """
    if not comms_dir.is_dir():
        return [("INFO", "comms/: missing (skipped)")]
    rows: list[tuple[str, str]] = []
    for role in COMMS_ROLES:
        inbox = comms_dir / role / "inbox"
        msgs = sorted(inbox.glob("*.md")) if inbox.is_dir() else []
        read_dir = comms_dir / role / "read"
        read_n = len(sorted(read_dir.glob("*.md"))) if read_dir.is_dir() else 0
        rows.append(
            ("INFO", f"comms {role}: {len(msgs)} unread, {read_n} read"))
        posts = [p for p in (_msg_posted(m) for m in msgs) if p is not None]
        threshold = timedelta(days=COMMS_UNREAD_AGE_DAYS_MAX)
        if posts:
            oldest_td = now - min(posts)
            if oldest_td > threshold:  # strictly older than 7 days
                # ceil-days display so 7d12h reads as "8d", never "7d (>7d)";
                # ceil on the float so 7d+0.5s also rounds up.
                disp = math.ceil(oldest_td.total_seconds() / 86_400)
                rows.append((
                    "ATTENTION",
                    f"comms {role}: oldest unread is {disp}d old "
                    f"(>{COMMS_UNREAD_AGE_DAYS_MAX}d) -- drain or relay it",
                ))
        if role == "operator" and msgs:
            rows.append((
                "INFO",
                f"comms operator inbox: {len(msgs)} message(s) awaiting the "
                "operator's decision",
            ))
    return rows


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

    # Comms mailbox (Stage 1) -- pure helper, UTC clock for the stamp ages.
    for level, line in _scan_comms(root / "comms", datetime.now(UTC)):
        report(level, line)

    print("-" * 72)
    if attention:
        print(f"ATTENTION items: {len(attention)} -- phase-boundary action required")
        return 1
    print("all checks within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
