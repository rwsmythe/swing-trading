def test_pattern_classification_dataclass_shape():
    from swing.data.models import PipelinePatternClassification
    row = PipelinePatternClassification(
        id=1, pipeline_run_id=2, ticker="AAPL",
        pattern="flag", confidence=0.78,
        components_json='{"a":1}',
        pivot=10.0, pole_high=11.0, flag_low=9.0,
        pole_start_date="2026-04-01", pole_end_date="2026-04-10",
        flag_start_date="2026-04-11", flag_end_date="2026-04-18",
        computed_at="2026-04-26T00:00:00",
    )
    assert row.pattern == "flag"
    assert row.confidence == 0.78


def test_pattern_classification_anchor_date_annotations_are_date_or_none():
    """Task 5.0a (Phase 2 carve-out extension; Phase 4 → Phase 5 handoff):
    The four anchor-date fields on PipelinePatternClassification must be
    annotated as ``date | None``, not ``str | None``. Phase 4's Task 4.0a
    fixed runtime parsing in ``_row_to_classification`` to return ``date``
    objects; Phase 5 brings the dataclass annotation in line with runtime.

    Discriminating: pre-fix returns ``str | None``; post-fix returns
    ``date | None``. Compounding-confound: also asserts the round-trip
    runtime value through ``insert_classification`` →
    ``get_classification`` returns a ``date`` instance, so a future
    accidental revert that drops ``_parse_date`` would also fail.
    """
    from datetime import date
    from typing import get_type_hints

    from swing.data.models import PipelinePatternClassification

    hints = get_type_hints(PipelinePatternClassification)
    expected = date | None
    assert hints["pole_start_date"] == expected
    assert hints["pole_end_date"] == expected
    assert hints["flag_start_date"] == expected
    assert hints["flag_end_date"] == expected


def test_trade_has_four_chart_pattern_fields():
    from swing.data.models import Trade
    t = Trade(
        id=None, ticker="AAPL", entry_date="2026-04-26",
        entry_price=10.0, initial_shares=1, initial_stop=9.0,
        current_stop=9.0, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    assert t.hypothesis_label is None
    assert t.chart_pattern_algo is None
    assert t.chart_pattern_algo_confidence is None
    assert t.chart_pattern_operator is None
    assert t.chart_pattern_classification_pipeline_run_id is None
