"""THE DASHBOARD'S BUY LIMIT AND THE LATCH'S ZONE CAP ARE ONE SOURCE.

The operator RETIRED his 2026-04-25 pure-trigger discipline ("wait for pivot,
do not chase >1% above pivot") on 2026-08-03, knowing it is a loosening. What
replaces it is not a second number: the dashboard's `buy_limit` is now the price
`mandate_limit_price` would emit for that pivot at the latch's own zone cap, so
the two surfaces cannot state different entry limits for the same setup.

CHARC's constraint on the fix SHAPE: "a second constant that happens to equal
the first is the item-6 drift class." So there is no `0.03` literal anywhere in
the chain -- `LATCH_ZONE_CAP_PCT` is the one authority, `zone_cap_for_pivot` is
the one arithmetic, `mandate_limit_price` is the one quantization, and
`Web.chase_factor`'s default plus the FIELD_REGISTRY mirror are DERIVED from it.

The discriminating geometry is the witnessed one: pivot 36.27 -> cap 37.3581,
whose third decimal is >= 5, so round-half-up (37.36) and the mandate's floor
(37.35) disagree. Pivot 18.34 -> cap 18.8902 is the control: it rounds DOWN, so
a "subtract a cent" implementation passes every assertion on the first and fails
the second.
"""
from __future__ import annotations

from dataclasses import replace

from swing.config import Web
from swing.config_validation import FIELD_REGISTRY, get_spec, validate_field
from swing.data.db import connect
from swing.latches.constants import (
    LATCH_ZONE_CAP_PCT,
    mandate_limit_price,
    zone_cap_for_pivot,
)

from tests.web.test_view_models.test_hyp_recs_expansion_vm import (
    _seed_complete_pipeline,
)

WITNESSED_PIVOT = 36.27          # AMN, 2026-08-03
CONTROL_PIVOT = 18.34            # FTRE


def _expanded(cfg, ticker="AMN"):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    conn = connect(cfg.paths.db_path)
    try:
        return build_hyp_recs_expanded(
            conn, cfg, ticker=ticker, current_balance=10_000.0)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The single source itself
# ---------------------------------------------------------------------------
def test_the_premise_the_witnessed_cap_actually_exhibits_the_disagreement():
    """Asserted inline so the file's reason cannot rot."""
    cap = zone_cap_for_pivot(WITNESSED_PIVOT)
    assert cap == 37.3581
    assert f"{cap:.2f}" == "37.36"
    assert mandate_limit_price(cap) == 37.35

    control = zone_cap_for_pivot(CONTROL_PIVOT)
    assert control == 18.8902
    assert f"{control:.2f}" == "18.89"
    assert mandate_limit_price(control) == 18.89


def test_zone_cap_for_pivot_IS_the_latch_derivations_own_arithmetic():
    """IDENTITY, not agreement (CHARC's item-6 rule). `swing/latches/service.py`
    computes every latch's frozen cap; if it kept a private copy of the
    expression, the two would agree today and drift on the next edit.
    """
    import swing.latches.service as service_mod

    assert service_mod.zone_cap_for_pivot is zone_cap_for_pivot
    for pivot in (WITNESSED_PIVOT, CONTROL_PIVOT, 16.90, 0.25, 141.00):
        assert (zone_cap_for_pivot(pivot)
                == round(pivot * (1.0 + LATCH_ZONE_CAP_PCT / 100.0), 4))


def test_the_chase_factor_DEFAULT_is_derived_from_the_latch_zone_cap():
    """PRE-FIX this was 0.01 -- the retired pure-trigger discipline, encoded as
    a framework default and diverging from the latch cap by two whole points."""
    assert Web().chase_factor == LATCH_ZONE_CAP_PCT / 100.0
    assert Web().chase_factor != 0.01


def test_the_registry_default_MIRRORS_the_dataclass_default():
    """THE #11 MIRROR, and the reason it is load-bearing rather than tidy:
    `config_overrides.get_field_source` reports 'default' vs 'tracked' by
    comparing the live value against `spec.default`, so a stale registry default
    makes the config page label an untouched field as operator-set.

    This passes both pre-fix and post-fix BY DESIGN -- it is the pin that fails
    a HALF-done fix (one of the two moved), which is the realistic defect here.
    """
    assert get_spec("web.chase_factor").default == Web().chase_factor


