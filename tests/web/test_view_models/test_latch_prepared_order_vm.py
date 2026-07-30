"""Arc 21-B Task 6 -- the panel VM's prepared-order block, disposition + prompt.

THE WITHHELD BRANCH IS THE DEFAULT, NOT THE AFTERTHOUGHT (plan section B.3): on
today's live substrate the newest close predates the derivation session, so the
regime is undeterminable and the form is withheld on EVERY card right now. The
tests are built accordingly -- the withheld path first, the offered path reached
by seeding a derivation-session close.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from swing.data.db import connect
from swing.latches.constants import (
    DERIVATION_FIELD_MANIFEST,
    LATCH_ATTESTED_DISPOSITIONS,
)
from swing.latches.order_intent import (
    FRAMEWORK_ANCHOR_FIELDS,
    build_anchor_digest,
    derivation_anchor_fields,
)
from swing.web.view_models.latches import (
    PANEL_SPECIFIC_FIELDS,
    build_latch_panel_vm,
    declared_banner_fields,
)

NOW = datetime(2026, 7, 25, 12, 0)      # Saturday -> action session 2026-07-27
DERIVATION_SESSION = "2026-07-24"       # horizon 2026-07-27, minus one session
_FTRE = (121, "2026-07-17", "2026-07-20", "FTRE", 18.34, 14.88)


def _seed_fire(cfg, *, close=17.76):
    rid, asof, action, ticker, pivot, stop = _FTRE
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
            (rid, f"{asof}T17:30:05", asof, action))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (?, ?, 'aplus', ?, ?, ?, 'universe')",
            (rid, ticker, close, pivot, stop))
    conn.close()


def _seed_derivation_session_close(cfg, price):
    """A close DATED the derivation session -- the only close allowed to pick
    the regime. The sample card in the plan is stamped this way for exactly this
    reason: writing the derivation-session date onto a close that does not carry
    it is the run-level-stamp error (#30)."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(900, ?, ?, '2026-07-27', 1, 0, 1, 0, 0, 0)",
            (f"{DERIVATION_SESSION}T17:30:05", DERIVATION_SESSION))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(900, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')", (price,))
    conn.close()


def _vm(cfg, *, now=NOW):
    conn = connect(cfg.paths.db_path)
    try:
        return build_latch_panel_vm(conn, cfg, now=now)
    finally:
        conn.close()


# --- the WITHHELD branch: today's live state ------------------------------
def test_the_form_is_withheld_when_the_regime_is_undeterminable(seeded_db):
    """The CURRENT live state, and therefore the DEFAULT branch. FTRE's newest
    close predates the derivation session, so `expected_mandate_order_type`
    returns None and a form that GUESSED the type would write the WRONG TYPE
    into the parity ledger."""
    cfg, _ = seeded_db
    _seed_fire(cfg)                    # close dated 2026-07-17, not 07-24
    block = _vm(cfg).rows[0].prepared_order
    assert block is not None
    assert block.offered is False
    assert block.withheld_reason == "regime_undeterminable"
    assert block.withheld_detail.strip()


def test_a_withheld_form_presents_NO_order_numbers_as_a_mandate(seeded_db):
    """A withheld block renders the mandate FACTS and the reason -- never a
    quantity, a limit or a duration, which would read as an order to place."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    block = _vm(cfg).rows[0].prepared_order
    assert block.headline == ""
    assert block.derivation_lines == ()
    assert block.anchor_fields == ()
    assert block.anchor_digest == ""


# --- the OFFERED branch ---------------------------------------------------
def test_the_offered_form_carries_the_prepared_order_at_the_ruled_geometry(
        seeded_db):
    """FTRE's real numbers. The close 19.20 is AT OR ABOVE the latched pivot
    18.34, so the mandate is the PULLBACK form: a GTC LIMIT at the cent-floored
    zone cap, with NO stop leg. Quantity 9, not 10: the sizing basis is the
    LIMIT price (RD 2026-07-29), and a pivot-basis 10 breaches the 0.5% policy
    cap at an ordinary cap fill."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    assert block.offered is True
    assert block.withheld_reason is None
    assert "BUY 9 FTRE" in block.headline
    assert "LIMIT 18.89" in block.headline
    assert "GOOD_TILL_CANCEL" in block.headline
    assert "STOP_LIMIT" not in block.headline


def test_the_offered_form_is_labelled_LOG_ONLY(seeded_db):
    """Nothing is sent to the broker in this arc, and the card says so where the
    operator reads it -- not only in a docstring."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    assert "LOG ONLY" in block.log_only_notice


def test_the_breakout_regime_renders_the_stop_leg(seeded_db):
    """Below the pivot the mandate is a GTC STOP_LIMIT triggered at the FROZEN
    pivot. A block that always renders the pullback form passes the test above
    and FAILS this one."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 17.76)
    block = _vm(cfg).rows[0].prepared_order
    assert "STOP_LIMIT" in block.headline
    assert "stop 18.34" in block.headline


def test_every_RENDERED_manifest_column_actually_appears_in_the_block(seeded_db):
    """SECTION A.4's closure, made CHECKABLE rather than aspirational.

    The rule is one decision, not two: a number is either part of the audited
    derivation -- hidden-anchored, compared at POST and stored -- or it is not
    shown as part of it. `rendered_derivation_columns` is declared BY THE LINE
    BUILDERS, so a line added without anchoring its inputs fails here.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    assert block.rendered_derivation_columns == frozenset(
        f.column for f in DERIVATION_FIELD_MANIFEST if f.rendered)


def test_the_derivation_shows_the_inputs_that_produced_every_number(seeded_db):
    """The D25 lesson made concrete: a human gate only helps if the human can
    SEE that a computation is wrong, and four bare numbers invite click-through.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    text = "\n".join(_vm(cfg).rows[0].prepared_order.derivation_lines)
    assert "18.34" in text and "1.03" in text          # the cap derivation
    assert "14.88" in text                             # the fire-time stop
    assert "evaluation run 121" in text                # the frozen provenance
    assert "risk per share" in text
    assert "sizing equity" in text
    assert "position cap" in text
    assert "19.20" in text and DERIVATION_SESSION in text   # the regime close
    assert "stop level only" in text                   # the V1 invalidation limit


def test_a_missing_active_risk_policy_row_labels_the_gap_and_still_offers(
        seeded_db, monkeypatch):
    """The sizing RATE comes from `cfg.risk.max_risk_pct`, NOT from the policy
    row, so a prepared order is fully computable with no active policy and the
    form is NOT withheld for one. The id is PROVENANCE -- and the card renders
    an explicit line rather than a blank, because an unlabelled gap is the quiet
    reduction the arc forbids."""
    import swing.web.view_models.latches as vm_mod
    from swing.data.repos.risk_policy import NoActivePolicyError
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)

    def _boom(_conn):
        raise NoActivePolicyError("none active")

    monkeypatch.setattr(vm_mod, "get_active_policy", _boom)
    block = _vm(cfg).rows[0].prepared_order
    assert block.offered is True
    assert "no active risk_policy row" in "\n".join(block.derivation_lines)


