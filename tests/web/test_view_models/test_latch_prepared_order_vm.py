"""Arc 21-B Task 6 -- the panel VM's prepared-order block, disposition + prompt.

THE WITHHELD BRANCH IS THE DEFAULT, NOT THE AFTERTHOUGHT (plan section B.3): on
today's live substrate the newest close predates the derivation session, so the
regime is undeterminable and the form is withheld on EVERY card right now. The
tests are built accordingly -- the withheld path first, the offered path reached
by seeding a derivation-session close.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from swing.data.db import connect
from tests._candidates_barrier_helper import candidates_barrier_lifted
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
    rederive_prepared_order,
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


def _seed_close(cfg, price, *, session=DERIVATION_SESSION, run_id=900):
    """A recorded close carrying `session` as its RUN STAMP.

    The stamp is an UPPER BOUND on the close's own date, never a proof of it
    (#30), so this helper only plants the recorded number -- what the panel is
    allowed to CLAIM about it is decided by the archive bars seeded alongside.
    """
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, '2026-07-27', 1, 0, 1, 0, 0, 0)",
            (run_id, f"{session}T17:30:05", session))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(?, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')",
            (run_id, price))
    conn.close()


def _write_archive_bars(cfg, rows, ticker="FTRE"):
    """Shape-A OHLCV archive bars for `ticker`, as `(iso_session, close)`.

    THE ARCHIVE IS THE ONLY READ-SIDE SOURCE THAT DATES A CLOSE PER ROW. Shape A
    (`{T}.yfinance.parquet`) is deliberate: the panel reads with `migrate=False`
    (the A4 no-write property), so a legacy `{T}.parquet` is invisible here
    exactly as it is in production. (Mirrors the order-fragment test helper.)
    """
    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


def _seed_derivation_session_close(cfg, price):
    """A close the archive PROVES is the derivation session's -- rung A, the
    only rung a prepared order may be asserted from.

    THE ARCHIVE BAR IS NOT DECORATION. A run stamp is only an upper bound on a
    close's date (#30), so seeding the recorded close alone would leave the
    panel unable to prove the date it renders and the form correctly WITHHELD.
    Corroborating it at the derivation session is what makes this the OFFERED
    fixture, and it is the seed the pre-fix code did not need -- which is why no
    test covered the contradicted geometry.
    """
    _seed_close(cfg, price)
    _write_archive_bars(cfg, [(DERIVATION_SESSION, price)])


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


# --- the PROVENANCE gate on the prepared order ----------------------------
def test_a_close_the_archive_CONTRADICTS_withholds_the_prepared_order(seeded_db):
    """THE ROUTE-B GEOMETRY, and the card must agree with itself on it.

    `candidates.close = 19.52` stamped 2026-07-24 while the archive holds a bar
    dated 2026-07-24 that closed 17.76. The stamp is only an UPPER BOUND on the
    close's own date (#30), so the panel cannot prove the recorded number is the
    derivation session's -- and 19.52 sits ABOVE the latched pivot 18.34 while
    the dated bar sits BELOW it, so the two answers are not even the same
    instrument.

    Gating on stamp equality offered a placeable LIMIT and asserted the date
    `2026-07-24` for it, two lines under a price line that said `close dated ON
    OR BEFORE 2026-07-24`. One card, one quantity, two claims.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_close(cfg, 19.52)
    _write_archive_bars(cfg, [(DERIVATION_SESSION, 17.76)])
    row = _vm(cfg).rows[0]
    block = row.prepared_order
    assert block.offered is False
    assert block.withheld_reason == "regime_undeterminable"
    assert block.withheld_detail.strip()            # RD ruling 4: LABELLED
    # ...and the price line makes the SAME claim about what is known. Asserted
    # as ONE pair so a future edit cannot restore the contradiction and keep a
    # green suite.
    assert row.price_asof == "-"
    assert "on or before" in row.price_asof_basis


def test_an_unassertable_close_never_reaches_the_parity_ledger(seeded_db):
    """CHARC's decisive reason for treating this as merge-blocking rather than
    cosmetic: `regime_close_session` is WRITTEN AS FACT into the append-only
    record this arc exists to create. A display defect is recoverable; a ledger
    write is not.

    Both the GET emit and the POST-time re-derivation seam are asserted, because
    those are the only two doors the column can come through.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_close(cfg, 19.52)
    _write_archive_bars(cfg, [(DERIVATION_SESSION, 17.76)])
    row = _vm(cfg).rows[0]
    assert row.prepared_order.anchor_fields == ()
    assert "derivation_regime_close_session" not in dict(
        row.prepared_order.anchor_fields)
    conn = connect(cfg.paths.db_path)
    try:
        _latch, block = rederive_prepared_order(
            conn, cfg, candidate_id=row.candidate_id, anchor=date(2026, 7, 27))
    finally:
        conn.close()
    assert block.offered is False
    assert block.withheld_reason == "regime_undeterminable"


@pytest.mark.parametrize("recorded,bars,offered,why", [
    (19.20, [(DERIVATION_SESSION, 19.20)], True, "rung A: corroborated at S"),
    (19.52, [(DERIVATION_SESSION, 17.76)], False, "B-conflict: contradicted"),
    (19.20, [("2026-07-20", 19.20)], False, "B-undated: no bar dated S"),
    (19.20, [], False, "B-undated: the archive holds nothing"),
])
def test_the_prepared_order_is_offered_IFF_the_close_may_be_ASSERTED(
        seeded_db, recorded, bars, offered, why):
    """THE CALLER-SIDE OBLIGATION, pinned behaviourally across the ladder.

    `expected_mandate_order_type` is a seam for the pivot-vs-close COMPARISON
    only. Whether a price may be handed to it at all is a decision only the
    CALLER can make, and this is the test that pins it: the form is offered on
    rung A and on no other rung. A caller that re-introduced a stamp comparison
    passes the rung-A row and fails all three others.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_close(cfg, recorded)
    if bars:
        _write_archive_bars(cfg, bars)
    block = _vm(cfg).rows[0].prepared_order
    assert block.offered is offered, why


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


def test_the_nightly_SIZING_DIVERGENCE_NOTE_is_GONE(seeded_db):
    """A GUARD OUTLIVING ITS CONDITION (RD 2026-08-04).

    The section-D.3 note existed because the nightly sized off the PIVOT and
    this form off the LIMIT, so the operator needed the two numbers and the
    reason side by side at the point of action. The nightly now sizes off the
    limit too -- the surfaces AGREE -- and a note explaining a divergence that
    no longer exists is dead prose that reads as an active warning.

    Pinned on the NO-ROW branch as well: `_seed_fire` writes no
    `daily_recommendations` row, so pre-fix this fixture rendered the "no
    nightly share count to compare against" variant. Both branches are gone.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    text = "\n".join(block.derivation_lines)
    assert block.offered is True
    assert "NOTE:" not in text
    assert "off the PIVOT" not in text
    assert "nightly" not in text.lower()
    assert "reconciliation break" not in text


def _seed_nightly_recommendation(cfg, shares: int):
    """The nightly's row FOR THIS FIRE -- the fire's own evaluation run and its
    own action session, which is exactly the pair `_nightly_shares` keys on."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO daily_recommendations (evaluation_run_id, "
            "data_asof_date, action_session_date, ticker, recommendation, "
            "action_text, entry_target, stop_target, shares, risk_dollars, "
            "risk_pct, rationale) VALUES (?, ?, ?, 'FTRE', 'today_decision', "
            "'seeded', 18.34, 14.88, ?, 36.0, 0.48, 'seed')",
            (_FTRE[0], _FTRE[1], _FTRE[2], shares))
    conn.close()


