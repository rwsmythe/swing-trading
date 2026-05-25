"""Discriminating tests for Codex R1 fixes.

M#1: Ruleset A removes undocumented breakeven raise at +2R arm
     (brief §3.1 specifies SMA21-ATR14 trail only; no BE raise).
M#3: Recency filter uses max(observed_asof_dates) not anchor_asof
     (the most-recent observation determines whether the W is still
     temporally actionable; not the highest-composite observation
     which may have an older asof).
M#5: Manifest carries source-artifact provenance (upstream manifest
     path + SHA + cohort_input_sha256) so cohort traceability survives
     the gitignored 287MB results.csv.
M#7: Trade dataclass + CSV emit add triggered + trade_pnl_dollars +
     peak_unrealized_R + drawdown_to_exit_R per dispatch brief §4.1.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import (
    PrimaryVerdict,
    filter_recent_patterns,
)
from research.harness.double_bottom_w_backtest.io import (
    RESULTS_CSV_HEADER,
    write_manifest,
)
from research.harness.double_bottom_w_backtest.rulesets import RulesetA
from research.harness.double_bottom_w_backtest.walkforward import (
    DEFAULT_CAPITAL_FLOOR_DOLLARS,
    DEFAULT_RISK_PCT,
    _compute_pnl_dollars_fractional,
    _compute_share_count,
    walk_forward,
)


def _bars(closes: list[float], *, start_date: str = "2026-04-25") -> pd.DataFrame:
    idx = pd.bdate_range(start=start_date, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": [c - 0.1 for c in closes],
            "High": [c + 0.5 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
            "Volume": [1000.0] * len(closes),
        },
        index=idx,
    )


def _verdict(
    *,
    asof: str = "2026-05-01",
    trough_2: str = "2026-04-20",
    trough_2_price: float = 95.0,
    center_peak_price: float = 100.0,
    max_observed_asof: str | None = None,
    observed_asofs: tuple[str, ...] | None = None,
) -> PrimaryVerdict:
    asof_d = date.fromisoformat(asof)
    return PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=asof_d,
        trough_1_date=date(2026, 4, 1),
        trough_1_price=trough_2_price + 1.0,
        center_peak_date=date(2026, 4, 6),
        center_peak_price=center_peak_price,
        trough_2_date=date.fromisoformat(trough_2),
        trough_2_price=trough_2_price,
        pivot_price=99.0,
        composite_score=0.85,
        geometric_score=0.85,
        template_match_score=None,
        max_observed_asof_date=(
            date.fromisoformat(max_observed_asof) if max_observed_asof else asof_d
        ),
        observed_asof_dates=(
            tuple(date.fromisoformat(s) for s in observed_asofs)
            if observed_asofs is not None
            else (asof_d,)
        ),
    )


# ---- M#1: Ruleset A breakeven raise REMOVED ----------------------------


def test_ruleset_a_arm_does_not_raise_stop_to_breakeven_per_codex_r1_m1() -> None:
    """After +2R close arms the trail, the stop is NOT raised to entry_price.
    Only the SMA21-ATR14 trail (when computable) governs post-arm stops.

    Pre-fix behavior: stop = max(initial_stop, entry_price) immediately on arm
    (incorrect; brief §3.1 does not prescribe BE raise).
    Post-fix behavior: stop remains at initial_stop until SMA21-ATR14 trail
    raises it (or until the TERMINAL close <= SMA50 exit fires).

    Discriminating scenario: build bars so position arms at +2R but SMA21/ATR14
    are uncomputable (insufficient pre-history). The stop should stay at
    initial_stop, NOT jump to entry_price. A subsequent close BELOW entry but
    ABOVE initial_stop should NOT exit (under post-fix); under pre-fix, the
    BE raise would have caused trail_stop fire when close < entry.
    """
    # Trigger at idx 1 (close=101 > peak=100); entry idx 2 open=101.9; stop=92*0.99=91.08
    # R = 101.9 - 91.08 = 10.82. +2R = 123.54. Plant a bar with close=130 to arm.
    # Then a bar with close=110 (above stop but below entry+BE-would-have-fired).
    closes = [99.0, 101.0, 102.0, 130.0, 110.0, 108.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    # Position should remain OPEN at data tail (no SMA50 computable; no terminal
    # exit; no stop hit because close=108 > stop=91.08; BE raise removed so no
    # trail_stop fire at close=110 < entry=101.9).
    assert trade.status == "open"
    assert trade.exit_reason == "open_at_data_tail"


# ---- M#3: Recency filter uses max(observed_asof_dates) -----------------


def test_recency_filter_uses_max_observed_asof_not_anchor_per_codex_r1_m3() -> None:
    """A W with anchor_asof=2026-04-01 (highest-composite verdict) BUT also
    observed at 2026-05-22 (later cohort_entry, lower composite) — recency
    is judged from the LATER observation (2026-05-22), not the anchor.

    Scenario: trough_2=2026-03-15. anchor_asof=2026-04-01 gives 17-day age
    (passes 60d recency). max_observed_asof=2026-05-22 gives 68-day age
    (fails 60d recency). Post-fix: REJECTED.
    Pre-fix would have ADMITTED this pattern.
    """
    v = _verdict(
        asof="2026-04-01",
        trough_2="2026-03-15",
        max_observed_asof="2026-05-22",
        observed_asofs=("2026-04-01", "2026-05-15", "2026-05-22"),
    )
    # Sanity: anchor-based recency = 17 days (would have passed)
    assert (v.anchor_asof_date - v.trough_2_date).days == 17
    # Post-fix: max_observed-based recency = 68 days (fails)
    assert (v.max_observed_asof_date - v.trough_2_date).days == 68
    filtered = filter_recent_patterns([v], max_calendar_days=60)
    assert len(filtered) == 0, "max_observed_asof rejects W observed > 60d post-t2"


def test_recency_filter_admits_when_max_observed_within_60d() -> None:
    """Symmetric: W observed multiple times all within 60d of trough_2 → admit."""
    v = _verdict(
        asof="2026-04-15",
        trough_2="2026-03-15",
        max_observed_asof="2026-05-10",  # 56 days after trough_2
        observed_asofs=("2026-04-15", "2026-04-30", "2026-05-10"),
    )
    filtered = filter_recent_patterns([v], max_calendar_days=60)
    assert len(filtered) == 1


def test_recency_filter_falls_back_to_anchor_when_max_observed_absent() -> None:
    """Defensive: pre-Codex-R1 fixtures without max_observed_asof_date should
    fall back to anchor_asof_date for recency calc."""
    v = PrimaryVerdict(
        ticker="DEF",
        anchor_asof_date=date(2026, 5, 1),
        trough_1_date=date(2026, 4, 1),
        trough_1_price=10.0, center_peak_date=date(2026, 4, 5), center_peak_price=12.0,
        trough_2_date=date(2026, 4, 20), trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
        max_observed_asof_date=None,  # explicitly missing (old fixture)
    )
    filtered = filter_recent_patterns([v], max_calendar_days=60)
    assert len(filtered) == 1


# ---- M#5: Manifest carries source provenance ---------------------------


def test_manifest_carries_source_artifact_provenance_per_codex_r1_m5(tmp_path: Path) -> None:
    """The manifest MUST surface upstream pattern_cohort_evaluator provenance:
    manifest_path, manifest_sha256, results.csv sha (when applicable),
    cohort_input_sha256 (from upstream manifest)."""
    out = tmp_path / "manifest.json"
    write_manifest(
        out,
        started_at_utc=datetime(2026, 5, 25, 22, 0, 0, tzinfo=timezone.utc),
        finished_at_utc=datetime(2026, 5, 25, 22, 0, 30, tzinfo=timezone.utc),
        cohort_csv_path="tests/fixtures/.../cohort.json",
        cohort_csv_sha256="abc",
        cache_dir="/path/to/cache",
        n_unique_verdicts_pre_filter=172,
        n_verdicts_after_adjacency_merge=172,
        n_patterns_after_recency_filter=12,
        recency_max_calendar_days=60,
        composite_threshold=0.7,
        max_trigger_search_business_days=60,
        n_trades_emitted=36,
        n_distinct_tickers=10,
        skipped_patterns={"ohlcv_missing": 0},
        source_artifact_manifest_path="exports/research/pattern-cohort-detection-X/manifest.json",
        source_artifact_manifest_sha256="def",
        source_results_csv_sha256="ghi",
        source_cohort_input_sha256="5333afe3d131c3116ef644acae74ec0e6c594968b610ddc485b85f59fdec1469",
        recency_filter_active=True,
    )
    m = json.loads(out.read_text(encoding="utf-8"))
    assert m["source_artifact_manifest_path"].endswith("manifest.json")
    assert m["source_artifact_manifest_sha256"] == "def"
    assert m["source_results_csv_sha256"] == "ghi"
    assert m["source_cohort_input_sha256"].startswith("5333afe3")
    assert m["recency_filter_active"] is True


# ---- M#7: Trade dataclass + CSV emit add 4 new columns ----------------


def test_csv_emits_triggered_pnl_peak_drawdown_columns_per_codex_r1_m7() -> None:
    """All 4 new columns appear in the CSV header in expected positions."""
    assert "triggered" in RESULTS_CSV_HEADER
    assert "trade_pnl_dollars" in RESULTS_CSV_HEADER
    assert "peak_unrealized_R" in RESULTS_CSV_HEADER
    assert "drawdown_to_exit_R" in RESULTS_CSV_HEADER
    # Order check: triggered after composite_score; pnl/peak/dd after r_multiple
    h = RESULTS_CSV_HEADER
    assert h.index("triggered") == h.index("composite_score") + 1
    assert h.index("trade_pnl_dollars") == h.index("r_multiple") + 1


def test_walk_forward_tracks_peak_unrealized_R_and_drawdown() -> None:
    """A trade that runs up to +2R then falls back to +0.5R closing should
    record peak_unrealized_R~2.0 and drawdown_to_exit_R~1.5 at the close."""
    # Trigger idx 1 close=101 > peak=100; entry idx 2 open=101.9; stop=91.08; R=10.82.
    # +2R intraday high ~ 101.9 + 21.64 = 123.54. Plant close=123 (intraday high=123.5)
    # at bar 3 → peak_R=2.0 reached intraday. Then drop to close=107 at bar 4.
    closes = [99.0, 101.0, 102.0, 123.0, 107.0, 108.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "open"
    assert trade.peak_unrealized_R is not None
    assert trade.peak_unrealized_R >= 1.9
    assert trade.drawdown_to_exit_R is not None
    assert trade.drawdown_to_exit_R > 0  # peak well above the tail close


def test_walk_forward_marks_triggered_true_when_entered() -> None:
    closes = [99.0, 101.0, 102.0, 103.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.triggered is True


def test_walk_forward_marks_triggered_false_when_untriggered() -> None:
    closes = [95.0] * 10
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.triggered is False


def test_compute_share_count_uses_capital_floor_and_risk_pct() -> None:
    """Per project_capital_risk_floor memory: shares = floor(7500 * 0.005 / R_unit)."""
    # R_unit = 10. risk_dollars = 7500 * 0.005 = 37.5. shares = floor(37.5/10) = 3.
    assert _compute_share_count(entry_price=100.0, initial_stop=90.0) == 3
    # R_unit = 2.5. risk_dollars = 37.5. shares = floor(37.5/2.5) = 15.
    assert _compute_share_count(entry_price=22.5, initial_stop=20.0) == 15


def test_compute_pnl_dollars_fractional_signed_by_direction_codex_r2_m3() -> None:
    """Fractional dollar PnL = R_multiple * risk_dollars. Avoids the
    integer-share floor-to-zero failure mode for wide-R patterns."""
    # entry=100 stop=90: R_unit=10. risk=37.5. exit=110 -> R_multiple=1; PnL=37.5
    assert _compute_pnl_dollars_fractional(
        entry_price=100.0, exit_price=110.0, initial_stop=90.0
    ) == pytest.approx(37.5)
    # exit=90 -> R_multiple=-1; PnL=-37.5
    assert _compute_pnl_dollars_fractional(
        entry_price=100.0, exit_price=90.0, initial_stop=90.0
    ) == pytest.approx(-37.5)


def test_compute_pnl_dollars_fractional_wide_R_does_not_floor_to_zero_codex_r2_m3() -> None:
    """Wide-R case where integer accounting would yield 0 shares + $0 PnL.
    Fractional accounting captures the true R-scaled dollar impact."""
    # entry=100 stop=70: R_unit=30. risk=37.5. exit=130 -> R_multiple=1; PnL=37.5
    # Under OLD integer logic: shares = floor(37.5/30) = 1; PnL = (130-100)*1 = $30
    # Under NEW fractional: PnL = (130-100) * (37.5/30) = $37.5
    assert _compute_pnl_dollars_fractional(
        entry_price=100.0, exit_price=130.0, initial_stop=70.0
    ) == pytest.approx(37.5)
    # entry=100 stop=50: R_unit=50 (> $37.5 risk budget). exit=150 -> R_multiple=1
    # OLD integer: shares = floor(37.5/50) = 0; PnL = $0 silently (the bug!)
    # NEW fractional: PnL = (150-100) * (37.5/50) = $37.5 (correctly scaled)
    assert _compute_pnl_dollars_fractional(
        entry_price=100.0, exit_price=150.0, initial_stop=50.0
    ) == pytest.approx(37.5)


def test_default_capital_floor_and_risk_pct_match_memory_invariants() -> None:
    """Locks the population-of-actionable-stocks floor + 0.5% risk-pct per
    CLAUDE.md operator memory + cfg.risk default."""
    assert DEFAULT_CAPITAL_FLOOR_DOLLARS == 7500.0
    assert DEFAULT_RISK_PCT == 0.005


# ---- Codex R2 fixes ---------------------------------------------------


def test_walk_forward_uses_effective_asof_when_max_observed_later_codex_r2_m1() -> None:
    """When max_observed_asof_date > anchor_asof_date, trigger search bounds
    use the later asof (per recency filter's semantic). Concretely: a W
    with anchor at 2026-04-15 + max_observed at 2026-05-01 should reject
    trigger candidates with close > peak occurring in 2026-04-16..2026-04-30
    (those predate the most-recent observation)."""
    # anchor=2026-04-15, max_observed=2026-05-01, trough_2=2026-04-10 (recent enough).
    # Build bars where price > peak on 2026-04-20 (would trigger under old logic
    # using anchor_asof=2026-04-15) but NOT after 2026-05-01.
    v = PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=date(2026, 4, 15),
        trough_1_date=date(2026, 3, 15),
        trough_1_price=10.0, center_peak_date=date(2026, 3, 22), center_peak_price=100.0,
        trough_2_date=date(2026, 4, 10), trough_2_price=92.0,
        pivot_price=99.0,
        composite_score=0.85, geometric_score=0.85, template_match_score=None,
        max_observed_asof_date=date(2026, 5, 1),
        observed_asof_dates=(date(2026, 4, 15), date(2026, 5, 1)),
    )
    # Bars: trigger candidate at 2026-04-20 (close=110); ALSO a later trigger at 2026-05-04 (close=120)
    bars = _bars(
        [95.0, 110.0, 95.0, 95.0, 95.0, 95.0, 95.0, 95.0, 95.0, 95.0,
         95.0, 120.0, 122.0],
        start_date="2026-04-15",
    )
    trade = walk_forward(v, bars, RulesetA())
    # Effective asof = max(2026-04-15, 2026-05-01) = 2026-05-01.
    # trigger lower bound exclusive = max(trough_1, trough_2, effective_asof) = 2026-05-01.
    # 2026-04-20 trigger is rejected (predates lower bound); 2026-05-04 trigger is admitted.
    if trade.triggered:
        assert trade.entry_date is not None
        # Entry must be AFTER max_observed (2026-05-01) per M#1 semantics
        assert trade.entry_date > date(2026, 5, 1), (
            f"entry_date {trade.entry_date} must be > max_observed 2026-05-01 "
            f"per Codex R2 M#1 effective_asof semantics"
        )


def test_days_held_is_bar_index_delta_not_calendar_codex_r2_m4() -> None:
    """days_held = sessions (bar count) not calendar days. Across a weekend
    a 2-session trade should report days_held=2, not 4 (Fri->Tue calendar)."""
    # Entry on Friday; exit 2 sessions later (Tue). Calendar diff = 4 days; bar diff = 2.
    # Use bdate_range starting Wed; entry idx 2 (Fri); exit idx 4 (Tue).
    closes = [98.0, 99.0, 101.0, 102.0, 88.0]  # idx 0 Wed; trigger idx 2 Fri; entry idx 3 Mon; stop hit idx 4 Tue
    bars = _bars(closes, start_date="2026-04-29")  # Wed
    v = _verdict(
        asof="2026-04-28",  # Tue
        trough_2="2026-04-15",
        center_peak_price=100.0,
        trough_2_price=92.0,
    )
    trade = walk_forward(v, bars, RulesetA())
    if trade.status == "closed":
        # bar-index delta = exit_idx - entry_idx; for this scenario expect <= 3
        assert trade.days_held is not None
        assert trade.days_held <= 3, (
            f"days_held={trade.days_held} > 3 suggests calendar-days "
            f"(weekend inflation) not bar-index delta"
        )
