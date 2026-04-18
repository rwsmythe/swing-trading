"""Retention: compress exports/<date>/ older than N days into exports/archive/<YYYY-MM>.zip."""
from __future__ import annotations

import os
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

from swing.rendering.retention import archive_old_exports, RetentionResult


def _make_export(root: Path, dt: date) -> Path:
    d = root / dt.isoformat()
    d.mkdir(parents=True)
    (d / "briefing.html").write_text("<html></html>", encoding="utf-8")
    (d / "briefing.md").write_text("# x", encoding="utf-8")
    ts = time.mktime(dt.timetuple())
    os.utime(d, (ts, ts))
    for f in d.iterdir():
        os.utime(f, (ts, ts))
    return d


def test_recent_exports_untouched(tmp_path: Path):
    root = tmp_path / "exports"
    fresh = _make_export(root, date.today())
    result = archive_old_exports(exports_dir=root, retention_days=90, today=date.today())
    assert fresh.exists()
    assert result.archived_paths == []


def test_old_exports_compressed(tmp_path: Path):
    root = tmp_path / "exports"
    today = date.today()
    old = _make_export(root, today - timedelta(days=120))
    kept = _make_export(root, today - timedelta(days=30))
    result = archive_old_exports(exports_dir=root, retention_days=90, today=today)

    assert not old.exists()
    assert kept.exists()
    assert len(result.archived_paths) == 1

    month_str = (today - timedelta(days=120)).strftime("%Y-%m")
    archive = root / "archive" / f"{month_str}.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert any("briefing.html" in n for n in names)


def test_multiple_old_same_month_into_same_zip(tmp_path: Path):
    root = tmp_path / "exports"
    today = date.today()
    month_start = (today - timedelta(days=120)).replace(day=1)
    _make_export(root, month_start)
    _make_export(root, month_start + timedelta(days=3))
    archive_old_exports(exports_dir=root, retention_days=90, today=today)

    archive = root / "archive" / f"{month_start.strftime('%Y-%m')}.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:
        dates = {name.split("/")[0] for name in z.namelist() if "/" in name}
        assert len(dates) == 2
