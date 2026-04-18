"""Export retention — compress exports/<date>/ folders older than N days."""
from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class RetentionResult:
    archived_paths: list[Path] = field(default_factory=list)
    zip_paths: list[Path] = field(default_factory=list)


def archive_old_exports(
    *, exports_dir: Path, retention_days: int = 90,
    today: date | None = None,
) -> RetentionResult:
    """Walk exports_dir for date-named folders older than retention_days;
    compress each into exports/archive/<YYYY-MM>.zip, then delete the folder.
    Skips `archive/` itself and any non-date-named dirs."""
    today = today or date.today()
    if not exports_dir.exists():
        return RetentionResult()

    result = RetentionResult([], [])
    archive_root = exports_dir / "archive"
    archive_root.mkdir(exist_ok=True)

    by_month: dict[str, list[tuple[date, Path]]] = {}
    for d in exports_dir.iterdir():
        if not d.is_dir() or d.name == "archive" or d.name.startswith("."):
            continue
        try:
            dt = date.fromisoformat(d.name)
        except ValueError:
            continue
        if (today - dt).days <= retention_days:
            continue
        month_key = dt.strftime("%Y-%m")
        by_month.setdefault(month_key, []).append((dt, d))

    for month_key, entries in by_month.items():
        zip_path = archive_root / f"{month_key}.zip"
        mode = "a" if zip_path.exists() else "w"
        with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED) as z:
            for dt, d in entries:
                for f in d.rglob("*"):
                    if f.is_file():
                        arcname = f"{dt.isoformat()}/{f.relative_to(d).as_posix()}"
                        if mode == "a" and arcname in z.namelist():
                            continue
                        z.write(f, arcname=arcname)
                shutil.rmtree(d)
                result.archived_paths.append(d)
        result.zip_paths.append(zip_path)
    return result
