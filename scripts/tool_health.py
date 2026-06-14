"""Operational tool-health probe (Phase 18 Arc 18-E).

Read-only roll-up of the data-collection-enabling signals -- pipeline-run
health, Schwab token TTL, OHLCV + weather freshness -- in one glance. Mirrors
scripts/weekly_glance.py: opens its OWN mode=ro connection, ASCII output, a
--json machine surface. Never writes anything. ASCII-only (Windows cp1252
stdout).

Usage (from the repo root):
    python scripts/tool_health.py [--db PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _resolve_now() -> datetime | None:
    """The clock seam (test-injectable). None -> the aggregator's default."""
    return None


def _render_ascii(status) -> str:
    lines: list[str] = []
    lines.append("== tool health ==")
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
        lines.append("TOOL HEALTH: all clear.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.expanduser("~/swing-data/swing.db"))
    ap.add_argument("--json", action="store_true",
                    help="emit the monitor-status JSON envelope and exit 0")
    args = ap.parse_args(argv)

    from swing.config import Config
    from swing.monitoring.tool_health import compute_tool_health

    cfg = Config.from_defaults()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found at {db_path} -- ran from the right box?")
        return 1

    ro_uri = db_path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(ro_uri, uri=True, timeout=2.0)
    try:
        status = compute_tool_health(
            conn,
            cfg=cfg,
            prices_cache_dir=cfg.paths.prices_cache_dir,
            now=_resolve_now(),
        )
    finally:
        conn.close()

    if args.json:
        print(json.dumps(status.to_dict(), indent=2))
        return 0  # machine surface: always exit 0 so a consumer parses cleanly

    print(_render_ascii(status))
    return 0 if status.overall == "green" else 1


if __name__ == "__main__":
    sys.exit(main())
