"""Harness-hygiene probe (CHARC charter section 4.2, v1).

Read-only measurement of the team-harness artifacts: CLAUDE.md weight,
live charter/context-doc weight, docs/ brief-corpus size, root session
artifacts, exports/ dated dirs, the auto-memory dir, and the research-output
size ceilings (exports/research/ + research/harness/). Prints an ASCII
report; exits 1 if any ATTENTION threshold fires, else 0.

This probe REPORTS form (weight, age, count, size). It never deletes and it
makes no content judgments -- disposal/compaction are phase-boundary
proposals routed to the owning role per the charter's custodian-of-form
boundary. Thresholds are calibrated in docs/tool-director-context.md
section 4.2; amend them there (dated) before changing them here.

Usage: python scripts/harness_probe.py [--root PATH] [--memory-dir PATH]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# v1 thresholds -- keep in sync with tool-director-context.md section 4.2.
CLAUDE_MD_TOTAL_CHARS_MAX = 100_000
# Reconciled 2026-09-14 to the orchestrator-context trigger table (was 9,000;
# the probe read OK on 09-08 while the operative trigger was OVER).
CLAUDE_MD_LINE3_CHARS_MAX = 2_000
# The Gotchas section (## Gotchas -> next top-level "## " header or EOF) and
# its per-bullet cap -- added 2026-09-14, the orchestrator-context caps, now
# MEASURED (previously invisible to the probe entirely).
CLAUDE_MD_GOTCHAS_CHARS_MAX = 55_000
CLAUDE_MD_GOTCHA_BULLET_CHARS_MAX = 700
CONTEXT_DOC_CHARS_MAX = 120_000
DOCS_MD_COUNT_MAX = 600
SESSION_ARTIFACT_AGE_DAYS_MAX = 14
MEMORY_FILE_COUNT_MAX = 80
# Comms mailbox (Stage 1): unread older than this many days -> ATTENTION.
COMMS_UNREAD_AGE_DAYS_MAX = 7
# Every singular-inbox role (21-D: the orchestrator became one, and its inbox
# now SURVIVES a generation rollover -- precisely when an undrained message can
# sit unnoticed, so the probe must cover it).
COMMS_ROLES = ("charc", "rd", "operator", "orchestrator")
# Research-output size ceilings (D18/H2, v1 -- a forward regrowth guard; both
# dirs sit at ~MB-scale at calibration time so this is quiet at baseline).
RESEARCH_SIZE_TARGETS_MB_MAX = (
    ("exports/research", 500),
    ("research/harness", 200),
)

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


def _claude_md_checks(root: Path) -> list[tuple[str, str]]:
    """Report rows (level, line) for CLAUDE.md weight + the Gotchas section.

    Pure + testable (root explicit). Missing CLAUDE.md -> a single ATTENTION
    row, never a crash. Total chars + line-3 chars are always reported; the
    Gotchas section (from the "## Gotchas" line to the next top-level "## "
    header, or EOF) additionally reports its own char total and its
    top-level bullet ("- " line) count, naming the five largest bullets over
    CLAUDE_MD_GOTCHA_BULLET_CHARS_MAX as INFO lines. A missing "## Gotchas"
    header reports INFO "section not found" and skips the section-specific
    rows -- never a crash.
    """
    claude_md = root / "CLAUDE.md"
    if not claude_md.is_file():
        return [("ATTENTION", "CLAUDE.md missing")]

    text = claude_md.read_text(encoding="utf-8", errors="replace")
    total = len(text)
    lines = text.splitlines()
    line3 = len(lines[2]) if len(lines) >= 3 else 0

    rows: list[tuple[str, str]] = []
    level = "ATTENTION" if total > CLAUDE_MD_TOTAL_CHARS_MAX else "OK"
    rows.append((level, f"CLAUDE.md total chars: {total:,} (max {CLAUDE_MD_TOTAL_CHARS_MAX:,})"))
    level = "ATTENTION" if line3 > CLAUDE_MD_LINE3_CHARS_MAX else "OK"
    rows.append((level, f"CLAUDE.md line-3 chars: {line3:,} (max {CLAUDE_MD_LINE3_CHARS_MAX:,})"))

    gotchas_start: int | None = None
    gotchas_end = len(lines)
    for i, ln in enumerate(lines):
        if gotchas_start is None:
            if ln == "## Gotchas":
                gotchas_start = i
            continue
        if ln.startswith("## "):
            gotchas_end = i
            break

    if gotchas_start is None:
        rows.append(("INFO", "CLAUDE.md Gotchas section not found"))
        return rows

    section_lines = lines[gotchas_start:gotchas_end]
    section_chars = len("\n".join(section_lines))
    level = "ATTENTION" if section_chars > CLAUDE_MD_GOTCHAS_CHARS_MAX else "OK"
    rows.append((
        level,
        f"CLAUDE.md Gotchas section chars: {section_chars:,} "
        f"(max {CLAUDE_MD_GOTCHAS_CHARS_MAX:,})",
    ))

    # Top-level bullets only: a line starting with "- " inside the section.
    # "###" subheaders and blockquote ("> ") lines are not bullets.
    bullets = [ln for ln in section_lines if ln.startswith("- ")]
    over = [ln for ln in bullets if len(ln) > CLAUDE_MD_GOTCHA_BULLET_CHARS_MAX]
    level = "ATTENTION" if over else "OK"
    rows.append((
        level,
        f"CLAUDE.md Gotchas bullets: {len(bullets)}, "
        f"over {CLAUDE_MD_GOTCHA_BULLET_CHARS_MAX}: {len(over)}",
    ))
    if over:
        for b in sorted(over, key=len, reverse=True)[:5]:
            rows.append(("INFO", f"{len(b)} {b[:60]}"))

    return rows


def _dir_size_bytes(path: Path) -> int:
    """Total byte size of path, recursing via stdlib os.walk (NO du subprocess
    -- Windows-safe). Returns 0 for a missing/non-directory path (never
    raises). A per-entry stat() failure (permission error, broken symlink,
    a file removed mid-walk) is skipped, not fatal -- the probe stays
    defensive per the report-never-raise contract.
    """
    if not path.is_dir():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                continue
    return total


def _research_size_checks(root: Path) -> list[tuple[str, str]]:
    """Report rows (level, line) for the research-output size ceilings.

    Pure + testable (root explicit). Each target is ALWAYS reported as an
    INFO-or-ATTENTION line naming its measured size; ATTENTION fires only
    when the measured size STRICTLY exceeds its v1 ceiling (a forward
    regrowth guard -- quiet at the current ~MB-scale baseline). A missing
    directory reports 0.0 MB, never raises (bounded to the two named dirs
    only -- never the whole repo / reference/ / .git / .worktrees).
    """
    rows: list[tuple[str, str]] = []
    for rel, max_mb in RESEARCH_SIZE_TARGETS_MB_MAX:
        size_mb = _dir_size_bytes(root / rel) / 1_048_576
        level = "ATTENTION" if size_mb > max_mb else "OK"
        rows.append((level, f"{rel}/: {size_mb:.1f} MB (max {max_mb} MB)"))
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

    # CLAUDE.md weight + Gotchas section -- pure helper, root-explicit.
    for level, line in _claude_md_checks(root):
        report(level, line)

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

    # Research-output size ceilings (D18/H2) -- pure helper, forward regrowth guard.
    for level, line in _research_size_checks(root):
        report(level, line)

    print("-" * 72)
    if attention:
        print(f"ATTENTION items: {len(attention)} -- phase-boundary action required")
        return 1
    print("all checks within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