def test_the_PERSISTED_nightly_column_survives_the_notes_removal(seeded_db):
    """THE LINE BETWEEN THE RENDER AND THE LEDGER.

    `derivation_nightly_recommendation_shares` is PER-ROW PROVENANCE on the
    append-only `latch_order_intents` table (migration 0033): what the nightly
    surface said AT INTENT TIME. Only the CARD's note was retired; the value is
    still gathered, still hidden-anchored with its real VALUE, still folded
    into `anchor_digest` and still persisted -- and an append-only ledger
    losing a provenance field to a display cleanup would be the anti-provenance
    move (RD, 2026-08-04).

    A REAL NON-NULL VALUE IS SEEDED (Codex R1 MINOR). Asserting only that the
    field NAME appears would pass against a render that anchored a constant
    None, which is the reduction this test exists to catch.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    _seed_nightly_recommendation(cfg, 7)
    block = _vm(cfg).rows[0].prepared_order
    emitted = dict(block.anchor_fields)
    assert emitted["derivation_nightly_recommendation_shares"] == "7"
    assert "derivation_nightly_recommendation_shares" in {
        c for c, _ in derivation_anchor_fields()}
    # ...and it is declared UNRENDERED, which is what keeps the section-A.4
    # closure assertion above honest rather than merely satisfied.
    field = next(f for f in DERIVATION_FIELD_MANIFEST
                 if f.column == "derivation_nightly_recommendation_shares")
    assert field.rendered is False
    assert field.nullable is True and field.null_reason.strip()


def test_the_anchor_DIGEST_still_moves_with_the_nightly_share_count(seeded_db):
    """THE PAIRED DISCRIMINATOR (Codex R1 MINOR). A field carried in
    `anchor_fields` but dropped from the digest would be un-audited: a stale
    form laundering a DIFFERENT nightly provenance would hit the replay SELECT
    and never reach the field-by-field comparison. Un-rendering the value must
    not un-audit it.
    """
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    _seed_nightly_recommendation(cfg, 7)
    first = _vm(cfg).rows[0].prepared_order.anchor_digest

    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute("UPDATE daily_recommendations SET shares = 8")
    conn.close()
    second = _vm(cfg).rows[0].prepared_order
    assert second.anchor_digest != first
    assert dict(second.anchor_fields)[
        "derivation_nightly_recommendation_shares"] == "8"
    # ...and the card still says NOTHING about either number.
    assert "nightly" not in "\n".join(second.derivation_lines).lower()


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
        # 22-A migration 0037 barriers `candidates`.  This test moves a close
        # to prove the ANCHOR DIGEST moves with the framework order; the moved
        # world is the SUBJECT of the assertion, so it is planted with the
        # barrier lifted and the barrier restored verbatim.
        with candidates_barrier_lifted(conn):
            conn.execute("UPDATE candidates SET close = 17.00 "
                         "WHERE evaluation_run_id = 900")
    conn.close()
    # THE ARCHIVE BAR MOVES WITH IT, or this stops being a digest test. Leaving
    # the 19.20 bar in place would make the moved close UNCORROBORATED, withhold
    # the form and pass this assertion on an empty digest -- a green test that
    # no longer discriminates.
    _write_archive_bars(cfg, [(DERIVATION_SESSION, 17.00)])
    second = _vm(cfg).rows[0].prepared_order
    assert second.offered is True
    assert second.anchor_digest != first


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
    # D84 T7.4 (Codex R4 A4-02): the fire's risk-layer read in
    # `_panel_risk_inputs`.
    "fetch_candidate_by_id",
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


# ---------------------------------------------------------------------------
# THE LABELLED GAP ON THE WITHHELD BRANCH (wave item 4, piece 2, Task 2.2).
#
# The DECLINE control lives inside the offered form, so a withheld card takes
# the decline affordance with it -- the same defect class as the cancel control
# riding on an alarm. It is NOT closed here, and the reason is the ledger
# contract rather than scope: a decline on a withheld card carries no framework
# and no derivation block (every withholding path in `compute_prepared_order`
# returns before any derivation object is built), which is UNWRITABLE at
# migration 0033's two CHECKs and at
# `LatchOrderIntent._validate_shape_exclusion`. So the SILENT absence becomes a
# LABELLED one -- the project's standing rule, and the honest interim.
# ---------------------------------------------------------------------------


def test_the_WITHHELD_branch_LABELS_why_a_decline_cannot_be_recorded(seeded_db):
    """DISCRIMINATOR -- the string does not exist anywhere pre-change."""
    from swing.web.view_models.latches import DECISION_UNAVAILABLE_NOTE
    cfg, _ = seeded_db
    _seed_fire(cfg)
    block = _vm(cfg).rows[0].prepared_order
    assert block.offered is False, "the premise: this card is WITHHELD"
    assert block.decision_unavailable_note == DECISION_UNAVAILABLE_NOTE
    assert block.decision_unavailable_note.strip()
    assert block.decision_unavailable_note.isascii()


def test_the_OFFERED_branch_carries_NO_decision_unavailable_note(seeded_db):
    """GUARD. It kills an implementation that sets the field on BOTH
    construction paths -- a default that is never overridden and a field set
    everywhere are indistinguishable from a test that looks at one branch."""
    cfg, _ = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    block = _vm(cfg).rows[0].prepared_order
    assert block.offered is True, "the premise: this card IS offered"
    assert block.decision_unavailable_note == ""


def test_the_WITHHELD_branch_STILL_offers_no_control(seeded_db):
    """GUARD, green pre-change. It kills the one wrong implementation: adding
    an INERT affordance while labelling the gap -- a control that renders and
    400s, which is the 21-B defect class this whole item is about.

    SCOPED TO THE PREPARED-ORDER `<section>`, not to the page: the attestation
    form renders on the same card and a page-wide assertion would be either
    vacuous or wrong.
    """
    from jinja2 import Environment, FileSystemLoader
    cfg, _ = seeded_db
    _seed_fire(cfg)
    row = _vm(cfg).rows[0]
    assert row.prepared_order.offered is False
    root = (Path(__file__).resolve().parents[3]
            / "swing" / "web" / "templates")
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=True)
    html = env.get_template(
        "partials/latch_prepared_order.html.j2").render(row=row)
    start = html.index('<section class="latch-prepared-order')
    section = html[start:html.index("</section>", start)]
    assert "latch-decision-unavailable" in section
    assert "<form" not in section
    assert "<button" not in section
    assert 'value="decline"' not in section


# ===========================================================================
# D84 T7.2 -- the card STATES its zero (F1-A, P3, E-i). The KOD geometry
# (pivot 104.00, stop 29.81, limit 107.12) at the $7,500 floor: one share risks
# $77.31 against the $37.50 budget, so the risk leg is the zero.
# ===========================================================================
KOD_FLAG_LINE = (
    "0 shares at the $37.50 budget; 1 share risks $77.31 (2.1x budget) at "
    "limit 107.12; above budget if you proceed")
KOD_DERIVATION_LINES = (
    "1-share risk $77.31 = limit 107.12 - fire-time stop 29.81",
    "budget $37.50 = sizing equity $7,500.00 x 0.500%",
    "sizing equity $7,500.00 = max(real equity $1,200.00, "
    "risk_equity_floor $7,500.00)",
    "shares at the budget 0 = floor($37.50 / $77.31)",
)


def _seed_kod_fire(cfg, *, risk_result="fail", ticker="KOD", pivot=104.00,
                   stop=29.81, close=98.46):
    """The KOD-shaped fire on run 121 (the FTRE session frame), carrying its
    persisted `risk_feasibility` row (the evaluation record)."""
    rid, asof, action = 121, "2026-07-17", "2026-07-20"
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
            (rid, f"{asof}T17:30:05", asof, action))
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (?, ?, 'aplus', ?, ?, ?, 'universe')",
            (rid, ticker, close, pivot, stop))
        if risk_result is not None:
            conn.execute(
                "INSERT INTO candidate_criteria (candidate_id, criterion_name, "
                "layer, result, value, rule) VALUES (?, 'risk_feasibility', "
                "'risk', ?, ?, ?)",
                (cur.lastrowid, risk_result,
                 "0 sh, $0.00 risk" if risk_result == "fail" else "1 sh",
                 ">= 1 share fits in 0.5% of equity ($37.50)"))
    conn.close()


def _seed_kod_derivation_session_close(cfg, price=98.46, ticker="KOD"):
    """Rung A for KOD: the recorded close AND an archive bar dated S."""
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
            "(900, ?, 'watch', ?, 104.0, 29.81, 'universe')",
            (ticker, price))
    conn.close()
    _write_archive_bars(cfg, [(DERIVATION_SESSION, price)], ticker=ticker)


def _render_card(row):
    from jinja2 import Environment, FileSystemLoader
    root = (Path(__file__).resolve().parents[3]
            / "swing" / "web" / "templates")
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=True)
    from types import SimpleNamespace
    return env.get_template("partials/latch_prepared_order.html.j2").render(
        row=row, vm=SimpleNamespace(horizon_session="2026-07-27"))


def _prepared_section(html):
    start = html.index('<section class="latch-prepared-order')
    return html[start:html.index("</section>", start)]


def test_acceptance_i_b_the_risk_flagged_card_renders_the_computed_shares_and_risk(
        seeded_db):
    """R-(i)b. The regime is determinable (a rung-A close), so the card is
    withheld on `sizing_infeasible` with the RISK leg the zero: the heading is
    the flag, the detail states the zero and the one-share risk at the limit,
    and the four derivation lines carry the equation (the D25 rule)."""
    import html as _html

    cfg, _ = seeded_db
    _seed_kod_fire(cfg)
    _seed_kod_derivation_session_close(cfg)
    row = _vm(cfg).rows[0]
    po = row.prepared_order
    assert po.offered is False
    assert po.withheld_reason == "sizing_infeasible"
    assert po.withheld_heading == "RISK FLAG - 0 SHARES AT THE BUDGET"
    assert po.withheld_detail == KOD_FLAG_LINE
    assert po.stated_zero_line == ""
    assert po.derivation_lines == KOD_DERIVATION_LINES
    assert all(line.isascii() for line in po.derivation_lines)
    section = _html.unescape(_prepared_section(_render_card(row)))
    assert "RISK FLAG - 0 SHARES AT THE BUDGET" in section
    assert KOD_FLAG_LINE in section
    for line in KOD_DERIVATION_LINES:
        assert line in section
    assert "<form" not in section
    assert "<button" not in section


def test_P3_the_regime_withheld_card_states_the_zero_BESIDE_the_regime_reason(  # noqa: N802
        seeded_db):
    """R-T7.6 -- CHARC P3: with the regime undeterminable the heading stays
    `PREPARED ORDER WITHHELD` and the detail stays the regime text (the regime
    fact is never masked), while the stated zero and its equation render
    BESIDE it. Still no form and no button in the prepared-order section."""
    import html as _html

    cfg, _ = seeded_db
    _seed_kod_fire(cfg)                  # no derivation-session close
    row = _vm(cfg).rows[0]
    po = row.prepared_order
    assert po.withheld_reason == "regime_undeterminable"
    assert po.withheld_heading == "PREPARED ORDER WITHHELD"
    assert po.withheld_detail.startswith(
        "No prepared order: the price regime is undeterminable")
    assert po.stated_zero_line == KOD_FLAG_LINE
    assert po.derivation_lines == KOD_DERIVATION_LINES
    section = _html.unescape(_prepared_section(_render_card(row)))
    assert "PREPARED ORDER WITHHELD" in section
    assert 'class="latch-stated-zero"' in section
    assert KOD_FLAG_LINE in section
    assert "<form" not in section
    assert "<button" not in section


def test_a_zero_nightly_count_maps_to_None_and_the_place_row_writes(  # noqa: N802
        seeded_db, monkeypatch):
    """R-T7.3 -- CHARC F1-A (4). Since D84 a zero nightly row is ROUTINE (every
    risk-flagged A+ sizes to zero), and 0033's CHECK
    `derivation_nightly_recommendation_shares IS NULL OR > 0` cannot store it.
    Seed `daily_recommendations.shares = 0` for the fire's run and session on
    an OFFERED geometry and POST `place`: the row writes with the column NULL.
    Before D84 the anchor carried "0" and the insert hit the CHECK."""
    from fastapi.testclient import TestClient

    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    from swing.web.app import create_app

    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cfg, cfg_path = seeded_db
    _seed_fire(cfg)
    _seed_derivation_session_close(cfg, 19.20)
    _seed_nightly_recommendation(cfg, 0)
    row = _vm(cfg).rows[0]
    assert row.prepared_order.offered is True
    form = dict(row.prepared_order.anchor_fields) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/latches/intent", headers={"HX-Request": "true"},
                        data=form)
    assert r.status_code == 200
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT intent_kind, derivation_nightly_recommendation_shares "
            "FROM latch_order_intents").fetchall()
    finally:
        conn.close()
    assert rows == [("place", None)]


# ===========================================================================
# D84 T7.4 -- the flag's KEY and the attest affordance (P2 (b), CHARC
# amendment 1's UNION). Keyed on the FIRE's STORED criteria (live AND terminal
# cards), OR on a LIVE card's own risk-bound `sizing_infeasible`.
# ===========================================================================
D84_LEAD = "The framework has no order here: 0 shares at the budget."


def _attest_section(html):
    start = html.index('<section class="latch-attest-prompt')
    return html[start:html.index("</section>", start)]


def test_acceptance_v_the_risk_withheld_card_offers_the_acted_manually_declaration(
        seeded_db):
    """R-(v)2 -- CHARC F1-A (2): a risk-withheld card with no declaration
    affordance IS the refusal the proposal forbids. The new field is True; the
    attest section offers exactly ONE radio, `acted_manually`, plus the broker
    order id; the prepared-order section still carries no form and no button."""
    cfg, _ = seeded_db
    _seed_kod_fire(cfg)
    _seed_kod_derivation_session_close(cfg)
    row = _vm(cfg).rows[0]
    assert row.risk_flag_attest_available is True
    assert row.prompt_required is False
    assert row.attest_options == (
        ("acted_manually", "I acted on this manually"),)
    html = _render_card(row)
    attest = _attest_section(html)
    assert attest.count('type="radio"') == 1
    assert 'value="acted_manually"' in attest
    assert 'name="actual_broker_order_id"' in attest
    assert D84_LEAD in attest
    section = _prepared_section(html)
    assert "<form" not in section and "<button" not in section


def _seed_superseding_fire(cfg, *, ticker="KOD"):
    """A SECOND A+ fire on run 125 with a different pivot, which supersedes the
    run-121 latch: the run-121 card is TERMINAL and inside the lookback."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (125, '2026-07-23T17:30:05', '2026-07-23', '2026-07-24', "
            "1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (125, ?, 'aplus', 18.0, 20.19, 16.515, 'universe')",
            (ticker,))
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, "
            "layer, result) VALUES (?, 'risk_feasibility', 'risk', 'pass')",
            (cur.lastrowid,))
    conn.close()


