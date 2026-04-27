"""Task 4.1+ — `_pattern_tags` helper + VM extensions.

Spec §3.5: SIBLING helper to `_flag_tags`. The flag tag is delivered to the
template via a SEPARATE field (`pattern_tags`) — NOT mixed into the
existing `tags` tuple. Sort-neutrality is structurally guaranteed by
construction (the flag tag never enters the `tags` tuple consumed by
`_sort_watchlist`).
"""
from __future__ import annotations

from datetime import date

from swing.data.models import PipelinePatternClassification


def _make_cls(
    ticker: str, pattern: str | None, conf: float | None,
) -> PipelinePatternClassification:
    return PipelinePatternClassification(
        id=1, pipeline_run_id=1, ticker=ticker,
        pattern=pattern, confidence=conf, components_json="{}",
        pivot=None, pole_high=None, flag_low=None,
        pole_start_date=date(2026, 4, 1) if pattern == "flag" else None,
        pole_end_date=date(2026, 4, 10) if pattern == "flag" else None,
        flag_start_date=date(2026, 4, 11) if pattern == "flag" else None,
        flag_end_date=date(2026, 4, 18) if pattern == "flag" else None,
        computed_at="ts",
    )


def test_pattern_tags_emits_flag_format_above_threshold():
    """Discriminating: pre-fix the helper doesn't exist (ImportError);
    post-fix it returns the formatted string for AAPL only."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {
        "AAPL": _make_cls("AAPL", "flag", 0.78),
        "MSFT": _make_cls("MSFT", "none", None),
    }
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {"AAPL": "flag (0.78)"}


def test_pattern_tags_filters_below_threshold():
    """Display-threshold gate: confidence 0.10 < threshold 0.50 → hidden."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {"X": _make_cls("X", "flag", 0.10)}
    tags = _pattern_tags(classifications, display_threshold=0.50)
    assert tags == {}


def test_pattern_tags_filters_classifier_error_rows():
    """Classifier-error rows have pattern=None; they don't render a tag."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {"X": _make_cls("X", None, None)}
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {}


def test_pattern_tags_filters_pattern_none_rows():
    """pattern='none' (evaluated negative) does NOT render a tag — only
    detected flags do."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {"X": _make_cls("X", "none", None)}
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {}


def test_pattern_tags_handles_None_classifications_arg():
    """Defensive: empty/None mapping returns {}. Build paths that have no
    pipeline_run_id pass None and must not raise."""
    from swing.web.view_models.dashboard import _pattern_tags
    assert _pattern_tags(None, display_threshold=0.0) == {}
    assert _pattern_tags({}, display_threshold=0.0) == {}


def test_pattern_tags_threshold_at_exact_value_renders():
    """Boundary: confidence == threshold passes the >= check (renders).
    Discriminating-test discipline: this distinguishes >= from >."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {"X": _make_cls("X", "flag", 0.50)}
    tags = _pattern_tags(classifications, display_threshold=0.50)
    assert tags == {"X": "flag (0.50)"}


def test_pattern_tags_format_uses_two_decimal_places():
    """Spec §3.5 format: 'flag (0.78)' — two decimals. This catches a
    regression where someone formats with %g or default float repr
    (which would render '0.7' for 0.7 or '0.78000000000000003' for an
    inexact float)."""
    from swing.web.view_models.dashboard import _pattern_tags
    classifications = {"X": _make_cls("X", "flag", 0.7)}
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {"X": "flag (0.70)"}
