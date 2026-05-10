"""Watchlist update — partitions today's evaluation into adds/requalifies/streak/removes.

Stable criteria gate watchlist membership (matching legacy STABLE_CRITERIA_NAMES).
Dynamic criteria are informational (populate `missing_criteria`).

Idempotency (spec §5.4): if a ticker's last_data_asof_date == today's data_asof_date,
streak/qualify operations are no-ops — re-running pipeline for the same session must
not double-count.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from swing.data.models import Candidate, WatchlistArchiveEntry, WatchlistEntry

# Names must match the criterion_name values produced by swing.evaluation.criteria.*
# Verified against Phase 1 modules: prior_trend.NAME, ma_stack_short.STACK_NAME/RISING_NAME,
# adr.NAME, pullback.NAME, orderliness.NAME, risk_feasibility.NAME,
# proximity.NAME (proximity_20ma), tightness.NAME, vcp.NAME (vcp_volume_contraction).
STABLE_CRITERION_NAMES: tuple[str, ...] = (
    "prior_trend",
    "ma_stack_10_20_50",
    "ma_short_rising",
    "adr",
    "pullback",
    "orderliness",
    "risk_feasibility",
)
DYNAMIC_CRITERION_NAMES: tuple[str, ...] = (
    "proximity_20ma",
    "tightness",
    "vcp_volume_contraction",
)
AGING_STREAK_THRESHOLD = 3


@dataclass(frozen=True)
class WatchlistDelta:
    adds: list[WatchlistEntry] = field(default_factory=list)
    requalifies: list[WatchlistEntry] = field(default_factory=list)
    streak_increments: list[WatchlistEntry] = field(default_factory=list)
    removes: list[WatchlistArchiveEntry] = field(default_factory=list)


def _stable_passes(c: Candidate) -> bool:
    by_name = {cr.criterion_name: cr.result for cr in c.criteria}
    return all(by_name.get(n) == "pass" for n in STABLE_CRITERION_NAMES)


def _missing_dynamic(c: Candidate) -> str | None:
    by_name = {cr.criterion_name: cr.result for cr in c.criteria}
    misses = [n for n in DYNAMIC_CRITERION_NAMES if by_name.get(n) != "pass"]
    return ";".join(misses) if misses else None


def compute_watchlist_changes(
    *, prior: Iterable[WatchlistEntry], today_candidates: Iterable[Candidate],
    data_asof_date: str,
) -> WatchlistDelta:
    prior_by_ticker = {e.ticker: e for e in prior}
    today_by_ticker = {c.ticker: c for c in today_candidates}
    delta = WatchlistDelta()
    all_tickers = set(prior_by_ticker) | set(today_by_ticker)

    for ticker in sorted(all_tickers):
        existing = prior_by_ticker.get(ticker)
        candidate = today_by_ticker.get(ticker)

        if candidate is None:
            continue

        qualifies = _stable_passes(candidate) and candidate.bucket in ("watch", "aplus")

        # Narrow idempotency guard (spec §5.4): a same-data_asof_date re-run with
        # the SAME outcome as the prior recording is a no-op. A re-run with a
        # DIFFERENT outcome (first fail → corrected qualify, or first qualify →
        # newly fail) legitimately flips the decision.
        # Prior outcome inferred from last_data_asof_date + not_qualified_streak:
        #   if last_data_asof_date == today AND streak == 0 → prior was qualify
        #   if last_data_asof_date == today AND streak  > 0 → prior was fail
        same_day_rerun = (
            existing is not None and existing.last_data_asof_date == data_asof_date
        )
        if same_day_rerun:
            prior_was_qualify = existing.not_qualified_streak == 0
            if prior_was_qualify == qualifies:
                continue  # same outcome today as already recorded — no-op

        if qualifies:
            if candidate.pivot is None or candidate.initial_stop is None:
                continue
            missing_dyn = _missing_dynamic(candidate)
            if existing is None:
                delta.adds.append(WatchlistEntry(
                    ticker=ticker, added_date=data_asof_date,
                    last_qualified_date=data_asof_date,
                    status=candidate.bucket if candidate.bucket in ("watch", "skip") else "watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date=data_asof_date,
                    entry_target=candidate.pivot,
                    initial_stop_target=candidate.initial_stop,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=missing_dyn, notes=None,
                ))
            else:
                delta.requalifies.append(WatchlistEntry(
                    ticker=ticker, added_date=existing.added_date,
                    last_qualified_date=data_asof_date,
                    status=existing.status,
                    qualification_count=existing.qualification_count + 1,
                    not_qualified_streak=0,
                    last_data_asof_date=data_asof_date,
                    entry_target=existing.entry_target,
                    initial_stop_target=existing.initial_stop_target,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=missing_dyn, notes=existing.notes,
                ))
        else:
            if existing is None:
                continue
            new_streak = existing.not_qualified_streak + 1
            if new_streak >= AGING_STREAK_THRESHOLD:
                delta.removes.append(WatchlistArchiveEntry(
                    id=None, ticker=ticker, added_date=existing.added_date,
                    removed_date=data_asof_date,
                    reason=f"aged out (failed stable {new_streak} consecutive runs)",
                    qualification_count=existing.qualification_count,
                    last_data_asof_date=data_asof_date,
                    notes=existing.notes,
                ))
            else:
                delta.streak_increments.append(WatchlistEntry(
                    ticker=ticker, added_date=existing.added_date,
                    last_qualified_date=existing.last_qualified_date,
                    status=existing.status,
                    qualification_count=existing.qualification_count,
                    not_qualified_streak=new_streak,
                    last_data_asof_date=data_asof_date,
                    entry_target=existing.entry_target,
                    initial_stop_target=existing.initial_stop_target,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=_missing_dynamic(candidate), notes=existing.notes,
                ))
    return delta