def _terminal_row(cfg, monkeypatch, *, risk_result="fail", disposition=None):
    """The TERMINAL run-121 card. The fixture predates the telemetry epoch, so
    the classifier says `pre_telemetry`; that one value is rewritten to
    `never_actionable` (the plan's terminal shape). Attestations and decisions
    the classifier resolves are left untouched; `disposition` forces one."""
    from dataclasses import replace as _replace

    import swing.web.view_models.latches as vm_mod

    real = vm_mod.classify_latch

    def _classify(**kwargs):
        base = real(**kwargs)
        if disposition is not None:
            return _replace(base, disposition=disposition)
        if base.disposition == "pre_telemetry":
            return _replace(base, disposition="never_actionable")
        return base

    monkeypatch.setattr(vm_mod, "classify_latch", _classify)
    _seed_kod_fire(cfg, risk_result=risk_result)
    _seed_superseding_fire(cfg)
    rows = _vm(cfg).rows
    (term,) = [r for r in rows if r.evaluation_run_id == 121]
    assert term.is_live is False and term.prepared_order is None
    return term


def test_P2_the_flag_and_affordance_ride_the_FIRES_criteria_on_a_TERMINAL_card(  # noqa: N802
        seeded_db, monkeypatch):
    """R-T7.7 -- P2 (b): keyed on the FIRE's stored criteria, so the flag and
    the affordance survive the latch going terminal ("attest first, then enter"
    must not become an order he has to obey). The lead paragraph is the D84
    one, never "went terminal with no action recorded". The four
    counterfactuals follow as their own tests."""
    cfg, _ = seeded_db
    term = _terminal_row(cfg, monkeypatch)
    assert term.disposition == "never_actionable"
    assert term.risk_flag_marker == "RISK FLAG"
    assert term.risk_flag_attest_available is True
    assert term.attest_options == (
        ("acted_manually", "I acted on this manually"),)
    attest = _attest_section(_render_card(term))
    assert D84_LEAD in attest
    assert "went terminal with no action recorded" not in attest
    assert attest.count('type="radio"') == 1


