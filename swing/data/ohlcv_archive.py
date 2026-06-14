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
import functools
import json
import logging
import math
import os
import tempfile
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from swing.data.ohlcv_finiteness import is_finite_ohlc

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

# Arc 6 warm-batch tunables (module constants, NOT config — benchmark-pinned).
DEFAULT_CHUNK_SIZE = 75          # benchmark sweeps 50-100; §8 reliability-constrained
GAP_DEEP_BAND_TRADING_DAYS = 30  # gaps staler than this collapse into ONE deep band


@dataclass
class WarmReport:
    """Lightweight result of warm_archives_batch — counts + the fallback list.
    Carries NO DB rows and NO schema (Arc 6 §6). `degraded` is True whenever
    any ticker fell through to the serial path (per-ticker miss or whole-chunk
    failure), so _step_evaluate can decide whether to emit a #27 warning."""
    cache_hit: int = 0
    gap: int = 0
    deep_gap: int = 0
    full_refresh: int = 0
    chunks_attempted: int = 0
    chunk_failures: int = 0
    fallback: list[str] = field(default_factory=list)
    wall_seconds: float = 0.0
    dry_run: bool = False
    # Arc 8: trailing NaN-OHLC bars dropped at the warm write barrier (#27 audit).
    trailing_nan_trimmed: int = 0

    @property
    def degraded(self) -> bool:
        return bool(self.fallback) or self.chunk_failures > 0


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


def _strip_incomplete_sessions(df: pd.DataFrame, cutoff_iso: str) -> pd.DataFrame:
    """Drop archive rows dated AFTER the last completed session (cutoff_iso =
    ISO YYYY-MM-DD). Shape-agnostic: Shape-A frames carry an `asof_date` column
    (string OR Timestamp -- both normalized to date before comparison so a
    `2026-06-04 00:00:00` value cannot lexically out-sort the cutoff day);
    legacy/yfinance frames are DatetimeIndex'd (compare `index.date`). Returns a
    new frame (may be empty).

    Codex R1 MAJOR #1: this is the single write-barrier chokepoint, so it FAILS
    CLOSED -- a NON-EMPTY frame carrying neither recognized shape raises (it
    must never silently persist a possibly-`> cutoff` row). An EMPTY frame of
    any shape passes through unchanged (nothing to strip)."""
    cutoff = date.fromisoformat(cutoff_iso)
    if "asof_date" in df.columns:
        asof = pd.to_datetime(df["asof_date"]).dt.date
        return df[asof <= cutoff]
    if isinstance(df.index, pd.DatetimeIndex):
        return df[df.index.date <= cutoff]
    if len(df) == 0:
        return df
    raise ValueError(
        "_strip_incomplete_sessions: unrecognized frame shape (no 'asof_date' "
        "column and non-DatetimeIndex index); refusing to persist to avoid "
        "leaking a row dated after the last completed session"
    )


def _write_archive_atomic(parquet_path: Path, df: pd.DataFrame) -> None:
    # Completed-day write barrier (L2, the single chokepoint): no archive write
    # path may persist a row dated after the last completed session. Applied
    # here -- the one function ALL Shape-A writers funnel through (write_window,
    # read_or_fetch_archive, _backward_compat_rename) -- so none can bypass it.
    df = _strip_incomplete_sessions(df, _last_completed_session_today().isoformat())
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


