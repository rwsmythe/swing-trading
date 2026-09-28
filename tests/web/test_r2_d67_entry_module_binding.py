"""R-2 (2026-09-28) -- the D67 L1 follow-on, CHARC-ruled 2026-09-24.

``swing/trades/entry.py`` binds ``insert_trade_with_event`` BY NAME at its
own first import (``from swing.data.repos.trades import
insert_trade_with_event``), a reference living in ``entry.py``'s OWN module
namespace. The ``tests/web/conftest.py`` autouse fixture used to patch only
``swing.data.repos.trades`` and ``swing.web.routes.trades`` -- never the
name at its actual lookup site inside ``entry.py`` -- so in a FULL suite
run, where ``tests/trades/`` imports ``swing.trades.entry`` before any web
fixture has run, ``record_entry`` calls the REAL ``insert_trade_with_event``
and the wrapper is never reached at all (run alone, the fixture happens to
patch first, so it looked reached).

This module reproduces the FULL-RUN import order DETERMINISTICALLY, in
isolation: it imports ``swing.trades.entry`` at MODULE TOP, which forces the
module's by-name binding to be captured (at THIS file's collection time,
before any per-test fixture has run) exactly the way the full suite's
``tests/trades/`` import does. The discriminator: a sentinel side effect
(``_wrapped_insert_trade_calls``, the conftest fixture) asserted AFTER
``record_entry`` -- the wrapper must be REACHED regardless of which module
imported ``swing.trades.entry`` first.

RED on the unmodified conftest (only ``trades_repo`` + the route module
patched): the sentinel list is empty after ``record_entry`` runs, because
``entry.py``'s own ``insert_trade_with_event`` name still points at the
REAL function. GREEN after: the conftest ALSO patches
``swing.trades.entry.insert_trade_with_event`` directly, at every test's
setup, so the wrapper is reached regardless of import order.
"""
from __future__ import annotations

import types

import pytest

# MODULE-TOP import -- forces swing.trades.entry's own by-name binding
# (`from swing.data.repos.trades import insert_trade_with_event`) to be
# captured at THIS file's collection time, before ANY per-test autouse
# fixture has run. This is the exact ordering tests/trades/ produces in a
# full suite run (tests/trades/ sorts before tests/web/), made
# deterministic here rather than depending on collection order across
# directories.
import swing.trades.entry  # noqa: F401  (import side effect is the point)

from swing.data.db import connect  # noqa: E402
from swing.trades.entry import EntryRequest, record_entry  # noqa: E402


def _entry_request(**overrides) -> EntryRequest:
    base = dict(
        ticker="R2TEST",
        entry_date="2026-09-28",
        entry_price=10.0,
        shares=100,
        initial_stop=9.0,
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes="R-2 discriminator",
        rationale="watchlist_breakout",
        event_ts="2026-09-28T09:30:00",
        thesis="test-thesis",
        why_now="test-why-now",
        invalidation_condition="stop-hit",
        expected_scenario="win",
        premortem_technical="tech-risk",
        premortem_market_sector="market-risk",
        premortem_execution="execution-risk",
        event_risk_present=0,
        event_handling="not_applicable",
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm"]',
        manual_entry_confidence="normal",
        market_regime="Bullish",
        catalyst="technical_only",
    )
    base.update(overrides)
    return EntryRequest(**base)


def test_record_entry_reaches_the_wrapper_under_full_run_import_order(
    seeded_db, _wrapped_insert_trade_calls,
):
    """The discriminator: record_entry (through swing.trades.entry, whose
    by-name binding was captured at module-collection time above, BEFORE
    this test's autouse fixture ran) must still route through the
    conftest wrapper -- not the real insert_trade_with_event."""
    cfg, _cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        req = _entry_request()
        result = record_entry(
            conn, req, soft_warn=cfg.position_limits.soft_warn_open,
            hard_cap=cfg.position_limits.hard_cap_open, force=False, cfg=cfg,
        )
        conn.commit()

        # RED on the unmodified conftest: this list is empty (the wrapper
        # was never reached; entry.py called the real function directly).
        assert _wrapped_insert_trade_calls, (
            "the wrapper was never reached -- swing.trades.entry.py's own "
            "insert_trade_with_event name was not patched"
        )
        assert any(
            call["via_record_entry"] for call in _wrapped_insert_trade_calls
        ), "the wrapper was reached but not via record_entry's own attempt_id"

        # The wrapper's existing called_via_record_entry skip must still
        # hold: record_entry inserts its OWN entry fill, so exactly ONE
        # entry fill exists and current_size is not doubled.
        fill_rows = conn.execute(
            "SELECT COUNT(*) FROM fills WHERE trade_id = ? AND action = 'entry'",
            (result.trade_id,),
        ).fetchone()
        assert fill_rows[0] == 1, (
            "exactly one entry fill expected -- a double-fill means the "
            "wrapper's skip guard did not hold once reached"
        )
        current_size = conn.execute(
            "SELECT current_size FROM trades WHERE id = ?", (result.trade_id,),
        ).fetchone()[0]
        assert current_size == 100
    finally:
        conn.close()


