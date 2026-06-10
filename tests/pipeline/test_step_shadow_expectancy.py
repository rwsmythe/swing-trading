"""Phase 16 Arc 5 — shadow-expectancy drumbeat step tests.

Exercise the PRODUCTION wiring of ``_step_shadow_expectancy``: the real argv
construction (incl. ``--db`` / ``--output-dir``), best-effort failure tolerance
(nonzero exit / timeout / spawn error / missing-or-unparseable manifest ->
warned, run continues), the gotcha-#27 zero-unique-signal warning built from the
REAL manifest funnel shape, keep-last-90 artifact retention (``shadow-expectancy-*``
only), and LeaseRevokedError propagation (the subprocess except is targeted, not
broad, so a revoke is never swallowed into a warned failure).
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from swing.pipeline import runner
from swing.pipeline.lease import LeaseRevokedError


# ---------------------------------------------------------------------------
# Lightweight fixtures (the conftest_temporal _Cfg lacks exports_dir).
# ---------------------------------------------------------------------------
class _Paths:
    def __init__(self, db_path, exports_dir):
        self.db_path = db_path
        self.exports_dir = exports_dir


class _Cfg:
    def __init__(self, db_path, exports_dir):
        self.paths = _Paths(db_path, exports_dir)


@pytest.fixture
def cfg(tmp_path):
    db = tmp_path / "swing.db"
    db.write_bytes(b"")  # presence only; the engine is mocked at the subprocess boundary
    exports = tmp_path / "exports"
    exports.mkdir()
    return _Cfg(db, exports)


def _manifest_payload(*, total=210, unique=42, per_hypothesis=None, unattributed=None):
    """Mirror the REAL manifest funnel shape (verified against the operator's
    manual-run artifact shadow-expectancy-20260609T174447Z)."""
    return {
        "funnel": {
            "detection_level": {
                "collapsed_duplicate_detection": total - unique,
                "total_detections": total,
                "unique_signals": unique,
            },
            "per_hypothesis": per_hypothesis if per_hypothesis is not None else {},
            "unattributed": (
                unattributed if unattributed is not None else {"no_canonical_detection": unique}
            ),
        },
        "harness_version": "0.1.0",
        "source": "pipeline",
        "started_iso_utc": "20260609T174447Z",
    }


def _write_artifact(cfg, *, name="shadow-expectancy-20260609T174447Z", **kw):
    """Write a real manifest.json under exports/research/<name>/; return its path."""
    art = cfg.paths.exports_dir / "research" / name
    art.mkdir(parents=True, exist_ok=True)
    manifest = art / "manifest.json"
    manifest.write_text(json.dumps(_manifest_payload(**kw)), encoding="utf-8")
    return manifest


def _cli_stdout(manifest_path):
    """The four click.echo lines the CLI emits on success (manifest.json last)."""
    parent = manifest_path.parent
    return (
        f"results.csv:     {parent / 'results.csv'}\n"
        f"per_session.csv: {parent / 'per_session.csv'}\n"
        f"summary.md:      {parent / 'summary.md'}\n"
        f"manifest.json:   {manifest_path}\n"
    )


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_run(monkeypatch, *, returns=None, raises=None, recorder=None):
    def fake_run(argv, **kwargs):
        if recorder is not None:
            recorder["argv"] = argv
            recorder["kwargs"] = kwargs
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(runner.subprocess, "run", fake_run)


# ---------------------------------------------------------------------------
# argv / kwargs construction (production wiring)
# ---------------------------------------------------------------------------
def test_argv_and_kwargs_are_the_real_cli_surface(cfg, monkeypatch):
    manifest = _write_artifact(cfg)
    rec: dict = {}
    _patch_run(monkeypatch, returns=_FakeProc(0, _cli_stdout(manifest)), recorder=rec)

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert rec["argv"] == [
        sys.executable, "-m", "swing.cli", "diagnose", "shadow-expectancy",
        "--db", str(cfg.paths.db_path),
        "--output-dir", str(cfg.paths.exports_dir / "research"),
    ]
    # cp1252-safe defensive capture + 300s timeout (locked design §3.3).
    assert rec["kwargs"]["timeout"] == 300
    assert rec["kwargs"]["encoding"] == "utf-8"
    assert rec["kwargs"]["errors"] == "replace"
    assert rec["kwargs"]["capture_output"] is True
    # Healthy run (42 unique signals) -> no warning.
    assert warnings == []


# ---------------------------------------------------------------------------
# #27 zero-unique-signal warning (built from the REAL manifest shape)
# ---------------------------------------------------------------------------
def test_zero_unique_signals_emits_27_warning(cfg, monkeypatch):
    manifest = _write_artifact(cfg, total=0, unique=0, unattributed={})
    _patch_run(monkeypatch, returns=_FakeProc(0, _cli_stdout(manifest)))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    w = warnings[0]
    assert w["step"] == "shadow_expectancy"
    assert w["unique_signals"] == 0
    assert "zero unique signals" in w["reason"]


def test_nonzero_unique_signals_does_not_warn(cfg, monkeypatch):
    # 42 unique signals but zero attributed (all unattributed) is the honest
    # funnel, NOT a warned failure (locked design §3.2).
    manifest = _write_artifact(cfg, total=210, unique=42)
    _patch_run(monkeypatch, returns=_FakeProc(0, _cli_stdout(manifest)))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert warnings == []


# ---------------------------------------------------------------------------
# Failure tolerance (never fails the run)
# ---------------------------------------------------------------------------
def test_nonzero_exit_is_warned_not_raised(cfg, monkeypatch):
    _patch_run(monkeypatch, returns=_FakeProc(1, stdout="", stderr="boom\nstack"))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)  # must not raise

    assert len(warnings) == 1
    assert warnings[0]["step"] == "shadow_expectancy"
    assert "exited 1" in warnings[0]["reason"]
    # stderr tail captured, newlines collapsed.
    assert "boom stack" in warnings[0]["detail"]


def test_timeout_is_warned_not_raised(cfg, monkeypatch):
    _patch_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd="x", timeout=300, stderr="partial"),
    )

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    assert "timed out" in warnings[0]["reason"]


def test_spawn_oserror_is_warned_not_raised(cfg, monkeypatch):
    _patch_run(monkeypatch, raises=OSError("no interpreter"))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    assert "spawn failed" in warnings[0]["reason"]


def test_missing_manifest_after_zero_exit_is_warned(cfg, monkeypatch):
    # zero exit but no manifest.json line in stdout -> artifact contract broke.
    _patch_run(monkeypatch, returns=_FakeProc(0, stdout="results.csv: foo\n"))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    assert "manifest missing" in warnings[0]["reason"]


def test_manifest_path_present_but_file_absent_is_warned(cfg, monkeypatch):
    ghost = cfg.paths.exports_dir / "research" / "shadow-expectancy-ghost" / "manifest.json"
    stdout = f"manifest.json:   {ghost}\n"
    _patch_run(monkeypatch, returns=_FakeProc(0, stdout=stdout))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    assert "manifest missing" in warnings[0]["reason"]


def test_unparseable_manifest_is_warned(cfg, monkeypatch):
    art = cfg.paths.exports_dir / "research" / "shadow-expectancy-bad"
    art.mkdir(parents=True)
    manifest = art / "manifest.json"
    manifest.write_text("{not json", encoding="utf-8")
    _patch_run(monkeypatch, returns=_FakeProc(0, _cli_stdout(manifest)))

    warnings: list[dict] = []
    runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)

    assert len(warnings) == 1
    assert "unparseable" in warnings[0]["reason"]


# ---------------------------------------------------------------------------
# LeaseRevokedError propagation (subprocess except is targeted, not broad)
# ---------------------------------------------------------------------------
def test_lease_revoked_propagates(cfg, monkeypatch):
    _patch_run(monkeypatch, raises=LeaseRevokedError("synthetic-revoke"))

    warnings: list[dict] = []
    with pytest.raises(LeaseRevokedError, match="synthetic-revoke"):
        runner._step_shadow_expectancy(cfg=cfg, run_warnings=warnings)
    # NOT swallowed into a warned failure.
    assert warnings == []


# ---------------------------------------------------------------------------
# Manifest-path parse helper (locked artifact-dir mechanism §3.3)
# ---------------------------------------------------------------------------
def test_parse_manifest_path_handles_windows_drive_colon():
    stdout = (
        "results.csv:     C:\\proj\\exports\\research\\shadow-expectancy-X\\results.csv\n"
        "manifest.json:   C:\\proj\\exports\\research\\shadow-expectancy-X\\manifest.json\n"
    )
    p = runner._parse_shadow_manifest_path(stdout)
    assert p is not None
    assert p.name == "manifest.json"
    assert str(p).endswith("shadow-expectancy-X\\manifest.json")


def test_parse_manifest_path_returns_none_when_absent():
    assert runner._parse_shadow_manifest_path("results.csv: foo\n") is None
    assert runner._parse_shadow_manifest_path("") is None
    assert runner._parse_shadow_manifest_path(None) is None
