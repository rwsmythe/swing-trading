# tests/rendering/test_render_chart_stop_omission.py — new file

"""Stop-hline omission for None/0 stops. Spec §A.

Manual visual verification per Phase 6 + Tier-1 mathtext lessons:
string-equality on title is INSUFFICIENT for rendered output. After
implementing, manually `Read` a generated PNG to confirm the visual
is correct.
"""
from __future__ import annotations

import pandas as pd
import pytest

from swing.rendering.charts import render_chart


def _ohlcv(n: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0,
         "Volume": 1_000_000.0},
        index=idx,
    )


def test_render_chart_omits_stop_hline_when_stop_is_none(tmp_path, monkeypatch):
    """Stop=None → no stop hline drawn AND no `stop X.XX` segment in title.

    Discriminating verification: capture the generated figure's HLines
    via mplfinance's returnfig=True. Pre-fix: hline drawn at y=0 (or
    raises). Post-fix: no hline at the stop position.
    """
    out = tmp_path / "AAPL.png"
    captured: dict = {}

    def _capture_kwargs(df, **kwargs):
        # Capture the hlines kwarg passed to mpf.plot, then short-circuit
        # the actual render so the test doesn't depend on mpf rendering
        # to a file. Plan Step 3 keeps render_chart calling mpf.plot with
        # `hlines=dict(hlines=[...], colors=[...], linestyle="--")` —
        # the test asserts on the LIST inside that dict.
        captured["hlines"] = kwargs.get("hlines", {}).get("hlines", [])
        # Return a stub fig so render_chart's no-overlay branch doesn't
        # raise. (For overlay branch, mpf.plot returns (fig, axes) under
        # returnfig=True; this test uses pattern_overlay=None so the
        # savefig branch is taken — see swing/rendering/charts.py:108.)
        return None

    # Patch `mplfinance.plot` directly on the mplfinance module — NOT via
    # `swing.rendering.charts.mpf.plot` (mpf is imported function-locally
    # inside render_chart's try/except, so it's NOT a module-level
    # attribute of swing.rendering.charts and cannot be patched there).
    # Patching the upstream module is robust because `mpf.plot(...)`
    # resolves `plot` against the mplfinance module object at call time.
    # Codex R3 Major 2.
    import mplfinance
    monkeypatch.setattr(mplfinance, "plot", _capture_kwargs)
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=None,
        output_path=out, pattern_overlay=None,
    )
    assert captured.get("hlines") == [110.0], (
        f"expected hlines=[110.0] (pivot only) when stop=None; "
        f"got {captured.get('hlines')!r}; "
        "regression: render_chart still passes stop to mpf.plot"
    )


def test_render_chart_omits_stop_hline_when_stop_is_zero(tmp_path, monkeypatch):
    """Stop=0.0 → same omission behavior as None.

    Discriminating verification: pre-fix code passed `stop=0.0` directly to
    matplotlib hlines; mplfinance's auto-scale would expand y-axis to
    include 0 (compressing legitimate price action). Post-fix omits.
    """
    out = tmp_path / "AAPL.png"
    captured: dict = {}

    def _capture_kwargs(df, **kwargs):
        captured["hlines"] = kwargs.get("hlines", {}).get("hlines", [])
        return None

    # Patch `mplfinance.plot` directly on the mplfinance module — NOT via
    # `swing.rendering.charts.mpf.plot` (mpf is imported function-locally
    # inside render_chart's try/except, so it's NOT a module-level
    # attribute of swing.rendering.charts and cannot be patched there).
    # Patching the upstream module is robust because `mpf.plot(...)`
    # resolves `plot` against the mplfinance module object at call time.
    # Codex R3 Major 2.
    import mplfinance
    monkeypatch.setattr(mplfinance, "plot", _capture_kwargs)
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=0.0,
        output_path=out, pattern_overlay=None,
    )
    assert captured.get("hlines") == [110.0], (
        f"expected hlines=[110.0] (pivot only) when stop=0.0; "
        f"got {captured.get('hlines')!r}; "
        "regression: render_chart still passes stop=0.0 to mpf.plot"
    )