def test_import_order_determines_whether_a_by_name_binding_leaks_after_teardown() -> None:
    """Codex R1 minor (2026-09-28, this dispatch's round-1 review): fixture-
    scoped ``monkeypatch.setattr(entry_module, "insert_trade_with_event",
    wrapped)`` only correctly restores the REAL function at teardown if
    ``entry_module``'s binding was NOT itself captured -- via a first-ever
    ``import swing.trades.entry`` -- AFTER ``trades_repo`` was already
    patched in that SAME test. If it were, the import's OWN execution
    (``from swing.data.repos.trades import insert_trade_with_event``) binds
    the module's name to THAT TEST'S wrapped closure as a side effect,
    ``monkeypatch.setattr`` then records that already-wrapped value as
    "original", and teardown restores it right back to the dead closure --
    pinned there until the next test's own patch overwrites it (never
    observed by ``record_entry``, which always passes ``attempt_id`` and so
    always takes the wrapper's delegate-to-real branch regardless of which
    closure answers -- but a real, needless leak).

    This reproduces the mechanism on a THROWAWAY synthetic module (never
    the real ``swing.trades.entry``, to avoid an xdist-fragile
    ``sys.modules`` del/re-import -- CLAUDE.md's raw-del gotcha), proving
    BOTH halves in one test: the OLD (buggy) order -- patch-source-first,
    bind-name-second -- leaks; the FIXED order the conftest fixture now
    uses -- bind-name-first, patch-source-second -- does not.
    """
    def real_fn(x: int) -> int:
        return x

    # OLD (buggy) order: patch the "trades_repo" stand-in FIRST, then
    # "import" (bind the module's own name to whatever the source
    # currently holds) SECOND -- reproduces entry.py's first-ever import
    # happening AFTER a test already patched what it imports from.
    stand_in_repo_buggy = types.SimpleNamespace(insert_trade_with_event=real_fn)
    mod_buggy = types.ModuleType("throwaway_entry_buggy_order")
    with pytest.MonkeyPatch().context() as mp:
        def wrapped_buggy(x: int) -> int:
            return real_fn(x)
        mp.setattr(stand_in_repo_buggy, "insert_trade_with_event", wrapped_buggy)
        # the "import" happens NOW, after the patch -- captures wrapped_buggy
        mod_buggy.insert_trade_with_event = stand_in_repo_buggy.insert_trade_with_event
        mp.setattr(mod_buggy, "insert_trade_with_event", wrapped_buggy)
        assert mod_buggy.insert_trade_with_event is wrapped_buggy
    # RED shape: teardown left the buggy-order module PINNED to the dead
    # closure, not restored to the real function.
    assert mod_buggy.insert_trade_with_event is wrapped_buggy, (
        "reproduces the leak the pre-fix conftest ordering had"
    )

    # FIXED order: "import" (bind) FIRST, patch the source SECOND -- the
    # conftest fixture's ordering after this rider's fix.
    stand_in_repo_fixed = types.SimpleNamespace(insert_trade_with_event=real_fn)
    mod_fixed = types.ModuleType("throwaway_entry_fixed_order")
    mod_fixed.insert_trade_with_event = stand_in_repo_fixed.insert_trade_with_event
    with pytest.MonkeyPatch().context() as mp:
        def wrapped_fixed(x: int) -> int:
            return real_fn(x)
        mp.setattr(stand_in_repo_fixed, "insert_trade_with_event", wrapped_fixed)
        mp.setattr(mod_fixed, "insert_trade_with_event", wrapped_fixed)
        assert mod_fixed.insert_trade_with_event is wrapped_fixed
    # GREEN shape: teardown correctly restored the fixed-order module to
    # the real function -- no leak.
    assert mod_fixed.insert_trade_with_event is real_fn, (
        "the fix: import-before-patch lets monkeypatch correctly restore "
        "the real function at teardown"
    )
