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
