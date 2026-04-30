"""Unit test for the rewritten `_CountingPriceFetcher` (research/parity/run.py).

Phase 3 removed `PriceFetcher._cache_path`. The wrapper now inspects
the per-ticker archive directory shape (`{TICKER}.parquet` +
`{TICKER}.meta.json` in `cfg.paths.prices_cache_dir`) to count hits
vs misses. A meta-stale archive counts as a MISS (the underlying
helper will re-fetch).

Discriminating: 3-ticker fixture exercising three states (fresh,
meta-stale, no-parquet); assertion on exact hits/misses count
distinguishes the new shape from any path-existence-only counter.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "prices_cache"
    cache_dir.mkdir()

    today = date.today()
    pd.DataFrame({"Close": [100.0]}, index=pd.to_datetime([today])).to_parquet(
        cache_dir / "AAPL.parquet",
    )
    (cache_dir / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": today.isoformat()}),
    )
    pd.DataFrame({"Close": [100.0]}, index=pd.to_datetime([today])).to_parquet(
        cache_dir / "MSFT.parquet",
    )
    (cache_dir / "MSFT.meta.json").write_text(
        json.dumps({
            "last_full_refresh_date": (today - timedelta(days=60)).isoformat(),
        }),
    )
    return cache_dir


class _StubInner:
    """Stub inner.get returning empty DataFrame; only the wrapper's
    counting behavior matters for these tests."""
    def get(self, ticker, lookback_days, *, as_of_date=None):
        return pd.DataFrame()


def test_counting_price_fetcher_distinguishes_fresh_stale_missing(archive_dir):
    """Wrapper counts: fresh AAPL = hit; meta-stale MSFT = miss;
    missing GOOG = miss."""
    from research.parity.run import _CountingPriceFetcher

    inner = _StubInner()
    wrapper = _CountingPriceFetcher(inner, prices_cache_dir=archive_dir)

    wrapper.get("AAPL", 60)
    wrapper.get("MSFT", 60)
    wrapper.get("GOOG", 60)

    assert wrapper.hits == 1, (
        f"Only AAPL has a fresh archive (hits=1 expected); got {wrapper.hits}. "
        "MSFT meta-stale counts as miss; GOOG no-parquet counts as miss."
    )
    assert wrapper.misses == 2, (
        f"MSFT (meta-stale) + GOOG (missing) = misses=2 expected; "
        f"got {wrapper.misses}"
    )


def test_counting_price_fetcher_constructor_requires_prices_cache_dir():
    """Smoke test for the constructor signature change. Catches the
    regression where the call site at research/parity/run.py:331 isn't
    updated when the constructor is changed (Codex R1 M2 anchor)."""
    from research.parity.run import _CountingPriceFetcher

    inner = _StubInner()
    with pytest.raises(TypeError):
        _CountingPriceFetcher(inner)  # missing required kwarg

    wrapper = _CountingPriceFetcher(inner, prices_cache_dir=Path("."))
    assert wrapper.prices_cache_dir == Path(".")
    assert wrapper.hits == 0
    assert wrapper.misses == 0


def test_run_parity_call_site_passes_prices_cache_dir_kwarg():
    """Smoke test for the runtime call site at research/parity/run.py:331-ish.
    Catches the regression where Task 7's constructor change isn't
    propagated to the real call site (the rewrite-without-call-site-
    update failure mode caught by Codex R1 M2).

    Static source-level check: the call site must pass
    `prices_cache_dir=...` kwarg when constructing _CountingPriceFetcher.
    Pre-Task-7 code instantiated the wrapper with a single positional
    arg only; post-Task-7 it passes the new kwarg.
    """
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "research" / "parity" / "run.py").read_text(encoding="utf-8")

    # Find every `_CountingPriceFetcher(` call site (excluding the
    # class definition itself); for each, scan forward through balanced
    # parentheses to extract the full argument list. Each call site
    # MUST contain the `prices_cache_dir=` kwarg.
    call_starts = [
        m.start() for m in re.finditer(r"_CountingPriceFetcher\(", text)
        if not text[max(0, m.start() - 6):m.start()].endswith("class ")
    ]
    assert call_starts, "Expected at least one _CountingPriceFetcher call site"
    for start in call_starts:
        open_paren = text.index("(", start)
        depth = 0
        end = open_paren
        for i in range(open_paren, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        args = text[open_paren + 1:end]
        assert "prices_cache_dir" in args, (
            f"_CountingPriceFetcher call site missing `prices_cache_dir` "
            f"kwarg at offset {start}: args={args!r}. The constructor "
            f"now requires this kwarg per the Phase 3 archive-shape rewrite."
        )