@pytest.mark.parametrize("risk_result", ["pass", None])
def test_P2_counterfactual_a_passing_or_EMPTY_risk_layer_renders_nothing(  # noqa: N802
        seeded_db, monkeypatch, risk_result):
    """R-T7.7 counterfactuals 1-2 -- a risk `pass` row, and NO risk row (E-d,
    the latch-VM consumer): no marker and no affordance."""
    cfg, _ = seeded_db
    term = _terminal_row(cfg, monkeypatch, risk_result=risk_result)
    assert term.risk_flag_marker == ""
    assert term.risk_flag_attest_available is False
    assert term.attest_options == ()


def test_P2_counterfactual_an_attestation_WITHDRAWS_the_affordance(  # noqa: N802
        seeded_db, monkeypatch):
    """R-T7.7 counterfactual 3 -- "until an attestation or a decision governs"
    (CHARC P2). After an `attest` the D84 affordance is gone and the correction
    affordance takes over, with the full vocabulary. The marker stays: it
    describes the fire."""
    cfg, _ = seeded_db
    attested = _terminal_row(cfg, monkeypatch,
                             disposition="attested_acted_manually")
    assert attested.risk_flag_attest_available is False
    assert attested.attest_correction_available is True
    assert attested.risk_flag_marker == "RISK FLAG"
    assert len(attested.attest_options) == 3


