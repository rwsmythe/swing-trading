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
    def __init__(self, db_path, exports_dir, project_root=None):
        self.paths = _Paths(db_path, exports_dir)
        # 19-B: _comms_root_for(cfg) -> config_project_root RAISES without this.
        # Default to exports_dir.parent (a tmp root) so _comms_root_for resolves a
        # tmp comms in tests (belt with the autouse comms seam-guard).
        self.project_root = (
            project_root if project_root is not None
            else Path(exports_dir).parent)


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
    # 19-B: the accessor now takes an optional `cfg`; the lambda accepts+ignores it
    # so the runner's research_health_artifact_path(cfg) call resolves to this tmp
    # path (the seam still intercepts the cfg-derived resolution for these tests).
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda cfg=None: artifact)
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
    # 19-B: the call threads run_id + shadow_manifest_path + run_warnings.
    assert 'shadow_manifest_path=shadow_manifest' in src
    assert 'run_id=lease.run_id' in src
    shadow_i = src.index('_step_shadow_expectancy(')
    research_i = src.index('shadow_manifest_path=shadow_manifest')
    complete_i = src.index('lease.step("complete")')
    assert shadow_i < research_i < complete_i


# --- 18-H.7: the RED-edge push wiring --------------------------------------

_POST_BASELINE_DATE = "2026-09-15"  # well after the 2026-06-13 finiteness cutoff
_NAN_OHLC = ('{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, '
             '"volume": 100.0, "provider": "yfinance"}')


def _seed_red_db(db_path: Path) -> None:
    # A genuine post-baseline non-finite OHLC observation -> finiteness RED ->
    # overall red. Planted via a RAW insert (the 18-B.1 write-barrier rejects
    # non-finite through insert_observation; this tests DETECTION of bad data).
    conn = ensure_schema(db_path)
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="ZZZ", detection_date=_POST_BASELINE_DATE,
        data_asof_date=_POST_BASELINE_DATE, pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-09-15T00:00:00"))
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, _POST_BASELINE_DATE, _NAN_OHLC, "invalidated", 1,
         "2026-09-15T00:00:00"))
    conn.commit()
    conn.close()


def _seed_pipeline_run(db_path: Path, run_id: int) -> None:
    # 19-B: a real pipeline_runs row so pipeline_run_exists(conn, run_id) is True
    # (the lease-verification proof for the push gate).
    conn = ensure_schema(db_path)
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date,"
        " action_session_date, state, lease_token) VALUES"
        " (?, '2026-09-15T00:00:00', 'manual', '2026-09-14', '2026-09-15',"
        " 'running', 'tok')", (run_id,))
    conn.commit()
    conn.close()


def _prior_envelope(overall: str) -> str:
    from datetime import UTC, datetime
    return json.dumps({
        "monitor": "research_measurement",
        "overall": overall,
        "checks": [{"key": "k", "status": overall, "summary": "s",
                    "detail": None}],
        "generated_ts": datetime.now(UTC).isoformat(timespec="seconds"),
    })


def test_step_still_writes_latest_json_when_push_raises(
    tmp_path, monkeypatch,
) -> None:
    # Task 3 double-guard: even when the push RAISES, the step's defensive
    # try/except catches it and write_research_health_artifact STILL runs ->
    # latest.json refreshes to the NEW red envelope.
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")

    def _boom(*a, **k):
        raise RuntimeError("push boom")

    monkeypatch.setattr(
        "swing.monitoring.research_health.push_research_health_red_to_rd", _boom)

    runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"), run_id=104)

    env = json.loads(artifact.read_text(encoding="utf-8"))
    assert env["overall"] == "red"  # the NEW envelope was written despite the raise


