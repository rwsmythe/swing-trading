from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# A driver run in a CHILD process. It installs the pipeline surface, emits records
# from the main thread + a worker thread, sets the run id, and exits. The parent
# reads the resulting pipeline.log. Kept tiny + hermetic (no real pipeline run).
_DRIVER = textwrap.dedent(
    """
    import logging, sys, threading
    from pathlib import Path
    from swing.config import load
    from swing.logging_setup import install_logging
    import swing.log_correlation as lc

    cfg = load(Path(sys.argv[1]))
    install_logging(cfg, surface="pipeline")
    log = logging.getLogger("swing.pipeline.lease")
    log.info("before-lease line")
    lc.set_pipeline_run_id(int(sys.argv[2]))
    log.info("after-lease line")

    def worker():
        logging.getLogger("swing.pipeline.worker").info("worker-thread line")
    t = threading.Thread(target=worker); t.start(); t.join()

    for h in logging.getLogger().handlers:
        try: h.flush()
        except Exception: pass
    """
)


def _write_cfg(tmp_path: Path) -> Path:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    return _minimal_config(project, home)


def _logs_dir(cfg_path: Path) -> Path:
    from swing.config import load
    return load(cfg_path).paths.logs_dir


def _run_driver(tmp_path, env_overrides, run_id=42):
    cfg_path = _write_cfg(tmp_path)
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    env = dict(os.environ)
    env.pop("SWING_WEB_REQUEST_ID", None)
    env.update(env_overrides)
    # Ensure the child imports the in-tree swing package (repo root on sys.path).
    repo_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(driver), str(cfg_path), str(run_id)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return (_logs_dir(cfg_path) / "pipeline.log").read_text(encoding="utf-8")


def test_subprocess_carries_request_id_and_run_id(tmp_path):
    text = _run_driver(tmp_path, {"SWING_WEB_REQUEST_ID": "uuid-sentinel-001"}, run_id=42)
    # The env sentinel is on every line (main + worker thread).
    assert text.count("req=uuid-sentinel-001") >= 3
    # Before the lease the run id is the placeholder; after, it is 42.
    before = [ln for ln in text.splitlines() if "before-lease line" in ln][0]
    after = [ln for ln in text.splitlines() if "after-lease line" in ln][0]
    worker = [ln for ln in text.splitlines() if "worker-thread line" in ln][0]
    assert "run=-" in before
    assert "run=42" in after
    # The worker-thread line carries BOTH ids -- the discriminator a contextvars
    # impl would FAIL (the thread would render req=-/run=-).
    assert "req=uuid-sentinel-001" in worker and "run=42" in worker


def test_subprocess_forged_env_falls_back(tmp_path):
    text = _run_driver(tmp_path, {"SWING_WEB_REQUEST_ID": "bad value\nwith newline"})
    assert "req=-" in text
    assert "bad value" not in text  # the forged value never reaches a log line


def test_subprocess_no_context_renders_placeholders(tmp_path):
    text = _run_driver(tmp_path, {})  # no SWING_WEB_REQUEST_ID at all
    assert "req=-" in text
    # No KeyError / "Logging error" leaked to the file or stderr.
    assert "--- Logging error ---" not in text
