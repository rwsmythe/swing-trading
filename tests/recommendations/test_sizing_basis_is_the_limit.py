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


def test_the_action_text_CARRIES_THE_WHOLE_RISK_EQUATION():
    """CODEX R1 MAJOR, completed at R2. The row reports the TRIGGER in
    `entry_target` and the LIMIT-basis risk in `risk_dollars`, so a reader
    recomputing `shares x (entry_target - stop_target)` gets $27.10 against the
    stated $32.50.

    NAMING THE BASIS ALONE WAS NOT ENOUGH: neither the markdown briefing nor
    the HTML one renders `stop_target` for a decision, so the operator had no
    route to the figure at all. The line must carry every term.

    THE TEST PARSES THE LINE rather than asserting a canned string, so it
    cannot pass on a line whose numbers are internally inconsistent -- which is
    the whole property under test.
    """
    import re

    rec = _recs()[0]
    text = rec.action_text or ""
    m = re.search(
        r"(\d+) sh \S+ \$([0-9.]+) risk = (\d+) x \(\$([0-9.]+) cap "
        r"- \$([0-9.]+) stop\)", text)
    assert m is not None, text
    shares, risk, shares2, cap, stop = (
        int(m[1]), float(m[2]), int(m[3]), float(m[4]), float(m[5]))
    assert shares == shares2 == rec.shares == 5
    assert (cap, stop) == (AMN_LIMIT, AMN_STOP)
    # The line EVALUATES to the risk it states...
    assert shares * (cap - stop) == pytest.approx(risk)
    assert risk == pytest.approx(rec.risk_dollars, abs=0.005)
    # ...and the trigger price on the same line does NOT reproduce it, which is
    # exactly why the cap and the stop had to be printed.
    assert shares * (AMN_PIVOT - stop) != pytest.approx(risk)


def test_the_stated_risk_is_TWO_DECIMALS_so_the_equation_evaluates():
    """CODEX R2. At `.0f` the exact $32.50 printed as `$32` and the equation
    beside it evaluated to something else -- a self-checkable line that fails
    its own check is worse than one that never invited the check."""
    text = _recs()[0].action_text or ""
    assert "$32.50 risk" in text
    assert "$32 risk" not in text


def test_the_action_text_still_does_not_say_LIMIT():
    """THE TRANCHE-B CONTRACT SURVIVES THE DISCLOSURE. "Buy-stop limit" was
    retired because it implied a two-price BROKER ORDER this row never
    produces; naming the SIZING price must not reintroduce it."""
    for rec in _recs(prior_watchlist=[_watchlist("MSFT")]):
        assert "limit" not in (rec.action_text or "").lower()


def test_the_NEAR_TRIGGER_action_text_carries_the_equation_too():
    """Both `_format_action` call sites, per the completeness lesson."""
    recs = _recs(today_aplus=[],
                 prior_watchlist=[_watchlist(last_close=AMN_PIVOT)])
    text = recs[0].action_text or ""
    assert f"= 5 x (${AMN_LIMIT:.2f} cap - ${AMN_STOP:.2f} stop)" in text


def test_the_equation_is_TRUE_for_a_SUB_CENT_STOP():
    """CODEX R3 MAJOR, and it is LIVE DATA, not a hypothetical.

    `candidates.initial_stop` is a bare REAL with no cent-precision
    constraint: 1105 of the 11753 live candidate rows carry a sub-cent stop,
    and ADPT's 2026-08-04 recommendation is one of them (pivot 23.15, stop
    19.771). Printing that stop at 2dp inside the equation makes the equation
    FALSE -- 9 x (23.84 - 19.77) is $36.63 beside a stated $36.62.
    """
    import re

    rec = _recs(today_aplus=[_candidate("ADPT", pivot=23.15, stop=19.771)])[0]
    text = rec.action_text or ""
    assert "$19.7710 stop" in text, text
    assert "$19.77 stop" not in text
    m = re.search(
        r"\$([0-9.]+) risk = (\d+) x \(\$([0-9.]+) cap - \$([0-9.]+) stop\)",
        text)
    assert m is not None, text
    risk, shares, cap, stop = (
        float(m[1]), int(m[2]), float(m[3]), float(m[4]))
    assert (shares, cap) == (9, 23.84)
    # THE EQUATION EVALUATES TO THE STATED RISK -- which it does NOT at 2dp.
    assert round(shares * (cap - stop), 2) == risk
    assert round(shares * (cap - 19.77), 2) != risk


def test_a_CENT_EXACT_stop_still_prints_at_TWO_decimals():
    """The control on `_equation`: adding precision where it is needed must not
    add noise where it is not."""
    text = _recs()[0].action_text or ""
    assert f"${AMN_STOP:.2f} stop" in text
    assert f"${AMN_STOP:.4f} stop" not in text


