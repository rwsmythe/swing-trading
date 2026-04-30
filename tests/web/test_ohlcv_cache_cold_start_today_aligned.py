"""True zero-yfinance cold-start test with today-aligned archive.

Complements `test_ohlcv_cache_cold_start_hydrates_from_disk_archive` in
`test_ohlcv_cache.py` — that test mocks `yf.download` (a safety guard,
not a contract assertion). This test installs a tracking MagicMock for
the entire `yfinance` module attached to the archive helper and asserts
zero method invocations / attribute access — discriminating against a
regression that switches from `yf.download` to `yf.Ticker(t).history()`
or any other yfinance entry point.

Critical design: archive's `last_full_refresh_date` AND in-memory
"today" are pinned to the SAME date as the archive's last bar, so the
helper's weekly-refresh and incremental-gap branches both no-op.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from swing.config import Config


@pytest.fixture
def cfg(test_cfg) -> Config:
    c, _ = test_cfg
    return c


def test_ohlcv_cache_cold_start_today_aligned_archive_makes_zero_yfinance_calls(
    cfg, monkeypatch,
):
    """Cold start with archive aligned to TODAY (no gap to fetch) must
    make zero yfinance calls — discriminating against any regression
    that introduces an unconditional yfinance ping or switches API entrypoint.
    """
    from swing.data import ohlcv_archive as archive_mod
    from swing.pipeline import ohlcv as ohlcv_mod
    from swing.web.ohlcv_cache import OhlcvCache

    cache_dir = cfg.paths.prices_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    pinned_today = date(2026, 4, 28)
    # Archive's last bar IS pinned_today, so latest_stored == today, so the
    # incremental-gap fetch branch (yf.download(start=today+1, end=today)) is
    # SKIPPED entirely. Combined with weekly-refresh fresh meta, the helper
    # makes ZERO yfinance calls.
    archive_dates = [pinned_today - timedelta(days=i) for i in range(59, -1, -1)]
    archive_df = pd.DataFrame(
        {
            "Open": [100.0]*60, "High": [100.0]*60, "Low": [100.0]*60,
            "Close": [100.0 + i for i in range(60)],
            "Volume": [1000]*60,
        },
        index=pd.to_datetime(archive_dates),
    )
    archive_df.to_parquet(cache_dir / "AAPL.parquet")
    (cache_dir / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": pinned_today.isoformat()}),
    )

    # Pin today to the SAME date the archive ends on. This makes the
    # helper's `today - last_stored == 0 days` so the incremental-fetch
    # branch is a no-op; weekly-refresh stays fresh.
    monkeypatch.setattr(
        archive_mod, "_last_completed_session_today",
        lambda: pinned_today,
    )

    # Replace the entire yfinance module attached to the archive helper
    # with a tracking MagicMock. spec_set=[] forbids ANY attribute
    # access — if the helper makes ANY yfinance call, AttributeError
    # surfaces immediately.
    mock_yf = MagicMock(spec_set=[])
    monkeypatch.setattr(archive_mod, "yf", mock_yf)

    helper_calls: list[str] = []
    real_helper = archive_mod.read_or_fetch_archive

    def counting_helper(ticker, *, end_date, cache_dir, archive_history_days):
        helper_calls.append(ticker)
        return real_helper(
            ticker, end_date=end_date, cache_dir=cache_dir,
            archive_history_days=archive_history_days,
        )

    monkeypatch.setattr(ohlcv_mod, "read_or_fetch_archive", counting_helper)

    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        bundles = cache.get_many_bundles(
            ["AAPL"], deadline_seconds=5.0, executor=ex,
        )

    assert "AAPL" in bundles
    bundle = bundles["AAPL"]
    # Bundle reflects the archive content (cold-start did hydrate).
    assert bundle.previous_close in (158.0, 159.0), (
        f"cold-start did not hydrate from disk archive; "
        f"got previous_close={bundle.previous_close}"
    )
    # Discriminator: helper ran exactly once for AAPL.
    assert helper_calls == ["AAPL"], (
        f"expected helper called exactly once for AAPL; got {helper_calls}"
    )
    # Discriminator: zero attribute access on the yfinance module mock.
    # `mock_yf.mock_calls` records ALL access (`mock_yf.something`,
    # `mock_yf.something()`, `mock_yf.something(args)`).
    assert mock_yf.mock_calls == [], (
        f"yfinance was accessed during cold-start; "
        f"calls={mock_yf.mock_calls}. With a today-aligned archive, "
        f"the cold-start path must make ZERO yfinance calls."
    )
