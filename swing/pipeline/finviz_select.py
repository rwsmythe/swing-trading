"""Finviz inbox CSV selection with date-from-filename + ambiguity check."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

_FILENAME_DATE_RE = re.compile(r"(\d{1,2})([A-Za-z]{3})(\d{4})")
_MONTHS = {
    m: i + 1 for i, m in enumerate([
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ])
}


class NoFilesError(Exception):
    """Inbox is empty (excluding rejected/)."""


class AmbiguousInboxError(Exception):
    """Multiple files share the same date stamp."""


def _parse_filename_date(name: str) -> date | None:
    m = _FILENAME_DATE_RE.search(name)
    if not m:
        return None
    day, mon_str, year = m.group(1), m.group(2).lower(), m.group(3)
    if mon_str not in _MONTHS:
        return None
    try:
        return date(int(year), _MONTHS[mon_str], int(day))
    except ValueError:
        return None


def _file_key(f: Path) -> float:
    """Sort key: parsed filename-date as noon timestamp if parseable, else mtime.

    Spec §5.1 step 2: "by filename date if parseable else by mtime, newest wins" —
    a unified per-file key so an undated-but-newer file can beat an old dated file
    (adversarial review Batch 4 Round 1 Major 2)."""
    d = _parse_filename_date(f.name)
    if d is not None:
        return datetime(d.year, d.month, d.day, 12, 0, 0).timestamp()
    return f.stat().st_mtime


def select_csv(inbox_dir: Path) -> Path:
    candidates = [
        f for f in inbox_dir.glob("*.csv")
        if f.is_file() and "rejected" not in f.parts
    ]
    if not candidates:
        raise NoFilesError(f"No CSV files in {inbox_dir}")

    keyed = sorted(
        ((f, _file_key(f)) for f in candidates),
        key=lambda kv: kv[1], reverse=True,
    )
    max_key = keyed[0][1]
    tied_at_max = [f for f, k in keyed if k == max_key]

    # Ambiguity is only meaningful when multiple DATED files share the winning
    # date — two undated files coincidentally tying on mtime resolve by
    # stable-sort order (still deterministic given a stable directory listing).
    dated_at_max = [f for f in tied_at_max if _parse_filename_date(f.name) is not None]
    if len(dated_at_max) > 1:
        d = _parse_filename_date(dated_at_max[0].name)
        raise AmbiguousInboxError(
            f"Multiple files for date {d}: {sorted(f.name for f in dated_at_max)}"
        )
    return tied_at_max[0]
