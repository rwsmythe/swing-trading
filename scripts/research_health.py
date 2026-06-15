"""Research data-collection-health probe (Phase 18 Arc 18-D, SCRIPT-FIRST).

Read-only roll-up of the 7 research data-collection-integrity checks in one
glance (the integrity SUPERSET of scripts/weekly_glance.py). Mirrors
scripts/tool_health.py: opens its OWN mode=ro connection, ASCII output, a --json
machine surface. On every SUCCESSFUL run (a readable DB) it ALSO writes the
conformant §3 status envelope ATOMICALLY to exports/research/health/latest.json
-- the artifact 18-F's research stoplight consumes (grey until 18-D writes a
conformant fresh artifact there). A missing/unreadable DB prints an error and
exits 1 WITHOUT writing (the monitor cannot assess health without the DB; it
does NOT overwrite a prior artifact with a synthetic state -- the 18-F staleness
gate greys the stale artifact on its own). ASCII-only (Windows cp1252 stdout).
Never writes the measurement DB.

Usage (from the repo root):
    python scripts/research_health.py [--db PATH] [--json] [--out PATH]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _resolve_now() -> datetime | None:
    """The clock seam (test-injectable). None -> the aggregator's default."""
    return None


def _resolve_out_path(args) -> Path:
    """Resolve the latest.json write destination.

    PRODUCTION default (no --out) = the shared accessor
    stoplights.research_health_artifact_path() (the 18-F providers call the SAME
    accessor; single source -- the contract path is HARDWIRED for any real run).
    --out is an EXPLICIT, operator-visible override used ONLY by the subprocess
    ASCII test (a separate process cannot inherit an in-process accessor
    monkeypatch). It defaults to None -> the accessor, so an ordinary
    `python scripts/research_health.py` ALWAYS writes the contract path
    exports/research/health/latest.json. NOT a hidden runtime env override.
    """
    if args.out is not None:
        return Path(args.out)
    from swing.monitoring import stoplights
    return stoplights.research_health_artifact_path()


def _write_latest_json_atomic(envelope: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # tmp in the SAME directory (os.replace requires same filesystem -- the
    # Windows OSError 18 gotcha) then atomic replace.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _render_ascii(status) -> str:
    lines: list[str] = []
    lines.append("== research health ==")
    lines.append(f"  generated: {status.generated_ts}")
    lines.append(f"  overall:   [{status.overall.upper()}]")
    lines.append("")
    for c in status.checks:
        lines.append(f"  [{c.status.upper()}] {c.key}: {c.summary}")
        if c.detail:
            lines.append(f"      {c.detail}")
    lines.append("")
    if status.overall != "green":
        attention = [c for c in status.checks if c.status != "green"]
        lines.append(f"ATTENTION ({len(attention)}):")
        for c in attention:
            lines.append(f"  ! [{c.status.upper()}] {c.key}: {c.summary}")
    else:
        lines.append("RESEARCH HEALTH: all clear.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.expanduser("~/swing-data/swing.db"))
    ap.add_argument("--json", action="store_true",
                    help="emit the monitor-status JSON envelope and exit 0")
    ap.add_argument("--out", default=None,
                    help="explicit latest.json write path (test-isolation "
                         "override; defaults to the shared contract path)")
    args = ap.parse_args(argv)

    from swing.config import Config
    from swing.monitoring.research_health import compute_research_health

    cfg = Config.from_defaults()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"DB not found at {db_path} -- ran from the right box?")
        return 1

    out_path = _resolve_out_path(args)
    # exports_root is derived from the SAME accessor/override so an in-process
    # monkeypatch (or --out) redirects BOTH the manifest reads AND the artifact
    # write consistently (single source).
    exports_root = out_path.parent.parent

    # Codex R3 MAJOR #5 + R6 MAJOR #2: an unreadable/corrupt DB (not just an
    # absent path) must print a concise operator error + exit 1 WITHOUT writing.
    # The DB-OPEN probe is SEPARATE from compute_research_health: only the open
    # (a SELECT 1 against the file header) is wrapped, so a non-schema
    # OperationalError raised INSIDE a check (which the monitor intentionally
    # re-raises) PROPAGATES rather than being masked as "DB unreadable".
    ro_uri = db_path.as_uri() + "?mode=ro"
    conn = None
    try:
        conn = sqlite3.connect(ro_uri, uri=True, timeout=2.0)
        # Probe sqlite_master (Codex R7 MAJOR #1): SELECT 1 does NOT force SQLite
        # to read the file header, so a corrupt non-SQLite file would pass it and
        # then traceback inside a check. Reading sqlite_master forces the header/
        # schema read -> a corrupt file raises HERE and is handled.
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    except sqlite3.DatabaseError as exc:
        if conn is not None:
            conn.close()
        print(f"DB at {db_path} is unreadable: {exc} -- ran from the right box?")
        return 1
    try:
        status = compute_research_health(
            conn, cfg=cfg, exports_root=exports_root, now=_resolve_now())
    finally:
        conn.close()

    # Write the conformant envelope ATOMICALLY in BOTH the ASCII and --json
    # paths (so the stoplight lights regardless of how the operator runs it).
    _write_latest_json_atomic(status.to_dict(), out_path)

    if args.json:
        print(json.dumps(status.to_dict(), indent=2))
        return 0  # machine surface: always exit 0 so a consumer parses cleanly

    print(_render_ascii(status))
    return 0 if status.overall == "green" else 1


if __name__ == "__main__":
    sys.exit(main())
