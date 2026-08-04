"""THE NIGHTLY SIZES OFF THE LIMIT, NOT THE PIVOT (RD 2026-07-30, applied to
the `build_recommendations` path by RD 2026-08-04).

The entry basis for position sizing is the LIMIT -- the worst price the order
can actually fill at -- in both regimes. The pivot is the TRIGGER, not the
fill: an order triggered at the pivot fills anywhere up to the buy-zone cap,
and in the pullback regime the cap is PRECISELY where it fills. Sizing off the
pivot therefore states a share count whose risk at an ordinary fill BREACHES
the operator's own policy cap, which is what the latch mandate already refused
to do and what this surface was still doing.

THE WORKED CASE IS LIVE, not illustrative: AMN, `daily_recommendations` id 153,
evaluation run 131, action session 2026-08-03 -- pivot 36.27, fire-time stop
30.85, sizing equity 7500.00 (the risk floor), max_risk_pct 0.005. The
persisted row says 6 shares. At the mandate limit 37.35 those 6 shares risk
$39.00 = 0.520% of the sizing equity, against a 0.500% cap. Five shares risk
$32.50 = 0.433%.

Every assertion below is computed under BOTH bases so it demonstrably
separates them -- the two differ by exactly one share on the live case, so a
loose assertion would catch nothing.
"""
from __future__ import annotations

import math

import pytest

from swing.data.models import Candidate, WatchlistEntry
from swing.latches.constants import mandate_limit_price, zone_cap_for_pivot
from swing.recommendations.build import BuildContext, build_recommendations

# --- the live AMN geometry, read off `daily_recommendations` id 153 --------
AMN_PIVOT = 36.27
AMN_STOP = 30.85
SIZING_EQUITY = 7500.0          # sizing_equity(real, risk_equity_floor=7500)
MAX_RISK_PCT = 0.005
POSITION_PCT_CAP = 0.15

AMN_LIMIT = 37.35               # mandate_limit_price(round(36.27*1.03, 4))
RISK_BUDGET = 37.50             # 7500 * 0.005


def _candidate(ticker="AMN", *, pivot=AMN_PIVOT, stop=AMN_STOP) -> Candidate:
    return Candidate(
        ticker=ticker, bucket="aplus", close=pivot - 0.5, pivot=pivot,
        initial_stop=stop, adr_pct=5.0, tight_streak=3, pullback_pct=10.0,
        prior_trend_pct=30.0, rs_rank=85, rs_return_12w_vs_spy=0.20,
        rs_method="universe", pattern_tag=None, notes=None, criteria=(),
    )


def _watchlist(ticker="AMN", *, target=AMN_PIVOT, stop=AMN_STOP,
               last_close=AMN_PIVOT) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-07-20", last_qualified_date="2026-07-31",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-07-31", entry_target=target,
        initial_stop_target=stop, last_close=last_close, last_pivot=target,
        last_stop=stop, last_adr_pct=5.0, missing_criteria=None, notes=None,
    )


def _ctx(*, equity=SIZING_EQUITY) -> BuildContext:
    return BuildContext(
        evaluation_run_id=131, data_asof_date="2026-07-31",
        action_session_date="2026-08-03", current_equity=equity,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )


def _recs(**over):
    return build_recommendations(
        ctx=over.pop("ctx", _ctx()),
        today_aplus=over.pop("today_aplus", [_candidate()]),
        prior_watchlist=over.pop("prior_watchlist", []))


# ---------------------------------------------------------------------------
# The premise, asserted inline so the file's reason cannot rot
# ---------------------------------------------------------------------------
def test_the_premise_the_two_bases_differ_by_exactly_one_share_here():
    """THE DISCRIMINATOR'S OWN PROOF. Every value test below is worthless
    unless the live geometry actually separates the bases, so the separation is
    derived here rather than assumed."""
    assert mandate_limit_price(zone_cap_for_pivot(AMN_PIVOT)) == AMN_LIMIT
    assert SIZING_EQUITY * MAX_RISK_PCT == RISK_BUDGET

    pivot_basis = math.floor(RISK_BUDGET / (AMN_PIVOT - AMN_STOP))
    limit_basis = math.floor(RISK_BUDGET / (AMN_LIMIT - AMN_STOP))
    assert (pivot_basis, limit_basis) == (6, 5)

    # ...and the position cap does not bind on either, so the risk leg is what
    # the assertions are actually measuring.
    assert math.floor(SIZING_EQUITY * POSITION_PCT_CAP / AMN_PIVOT) > pivot_basis
    assert math.floor(SIZING_EQUITY * POSITION_PCT_CAP / AMN_LIMIT) > limit_basis


