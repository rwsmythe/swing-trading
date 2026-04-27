"""Phase 5 Task 5.2 — `TradeEntryFormVM` gains 4 chart_pattern fields;
``build_entry_form_vm`` resolves the cache row at the entry-surface.

Spec §3.6: cache resolution happens ONCE here (the form-render
boundary). The resolved values flow through hidden form fields to the
POST handler; ``record_entry`` persists what's passed AS-IS. ToCToU
fix: a pipeline run completing between form render and submit cannot
change the persisted values vs the operator's view.

Bug-7-family anchor discipline (Phase 4 lesson): classifications bind
to ``pipeline_runs.evaluation_run_id → pipeline_run_id`` via the
single-round-trip ``SELECT id, evaluation_run_id FROM pipeline_runs
WHERE state='complete' ORDER BY finished_ts DESC LIMIT 1`` query. The
``id`` IS the parent ``pipeline_run_id`` by construction; no secondary
``WHERE evaluation_run_id = ?`` round-trip.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from swing.data.db import connect

from ._pattern_classification_seed import (
    seed_pipeline_with_classification,
)


def test_entry_form_vm_populates_chart_pattern_when_classification_exists(seeded_db):
    """Discriminating: pre-fix the VM has no chart_pattern_* fields
    (AttributeError); post-fix it carries algo='flag', confidence=0.78,
    evaluated=True, and the audit anchor pipeline_run_id."""
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.chart_pattern_algo == "flag"
    assert vm.chart_pattern_algo_confidence == 0.78
    assert vm.chart_pattern_algo_evaluated is True
    assert vm.chart_pattern_classification_pipeline_run_id == run_id


def test_entry_form_vm_chart_pattern_evaluated_False_for_classifier_error(seeded_db):
    """Classifier-error rows have pattern=NULL; UI must treat them as
    "not classified" so no spurious "flag (NULL)" artifact appears.

    Compounding-confound: keep all the same scaffolding (eval row,
    pipeline_run row, watchlist row) — only the classification row
    differs from the happy path. The discriminator is solely the
    pattern=NULL distinction.
    """
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    # Replace the seeded 'flag' row with a classifier-error row (pattern=NULL).
    conn = connect(cfg.paths.db_path)
    try:
        conn.execute(
            "DELETE FROM pipeline_pattern_classifications WHERE pipeline_run_id=?",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO pipeline_pattern_classifications "
            "(pipeline_run_id, ticker, pattern, confidence, components_json, computed_at) "
            "VALUES (?, ?, NULL, NULL, '{\"error\":\"boom\"}', '2026-04-26T00:00:00')",
            (run_id, "AAPL"),
        )
        conn.commit()
    finally:
        conn.close()
    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.chart_pattern_algo_evaluated is False
    assert vm.chart_pattern_algo is None
    assert vm.chart_pattern_algo_confidence is None


def test_entry_form_vm_chart_pattern_evaluated_False_for_no_cache_row(seeded_db):
    """Compounding-confound (anchor edition): with the cache row
    deleted, ``cp_evaluated`` is False even though the pipeline_run +
    eval scaffolding still exists. Proves the read binds to the cache
    row presence, not just the pipeline_run anchor."""
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    conn = connect(cfg.paths.db_path)
    try:
        conn.execute(
            "DELETE FROM pipeline_pattern_classifications WHERE pipeline_run_id=?",
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()
    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.chart_pattern_algo_evaluated is False
    assert vm.chart_pattern_algo is None
    assert vm.chart_pattern_classification_pipeline_run_id is None
