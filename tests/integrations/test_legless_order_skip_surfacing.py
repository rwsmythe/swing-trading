"""Item-5 rider 1 -- legless Schwab orders are COUNTED and SURFACED.

RD's ruling: the minimum fix is COUNT-AND-SURFACE, not stop-skipping. Refusing
to skip would fail the whole orders fetch on a legitimately legless
parent-conditional row, and that resilience is correct. What is wrong is that
the skip is INVISIBLE: downstream a dropped order is a FALSE NEGATIVE ON A FILL
-- reconciliation sees no fill, raises no discrepancy, reports clean. The
instrument does not alarm; it goes quiet. Gotcha #27 in a mapper rather than a
pipeline step.

BOTH-MODES REQUIREMENT (recipe section 2A, RD's attached rule): a negative test
asserting only "it did not fire" passes regardless of the logic it claims to
pin. So every negative test here asserts the COUNTERFACTUAL fields (the skip
list is empty AND the returned order count equals the input count), and the
founding case runs BOTH with and without the accumulator supplied.

No incidence-rate claim is made anywhere in this file -- RD is explicitly not
asserting one; the ruling rests on the asymmetry.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.integrations.schwab.mappers import map_orders_to_fill_candidates
from swing.trades.reconciliation_backfill import (
    BackfillSummary,
    _fold_legless_skips,
    format_summary_block,
)


def _well_formed_order(order_id: str = "1001", symbol: str = "FTRE") -> dict:
    return {
        "orderId": order_id,
        "status": "FILLED",
        "enteredTime": "2026-07-23T14:30:00.000Z",
        "orderType": "LIMIT",
        "price": 18.8,
        "quantity": 10,
        "orderLegCollection": [{
            "instruction": "BUY",
            "quantity": 10,
            "instrument": {"symbol": symbol, "assetType": "EQUITY"},
        }],
    }


def _legless_order(order_id: str = "2002") -> dict:
    """A parent-conditional row: no orderLegCollection at all. The mapper
    SKIPPING this is correct; the skip being invisible is not."""
    return {
        "orderId": order_id,
        "status": "WORKING",
        "enteredTime": "2026-07-23T14:30:00.000Z",
        "orderType": "MARKET",
        "orderLegCollection": [],
    }


def _non_dict_leg_order(order_id: str = "3003") -> dict:
    """The SECOND silent branch, which the register's own wording did not
    name: orderLegCollection[0] is not a dict."""
    return {
        "orderId": order_id,
        "status": "FILLED",
        "enteredTime": "2026-07-23T14:30:00.000Z",
        "orderType": "MARKET",
        "orderLegCollection": ["not-a-dict"],
    }


# ===========================================================================
# The mapper
# ===========================================================================


def test_the_mapper_return_shape_is_unchanged_without_an_accumulator():
    """The single contract at all three layers: RETURN SHAPES NEVER CHANGE.
    A caller that passes no list gets today's behaviour byte-for-byte."""
    out = map_orders_to_fill_candidates([
        _well_formed_order("1001"), _legless_order("2002"),
    ])
    assert isinstance(out, list)
    assert [o.order_id for o in out] == ["1001"]


def test_the_mapper_records_a_missing_leg_collection_skip():
    skips: list[dict] = []
    out = map_orders_to_fill_candidates(
        [_well_formed_order("1001"), _legless_order("2002")], skips=skips,
    )
    assert [o.order_id for o in out] == ["1001"]
    assert skips == [{
        "order_id": "2002", "index": 1,
        "reason": "missing_or_empty_leg_collection",
    }]


def test_the_mapper_records_a_non_dict_leg_skip():
    """BOTH silent branches count, not just the one the register named."""
    skips: list[dict] = []
    out = map_orders_to_fill_candidates(
        [_non_dict_leg_order("3003"), _well_formed_order("1001")], skips=skips,
    )
    assert [o.order_id for o in out] == ["1001"]
    assert skips == [{
        "order_id": "3003", "index": 0, "reason": "non_dict_leg_0",
    }]


def test_the_mapper_still_SKIPS_rather_than_raising():
    """Stop-skipping is NOT the fix. A legitimately legless parent-conditional
    row must not fail the whole orders fetch."""
    skips: list[dict] = []
    out = map_orders_to_fill_candidates([_legless_order("2002")], skips=skips)
    assert out == []
    assert len(skips) == 1


