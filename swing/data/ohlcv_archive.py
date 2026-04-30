"""Per-ticker incremental OHLCV archive.

Source-of-truth for archive-aware reads consumed by `swing.prices.PriceFetcher`,
`swing.pipeline.ohlcv.fetch_daily_bars`, and (via the latter) `swing.web.ohlcv_cache.OhlcvCache`.

Schema:
- `{cache_dir}/{TICKER}.parquet` — full retained history, indexed by date,
  with OHLCV columns. Sliced by callers as needed.
- `{cache_dir}/{TICKER}.meta.json` — sidecar metadata, currently
  `{"last_full_refresh_date": "YYYY-MM-DD"}`. Additive shape; future fields
  may join (e.g., last-incremental-fetch timestamp).

Coherence policy (per OHLCV archive consolidation plan locked decision §2.2):
1. New ticker (no archive on disk) → full-history fetch (start = end_date -
   `_calendar_window_for_trading_days(archive_history_days)`; the helper
   post-trims to last `archive_history_days` rows).
2. Weekly full-refresh: if (today - last_full_refresh_date).days >= 7 →
   full-history fetch.
3. Otherwise incremental: if latest_stored_bar < end_date → fetch
   (latest+1, end_date+1).
4. Else cache hit → return archive slice ≤ end_date with NO yfinance call.

Atomicity: all writes go to a `tempfile.NamedTemporaryFile`-style temp file
in the destination directory, then `os.replace` to the final path. Avoids
the cross-device-link gotcha (CLAUDE.md) and ensures readers never observe
partial writes.

yfinance gotchas (CLAUDE.md): all calls go through `yf.download` with
`threads=False` (NOT `yf.Ticker.history()`); MultiIndex columns are squeezed
defensively.
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def _archive_paths(cache_dir: Path, ticker: str) -> tuple[Path, Path]:
    return (cache_dir / f"{ticker}.parquet"), (cache_dir / f"{ticker}.meta.json")


def _read_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("corrupted meta %s: %s — treating as missing", meta_path, exc)
        return {}


def _write_meta_atomic(meta_path: Path, meta: dict) -> None:
    cache_dir = meta_path.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{meta_path.stem}.", suffix=".meta.json.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(json.dumps(meta))
        os.replace(tmp_path, meta_path)
    except Exception:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise


def _read_archive(parquet_path: Path) -> pd.DataFrame | None:
    if not parquet_path.exists():
        return None
    return pd.read_parquet(parquet_path)


def _write_archive_atomic(parquet_path: Path, df: pd.DataFrame) -> None:
    cache_dir = parquet_path.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{parquet_path.stem}.", suffix=".parquet.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path)
        os.replace(tmp_path, parquet_path)
    except Exception:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise


def _squeeze_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _calendar_window_for_trading_days(trading_days: int) -> int:
    """Convert trading-day retention to a calendar-day yfinance window.

    Codex R1 Critical 1 + R2 Critical 1 resolution: 1260 trading days is
    NOT 1260 calendar days (~3.45y) AND the old `n * 7 / 5 + 14` heuristic
    is too tight for a full 5-year retention target; multi-year holiday
    clustering eats more than a 14-day buffer. The locked
    retention is "5 years" (spec §2.5), so the conversion uses the actual
    market-calendar ratio: ~252 trading days per ~365.25 calendar days,
    plus a 30-day buffer for holiday clustering. For default 1260 trading
    days: ceil(1260 * 365.25 / 252) + 30 = 1857 calendar days (~5.08y).
    Caller truncates the returned DataFrame to last `trading_days` rows
    post-fetch so the archive doesn't bloat with the buffer days.
    """
    return int(math.ceil(trading_days * 365.25 / 252)) + 30


def _yf_download_window(ticker: str, *, start: date, end: date) -> pd.DataFrame:
    """Wrap yf.download with the project's gotcha-resistant kwargs.
    `start` is inclusive, `end` is exclusive in yfinance — we always pass
    `end + 1 day` to make the call site's `end_date` semantics inclusive.
    """
    df = yf.download(
        ticker,
        start=start,
        end=end + timedelta(days=1),
        progress=False,
        auto_adjust=False,
        actions=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = _squeeze_multiindex(df)
    keep_cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[keep_cols]
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _last_completed_session_today() -> date:
    """Return the most recent completed NYSE session as of now. Used as the
    'today' anchor for weekly-refresh and partial-bar-strip semantics.
    Imports lazily to avoid circular references at module load time."""
    from swing.evaluation.dates import last_completed_session
    return last_completed_session(datetime.now())


def read_or_fetch_archive(
    ticker: str,
    *,
    end_date: date,
    cache_dir: Path,
    archive_history_days: int,
) -> pd.DataFrame | None:
    """Read the per-ticker archive, refreshing from yfinance as needed,
    return rows ≤ end_date.

    Args:
        ticker: ticker symbol; used as the archive filename stem.
        end_date: caller's window end (inclusive); typically the most-recent
            completed NYSE session. Caller must NOT pass dates past
            today's last completed session — the helper does not validate.
        cache_dir: archive directory (typically `cfg.paths.prices_cache_dir`).
            Must already exist.
        archive_history_days: full-history fetch window (typically
            `cfg.archive.archive_history_days`).

    Returns:
        DataFrame indexed by date with OHLCV columns; rows ≤ end_date.
        None if yfinance returns empty (delisted / invalid ticker / no history).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    parquet_path, meta_path = _archive_paths(cache_dir, ticker)

    today = _last_completed_session_today()

    archive = _read_archive(parquet_path)
    meta = _read_meta(meta_path)

    last_full_refresh: date | None = None
    last_full_str = meta.get("last_full_refresh_date")
    if last_full_str:
        try:
            last_full_refresh = date.fromisoformat(last_full_str)
        except ValueError:
            last_full_refresh = None

    needs_full_refresh = (
        archive is None
        or archive.empty
        or last_full_refresh is None
        or (today - last_full_refresh).days >= 7
    )

    if needs_full_refresh:
        full_calendar_days = _calendar_window_for_trading_days(archive_history_days)
        full_start = end_date - timedelta(days=full_calendar_days)
        fetched = _yf_download_window(ticker, start=full_start, end=end_date)
        if fetched.empty:
            return None
        fetched = fetched.tail(archive_history_days)
        _write_archive_atomic(parquet_path, fetched)
        _write_meta_atomic(meta_path, {"last_full_refresh_date": today.isoformat()})
        return fetched.loc[fetched.index.date <= end_date]

    assert archive is not None
    latest_stored: date = archive.index.max().date()
    if latest_stored < end_date:
        gap_start = latest_stored + timedelta(days=1)
        gap = _yf_download_window(ticker, start=gap_start, end=end_date)
        if not gap.empty:
            combined = pd.concat([archive, gap])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            _write_archive_atomic(parquet_path, combined)
            archive = combined

    return archive.loc[archive.index.date <= end_date]