def _trim_trailing_ragged(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Arc 8 — drop trailing rows where ANY of Open/High/Low/Close is non-finite.

    Phase 18 18-A: the finiteness test is the shared ``is_finite_ohlc`` (the ONE
    predicate also used by the temporal-log writer; C1) — ``math.isfinite``, so
    a trailing +/-inf row is trimmed too (a strict superset of the prior
    ``isna()`` NaN-only check, aligning with the engine gate's finiteness
    definition). Volume is excluded from ``ohlc`` so Volume-only-NaN never trims.

    Iterates from the END, removing rows while the newest remaining row has a
    NaN in any OHLC field; stops at the first clean row. Returns the trimmed
    frame plus the number of rows dropped.

    Scope (LOCKED, run-#99 evidence base):
    - Guards ONLY the incoming TRAILING bar(s) — the run-#99 class is yfinance
      returning the newest bar with NaN `Close` while O/H/L/V are present (the
      adjusted-close derivation artifact). Trimming it leaves the meta/archive
      stale so the next fetch retries a settled bar (the F6-transient posture).
    - INTERIOR ragged rows are PRESERVED — the Phase-15 bad-bar-accept posture
      for HISTORICAL bars is explicitly unchanged; this barrier never reaches
      past the first clean trailing row.
    - Volume-NaN ALONE does NOT trim (legitimately volume-less bars exist).
    """
    ohlc = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    if df.empty or not ohlc:
        return df, 0
    n = len(df)
    cut = n
    while cut > 0 and not is_finite_ohlc(*df.iloc[cut - 1][ohlc]):
        cut -= 1
    if cut == n:
        return df, 0
    return df.iloc[:cut], n - cut


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
    # Arc 8 trailing-bar NaN-Close barrier — covers BOTH serial branches (the
    # full-refresh tail->write @~709 and the gap concat->write @~722). A frame
    # trimmed to empty composes with the existing `if fetched.empty` /
    # `if not gap.empty` guards (no write, meta stays stale, retry next call).
    trimmed_df, n_trimmed = _trim_trailing_ragged(df)
    if n_trimmed:
        dropped = [d.date().isoformat() for d in df.index[len(trimmed_df):]]
        log.warning(
            "serial trailing-ragged trim (%s): dropped %d trailing non-finite "
            "OHLC bar(s) %s (retry next fetch)", ticker, n_trimmed, dropped,
        )
    return trimmed_df


def _last_completed_session_today() -> date:
    """Return the most recent completed NYSE session as of now. Used as the
    'today' anchor for weekly-refresh and partial-bar-strip semantics.
    Imports lazily to avoid circular references at module load time."""
    from swing.evaluation.dates import last_completed_session
    return last_completed_session(datetime.now())


def _full_refresh_due(
    ticker: str,
    last_full_refresh: date,
    today_session: date,
    *,
    stagger_enabled: bool,
) -> bool:
    """PURE predicate — the single source of full-refresh-due truth, called by
    BOTH read_or_fetch_archive AND warm_archives_batch with the SAME
    stagger_enabled value (resolved once by _full_refresh_stagger_enabled).

    `last_full_refresh` is a real date; callers with no parseable meta MUST
    NOT call this (they are full-refresh-due unconditionally via the
    archive-missing / meta-missing arms of the classifier).

    stagger_enabled=False  -> exact legacy `days_since >= 7` cliff.
    stagger_enabled=True   -> fire on the ticker's own crc32 bucket day once
    `>= 7` due, with a `>= 13` hard ceiling bounding worst-case staleness.
    crc32 (NOT Python hash()) for cross-process determinism — hash(str) is
    randomized by PYTHONHASHSEED.
    """
    days_since_full = (today_session - last_full_refresh).days
    if not stagger_enabled:
        return days_since_full >= 7
    bucket = zlib.crc32(ticker.encode()) % 7
    day_idx = today_session.toordinal() % 7
    return (days_since_full >= 7 and bucket == day_idx) or (days_since_full >= 13)


def _load_archive_config_for_stagger() -> bool:
    """Read [archive].stagger_full_refresh from the tracked project config.

    Isolated so tests can monkeypatch the config read without touching disk.
    Lazy import avoids any import cycle (swing.config imports only stdlib).
    """
    from swing.config import Config
    return Config.from_defaults().archive.stagger_full_refresh


@functools.lru_cache(maxsize=1)
def _full_refresh_stagger_enabled() -> bool:
    """Single source of the stagger kill-switch, cached at module level.

    Returns True (stagger ON) if the config is unreadable for any reason —
    the safe default that prevents the weekly storm. Cached for the process
    lifetime: the nightly pipeline (a fresh process) always reads current
    config; a long-lived `swing web` server holds the value until restart
    (call `_full_refresh_stagger_enabled.cache_clear()` to force a re-read,
    or restart the server — Arc 6 §5 R3 Minor #2).
    """
    try:
        return bool(_load_archive_config_for_stagger())
    except Exception:  # noqa: BLE001 — any failure -> safe default
        log.warning("could not resolve [archive].stagger_full_refresh; defaulting to True")
        return True


def _classify_warm_cohorts(
    tickers: list[str],
    *,
    cache_dir: Path,
    today_session: date,
    archive_history_days: int,
    stagger_enabled: bool,
) -> dict:
    """Bucket each ticker into cache-hit / gap-bands / deep-gap / full-refresh
    using the EXACT read_or_fetch_archive predicates (Arc 6 §4.1). Local I/O
    only — reads archive + meta from disk, performs ZERO yf.download calls.

    Returns a dict:
      {"cache_hit": [t...],
       "gap_bands": {latest_date: [t...], ...},   # near-current bands
       "deep_gap": [t...],                          # collapsed deep band
       "full_refresh": [t...]}
    """
    cache_dir = Path(cache_dir)
    cache_hit: list[str] = []
    gap_bands: dict[date, list[str]] = {}
    deep_gap: list[str] = []
    full_refresh: list[str] = []

    for raw in tickers:
        ticker = raw.upper()
        parquet_path, meta_path = _archive_paths(cache_dir, ticker)
        archive = _read_archive(parquet_path)
        meta = _read_meta(meta_path)

        last_full_refresh: date | None = None
        last_full_str = meta.get("last_full_refresh_date")
        if last_full_str:
            try:
                last_full_refresh = date.fromisoformat(last_full_str)
            except ValueError:
                last_full_refresh = None

        # Archive-missing / empty / meta-missing -> full-refresh (NO bucket gate),
        # mirroring read_or_fetch_archive's needs_full_refresh arms.
        if archive is None or archive.empty or last_full_refresh is None:
            full_refresh.append(ticker)
            continue
        if _full_refresh_due(ticker, last_full_refresh, today_session,
                             stagger_enabled=stagger_enabled):
            full_refresh.append(ticker)
            continue

        latest_stored = archive.index.max().date()
        if latest_stored >= today_session:
            cache_hit.append(ticker)
            continue

        # Gap cohort — band by latest_stored; collapse very-stale into deep band.
        # Codex R1 Major #3: measure staleness in TRADING days (spec §4.2 locks the
        # collapse at "> 30 trading days"), NOT calendar days through
        # _calendar_window_for_trading_days (which adds a +30 fetch buffer -> ~74
        # calendar days ~= 53 trading days, far looser than the spec). bdate_range
        # counts business days (a holiday-agnostic trading-session proxy, same order
        # of approximation as the existing helper).
        gap_sessions = pd.bdate_range(
            latest_stored + timedelta(days=1), today_session
        ).size
        if gap_sessions > GAP_DEEP_BAND_TRADING_DAYS:
            deep_gap.append(ticker)
        else:
            gap_bands.setdefault(latest_stored, []).append(ticker)

    return {
        "cache_hit": cache_hit,
        "gap_bands": gap_bands,
        "deep_gap": deep_gap,
        "full_refresh": full_refresh,
    }


def _chunk_tickers(tickers: list[str], *, chunk_size: int) -> list[list[str]]:
    """Split into chunks of chunk_size, folding a trailing lone remnant into the
    previous chunk so no size-1 chunk is sent (the single-ticker-remnant shape
    is still handled by _extract_ticker_subframe — this just avoids it where we
    can). Returns [] for empty input."""
    if not tickers:
        return []
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        lone = chunks.pop()
        chunks[-1] = chunks[-1] + lone
    return chunks


def _extract_ticker_subframe(frame: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Extract + validate one ticker's OHLCV subframe from a group_by='ticker'
    batch response (Arc 6 §4.3 validation ladder). Returns the normalized
    subframe ([Open,High,Low,Close,Volume], tz-stripped) on success, or None on
    ANY gate failure (-> caller routes the ticker to fallback). Wrapped so a
    malformed shape degrades to None rather than crashing the chunk."""
    try:
        ticker = ticker.upper()
        # (a) subframe present. Flat (non-MultiIndex) frame == single-ticker remnant.
        if isinstance(frame.columns, pd.MultiIndex):
            level0 = {str(c).upper(): c for c in frame.columns.get_level_values(0)}
            if ticker not in level0:
                return None
            sub = frame[level0[ticker]]
            if isinstance(sub, pd.Series):  # degenerate single-column
                return None
        else:
            sub = frame  # flat remnant -> already this ticker's OHLCV
        sub = sub.copy()
        # case-insensitive column resolution
        col_map = {str(c).lower(): c for c in sub.columns}
        # (b) required OHLCV columns present
        required = ["open", "high", "low", "close", "volume"]
        if not all(r in col_map for r in required):
            return None
        keep = sub[[col_map[r] for r in required]]
        keep.columns = ["Open", "High", "Low", "Close", "Volume"]  # canonical (Adj Close dropped)
        # (c) non-empty after dropna(how="all") — F6: present-but-all-NaN -> fallback
        keep = keep.dropna(how="all")
        if keep.empty:
            return None
        # (d) index parseable to DatetimeIndex
        if not isinstance(keep.index, pd.DatetimeIndex):
            keep.index = pd.to_datetime(keep.index)
        if getattr(keep.index, "tz", None) is not None:
            keep.index = keep.index.tz_localize(None)
        return keep
    except Exception:  # noqa: BLE001 — any unforeseen shape error -> fallback
        return None


def _fetch_chunk(
    chunk: list[str], *, start: date, end: date,
) -> tuple[dict[str, pd.DataFrame], list[str], bool]:
    """Fetch ONE chunk with a single multi-ticker yf.download (threads=True,
    group_by='ticker'), mirroring _yf_download_window's kwargs + the inclusive-end
    `+1 day` convention. threads=True is the Arc-6 spec §8 stretch lever,
    OPERATOR-AUTHORIZED 2026-06-10 after the 6c cold gate measured threads=False
    at 207.5s warm (evaluate 220s vs the <=90s target); the serial-fallback
    safety net (proven live, run #99) bounds the rate-limit downside to a slower
    night, never a broken one. The SINGLE-ticker path (_yf_download_window)
    keeps threads=False per the original gotcha. Revert = this one kwarg.
    Returns (extracted, failed, chunk_failed):
      - extracted: {ticker: valid_subframe}
      - failed: tickers that did not extract (per-ticker miss OR whole-chunk)
      - chunk_failed: True ONLY when the whole call failed (yf.download raised, or
        an empty/None response) — a WHOLE-CHUNK download failure (Arc 6 §6). A
        VALID response in which every ticker is present-but-all-NaN sets
        chunk_failed=False (those are per-ticker misses), so the #27
        chunk_failures counter is not corrupted (Codex R1 Major #6)."""
    try:
        raw = yf.download(
            chunk, start=start, end=end + timedelta(days=1),
            group_by="ticker", threads=True, progress=False,
            auto_adjust=False, actions=False,
        )
    except Exception as exc:  # noqa: BLE001 — whole chunk -> serial fallback
        log.warning("warm chunk yf.download failed (%d tickers -> fallback): %s",
                    len(chunk), exc)
        return {}, list(chunk), True
    if raw is None or raw.empty:
        return {}, list(chunk), True
    extracted: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for t in chunk:
        sub = _extract_ticker_subframe(raw, t)
        if sub is None:
            failed.append(t.upper())
        else:
            extracted[t.upper()] = sub
    return extracted, failed, False


def _merge_gap_subframe(
    cache_dir: Path, ticker: str, sub: pd.DataFrame, *, archive_history_days: int,
) -> None:
    """Merge a gap subframe into the existing archive — data-content-identical to
    the serial read_or_fetch_archive incremental-gap branch (lines ~277-281):
    concat, dedup keep='last', sort, tail(N), atomic write. NO meta write (gap).

    Codex R1 Critical #1 (deep-band overlap): the deep-gap band collapses tickers
    with DIFFERENT latest_stored into ONE wide window, so a ticker's subframe can
    carry rows AT-OR-BEFORE its own latest_stored (rows another, staler band member
    needed). The serial gap branch fetches ONLY `[latest+1, today]`, so it NEVER
    rewrites a pre-existing archived bar. To match that outcome we slice the
    incoming sub to `index.date > latest_stored` before concat — dropping the
    overlap so existing bars are untouched (a re-fetch of an old bar yfinance may
    have re-stated must NOT overwrite the archived value; that is the serial
    behavior and the #26-temporal-mutation parity requirement). Harmless for
    ordinary bands (all members share latest_stored → zero overlap)."""
    parquet_path, _ = _archive_paths(Path(cache_dir), ticker.upper())
    archive = _read_archive(parquet_path)
    if archive is None or archive.empty:
        # Codex R1 Critical #2: a gap-classified ticker had a non-empty archive at
        # classify time; if it vanished by merge time (TOCTOU), writing the gap
        # sub ALONE would truncate retained history AND — with a surviving recent
        # meta — let the serial path serve the stub as a cache-hit, masking the
        # loss. Pure accelerator: write NOTHING and raise so _warm_one_window
        # routes the ticker to WarmReport.fallback; the serial read_or_fetch_archive
        # (archive-missing -> full-refresh) stays authoritative and self-heals.
        raise RuntimeError(
            f"gap-classified {ticker} archive missing/empty at merge time; "
            "routing to serial fallback (no truncated write)"
        )
    latest_stored = archive.index.max().date()
    # Drop any incoming row dated <= latest_stored so existing bars are never
    # overwritten (byte-parity with the serial `[latest+1, today]` gap fetch).
    fresh = sub.loc[sub.index.date > latest_stored]
    # Arc 8 (Codex R1 MAJOR): the trailing-ragged trim can leave a sub with ONLY
    # overlap rows (<= latest_stored) — e.g. a deep-gap band whose only post-
    # latest_stored row was today's ragged bar. With nothing fresh, the serial
    # gap path no-ops (its `[latest+1, today]` fetch trims to empty -> no write);
    # match that here so warm leaves the archive untouched too (trim-to-empty
    # parity by construction; no needless rewrite).
    if fresh.empty:
        return
    combined = pd.concat([archive, fresh])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined = combined.tail(archive_history_days)
    _write_archive_atomic(parquet_path, combined)


def _write_full_refresh_subframe(
    cache_dir: Path, ticker: str, sub: pd.DataFrame, *,
    today_session: date, archive_history_days: int,
) -> None:
    """Write a full-refresh subframe — data-content-identical to the serial
    full-refresh branch (lines ~266-268): tail(N), atomic write, THEN write meta."""
    parquet_path, meta_path = _archive_paths(Path(cache_dir), ticker.upper())
    fetched = sub.tail(archive_history_days)
    _write_archive_atomic(parquet_path, fetched)
    _write_meta_atomic(meta_path, {"last_full_refresh_date": today_session.isoformat()})


def warm_archives_batch(
    tickers: list[str],
    *,
    cache_dir: Path,
    archive_history_days: int,
    end_date: date,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    inter_chunk_pause_s: float = 0.0,
    dry_run: bool = False,
) -> WarmReport:
    """Pre-warm per-ticker archives with batched multi-ticker yf.download calls
    so the serial read_or_fetch_archive loops all hit the cache-hit branch
    (Arc 6 §3). PURE ACCELERATOR: any per-ticker or per-chunk failure routes to
    `WarmReport.fallback`; the serial path re-fetches those. Never raises for a
    data problem.

    SESSION ANCHOR (Codex R1 Critical #2 — clarified). The warm has NO return
    slice (it returns a WarmReport, not bars), so `end_date` is accepted for
    signature parity with the spec §3 contract but is intentionally UNUSED for
    the write anchor: archives are always warmed to
    `today_session = _last_completed_session_today()`, the SAME source function
    the serial write path (`read_or_fetch_archive` + `_write_archive_atomic`'s
    completed-day strip) uses. The §4.1 invariant is "same SOURCE FUNCTION", not
    a single value threaded through `_write_archive_atomic` (a Shape-A shared
    writer outside this arc's carve-out). Resolving `today_session` once here and
    passing it to the classifier + writers means the warm introduces NO new
    divergence surface beyond what already exists — the three serial fetch loops
    in `_step_evaluate` each call `_last_completed_session_today()` independently
    today. A session-boundary race remains theoretically possible (warm vs serial
    crossing ~16:00 ET mid-run) but is identical in kind to that pre-existing
    inter-loop race and acceptable for a single-operator nightly that runs well
    after the close. Callers MUST pass `end_date` (signature contract); pass
    `last_completed_session(run_now)` from the runner for documentation symmetry.

    dry_run=True: classify + return cohort counts with ZERO yf.download calls.
    """
    import time
    started = time.monotonic()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    today_session = _last_completed_session_today()
    stagger_enabled = _full_refresh_stagger_enabled()

    deduped = sorted({t.upper() for t in tickers})
    cohorts = _classify_warm_cohorts(
        deduped, cache_dir=cache_dir, today_session=today_session,
        archive_history_days=archive_history_days, stagger_enabled=stagger_enabled,
    )
    gap_count = sum(len(v) for v in cohorts["gap_bands"].values())
    report = WarmReport(
        cache_hit=len(cohorts["cache_hit"]),
        gap=gap_count,
        deep_gap=len(cohorts["deep_gap"]),
        full_refresh=len(cohorts["full_refresh"]),
        dry_run=dry_run,
    )
    if dry_run:
        report.wall_seconds = time.monotonic() - started
        return report

    # --- gap bands: each distinct latest_stored band gets its own window ---
    for band_latest, band_tickers in cohorts["gap_bands"].items():
        _warm_one_window(
            band_tickers, start=band_latest + timedelta(days=1), end=today_session,
            cohort="gap", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    # --- deep-gap band: ONE widest window (still INCREMENTAL — no meta) ---
    if cohorts["deep_gap"]:
        deep_latest = min(
            _read_archive(_archive_paths(cache_dir, t)[0]).index.max().date()
            for t in cohorts["deep_gap"]
        )
        _warm_one_window(
            cohorts["deep_gap"], start=deep_latest + timedelta(days=1), end=today_session,
            cohort="gap", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    # --- full-refresh cohort: one deep window, writes meta ---
    if cohorts["full_refresh"]:
        full_start = today_session - timedelta(
            days=_calendar_window_for_trading_days(archive_history_days)
        )
        _warm_one_window(
            cohorts["full_refresh"], start=full_start, end=today_session,
            cohort="full_refresh", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    report.wall_seconds = time.monotonic() - started
    return report


def _warm_one_window(
    tickers: list[str], *, start: date, end: date, cohort: str,
    cache_dir: Path, today_session: date, archive_history_days: int,
    chunk_size: int, inter_chunk_pause_s: float, report: WarmReport,
) -> None:
    """Fetch one uniform [start, end] window for a set of tickers in chunks;
    merge each extracted subframe per the cohort's write rule. Mutates `report`
    counters + fallback list. cohort in {'gap', 'full_refresh'}."""
    import time
    chunks = _chunk_tickers(tickers, chunk_size=chunk_size)
    for i, chunk in enumerate(chunks):
        report.chunks_attempted += 1
        extracted, failed, chunk_failed = _fetch_chunk(chunk, start=start, end=end)
        if chunk_failed:
            report.chunk_failures += 1   # whole-chunk download failure ONLY (Codex R1 Major #6)
        report.fallback.extend(failed)
        for ticker, sub in extracted.items():
            # Arc 8 trailing-bar NaN-Close barrier — trim here (the single locus
            # feeding BOTH warm cohorts: gap-merge and full-refresh) rather than
            # inside _extract_ticker_subframe, because this site has the `report`
            # for the #27 count and lets a trim-to-empty SKIP-without-fallback.
            # Chosen over fallback-to-serial (the brief's option a) because the
            # serial path would re-fetch the SAME ragged bar and trim it to the
            # SAME no-op — wasteful on an event night (134 archives, run #99);
            # archives end byte-identical either way. The skip leaves the archive
            # + meta stale so the next call retries a settled bar.
            trimmed_sub, trimmed = _trim_trailing_ragged(sub)
            if trimmed:
                report.trailing_nan_trimmed += trimmed
                dropped = [d.date().isoformat() for d in sub.index[len(trimmed_sub):]]
                log.warning(
                    "warm trailing-ragged trim (%s): dropped %d trailing "
                    "non-finite OHLC bar(s) %s (retry next fetch)", ticker, trimmed, dropped,
                )
            sub = trimmed_sub
            if sub.empty:
                continue
            try:
                if cohort == "gap":
                    _merge_gap_subframe(cache_dir, ticker, sub,
                                        archive_history_days=archive_history_days)
                else:
                    _write_full_refresh_subframe(
                        cache_dir, ticker, sub, today_session=today_session,
                        archive_history_days=archive_history_days)
            except Exception as exc:  # noqa: BLE001 — per-ticker merge fault -> fallback
                log.warning("warm merge failed for %s -> fallback: %s", ticker, exc)
                report.fallback.append(ticker)
        if inter_chunk_pause_s and i < len(chunks) - 1:
            time.sleep(inter_chunk_pause_s)


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

    if archive is None or archive.empty or last_full_refresh is None:
        needs_full_refresh = True
    else:
        needs_full_refresh = _full_refresh_due(
            ticker, last_full_refresh, today,
            stagger_enabled=_full_refresh_stagger_enabled(),
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
    """Atomically write a Shape A window, merging with any pre-existing rows by
    `asof_date` (keep='last'). The hard completed-day strip lives in
    `_write_archive_atomic` (every write inherits it); this function adds the
    merge + the M3 guarantee (rewrite existing on an empty incoming so a
    pre-existing on-disk partial is stripped) + F6 (never blank valid history
    on a transient empty fetch).

    Merge semantics: the incoming window is concatenated with the existing
    parquet (if any), deduped on `asof_date` with `keep='last'` (NEW rows win
    on conflict), sorted ascending, then atomically written back -- preserving
    rows OUTSIDE the fetched window (e.g. a 1260-row archive is not clobbered
    by a 60-row ladder fetch).

    F6 (CLAUDE.md "External-API empty-result must be treated as transient"): an
    empty/None incoming window NEVER blanks valid (<= cutoff) history. It only
    triggers a rewrite when the on-disk file still carries a > cutoff partial
    (M3) -- the rewrite re-runs the atomic strip and drops that partial.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _shape_a_path(cache_dir, ticker, provider)
    cutoff_iso = _last_completed_session_today().isoformat()

    # --- normalize incoming to a DataFrame-or-None ---
    incoming: pd.DataFrame | None = window
    if incoming is not None and not isinstance(incoming, pd.DataFrame):
        try:
            is_empty = len(incoming) == 0
        except TypeError:
            raise TypeError(
                f"write_window expects pd.DataFrame, got {type(window).__name__}"
            ) from None
        if is_empty:
            incoming = None
        else:
            raise TypeError(
                f"write_window expects pd.DataFrame, got {type(window).__name__}")
    if isinstance(incoming, pd.DataFrame) and incoming.empty:
        incoming = None

    # --- read existing ---
    existing: pd.DataFrame | None = None
    if path.exists():
        try:
            existing = pd.read_parquet(path)
        except (OSError, ValueError) as exc:  # pragma: no cover - defensive
            log.warning("write_window: failed to read existing %s (%s)", path, exc)
            existing = None

    if incoming is None and existing is None:
        return

    # Empty incoming: the only work is M3 -- strip a pre-existing on-disk
    # partial. SHAPE-AGNOSTIC (Codex R1 MAJOR #2): handle a DatetimeIndex/legacy
    # `existing` too, not just Shape-A. F6: an empty fetch NEVER blanks valid
    # (<= cutoff) history -- rewrite ONLY when a > cutoff partial is present.
    if incoming is None:
        assert existing is not None  # the both-None case returned above
        if len(_strip_incomplete_sessions(existing, cutoff_iso)) == len(existing):
            return  # no partial -> no-op
        _write_archive_atomic(path, existing)  # the barrier strips the partial
        return

    # legacy REPLACE for non-Shape-A incoming (dedup needs the asof_date key);
    # the atomic strip still fires inside _write_archive_atomic.
    if "asof_date" not in incoming.columns:
        _write_archive_atomic(path, incoming)
        return

    frames = [f for f in (existing, incoming)
              if f is not None and "asof_date" in f.columns]
    if not frames:
        return
    union = pd.concat(frames) if len(frames) > 1 else frames[0]
    merged = union.drop_duplicates(subset=["asof_date"], keep="last")
    merged = merged.sort_values("asof_date").reset_index(drop=True)
    # The atomic writer applies the > cutoff strip; an all-partial union writes
    # clean (no > cutoff survives), a valid union preserves <= cutoff history.
    _write_archive_atomic(path, merged)


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

    # Codex R1 Major #1: wire one-shot legacy migration into the read path so
    # existing {TICKER}.parquet archives are automatically migrated to Shape
    # A on FIRST read. Idempotent — subsequent invocations no-op when the
    # legacy file is absent (case 3: new-only).
    if cache_dir.exists():
        _backward_compat_rename(ticker_u, cache_dir=cache_dir)

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


_OHLCV_LOWER_NAMES = frozenset({"open", "high", "low", "close", "volume"})


def _file_mtime_ns(path: Path) -> int:
    """Return file mtime in nanoseconds when available, else seconds * 1e9.

    Codex R4 Minor #2: on filesystems with coarse-timestamp resolution
    (FAT32, older NFS without sub-second precision, post-rsync), a real
    legacy refresh can tie with a Shape A file's mtime at second-level,
    causing the ``_backward_compat_rename`` default branch (Shape A wins)
    to fire when the legacy refresh should have won. Prefer
    ``st_mtime_ns`` (nanosecond precision; NTFS + modern POSIX
    filesystems support it) over ``st_mtime`` (seconds; float, FAT32
    coarse). The graceful fallback to ``st_mtime * 1_000_000_000``
    preserves V1 best-effort posture on platforms whose
    ``os.stat_result`` does not carry ``st_mtime_ns``.
    """
    stat = path.stat()
    if hasattr(stat, "st_mtime_ns"):
        return stat.st_mtime_ns
    return int(stat.st_mtime * 1_000_000_000)


def _normalize_ohlcv_column_case(df: pd.DataFrame) -> pd.DataFrame:
    """Map any-case OHLCV column names to lowercase Shape A names.

    Returns a renamed view (or the unchanged frame if no rename needed).

    Codex R3 Minor #1: factored out so the public
    ``normalize_legacy_dataframe`` short-circuit branch (frames that
    already have ``asof_date``) still normalizes mixed-shape OHLCV
    casing rather than passing capitalized names through untouched.

    Codex R4 Minor #1: restored case-insensitive matching. The R3 Minor
    #1 implementation pinned an exact title-case keyset (``Open``,
    ``High``, ``Low``, ``Close``, ``Volume``), which narrowed the prior
    case-insensitive normalization. Mixed-casing frames carrying e.g.
    ``CLOSE`` (uppercase), ``open`` (already lowercase mixed with
    capitalized siblings), or other casing variants from V2 broker
    integrations would leak through untouched. Non-OHLCV columns
    (e.g. ``Volume_DAILY``) are preserved as-is — only columns whose
    ``col.lower()`` is in the canonical OHLCV name set are renamed,
    and only when the lowercase form differs from the original.
    """
    rename_dict: dict[str, str] = {}
    for col in df.columns:
        if (
            isinstance(col, str)
            and col.lower() in _OHLCV_LOWER_NAMES
            and col != col.lower()
        ):
            rename_dict[col] = col.lower()
    return df.rename(columns=rename_dict) if rename_dict else df


def normalize_legacy_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a legacy DatetimeIndex archive into Shape A.

    **Public helper (promoted from `_normalize_legacy_dataframe` per Codex
    R2 Minor #1).** Cross-module callers (e.g. the Schwab market-data ladder
    at `swing/integrations/schwab/marketdata_ladder.py`) consume this to
    normalize yfinance-shaped fallback windows into Shape A before
    persisting via `write_window`. The underscore-prefixed alias is
    preserved for backward compatibility with existing test imports.

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

    Codex R3 Minor #1 fix: a frame may carry ``asof_date`` AND capitalized
    OHLCV columns (mixed shape — e.g. a partial migration). The pre-R3
    short-circuit returned such a frame unchanged, leaking capitalized
    columns into Shape A consumers. Now we ALWAYS apply lowercase OHLCV
    column normalization, whether or not the date column needs work.
    """
    if "asof_date" in df.columns:
        # Already has asof_date — but still normalize OHLCV column casing
        # so mixed-shape frames (asof_date + capitalized OHLCV) emerge as
        # full Shape A.
        return _normalize_ohlcv_column_case(df)

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
            "normalize_legacy_dataframe: cannot identify date column; "
            f"available columns: {list(normalized.columns)!r}"
        )

    normalized = normalized.rename(columns={date_col: "asof_date"})
    # Coerce to ISO date string (mirrors `OhlcvBar.asof_date` + Shape A
    # convention used elsewhere in this module).
    normalized["asof_date"] = (
        pd.to_datetime(normalized["asof_date"]).dt.date.astype(str)
    )

    # Normalize OHLCV column case to lowercase to match Shape A. Shared
    # with the asof_date short-circuit branch (Codex R3 Minor #1).
    normalized = _normalize_ohlcv_column_case(normalized)

    return normalized.reset_index(drop=True)


# Codex R2 Minor #1: backward-compat alias. Existing tests + the Schwab
# market-data ladder import the underscore-prefixed name; preserve it so we
# don't churn unrelated call sites. New code should use the public name.
_normalize_legacy_dataframe = normalize_legacy_dataframe


def _backward_compat_rename(ticker: str, *, cache_dir: Path) -> None:
    """One-shot **non-destructive** replication of legacy `{TICKER}.parquet`
    → Shape A `{TICKER}.yfinance.parquet`.

    Per Codex R2 Major #1 — V1 LEAVES the legacy `{TICKER}.parquet` file
    IN PLACE because ``read_or_fetch_archive`` (consumed by
    ``swing/prices.py``, ``swing/pipeline/ohlcv.py``, and
    ``swing/trades/daily_management.py``) reads ONLY the legacy path. A
    destructive migration (unlink legacy / orphan-rename) would leave V1
    chart-rendering, daily-management ATR computation, and PriceFetcher
    callers without any archive on disk — they would refetch from yfinance
    on every read, defeating the cache. The plan §H.6.3 "rename" terminology
    is preserved for stability of the symbol; semantics are **copy** in V1.

    **V1 → V2 transition path:** when all consumers of
    ``read_or_fetch_archive`` have been refactored to consume the Shape A
    resolver (``resolve_ohlcv_window``), V2 can drop the legacy parquet via
    ``os.remove(old_path)`` in a one-shot cleanup pass. See V2 candidate
    banked in the M#1 R2 fix commit body.

    Per plan §H.6.3 + Codex R1 Major #6 + R1 Major #2 + R2 Minor #1 +
    R2 Major #1 + R3 Major #1 — handles 4 cases without data loss:

    1. **old-only:** `{TICKER}.parquet` exists, `{TICKER}.yfinance.parquet`
       absent → NORMALIZE legacy DatetimeIndex/capitalized shape to Shape A
       (asof_date column + lowercase OHLCV) via
       ``normalize_legacy_dataframe``, write to
       ``{TICKER}.yfinance.parquet``. **LEGACY FILE LEFT IN PLACE** (Codex
       R2 Major #1; both files coexist during V1 read-path co-existence).
       Codex R1 Major #2 fix: previously a bare ``os.replace`` would have
       left the post-rename file invisible to ``resolve_ohlcv_window``.
    2. **both-exist:** MERGE-PRESERVING-BOTH with **mtime-based freshness
       winner** (Codex R3 Major #1). Read both, normalize the legacy one
       first, then concat-dedupe on ``asof_date`` keyed on which file is
       fresher by ``Path.stat().st_mtime``:

         - If legacy ``{TICKER}.parquet`` mtime > Shape A mtime → legacy
           rows win on conflict (concat order ``[new_df, old_df]`` with
           ``keep='last'``). Closes the "yfinance corrections (e.g.,
           post-split adjustment) refreshed legacy but Shape A retains
           stale snapshot" window — legacy is the canonical archive under
           V1 copy-not-move, so a fresher legacy must propagate forward.
         - Otherwise (Shape A fresher or tied) → Shape A rows win on
           conflict (concat order ``[old_df, new_df]`` with
           ``keep='last'``). This was the pre-R3 default and remains the
           tie-breaker.

       Trade-off: mtime-based pick assumes the filesystem preserves mtime
       correctly. Edge cases like rsync/git checkout zeroing mtimes are
       banked as V2 candidate; in V1 copy-not-move mode the worst-case
       outcome of a wrong mtime read is "Shape A retains its own value"
       — the same posture we had before R3, never worse.
       **LEGACY FILE LEFT IN PLACE** (Codex R2 Major #1; quarantine/orphan
       step removed because both files coexist during V1).
    3. **new-only:** already migrated; no-op.
    4. **neither:** no historical data; no-op.

    Idempotent: invoking twice on the same ticker drives the post-state to
    case 2 (both-exist) on the second call, which merges the legacy file
    with the existing Shape A file (no-op if both already contain the same
    content) without losing rows.
    """
    cache_dir = Path(cache_dir)
    ticker_u = ticker.upper()
    old_path = cache_dir / f"{ticker_u}.parquet"
    new_path = cache_dir / f"{ticker_u}.yfinance.parquet"

    old_exists = old_path.exists()
    new_exists = new_path.exists()

    if old_exists and not new_exists:
        # Read + normalize + write to Shape A path. **LEGACY FILE LEFT IN PLACE**
        # (Codex R2 Major #1 copy-not-move) — read_or_fetch_archive still
        # consumes the legacy path under V1.
        old_df = pd.read_parquet(old_path)
        normalized = normalize_legacy_dataframe(old_df)
        _write_archive_atomic(new_path, normalized)
        return

    if old_exists and new_exists:
        # MERGE-PRESERVING-BOTH — preserve every row across both files.
        # Normalize legacy first. **LEGACY FILE LEFT IN PLACE** (Codex R2
        # Major #1 copy-not-move) — no quarantine/orphan; both files coexist.
        old_df = pd.read_parquet(old_path)
        new_df = pd.read_parquet(new_path)
        old_df = normalize_legacy_dataframe(old_df)
        new_df = normalize_legacy_dataframe(new_df)  # idempotent on Shape A

        # Codex R3 Major #1: mtime-based freshness winner. Under V1
        # copy-not-move, the legacy parquet may have been refreshed more
        # recently than Shape A (yfinance refresh post-split, etc.). In
        # that case legacy rows MUST win on `asof_date` conflicts —
        # otherwise Shape A retains stale values forever and yfinance
        # corrections never propagate into the resolver's read path.
        # `Path.stat().st_mtime` is the standard freshness signal; ties
        # fall through to Shape-A-wins (the pre-R3 default, preserved
        # as the tie-breaker for backward compatibility).
        #
        # V1 trade-off note (Codex R4 M#1 ACCEPT-WITH-RATIONALE):
        # File-level mtime is a coarse signal — it cannot distinguish
        # per-row freshness. Consequence: if legacy is touched by a
        # partial refresh, the file-level mtime check lets legacy win
        # for EVERY overlapping asof_date, including rows the refresh
        # did not touch (so Shape A's newer-of-truth values for those
        # rows get rolled back). This is the inverse failure of pre-R3
        # (Shape-A-always-wins → stale Shape A when legacy is refreshed).
        # Under V1, the impact is BOUNDED because:
        #   - read_or_fetch_archive consumers read legacy directly (so
        #     Shape A merge state does not affect their reads).
        #   - Shape A consumers (Sub-bundle C ladder + Phase 10 metrics
        #     if any) see a deterministic merge state that may diverge
        #     from per-row truth.
        # V2 resolves both directions by adding a per-row `recorded_at`
        # column to both archives; the merge then picks per-row winner
        # by `recorded_at` rather than file-level mtime. Tracked as V2
        # candidate in the Sub-bundle C return report (per-row
        # `recorded_at` column already banked from R3 M#1 review).
        #
        # Codex R4 Minor #2: use `_file_mtime_ns` (nanosecond precision
        # where the OS / filesystem supports it) so a real legacy
        # refresh that lands within the same wall-clock second as the
        # Shape A write still wins on conflict. Coarse-timestamp
        # filesystems (FAT32 / older NFS / post-rsync) fall back to
        # the float-mtime-times-1e9 approximation — V1 best-effort.
        try:
            old_mtime = _file_mtime_ns(old_path)
            new_mtime = _file_mtime_ns(new_path)
        except OSError:  # pragma: no cover — defensive
            old_mtime = 0
            new_mtime = 0
        if old_mtime > new_mtime:
            # Legacy fresher → legacy rows win on conflict.
            merged = pd.concat([new_df, old_df]).drop_duplicates(
                subset=["asof_date"], keep="last"
            )
        else:
            # Shape A fresher or tied → Shape A rows win on conflict.
            merged = pd.concat([old_df, new_df]).drop_duplicates(
                subset=["asof_date"], keep="last"
            )
        merged = merged.sort_values("asof_date").reset_index(drop=True)

        # Idempotency optimization: if the existing Shape A file already
        # contains every row that the merge produces (i.e. the legacy file's
        # asof_dates are a subset of the new file's), skip the rewrite to
        # preserve mtime + avoid spurious churn. Compare by content hash.
        try:
            existing_sorted = new_df.sort_values("asof_date").reset_index(drop=True)
            if existing_sorted.equals(merged):
                return
        except (ValueError, TypeError):  # pragma: no cover — defensive
            pass

        _write_archive_atomic(new_path, merged)
        return

    # Cases 3 + 4: new-only or neither — no-op.
    return