def test_a_well_formed_payload_produces_an_EMPTY_skip_list():
    """The negative case, asserting the COUNTERFACTUAL fields rather than
    merely 'it did not fire': the list is empty AND every input order came
    back."""
    orders = [_well_formed_order(str(1000 + i)) for i in range(3)]
    skips: list[dict] = []
    out = map_orders_to_fill_candidates(orders, skips=skips)
    assert skips == []
    assert len(out) == len(orders)
    assert [o.order_id for o in out] == ["1000", "1001", "1002"]


def test_the_founding_case_runs_BOTH_with_and_without_the_accumulator():
    """A feature reached only through an optional parameter can pass its own
    tests while every production caller misses it. Same payload, both modes,
    identical mapped output."""
    payload = [
        _well_formed_order("1001"),
        _legless_order("2002"),
        _non_dict_leg_order("3003"),
    ]
    unarmed = map_orders_to_fill_candidates(payload)
    skips: list[dict] = []
    armed = map_orders_to_fill_candidates(payload, skips=skips)
    assert [o.order_id for o in unarmed] == [o.order_id for o in armed] == [
        "1001",
    ]
    assert len(skips) == 2
    assert {s["reason"] for s in skips} == {
        "missing_or_empty_leg_collection", "non_dict_leg_0",
    }


# ===========================================================================
# The wrappers -- the seam the first design could not cross
# ===========================================================================


def test_both_wrappers_expose_the_accumulator_keyword():
    """`_call_endpoint` invokes `mapper(payload)` POSITIONALLY with exactly one
    argument, so a `skips=` keyword cannot reach the mapper through it. The
    accumulator has to ride in a functools.partial closure -- and BOTH wrappers
    need it, because the AUDITED variant is the one feeding the Pass-2 backfill
    (threading only the first would leave that half exactly as blind)."""
    import inspect

    from swing.integrations.schwab import trader

    for fn in (trader.get_account_orders, trader.get_account_orders_audited):
        params = inspect.signature(fn).parameters
        assert "skips" in params, fn.__name__
        assert params["skips"].default is None, fn.__name__
        assert params["skips"].kind is inspect.Parameter.KEYWORD_ONLY


def test_call_endpoint_is_not_widened():
    """`_call_endpoint` is shared by every Schwab endpoint and has no business
    knowing about order legs."""
    import inspect

    from swing.integrations.schwab import trader

    assert "skips" not in inspect.signature(trader._call_endpoint).parameters


# ===========================================================================
# Pass 1 -- the pipeline step, on EVERY post-fetch return path
# ===========================================================================


def _cfg(environment: str = "production") -> SimpleNamespace:
    return SimpleNamespace(
        integrations=SimpleNamespace(schwab=SimpleNamespace(
            environment=environment,
            account_hash="abc...64charhash",
            lookback_days=7,
            timeout_seconds=30.0,
            marketdata_ladder_enabled=True,
            callback_url="https://127.0.0.1",
        )),
        account=SimpleNamespace(starting_equity=0.0),
        reconciliation=SimpleNamespace(out_of_framework_tickers=()),
    )


def _resp(value, *, status_code: int = 200):
    r = MagicMock()
    r.json.return_value = value
    r.status_code = status_code
    r.headers = {}
    return r


def _client(orders_payload):
    client = MagicMock()
    client.account_orders.return_value = _resp(orders_payload)
    client.transactions.return_value = _resp([])
    client.account_details.return_value = _resp({
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": 2014.36, "cashBalance": 100.0,
                "buyingPower": 4000.0,
            },
            "positions": [],
        },
    })
    return client


@pytest.fixture
def conn(tmp_path):
    from swing.data.db import ensure_schema
    c = ensure_schema(tmp_path / "legless.db")
    yield c
    c.close()


def _legless_entries(result: dict) -> list[dict]:
    return [
        w for w in (result.get("warnings") or [])
        if w.get("reason") == "legless_orders_skipped"
    ]


def test_pass1_success_path_surfaces_the_skip(conn):
    from swing.integrations.schwab.pipeline_steps import _step_schwab_orders

    result = _step_schwab_orders(
        conn, _cfg(), pipeline_run_id=None,
        client=_client([_well_formed_order("1001"), _legless_order("2002")]),
    )
    assert result["status"] == "completed"
    entries = _legless_entries(result)
    assert len(entries) == 1
    assert entries[0]["step"] == "schwab_orders"
    assert entries[0]["skipped_count"] == 1
    assert entries[0]["order_ids"] == ["2002"]


