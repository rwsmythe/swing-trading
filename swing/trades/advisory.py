"""Seven stop-advisory rules (legacy parity).

Each rule is pure: (Trade, AdvisoryContext) → AdvisorySuggestion | None.
Aggregator returns the non-None list, ordered for display.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from swing.config import StopAdvisoryConfig
from swing.data.models import Trade
from swing.trades.equity import r_so_far


@dataclass(frozen=True)
class AdvisoryContext:
    as_of_date: str
    current_price: float
    sma10: float | None
    sma20: float | None
    sma50: float | None                  # NEW (spec §3.3)
    previous_close: float | None         # NEW (drives exit_close_below_ma)
    weather_status: str
    config: StopAdvisoryConfig
    # 3e.8 Bundle 2 — ADR% of price over trailing ~20 bars (per
    # swing/evaluation/criteria/_base.py:adr_pct). Drives suggest_parabolic_trim
    # (§4.D). None when OHLCV unavailable / fewer than lookback bars — rule
    # silently no-ops.
    adr_pct: float | None = None
    # 3e.8 Bundle 2 — True iff the trade has at least one non-entry fill
    # (action != 'entry') recorded. Drives suggest_trim_into_strength (§4.B):
    # the rule suppresses itself after the first trim/exit, even if the
    # trade still meets the +1R trigger. Callers compute this from the same
    # fills they already query for remaining-shares math; default False so
    # legacy unit-test fixtures continue to fire the rule.
    has_been_trimmed: bool = False
    # 3e.8 Bundle 3 — Phase 8 daily-management maturity stage from the
    # trade's active daily_snapshot. Drives suggest_maturity_stage_trail_ma_hint
    # (§4.A.bis): operator-policy maturity-stage → recommended-trail-MA hint
    # per Tier-3 #6. Expected enum (None | "pre_+1.5R" | "+1.5R_to_+2R" |
    # ">=+2R_trail_eligible") matches ``compute_maturity_stage``. None when no
    # active snapshot exists (e.g., trade just opened pre-pipeline-run) → rule
    # no-ops; default None keeps legacy callers (test fixtures + pre-Bundle-3
    # composition sites) green.
    maturity_stage: str | None = None


@dataclass(frozen=True)
class AdvisorySuggestion:
    rule: str
    message: str


def suggest_breakeven(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    if r_so_far(trade, ctx.current_price) < ctx.config.breakeven_r_trigger:
        return None
    if trade.current_stop >= trade.entry_price:
        return None
    return AdvisorySuggestion(
        rule="breakeven",
        message=f"Move stop to breakeven (${trade.entry_price:.2f})",
    )


def suggest_trail_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str, buffer_pct: float,
) -> AdvisorySuggestion | None:
    if ma_value is None or ctx.current_price < ma_value:
        return None
    # Ceiling-round to the cent so the .2f-displayed target equals the actual
    # extinction threshold. Without this, displayed "$X.YZ" can represent a
    # threshold slightly above X.YZ and a user who sets their stop to the
    # displayed value sees the advisory persist (Bug 2).
    proposed = math.ceil(ma_value * (1 - buffer_pct / 100) * 100) / 100
    if proposed <= trade.current_stop:
        return None
    return AdvisorySuggestion(
        rule=f"trail_{ma_label.lower()}",
        message=f"Trail stop up to ${proposed:.2f} \u2014 {buffer_pct}% below {ma_label} (${ma_value:.2f})",
    )


def suggest_exit_close_below_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str,
) -> AdvisorySuggestion | None:
    """Minervini: "Sell on a close below the N-day MA." Fires when
    YESTERDAY'S DAILY CLOSE is below the MA — not on a live intraday tick.
    Spec §3.3."""
    if ma_value is None or ctx.previous_close is None:
        return None
    if ctx.previous_close >= ma_value:
        return None
    return AdvisorySuggestion(
        rule=f"exit_below_{ma_label.lower()}",
        message=f"EXIT \u2014 yesterday's close ${ctx.previous_close:.2f} "
                f"is below {ma_label} (${ma_value:.2f})",
    )


def suggest_weather_action(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    s = (ctx.weather_status or "").lower()
    if s.startswith("bearish"):
        return AdvisorySuggestion(
            rule="weather",
            message="Bearish weather \u2014 tighten stops or exit longs",
        )
    if s.startswith("caution"):
        return AdvisorySuggestion(
            rule="weather",
            message="Caution weather \u2014 tighten stops; consider half sizing",
        )
    return None


def suggest_time_stop(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    days_open = (date.fromisoformat(ctx.as_of_date) - date.fromisoformat(trade.entry_date)).days
    if days_open <= ctx.config.time_stop_days:
        return None
    if r_so_far(trade, ctx.current_price) >= ctx.config.time_stop_min_r:
        return None
    return AdvisorySuggestion(
        rule="time_stop",
        message=f"Time stop \u2014 {days_open} days open with only "
                f"+{r_so_far(trade, ctx.current_price):.2f}R; consider exit",
    )


def suggest_trim_into_strength(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """3e.8 Bundle 2 §4.B — sell-into-strength first-trim advisory.

    Fires when current R-multiple ≥ ``trim_first_r_trigger`` (default 1.0R)
    AND the trade has not yet been partially trimmed (no non-entry fills).
    Suppresses after first trim — caller stamps ``ctx.has_been_trimmed``
    from the same fills they already query for remaining-shares math.

    Operator-locked R-multiple trigger (brief §0.3 #1; DST D.2 calendar
    trigger banked for V2).
    """
    r = r_so_far(trade, ctx.current_price)
    if r < ctx.config.trim_first_r_trigger:
        return None
    if ctx.has_been_trimmed:
        return None
    pct = ctx.config.trim_first_pct_default
    return AdvisorySuggestion(
        rule="trim_into_strength",
        message=(
            f"Consider trimming {pct * 100:.0f}% of position — up "
            f"+{r:.2f}R; sell-into-strength discipline"
        ),
    )


def suggest_planned_target_r_hit(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """3e.8 Bundle 2 §4.K — planned-target-R-hit advisory.

    Fires when the trade has an operator-supplied ``planned_target_R``
    (Phase 8; nullable) AND current R-multiple ≥ that target. Silently
    no-ops for legacy / no-target trades (the NULL guard predates the
    R-comparison so ``None >= 1.0`` cannot raise).

    Continues firing every render until the trade closes or the target is
    revised — operator's reminder that the locked thesis target has been
    met.
    """
    target = trade.planned_target_R
    if target is None:
        return None
    r = r_so_far(trade, ctx.current_price)
    if r < target:
        return None
    return AdvisorySuggestion(
        rule="planned_target_r_hit",
        message=(
            f"Reached planned target +{target:.1f}R — consider trim "
            f"per sell-into-strength discipline"
        ),
    )


def suggest_parabolic_trim(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """3e.8 Bundle 2 §4.D — parabolic-extension advisory (DST D.7 / Realsimpleariel).

    Fires when current price has extended ≥ ``parabolic_adr_multiple`` ×
    ``adr_pct`` percent above the 50-day SMA. Silently no-ops when:

    - ADR% or 50SMA is unavailable (None);
    - ADR% / 50SMA / current_price is non-finite (NaN / inf), zero, or
      negative (Codex R1 Major #3 + R2 Major #2 — defends against
      corrupted OHLCV or zero-range/illiquid days);
    - price is at/below 50SMA (no parabolic extension exists below the
      anchor).

    Operator-locked DST D.7 doctrine anchor (brief §0.3 #2; 3e.8 arbitrary
    25%/5d/15% defaults rejected). V2 watch item: intraday-EMA reference
    (DST D.6) — V1 stays on daily-bar 50SMA.
    """
    if ctx.adr_pct is None or ctx.sma50 is None:
        return None
    # Codex R1 Major #3 + R2 Major #2 — defensive numeric guards. Cache
    # corruption / bad upstream OHLCV / zero-range (illiquid/holiday)
    # days could surface NaN/inf/zero/negative values; rule must no-op
    # rather than divide-by-zero or compute a nonsense threshold. R2
    # tightened adr_pct guard from `>= 0` to `> 0` — zero ADR makes
    # threshold zero and would otherwise fire for any close above sma50.
    if not math.isfinite(ctx.adr_pct) or ctx.adr_pct <= 0:
        return None
    if not math.isfinite(ctx.sma50) or ctx.sma50 <= 0:
        return None
    if not math.isfinite(ctx.current_price):
        return None
    if ctx.current_price <= ctx.sma50:
        return None
    extension_pct = (ctx.current_price - ctx.sma50) / ctx.sma50 * 100
    threshold = ctx.config.parabolic_adr_multiple * ctx.adr_pct
    if extension_pct < threshold:
        return None
    return AdvisorySuggestion(
        rule="parabolic_trim",
        message=(
            f"Parabolic extension — price ${ctx.current_price:.2f} is "
            f"≥{ctx.config.parabolic_adr_multiple:.1f}× ADR above "
            f"50SMA (ADR={ctx.adr_pct:.2f}%); consider aggressive trim per "
            f"DST D.7 / Realsimpleariel"
        ),
    )


# 3e.8 Bundle 3 §0.3 #2 — operator-policy maturity-stage → recommended-MA mapping.
# Frozen dict so a future maintainer cannot accidentally mutate it. Defensive
# pattern matches Bundle 2's `__post_init__` numeric guards: future enum values
# emitted by `compute_maturity_stage` (V2) yield no-op rather than KeyError.
_MATURITY_STAGE_TRAIL_MA: dict[str, str] = {
    "pre_+1.5R": "20MA",
    "+1.5R_to_+2R": "20MA",
    ">=+2R_trail_eligible": "10MA",
}


def suggest_maturity_stage_trail_ma_hint(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """3e.8 Bundle 3 §4.A.bis — maturity-stage → recommended-trail-MA hint.

    Operator-policy mapping per Tier-3 #6 (brief §0.3 #2):

    - ``pre_+1.5R``             → recommend trail at 20MA (default; trade
      has not yet proven itself)
    - ``+1.5R_to_+2R``          → recommend trail at 20MA (pending +2R
      promotion)
    - ``>=+2R_trail_eligible``  → recommend trail at 10MA (well-mature;
      tighter trail unlocked)

    Returns ``None`` when ``ctx.maturity_stage`` is ``None`` (no active
    daily_snapshot yet) OR when it falls outside the known enum (defensive
    against future ``compute_maturity_stage`` V2 additions; rule silently
    no-ops rather than raising KeyError).

    ADVISORY-MESSAGE-ONLY — does NOT suppress existing ``trail_10ma`` /
    ``trail_20ma`` advisories (brief §0.3 #1; investigation §4.A.bis line
    336). Operator reads both concurrently: existing rules answer "trail
    at the proposed level?", this rule answers "which MA is the right
    target?".

    NOT doctrine-faithful (brief §0.3 #3) — DST D.3 selects trail-MA by
    stock-strength/speed; the maturity-stage gating is a project/operator
    policy hybrid. V2 doctrine-faithful version requires a new schema
    field (``stock_speed_class`` at entry).
    """
    if ctx.maturity_stage is None:
        return None
    recommended_ma = _MATURITY_STAGE_TRAIL_MA.get(ctx.maturity_stage)
    if recommended_ma is None:
        return None
    return AdvisorySuggestion(
        rule="maturity_stage_trail_ma_hint",
        message=(
            f"Maturity stage {ctx.maturity_stage} — "
            f"recommended trail-MA: {recommended_ma}"
        ),
    )


def suggest_r_multiple_stop_tighten(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """3e.8 Bundle 3 §M.2 — R-multiple stop-tighten advisory.

    Fires when ``r_so_far(trade, ctx.current_price) >=
    ctx.config.tighten_at_r_multiple`` (default 2.0R; operator-tunable).
    Doctrine anchor: TLSMW Ch 13 p. 296 — "when a stock advances 7-8% off
    the buy point — the 20% scenario — the smart move is to lock in gains
    by raising the stop". The 7%/20% example ≈ 2.86R; default conservatively
    floored to 2.0R per brief §0.3 #4.

    Fires regardless of:

    - **current stop position** (still fires when current_stop is already
      at breakeven — second half of the message "tighten trail" remains
      actionable per brief §0.3 #4).
    - **maturity stage** (M.2 is cross-cutting on R-multiple per §5.1
      matrix; brief §0.3 #4).

    Does NOT suppress the existing ``breakeven`` advisory (which uses a
    different trigger — ``r_so_far >= 1.0R AND current_stop < entry_price``);
    they may both fire concurrently for trades crossing +2R with stop still
    below entry, which is the intended behavioral overlap (brief §0.3 #4).
    """
    # Codex R1 Major #1 — defensive numeric guard. ``r_so_far`` returns NaN
    # when ``ctx.current_price`` is NaN; ``nan < 2.0`` is False so a bare
    # comparison lets NaN sneak past + the rule emits "+nanR" output. Mirrors
    # the Bundle 2 ``suggest_parabolic_trim`` isfinite discipline.
    if not math.isfinite(ctx.current_price):
        return None
    r = r_so_far(trade, ctx.current_price)
    if not math.isfinite(r):
        return None
    if r < ctx.config.tighten_at_r_multiple:
        return None
    return AdvisorySuggestion(
        rule="r_multiple_stop_tighten",
        message=(
            f"At +{r:.2f}R (≥{ctx.config.tighten_at_r_multiple:.1f}× stop) — "
            f"Minervini M.2: consider moving stop to breakeven OR "
            f"tightening trail to lock in majority of gain"
        ),
    )


def compute_price_independent_suggestions(
    trade: Trade, ctx: AdvisoryContext,
) -> list[AdvisorySuggestion]:
    """Subset of advisory rules that do NOT consume ``ctx.current_price``.

    Used by composition layers when no live price snapshot is available
    (PriceCache degraded; OHLCV fetch failed; etc.) so DB-sourced advisories
    still fire. Currently V1: only §4.A.bis ``suggest_maturity_stage_trail_ma_hint``
    is price-independent. Future price-independent rules should be appended
    here.

    Codex R1 Major #2 closure (3e.8 Bundle 3): pre-fix, the 5 web/briefing
    composition sites gated ALL advisories on ``snap is not None``, which
    silently dropped §4.A.bis under PriceCache degradation. Per brief §0.3 #13
    + §5 Surface 1: the maturity hint must fire for every open trade with
    non-NULL maturity_stage regardless of price availability.

    Caller passes an ``AdvisoryContext`` constructed with a sentinel
    ``current_price`` (e.g., 0.0) — none of the rules called here read it.
    """
    sugs: list[AdvisorySuggestion | None] = []
    sugs.append(suggest_maturity_stage_trail_ma_hint(trade, ctx))
    return [s for s in sugs if s is not None]


def compute_all_suggestions(trade: Trade, ctx: AdvisoryContext) -> list[AdvisorySuggestion]:
    sugs: list[AdvisorySuggestion | None] = []
    sugs.append(suggest_breakeven(trade, ctx))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA",
                                  buffer_pct=ctx.config.trail_10ma_buffer_pct))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA",
                                  buffer_pct=ctx.config.trail_20ma_buffer_pct))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma50, ma_label="50MA"))  # NEW
    sugs.append(suggest_weather_action(trade, ctx))
    sugs.append(suggest_time_stop(trade, ctx))
    # 3e.8 Bundle 2 — three new sell-side advisories. Appended after existing
    # rules so display ordering remains stable across the 5-site composition
    # mirror (brief §3.3 watch item). Each rule no-ops when its preconditions
    # fail; the trailing `[s for s in sugs if s is not None]` strips inactive.
    sugs.append(suggest_trim_into_strength(trade, ctx))
    sugs.append(suggest_planned_target_r_hit(trade, ctx))
    sugs.append(suggest_parabolic_trim(trade, ctx))
    # 3e.8 Bundle 3 — two new advisory rules. Appended after Bundle 2's three
    # rules per brief §3.3 C.AC.1: positions 12 and 13 in the per-trade tuple.
    # Both fire independently; no suppression interactions (brief §0.3 #5).
    sugs.append(suggest_maturity_stage_trail_ma_hint(trade, ctx))
    sugs.append(suggest_r_multiple_stop_tighten(trade, ctx))
    return [s for s in sugs if s is not None]
