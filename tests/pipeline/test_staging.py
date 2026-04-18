"""StagingDir + atomic promote with manifest + .prev backup."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swing.pipeline.staging import StagingDir, promote_staging


def test_writes_to_staging(tmp_path: Path):
    staging = StagingDir(base=tmp_path / "charts", run_id=1, artifact_type="charts")
    staging.path.parent.mkdir(parents=True, exist_ok=True)
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"png-data")
    assert (tmp_path / "charts" / ".staging" / "1" / "AAPL.png").exists()


def _seed_running_run(db_path: Path, *, run_id_target: int = 1) -> str:
    from swing.data.db import ensure_schema
    from swing.data.repos.pipeline import insert_pipeline_run
    ensure_schema(db_path).close()
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T21:49:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T21:49:30",
            )
        assert rid == run_id_target
    finally:
        conn.close()
    return token


def test_promote_to_canonical(tmp_path: Path):
    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"x")

    target = base / "2026-04-15"
    result = promote_staging(
        staging=staging, target=target, lease_token=token, db_path=db,
        manifest_extras={"data_asof_date": "2026-04-15"},
    )
    assert result.target_path == target
    assert (target / "AAPL.png").exists()
    assert (target / "MANIFEST.json").exists()
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["lease_token"] == token
    assert manifest["run_id"] == 1
    assert manifest["data_asof_date"] == "2026-04-15"


def test_promote_backs_up_previous(tmp_path: Path):
    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    target = base / "2026-04-15"
    target.mkdir(parents=True)
    (target / "OLD.png").write_bytes(b"old")

    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "NEW.png").write_bytes(b"new")
    promote_staging(
        staging=staging, target=target, lease_token=token, db_path=db,
    )
    assert (target / "NEW.png").exists()
    prev = base / ".prev"
    assert prev.exists()
    assert any("2026-04-15" in p.name for p in prev.iterdir())


def test_promote_aborts_when_lease_revoked(tmp_path: Path):
    """Spec §5.7: if the owning run's lease was force-cleared mid-work,
    promote_staging must refuse to rename and leave staging for sweep."""
    from swing.data.repos.pipeline import LeaseRevoked, force_clear

    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"x")

    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            force_clear(conn, run_id=1, error_message="admin cleared")
    finally:
        conn.close()

    target = base / "2026-04-15"
    with pytest.raises(LeaseRevoked):
        promote_staging(
            staging=staging, target=target, lease_token=token, db_path=db,
        )
    assert staging.path.exists()
    assert not target.exists()
