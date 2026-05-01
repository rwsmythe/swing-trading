"""Phase 4.5 — TradeEntryFormVM.hypothesis_label resolution.

build_entry_form_vm resolves the active hypothesis recommendation label
at form-render time via lookup_active_recommendation_label (snapshot-
at-entry-surface; ToCToU fix per spec §3.6 / Phase 5 lesson). The
resolved value flows through a hidden form field to the POST handler
in Task 4 and persists AS-IS via record_entry.

Test seed pattern mirrors tests/cli/test_cli_trade_entry_hypothesis_prefill.py.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from swing.data.db import connect


def _seed_aplus_pipeline(db_path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_build_entry_form_vm_populates_exact_matcher_label_when_recommendation_exists(
    seeded_db,
):
    """Discriminating (per Codex R1 Major 3): with an A+ candidate seeded
    for AAPL, the VM carries hypothesis_label EXACTLY equal to the
    matcher's deterministic output "A+ baseline (aplus)" — the constant
    pinned at the top of this plan. Exact-equality (not prefix-match)
    catches a class of bugs where the VM transforms or truncates the
    label between helper-return and dataclass-construct.

    Sanity: if build_entry_form_vm never calls
    lookup_active_recommendation_label (e.g. the new resolution line is
    missing or guarded behind an unreachable branch), the field stays
    at its dataclass default (None) and this exact-equality assertion
    fails.
    """
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )

    assert vm.hypothesis_label == "A+ baseline (aplus)", (
        f"VM must carry exact matcher label; got {vm.hypothesis_label!r}"
    )


def test_build_entry_form_vm_returns_None_hypothesis_label_when_no_candidate(
    seeded_db,
):
    """Degenerate: ticker has no candidate row in the latest evaluation
    → vm.hypothesis_label is None. Preserves the no-match → empty
    persistence guarantee for off-pipeline trade entries.

    Sanity: if the helper falsely cross-resolved from another ticker's
    row (cursor-iteration bug), this assertion would fail.
    """
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="ZZZ", cfg=cfg, cache=cache, executor=MagicMock(),
    )

    assert vm.hypothesis_label is None
