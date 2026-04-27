def test_trade_has_chart_pattern_fields_with_none_defaults():
    from swing.data.models import Trade

    t = Trade(
        id=None,
        ticker="AAPL",
        entry_date="2026-04-01",
        entry_price=100.0,
        initial_shares=10,
        initial_stop=95.0,
        current_stop=95.0,
        status="open",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
    )

    assert t.chart_pattern_algo is None
    assert t.chart_pattern_algo_confidence is None
    assert t.chart_pattern_operator is None
    assert t.chart_pattern_classification_pipeline_run_id is None
