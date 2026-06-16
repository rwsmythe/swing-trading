"""Task 2 (18-D nightly half) -- the best-effort _step_research_health pipeline
step (C-NH1/2/3/5).

Runs the SAME compute_research_health + write_research_health_artifact as the
script, immediately after _step_shadow_expectancy, on a mode=ro conn, writing
nothing on failure, wrapped by the BARE B-shape step_guard (NO status_key -- the
O1 resolution: a status_key would trip update_status_columns' allowed-set raise
and need a non-existent pipeline_runs column => fail the run / cross the schema
LOCK).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.data.repos.pipeline import LeaseRevokedError
from swing.pipeline import runner
from swing.pipeline.step_guard import step_guard

_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


class _Paths:
    def __init__(self, db_path, exports_dir):
        self.db_path = db_path
        self.exports_dir = exports_dir


class _Cfg:
    def __init__(self, db_path, exports_dir):
        self.paths = _Paths(db_path, exports_dir)


class FakeLease:
    def __init__(self):
        self.steps: list[str] = []
        self.status_calls: list[dict] = []

    def step(self, name: str) -> None:
        self.steps.append(name)

    def status(self, **cols: str) -> None:
        self.status_calls.append(cols)


def _seed_green_db(db_path: Path) -> None:
    conn = ensure_schema(db_path)
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="AAA", detection_date="2026-06-05",
        data_asof_date="2026-06-04", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00"))
    # one TERMINAL detection so coverage expects no tail vs the real wall clock.
    insert_observation(conn, PatternForwardObservation(
        observation_id=None, detection_id=det, observation_date="2026-06-05",
        ohlc_today_json=_FINITE_OHLC, status="invalidated",
        sessions_since_detection=1, created_at="2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


def _patch_artifact(tmp_path: Path, monkeypatch) -> Path:
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    return artifact


def _seed_fresh_manifest(research_root: Path, *, invalid_ohlc: int = 1) -> None:
    from datetime import UTC, datetime, timedelta
    ts = datetime.now(UTC) - timedelta(hours=1)
    run_dir = research_root / ("shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": invalid_ohlc}}},
        "unattributed": {},
    }}), encoding="utf-8")


def test_step_runs_and_writes_latest_json(tmp_path, monkeypatch) -> None:
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)
    # a fresh manifest under cfg.paths.exports_dir/research (where the shadow step
    # writes) keeps the manifest-consuming checks (#2/#5) green so the envelope
    # validates fresh.
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")

    runner._step_research_health(cfg=_Cfg(db, exports_dir))

    assert artifact.exists()
    from swing.monitoring import stoplights
    assert stoplights.read_validated_research_envelope() is not None


def test_step_reads_manifest_from_cfg_exports_dir_not_default_root(
    tmp_path, monkeypatch,
) -> None:
    # Codex R1: the health step must read the manifests from EXACTLY the root the
    # shadow step wrote to (cfg.paths.exports_dir/research), NOT the contract
    # default root. Seed a FRESH GOOD manifest under the cfg root and a CORRUPT
    # newest manifest under the default contract root; assert the emitted envelope
    # reflects the CFG-root manifest (excluded check green/n-a, not the corrupt
    # yellow). Distinguishing: the pre-fix code (default exports_root) would read
    # the corrupt default-root manifest -> the excluded check would be yellow.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)  # contract default = tmp_path
    # the DEFAULT contract root (artifact.parent.parent = tmp_path) gets a CORRUPT
    # NEWEST manifest.
    from datetime import UTC, datetime, timedelta
    newest = datetime.now(UTC) - timedelta(minutes=30)
    corrupt_dir = tmp_path / (
        "shadow-expectancy-" + newest.strftime("%Y%m%dT%H%M%S") + "Z")
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")
    # the CFG exports root gets a FRESH GOOD manifest (a DIFFERENT directory).
    exports_dir = tmp_path / "configured-exports"
    _seed_fresh_manifest(exports_dir / "research")

    runner._step_research_health(cfg=_Cfg(db, exports_dir))

    env = json.loads(artifact.read_text(encoding="utf-8"))
    excluded = next(
        c for c in env["checks"] if c["key"] == "excluded_reason_breakdown")
    # the GOOD cfg-root manifest -> the excluded check is NOT the corrupt-yellow.
    assert excluded["status"] == "green"


def test_step_uses_readonly_conn(tmp_path, monkeypatch) -> None:
    # C-NH2: the conn handed to compute_research_health must be a mode=ro URI conn
    # (a write through it raises "readonly database"). A read-write connect() would
    # let the write succeed.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    _patch_artifact(tmp_path, monkeypatch)
    captured = {}

    def _spy(conn, **kwargs):
        # Assert read-only WHILE the conn is open (the step closes it after
        # compute returns): a write must raise "readonly database". A read-write
        # connect() would let the write succeed.
        try:
            conn.execute(
                "INSERT INTO pattern_detection_events (ticker, detection_date,"
                " data_asof_date, pattern_class, structural_anchors_json,"
                " composite_score, detector_version, source,"
                " per_pattern_metadata_json, created_at)"
                " VALUES ('X','2026-06-05','2026-06-04','vcp','{}',1.0,'t',"
                "'synthetic','{}','2026-06-05T00:00:00')")
        except sqlite3.OperationalError as exc:
            captured["readonly_err"] = str(exc)
        from swing.monitoring.research_health import (
            ResearchHealthCheck,
            ResearchHealthStatus,
        )
        return ResearchHealthStatus(
            overall="green",
            checks=[ResearchHealthCheck(
                key="k", status="green", summary="s", detail=None)])

    monkeypatch.setattr(
        "swing.monitoring.research_health.compute_research_health", _spy)
    runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"))
    assert "readonly" in captured.get("readonly_err", "").lower(), (
        "expected a readonly-database error -> conn was NOT opened mode=ro")


def test_failing_compute_does_not_write_and_leaves_prior_artifact(
    tmp_path, monkeypatch,
) -> None:
    # C-NH5: on ANY failure write NOTHING -- the prior latest.json stays
    # BYTE-IDENTICAL, no partial, no .tmp leftover.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    sentinel = b'{"monitor": "prior-sentinel"}'
    artifact.write_bytes(sentinel)

    def _boom(conn, **kwargs):
        raise RuntimeError("compute exploded")

    monkeypatch.setattr(
        "swing.monitoring.research_health.compute_research_health", _boom)

    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    # run under the SAME bare B-shape guard the runner uses -> the error is
    # swallowed (no escape).
    with step_guard(lease, "research_health", logger=log):
        runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"))

    assert artifact.read_bytes() == sentinel  # untouched
    assert not list((tmp_path / "health").glob("*.tmp"))


def test_step_does_not_fail_the_run_on_arbitrary_error(tmp_path) -> None:
    # C-NH1 swallow: a generic RuntimeError inside the bare-B-shape guard does NOT
    # escape (the run is never failed).
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with step_guard(lease, "research_health", logger=log):
        raise RuntimeError("boom")  # swallowed by the guard
    assert lease.steps == ["research_health"]


def test_step_writes_no_status_column(tmp_path, monkeypatch) -> None:
    # The O1 / no-schema LOCK proof: the BARE B-shape never calls lease.status
    # (no *_status column => no update_status_columns => no pipeline_runs schema
    # dependency), on BOTH the success path AND a forced-error path. A B-shape
    # passing status_key="research_health_status" WOULD call lease.status.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    _patch_artifact(tmp_path, monkeypatch)
    log = logging.getLogger("swing.pipeline.runner")

    # success path
    lease_ok = FakeLease()
    with step_guard(lease_ok, "research_health", logger=log):
        runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"))
    assert lease_ok.status_calls == []

    # forced-error path
    monkeypatch.setattr(
        "swing.monitoring.research_health.compute_research_health",
        lambda conn, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    lease_err = FakeLease()
    with step_guard(lease_err, "research_health", logger=log):
        runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"))
    assert lease_err.status_calls == []


def test_step_propagates_lease_revoked(tmp_path) -> None:
    # C-NH1 revoke: inside the bare-B-shape guard a LeaseRevokedError PROPAGATES.
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with pytest.raises(LeaseRevokedError):
        with step_guard(lease, "research_health", logger=log):
            raise LeaseRevokedError("revoked")


def test_runner_invokes_step_via_step_guard_between_shadow_and_complete() -> None:
    # C-NH3 + C-NH1 wiring: the research_health site is wrapped by step_guard
    # (NOT a hand-rolled try/except) and placed AFTER shadow_expectancy, BEFORE
    # complete. Assert against the runner SOURCE.
    src = Path(runner.__file__).read_text(encoding="utf-8")
    assert 'step_guard(lease, "research_health", logger=log)' in src
    assert '_step_research_health(cfg=cfg)' in src
    shadow_i = src.index('_step_shadow_expectancy(cfg=cfg')
    research_i = src.index('_step_research_health(cfg=cfg)')
    complete_i = src.index('lease.step("complete")')
    assert shadow_i < research_i < complete_i