def _parse_equation(text: str):
    """`(risk, shares, cap, stop)` off the action line, or None."""
    import re

    m = re.search(
        r"\$([0-9.]+) risk = (\d+) x \(\$([0-9.eE+-]+) cap "
        r"- \$([0-9.eE+-]+) stop\)", text)
    return None if m is None else (
        float(m[1]), int(m[2]), float(m[3]), float(m[4]))


@pytest.mark.parametrize("pivot,stop,why", [
    (36.27, 30.85, "AMN live -- cent-exact, needs 2dp"),
    (23.15, 19.771, "ADPT live -- 3dp stop, needs 4dp"),
    (0.5001, 0.500049, "R4: the position cap binds at 2205 sh, so a 4dp "
                       "stop states $22.05 against a $21.94 risk"),
    (0.5001, 0.5000499999, "one digit past the widest fixed precision"),
    (250.0, 249.0000001, "a large share-count amplifier on a tiny residual"),
])
def test_the_printed_equation_EVALUATES_at_every_reachable_precision(
        pivot, stop, why):
    """CODEX R4 MAJOR. A FIXED display precision cannot serve every stop,
    because the residual is MULTIPLIED BY THE SHARE COUNT: `_price`'s 4-decimal
    ceiling passed the ADPT case and still printed a false equation at
    0.5001 / 0.500049. `candidates.initial_stop` is a bare REAL with no
    precision constraint, so the precision must be DERIVED FROM THE CHECK.

    This is the PROPERTY, asserted over the geometries that break each
    candidate implementation in turn -- 2dp, 4dp, and the `repr` fallback.
    """
    recs = _recs(today_aplus=[_candidate("EQN", pivot=pivot, stop=stop)])
    rec = recs[0]
    if rec.shares == 0:
        pytest.skip("infeasible geometry states no equation")
    parsed = _parse_equation(rec.action_text or "")
    assert parsed is not None, rec.action_text
    risk, shares, cap, parsed_stop = parsed
    assert shares == rec.shares
    assert cap == mandate_limit_price(zone_cap_for_pivot(pivot))
    assert round(shares * (cap - parsed_stop), 2) == round(rec.risk_dollars, 2), (
        f"{why}: the printed equation does not evaluate to the printed risk")
    assert risk == round(rec.risk_dollars, 2)


def test_the_R4_geometry_needed_MORE_than_four_decimals():
    """The DISCRIMINATOR behind the property test above -- without it, a
    reviewer cannot tell whether the parametrised rows exercise anything the
    previous fixed-4dp implementation did not."""
    rec = _recs(today_aplus=[
        _candidate("EQN", pivot=0.5001, stop=0.500049)])[0]
    text = rec.action_text or ""
    assert rec.shares == 2205
    assert "$0.500049 stop" in text, text
    # The retired 4-decimal form printed this, and it is FALSE:
    assert round(2205 * (0.51 - 0.5000), 2) != round(rec.risk_dollars, 2)


def test_an_UNORDERABLE_geometry_is_INFEASIBLE_not_an_ABORT():
    """CODEX R3 MAJOR. The whole-cent floor can put the limit AT OR BELOW the
    stop for a sub-cent pivot -- cap 0.0093 floors to 0.00 -- and
    `compute_shares` then raises `stop >= entry`. Uncaught in this builder that
    exception aborts the WHOLE nightly step, so ONE such candidate would leave
    the operator with NO recommendations at all. The pivot basis accepted this
    geometry, and `candidates.pivot` carries no schema CHECK.

    The today_decision snapshot is specified to LIST infeasible names rather
    than drop them, so an unorderable row is emitted with zero shares.
    """
    assert mandate_limit_price(zone_cap_for_pivot(0.009)) <= 0.001
    recs = _recs(today_aplus=[_candidate("PENNY", pivot=0.009, stop=0.001),
                              _candidate()])
    by_ticker = {r.ticker: r for r in recs}
    assert by_ticker["PENNY"].shares == 0
    assert by_ticker["PENNY"].risk_dollars == 0.0
    assert "infeasible" in (by_ticker["PENNY"].action_text or "").lower()
    # ...and the REST OF THE BATCH still gets written, which is the point.
    assert by_ticker["AMN"].shares == 5


