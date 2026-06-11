from __future__ import annotations

import pytest

import swing.log_correlation as lc
import swing.pipeline.runner as runner
from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _runner_cfg(tmp_path):
    # Build the cfg FIRST (real mkdir), BEFORE any monkeypatching -- so the cfg
    # construction is never affected by the stubs below (R1-major-3: do NOT patch
    # Path.mkdir, which would break this helper's own project/home mkdir).
    project = tmp_path / "p"; project.mkdir()
    home = tmp_path / "h"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    # run_pipeline_internal opens the DB (sweep_stale_artifacts -> connect) BEFORE
    # the lease, so the schema must exist or connect() raises before the stubbed
    # acquire_lease is ever reached.
    from swing.data.db import ensure_schema
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def test_set_pipeline_run_id_called_after_lease(tmp_path, monkeypatch):
    # set_pipeline_run_id(lease.run_id) must run immediately after lease acquisition.
    # Stub acquire_lease -> a fake lease, spy on set_pipeline_run_id, and make the
    # NEXT call after it (Heartbeat(), constructed right after the set and OUTSIDE
    # the post-lease try) raise -- so run_pipeline_internal aborts with the run id
    # already stamped. No network/DB beyond the lease.
    cfg = _runner_cfg(tmp_path)
    seen = {}

    class _FakeLease:
        run_id = 909
        token = "tok"
        def release(self, **kw):  # noqa: ARG002
            pass

    monkeypatch.setattr(runner, "acquire_lease", lambda **kw: _FakeLease())

    real_set = lc.set_pipeline_run_id
    def spy(rid):
        seen["rid"] = rid
        return real_set(rid)
    monkeypatch.setattr(runner, "set_pipeline_run_id", spy)

    class _Stop(RuntimeError):
        pass
    def boom(**kw):  # noqa: ARG001
        raise _Stop("stop after set_pipeline_run_id")
    monkeypatch.setattr(runner, "Heartbeat", boom)

    with pytest.raises(_Stop):
        runner.run_pipeline_internal(cfg=cfg, trigger="manual")
    assert seen["rid"] == 909
    assert lc.get_pipeline_run_id() == "909"
