"""OHLCV + earnings fetchers with disk caching for the replay harness.

Scope
-----
US-equities only. The coverage predicate :func:`_covers` clamps to the
NYSE calendar (``XNYS``) — passing tickers with a non-NYSE-aligned
trading calendar (LSE, TSX, etc.) would produce wrong coverage decisions.
The harness's broader research scope (RS universe = SPX + NDX) makes
this assumption load-bearing rather than incidental.

Caching strategy
----------------
- **OHLCV** — per-ticker Parquet file under ``<cache_dir>/ohlcv/<TICKER>.parquet``.
  Historical daily bars are immutable, so cache entries don't expire. If the
  requested ``(start, end)`` window is fully contained in the cached frame,
  the cache is returned directly. Otherwise yfinance is called for the
  full requested range and the result is union-merged back into the cache.

- **Earnings** — per-ticker JSON file under ``<cache_dir>/earnings/<TICKER>.json``
  with ``fetched_ts``. Stale if ``now - fetched_ts > cache_max_age_hours``.
  Empty list (``[]``) is a VALID result — the method record mandates
  absent-data → do NOT exclude, flag for review.

Both loaders also report per-ticker cache outcomes (``hit`` vs ``miss``) so
the run-manifest cache_stats reflect actual fetcher behavior rather than
naive file-existence counts.

yfinance gotchas (CLAUDE.md)
----------------------------
- ``threads=False`` ONLY on :func:`yf.download`. Never pass ``threads=`` to
  ``Ticker`` methods (``TypeError`` on yfinance >= 1.2).
- ``yf.download(group_by="ticker")`` on a single ticker can still return a
  MultiIndex column frame. Squeeze defensively before extracting per-ticker
  slices.
- Errors are NOT silenced. If yfinance raises, the caller sees it — no
  log-and-return-None which would mask real breakage.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf

_OHLCV_COLS = ("Open", "High", "Low", "Close", "Volume")
# Subset for the pre-IPO-NaN-row drop: bars without OHLC are not real
# trading days. Volume can legitimately be NaN on certain holidays / halts
# while OHLC are present, so it is excluded from this subset.
_OHLC_ONLY_COLS = ("Open", "High", "Low", "Close")

# Calendar used for the "most recent NYSE session at-or-before today" clamp
# in :func:`_covers`. Cached at module load — exchange_calendars handles
# this internally too, but the explicit reference makes the dependency
# obvious.
_NYSE = xcals.get_calendar("XNYS")


def _drop_ohlc_nan_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where any of Open/High/Low/Close is NaN.

    Volume is excluded from the subset — it can legitimately be NaN on
    holiday/halt bars where OHLC are present. Applied at consumer-return
    time (in :func:`load_ohlcv_with_stats`'s final dict comprehension),
    NOT at cache-write time. Cleaning at cache-write would shift
    ``idx_min`` for mid-window-IPO tickers (the cache loses its leading
    NaN-padded rows), and :func:`_covers` would then report "partial
    coverage" on every subsequent run — an infinite refetch loop.
    Cleaning at return time keeps the cache aligned with yfinance's raw
    output (idx_min == window start) so :func:`_covers` returns True on
    warm runs, while consumers never see the NaN rows that crash
    downstream code (e.g.,
    ``swing.evaluation.criteria.risk_feasibility``).
    """
    if df is None or df.empty:
        return df
    ohlc_present = [c for c in _OHLC_ONLY_COLS if c in df.columns]
    if not ohlc_present:
        return df
    return df.dropna(subset=ohlc_present)


@dataclass(frozen=True)
class FetchStats:
    """Per-ticker fetcher outcomes for one load_* call.

    A ticker counts as a HIT iff its on-disk cache fully covered the request
    AND no yfinance call was made for it. Any cache-miss, partial-coverage
    refetch, or stale-earnings refetch counts as a MISS.
    """

    hits: tuple[str, ...] = field(default_factory=tuple)
    misses: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hit_count(self) -> int:
        return len(self.hits)

    @property
    def miss_count(self) -> int:
        return len(self.misses)