def test_P2_counterfactual_a_governing_PLACE_withdraws_the_affordance(  # noqa: N802
        seeded_db, monkeypatch):
    """R-T7.7 counterfactual 4 -- a governing `place` (disposition
    `accepted`) withdraws it."""
    cfg, _ = seeded_db
    accepted = _terminal_row(cfg, monkeypatch, disposition="accepted")
    assert accepted.risk_flag_attest_available is False
    assert accepted.attest_options == ()


def test_the_band_card_offers_the_declaration_without_a_marker(seeded_db):
    """R-T7.8 -- a GUARD over CHARC amendment 1's leg (b). The BAND: the risk
    criterion PASSES at the pivot (pivot 100.00, stop 63.00: one share risks
    $37.00 against the $37.50 budget) while the limit
    `mandate_limit_price(zone_cap_for_pivot(100.0))` = 103.00 risks $40.00, so
    the card sizes to ZERO on the RISK leg (the position cap allows 10).
    Without leg (b) a manual act in the band would be UNRECORDABLE: no
    framework order, no affordance, and no later prompt. The marker stays
    criteria-only (P1): the criterion passed, so NO marker."""
    from swing.latches.constants import mandate_limit_price, zone_cap_for_pivot

    assert mandate_limit_price(zone_cap_for_pivot(100.0)) == 103.00
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="pass", ticker="BAND", pivot=100.00,
                   stop=63.00, close=99.0)
    _seed_kod_derivation_session_close(cfg, price=99.0, ticker="BAND")
    row = _vm(cfg).rows[0]
    po = row.prepared_order
    assert po.withheld_reason == "sizing_infeasible"
    assert po.withheld_detail == (
        "0 shares at the $37.50 budget; 1 share risks $40.00 (1.1x budget) at "
        "limit 103.00; above budget if you proceed")
    assert row.risk_flag_marker == ""
    assert row.risk_flag_attest_available is True
    assert row.attest_options == (
        ("acted_manually", "I acted on this manually"),)


