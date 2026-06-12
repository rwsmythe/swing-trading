"""Phase 16 / Arc 3 (3c) — content-derived ``chart_renders.source_data_hash``.

The prior write sites stamped a STATIC literal (``"step_charts_v1"`` /
``"chart_jit_v1"``) which does not encode the underlying data, so the audit
field never changes when the chart's bar history grows or its window shifts.
``compute_chart_source_hash`` keys the value on (bar count + first/last
asof_date) so data growth yields a different hash.
"""
from __future__ import annotations

import pandas as pd

from swing.web.charts import compute_chart_source_hash


def _frame(end: str, n: int) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes],
            "Close": closes,
            "Volume": [1000 + i for i in range(n)],
        },
        index=idx,
    )


def test_identical_frames_produce_identical_hash():
    a = _frame("2026-06-08", 120)
    b = _frame("2026-06-08", 120)
    assert compute_chart_source_hash(a) == compute_chart_source_hash(b)


def test_data_growth_changes_hash():
    """The XMAX symptom substrate: a sparse frame and a rich frame for the
    same ticker MUST hash differently so the cached row is not silently
    treated as unchanged."""
    sparse = _frame("2026-06-08", 16)
    rich = _frame("2026-06-08", 207)
    assert compute_chart_source_hash(sparse) != compute_chart_source_hash(rich)


def test_window_shift_changes_hash():
    """Same bar count, later last session → different hash."""
    earlier = _frame("2026-06-01", 120)
    later = _frame("2026-06-08", 120)
    assert compute_chart_source_hash(earlier) != compute_chart_source_hash(later)


def test_empty_frame_is_stable_and_distinct():
    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    assert compute_chart_source_hash(empty) == compute_chart_source_hash(empty)
    assert compute_chart_source_hash(empty) != compute_chart_source_hash(
        _frame("2026-06-08", 1)
    )


def test_hash_is_not_the_old_static_literal():
    h = compute_chart_source_hash(_frame("2026-06-08", 207))
    assert h not in ("step_charts_v1", "chart_jit_v1")
