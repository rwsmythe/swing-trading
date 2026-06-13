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
``tests/research`` ``_restore_swing_sys_modules_identity`` autouse fixture restores the
deleted module's identity at the L2-LOCK test's teardown, so step 3 passes.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import types
from pathlib import Path

import pytest

from tests.research._sys_modules_isolation import (
    _restore_swing_modules,
    _swing_module_snapshot,
)

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
    try:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", *_REPRO_NODES,
                "-n", "0", "-p", "no:cacheprovider", "-q",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"")
        err = (exc.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        pytest.fail(
            "17-D.4 regression child run timed out after 300s (deadlock?).\n"
            "----- child stdout (tail) -----\n" + out[-3000:]
            + "\n----- child stderr (tail) -----\n" + err[-2000:]
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


def test_restore_swing_modules_repairs_sys_modules_and_parent_attr():
    """Unit test of the restore semantics (closes Codex R1 Major #2).

    Directly exercises the ``tests/research`` fixture's restore helper against
    the exact polluter shape -- a RAW delete + re-import of a ``swing.*`` module
    -- and asserts BOTH halves of the repair: the ``sys.modules`` entry AND the
    parent-package attribute are returned to the ORIGINAL object.

    Non-vacuous: it first proves the re-import genuinely produced a NEW object and
    repointed the parent attribute (the pollution), then proves the helper undoes
    both. A restore that only fixed ``sys.modules`` (the pre-Major-#1 version)
    fails the parent-attribute assertion.
    """
    target = "swing.data.ohlcv_archive"
    importlib.import_module(target)  # ensure cached
    parent_name, _, child = target.rpartition(".")

    snapshot = _swing_module_snapshot()
    original = sys.modules[target]
    parent = sys.modules[parent_name]
    assert getattr(parent, child) is original

    # Simulate the polluter: RAW delete + re-import -> NEW object, and the import
    # machinery repoints the parent attribute at the NEW submodule.
    del sys.modules[target]
    new_mod = importlib.import_module(target)
    assert new_mod is not original, "re-import did not produce a new object"
    assert sys.modules[target] is new_mod
    assert getattr(parent, child) is new_mod, (
        "precondition: re-import must repoint the parent attribute"
    )

    # Repair.
    _restore_swing_modules(snapshot)

    assert sys.modules[target] is original, (
        "restore must return the sys.modules entry to the original object"
    )
    assert getattr(parent, child) is original, (
        "restore must also return the parent-package attribute to the original "
        "object (Codex R1 Major #1)"
    )


def test_restore_repairs_parent_attr_even_when_sys_modules_already_original():
    """Parent-attribute repair must not depend on this helper restoring
    sys.modules (closes Codex R2 Major #1).

    Models the ``monkeypatch.delitem`` teardown ordering: another teardown has
    already put ``sys.modules[target]`` back to the original, but a re-import
    earlier in the test left the parent-package attribute pointing at the
    now-discarded new module. The restore helper must still repair that stale
    attribute.

    Non-vacuous: a pass-2 that only iterated entries IT restored in pass 1 (the
    pre-R2 implementation) would skip ``target`` here -- ``sys.modules[target]``
    already equals the original -- and leave the parent attribute stale, failing
    the final assertion.
    """
    target = "swing.data.ohlcv_archive"
    importlib.import_module(target)  # ensure cached
    parent_name, _, child = target.rpartition(".")

    snapshot = _swing_module_snapshot()
    original = sys.modules[target]
    parent = sys.modules[parent_name]

    # Re-import repoints the parent attribute at a NEW module...
    del sys.modules[target]
    new_mod = importlib.import_module(target)
    assert new_mod is not original
    assert getattr(parent, child) is new_mod
    # ...but sys.modules[target] is independently restored first (the ordering
    # this test exists to cover). Now ONLY the parent attribute is stale.
    sys.modules[target] = original
    assert getattr(parent, child) is new_mod, (
        "precondition: parent attribute must still be stale while sys.modules "
        "is already original"
    )

    _restore_swing_modules(snapshot)

    assert sys.modules[target] is original
    assert getattr(parent, child) is original, (
        "restore must repair a stale parent attribute even when sys.modules was "
        "already restored to the original by another teardown (Codex R2 Major #1)"
    )


def test_restore_skips_non_module_parent_slot_without_raising():
    """pass-2 parent-attribute repair must tolerate a non-module parent slot.

    Models an L2-LOCK test that plants a ``_NoImportSentinel`` (``__getattr__``
    raises on ANY access) at a ``swing.*`` parent slot. ``getattr(parent, child,
    None)`` does NOT swallow that ``AssertionError``, so pass 2 would crash the
    research test's teardown. The fixture must skip non-module parents.

    Non-vacuous: without the ``isinstance(parent, ModuleType)`` guard, the
    sentinel's ``__getattr__`` raises and this test errors; with it, restore is a
    no-op for that entry and the child is still restored in pass 1.
    """
    class _Raiser:
        def __getattr__(self, attr):  # noqa: D401 - sentinel
            raise AssertionError(f"banned access: {attr!r}")

    child_name = "swing.fake_pkg_17d4.child"
    parent_name = "swing.fake_pkg_17d4"
    original_child = types.ModuleType(child_name)
    sys.modules[child_name] = object()      # != original -> pass 1 restores it
    sys.modules[parent_name] = _Raiser()    # non-module parent -> pass 2 must skip
    try:
        # parent_name intentionally absent from the snapshot, so pass 1 does not
        # replace the sentinel before pass 2 reads it.
        _restore_swing_modules({child_name: original_child})
        assert sys.modules[child_name] is original_child
    finally:
        sys.modules.pop(child_name, None)
        sys.modules.pop(parent_name, None)