def test_render_chart_title_omits_stop_segment_when_stop_is_zero(tmp_path):
    """When stop is None or 0, title must NOT contain `stop X.XX`.

    Discriminating verification: pre-fix the title format was something
    like `AAPL  pivot 110.00  stop 0.00`; post-fix becomes
    `AAPL  pivot 110.00`. Substring exclusion catches the regression.

    Note: per CLAUDE.md mathtext gotcha, the title format MUST also NOT
    introduce a `$` metacharacter. The post-fix format omits the `stop`
    segment entirely; reviewer must confirm no leading `$` is added in
    its place.

    Title-extraction pattern (Phase 6 lesson): mpf renders title via
    `fig.suptitle`, NOT `price_ax.set_title`. Rather than capture mpf's
    title kwarg through monkeypatch (which is brittle), this test calls
    the new pure helper `_build_chart_title` directly — single source of
    truth for the title's pivot/stop segment. The full rendered title
    appended at the call site (`| last N bars`) is verified separately
    by manual visual verification (Step 5).
    """
    from swing.rendering.charts import _build_chart_title  # NEW helper
    title_stop_zero = _build_chart_title(ticker="AAPL", pivot=110.0, stop=0.0)
    title_stop_none = _build_chart_title(ticker="AAPL", pivot=110.0, stop=None)
    title_stop_positive = _build_chart_title(ticker="AAPL", pivot=110.0, stop=95.0)
    assert "stop" not in title_stop_zero.lower(), (
        f"title still contains 'stop' segment when stop=0.0: {title_stop_zero!r}"
    )
    assert "stop" not in title_stop_none.lower(), (
        f"title still contains 'stop' segment when stop=None: {title_stop_none!r}"
    )
    assert "stop 95" in title_stop_positive.lower(), (
        f"verified-empirically pin failed: positive stop omits 'stop 95.00': {title_stop_positive!r}"
    )
    for t in (title_stop_zero, title_stop_none, title_stop_positive):
        # CLAUDE.md mathtext gotcha — no metacharacters in the title.
        assert "$" not in t and "^" not in t and "_" not in t, (
            f"title contains mathtext metacharacter: {t!r}"
        )


def test_render_chart_passes_built_title_to_mpf_plot(tmp_path, monkeypatch):
    """Wiring pin: render_chart's `title=` kwarg to mpf.plot must START with
    the value produced by _build_chart_title (the call site appends the
    `| last N bars` suffix).

    Codex R4 Major 1: without this test, a regression where `_build_chart_title`
    is correct but `render_chart` reverts to the old f-string `f"{ticker} |
    pivot {pivot:.2f} stop {stop:.2f} | last ..."` would pass ALL hline-count
    tests AND the helper-direct title test, only failing at manual visual
    verification. Verifying render_chart's actual title kwarg pins the
    helper-to-render wiring.

    Discriminating verification: with stop=0.0, the captured title prefix is
    `_build_chart_title(ticker="AAPL", pivot=110.0, stop=0.0)`. A regression
    that drops the helper call AND keeps the old f-string would emit a title
    containing "stop 0.00" — the assertion `"stop" not in captured_title`
    fails. **Verified-empirically pin** (also asserted in same test): with
    stop=95.0, the captured title prefix DOES include "stop 95.00", proving
    the helper-driven path correctly emits the segment when stop is positive.
    """
    from swing.rendering.charts import _build_chart_title

    captured: dict = {}

    def _capture_kwargs(df, **kwargs):
        captured["title"] = kwargs.get("title", "")
        return None

    import mplfinance
    monkeypatch.setattr(mplfinance, "plot", _capture_kwargs)
    out = tmp_path / "AAPL.png"

    # stop=0.0 — title must NOT contain 'stop' substring AND must start with
    # the helper's output for these args.
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=0.0,
        output_path=out, pattern_overlay=None,
    )
    title_zero = captured["title"]
    expected_prefix_zero = _build_chart_title(
        ticker="AAPL", pivot=110.0, stop=0.0,
    )
    assert title_zero.startswith(expected_prefix_zero), (
        f"render_chart title does not start with helper output; "
        f"got {title_zero!r}; expected prefix {expected_prefix_zero!r}; "
        "regression: render_chart constructs title without _build_chart_title"
    )
    assert "stop" not in title_zero.lower(), (
        f"render_chart title still contains 'stop' segment when stop=0.0: "
        f"{title_zero!r}"
    )

    # Verified-empirically: stop=95.0 — title MUST contain 'stop 95.00'
    # (proves the helper-driven path is correct, not just emitting empty).
    captured.clear()
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    title_pos = captured["title"]
    assert "stop 95.00" in title_pos, (
        f"render_chart title MISSING 'stop 95.00' segment when stop>0; "
        f"got {title_pos!r}; "
        "regression: helper-driven path emits empty stop segment even when stop>0"
    )


def test_render_chart_renders_stop_hline_when_stop_is_positive(tmp_path, monkeypatch):
    """Verified-empirically pin: positive stop renders the hline as before.

    Discriminating verification: catches a regression that omits the hline
    even when stop > 0. With stop=95.0, hlines=[110.0, 95.0] (pivot+stop).
    """
    out = tmp_path / "AAPL.png"
    captured: dict = {}

    def _capture_kwargs(df, **kwargs):
        captured["hlines"] = kwargs.get("hlines", {}).get("hlines", [])
        return None

    # Patch `mplfinance.plot` directly on the mplfinance module — NOT via
    # `swing.rendering.charts.mpf.plot` (mpf is imported function-locally
    # inside render_chart's try/except, so it's NOT a module-level
    # attribute of swing.rendering.charts and cannot be patched there).
    # Patching the upstream module is robust because `mpf.plot(...)`
    # resolves `plot` against the mplfinance module object at call time.
    # Codex R3 Major 2.
    import mplfinance
    monkeypatch.setattr(mplfinance, "plot", _capture_kwargs)
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    assert captured.get("hlines") == [110.0, 95.0], (
        f"expected hlines=[110.0, 95.0] (pivot + stop) when stop>0; "
        f"got {captured.get('hlines')!r}; "
        "regression: render_chart drops the stop hline even when stop is positive"
    )