def test_step_runtime_ordering_read_prior_then_push_then_write(
    tmp_path, monkeypatch,
) -> None:
    # The PRIMARY behavioral ordering proof (NOT a source-string check): the prior
    # is read FIRST (and is the previous night's GREEN, not the just-computed red),
    # the push is called NEXT with that prior + the threaded run_id, write runs LAST.
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")

    import swing.monitoring.research_health as rh

    calls: list[tuple] = []
    real_read_prior = rh._read_prior_overall

    def _spy_read_prior(*a, **k):
        val = real_read_prior(*a, **k)
        calls.append(("read_prior", val))
        return val

    def _spy_push(status, *, run_id, prior_overall, lease_verified=False,
                  comms_root=None):
        calls.append(("push", prior_overall, run_id))
        return False

    def _spy_write(status, out_path=None, *, extra=None):
        calls.append(("write",))
        return artifact

    monkeypatch.setattr(rh, "_read_prior_overall", _spy_read_prior)
    monkeypatch.setattr(rh, "push_research_health_red_to_rd", _spy_push)
    monkeypatch.setattr(rh, "write_research_health_artifact", _spy_write)

    runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"), run_id=104)

    assert calls == [("read_prior", "green"), ("push", "green", 104), ("write",)]


def test_step_edge_posts_to_rd_end_to_end(tmp_path, monkeypatch) -> None:
    # Drives the REAL helper (no push monkeypatch): a prior GREEN + a RED db + a
    # REAL pipeline_runs row (lease_verified) -> the edge fires through
    # push_research_health_red_to_rd, posting one status to the cfg-derived tmp
    # comms tree (_comms_root_for(cfg) = cfg.project_root/comms).
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    _seed_pipeline_run(db, 104)  # 19-B: lease_verified proof
    artifact = _patch_artifact(tmp_path, monkeypatch)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")
    # cfg.project_root = (tmp_path/"exports").parent = tmp_path -> comms = tmp/comms
    comms = tmp_path / "comms"

    runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"), run_id=104)

    inbox = sorted((comms / "rd" / "inbox").glob("*.md"))
    assert len(inbox) == 1
    text = inbox[0].read_text(encoding="utf-8")
    assert "from: pipeline" in text
    assert "to: rd" in text
    assert "type: status" in text
    assert "temporal_log_finiteness" in text
    assert "104" in text


def test_step_no_edge_when_prior_already_red(tmp_path, monkeypatch) -> None:
    # prior RED + RED db -> no edge -> no post (but the write still refreshes
    # latest.json, asserted by the still-writes test).
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    artifact = _patch_artifact(tmp_path, monkeypatch)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("red"), encoding="utf-8")
    comms = tmp_path / "comms"
    monkeypatch.setattr(
        "swing.monitoring.research_health._default_comms_root", lambda: comms)

    runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"), run_id=104)

    assert not list((comms / "rd" / "inbox").glob("*.md")) if (
        comms / "rd" / "inbox").is_dir() else True


# --- 19-B Task 6: anchor consistency + lease gate + broken-context guard -----

from swing.monitoring.stoplights import (  # noqa: E402
    RESEARCH_HEALTH_ARTIFACT_PATH,
)


def _cfg_artifact(exports_dir: Path) -> Path:
    return Path(exports_dir) / "research" / "health" / "latest.json"


def _prior_envelope_with_count(overall: str, detection_count: int) -> str:
    from datetime import UTC, datetime
    return json.dumps({
        "monitor": "research_measurement",
        "overall": overall,
        "checks": [{"key": "k", "status": overall, "summary": "s",
                    "detail": None}],
        "generated_ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "detection_count": detection_count,
    })


def test_step_writes_to_cfg_derived_artifact_path(tmp_path) -> None:
    # ANCHOR CONSISTENCY (no monkeypatch): the runner resolves the artifact via
    # research_health_artifact_path(cfg) -> cfg.paths.exports_dir path, NOT the
    # __file__ constant. Pre-fix: write_research_health_artifact(status) -> __file__.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")

    runner._step_research_health(cfg=_Cfg(db, exports_dir))

    got = _cfg_artifact(exports_dir)
    assert got.exists()
    assert got != RESEARCH_HEALTH_ARTIFACT_PATH
    env = json.loads(got.read_text(encoding="utf-8"))
    assert env["monitor"] == "research_measurement"


def test_step_pushes_to_cfg_derived_comms_root(tmp_path) -> None:
    # The push lands under cfg.project_root/comms (config-derived), NOT the real
    # comms. Combined with the autouse seam-guard the tmp comms passes through.
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    _seed_pipeline_run(db, 104)
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    proj = tmp_path / "proj"
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir, project_root=proj), run_id=104)

    inbox = sorted((proj / "comms" / "rd" / "inbox").glob("*.md"))
    assert len(inbox) == 1


