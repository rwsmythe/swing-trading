"""Manifest-driven staged promotion (spec §5.7)."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StagingDir:
    base: Path
    run_id: int
    artifact_type: str

    @property
    def staging_root(self) -> Path:
        return self.base / ".staging"

    @property
    def path(self) -> Path:
        return self.staging_root / str(self.run_id)

    def create(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path


@dataclass(frozen=True)
class PromoteResult:
    target_path: Path
    manifest_path: Path
    backup_path: Path | None


def promote_staging(
    *, staging: StagingDir, target: Path, lease_token: str, db_path: Path,
    manifest_extras: dict[str, Any] | None = None,
) -> PromoteResult:
    """Atomic swap with manifest + .prev/ backup + in-line lease re-check.

    Steps (spec §5.7):
      1. Write MANIFEST.json into staging
      2. Re-read pipeline_runs for the owning run; if lease_token doesn't match
         OR state != 'running', abort WITHOUT promoting (staging stays for sweep)
      3. If target exists, move to .prev/<name>-<ts>/
      4. Rename staging dir → target

    A force-cleared stale worker cannot overwrite canonical artifacts written
    by the new run: the re-check aborts before the irreversible rename.
    """
    from swing.data.db import connect
    from swing.data.repos.pipeline import LeaseRevoked, find_run

    if not staging.path.exists():
        raise RuntimeError(f"staging dir does not exist: {staging.path}")

    manifest = {
        "run_id": staging.run_id,
        "lease_token": lease_token,
        "artifact_type": staging.artifact_type,
        "target_path": str(target),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "artifact_count": sum(1 for _ in staging.path.rglob("*") if _.is_file()),
        **(manifest_extras or {}),
    }
    manifest_path = staging.path / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    conn = connect(db_path)
    try:
        run = find_run(conn, staging.run_id)
        if run is None or run.lease_token != lease_token or run.state != "running":
            raise LeaseRevoked(
                f"run {staging.run_id} lease revoked or state changed "
                f"(state={run.state if run else 'missing'}); aborting promote"
            )
    finally:
        conn.close()

    backup_path: Path | None = None
    if target.exists():
        prev_root = staging.base / ".prev"
        prev_root.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = prev_root / f"{target.name}-{ts}"
        shutil.move(str(target), str(backup_path))

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging.path), str(target))

    return PromoteResult(
        target_path=target,
        manifest_path=target / "MANIFEST.json",
        backup_path=backup_path,
    )