# --- the HIDDEN ANCHOR ----------------------------------------------------
def test_the_hidden_anchor_carries_every_field_the_digest_covers(seeded_db):
    """Generated by WALKING the manifest, so the form's hidden inputs, the
    digest and the POST-time comparison cannot drift and no site re-lists the
    columns."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    names = {name for name, _ in block.anchor_fields}
    expected = (
        {"view_session_date", "candidate_id"}
        | {n for n, _ in FRAMEWORK_ANCHOR_FIELDS}
        | {c for c, _ in derivation_anchor_fields()}
    )
    assert names == expected


def test_the_anchor_digest_matches_the_pure_builder_over_the_emitted_fields(
        seeded_db):
    """The digest is REPRODUCIBLE from the emitted hidden fields alone -- which
    is exactly what the POST-time comparison re-derives. A VM that hashed
    something the form does not emit would make the handler unimplementable."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    vm = _vm(cfg)
    block = vm.rows[0].prepared_order
    emitted = dict(block.anchor_fields)
    assert block.anchor_digest == build_anchor_digest(
        intent_kind="place", candidate_id=vm.rows[0].candidate_id,
        view_session_date=vm.horizon_session, values=emitted)


def test_the_anchor_digest_is_stable_across_two_identical_renders(seeded_db):
    """Content-derived, NOT a render-time nonce -- otherwise a plain refresh
    followed by an identical resubmit would write a SECOND ledger row."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    assert (_vm(cfg).rows[0].prepared_order.anchor_digest
            == _vm(cfg).rows[0].prepared_order.anchor_digest)


def test_the_anchor_digest_MOVES_when_the_framework_order_moves(seeded_db):
    """The paired discriminator. A digest that did not move would let a stale
    form laundering a DIFFERENT framework order hit the replay SELECT and
    return 200 without ever reaching the field-by-field comparison."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    first = _vm(cfg).rows[0].prepared_order.anchor_digest
    conn = connect(cfg.paths.db_path)
    with conn:                          # move the regime close -> BREAKOUT form
        conn.execute("UPDATE candidates SET close = 17.00 "
                     "WHERE evaluation_run_id = 900")
    conn.close()
    assert _vm(cfg).rows[0].prepared_order.anchor_digest != first