def test_step_skips_push_when_run_id_not_in_pipeline_runs(tmp_path) -> None:
    # lease-or-silent: a RED edge with run_id=999 that is NOT a pipeline_runs row
    # -> NO push, but the artifact STILL writes. Pre-fix (run_id-not-None only):
    # the push fires. Post-fix: pipeline_run_exists False -> lease_verified False.
    db = tmp_path / "swing.db"
    _seed_red_db(db)  # NO pipeline_runs row seeded
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    proj = tmp_path / "proj"
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir, project_root=proj), run_id=999)

    assert not (proj / "comms" / "rd" / "inbox").exists() or not list(
        (proj / "comms" / "rd" / "inbox").glob("*.md"))
    assert json.loads(artifact.read_text(encoding="utf-8"))["overall"] == "red"


def test_step_pushes_when_run_id_is_real_pipeline_run(tmp_path) -> None:
    # The gate is not over-tight: a real pipeline_runs row -> the push fires.
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    _seed_pipeline_run(db, 999)
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    proj = tmp_path / "proj"
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir, project_root=proj), run_id=999)

    assert len(list((proj / "comms" / "rd" / "inbox").glob("*.md"))) == 1


def test_step_suppresses_on_broken_context_empty_db(tmp_path) -> None:
    # BROKEN-CONTEXT (empty-DB vector): prior artifact records detections>0, the DB
    # is empty (0 detections), shadow_manifest_path=None -> write NOTHING (prior
    # byte-identical), no push. Pre-fix (no guard): compute overwrites the prior.
    db = tmp_path / "swing.db"
    ensure_schema(db).close()  # schema, ZERO detections
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    sentinel = _prior_envelope_with_count("green", 5)
    artifact.write_text(sentinel, encoding="utf-8")

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir), run_id=104, shadow_manifest_path=None)

    assert artifact.read_text(encoding="utf-8") == sentinel  # untouched


def test_step_suppresses_on_shadow_manifest_invisible(tmp_path) -> None:
    # BROKEN-CONTEXT (invisible-manifest vector): shadow wrote a manifest but the
    # cfg exports/research scan root is empty -> anchor divergence -> suppress.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    exports_dir = tmp_path / "exports"  # NO shadow dir seeded under research/
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    sentinel = _prior_envelope("green")
    artifact.write_text(sentinel, encoding="utf-8")

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir), run_id=104,
        shadow_manifest_path=tmp_path / "elsewhere" / "manifest.json")

    assert artifact.read_text(encoding="utf-8") == sentinel  # untouched


def test_step_writes_on_genuine_empty(tmp_path) -> None:
    # GENUINE-EMPTY: empty DB + prior ABSENT -> NOT suppressed -> writes the honest
    # envelope carrying detection_count: 0 (never over-suppress a fresh system).
    db = tmp_path / "swing.db"
    ensure_schema(db).close()  # schema, ZERO detections
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    artifact = _cfg_artifact(exports_dir)

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir), run_id=104,
        shadow_manifest_path=exports_dir / "research" / "m.json")

    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8"))["detection_count"] == 0


def test_step_emits_run_warning_on_suppress_empty_db_vector(tmp_path) -> None:
    # RD 8.1(b): a suppress emits a run_warnings entry (step=research_health) so the
    # recurrence surfaces in the run ledger + GUI, not only pipeline.log.
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    exports_dir = tmp_path / "exports"
    _seed_fresh_manifest(exports_dir / "research")
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope_with_count("green", 5), encoding="utf-8")
    warns: list[dict] = []

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir), run_id=104, shadow_manifest_path=None,
        run_warnings=warns)

    assert any(w["step"] == "research_health" for w in warns)


def test_step_emits_run_warning_on_suppress_invisible_manifest_vector(
    tmp_path,
) -> None:
    # RD 8.1(b) -- the OTHER suppress vector also emits the run-warning.
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    exports_dir = tmp_path / "exports"  # empty scan root
    artifact = _cfg_artifact(exports_dir)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(_prior_envelope("green"), encoding="utf-8")
    warns: list[dict] = []

    runner._step_research_health(
        cfg=_Cfg(db, exports_dir), run_id=104,
        shadow_manifest_path=tmp_path / "elsewhere" / "m.json",
        run_warnings=warns)

    assert any(w["step"] == "research_health" for w in warns)
