"""Phase 5 Task 5.3 — trade-entry form template renders the Chart
Pattern section (algo display + override dropdown + hidden snapshot
inputs) when a cached classification exists, and the "Not classified"
stub when it doesn't.

Spec §3.6 form fragment. The Chart Pattern section lives in its own
shared include partial (``partials/trade_entry_chart_pattern_section.html.j2``)
per CLAUDE.md HTMX OOB-swap discipline — any future row-reload OOB-swap
path that re-renders this section will reach the same markup, no
hand-duplication.

Assertions use exact fragments (per discriminating-test discipline +
2026-04-26 lesson: substring-match assertions almost never distinguish
pre-fix from post-fix on rendered HTML). Each fragment is a complete,
unambiguous element so a regression that drops an attribute, changes
the option value, or swaps element nesting will fail.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache

from ..test_view_models._pattern_classification_seed import (
    seed_pipeline_with_classification,
)


def _patch_price_cache(monkeypatch):
    """Stub PriceCache so the route doesn't try to fetch prices."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_entry_form_renders_chart_pattern_section_when_evaluated(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-Task-5.3, the form template doesn't reference
    chart_pattern_* fields so none of these tokens render. Post-fix:
    hidden snapshot inputs + override dropdown are present.
    """
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Hidden snapshot inputs — exact fragments.
    assert (
        '<input type="hidden" name="chart_pattern_algo" value="flag">'
        in body
    )
    assert (
        '<input type="hidden" name="chart_pattern_algo_confidence" '
        'value="0.78">'
        in body
    )
    assert (
        '<input type="hidden" name="chart_pattern_classification_pipeline_run_id" '
        f'value="{run_id}">'
        in body
    )

    # Override dropdown options — exact fragments.
    assert '<option value="">Accept algo</option>' in body
    assert '<option value="flag">flag</option>' in body
    assert '<option value="none">none</option>' in body
    assert '<option value="other">other (specify)</option>' in body
    # Free-text companion input for "other".
    assert 'name="chart_pattern_operator_other"' in body

    # Algo display fragment — exact "<strong>flag</strong> (0.78)".
    assert "<strong>flag</strong> (0.78)" in body


def test_entry_form_renders_not_classified_stub_when_unevaluated(
    seeded_db, monkeypatch,
):
    """Compounding-confound: with a watchlist row but NO classification,
    the override surface must NOT render — the operator should not be
    able to submit a value the CLI parity gate would have refused.

    Discriminating: post-Task-5.3 the stub fragment text shows up, and
    the override dropdown is structurally absent. With the algo-display
    dropdown structurally tied to ``chart_pattern_algo_evaluated``, this
    catches a regression that renders the dropdown unconditionally.
    """
    cfg, cfg_path = seeded_db
    # Seed a watchlist row for NOPE but NO classification.
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, last_qualified_date, "
            "status, qualification_count, not_qualified_streak, "
            "last_data_asof_date, entry_target, last_close) "
            "VALUES ('NOPE', '2026-04-01','2026-04-26','watch',1,0,"
            "'2026-04-25',110.0,100.0)"
        )
        conn.commit()
    finally:
        conn.close()
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=NOPE")
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert (
        '<div class="subtitle">Not classified '
        "(out-of-scope or no recent pipeline run).</div>"
    ) in body
    # Override dropdown MUST NOT appear when unevaluated (cached-only
    # consumption gate's UI half — the CLI half is Task 5.5).
    assert 'name="chart_pattern_operator"' not in body
    # Hidden algo input also absent (no snapshot to flow).
    assert 'name="chart_pattern_algo"' not in body
