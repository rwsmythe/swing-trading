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
PRODUCTION (``swing.*``) modules it drops: it snapshots ``sys.modules`` before
each research test and, at teardown, restores the original object for any
``swing.*`` key that the test deleted or replaced. Modules first imported DURING
the test (genuinely new keys) are left in place so normal import caching is
unaffected -- only deletions and identity replacements of already-cached
``swing.*`` modules are healed.

Scope is deliberately limited to ``swing.*``:

  * Healing ``swing.integrations.schwab.*`` and ``swing.data.ohlcv_archive`` (the
    only production modules these L2-LOCK tests drop) closes the entire class of
    web-route victims -- every module that bound one of their classes/exceptions
    earlier in the process -- not just the two observed routes, and it covers
    future research tests that forget to restore.
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

import sys

import pytest


@pytest.fixture(autouse=True)
def _restore_swing_sys_modules_identity():
    """Restore any ``swing.*`` ``sys.modules`` entry a research test dropped.

    Snapshot at setup; at teardown, for every ``swing.*`` key present in the
    snapshot whose current value is no longer the original object (deleted ->
    absent, or replaced -> different object), put the original object back. Keys
    added during the test, and all non-``swing.*`` keys (notably the
    ``research.harness.*`` package tree), are left untouched.
    """
    snapshot = {
        name: mod for name, mod in sys.modules.items()
        if name == "swing" or name.startswith("swing.")
    }
    try:
        yield
    finally:
        for name, original in snapshot.items():
            if sys.modules.get(name) is not original:
                sys.modules[name] = original
