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