def test_pass1_success_path_with_a_clean_payload_emits_NO_legless_entry(conn):
    """Counterfactual: the OTHER warnings still flow, so this is not passing
    because the envelope is empty."""
    from swing.integrations.schwab.pipeline_steps import _step_schwab_orders

    result = _step_schwab_orders(
        conn, _cfg(), pipeline_run_id=None,
        client=_client([_well_formed_order("1001")]),
    )
    assert result["status"] == "completed"
    assert _legless_entries(result) == []
    assert result["warnings"], "no warnings at all -- the assertion is vacuous"


def test_pass1_SANDBOX_short_circuit_still_surfaces_the_skip(conn):
    """A skip recorded at the fetch and dropped by an early return would be a
    silent skip inside the fix for silent skips."""
    from swing.integrations.schwab.pipeline_steps import _step_schwab_orders

    result = _step_schwab_orders(
        conn, _cfg(environment="sandbox"), pipeline_run_id=None,
        client=_client([_well_formed_order("1001"), _legless_order("2002")]),
    )
    assert result["status"] == "sandbox_audit_only"
    entries = _legless_entries(result)
    assert len(entries) == 1
    assert entries[0]["order_ids"] == ["2002"]


def test_pass1_TRADER_API_FAILURE_path_still_surfaces_the_skip(conn):
    """The sharpest early-return case: the ORDERS fetch SUCCEEDS (so the skip
    is already recorded) and a LATER Trader call raises. Pre-fix that return
    dict carried no `warnings` key at all, so the recorded skip evaporated."""
    from swing.integrations.schwab.client import SchwabApiError
    from swing.integrations.schwab.pipeline_steps import _step_schwab_orders

    client = _client([_well_formed_order("1001"), _legless_order("2002")])
    client.transactions.side_effect = SchwabApiError(500, "boom")

    result = _step_schwab_orders(
        conn, _cfg(), pipeline_run_id=None, client=client,
    )
    assert result["status"] == "failed"
    entries = _legless_entries(result)
    assert len(entries) == 1
    assert entries[0]["order_ids"] == ["2002"]


def test_pass1_RECONCILIATION_FAILURE_path_still_surfaces_the_skip(
    conn, monkeypatch,
):
    from swing.integrations.schwab import pipeline_steps

    def _boom(*a, **k):
        raise RuntimeError("recon exploded")

    monkeypatch.setattr(
        "swing.trades.schwab_reconciliation.run_schwab_reconciliation", _boom,
    )
    result = pipeline_steps._step_schwab_orders(
        conn, _cfg(), pipeline_run_id=None,
        client=_client([_well_formed_order("1001"), _legless_order("2002")]),
    )
    assert result["status"] == "failed"
    entries = _legless_entries(result)
    assert len(entries) == 1
    assert entries[0]["order_ids"] == ["2002"]


def test_the_runner_merges_the_step_warnings_from_a_failure_dict():
    """The runner reads `result.get('warnings')` regardless of status, so the
    failure/sandbox dicts reach `pipeline_runs.warnings_json` the same way the
    success dict does. Pinned as a CALLER-SIDE obligation rather than assumed
    (gotcha #31: pin what the caller MUST do)."""
    import inspect

    from swing.pipeline import runner

    src = inspect.getsource(runner)
    assert '(_schwab_result or {}).get("warnings")' in src


# ===========================================================================
# Pass 2 -- the backfill, which has NO warning envelope of its own
# ===========================================================================


def test_backfill_summary_carries_the_counter_and_the_ids():
    summary = BackfillSummary()
    assert summary.legless_orders_skipped == 0
    assert summary.legless_order_ids == []
    _fold_legless_skips(summary, [
        {"order_id": "2002", "index": 1,
         "reason": "missing_or_empty_leg_collection"},
        {"order_id": "3003", "index": 4, "reason": "non_dict_leg_0"},
    ])
    assert summary.legless_orders_skipped == 2
    assert summary.legless_order_ids == ["2002", "3003"]


def test_the_fold_clears_the_accumulator_so_nothing_is_double_counted():
    summary = BackfillSummary()
    skips = [{"order_id": "2002", "index": 0, "reason": "non_dict_leg_0"}]
    _fold_legless_skips(summary, skips)
    assert skips == []
    _fold_legless_skips(summary, skips)
    assert summary.legless_orders_skipped == 1


def test_the_summary_block_RENDERS_the_gap():
    """The SURFACE half. A counter nobody prints is a quieter silence, not a
    fix -- and this is the assertion that pins the difference."""
    summary = BackfillSummary()
    _fold_legless_skips(summary, [
        {"order_id": "2002", "index": 1,
         "reason": "missing_or_empty_leg_collection"},
    ])
    block = format_summary_block(summary)
    assert "Legless Schwab orders SKIPPED by the mapper: 1" in block
    assert "2002" in block
    block.encode("cp1252")


