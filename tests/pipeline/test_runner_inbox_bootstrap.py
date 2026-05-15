"""Pipeline runner auto-creates the Finviz inbox dir on first-run.

Regression test for operator-reported bug 2026-05-15: pipeline run errored
out on missing `data/finviz-inbox/` folder because `Path.glob` on a
non-existent dir returns an empty iterator silently, causing `select_csv`
to raise a misleading `NoFilesError("No CSV files in <missing_dir>")`
instead of bootstrapping the dir.

Discriminating signal: post-call, the previously-missing inbox dir EXISTS.
Pipeline still fails (correctly) with NoFilesError because the dir is
empty after auto-creation — that's the right failure mode for "no data
available." The fix only addresses the first-run-bootstrap case.
"""
from __future__ import annotations

from pathlib import Path

from swing.config import load
from swing.data.db import ensure_schema
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config


def test_pipeline_run_auto_creates_missing_finviz_inbox_dir(tmp_path: Path):
    """Runner bootstraps `cfg.paths.finviz_inbox_dir` if missing.

    Before fix: pipeline fails with NoFilesError + dir stays missing.
    After fix: pipeline still fails with NoFilesError (dir is now empty)
    BUT the dir was auto-created — operator can now drop a CSV or run
    `swing finviz fetch` and re-invoke pipeline successfully.
    """
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

    # Pipeline should still fail — empty inbox = no data to evaluate.
    assert result.state == "failed", (
        f"unexpected state {result.state!r} (error: {result.error_message!r}); "
        f"empty inbox should produce a failed run"
    )
    assert "no csv files" in (result.error_message or "").lower(), (
        f"expected NoFilesError-style message about missing CSVs; "
        f"got: {result.error_message!r}"
    )

    # POST-CONDITION (the discriminating regression signal): inbox dir
    # exists post-call. Before the fix, this assertion would fail because
    # the runner errored on `select_csv` before any mkdir happened.
    assert inbox.exists(), (
        f"runner should auto-create missing inbox dir; "
        f"dir still absent after pipeline call: {inbox}"
    )
    assert inbox.is_dir(), f"path exists but is not a directory: {inbox}"