# ===========================================================================
# D84 T7.4 -- CHARC amendment 1 CORRECTED (20261026T164436Z, item 1).
# (a) leg (b) keys on the SIZING FACT (a live card whose own SizingResult is a
#     risk-bound zero), not on the `sizing_infeasible` reason or its heading,
#     so a regime-withheld card in the band still carries the declaration;
# (b) leg (a), the fire's flagged layer, is WITHDRAWN while the card OFFERS an
#     order: "The framework has no order here" is false on an offered card,
#     and the offered form's own place/decline path records the act. The
#     MARKER stays (P1: the fire's criterion did fail).
# ===========================================================================


def test_amendment1_corrected_a_the_regime_withheld_BAND_card_offers_the_declaration(  # noqa: N802
        seeded_db):
    """RED before the correction. R-T7.8's geometry (pivot 100.00, stop 63.00,
    risk PASSES at the pivot) with NO derivation-session close, so
    `regime_order_type` is None: the ORDINARY intraday state of a live card.
    The result is `regime_undeterminable` and still carries the sizing, a
    RISK-bound zero at limit 103.00. Keyed on the reason, the affordance was
    absent here; keyed on the sizing fact, it renders. No marker (P1)."""
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="pass", ticker="BAND", pivot=100.00,
                   stop=63.00, close=99.0)
    row = _vm(cfg).rows[0]
    assert row.is_live is True
    po = row.prepared_order
    assert po.withheld_reason == "regime_undeterminable"
    assert po.withheld_heading == "PREPARED ORDER WITHHELD"
    assert po.stated_zero_line.startswith("0 shares at the $37.50 budget")
    assert row.risk_flag_marker == ""
    assert row.risk_flag_attest_available is True
    assert row.attest_options == (
        ("acted_manually", "I acted on this manually"),)
    assert D84_LEAD in _attest_section(_render_card(row))