@pytest.mark.parametrize("pivot,why", [
    (float("inf"), "SQLite REAL stores infinity and no CHECK excludes it; the "
                   "pivot basis absorbed it as floor(budget / inf) = 0, so "
                   "this one is a REGRESSION the change introduced"),
    (1.79e308, "finite, but pivot x 1.03 OVERFLOWS to inf inside the cap -- "
               "the same regression"),
    (float("nan"), "NOT a regression: the pivot basis reached math.floor(nan) "
                   "and aborted too. Pinned anyway, because the ordering gate "
                   "is `stop >= pivot` rather than `not stop < pivot` "
                   "PRECISELY so nan falls through to the per-row refusal"),
])
def test_a_NON_FINITE_pivot_cannot_suppress_the_REST_of_the_batch(pivot, why):
    """CODEX R5 MAJOR -- the R3 class one step earlier.

    `zone_cap_for_pivot` refuses a non-finite or overflowing pivot with
    `ValueError`, and nothing caught it before `_step_recommendations` reached
    its write phase, so ONE such candidate lost the whole night.
    """
    recs = _recs(today_aplus=[_candidate("BAD", pivot=pivot, stop=30.85),
                              _candidate()])
    by_ticker = {r.ticker: r for r in recs}
    assert by_ticker["BAD"].shares == 0, why
    assert "infeasible" in (by_ticker["BAD"].action_text or "").lower()
    assert "$" not in (by_ticker["BAD"].action_text or "")
    # ...and the ordinary row is still written, which is the whole point.
    assert by_ticker["AMN"].shares == 5


def test_the_repr_FALLBACK_is_EXACT_when_the_precision_loop_runs_OUT():
    """CODEX R5 MINOR. `_equation`'s docstring calls the `repr` fallback the
    correctness guarantee, so the guarantee has to be EXECUTED -- every
    parametrised geometry above exits the loop at 2, 4 or 6 decimals, so none
    of them reached it.

    `repr` is the shortest decimal that ROUND-TRIPS a float, so the emitted
    operands parse back to the very floats the subtraction used and the
    equation reproduces the risk bit for bit. That is asserted here directly:
    the operands are compared to the ORIGINAL floats, not merely to each other.
    """
    from swing.recommendations.build import _equation

    basis, stop, shares = 0.02, 0.010000001, 500_000_050
    risk = shares * (basis - stop)
    # The widest FIXED precision the loop tries is not enough at this scale...
    assert round(shares * (float(f"{basis:.8f}") - float(f"{stop:.8f}")), 2) \
        != round(risk, 2)
    text = _equation(shares, basis, stop, risk)
    cap_text, stop_text = text.split("$")[1].split()[0], text.split("$")[2]
    stop_text = stop_text.split()[0]
    assert float(cap_text) == basis and float(stop_text) == stop
    assert round(shares * (float(cap_text) - float(stop_text)), 2) \
        == round(risk, 2)


def test_the_fallback_is_a_TOTALITY_guarantee_not_a_live_path():
    """...and the reachability is stated rather than left to a reader.

    Through the production builder the fallback CANNOT be reached at any
    realistic equity: the position cap bounds the share count at
    `floor(equity x 0.15 / basis)`, an 8-decimal operand carries at most 5e-9
    of residual each, and at the $7,500 sizing floor the widest possible count
    is 112,500 shares against the smallest orderable basis of $0.01 -- a
    maximum displacement of about a tenth of a cent, which cannot move the
    cent-rounded product. The branch is what makes `_equation` TOTAL; it is not
    a hot path, and a future reader must not mistake it for one.
    """
    from swing.latches.constants import mandate_limit_price

    smallest_orderable_basis = 0.01
    assert mandate_limit_price(0.0199) == smallest_orderable_basis
    widest_count = math.floor(
        SIZING_EQUITY * POSITION_PCT_CAP / smallest_orderable_basis)
    assert widest_count == 112_500
    assert widest_count * 2 * 5e-9 < 0.005


def test_the_unorderable_refusal_does_NOT_swallow_a_stop_ABOVE_the_pivot():
    """THE PAIRED DISCRIMINATOR. Degenerate DATA (a stop at or above the
    trigger) aborted the step before this change too and must stay LOUD; a
    blanket try/except around the sizing would pass the test above and silently
    ship a setup whose stop is above its own trigger."""
    with pytest.raises(ValueError):
        _recs(today_aplus=[_candidate("DEGEN", pivot=100.0, stop=101.5)])


def test_the_INFEASIBLE_action_text_states_no_price_at_all():
    """An infeasible row recommends nothing, so it states no price -- appending
    a cap to "Risk infeasible" would read as an order."""
    rec = _recs(today_aplus=[_candidate("WIDE", pivot=100.0, stop=50.0)])[0]
    assert rec.shares == 0
    assert "infeasible" in (rec.action_text or "").lower()
    assert "cap" not in (rec.action_text or "")
    assert "$" not in (rec.action_text or "")


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
