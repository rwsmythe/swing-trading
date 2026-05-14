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
1. New ticker (no archive on disk) → full-history fetch (start = today -
   `_calendar_window_for_trading_days(archive_history_days)`; end = today
   (`_last_completed_session_today`); the helper post-trims to last
   `archive_history_days` rows).
2. Weekly full-refresh: if (today - last_full_refresh_date).days >= 7 →
   full-history fetch.
3. Otherwise incremental: if latest_stored_bar < today → fetch
   (latest+1, today). Caller's end_date controls the return slice ONLY,
   never the fetch upper bound — so historical callers never truncate the
   archive.
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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# Shape A persistence (Schwab API Sub-bundle C T-C.2 / plan §A.8 + §H.6.3):
# parquet-per-(ticker, provider). LOWER integer = HIGHER priority under
# `min()`-by-precedence selection in `resolve_ohlcv_window`. Mirrors the
# Phase 9 Sub-bundle C `_SOURCE_PRECEDENCE` pattern at
# `swing/data/repos/account_equity_snapshots.py` (schwab_api > yfinance).
_SOURCE_PRECEDENCE_MARKET_DATA: dict[str, int] = {
    "schwab_api": 0,
    "yfinance": 1,
}


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
        end_date: caller's window end (inclusive). Used ONLY for the return
            slice — the on-disk archive always extends to
            `_last_completed_session_today()` regardless. Historical callers
            receive a slice; they do not truncate the archive.
        cache_dir: archive directory (typically `cfg.paths.prices_cache_dir`).
            Must already exist.
        archive_history_days: full-history fetch window (typically
            `cfg.archive.archive_history_days`).

    Returns:
        DataFrame indexed by date with OHLCV columns; rows ≤ end_date.
        None if yfinance returns empty (delisted / invalid ticker / no history).
    """
    cache_dir = Path(cache_dir)
    ticker = ticker.upper()
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
        full_start = today - timedelta(days=full_calendar_days)
        fetched = _yf_download_window(ticker, start=full_start, end=today)
        if fetched.empty:
            # Codex R2 Major 2 — established ticker + transient empty upstream:
            # do NOT overwrite archive or meta. Fall back to the existing archive
            # so callers don't see a transient yfinance hiccup as data absence.
            # Meta stays stale so the next call retries the weekly refresh.
            if archive is not None and not archive.empty:
                return archive.loc[archive.index.date <= end_date]
            return None
        fetched = fetched.tail(archive_history_days)
        _write_archive_atomic(parquet_path, fetched)
        _write_meta_atomic(meta_path, {"last_full_refresh_date": today.isoformat()})
        return fetched.loc[fetched.index.date <= end_date]

    assert archive is not None
    latest_stored: date = archive.index.max().date()
    if latest_stored < today:
        gap_start = latest_stored + timedelta(days=1)
        gap = _yf_download_window(ticker, start=gap_start, end=today)
        if not gap.empty:
            combined = pd.concat([archive, gap])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            combined = combined.tail(archive_history_days)
            _write_archive_atomic(parquet_path, combined)
            archive = combined

    return archive.loc[archive.index.date <= end_date]


# ---------------------------------------------------------------------------
# Shape A persistence (Schwab API Sub-bundle C T-C.2 / plan §H.6.3)
# ---------------------------------------------------------------------------
#
# Files: `{cache_dir}/{TICKER}.{PROVIDER}.parquet` with an explicit
# `asof_date` column (ISO `YYYY-MM-DD` string per
# `swing.integrations.schwab.models.OhlcvBar.asof_date`) plus OHLCV columns.
# Coexists with the legacy `{TICKER}.parquet` shape consumed by
# `read_or_fetch_archive` above; the one-shot `_backward_compat_rename`
# migrates the legacy file to `{TICKER}.yfinance.parquet`.
#
# `resolve_ohlcv_window` is the read path consumed by the Sub-bundle C
# ladder (`swing/integrations/schwab/marketdata_ladder.py` — T-C.3); reads
# both per-provider files (if present), filters to the caller's
# [start, end] window, then picks the highest-priority row per asof_date.


def _shape_a_path(cache_dir: Path, ticker: str, provider: str) -> Path:
    """Return the Shape A parquet path for `(ticker, provider)`.

    Ticker is uppercased here so callers can pass lowercase without
    silently splitting the cache (mirrors the existing helper's
    discipline at `read_or_fetch_archive`).
    """
    return cache_dir / f"{ticker.upper()}.{provider}.parquet"


def write_window(
    ticker: str,
    window: pd.DataFrame | None,
    provider: str,
    *,
    cache_dir: Path,
) -> None:
    """Atomically write a Shape A window to
    `{cache_dir}/{TICKER}.{PROVIDER}.parquet`.

    Empty-window guard (Codex R1 Major #7 + CLAUDE.md "External-API
    empty-result must be treated as transient"): if `window` is `None` or
    has zero rows, return WITHOUT touching disk. This prevents the ladder
    from clobbering a populated parquet when a transient Schwab call
    returns no candles. The caller (ladder) records the audit row with
    `status='error'`; this function's contract is "non-empty windows only".

    Defense-in-depth: caller MUST ensure non-empty windows in normal flow;
    the guard exists so a future regression cannot blank the archive.
    """
    if window is None:
        return
    # `len()` on a DataFrame returns row count; an explicit `.empty` check
    # tolerates non-DataFrame falsy inputs the caller might pass in error.
    try:
        n_rows = len(window)
    except TypeError:
        return
    if n_rows == 0:
        return

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _shape_a_path(cache_dir, ticker, provider)
    _write_archive_atomic(path, window)


def resolve_ohlcv_window(
    ticker: str,
    *,
    start: str,
    end: str,
    cache_dir: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Resolve the OHLCV window for `ticker` across both provider parquets.

    Reads `{TICKER}.schwab_api.parquet` AND `{TICKER}.yfinance.parquet` from
    `cache_dir` (whichever are present), filters to ISO-date window
    `[start, end]` (inclusive on both ends), and selects the highest-
    priority row per `asof_date` per `_SOURCE_PRECEDENCE_MARKET_DATA`.

    Codex R1 Minor #4: the window filter (`start <= asof_date <= end`) is
    applied AFTER reading both parquets but BEFORE winner selection so
    out-of-range rows neither pollute the merge decision nor leak into the
    return value.

    Args:
        ticker: ticker symbol; will be uppercased to match write_window.
        start: ISO `YYYY-MM-DD` window start (inclusive).
        end: ISO `YYYY-MM-DD` window end (inclusive).
        cache_dir: archive directory; need not exist.

    Returns:
        Tuple of (DataFrame indexed 0..n-1 with `asof_date` column +
        OHLCV columns sorted ascending by `asof_date`,
        provenance dict mapping `asof_date` -> winning provider name).
        Empty DataFrame + empty dict when no rows match.
    """
    cache_dir = Path(cache_dir)
    ticker_u = ticker.upper()

    # Read both providers' parquet files (if present), accumulate rows by
    # (asof_date, provider). Reading returns a fresh DataFrame so we keep
    # provider attribution on a per-row basis.
    rows_by_date: dict[str, dict[str, pd.Series]] = {}
    for provider in ("schwab_api", "yfinance"):
        path = _shape_a_path(cache_dir, ticker_u, provider)
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if df.empty or "asof_date" not in df.columns:
            continue
        for _, row in df.iterrows():
            asof = str(row["asof_date"])
            rows_by_date.setdefault(asof, {})[provider] = row

    # Merge: filter to [start, end] then pick lowest-precedence provider.
    merged_rows: list[pd.Series] = []
    provenance: dict[str, str] = {}
    for asof_date in sorted(rows_by_date.keys()):
        if not (start <= asof_date <= end):
            continue
        candidates = rows_by_date[asof_date]
        winner_provider = min(
            candidates.keys(),
            key=lambda p: _SOURCE_PRECEDENCE_MARKET_DATA.get(p, 99),
        )
        merged_rows.append(candidates[winner_provider])
        provenance[asof_date] = winner_provider

    if not merged_rows:
        return pd.DataFrame(), {}

    merged_df = pd.DataFrame(merged_rows).reset_index(drop=True)
    return merged_df, provenance


def _normalize_legacy_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a legacy DatetimeIndex archive into Shape A.

    Legacy archives produced by ``read_or_fetch_archive`` /
    ``_yf_download_window`` carry a DatetimeIndex (date-like, may be named
    ``Date`` after ``reset_index``) plus capitalized OHLCV columns
    (``Open``/``High``/``Low``/``Close``/``Volume``). Shape A (consumed by
    ``resolve_ohlcv_window``) requires:

      - an ``asof_date`` column (ISO ``YYYY-MM-DD`` string) — NOT an index;
      - lowercase OHLCV column names (``open``/``high``/``low``/``close``/
        ``volume``) matching ``_mk_window`` in tests + the
        ``write_window`` writer pattern from ``map_price_history_to_window``.

    Codex R1 Major #2 fix: prior to this helper, ``_backward_compat_rename``
    only renamed the legacy file without normalizing — Shape A's reader
    (``resolve_ohlcv_window``) requires an ``asof_date`` column and skips
    files without one at lines 360-362, so a real legacy archive became
    INVISIBLE post-rename. Idempotent on already-Shape-A frames.
    """
    if "asof_date" in df.columns:
        return df  # already Shape A — idempotent

    normalized = df.reset_index()
    # `reset_index` promotes the index to a column; the legacy yfinance shape
    # names it `Date` (or sometimes `index` for an unnamed DatetimeIndex). Find
    # the most date-like column and rename it `asof_date`.
    date_col: str | None = None
    for candidate in ("Date", "date", "index", "Datetime", "datetime"):
        if candidate in normalized.columns:
            date_col = candidate
            break
    if date_col is None:
        # Last-ditch: scan for the first column whose dtype is datetime-like.
        for col in normalized.columns:
            if pd.api.types.is_datetime64_any_dtype(normalized[col]):
                date_col = col
                break
    if date_col is None:
        raise ValueError(
            "_normalize_legacy_dataframe: cannot identify date column; "
            f"available columns: {list(normalized.columns)!r}"
        )

    normalized = normalized.rename(columns={date_col: "asof_date"})
    # Coerce to ISO date string (mirrors `OhlcvBar.asof_date` + Shape A
    # convention used elsewhere in this module).
    normalized["asof_date"] = (
        pd.to_datetime(normalized["asof_date"]).dt.date.astype(str)
    )

    # Normalize OHLCV column case to lowercase to match Shape A. Preserves
    # any non-OHLCV columns verbatim (defensive).
    rename_map: dict[str, str] = {}
    for col in normalized.columns:
        lc = col.lower()
        if lc in ("open", "high", "low", "close", "volume") and col != lc:
            rename_map[col] = lc
    if rename_map:
        normalized = normalized.rename(columns=rename_map)

    return normalized.reset_index(drop=True)


def _backward_compat_rename(ticker: str, *, cache_dir: Path) -> None:
    """One-shot migration of legacy `{TICKER}.parquet` → Shape A
    `{TICKER}.yfinance.parquet`.

    Per plan §H.6.3 + Codex R1 Major #6 + R2 Minor #1 — handles 4 cases
    without data loss:

    1. **old-only:** `{TICKER}.parquet` exists, `{TICKER}.yfinance.parquet`
       absent → NORMALIZE legacy DatetimeIndex/capitalized shape to Shape A
       (asof_date column + lowercase OHLCV) via
       ``_normalize_legacy_dataframe``, write to
       ``{TICKER}.yfinance.parquet``, unlink the old file (same-volume).
       Codex R1 Major #2 fix: previously a bare ``os.replace`` would have
       left the post-rename file invisible to ``resolve_ohlcv_window``.
    2. **both-exist:** MERGE-AND-QUARANTINE — read both, normalize the
       legacy one first, then concat-dedupe on ``asof_date`` keeping the
       new file's row on conflict (post-Shape-A writes are presumed more
       recent than the legacy snapshot), write merged back to the new file,
       rename old to ``{TICKER}.parquet.orphan-{timestamp}.parquet``. The
       orphan file is operator-visible only; the resolver never reads it.
    3. **new-only:** already migrated; no-op.
    4. **neither:** no historical data; no-op.

    Idempotent: invoking twice on the same ticker drives the post-state to
    case 3 (new-only) on the second call, which is a no-op.
    """
    cache_dir = Path(cache_dir)
    ticker_u = ticker.upper()
    old_path = cache_dir / f"{ticker_u}.parquet"
    new_path = cache_dir / f"{ticker_u}.yfinance.parquet"

    old_exists = old_path.exists()
    new_exists = new_path.exists()

    if old_exists and not new_exists:
        # Read + normalize + write to Shape A path; unlink the old file.
        # We can't just `os.replace` because the legacy shape is invisible
        # to `resolve_ohlcv_window` (Codex R1 Major #2).
        old_df = pd.read_parquet(old_path)
        normalized = _normalize_legacy_dataframe(old_df)
        _write_archive_atomic(new_path, normalized)
        with contextlib.suppress(OSError):
            old_path.unlink()
        return

    if old_exists and new_exists:
        # MERGE-AND-QUARANTINE — preserve every row. Normalize legacy first.
        old_df = pd.read_parquet(old_path)
        new_df = pd.read_parquet(new_path)
        old_df = _normalize_legacy_dataframe(old_df)
        new_df = _normalize_legacy_dataframe(new_df)  # idempotent on Shape A

        # Both frames now have `asof_date` column; dedup on it.
        merged = pd.concat([old_df, new_df]).drop_duplicates(
            subset=["asof_date"], keep="last"
        )
        merged = merged.sort_values("asof_date").reset_index(drop=True)

        _write_archive_atomic(new_path, merged)

        # Quarantine the old file with a UTC timestamp suffix so an operator
        # can inspect it post-fact. Same-volume rename (`cache_dir` → `cache_dir`).
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        orphan_path = cache_dir / f"{ticker_u}.parquet.orphan-{timestamp}.parquet"
        os.replace(old_path, orphan_path)
        return

    # Cases 3 + 4: new-only or neither — no-op.
    return
