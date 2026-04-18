"""Startup recovery sweep (spec §5.7)."""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.pipeline import find_run


@dataclass(frozen=True)
class SweepResult:
    deleted_staging_run_ids: list[int] = field(default_factory=list)
    deleted_prev_paths: list[Path] = field(default_factory=list)
    deleted_orphan_staging_paths: list[Path] = field(default_factory=list)
    flagged_stale_running_runs: list[int] = field(default_factory=list)


def sweep_stale_artifacts(
    *, db_path: Path, artifact_dirs: list[Path],
    prev_retention_days: int = 7, orphan_age_seconds: int = 3600,
    stale_heartbeat_seconds: int = 300,
) -> SweepResult:
    """For each base dir in artifact_dirs, sweep .staging/ and .prev/.

    For .staging/<id>/ with MANIFEST.json:
      - If the owning run is missing or no longer 'running': delete the staging dir.
      - If the owning run is 'running' but heartbeat is older than
        stale_heartbeat_seconds: flag (don't delete — deletion is only safe once
        the run has moved out of 'running' via force-clear; spec §5.6 makes
        this an operator decision).
    For .staging/<id>/ without MANIFEST.json: if older than orphan_age_seconds, delete.
    For .prev/<...>/ older than prev_retention_days: delete.
    """
    result = SweepResult([], [], [], [])
    conn = connect(db_path)
    try:
        for base in artifact_dirs:
            staging_root = base / ".staging"
            if staging_root.exists():
                for d in staging_root.iterdir():
                    if not d.is_dir():
                        continue
                    manifest = d / "MANIFEST.json"
                    if manifest.exists():
                        try:
                            data = json.loads(manifest.read_text(encoding="utf-8"))
                            rid = int(data.get("run_id", 0))
                        except (ValueError, OSError):
                            rid = 0
                        run = find_run(conn, rid) if rid else None
                        if run is None or run.state != "running":
                            shutil.rmtree(d, ignore_errors=True)
                            result.deleted_staging_run_ids.append(rid)
                        else:
                            hb = run.lease_heartbeat_ts
                            if hb is None:
                                result.flagged_stale_running_runs.append(rid)
                            else:
                                age = (
                                    datetime.now() - datetime.fromisoformat(hb)
                                ).total_seconds()
                                if age > stale_heartbeat_seconds:
                                    result.flagged_stale_running_runs.append(rid)
                    else:
                        age = time.time() - d.stat().st_mtime
                        if age > orphan_age_seconds:
                            shutil.rmtree(d, ignore_errors=True)
                            result.deleted_orphan_staging_paths.append(d)

            prev_root = base / ".prev"
            if prev_root.exists():
                cutoff = time.time() - prev_retention_days * 86400
                for d in prev_root.iterdir():
                    if d.is_dir() and d.stat().st_mtime < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                        result.deleted_prev_paths.append(d)
    finally:
        conn.close()
    return result
