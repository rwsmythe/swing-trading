"""THE DASHBOARD SIZES OFF THE LIMIT IT DISPLAYS, NOT OFF THE PIVOT.

RD ruled the entry basis for sizing on 2026-07-30 -- the LIMIT, the worst price
the order can fill at, in both regimes -- and applied it to the two
`build_hyp_recs_expanded` sizing calls on 2026-08-04. The card already stated
the buy limit; it sized off the buy STOP, so the share count it recommended
breached the operator's own risk cap at the fill its own limit permits.

THE BASIS IS `buy_limit`, THE CARD'S OWN NUMBER, AND THAT CHOICE IS THE RULING
APPLIED RATHER THAN A PREFERENCE. `chase_factor` remains an operator-editable
knob, so `buy_limit` can sit above `mandate_buy_limit`; sizing off the mandate
while DISPLAYING the override would state a count that breaches the policy at
the price the card itself tells him to enter -- the very defect being removed,
relocated one field to the left. At the default chase factor (which is derived
from the latch zone cap, so it is the live value) the two are the same number.

THE WORKED CASE IS LIVE: AMN, evaluation run 131, session 2026-08-03 -- pivot
36.27, fire-time stop 30.85, sizing equity 7500.00 (the risk floor), 0.5% cap.
Pivot basis floor(37.50 / 5.42) = 6. Limit basis floor(37.50 / 6.50) = 5.
"""
from __future__ import annotations

import math
from dataclasses import replace

from swing.data.db import connect
from swing.latches.constants import mandate_limit_price, zone_cap_for_pivot
from swing.recommendations.build import BuildContext, build_recommendations

from tests.web.test_view_models.test_hyp_recs_expansion_vm import (
    _seed_complete_pipeline,
)

AMN_PIVOT = 36.27
AMN_STOP = 30.85
AMN_LIMIT = 37.35
RISK_FLOOR = 7500.0
RISK_BUDGET = 37.50          # 7500 * 0.005 -- the _minimal_config rate


def _expanded(cfg, ticker="AMN", *, balance=1200.0):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    conn = connect(cfg.paths.db_path)
    try:
        return build_hyp_recs_expanded(
            conn, cfg, ticker=ticker, current_balance=balance)
    finally:
        conn.close()


def _seed_amn(cfg, *, pivot=AMN_PIVOT, stop=AMN_STOP):
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": pivot, "initial_stop": stop},
    ])


def _render(vm):
    from swing.web.app import _build_templates, _templates_dir

    template = _build_templates(_templates_dir()).env.get_template(
        "partials/hypothesis_recommendations_expanded.html.j2")
    return template.render(expanded=vm, watchlist_entry=None)


# ---------------------------------------------------------------------------
# The change itself
# ---------------------------------------------------------------------------
def test_the_live_AMN_card_moves_from_SIX_shares_to_FIVE(seeded_db):
    """THE MERGE-BLOCKING DISCRIMINATOR, on the operator's own live geometry.

    PRE-FIX: floor(37.50 / (36.27 - 30.85)) = 6.
    POST-FIX: floor(37.50 / (37.35 - 30.85)) = 5.
    """
    cfg, _ = seeded_db
    _seed_amn(cfg)
    vm = _expanded(cfg)
    assert vm is not None
    assert vm.risk_equity == RISK_FLOOR
    assert vm.sizing_risk.shares == 5
    assert vm.sizing_risk.shares != math.floor(
        RISK_BUDGET / (AMN_PIVOT - AMN_STOP)), "6 is the pivot-basis count"
    assert vm.sizing_risk.risk_dollars == 5 * (AMN_LIMIT - AMN_STOP)
    assert vm.sizing_risk.notional == 5 * AMN_LIMIT


def test_the_recommended_size_stays_INSIDE_the_policy_at_a_CAP_FILL(seeded_db):
    """THE REASON. Six shares filled at the limit risk $39.00 = 0.520% against
    a 0.500% cap, and the pullback regime fills AT the cap."""
    cfg, _ = seeded_db
    _seed_amn(cfg)
    vm = _expanded(cfg)
    at_cap = vm.sizing_risk.shares * (vm.buy_limit - AMN_STOP)
    assert at_cap <= RISK_BUDGET
    assert 6 * (AMN_LIMIT - AMN_STOP) > RISK_BUDGET


def test_the_CASH_twin_moves_to_the_limit_basis_too(seeded_db):
    """THE SECOND CALL SITE (`dashboard.py:787`). A fix applied to the risk
    twin alone leaves the cash line stating a pivot-basis count on the same
    card -- the completeness lesson.

    At a $1,200 balance the $6.00 budget bought ONE share at the pivot-basis
    $5.42 risk-per-share and buys NONE at the $6.50 the order can actually
    fill at. That is the honest answer, not a regression: a single share of
    this setup breaches the cap at its own limit.
    """
    cfg, _ = seeded_db
    _seed_amn(cfg)
    vm = _expanded(cfg, balance=1200.0)
    assert vm.current_balance == 1200.0
    assert math.floor(1200.0 * 0.005 / (AMN_PIVOT - AMN_STOP)) == 1   # pre-fix
    assert vm.sizing_cash.shares == 0
    assert vm.sizing_cash.feasible is False


