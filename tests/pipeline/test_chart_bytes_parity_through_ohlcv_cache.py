"""Phase 13 T1.SB0 — chart-bytes parity discriminating test.

Plan §G.0 T-T1.SB0.4 acceptance (per spec §4.1 step 2):
"chart renderers accept the to_dataframe() shape; assert chart bytes match
a known-good fixture rendered from both paths".

Stronger end-to-end version of the T-T1.SB0.2 shape-parity test:
proves that rendering a chart from ``OhlcvCache.get_or_fetch``'s DataFrame
produces BYTE-IDENTICAL output to rendering from the legacy
``PriceFetcher.get`` DataFrame. The wiring did NOT change chart bytes —
only the data fetch path.

Discriminator: if ``OhlcvCache.get_or_fetch`` introduces ANY shape drift
(column order, index dtype, value scaling, in-progress-bar strip), the
rendered PNG bytes would diverge. Byte-identity is the strongest possible
invariant for the wiring.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from swing.config import load
from tests.cli.test_cli_eval import _minimal_config

# mplfinance is required for this gate to be honest. The plan's T-T1.SB0.4
# acceptance criterion ("chart bytes parity passes") is unconditional; a
# silent ImportError-skip would mask the assertion in barebones environments
# and the Codex R1 Major #3 flag (2026-05-18) caught the bypass. Import at
# module load — failure here surfaces as a clear collection error, not a
# silent skip. mplfinance is now part of the `dev` extra (Codex R2 Major #1
# fix 2026-05-18) so the documented `pip install -e ".[dev,web]"` profile
# at CLAUDE.md Quick Start satisfies this test's gate.
import mplfinance  # noqa: F401


def _make_cfg(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    return load(cfg_path)


def _fixture_bars(*, end: pd.Timestamp, n_rows: int = 240) -> pd.DataFrame:
    """Deterministic OHLCV fixture (capitalized columns + DatetimeIndex)."""
    idx = pd.bdate_range(end=end, periods=n_rows)
    closes = [100.0 + i * 0.05 for i in range(n_rows)]
    return pd.DataFrame(
        {
            "Open": [c - 0.05 for c in closes],
            "High": [c + 0.30 for c in closes],
            "Low": [c - 0.30 for c in closes],
            "Close": closes,
            "Volume": [1_000_000 + i for i in range(n_rows)],
        },
        index=idx,
    )


def test_chart_bytes_match_between_ohlcv_cache_and_legacy_price_fetcher(
    tmp_path: Path, monkeypatch,
):
    """T-T1.SB0.4 acceptance: chart bytes are identical between (a) chart
    rendered from ``OhlcvCache.get_or_fetch``'s DataFrame and (b) chart
    rendered from the legacy ``PriceFetcher.get``'s DataFrame for the same
    fixture archive.

    Wiring property: the data fetch path changed; the chart output did NOT.

    mplfinance imported at module level — silent skip on missing dep would
    mask the acceptance assertion (Codex R1 Major #3 fix 2026-05-18). The
    `[dev,web]` install profile per CLAUDE.md Quick Start includes the
    dependency.
    """
    from swing.prices import PriceFetcher
    from swing.rendering.charts import render_chart
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture = _fixture_bars(end=end)

    def _stub_read(ticker, *, end_date, cache_dir, archive_history_days):
        return fixture.loc[fixture.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", _stub_read)
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read,
    )
    monkeypatch.setattr(
        "swing.evaluation.dates.last_completed_session", _stub_session,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
    )

    # Fetch via both paths.
    cache = OhlcvCache(cfg=cfg)
    cache_df = cache.get_or_fetch(ticker="AAPL", window_days=200)

    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
    legacy_df = fetcher.get("AAPL", lookback_days=200, as_of_date=None)

    # Pre-condition: DataFrames must be structurally identical
    # (otherwise the bytes-parity test is meaningless).
    pd.testing.assert_frame_equal(cache_df, legacy_df, check_exact=False, rtol=1e-9)

    # Render both charts to separate paths.
    out_cache = tmp_path / "out_cache.png"
    out_legacy = tmp_path / "out_legacy.png"
    p1 = render_chart(
        ticker="AAPL", ohlcv=cache_df, pivot=110.0, stop=100.0,
        output_path=out_cache, pattern_overlay=None,
    )
    p2 = render_chart(
        ticker="AAPL", ohlcv=legacy_df, pivot=110.0, stop=100.0,
        output_path=out_legacy, pattern_overlay=None,
    )
    assert p1 is not None and p2 is not None, "render_chart must succeed for both"
    assert p1.exists() and p2.exists()

    bytes_cache = p1.read_bytes()
    bytes_legacy = p2.read_bytes()
    # Strongest possible invariant: byte-identical PNG output.
    assert bytes_cache == bytes_legacy, (
        f"chart bytes diverge — wiring changed chart output. "
        f"cache sha256={hashlib.sha256(bytes_cache).hexdigest()[:16]}, "
        f"legacy sha256={hashlib.sha256(bytes_legacy).hexdigest()[:16]}"
    )