def test_amendment1_corrected_a_a_regime_withheld_FEASIBLE_card_offers_nothing(  # noqa: N802
        seeded_db):
    """GUARD. The same regime-None state with FEASIBLE sizing (pivot 100.00,
    stop 90.00: one share risks $13.00 at limit 103.00, 2 shares fit): no
    zero, so no declaration. Unchanged pre-D84 posture: the offered form
    arrives with the close. Fails if leg (b) keys on `sizing is not None`."""
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="pass", ticker="FEAS", pivot=100.00,
                   stop=90.00, close=99.0)
    row = _vm(cfg).rows[0]
    po = row.prepared_order
    assert po.withheld_reason == "regime_undeterminable"
    assert po.stated_zero_line == ""
    assert row.risk_flag_marker == ""
    assert row.risk_flag_attest_available is False
    assert row.attest_options == ()


def test_amendment1_corrected_a_a_regime_withheld_CAP_bound_zero_offers_nothing(  # noqa: N802
        seeded_db):
    """GUARD. Regime None with a CAP-bound zero (pivot 1200.00, stop 1199.00:
    one share risks $37.00 at limit 1236.00, inside the $37.50 budget, but one
    share's notional exceeds the position cap): the zero is the cap's, not the
    risk leg's, so no declaration. Fails if leg (b) keys on `shares == 0`."""
    from swing.recommendations.sizing import risk_bound_zero

    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="pass", ticker="CAPZ", pivot=1200.00,
                   stop=1199.00, close=1190.0)
    row = _vm(cfg).rows[0]
    po = row.prepared_order
    assert po.withheld_reason == "regime_undeterminable"
    assert po.sizing is not None and po.sizing.shares == 0
    # The RISK leg allows a share ($37.50 / $37.00 floors to 1), so the zero is
    # the position cap's.
    assert po.sizing.max_risk_dollars == 37.5
    assert po.sizing.risk_per_share == 37.0
    assert risk_bound_zero(po.sizing) is False
    assert row.risk_flag_attest_available is False
    assert row.attest_options == ()