def test_the_card_SIZES_off_the_limit_it_DISPLAYS(seeded_db, monkeypatch):
    """IDENTITY, not agreement. The sized price must BE `buy_limit` -- the
    number the card renders -- not a second derivation that happens to equal
    it today (the item-6 drift class). Pinned by SUBSTITUTION: replacing the
    quantizer moves the displayed limit AND the share count together.

    limit 40.85 -> rps 10.00 -> floor(37.50 / 10.00) = 3, which no other basis
    in this builder produces (pivot -> 6, mandate -> 5).
    """
    import swing.web.view_models.dashboard as dash_mod

    cfg, _ = seeded_db
    _seed_amn(cfg)
    with monkeypatch.context() as m:
        m.setattr(dash_mod, "mandate_limit_price", lambda cap: 40.85)
        vm = _expanded(cfg)
        assert vm.buy_limit == 40.85
        assert vm.sizing_risk.shares == 3
        assert vm.sizing_risk.notional == 3 * 40.85


def test_an_OPERATOR_OVERRIDE_sizes_off_the_OVERRIDDEN_limit(seeded_db):
    """The knob still moves the card, and now it moves the SIZE with it --
    otherwise the count would breach the cap at the price the card states.

    chase_factor 0.10 -> cap 39.897 -> limit 39.89 -> rps 9.04 ->
    floor(37.50 / 9.04) = 4, distinct from the default basis's 5.
    """
    cfg, _ = seeded_db
    _seed_amn(cfg)
    over = replace(cfg, web=replace(cfg.web, chase_factor=0.10))
    vm = _expanded(over)
    assert vm.buy_limit == 39.89
    assert vm.mandate_buy_limit == AMN_LIMIT
    assert vm.chase_factor_diverges_from_mandate is True
    assert vm.sizing_risk.shares == 4
    assert vm.sizing_risk.shares != _expanded(cfg).sizing_risk.shares
    # ...and the count is inside the policy at the price the CARD states.
    assert vm.sizing_risk.shares * (vm.buy_limit - AMN_STOP) <= RISK_BUDGET


def test_the_rendered_sizing_line_MULTIPLIES_BY_THE_PRICE_IT_SIZED_OFF(
        seeded_db):
    """A RENDERED ARITHMETIC CONTRADICTION IS A DEFECT IN ITS OWN RIGHT.

    The sizing line reads `N sh x $PRICE = $NOTIONAL`. With the basis moved and
    the multiplicand left as the buy STOP the card would print
    `5 sh x $36.27 = $186.75`, which is simply false -- the D25 lesson is that a
    human gate only works if the numbers he can check actually check out.
    """
    cfg, _ = seeded_db
    _seed_amn(cfg)
    text = _render(_expanded(cfg))
    assert "5 sh × $37.35" in text
    assert "$186.75" in text
    assert "× $36.27" not in text, "the buy STOP is not the sizing basis"
    assert "Buy stop:  $36.27" in text, "the TRIGGER is still the pivot"


def test_the_dashboard_and_the_NIGHTLY_state_ONE_share_count(seeded_db):
    """THE POINT OF THE CHANGE, stated as an equality between the surfaces
    rather than as a value on either. Driven through the production nightly
    builder, not a re-derivation of it."""
    cfg, _ = seeded_db
    _seed_amn(cfg)
    card = _expanded(cfg)

    from swing.data.repos.candidates import fetch_candidates_for_run
    conn = connect(cfg.paths.db_path)
    try:
        eval_id = conn.execute(
            "SELECT evaluation_run_id FROM pipeline_runs "
            "WHERE state = 'complete' ORDER BY id DESC LIMIT 1").fetchone()[0]
        candidate = [
            c for c in fetch_candidates_for_run(conn, eval_id)
            if c.ticker == "AMN"
        ][0]
    finally:
        conn.close()
    # The pivot and stop come from the SAME row the card read; only the
    # display-only rationale fields (which the seed helper leaves NULL) are
    # filled in so the nightly builder can format its prose.
    candidate = replace(candidate, adr_pct=5.0, prior_trend_pct=30.0)
    nightly = build_recommendations(
        ctx=BuildContext(
            evaluation_run_id=eval_id, data_asof_date="2026-04-28",
            action_session_date="2026-04-29", current_equity=RISK_FLOOR,
            max_risk_pct=0.005, position_pct_cap=0.15),
        today_aplus=[candidate], prior_watchlist=[])[0]

    assert card.sizing_risk.shares == nightly.shares == 5


# ---------------------------------------------------------------------------
# The degenerate-geometry guard must not be LOOSENED by the wider basis
# ---------------------------------------------------------------------------
def test_a_stop_AT_OR_ABOVE_the_pivot_still_returns_None(seeded_db):
    """THE SILENT-LOOSENING GUARD. `compute_shares` refuses `stop >= entry`,
    and with entry = the pivot that doubled as the "stop below the trigger"
    sanity gate. Widening the entry to 103.00 lets a 101.50 stop through, and
    the card would render a setup whose stop sits ABOVE its own buy stop. The
    latch derivation carries the same invariant (`Latch.__post_init__`:
    stop < pivot < zone_cap).
    """
    cfg, _ = seeded_db
    assert 101.50 < mandate_limit_price(zone_cap_for_pivot(100.0))
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "DEGEN", "pivot": 100.0, "initial_stop": 101.50},
    ])
    assert _expanded(cfg, ticker="DEGEN") is None


def test_an_ORDINARY_geometry_still_renders(seeded_db):
    """The control on the guard: refusing degenerate input must not perturb a
    real setup."""
    cfg, _ = seeded_db
    _seed_amn(cfg)
    assert _expanded(cfg) is not None
