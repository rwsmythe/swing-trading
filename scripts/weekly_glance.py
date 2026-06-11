"""Weekly watch glance — research-director watch standard section 2.

Read-only over the shadow-expectancy export artifacts + the live DB
(mode=ro). Prints the week at a glance and flags the watch-standard
tripwires (T1/T2/T3/T6/T7) that the weekly tier can detect. ASCII-only
output (Windows cp1252 stdout). Never writes anything.

Usage (from the repo root):
    python scripts/weekly_glance.py [--db PATH] [--runs N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORTS = REPO_ROOT / "exports" / "research"

# T1 tolerance: newest artifact older than this many calendar days -> flag.
# (>2 trading sessions; 4 calendar days tolerates a normal weekend.)
T1_MAX_AGE_DAYS = 4

_FUNNEL_RE = re.compile(
    r"total_detections=(\d+) collapsed_duplicate=(\d+) unique_signals=(\d+)")
_UNATTR_RE = re.compile(r"total_unattributed=(\d+)")
_TRIGGER_RE = re.compile(r"trigger rate (\d+)/(\d+)")
_DIR_TS_RE = re.compile(r"shadow-expectancy-(\d{8}T\d{6})Z$")


def _risk_recon_tags() -> set[str]:
    from swing.trades.review import MISTAKE_TAGS  # editable install
    return set(MISTAKE_TAGS["risk"]) | set(MISTAKE_TAGS["reconciliation"])


def _epoch_leak_tags() -> set[str]:
    return {"CHASED", "NO_SETUP"}


def scan_artifacts(n_runs: int) -> list[str]:
    """Items 1-4: drumbeat liveness, unattributed, accrual, trigger rate."""
    flags: list[str] = []
    dirs = sorted(
        (d for d in EXPORTS.glob("shadow-expectancy-*") if d.is_dir()),
        key=lambda d: d.name, reverse=True,
    )[:n_runs]
    if not dirs:
        print("  NO shadow-expectancy artifacts found at all.")
        flags.append("T1: zero artifacts on disk -- drumbeat never ran?")
        return flags

    print(f"  {'run (UTC)':22} {'detections':>10} {'signals':>8} "
          f"{'unattrib':>9} {'trigger':>9}")
    rows: list[tuple[str, int, int, int, str]] = []
    for d in dirs:
        text = (d / "summary.md").read_text(encoding="utf-8") \
            if (d / "summary.md").exists() else ""
        fm = _FUNNEL_RE.search(text)
        um = _UNATTR_RE.search(text)
        tm = _TRIGGER_RE.search(text)
        det, sig = (int(fm.group(1)), int(fm.group(3))) if fm else (-1, -1)
        unattr = int(um.group(1)) if um else -1
        trig = f"{tm.group(1)}/{tm.group(2)}" if tm else "?"
        name = d.name.replace("shadow-expectancy-", "")
        rows.append((name, det, sig, unattr, trig))
        print(f"  {name:22} {det:>10} {sig:>8} {unattr:>9} {trig:>9}")

    # T1 — newest artifact age.
    m = _DIR_TS_RE.search(dirs[0].name)
    if m:
        newest = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(
            tzinfo=UTC)
        age_days = (datetime.now(UTC) - newest).days
        print(f"  newest artifact age: {age_days} day(s)")
        if age_days > T1_MAX_AGE_DAYS:
            flags.append(
                f"T1: newest artifact is {age_days} days old "
                f"(>{T1_MAX_AGE_DAYS}) -- drumbeat may be dead.")
    # T2 — unattributed must be zero in the NEWEST run (older artifacts may
    # legitimately predate a registry amendment; they are history, not a
    # live regression -- e.g. the pre-0026 runs show 42/42 unattributed).
    if rows and rows[0][3] > 0:
        flags.append(
            f"T2: newest run has {rows[0][3]} unattributed -- "
            "same-session root-cause.")
    # T3 — first priced trade (trigger numerator nonzero).
    priced = [r for r in rows if r[4] not in ("?",) and int(r[4].split("/")[0]) > 0]
    if priced:
        flags.append(
            "T3: trigger rate is NONZERO (" + priced[0][4] + " in "
            + priced[0][0] + ") -- if this is the FIRST priced trade, the "
            "golden-gate hand-walk is required before trusting accruals.")
    # Accrual pulse (informational).
    if len(rows) >= 2 and rows[0][2] >= 0 and rows[-1][2] >= 0:
        print(f"  accrual delta across shown runs: "
              f"{rows[-1][2]} -> {rows[0][2]} unique signals")
    return flags


def scan_live_trades(db_path: str) -> list[str]:
    """Item 5: this week's entries + epoch-integrity tags (T6/T7)."""
    flags: list[str] = []
    if not os.path.exists(db_path):
        flags.append(f"DB not found at {db_path} -- ran from the right box?")
        return flags
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)")}
        if "entry_intent" not in cols:
            flags.append("entry_intent column MISSING -- live DB pre-v27?")
            return flags
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        new = conn.execute(
            "SELECT ticker, entry_date, entry_intent, hypothesis_label "
            "FROM trades WHERE entry_date >= ? ORDER BY entry_date",
            (week_ago,)).fetchall()
        if not new:
            print("  no new trades this week.")
        for t, ed, intent, label in new:
            print(f"  NEW {ed} {t:6} intent={intent!r} label={label!r}")
            if intent is None:
                flags.append(
                    f"epoch contract: {t} ({ed}) has NULL entry_intent -- "
                    "set it (entry/review form or backfill-intent).")
            elif intent == "hypothesis_test_by_design":
                flags.append(
                    f"T7 check: {t} ({ed}) is by_design -- legitimate ONLY "
                    "if an H2/H4 program fire; verify the label.")
        # T6/T7 — tags on standard-intent trades (new epoch only; the 16
        # pre-epoch by_design trades can never match this filter).
        risk_recon = _risk_recon_tags()
        leak = _epoch_leak_tags()
        std = conn.execute(
            "SELECT ticker, entry_date, mistake_tags FROM trades "
            "WHERE entry_intent = 'standard' AND mistake_tags IS NOT NULL",
        ).fetchall()
        for t, ed, raw in std:
            try:
                tags = set(json.loads(raw))
            except (ValueError, TypeError):
                continue
            hit_rr = sorted(tags & risk_recon)
            hit_lk = sorted(tags & leak)
            if hit_rr:
                flags.append(
                    f"T6: risk/reconciliation tag(s) {hit_rr} on STANDARD "
                    f"trade {t} ({ed}) -- the retired slip class recurred.")
            if hit_lk:
                flags.append(
                    f"T7: {hit_lk} on STANDARD trade {t} ({ed}) -- the old "
                    "pattern leaking into the new epoch.")
    finally:
        conn.close()
    return flags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.expanduser(
        "~/swing-data/swing.db"))
    ap.add_argument("--runs", type=int, default=7,
                    help="how many recent nightly artifacts to show")
    args = ap.parse_args()

    print("== weekly glance: shadow-expectancy drumbeat ==")
    flags = scan_artifacts(args.runs)
    print()
    print("== weekly glance: live trades (new epoch) ==")
    flags += scan_live_trades(args.db)
    print()
    if flags:
        print("ATTENTION (" + str(len(flags)) + "):")
        for f in flags:
            print("  ! " + f)
        print("Escalate per docs/research-director-watch-standard.md "
              "section 4.")
    else:
        print("WEEKLY GLANCE: all clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
