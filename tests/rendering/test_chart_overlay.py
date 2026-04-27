"""Phase 3 Task 3.1: render_chart accepts pattern_overlay kwarg (no-op stub).

Phase 6 will paint the pole/flag region from a non-None overlay; Phase 3
just opens the kwarg gate so the pipeline runner can pass overlays through
without painting.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from swing.rendering.charts import PatternOverlay, render_chart


@pytest.fixture
def fake_ohlcv() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=120, freq="B")
    return pd.DataFrame({
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0,
        "Volume": 1_000_000.0,
    }, index=idx)


def test_render_chart_pattern_overlay_default_is_none_and_writes_png(
    tmp_path: Path, fake_ohlcv,
):
    """Backward-compat: render_chart(...) without pattern_overlay must
    behave as before — accept the call, produce the PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out,
    )
    assert res == out
    assert out.exists()


def test_render_chart_accepts_pattern_overlay_none_kwarg(
    tmp_path: Path, fake_ohlcv,
):
    """The kwarg is OPTIONAL and defaults to None; passing None explicitly
    must produce the same PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    assert res == out


def test_render_chart_pattern_overlay_none_is_byte_identical_to_default(
    tmp_path: Path, fake_ohlcv,
):
    """Phase 3 contract: `pattern_overlay=None` MUST produce a chart byte-
    identical to the legacy call without the kwarg. Phase 6 lands the actual
    painting; until then the kwarg is a no-op stub.

    Discriminating: if Phase 6 painting accidentally landed early (or the
    `del pattern_overlay` line was removed), this test would diverge.
    """
    default_path = tmp_path / "default.png"
    explicit_path = tmp_path / "explicit_none.png"

    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=default_path,
    )
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=explicit_path, pattern_overlay=None,
    )

    assert default_path.read_bytes() == explicit_path.read_bytes(), (
        "render_chart with pattern_overlay=None must produce a byte-identical "
        "PNG to the default kwarg-omitted call (Phase 3 no-op stub contract)"
    )


def test_render_chart_real_pattern_overlay_is_byte_identical_to_default(
    tmp_path: Path, fake_ohlcv,
):
    """Phase 3 contract (Codex R2 Major 2): the no-op stub MUST hold even
    when pattern_overlay is a fully-populated PatternOverlay. _step_charts
    passes a non-None overlay whenever classify_flag detects a flag — Phase
    3 must produce identical PNGs in BOTH the None and the non-None case.

    A premature Phase 6 painting that fires only on non-None overlays would
    pass `pattern_overlay=None` byte-identity tests but break this test.
    Phase 6 lands the actual painting; this test is expected to be updated
    or removed when that lands.
    """
    overlay = PatternOverlay(
        pattern="flag", confidence=0.85,
        pole_start_date=date(2026, 1, 5),
        pole_end_date=date(2026, 1, 19),
        flag_start_date=date(2026, 1, 20),
        flag_end_date=date(2026, 1, 29),
        pivot=110.5,
    )
    default_path = tmp_path / "default.png"
    overlay_path = tmp_path / "with_overlay.png"

    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=default_path,
    )
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=overlay_path, pattern_overlay=overlay,
    )

    assert default_path.read_bytes() == overlay_path.read_bytes(), (
        "render_chart with a non-None PatternOverlay must produce a byte-"
        "identical PNG to the default call in Phase 3 (no-op stub). If this "
        "test fails, Phase 6 painting may have leaked into Phase 3."
    )