def test_the_summary_block_is_SILENT_when_nothing_was_skipped():
    block = format_summary_block(BackfillSummary())
    assert "Legless" not in block
    # Counterfactual: the block is not empty, so the assertion is not vacuous.
    assert "Backfill summary:" in block


def test_an_ABORTED_backfill_still_reports_what_it_dropped():
    """The partial-summary path renders through the same function, so an
    interrupted run does not swallow the gap."""
    summary = BackfillSummary()
    _fold_legless_skips(summary, [
        {"order_id": "2002", "index": 0, "reason": "non_dict_leg_0"},
    ])
    summary.aborted_mid_iteration = True
    summary.abort_reason = "pipeline started"
    block = format_summary_block(summary)
    assert "ABORTED MID-ITERATION" in block
    assert "Legless Schwab orders SKIPPED by the mapper: 1" in block


def test_pass2_dispatch_threads_the_accumulator_to_the_audited_wrapper():
    """The whole Pass-2 half turns on this one keyword reaching
    `get_account_orders_audited`; without it the backfill collects nothing."""
    import inspect

    from swing.trades import reconciliation_backfill as bf

    for fn in (
        bf._pass_2_dispatch, bf._handle_pass_2, bf._classify_and_apply,
    ):
        assert "legless_skips" in inspect.signature(fn).parameters, fn.__name__
    src = inspect.getsource(bf._pass_2_dispatch)
    assert "skips=legless_skips" in src


def test_r1_M4_a_POST_FETCH_raise_still_folds_the_recorded_skips():
    """Codex R1 Major 4. Legless skips sat in the local accumulator until
    `_classify_and_apply` RETURNED. But that call can raise AFTER the audited
    Schwab fetch has already recorded skips -- the per-iteration
    pipeline-exclusion recheck inside `_handle_pass_2` raises
    `BackfillPipelineActiveError` carrying the summary as its partial, and the
    post-fetch classifier path can raise too. A fold that only ran on the
    success path would drop an already-observed legless order out of the
    aborted summary: this rider's own failure mode, reproduced inside its own
    remedy.

    Driven through the REAL `run_backfill` loop with a stub
    `_classify_and_apply` that fills the accumulator and then raises, so the
    assertion is about the loop's control flow rather than about a helper.
    """
    import sqlite3
    import tempfile
    from pathlib import Path as _P

    from swing.data.db import ensure_schema
    from swing.trades import reconciliation_backfill as bf

    conn = ensure_schema(_P(tempfile.mkdtemp()) / "abort.db")
    try:
        run_id = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('schwab_api', '2026-08-09T00:00:00', 'completed')",
        ).lastrowid
        conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, field_name, material_to_review, resolution, "
            "created_at) VALUES (?, 'unmatched_open_fill', 'fill_match', 1, "
            "'unresolved', '2026-08-09T00:00:00')", (run_id,),
        )
        conn.commit()

        real = bf._classify_and_apply

        def _fetch_then_raise(*a, legless_skips=None, partial_summary=None, **k):
            assert legless_skips is not None, (
                "the accumulator never reached _classify_and_apply"
            )
            # The audited fetch has already happened and recorded a skip; THEN
            # the pipeline-exclusion recheck fires.
            legless_skips.append({
                "order_id": "2002", "index": 0,
                "reason": "missing_or_empty_leg_collection",
            })
            raise bf.BackfillPipelineActiveError(
                "pipeline started mid-iteration",
                partial_summary=partial_summary,
            )

        bf._classify_and_apply = _fetch_then_raise
        try:
            with pytest.raises(bf.BackfillPipelineActiveError) as exc:
                bf.run_backfill(
                    conn, dry_run=True, schwab_client=None,
                    environment="production", account_hash=None,
                )
        finally:
            bf._classify_and_apply = real

        partial = exc.value.partial_summary
        assert partial is not None
        # PRE-FIX this reads 0: the fold ran only after a successful return.
        assert partial.legless_orders_skipped == 1
        assert partial.legless_order_ids == ["2002"]
        block = format_summary_block(partial)
        assert "Legless Schwab orders SKIPPED by the mapper: 1" in block
        assert "2002" in block
    finally:
        conn.close()
    assert isinstance(sqlite3.Connection, type)