def _ohlcv_cache_file(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / "ohlcv" / f"{ticker}.parquet"


def _earnings_cache_file(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / "earnings" / f"{ticker}.json"


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Return a flat-columns OHLCV DataFrame for ``ticker`` from a yf.download result.

    Handles three cases observed in yfinance >= 1.2:
      - Multi-ticker MultiIndex (level 0 = Ticker, level 1 = Price) when
        ``group_by="ticker"``.
      - Single-ticker MultiIndex (same structure, still one ticker) — the
        CLAUDE.md regression case.
      - Flat columns (legacy / single-ticker older yfinance).
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=list(_OHLCV_COLS))

    if isinstance(raw.columns, pd.MultiIndex):
        top_level = raw.columns.get_level_values(0)
        if ticker in set(top_level):
            df_t = raw[ticker].copy()
        else:
            # group_by="column" would put Price on level 0 instead.
            price_level = raw.columns.get_level_values(0)
            if any(p in set(price_level) for p in _OHLCV_COLS):
                # Level 0 is Price; level 1 is Ticker. Swap and slice.
                swapped = raw.swaplevel(axis=1)
                if ticker in set(swapped.columns.get_level_values(0)):
                    df_t = swapped[ticker].copy()
                else:
                    return pd.DataFrame(columns=list(_OHLCV_COLS))
            else:
                return pd.DataFrame(columns=list(_OHLCV_COLS))
    else:
        df_t = raw.copy()

    # Keep only the OHLCV columns that are present. The pre-IPO NaN
    # row strip happens at consumer-return time in
    # :func:`load_ohlcv_with_stats`, NOT here, so the on-disk cache stays
    # aligned with yfinance's raw output (preventing infinite refetch
    # loops on mid-window-IPO tickers — see :func:`_drop_ohlc_nan_rows`).
    keep = [c for c in _OHLCV_COLS if c in df_t.columns]
    df_t = df_t[keep]
    return df_t


def _today() -> date:
    """Return today's local date.

    Indirected through this helper so tests can substitute a fixed date
    via ``monkeypatch.setattr(fetchers, "_today", lambda: ...)`` without
    monkeypatching the stdlib.
    """
    return date.today()


def _most_recent_nyse_session_at_or_before(d: date) -> date:
    """Return the most recent NYSE session date at-or-before ``d``.

    Resolves weekends and exchange holidays so the coverage predicate
    doesn't ask for a bar yfinance cannot supply (Sunday, July 4, etc.).
    Falls back to ``d`` if no session is found in a 14-day lookback,
    which only happens in pathological clock skew — a legitimate cache
    that doesn't cover ``d`` will then be reported as missing, the
    conservative outcome.
    """
    ts = pd.Timestamp(d)
    sessions = _NYSE.sessions_in_range(ts - pd.Timedelta(days=14), ts)
    if len(sessions) == 0:
        return d
    return sessions[-1].date()


def _covers(cached: pd.DataFrame, start: date, end: date) -> bool:
    """True iff the cached frame covers the requested window [start, end).

    Two refinements beyond the literal ``end - 1 day`` check:

    1. **Future-end clamp.** yfinance cannot return bars past today, so a
       request with ``end`` past today is satisfied as soon as the cache
       covers today's most recent session. ``run.py`` requests ~30
       trading sessions of forward buffer past the replay window for the
       simulator's time cap; pre-fix, every full run wasted ~7 minutes
       refetching data yfinance could not supply (Session 2c Open
       Issue #3).
    2. **Session-aware clamp.** The required last bar is then mapped to
       the most recent NYSE session at-or-before that calendar day, so
       weekends and exchange holidays don't trip the predicate. Without
       this, a Monday-pre-market run with a Friday-close cache would
       report "not covered" because Sunday is not a session and so the
       cache's Friday bar fails the literal ``end - 1 day = Sunday``
       comparison.

    Trade-off (accepted, not fixed)
    -------------------------------
    For ``end > today``, the implementation requires the cache to cover
    up through the most recent session at-or-before ``today - 1 day`` —
    i.e., yesterday's session, not today's. A stricter predicate would
    require today's session and refetch on every run between market
    close and the next morning's run, BUT during market hours yfinance
    has only an in-progress today bar (or none yet), so the strict
    predicate would either (a) trigger a wasted refetch every call, or
    (b) cache today's partial bar and serve stale data thereafter. The
    research-replay use case (windows ending weeks-to-months in the
    past) is insensitive to a one-session lag at the rightmost edge of
    the cache; the wasted-refetch failure mode this predicate was built
    to fix (Session 2c Open Issue #3) was the explicit prior cost. If a
    future use case becomes lag-sensitive, revisit with a market-hours-
    aware clamp rather than restoring the strict-but-wasteful semantics.
    """
    if cached.empty:
        return False
    idx_min = cached.index.min()
    idx_max = cached.index.max()
    start_ts = pd.Timestamp(start)
    # yf.download uses an end-exclusive contract; the last bar we need is
    # strictly before ``end``.
    effective_end = min(end, _today())
    end_calendar_day = effective_end - timedelta(days=1)
    end_inclusive_session = _most_recent_nyse_session_at_or_before(end_calendar_day)
    end_inclusive_ts = pd.Timestamp(end_inclusive_session)
    return idx_min <= start_ts and idx_max >= end_inclusive_ts


def _slice_window(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Return rows with index in [start, end). End is exclusive per yfinance."""
    if df.empty:
        return df
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    mask = (df.index >= start_ts) & (df.index < end_ts)
    return df.loc[mask]


def load_ohlcv(
    tickers: Iterable[str],
    *,
    start: date,
    end: date,
    cache_dir: Path,
    stats: FetchStats | None = None,  # noqa: ARG001 — kept for forward signature compat
) -> dict[str, pd.DataFrame]:
    """Load OHLCV daily bars for ``tickers`` spanning ``[start, end)``.

    See :func:`load_ohlcv_with_stats` for the variant that also returns a
    :class:`FetchStats`. This thin wrapper preserves the historical
    ``dict[str, DataFrame]``-only return shape for callers that don't need
    cache telemetry.
    """
    data, _ = load_ohlcv_with_stats(tickers, start=start, end=end, cache_dir=cache_dir)
    return data


def load_ohlcv_with_stats(
    tickers: Iterable[str],
    *,
    start: date,
    end: date,
    cache_dir: Path,
) -> tuple[dict[str, pd.DataFrame], FetchStats]:
    """Same as :func:`load_ohlcv` but also returns per-ticker cache outcomes.

    A ticker is a HIT iff its parquet existed and fully covered the requested
    window. Anything that triggered a yf.download call (missing file, partial
    coverage, or empty cached frame) is a MISS.
    """
    tickers = [t.upper() for t in tickers]
    cache_dir = Path(cache_dir)
    (cache_dir / "ohlcv").mkdir(parents=True, exist_ok=True)

    cached: dict[str, pd.DataFrame] = {}
    needs_fetch: list[str] = []
    hits: list[str] = []
    for t in tickers:
        path = _ohlcv_cache_file(cache_dir, t)
        if path.exists():
            df = pd.read_parquet(path)
            cached[t] = df
            if _covers(df, start, end):
                hits.append(t)
            else:
                needs_fetch.append(t)
        else:
            needs_fetch.append(t)

    if needs_fetch:
        raw = yf.download(
            tickers=needs_fetch,
            start=start,
            end=end,
            threads=False,  # CLAUDE.md gotcha
            group_by="ticker",
            auto_adjust=False,
            progress=False,
        )
        for t in needs_fetch:
            fresh = _extract_ticker_frame(raw, t)
            if fresh.empty:
                # Leave cache as-is; upstream will see an empty frame and skip.
                cached[t] = cached.get(t, fresh)
                continue
            # Union-merge cached + fresh, keep fresh values on overlap.
            if t in cached and not cached[t].empty:
                merged = pd.concat([cached[t], fresh])
                merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            else:
                merged = fresh.sort_index()
            merged.to_parquet(_ohlcv_cache_file(cache_dir, t))
            cached[t] = merged

    # Drop pre-IPO NaN rows at consumer-return time so warm caches from
    # before the C3/C5 fix (Session 2c artifacts) are remediated without
    # touching the on-disk parquet — see :func:`_drop_ohlc_nan_rows`.
    data = {
        t: _drop_ohlc_nan_rows(
            _slice_window(
                cached.get(t, pd.DataFrame(columns=list(_OHLCV_COLS))),
                start,
                end,
            )
        )
        for t in tickers
    }
    stats = FetchStats(hits=tuple(hits), misses=tuple(needs_fetch))
    return data, stats


def _cache_fresh(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    fetched_raw = payload.get("fetched_ts")
    if not fetched_raw:
        return False
    try:
        fetched = datetime.fromisoformat(fetched_raw)
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    age = datetime.now(UTC) - fetched
    return age.total_seconds() < max_age_hours * 3600


def _load_earnings_cache(path: Path) -> list[date]:
    payload = json.loads(path.read_text())
    return [date.fromisoformat(s) for s in payload.get("earnings_dates", [])]


def _extract_earnings_dates(raw: pd.DataFrame | None) -> list[date]:
    """Extract sorted ET-date list from a yfinance earnings DataFrame.

    yfinance returns tz-aware timestamps (America/New_York). Take ``.date()``
    in ET to avoid UTC-rollover on late-day AMC releases.
    """
    if raw is None or getattr(raw, "empty", True):
        return []
    ny = "America/New_York"
    out: set[date] = set()
    for ts in raw.index:
        if not isinstance(ts, pd.Timestamp):
            continue
        # yfinance earnings timestamps are tz-aware ET in practice; tz-naive
        # fallback assumes ET (would otherwise roll AMC releases to UTC date).
        ts_ny = ts.tz_localize(ny) if ts.tz is None else ts.tz_convert(ny)
        out.add(ts_ny.date())
    return sorted(out)


def load_earnings(
    tickers: Iterable[str],
    *,
    cache_dir: Path,
    cache_max_age_hours: int = 24,
) -> dict[str, list[date]]:
    """Load next-earnings-date lists for ``tickers`` with disk caching.

    See :func:`load_earnings_with_stats` for the variant that also reports
    per-ticker cache outcomes. Returns a dict mapping ticker → list[date]
    sorted ascending. Empty list is a valid absent-data result (per method
    record rule: do NOT exclude, flag for review).
    """
    data, _ = load_earnings_with_stats(
        tickers, cache_dir=cache_dir, cache_max_age_hours=cache_max_age_hours
    )
    return data


def load_earnings_with_stats(
    tickers: Iterable[str],
    *,
    cache_dir: Path,
    cache_max_age_hours: int = 24,
) -> tuple[dict[str, list[date]], FetchStats]:
    """Same as :func:`load_earnings` but also returns per-ticker cache outcomes.

    A ticker is a HIT iff its JSON cache existed AND was fresh (within
    ``cache_max_age_hours`` of ``now``). Anything that triggered a refetch
    (missing file, malformed JSON, stale ``fetched_ts``) is a MISS.
    """
    tickers = [t.upper() for t in tickers]
    cache_dir = Path(cache_dir)
    (cache_dir / "earnings").mkdir(parents=True, exist_ok=True)

    out: dict[str, list[date]] = {}
    hits: list[str] = []
    misses: list[str] = []
    for t in tickers:
        path = _earnings_cache_file(cache_dir, t)
        if _cache_fresh(path, cache_max_age_hours):
            out[t] = _load_earnings_cache(path)
            hits.append(t)
            continue
        raw = yf.Ticker(t).get_earnings_dates(limit=30)
        dates = _extract_earnings_dates(raw)
        payload = {
            "ticker": t,
            "fetched_ts": datetime.now(UTC).isoformat(),
            "earnings_dates": [d.isoformat() for d in dates],
        }
        path.write_text(json.dumps(payload, indent=2))
        out[t] = dates
        misses.append(t)

    return out, FetchStats(hits=tuple(hits), misses=tuple(misses))