# --- the DISPOSITION + the PROMPT ----------------------------------------
def test_a_live_latch_with_no_telemetry_is_pre_telemetry_and_never_prompts(
        seeded_db):
    """FTRE anchored 2026-07-20 predates the 2026-07-29 telemetry epoch, so its
    window is partially dark with no observation: RD's ruled table says
    `pre_telemetry`. A naive 'no view rows -> away' implementation FAILS."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    row = _vm(cfg).rows[0]
    assert row.disposition == "pre_telemetry"
    assert row.prompt_required is False
    assert row.attest_options == ()


def test_the_attestation_prompt_renders_on_discipline_lapse_and_only_there(
        seeded_db, monkeypatch):
    """`prompt_required` is True on EXACTLY ONE disposition. Prompting a man to
    attest about a decision the panel never presented is the purest form of the
    train-the-dismissal-reflex failure."""
    import swing.web.view_models.latches as vm_mod
    from swing.latches.classification import LatchDisposition
    cfg, _ = seeded_db
    _seed_fire(cfg)
    real = vm_mod.classify_latch

    def _lapse(**kwargs):
        base = real(**kwargs)
        return LatchDisposition(
            candidate_id=base.candidate_id, disposition="discipline_lapse",
            execution_outcome=base.execution_outcome, prompt_required=True,
            is_terminal=True, coverage=base.coverage)

    monkeypatch.setattr(vm_mod, "classify_latch", _lapse)
    row = _vm(cfg).rows[0]
    assert row.prompt_required is True
    assert {v for v, _ in row.attest_options} == set(LATCH_ATTESTED_DISPOSITIONS)


# --- the BEACON PAYLOAD SPLIT (the R7 CRITICAL discriminator) -------------
def test_the_beacon_payload_splits_actionable_from_withheld_ids(seeded_db):
    """THE R7 CRITICAL. On today's live substrate EVERY card is withheld, so a
    payload that lumps them records a full 'he saw the mandate' view for every
    latch -- and the away/lapse split would then be computed from renders that
    never presented a decision. It is not even a bias in one direction: it
    inflates `discipline_lapse`, deflates `away_unseen` and therefore DEFLATES
    the away rate, arguing against stage-3 auto-place on evidence the panel
    never actually showed him."""
    cfg, _ = seeded_db
    _seed_fire(cfg)                     # withheld: no derivation-session close
    vm = _vm(cfg)
    payload = json.loads(vm.beacon_payload_json)
    cid = str(vm.rows[0].candidate_id)
    assert payload["withheld_candidate_ids"] == cid
    assert payload["actionable_candidate_ids"] == ""
    assert "candidate_ids" not in payload


def test_an_offered_card_posts_its_id_on_the_ACTIONABLE_leg(seeded_db):
    """The paired discriminator: an implementation that always reports withheld
    passes the test above and fails this one."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    vm = _vm(cfg)
    payload = json.loads(vm.beacon_payload_json)
    cid = str(vm.rows[0].candidate_id)
    assert payload["actionable_candidate_ids"] == cid
    assert payload["withheld_candidate_ids"] == ""


