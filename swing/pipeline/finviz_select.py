"""Finviz inbox CSV selection with date-from-filename + ambiguity check."""
from __future__ import annotations

import re
from datetime import date
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


def select_csv(inbox_dir: Path) -> Path:
    candidates = [
        f for f in inbox_dir.glob("*.csv")
        if f.is_file() and "rejected" not in f.parts
    ]
    if not candidates:
        raise NoFilesError(f"No CSV files in {inbox_dir}")

    by_date: dict[date | None, list[Path]] = {}
    for f in candidates:
        d = _parse_filename_date(f.name)
        by_date.setdefault(d, []).append(f)

    dated = {d: files for d, files in by_date.items() if d is not None}
    if dated:
        newest_date = max(dated.keys())
        files = dated[newest_date]
        if len(files) > 1:
            raise AmbiguousInboxError(
                f"Multiple files for date {newest_date}: {sorted(f.name for f in files)}"
            )
        return files[0]

    return max(candidates, key=lambda p: p.stat().st_mtime)