def test_the_framework_never_soft_warns_against_its_own_default():
    """A default that trips its own 'confirm intent' warning is the framework
    contradicting itself at the operator's first edit. Asked of EVERY numeric
    registry entry, so the next field cannot reintroduce it."""
    for spec in FIELD_REGISTRY:
        if spec.type not in (int, float) or spec.default is None:
            continue
        result = validate_field(spec.path, str(spec.default))
        assert result.hard_errors == [], spec.path
        assert result.soft_warnings == [], (
            f"{spec.path}: the registry default {spec.default} warns against "
            f"itself -- {[w.message for w in result.soft_warnings]}")


# ---------------------------------------------------------------------------
# The dashboard buy limit
# ---------------------------------------------------------------------------
def test_the_dashboard_buy_limit_IS_the_price_the_framework_would_ORDER(
        seeded_db):
    """THE MERGE-BLOCKING DISCRIMINATOR.

    PRE-FIX: 36.27 x 1.01 = 36.6327, rendered '36.63' -- a limit two full
    points below the latch card's own mandate for the same setup, and not a
    whole-cent price at all.
    POST-FIX: the same 37.35 the latch panel and the prepared order state.
    """
    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    vm = _expanded(cfg)
    assert vm is not None
    assert vm.buy_stop == WITNESSED_PIVOT
    assert vm.buy_limit == mandate_limit_price(
        zone_cap_for_pivot(WITNESSED_PIVOT))
    assert vm.buy_limit == 37.35          # the PREMISE, not the contract
    assert vm.buy_limit != round(zone_cap_for_pivot(WITNESSED_PIVOT), 2), (
        "round-half-up would state 37.36, one cent ABOVE the cap")


def test_the_dashboard_buy_limit_control_a_cap_that_rounds_DOWN(seeded_db):
    """THE CONTROL. A blanket 'subtract a cent' implementation yields 18.88
    here and passes every assertion in the test above."""
    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "FTRE", "pivot": CONTROL_PIVOT, "initial_stop": 14.88},
    ])
    vm = _expanded(cfg, ticker="FTRE")
    assert vm is not None
    assert vm.buy_limit == mandate_limit_price(zone_cap_for_pivot(CONTROL_PIVOT))
    assert vm.buy_limit == 18.89
    assert vm.buy_limit == round(zone_cap_for_pivot(CONTROL_PIVOT), 2)


def test_the_buy_limit_equals_the_LATCH_mandate_limit_for_the_same_pivot(
        seeded_db):
    """THE WHOLE POINT OF THE CHANGE, stated as an equality between the two
    surfaces rather than as a value on either.

    The latch side is driven through `compute_prepared_order` -- the function
    that actually emits the operator's order -- so this compares the dashboard
    against the production emitter, not against a re-derivation of it.
    """
    from datetime import date

    from swing.latches.identity import LatchIdentity
    from swing.latches.models import Latch
    from swing.latches.order_intent import SizingInputs, compute_prepared_order

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    vm = _expanded(cfg)

    latch = Latch(
        identity=LatchIdentity(
            candidate_id=9901, evaluation_run_id=141, ticker="AMN",
            detection_date="2026-07-20", pipeline_run_id=None),
        latched_pivot=WITNESSED_PIVOT, latched_initial_stop=33.00,
        zone_cap=zone_cap_for_pivot(WITNESSED_PIVOT),
        anchor=date(2026, 7, 20), horizon_expiry=date(2026, 9, 1),
        sessions_elapsed=3, sessions_to_horizon=27, state="armed")
    prepared = compute_prepared_order(
        latch=latch, regime_order_type="STOP_LIMIT", regime_close=35.10,
        regime_close_session="2026-07-24",
        sizing_inputs=SizingInputs(
            real_equity=1234.56, equity_floor=7500.0, sizing_equity=7500.0,
            max_risk_pct=0.005, position_pct_cap=0.15)).order

    assert vm is not None
    assert vm.buy_limit == prepared.limit_price, (
        "the dashboard and the latch mandate must state ONE entry limit for "
        "one pivot")


def test_an_OPERATOR_OVERRIDE_still_reaches_the_buy_limit(seeded_db):
    """The knob STAYS LIVE. Single-sourcing the DEFAULT must not quietly turn
    an operator-facing tunable into a decoration that no longer moves anything
    -- a knob that lies is worse than a knob that is gone.
    """
    cfg, _ = seeded_db
    cfg = replace(cfg, web=replace(cfg.web, chase_factor=0.05))
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    vm = _expanded(cfg)
    assert vm is not None
    assert vm.chase_factor == 0.05
    assert vm.buy_limit == mandate_limit_price(
        zone_cap_for_pivot(WITNESSED_PIVOT, cap_fraction=0.05))
    assert vm.buy_limit == 38.08
    assert vm.buy_limit != mandate_limit_price(
        zone_cap_for_pivot(WITNESSED_PIVOT))
