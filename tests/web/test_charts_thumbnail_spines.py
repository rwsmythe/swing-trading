"""F-4: the shared thumbnail renderer hides matplotlib axes spines (no black
box around the hyp-rec / watchlist thumbnails). Asserts the spines are set
invisible by intercepting Spine.set_visible on both sub-axes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing.web.charts import render_watchlist_thumbnail_svg


def _frame(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = np.linspace(10.0, 20.0, n)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": np.full(n, 1000.0)},
        index=idx,
    )


def test_thumbnail_renders_without_spines(monkeypatch):
    # Capture spine visibility by intercepting the spine.set_visible calls.
    import matplotlib.spines
    visibilities: list[bool] = []
    orig = matplotlib.spines.Spine.set_visible

    def _track(self, b):
        visibilities.append(b)
        return orig(self, b)

    monkeypatch.setattr(matplotlib.spines.Spine, "set_visible", _track)
    out = render_watchlist_thumbnail_svg(
        ticker="AAPL", bars=_frame(), ma_lines=[10, 20],
    )
    assert isinstance(out, bytes) and len(out) > 0
    # Both sub-axes (price + vol) have 4 spines each = 8 set_visible(False).
    assert visibilities.count(False) >= 8
