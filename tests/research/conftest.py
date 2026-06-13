"""Research-suite test isolation (17-D.4).

The research L2-LOCK / reader tests deliberately drop modules from
``sys.modules`` -- ``swing.integrations.schwab.*``, ``swing.data.ohlcv_archive``,
``yfinance``, ``schwabdev``, and the research harness packages -- then re-import
to prove the research module graph never pulls in any Schwab / yfinance dependency
(the L2 LOCK contract). Most do this with ``monkeypatch.delitem`` (restored at
teardown), but several use a RAW ``del sys.modules[...]`` / ``sys.modules.pop(...)``
that is NEVER restored.

A raw, unrestored deletion is a process-global mutation: the next time any code
imports the deleted module it is rebuilt as a NEW module object whose classes and
exceptions have NEW identities. Code that bound the OLD class earlier in the
process -- e.g. ``swing.web.routes.schwab`` doing
``from swing.integrations.schwab.client import SchwabPipelineActiveError`` at
import and later ``except SchwabPipelineActiveError`` -- then no longer catches a
freshly-raised instance (different class object), so the route returns HTTP 500
instead of its intended 409/400. Under ``pytest -n auto`` xdist co-locates a
research L2-LOCK test before a web-route test on the same worker, surfacing this
as NON-DETERMINISTIC web-route failures (17-D.4: ``test_hyp_recs_expand_route`` +
``test_schwab_setup_route``, both clean in isolation).

This autouse fixture makes the research suite hermetic with respect to the
PRODUCTION (``swing.*``) modules it drops. It snapshots ``sys.modules`` before
each research test and, at teardown, for any ``swing.*`` key the test deleted or
replaced, restores BOTH the ``sys.modules`` entry (so ``import x.y.z`` /
``from x.y.z import ...`` see the original object again) AND the corresponding
attribute on the parent package object (so attribute-style access agrees with
``sys.modules``). The snapshot/restore helpers live in
``tests/research/_sys_modules_isolation.py`` so tests can exercise them directly.

Scope is deliberately limited to ``swing.*``:

  * Healing ``swing.integrations.schwab.*`` and ``swing.data.ohlcv_archive`` (the
    only production modules these L2-LOCK tests drop) repairs every web-route
    victim that bound one of their classes/exceptions earlier in the process --
    not just the two observed routes -- and covers future research tests that
    forget to restore.
  * It must NOT restore the ``research.harness.*`` package tree: those tests
    intentionally re-import their own subpackages, and blindly restoring a parent
    package object to a pre-test snapshot drops submodule attributes (e.g.
    ``research.harness.pattern_cohort_evaluator.run``) that sibling tests rely on
    via ``monkeypatch.setattr("...run...")``. The research tests already manage
    their own subtree (their L2-LOCK assertions re-import it fresh each run).
  * Third-party modules (``yfinance`` / ``schwabdev``) are left to the tests'
    own sentinel handling.

It does NOT touch production code or weaken any logging / redaction behavior; it
only repairs test-induced ``swing.*`` ``sys.modules`` damage at the polluter's
boundary.
"""
from __future__ import annotations

import pytest

from tests.research._sys_modules_isolation import (
    _restore_swing_modules,
    _swing_module_snapshot,
)


@pytest.fixture(autouse=True)
def _restore_swing_sys_modules_identity():
    """Restore any ``swing.*`` ``sys.modules`` entry a research test dropped.

    Snapshot at setup; restore (sys.modules entries + parent-package attributes)
    at teardown. See module docstring for why scope is limited to ``swing.*``.
    """
    snapshot = _swing_module_snapshot()
    try:
        yield
    finally:
        _restore_swing_modules(snapshot)