# ---------------------------------------------------------------------------
# The change itself
# ---------------------------------------------------------------------------
def test_the_live_AMN_recommendation_moves_from_SIX_shares_to_FIVE():
    """THE MERGE-BLOCKING DISCRIMINATOR, on the operator's own persisted row.

    PRE-FIX: 6 shares off the pivot -- the number in `daily_recommendations`
    id 153 today.
    POST-FIX: 5 shares off the mandate limit 37.35.
    """
    rec = _recs()[0]
    assert rec.ticker == "AMN"
    assert rec.recommendation == "today_decision"
    assert rec.shares == 5
    assert rec.shares != 6, "6 is the pivot-basis count this fix removes"


def test_the_recommended_size_stays_INSIDE_the_policy_at_a_CAP_FILL():
    """THE REASON, stated as the property rather than as a number.

    The pivot-basis count breaches the operator's own 0.5% cap at an ordinary
    fill -- 6 x $6.50 = $39.00 = 0.520% -- and the pullback regime fills AT the
    cap, so that is not a tail event.
    """
    rec = _recs()[0]
    risk_at_a_cap_fill = rec.shares * (AMN_LIMIT - AMN_STOP)
    assert risk_at_a_cap_fill <= RISK_BUDGET
    assert risk_at_a_cap_fill / SIZING_EQUITY <= MAX_RISK_PCT
    # The count this replaces does NOT satisfy either line above.
    assert 6 * (AMN_LIMIT - AMN_STOP) > RISK_BUDGET


def test_the_persisted_risk_figures_are_the_LIMIT_basis_ones():
    """`risk_dollars` / `risk_pct` travel with the basis or the row states a
    risk it did not size to. Pivot basis persisted $32.52 / 0.4336%."""
    rec = _recs()[0]
    assert rec.risk_dollars == pytest.approx(5 * (AMN_LIMIT - AMN_STOP))
    assert rec.risk_dollars == pytest.approx(32.50)
    assert rec.risk_pct == pytest.approx(32.50 / SIZING_EQUITY * 100)
    assert rec.risk_dollars != pytest.approx(32.52)


def test_the_TRIGGER_price_stays_the_PIVOT():
    """SCOPE PIN. Only the sizing BASIS moved. `entry_target` is the buy-stop
    trigger, not the fill, and a change there would silently redefine what the
    nightly is telling the operator to place."""
    rec = _recs()[0]
    assert rec.entry_target == AMN_PIVOT
    assert rec.stop_target == AMN_STOP
    assert f"Buy-stop ${AMN_PIVOT:.2f}" in (rec.action_text or "")


def test_the_action_text_NAMES_the_basis_so_the_stated_risk_RECOMPUTES():
    """CODEX R1 MAJOR. The row reports the TRIGGER in `entry_target` and the
    LIMIT-basis risk in `risk_dollars`, so a reader recomputing
    `shares x (entry_target - stop_target)` gets $27.10 against the stated
    $32.50. Without the basis on the line the row is not self-checkable -- the
    same rendered-arithmetic defect the dashboard's sizing line had.
    """
    rec = _recs()[0]
    text = rec.action_text or ""
    assert f"${AMN_LIMIT:.2f} buy-zone cap" in text
    # The stated risk RECOMPUTES from the numbers on the line...
    assert round(rec.shares * (AMN_LIMIT - AMN_STOP)) == round(rec.risk_dollars)
    # ...and does NOT from the trigger, which is exactly why it is named.
    assert round(rec.shares * (AMN_PIVOT - AMN_STOP)) != round(rec.risk_dollars)


def test_the_action_text_still_does_not_say_LIMIT():
    """THE TRANCHE-B CONTRACT SURVIVES THE DISCLOSURE. "Buy-stop limit" was
    retired because it implied a two-price BROKER ORDER this row never
    produces; naming the SIZING price must not reintroduce it."""
    for rec in _recs(prior_watchlist=[_watchlist("MSFT")]):
        assert "limit" not in (rec.action_text or "").lower()


def test_the_NEAR_TRIGGER_action_text_names_its_basis_too():
    """Both `_format_action` call sites, per the completeness lesson."""
    recs = _recs(today_aplus=[],
                 prior_watchlist=[_watchlist(last_close=AMN_PIVOT)])
    assert f"${AMN_LIMIT:.2f} buy-zone cap" in (recs[0].action_text or "")


def test_the_INFEASIBLE_action_text_names_no_basis():
    """An infeasible row recommends nothing, so it states no price at all --
    appending a cap to "Risk infeasible" would read as an order."""
    rec = _recs(today_aplus=[_candidate("WIDE", pivot=100.0, stop=50.0)])[0]
    assert rec.shares == 0
    assert "infeasible" in (rec.action_text or "").lower()
    assert "buy-zone cap" not in (rec.action_text or "")


