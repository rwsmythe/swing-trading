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


def test_the_LATCH_DERIVATION_actually_INVOKES_the_shared_helper(monkeypatch):
    """CODEX R1 MINOR: a BINDING IS NOT A CALL.

    The identity assertion above proves only that `service.py` still imports
    the name. It could reintroduce a local expression and leave the unused
    import in place, and every value test would keep passing for as long as the
    two happened to agree -- exactly the drift this ruling exists to make
    impossible. So the property is pinned by SUBSTITUTION (the in-tree
    precedent: tests/latches/test_mandate_limit_contract.py).
    """
    import swing.latches.service as service_mod

    sentinel = 99.9999
    monkeypatch.setattr(
        service_mod, "zone_cap_for_pivot", lambda *a, **k: sentinel)
    draft = service_mod._Draft(
        fire=None, anchor=None, pivot=WITNESSED_PIVOT, stop=33.00,
        horizon_expiry=None)
    assert draft.zone_cap == sentinel, (
        "_Draft.zone_cap must OBTAIN the cap from the shared helper")


def test_the_DASHBOARD_actually_INVOKES_both_shared_functions(
        seeded_db, monkeypatch):
    """The same substitution pin on the other side of the seam: the buy limit
    must come from `zone_cap_for_pivot` AND from `mandate_limit_price`, not
    from a local expression that agrees with them today."""
    import swing.web.view_models.dashboard as dash_mod

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    # `monkeypatch.context()` rather than `monkeypatch.undo()` (Codex R2 NIT):
    # `undo()` reverts EVERY patch on the fixture, including the autouse
    # HOME/USERPROFILE redirection that keeps this test off the operator's real
    # user-config -- a scoped context reverts only what it set.
    with monkeypatch.context() as m:
        m.setattr(dash_mod, "zone_cap_for_pivot", lambda *a, **k: 41.1111)
        assert _expanded(cfg).buy_limit == 41.11
    with monkeypatch.context() as m:
        m.setattr(dash_mod, "mandate_limit_price", lambda cap: 12.34)
        assert _expanded(cfg).buy_limit == 12.34


def test_the_DEFAULTS_are_written_as_the_NAME_not_as_a_copied_literal():
    """CODEX R1 MINOR, and it is the finding that matters most here.

    A float comparison cannot tell `LATCH_ZONE_CAP_FRACTION` from a hand-typed
    `0.03` -- both equal 0.03 -- so every value assertion in this file would
    pass a copied literal, which IS the drift class the change exists to
    remove. The only way to pin DERIVATION rather than AGREEMENT is to read the
    source: the two defaults must be the NAME.
    """
    import ast
    import inspect

    import swing.config as config_mod
    import swing.config_validation as validation_mod

    def _default_expr(module, class_or_call: str, field: str) -> str:
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if (isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == field
                    and node.value is not None):
                return ast.unparse(node.value)
            if isinstance(node, ast.keyword) and node.arg == field:
                return ast.unparse(node.value)
        raise AssertionError(f"{field} not found in {module.__name__}")

    assert _default_expr(config_mod, "Web", "chase_factor") == (
        "LATCH_ZONE_CAP_FRACTION"), (
        "Web.chase_factor's default must BE the shared name, not a literal "
        "that happens to equal it")
    # The registry's `default=` and `soft_warn_max=` keywords, in FIELD_REGISTRY
    # source order -- `web.chase_factor` is the first entry.
    registry_src = inspect.getsource(validation_mod)
    chase_block = registry_src.split('path="web.chase_factor"')[1].split(
        "FieldSpec(")[0]
    assert "default=LATCH_ZONE_CAP_FRACTION" in chase_block
    assert "soft_warn_max=LATCH_ZONE_CAP_FRACTION" in chase_block


# ---------------------------------------------------------------------------
# CODEX R1 MAJOR -- a non-finite chase factor must not become a 500
# ---------------------------------------------------------------------------
def test_a_non_finite_chase_factor_is_REFUSED_not_crashed(seeded_db):
    """`validate_field` performs ORDERED comparisons only, and every comparison
    against `nan` is False, so `nan` passes both the hard bounds and the soft
    warning and reaches `Web.chase_factor`. A TOML `chase_factor = inf` bypasses
    the registry entirely (`Web(**raw)`).

    PRE-FIX the multiplication produced `nan`/`inf` and the card rendered the
    word. POST-FIX the value reaches `Decimal(...).quantize`, which raises
    `decimal.InvalidOperation` -- NOT the `ValueError` the builder's degenerate
    -sizing guard catches -- so the expansion route 500s. That is a REGRESSION
    introduced by the single-sourcing, so the guard belongs at the shared
    helper and the builder degrades exactly as it does for degenerate sizing.
    """
    import pytest

    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            zone_cap_for_pivot(WITNESSED_PIVOT, cap_fraction=bad)
        with pytest.raises(ValueError):
            zone_cap_for_pivot(bad)

    cfg, _ = seeded_db
    cfg = replace(cfg, web=replace(cfg.web, chase_factor=float("inf")))
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    assert _expanded(cfg) is None, (
        "the builder must degrade to its unavailable partial, not raise")