# --- surfaces, A5, A6 -----------------------------------------------------
def test_a_non_counted_surface_row_moves_nothing(seeded_db):
    """Section E.3 conjunct 2, exercised through the `counted_surfaces=`
    PARAMETER over a VALID `latch_panel` row. Planting a `dashboard` row is
    UNWRITABLE today (the CHECK plus the model validator), so a test that did so
    could only pass by bypassing the very #11 mirror it exists to respect."""
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.reader import build_latch_derivation
    from swing.web.view_models.latches import _load_views
    cfg, _ = seeded_db
    _seed_fire(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        derivation = build_latch_derivation(conn, cfg, now=NOW)
        latch = derivation.latches[0]
        with conn:
            record_view(
                conn, identity=latch.identity,
                view_session_date=derivation.horizon_session.isoformat(),
                viewed_ts="2026-07-27T09:00:00", latch_state=latch.state,
                surface="latch_panel", actionable=1)
        assert _load_views(
            conn, [latch], derivation.horizon_session,
            counted_surfaces=frozenset()) == {latch.identity.candidate_id: ()}
    finally:
        conn.close()


def test_the_new_panel_fields_are_declared_panel_specific(seeded_db):
    """A5. `declared_banner_fields()` must be UNCHANGED from 21-A, or the
    cross-VM banner drift pin breaks on a field that is not a banner field."""
    from swing.web.view_models.latches import LatchPanelVM
    cfg, _ = seeded_db
    _seed_fire(cfg)
    names = {f.name for f in __import__("dataclasses").fields(LatchPanelVM)}
    assert declared_banner_fields() == names - PANEL_SPECIFIC_FIELDS
    assert {"intent_payload_json", "telemetry_health_verdict",
            "telemetry_health_label"} <= PANEL_SPECIFIC_FIELDS
    assert not ({"intent_payload_json", "telemetry_health_verdict",
                 "telemetry_health_label"} & declared_banner_fields())


@pytest.mark.parametrize("target", [
    "compute_prepared_order", "classify_latch", "assess_telemetry_health",
    "list_intents_for_latch", "get_active_policy",
])
def test_every_new_read_degrades_and_the_panel_never_500s(
        seeded_db, monkeypatch, target):
    """A6, per new seam. Each of these is a NEW read this task introduces, and
    any one of them raising must degrade the block rather than take the page
    down."""
    import swing.web.view_models.latches as vm_mod
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)

    def _boom(*_a, **_k):
        raise RuntimeError(f"{target} exploded")

    monkeypatch.setattr(vm_mod, target, _boom)
    vm = _vm(cfg)
    assert vm.available is True
    assert vm.rows


# --- the classifier's corpus vs the card's echo ---------------------------
def test_the_classifier_gets_the_WHOLE_covered_window_not_only_this_session(
        seeded_db, monkeypatch):
    """CODEX EXEC R2 MAJOR 1. `_load_views` narrows to the render session
    because the card's telemetry label is a claim about THIS visit -- but
    `classify_latch` reads the latch's WHOLE covered window, so handing it the
    narrowed set silently discards a PRIOR session's actionable view. A latch he
    demonstrably acted under would then fall out of `discipline_lapse` into
    `away_unseen` or `never_actionable`: the instrument losing its own evidence
    and scoring the loss against its subject.

    The capture is on the ARGUMENT rather than on a resulting disposition
    because the epoch gates the disposition ladder independently -- pinning the
    corpus is the claim being made, and it distinguishes: under the narrowed set
    the prior-session row is absent from what the classifier is handed.
    """
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.reader import build_latch_derivation
    import swing.web.view_models.latches as vm_mod
    cfg, _ = seeded_db
    _seed_fire(cfg)
    prior = "2026-07-21"      # inside the covered window, NOT the horizon
    conn = connect(cfg.paths.db_path)
    try:
        derivation = build_latch_derivation(conn, cfg, now=NOW)
        latch = derivation.latches[0]
        assert prior != derivation.horizon_session.isoformat()
        assert latch.anchor.isoformat() <= prior
        with conn:
            record_view(
                conn, identity=latch.identity, view_session_date=prior,
                viewed_ts=f"{prior}T09:00:00", latch_state=latch.state,
                surface="latch_panel", actionable=1)
    finally:
        conn.close()

    seen: dict = {}
    real = vm_mod.classify_latch

    def _capture(**kw):
        seen[kw["latch"].identity.candidate_id] = tuple(kw["views"])
        return real(**kw)

    monkeypatch.setattr(vm_mod, "classify_latch", _capture)
    vm = _vm(cfg)
    assert vm.rows
    cid = vm.rows[0].candidate_id
    assert [r.view_session_date for r in seen[cid]] == [prior]


def test_the_cards_own_telemetry_echo_STAYS_narrowed_to_this_session(
        seeded_db):
    """The other half of R2 MAJOR 1, and the reason the fix is two readers
    rather than one widened reader: the card's label answers 'was this panel
    opened THIS session'. Widening it would make a card claim a view it did not
    receive today."""
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.reader import build_latch_derivation
    from swing.web.view_models.latches import _load_all_views, _load_views
    cfg, _ = seeded_db
    _seed_fire(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        derivation = build_latch_derivation(conn, cfg, now=NOW)
        latch = derivation.latches[0]
        cid = latch.identity.candidate_id
        with conn:
            record_view(
                conn, identity=latch.identity, view_session_date="2026-07-21",
                viewed_ts="2026-07-21T09:00:00", latch_state=latch.state,
                surface="latch_panel", actionable=1)
        echo = _load_views(conn, [latch], derivation.horizon_session)
        whole = _load_all_views(conn, [latch])
    finally:
        conn.close()
    assert echo[cid] == ()
    assert [r.view_session_date for r in whole[cid]] == ["2026-07-21"]
