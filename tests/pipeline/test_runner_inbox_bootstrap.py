"""Pipeline runner auto-creates the Finviz inbox dir on first-run.

Regression test for operator-reported bug 2026-05-15: pipeline run errored
out on missing `data/finviz-inbox/` folder because `Path.glob` on a
non-existent dir returns an empty iterator silently, causing `select_csv`
to raise a misleading `NoFilesError("No CSV files in <missing_dir>")`
instead of bootstrapping the dir.

Discriminating signal: post-call, the previously-missing inbox dir EXISTS.
Pipeline still fails with a NoFilesError-bearing message because the dir
is empty after auto-creation AND the post-Phase-12.5 inline auto-fetch
also fails (we monkeypatch ``_step_finviz_fetch`` to raise; otherwise the
operator's real Finviz token would leak through ``apply_overrides`` and
make a live API call from inside this fast-suite test).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config


def test_pipeline_run_auto_creates_missing_finviz_inbox_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runner bootstraps `cfg.paths.finviz_inbox_dir` if missing.

    Before mkdir fix (2026-05-15): pipeline fails with NoFilesError + dir
    stays missing.

    After mkdir fix: pipeline still fails BUT the dir was auto-created —
    operator can drop a CSV or run `swing finviz fetch` and re-invoke
    pipeline successfully.

    After Phase 12.5 inline-auto-fetch fix (2026-05-18): the empty-inbox
    NoFilesError ALSO routes through an inline ``_step_finviz_fetch``
    retry. To keep this test deterministic + offline, we monkeypatch
    ``_step_finviz_fetch`` to raise — the combined-error path still
    carries the initial NoFilesError "no csv files" substring per the
    Phase 12.5 fix's contract (initial cause preserved alongside the
    retry failure cause).
    """
    def _fake_step_finviz_fetch_raising(*, cfg, lease):
        raise RuntimeError("simulated: token unavailable in test env")

    monkeypatch.setattr(
        "swing.pipeline.runner._step_finviz_fetch",
        _fake_step_finviz_fetch_raising,
    )

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    inbox = cfg.paths.finviz_inbox_dir
    # PRE-CONDITION: inbox does NOT exist.
    assert not inbox.exists(), f"setup error: inbox should be absent: {inbox}"

    result = run_pipeline(cfg=cfg, trigger="manual")

    # Pipeline should still fail — empty inbox + simulated auto-fetch
    # failure = no data to evaluate.
    assert result.state == "failed", (
        f"unexpected state {result.state!r} (error: {result.error_message!r}); "
        f"empty inbox + auto-fetch failure should produce a failed run"
    )
    # Initial NoFilesError cause MUST still appear in the post-Phase-12.5
    # combined error message (auto-fetch-failed path preserves it).
    assert "no csv files" in (result.error_message or "").lower(), (
        f"expected initial NoFilesError 'no csv files' substring "
        f"preserved in combined error message; got: {result.error_message!r}"
    )

    # POST-CONDITION (the discriminating regression signal): inbox dir
    # exists post-call. Before the mkdir fix, this assertion would fail
    # because the runner errored on `select_csv` before any mkdir happened.
    assert inbox.exists(), (
        f"runner should auto-create missing inbox dir; "
        f"dir still absent after pipeline call: {inbox}"
    )
    assert inbox.is_dir(), f"path exists but is not a directory: {inbox}"