def test_the_NEAR_TRIGGER_path_sizes_off_the_limit_TOO():
    """THE SECOND CALL SITE. `build_recommendations` sizes twice -- A+ names and
    near-trigger watchlist rows -- and a fix applied to one leaves the other
    stating a pivot-basis count for the same geometry."""
    recs = _recs(today_aplus=[],
                 prior_watchlist=[_watchlist(last_close=AMN_PIVOT)])
    near = [r for r in recs if r.recommendation == "near_trigger"]
    assert len(near) == 1
    assert near[0].shares == 5
    assert near[0].shares != 6
    assert near[0].entry_target == AMN_PIVOT


# ---------------------------------------------------------------------------
# The basis is OBTAINED from the shared authorities, not re-derived
# ---------------------------------------------------------------------------
def test_the_builder_actually_INVOKES_both_shared_functions(monkeypatch):
    """A BINDING IS NOT A CALL (the in-tree precedent:
    tests/web/test_view_models/test_chase_factor_single_source.py). A local
    `pivot * 1.03` would agree with the helpers today and drift on the next
    edit -- the item-6 class. Pinned by SUBSTITUTION.
    """
    import swing.recommendations.build as build_mod

    with monkeypatch.context() as m:
        # A cap whose mandate limit gives an exactly-computable count:
        # rps = 33.85 - 30.85 = 3.00 -> floor(37.50 / 3.00) = 12.
        m.setattr(build_mod, "zone_cap_for_pivot", lambda *a, **k: 33.8500)
        assert _recs()[0].shares == 12
    with monkeypatch.context() as m:
        # rps = 34.85 - 30.85 = 4.00 -> floor(37.50 / 4.00) = 9.
        m.setattr(build_mod, "mandate_limit_price", lambda cap: 34.85)
        assert _recs()[0].shares == 9


def test_the_basis_is_the_WHOLE_CENT_ORDERABLE_price_not_the_raw_cap():
    """THE CONTROL on the quantization, and it needs `risk_dollars` to bite.

    AMN's cap is 37.3581. All three candidate bases -- the raw cap, its
    half-up rounding 37.36 and the mandate's floor 37.35 -- yield the SAME
    5 shares, so the share count cannot discriminate them. `risk_dollars`
    can: 5 x 6.5081 = 32.5405 off the raw cap against 5 x 6.50 = 32.50 off
    the orderable price. The operator can only ever place a whole-cent limit,
    so the risk the row states must be the risk at a price that exists.
    """
    raw_cap = zone_cap_for_pivot(AMN_PIVOT)
    assert raw_cap == 37.3581
    assert round(raw_cap, 2) == 37.36            # half-up EXCEEDS the cap
    rec = _recs()[0]
    assert rec.shares == 5
    assert rec.risk_dollars == pytest.approx(5 * (AMN_LIMIT - AMN_STOP))
    assert rec.risk_dollars != pytest.approx(5 * (raw_cap - AMN_STOP))
    assert rec.risk_dollars != pytest.approx(5 * (round(raw_cap, 2) - AMN_STOP))


# ---------------------------------------------------------------------------
# The degenerate-geometry guard must not be LOOSENED by the wider basis
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stop", [100.0, 101.5, 102.99])
def test_a_stop_AT_OR_ABOVE_the_pivot_is_still_REFUSED(stop):
    """THE SILENT-LOOSENING GUARD.

    `compute_shares` refuses `stop >= entry`, and with entry = the pivot that
    doubled as the "the stop must sit below the trigger" sanity gate. Widening
    the entry to the limit (100.00 -> 103.00) would let a stop ABOVE the pivot
    pass, shipping a recommendation whose stop is above its own trigger. The
    latch derivation carries the same invariant (`Latch.__post_init__`:
    stop < pivot < zone_cap), so this preserves it rather than inventing it.

    All three stops are BELOW the post-fix limit 103.00 and AT-OR-ABOVE the
    pivot 100.00 -- i.e. each one passes an unguarded post-fix builder.
    """
    assert stop >= 100.0
    assert stop < mandate_limit_price(zone_cap_for_pivot(100.0))
    with pytest.raises(ValueError):
        _recs(today_aplus=[_candidate("DEGEN", pivot=100.0, stop=stop)])


def test_the_same_refusal_holds_on_the_NEAR_TRIGGER_path():
    """Both call sites, per the completeness lesson."""
    with pytest.raises(ValueError):
        _recs(today_aplus=[],
              prior_watchlist=[_watchlist("DEGEN", target=100.0, stop=101.5,
                                          last_close=100.0)])


def test_an_ORDINARY_geometry_is_untouched_by_the_guard():
    """The control: refusing degenerate input must not perturb a real setup."""
    assert _recs()[0].shares == 5
