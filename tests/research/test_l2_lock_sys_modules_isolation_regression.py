"""17-D.4 regression: research L2-LOCK sys.modules deletion must not leak.

Root cause (17-D.4): several research L2-LOCK tests prove the research module
graph never imports Schwab/yfinance by RAW-deleting modules from ``sys.modules``
(``del sys.modules[...]`` / ``sys.modules.pop(...)``) and re-importing. A raw
delete that is NOT restored re-creates ``swing.integrations.schwab.client`` (and
siblings) as a NEW module object on the next import elsewhere in the process,
giving its exception classes NEW identities. Any module that bound the OLD class
earlier -- e.g. ``swing.web.routes.schwab`` doing
``from swing.integrations.schwab.client import SchwabPipelineActiveError`` at
import time and later ``except SchwabPipelineActiveError`` -- then fails to catch
the freshly-raised exception (different class object), returning HTTP 500 instead
of the intended 409/400. Under ``pytest -n auto`` xdist places a research L2-LOCK
test before a web-route test on the same worker (without the collection-order
"resetter" that masks it in a single ``-n 0`` run), so the web-route tests fail
NON-DETERMINISTICALLY.

This guard runs the EXACT deterministic ordering that reproduces the bug, in a
child ``-n 0`` process:

  1. a web test that builds the app  -> imports ``swing.web.routes.schwab``,
     binding ``SchwabPipelineActiveError`` (the OLD class object);
  2. a research L2-LOCK test         -> deletes ``swing.integrations.schwab.client``
     from ``sys.modules``;
  3. the schwab-setup web victim     -> raises a freshly-imported
     ``SchwabPipelineActiveError``; the route's ``except`` must still catch it.

PRE-FIX this child run reds (the victim gets 500, not 409). POST-FIX the
``tests/research`` ``_restore_sys_modules_identity`` autouse fixture restores the
deleted module's identity at the L2-LOCK test's teardown, so step 3 passes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Repo root = three levels up from this file (tests/research/<this file>).
_REPO_ROOT = Path(__file__).resolve().parents[2]

# The minimal deterministic 17-D.4 ordering (app-bind -> polluter -> victim).
_REPRO_NODES = (
    "tests/web/test_app_smoke.py::test_create_app_returns_fastapi",
    "tests/research/double_bottom_w_backtest/test_l2_lock.py"
    "::test_no_forbidden_imports_reach_d1_module_graph",
    "tests/web/test_routes/test_schwab_setup_route.py"
    "::test_post_with_pipeline_active_returns_409",
)


def test_research_l2lock_del_does_not_break_web_route_exception_identity():
    """The deterministic 17-D.4 polluter->victim ordering must pass.

    Non-vacuous: pre-fix (no sys.modules restoration around the L2-LOCK test)
    the child run reds with the victim returning 500 instead of 409; post-fix
    it passes. The child runs ``-n 0`` so the ordering is fixed and the bug is
    reproduced deterministically rather than chased under ``-n auto``.
    """
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", *_REPRO_NODES,
            "-n", "0", "-p", "no:cacheprovider", "-q",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "17-D.4 regression: a research L2-LOCK sys.modules deletion leaked into "
        "the web schwab route's exception-class identity (victim returned 500 "
        "instead of 409). The tests/research sys.modules-restoration fixture is "
        "missing or ineffective.\n"
        "----- child stdout (tail) -----\n"
        + proc.stdout[-3000:]
        + "\n----- child stderr (tail) -----\n"
        + proc.stderr[-2000:]
    )