def test_the_finiteness_guard_does_not_move_any_ORDINARY_value():
    """The control on the guard: rejecting non-finite input must not perturb a
    single real cap."""
    for pivot in (0.25, 1.0, 18.34, 36.27, 141.00, 999.99):
        assert zone_cap_for_pivot(pivot) == round(pivot * 1.03, 4)


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
    It pins AGREEMENT only; DERIVATION is pinned at the source level by
    `test_the_DEFAULTS_are_written_as_the_NAME_not_as_a_copied_literal`.
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

    WHAT THIS TEST DOES NOT BLESS (codex-auto-review MAJOR, 2026-08-03): at an
    override the dashboard states a limit the latch mandate would NOT order --
    38.08 against the mandate's 37.35 -- so the "one entry limit for one pivot"
    property holds at the DEFAULT and not above it. That residual is REAL and it
    is FLAGGED UPWARD as the directors' open question the brief reserved (should
    the knob exist at all). What is fixed here is the SILENCE: the card no
    longer presents an operator override as the framework's own price. See
    `test_an_override_is_DISCLOSED_as_a_divergence_from_the_mandate`.
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


def test_an_override_is_DISCLOSED_as_a_divergence_from_the_mandate(seeded_db):
    """CODEX-AUTO-REVIEW MAJOR. An override above the latch cap makes this card
    state a price the framework would refuse to order -- the exact defect the
    arc exists to remove, relocated behind a knob.

    Removing the knob is the directors' call and is NOT taken here. What IS
    taken is the project's standing posture: an unlabelled reduction is a quiet
    all-clear by omission. So the divergence is NAMED on the card, with both
    numbers, rather than presented as the framework's own limit.
    """
    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])

    at_default = _expanded(cfg)
    assert at_default.chase_factor_diverges_from_mandate is False
    assert at_default.mandate_buy_limit == at_default.buy_limit

    over = replace(cfg, web=replace(cfg.web, chase_factor=0.05))
    vm = _expanded(over)
    assert vm.chase_factor_diverges_from_mandate is True
    assert vm.mandate_buy_limit == mandate_limit_price(
        zone_cap_for_pivot(WITNESSED_PIVOT))
    assert vm.mandate_buy_limit == 37.35
    assert vm.buy_limit == 38.08


def test_the_divergence_DISCLOSURE_reaches_the_rendered_card(seeded_db):
    """Through the REAL template, because a VM flag nobody renders discloses
    nothing.

    The VM is built by the production builder and then handed to the production
    partial directly (the in-tree pattern from
    tests/web/templates/test_expanded_chart_suppress_banner.py) rather than
    driven through `create_app` + TestClient: the route path pulls in the price
    cache and its executor, which makes a pure template assertion depend on a
    live fetch and on worker-shared app state.
    """
    from swing.web.app import _build_templates, _templates_dir

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])

    def _render(effective):
        vm = _expanded(effective)
        assert vm is not None
        templates = _build_templates(_templates_dir())
        template = templates.env.get_template(
            "partials/hypothesis_recommendations_expanded.html.j2")
        return template.render(expanded=vm, watchlist_entry=None)

    over = replace(cfg, web=replace(cfg.web, chase_factor=0.05))
    text = _render(over)
    assert "38.08" in text
    assert "37.35" in text, "the mandate's own limit must be shown beside it"
    assert "does not match the latch mandate" in text

    clean = _render(cfg)
    assert "does not match the latch mandate" not in clean, (
        "the disclosure must be SILENT at the default, or it is noise")
    assert "37.35" in clean


