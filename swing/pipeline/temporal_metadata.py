"""Pure-bars per-pattern metadata helpers (Phase 14 Sub-bundle 2, spec section 9).

No I/O: every function consumes an already-fetched ``bars`` DataFrame (the
detect loop's existing fetch) sliced to ``<= data_asof_date``. Short-history
inputs return ``None`` for the field (never raise) so a thin-history ticker
never poisons the metadata emit. L2 LOCK: no fetch, no Schwab.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date

import pandas as pd

from swing.data.ohlcv_finiteness import is_finite_ohlc


def _usable(bars: pd.DataFrame, *, need: tuple[str, ...]) -> bool:
    """True only if bars is a non-empty frame carrying the needed columns.

    Guards the empty-frame path (Codex chain #1 R2 Major #1): the detect loop
    may pass an empty DataFrame when bars are unexpectedly absent for an
    emitted verdict; the helpers then return None rather than KeyError.
    """
    return (
        bars is not None and not bars.empty
        and all(c in bars.columns for c in need)
    )


def _slice_to_asof(bars: pd.DataFrame, asof: str) -> pd.DataFrame:
    """Drop any bar dated AFTER asof (strips the yfinance in-progress partial
    bar per the CLAUDE.md gotcha). asof is an ISO date string."""
    asof_d = date.fromisoformat(asof)
    return bars[bars.index.map(lambda ts: ts.date() <= asof_d)]


def _squeeze(col):
    """Squeeze a yfinance group_by='column' MultiIndex single-ticker column
    (a one-column DataFrame, ndim==2) down to a Series. Pass-through for an
    already-1D Series. Used by every helper that reads High/Low/Close so a
    single-ticker MultiIndex frame never makes float(col.iloc[-1]) raise."""
    return col.iloc[:, 0] if getattr(col, "ndim", 1) == 2 else col


def _close_series(bars: pd.DataFrame) -> pd.Series:
    return _squeeze(bars["Close"])


def compute_atr_pct(bars: pd.DataFrame, *, asof: str, period: int = 14) -> float | None:
    """True ATR(period) / last_close * 100 (distinct from candidates.adr_pct)."""
    if not _usable(bars, need=("High", "Low", "Close")):
        return None
    df = _slice_to_asof(bars, asof)
    if len(df) < period + 1:
        return None
    high = _squeeze(df["High"])
    low = _squeeze(df["Low"])
    close = _squeeze(df["Close"])
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.tail(period).mean()
    last_close = float(close.iloc[-1])
    if last_close <= 0:
        return None
    return float(atr / last_close * 100.0)


def compute_return_pct(
    bars: pd.DataFrame, *, asof: str, lookback_sessions: int,
) -> float | None:
    """(close_today - close_N_sessions_ago) / close_N_sessions_ago * 100."""
    if not _usable(bars, need=("Close",)):
        return None
    close = _close_series(_slice_to_asof(bars, asof))
    if len(close) < lookback_sessions + 1:
        return None
    now = float(close.iloc[-1])
    then = float(close.iloc[-(lookback_sessions + 1)])
    if then <= 0:
        return None
    return float((now - then) / then * 100.0)


def compute_52w_high_proximity_pct(bars: pd.DataFrame, *, asof: str) -> float | None:
    """(high_52w - close_today) / high_52w * 100 over the last 252 sessions
    (reuses the trend_template.py TT7 formula). Lower = closer to the high."""
    if not _usable(bars, need=("Close",)):
        return None
    close = _close_series(_slice_to_asof(bars, asof))
    if len(close) < 1:
        return None
    window = close.iloc[-252:]
    high_52w = float(window.max())
    if high_52w <= 0:
        return None
    now = float(close.iloc[-1])
    return float((high_52w - now) / high_52w * 100.0)


def build_per_pattern_metadata(candidate, bars: pd.DataFrame, *, asof: str) -> str:
    """Serialize per-pattern metadata JSON (spec section 9.2). market_cap is
    NULL in V1+ (OQ-16: not persisted to candidates)."""
    return json.dumps({
        "sector": candidate.sector,
        "industry": candidate.industry,
        "adr_pct": candidate.adr_pct,
        "atr_pct": compute_atr_pct(bars, asof=asof),
        "ret_90d": compute_return_pct(bars, asof=asof, lookback_sessions=90),
        "prox_52w_high_pct": compute_52w_high_proximity_pct(bars, asof=asof),
        "rs_rank": candidate.rs_rank,
        "close_at_detection": candidate.close,
        "market_cap": None,
    })


def build_finviz_screen_state(candidate) -> str:
    """Canonicalized per-ticker eval/screen state (spec section 9.4). The
    per-criterion value is CriterionResult.result (the verdict string)."""
    return json.dumps({
        "bucket": candidate.bucket,
        "rs_rank": candidate.rs_rank,
        "rs_method": candidate.rs_method,
        "criteria": {cr.criterion_name: cr.result for cr in candidate.criteria},
    })


def build_structural_anchors_json(window, evidence) -> str:
    """{window: {...}, evidence: asdict(evidence)} (spec section 6.3). The
    evidence asdict losslessly contains every per-class structural anchor."""
    return json.dumps({
        "window": {
            "start_date": window.start_date.isoformat(),
            "end_date": window.end_date.isoformat(),
            "anchor_date": getattr(window, "anchor_date", None).isoformat()
                if getattr(window, "anchor_date", None) is not None else None,
            "anchor_reason": getattr(window, "anchor_reason", None),
        },
        "evidence": dataclasses.asdict(evidence),
    }, default=str)


_OHLC_TODAY_PROVIDERS = ("schwab_api", "yfinance")
_OHLC_TODAY_KEYS = ("open", "high", "low", "close", "volume", "provider")


def build_ohlc_today_json(
    bar: dict, *, observation_date: str, cutoff: date,
) -> str:
    """Validated serializer for ohlc_today_json. Construction-barrier guard:
    refuses to serialize a bar for a non-completed session (date-only; L3) so
    no partial/in-progress bar enters the append-only log. Then validates the
    key set + provider domain as before (Codex chain #2 Major #6 -- the
    substrate's provider provenance is guaranteed, not convention).

    Phase 18 18-A: also refuses a non-finite OHLC bar (shared is_finite_ohlc;
    Volume exempt) -- a belt-and-suspenders construction barrier; the shipped
    skip-with-warning happens at the caller, which pre-checks before serializing."""
    if date.fromisoformat(observation_date) > cutoff:
        raise ValueError(
            f"ohlc_today_json: refusing to lock a non-completed-session bar "
            f"({observation_date} > {cutoff.isoformat()})"
        )
    missing = [k for k in _OHLC_TODAY_KEYS if k not in bar]
    if missing:
        raise ValueError(f"ohlc_today_json missing keys: {missing}")
    if bar["provider"] not in _OHLC_TODAY_PROVIDERS:
        raise ValueError(
            f"ohlc_today_json provider must be one of {_OHLC_TODAY_PROVIDERS}, "
            f"got {bar['provider']!r}"
        )
    # Phase 18 Arc 18-A -- finiteness construction-barrier (belt-and-suspenders).
    # Mirrors the Arc-8 trailing-ragged barrier at this SECOND write path via the
    # ONE shared predicate (C1). Volume is EXEMPT (not passed) -- Arc-8: legit
    # volume-less bars exist; validate_bars likewise ignores volume. SHIPPED
    # behavior is skip-with-warning at the caller (_step_pattern_observe), which
    # pre-checks and skips BEFORE reaching this serializer; this raise is the
    # suspenders that fail LOUD if a FUTURE write path forgets the pre-check,
    # rather than silently locking a NaN into the immutable, append-only log
    # (the #26 anti-drift guarantee). LOCK 1/2: validate_bars untouched; the
    # session/key/provider guards preserved (finiteness ADDED, nothing removed).
    if not is_finite_ohlc(bar["open"], bar["high"], bar["low"], bar["close"]):
        raise ValueError(
            f"ohlc_today_json: refusing to lock a non-finite OHLC bar "
            f"(open={bar['open']!r}, high={bar['high']!r}, "
            f"low={bar['low']!r}, close={bar['close']!r})"
        )
    return json.dumps({k: bar[k] for k in _OHLC_TODAY_KEYS})