def test_amendment1_corrected_b_an_OFFERED_card_withdraws_the_fire_flag_declaration(  # noqa: N802
        seeded_db):
    """RED before the correction. The fire's stored risk layer is FLAGGED,
    but the live card OFFERS an order (a rung-A close; pivot 100.00, stop
    90.00 sizes to 2 shares at limit 103.00), reachable when real equity rises
    above the floor or the policy is edited after the fire. "The framework has
    no order here" would be false and the act is recordable through the
    offered form, so the declaration is withdrawn. The marker STAYS (P1)."""
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="fail", ticker="OFR", pivot=100.00,
                   stop=90.00, close=99.0)
    _seed_kod_derivation_session_close(cfg, price=99.0, ticker="OFR")
    row = _vm(cfg).rows[0]
    assert row.prepared_order.offered is True
    assert row.risk_flag_marker == "RISK FLAG"
    assert row.risk_flag_attest_available is False
    assert row.attest_options == ()
    assert D84_LEAD not in _render_card(row)


def test_amendment1_corrected_b_a_flagged_WITHHELD_live_card_keeps_the_declaration(  # noqa: N802
        seeded_db):
    """GUARD. Fire flagged + a live WITHHELD card keeps leg (a). The geometry
    sizes FEASIBLY (pivot 100.00, stop 90.00) and the regime is None, so no
    order is offered and leg (b) cannot carry it: the declaration here is leg
    (a)'s alone. Fails if leg (a) is withdrawn on every LIVE card rather than
    on an OFFERED one. The terminal sibling is R-T7.7, unchanged."""
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="fail", ticker="WTH", pivot=100.00,
                   stop=90.00, close=99.0)       # no derivation-session close
    row = _vm(cfg).rows[0]
    assert row.is_live is True
    po = row.prepared_order
    assert po.offered is False
    assert po.withheld_reason == "regime_undeterminable"
    assert po.stated_zero_line == ""             # feasible: no zero, no leg (b)
    assert row.risk_flag_marker == "RISK FLAG"
    assert row.risk_flag_attest_available is True


def test_a_failed_risk_layer_read_degrades_only_its_row_no_marker_no_affordance(
        seeded_db, monkeypatch):
    """Codex R4 A4-02 (A6, D84's own read). A FLAGGED fire on a live withheld
    card (the WTH geometry: marker and leg-(a) affordance both present when the
    read succeeds) whose `fetch_candidate_by_id` raises: the panel stays
    available with its row, and that row renders NO marker and NO declaration
    affordance -- an unread layer is neither a flag nor a pass. Fails if the
    per-latch containment in `_panel_risk_inputs` is removed (the panel then
    degrades through its outer boundary)."""
    import swing.web.view_models.latches as vm_mod
    cfg, _ = seeded_db
    _seed_kod_fire(cfg, risk_result="fail", ticker="WTH", pivot=100.00,
                   stop=90.00, close=99.0)
    witness = _vm(cfg).rows[0]
    assert witness.risk_flag_marker == "RISK FLAG"
    assert witness.risk_flag_attest_available is True

    def _boom(*_a, **_k):
        raise RuntimeError("fetch_candidate_by_id exploded")

    monkeypatch.setattr(vm_mod, "fetch_candidate_by_id", _boom)
    vm = _vm(cfg)
    assert vm.available is True
    assert len(vm.rows) == 1
    row = vm.rows[0]
    assert row.risk_flag_marker == ""
    assert row.risk_flag_attest_available is False
    assert D84_LEAD not in _render_card(row)