def test_the_divergence_flag_is_DERIVED_not_a_second_stored_field():
    """CODEX R3 MINOR. A stored boolean beside the price is a second source a
    DIRECT constructor can set inconsistently -- and this VM has direct
    constructors in-tree (one passes limit 210 at a 5% factor, whose mandate is
    206, and a defaulted `False` rendered that as agreement).

    So the flag is a PROPERTY. This test builds the VM by hand, deliberately
    bypassing the builder, and a re-introduced stored field fails it.
    """
    from dataclasses import fields as dc_fields

    from swing.recommendations.sizing import SizingResult
    from swing.web.view_models.dashboard import HypRecsExpandedVM

    names = {f.name for f in dc_fields(HypRecsExpandedVM)}
    assert "chase_factor_diverges_from_mandate" not in names, (
        "the flag must be DERIVED; a stored field can contradict the price")

    sizing = SizingResult(
        feasible=True, shares=10, notional=2000.0, risk_dollars=100.0,
        risk_pct=1.0, notional_pct=20.0, constraint="ok")

    def _vm(**over):
        base = dict(
            ticker="UCTT", buy_stop=200.0, buy_limit=210.0, sell_stop=190.0,
            chase_factor=0.05, current_balance=10_000.0, risk_equity=10_000.0,
            sizing_risk=sizing, sizing_cash=sizing, sector="Technology",
            industry="Semiconductors", data_asof_date="2026-04-28",
            chart_reason=None, chart_reason_message=None,
            pipeline_finished_at="2026-04-29T16:00:00")
        base.update(over)
        return HypRecsExpandedVM(**base)

    # NOT COMPUTED is not AGREEMENT, but it is also not a claim: the card says
    # nothing rather than guessing.
    assert _vm().mandate_buy_limit is None
    assert _vm().chase_factor_diverges_from_mandate is False

    # ...and the CARD must not fall back to the agreement label either (Codex
    # R4 MINOR): with no mandate computed it makes NO source claim at all, or a
    # direct constructor at limit 210 / factor 5% would be told 210 is the cap
    # when the mandate is 206.
    from swing.web.app import _build_templates, _templates_dir
    template = _build_templates(_templates_dir()).env.get_template(
        "partials/hypothesis_recommendations_expanded.html.j2")
    uncomputed = template.render(expanded=_vm(), watchlist_entry=None)
    assert "the buy-zone cap for this pivot" not in uncomputed
    assert "your configured chase factor" not in uncomputed
    assert "floored to whole cents" in uncomputed
    # Computed and different -> disclosed, with no way to say otherwise.
    assert _vm(mandate_buy_limit=206.0).chase_factor_diverges_from_mandate
    # Computed and equal -> silent.
    assert _vm(mandate_buy_limit=210.0).chase_factor_diverges_from_mandate is False


def test_the_card_does_not_call_an_OVERRIDE_the_buy_zone_cap(seeded_db):
    """CODEX R3 MINOR. Under an override the annotation used to name 38.08 as
    "the buy-zone cap for this pivot" on the line directly above a disclosure
    identifying 37.35 as the framework's cap -- the disclosure fixed the
    silence but the label was still false."""
    from swing.web.app import _build_templates, _templates_dir

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    templates = _build_templates(_templates_dir())
    template = templates.env.get_template(
        "partials/hypothesis_recommendations_expanded.html.j2")

    over = replace(cfg, web=replace(cfg.web, chase_factor=0.05))
    text = template.render(expanded=_expanded(over), watchlist_entry=None)
    assert "your configured chase factor" in text
    assert "the buy-zone cap for this pivot" not in text

    clean = template.render(expanded=_expanded(cfg), watchlist_entry=None)
    assert "the buy-zone cap for this pivot" in clean
    assert "your configured chase factor" not in clean


def test_a_LARGE_FINITE_chase_factor_degrades_instead_of_500(seeded_db):
    """CODEX R2 MAJOR / codex-auto-review MINOR. `zone_cap_for_pivot`'s
    finiteness guard does not catch a large FINITE value: `1e25` yields a finite
    cap that `Decimal.quantize` then refused at the default 28-digit precision,
    so the route 500'd where the old multiplication rendered a number.

    Fixed at `mandate_limit_price` (a precision context), so this asserts the
    surface RENDERS rather than raising -- the guard is not what saves it.
    """
    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AMN", "pivot": WITNESSED_PIVOT, "initial_stop": 33.00},
    ])
    for factor in (1e25, 1e300):
        over = replace(cfg, web=replace(cfg.web, chase_factor=factor))
        vm = _expanded(over)
        assert vm is not None, f"chase_factor={factor} must not raise"
        assert vm.buy_limit > WITNESSED_PIVOT
