"""22-A Task 11 -- the CORRECTION path's latch dispatch (cases 17 and 31).

Task 11's SQL half shipped first: migration 0037's six columns and the
citation trigger that refuses a `latch_ladder` row whose evidence it cannot
verify.  This module is the SERVICE half -- `_authorize` resolving the tier
BEFORE the last-word guard, dispatching on it, and persisting the citation.

THE TWO CASES, AND WHY EACH EXISTS.

  * **Case 17 -- the exclusion parameter.**  On the CORRECTION path the
    subject trade's own entry fill already exists, and `_match_fill`'s windowed
    rung admits any NULL-candidate, same-ticker, in-zone entry -- so a probe
    that does NOT exclude the subject returns `clear_reason='fill'` for the
    very mandate it is being asked about and refuses.  The case is RE-BASED
    FOR OPTION C onto a POST-BARRIER synthetic: on trade 25 the correction
    would refuse `pre_barrier_unproven` at rung 9 and never reach the clause
    this case is written for.  **Both directions are executed** -- the
    exclusion admits, its omission returns `clear_reason='fill'` -- because a
    one-directional assertion cannot show the parameter is what decided it.

  * **Case 31 -- the criteria-drift REVEALING test.**  `candidate_criteria` is
    a SEPARATE table with NO barrier of its own (0001:47-55), and the
    hypothesis label is built from the non-pass criterion set.  So the
    pivot/stop cross-check can stay perfectly clean while the derived LABEL
    moves.  **This case pins a LIMITATION, not a guarantee** (plan S2.6 /
    L13); nobody may later read its green as proof the label is frozen.

FROZEN CLOCK.  Every session is an explicit date; nothing reads the wall clock.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.trades.cohort_provenance_correction import (
    CohortProvenanceCorrectionError,
    correct_cohort_provenance,
    preview_cohort_provenance_correction,
)
from tests._latch_link_fixtures_22a import insert_intent, place_row, validity_row
from tests.trades._cohort_provenance_fixtures import CADL_TICKER, build_cadl_case

# CADL's own geometry, from the live case the Demand-C fixtures reproduce.
FILL_SESSION = date(2026, 8, 12)
BARS_THROUGH = date(2026, 8, 11)        # the session BEFORE the fill
ANCHOR_SESSION = "2026-08-11"           # the fire's action session
FRAMEWORK_CAP = 11.13                   # mandate_limit_price(zone_cap(pivot))
ACCEPTED_QUANTITY = 19                  # the fill executes 19; 0 < 19 <= 19
ARCHIVE_CLOSE = 10.5                    # above the stop 9.161, below the pivot


def _cfg(root: Path) -> SimpleNamespace:
    """The reader's config surface, and the ONE scoring field it reaches.

    `structural_inputs_from_rows` -> `structural_gate_passes` reads
    `cfg.trend_template`, and CADL carries a FULL criterion roster (the probe
    world's bare fire does not), so this fixture must supply it or the
    derivation raises and the probe fail-closes to `aliveness_unverifiable` --
    a refusal for a reason unrelated to either case.  Values are production's,
    read off `swing.config.toml` `[trend_template]`.
    """
    from swing.config import TrendTemplate

    cache = root / "prices"
    cache.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=root / "swing.db"),
        pipeline=SimpleNamespace(observe_max_pending_window_sessions=30),
        trend_template=TrendTemplate(
            min_passes=7, allowed_miss_names=("TT8_rs_rank",),
            rising_ma_period_days=21, high_52w_margin_pct=25.0,
            low_52w_min_pct=30.0),
    )


def build_world(tmp_path: Path, name: str, *, closes=None) -> tuple:
    """CADL's citation graph, a POST-BARRIER minted link, and the archive.

    The link is never inserted by hand: the place + validity pair goes in and
    the 0037 minting trigger produces it, so this is real emitter output.  The
    fire is created AFTER the migration, so the epoch boundary sits below it
    and the link mints `live_at_acceptance` -- the post-barrier world case 17
    is re-based onto.
    """
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)
    conn = ensure_schema(root / "swing.db")
    ids = build_cadl_case(conn)
    run_id, candidate_id = ids["evaluation_run_id"], ids["candidate_id"]

    place = place_row(candidate_id, run_id=run_id)
    place.update(ticker=CADL_TICKER, detection_date=ANCHOR_SESSION,
                 action_session_date=ANCHOR_SESSION,
                 recorded_ts=ANCHOR_SESSION + "T12:00:00")
    place_id = insert_intent(conn, place)
    validity = validity_row(candidate_id, place_id, run_id=run_id)
    validity.update(ticker=CADL_TICKER, detection_date=ANCHOR_SESSION,
                    action_session_date=ANCHOR_SESSION,
                    recorded_ts=ANCHOR_SESSION + "T12:05:00",
                    actual_quantity=ACCEPTED_QUANTITY,
                    actual_limit_price=FRAMEWORK_CAP)
    validity_id = insert_intent(conn, validity)

    link = conn.execute(
        "SELECT link_id, broker_order_id, freeze_tier FROM "
        "latch_order_mandate_links").fetchone()
    assert link is not None and link[2] == "live_at_acceptance", (
        "the minting trigger produced " + repr(link) + "; case 17 is "
        "specified on a POST-BARRIER synthetic and a pre-barrier link would "
        "refuse at rung 9 for a reason unrelated to the exclusion parameter")

    # The fill must LOOK like the broker fill: the envelope is what
    # `resolve_latched_provenance` reads to find the order at all.
    fill_id = conn.execute(
        "SELECT fill_id FROM fills WHERE trade_id = ?",
        (ids["trade_id"],)).fetchone()[0]
    conn.execute(
        "UPDATE fills SET fill_origin = 'schwab_auto', "
        "schwab_source_value_json = ? WHERE fill_id = ?",
        (json.dumps({"schwab_order_id": link[1],
                     "schwab_instrument_symbol": CADL_TICKER}), fill_id))
    conn.commit()

    bars = {BARS_THROUGH: ARCHIVE_CLOSE} if closes is None else dict(closes)
    pd.DataFrame([
        {"asof_date": session.isoformat(), "open": close,
         "high": close + 0.1, "low": close - 0.1, "close": close,
         "volume": 100.0}
        for session, close in sorted(bars.items())
    ]).to_parquet(
        cfg.paths.prices_cache_dir / (CADL_TICKER + ".yfinance.parquet"))

    ids.update(place_intent_id=place_id, validity_intent_id=validity_id,
               link_id=link[0], broker_order_id=link[1], fill_id=fill_id)
    return conn, cfg, ids


def _apply(conn, cfg, ids, **over):
    kw = dict(trade_id=ids["trade_id"],
              cited_candidate_id=ids["candidate_id"],
              cited_recommendation_id=ids["daily_recommendation_id"],
              reason="22-A task 11 dispatch", cfg=cfg)
    kw.update(over)
    return correct_cohort_provenance(conn, **kw)


def _stored(conn, trade_id: int) -> dict:
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(provenance_corrections)")]
    row = conn.execute(
        "SELECT * FROM provenance_corrections WHERE trade_id = ?",
        (trade_id,)).fetchone()
    assert row is not None, "no correction row for trade " + str(trade_id)
    return dict(zip(cols, row, strict=True))


# ===========================================================================
# CASE 17 -- THE EXCLUSION PARAMETER, on a POST-BARRIER synthetic
# ===========================================================================
def test_the_correction_admits_at_the_latch_ladder_case_17(tmp_path) -> None:
    """PRE-FIX: `admission_tier='last_word'` and all five citations NULL --
    the service had no latch dispatch at all.  POST-FIX: `latch_ladder` with
    the link, both intents, the order id and the probe blob persisted.

    Both values are stated so the assertion distinguishes.
    """
    conn, cfg, ids = build_world(tmp_path, "c17")
    result = _apply(conn, cfg, ids)
    assert result.admission_tier == "latch_ladder"
    assert result.cited_latch_link_id == ids["link_id"]
    assert result.cited_latch_validity_intent_id == ids["validity_intent_id"]
    assert result.cited_latch_place_intent_id == ids["place_intent_id"]
    assert result.cited_latch_broker_order_id == ids["broker_order_id"]

    row = _stored(conn, ids["trade_id"])
    assert row["admission_tier"] == "latch_ladder"
    assert row["cited_latch_link_id"] == ids["link_id"]
    assert row["cited_latch_probe_json"] is not None
    blob = json.loads(row["cited_latch_probe_json"])
    assert blob["fire_candidate_id"] == ids["candidate_id"]
    assert blob["clear_reason"] is None
    assert blob["freeze_tier"] == "live_at_acceptance"


def test_omitting_the_exclusion_returns_clear_reason_fill_case_17(
        tmp_path) -> None:
    """THE DISCRIMINATOR, EXECUTED IN BOTH DIRECTIONS.

    The admitting half above proves the ladder can reach the fire.  This half
    proves the exclusion is WHAT DECIDED IT: the identical world probed
    WITHOUT `exclude_trade_ids` returns `mandate_not_alive` naming
    `clear_reason='fill'` -- the subject's own fill read as a consumption of
    the mandate it demonstrably came from.  An implementation that dropped the
    parameter passes the admitting assertion only if this one fails.
    """
    from swing.trades.latched_origin import (
        authorize_accepted_order,
        competitor_liveness_rung,
        find_accepted_latch_order,
    )

    conn, cfg, ids = build_world(tmp_path, "c17x")
    orders = find_accepted_latch_order(
        conn, broker_order_id=ids["broker_order_id"])
    assert len(orders) == 1
    kw = dict(order=orders[0], ticker=CADL_TICKER, fill_session=FILL_SESSION,
              price=10.81, shares=float(ACCEPTED_QUANTITY),
              fill_origin="schwab_auto", envelope_symbol=CADL_TICKER,
              trade_id=ids["trade_id"],
              competitor_rung=competitor_liveness_rung)

    with_exclusion = authorize_accepted_order(
        conn, cfg, exclude_trade_ids=frozenset({ids["trade_id"]}), **kw)
    without = authorize_accepted_order(
        conn, cfg, exclude_trade_ids=frozenset(), **kw)

    assert with_exclusion.admitted is True
    assert with_exclusion.clear_reason is None
    assert without.admitted is False
    assert without.decline_reason == "mandate_not_alive"
    assert without.clear_reason == "fill"
    assert without.clear_session == FILL_SESSION


def test_the_service_passes_the_subject_in_the_exclusion_set_case_17(
        tmp_path) -> None:
    """AND THE SERVICE IS WHAT PASSES IT.

    The two halves above establish the parameter's effect; this pins that the
    CORRECTION service supplies it, by spying on the resolver's arguments.
    Without it the admitting assertion could be satisfied by a resolver whose
    default happened to exclude the subject for some other reason.
    """
    import swing.trades.cohort_provenance_correction as mod
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, ids = build_world(tmp_path, "c17s")
    seen: list[dict] = []

    def spy(conn_, cfg_, req, **kw):
        seen.append(dict(kw))
        return resolve_latched_provenance(conn_, cfg_, req, **kw)

    original = mod.resolve_latched_provenance
    mod.resolve_latched_provenance = spy
    try:
        _apply(conn, cfg, ids)
    finally:
        mod.resolve_latched_provenance = original

    assert seen, "the correction service never consulted the latch resolver"
    assert seen[0]["exclude_trade_ids"] == frozenset({ids["trade_id"]})
    assert seen[0]["trade_id"] == ids["trade_id"]


# ===========================================================================
# AL-2 / 22A-R2-03 -- THE TWO LEDGER READS ARE ONE WORLD ONLY UNDER THE
# CALLER'S `BEGIN IMMEDIATE`, AND THE CALLER IS THIS SERVICE.
# ===========================================================================
def test_the_latch_resolution_runs_inside_the_correction_transaction(
        tmp_path) -> None:
    """PINNED BY A TEST, NEVER BY A COMMENT (#31).

    `resolve_latched_provenance` issues its own SELECTs and the derivation
    issues more; they are ONE world only if the caller holds a write
    reservation across both.  The predecessor's ledger recorded that as a
    PRECONDITION in prose, and a comment asserting an invariant its code does
    not hold is worse than no comment -- this arc has already caught one.  So
    the spy asserts `conn.in_transaction` AT THE MOMENT the resolver is
    called, on the WRITE path.
    """
    import swing.trades.cohort_provenance_correction as mod
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, ids = build_world(tmp_path, "al2")
    inside: list[bool] = []

    def spy(conn_, cfg_, req, **kw):
        inside.append(bool(conn_.in_transaction))
        return resolve_latched_provenance(conn_, cfg_, req, **kw)

    original = mod.resolve_latched_provenance
    mod.resolve_latched_provenance = spy
    try:
        _apply(conn, cfg, ids)
    finally:
        mod.resolve_latched_provenance = original

    assert inside == [True], (
        "the latch resolution ran OUTSIDE the correction's own transaction; "
        "the derivation and the ordering guard can then observe different "
        "ledger worlds (AL-2 / 22A-R2-03)")


# ===========================================================================
# CASE 31 -- THE CRITERIA-DRIFT REVEALING TEST
# ===========================================================================
def test_a_criterion_edited_after_minting_moves_the_label_case_31(
        tmp_path) -> None:
    """THIS CASE PINS A LIMITATION, NOT A GUARANTEE.

    The 0037 barrier freezes `candidates`; it does NOT freeze
    `candidate_criteria`, which `fetch_candidate_by_id` hydrates live and from
    which the hypothesis label's `failed:` suffix is built.  So a criterion
    edited between the acceptance and the correction moves the LABEL while the
    pivot/stop cross-check stays perfectly clean.

    The case asserts the change is VISIBLE in the recorded evidence.  It does
    NOT assert a refusal: with the third-table barrier declined (S4.5B) there
    is nothing to refuse on.  **Nobody may read this test's green as proof
    that the label is frozen** -- it proves the opposite, on purpose, so the
    gap is a recorded fact rather than a surprise.
    """
    conn, cfg, ids = build_world(tmp_path, "c31")

    # The label BEFORE the edit, from the framework's own builder.
    baseline = preview_cohort_provenance_correction(
        conn, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason="baseline", cfg=cfg,
    ).post_values["trades.hypothesis_label"]
    assert baseline == "A+ baseline (aplus); failed: TT8_rs_rank"

    # ONE criterion row edited -- the table the barrier does not reach.
    conn.execute(
        "UPDATE candidate_criteria SET result = 'pass' "
        "WHERE candidate_id = ? AND criterion_name = 'TT8_rs_rank'",
        (ids["candidate_id"],))
    conn.commit()

    result = _apply(conn, cfg, ids)
    row = _stored(conn, ids["trade_id"])
    blob = json.loads(row["cited_latch_probe_json"])

    # The cross-check is CLEAN: the frozen and live pivot/stop still agree.
    assert blob["invalidation_equal_at_dp"] == 1
    assert blob["pivot_equal_at_dp"] == 1
    assert blob["frozen_pivot_raw"] == blob["live_pivot_raw"]

    # And the LABEL has moved anyway.
    applied = json.loads(row["applied_value_json"])
    assert applied["trades.hypothesis_label"] == "A+ baseline (aplus)"
    assert applied["trades.hypothesis_label"] != baseline
    assert result.applied_values["trades.hypothesis_label"] == (
        "A+ baseline (aplus)")


# ===========================================================================
# THE DISPATCH ITSELF -- what the tier decides
# ===========================================================================
def test_the_latch_tier_skips_the_last_word_guard(tmp_path) -> None:
    """S2.7: under the latch ladder the last-word guard is NOT run.

    A LATER `watch` row for the same ticker is the framework's last word and
    would refuse the citation outright.  Under `latch_ladder` the citation is
    FORCED to the fire an append-only broker acceptance created, so there is
    nothing to rank and the guard is not consulted.  Without the skip this
    correction refuses; with it, it admits.
    """
    from tests.trades._cohort_provenance_fixtures import (
        seed_candidate,
        seed_evaluation_run,
    )

    conn, cfg, ids = build_world(tmp_path, "skiplw")
    later_run = seed_evaluation_run(
        conn, run_ts="2026-08-11T17:30:26", data_asof_date="2026-08-11",
        action_session_date="2026-08-12")
    seed_candidate(conn, evaluation_run_id=later_run, bucket="watch")
    conn.commit()

    result = _apply(conn, cfg, ids)
    assert result.admission_tier == "latch_ladder"
    assert result.cited_candidate_id == ids["candidate_id"]


def test_no_cfg_on_an_UNLINKED_fill_keeps_the_last_word_tier(tmp_path) -> None:
    """`cfg=None` is the pre-arc path byte-for-byte, WHERE THERE IS NO LATCH.

    Every existing Demand-C caller passes no config, so the resolver returns
    `no_config`, the ladder falls through to the last-word guard, and the row
    lands `last_word` with all five citations NULL.  This is what makes the
    whole existing suite a non-regression control rather than a rewrite -- and
    the fill's envelope is STRIPPED here, because that is the world those
    callers are actually in.
    """
    conn, _unused, ids = build_world(tmp_path, "nocfg")
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = NULL WHERE fill_id = ?",
        (ids["fill_id"],))
    conn.commit()
    result = _apply(conn, None, ids)
    assert result.admission_tier == "last_word"
    row = _stored(conn, ids["trade_id"])
    assert row["cited_latch_link_id"] is None
    assert row["cited_latch_probe_json"] is None


def test_no_cfg_on_a_LINKED_fill_is_refused_by_the_trigger(tmp_path) -> None:
    """22A-R6-04's correction half, closed STRUCTURALLY rather than by a rule.

    `cfg=None` maps to `no_config` and therefore to the `last_word` tier, so a
    caller who simply omitted the config could write a `last_word` correction
    on a fill whose own envelope names an accepted order -- the authority made
    caller-selectable.  MY OWN EARLIER TEST ASSERTED THAT THIS SUCCEEDS.

    It no longer can, and not because the service learned a new rule: the
    citation trigger's `last_word` branch now REQUIRES that the fill's order
    resolve to no link (22A-R6-01).  So the guarantee sits in the schema,
    where a caller cannot opt out of it, which is strictly better than a
    service-side check a second caller could forget.

    AND SINCE 22A-R7-01 THE SERVICE REFUSES FIRST, WHICH IS BETTER STILL.
    The resolver now RECOGNISES the order before consulting the config, so a
    linked fill with no config returns `recognised_but_underivable` and the
    correction refuses with a legible message naming `no_config` -- rather
    than authorizing and then aborting at the INSERT.  The schema belt is
    still there and still load-bearing (it is what closes the case for any
    RAW writer), and it is asserted separately below so a regression in either
    layer is named by its own failure.

    PRE-FIX: a `last_word` row landed.  POST-FIX: refused, nothing written.
    """
    conn, _unused, ids = build_world(tmp_path, "nocfglinked")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _apply(conn, None, ids)
    assert "no_config" in str(exc.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0

    # THE SCHEMA BELT IS EXERCISED SEPARATELY, not duplicated here.
    # `tests/data/test_22a_task11_citation_evidence.py`
    # `::test_a_last_word_DOWNGRADE_on_a_linked_fill_is_rejected` plants the
    # RAW row this service refusal would otherwise be the only guard against,
    # so a regression in either layer is named by its own failure rather than
    # hidden behind the other.


def test_a_recognised_but_refused_mandate_refuses_the_correction(
        tmp_path) -> None:
    """RECOGNISED-AND-REFUSED DOES NOT FALL BACK TO `last_word`.

    Falling back would let an operator correct a trade whose mandate the
    ladder refused -- citation shopping through the back door, on the one
    surface that exists to close it.  The refusal NAMES the decline reason so
    the operator can act on it.

    The world is mutated in ONE dimension: the fire's `initial_stop` is moved
    after minting, so the frozen/live cross-check disagrees.  The move goes
    through `candidates_barrier_lifted` -- the arc's own drop-and-restore-
    VERBATIM helper -- because 0037 makes `candidates` structurally immutable
    and that immutability is the proof this case is standing next to.  A raw
    UPDATE aborts; a hand-typed trigger restore would leave the admission
    reader comparing against a drifted body and refuse `barrier_not_installed`
    for a reason unrelated to the case.
    """
    from tests._candidates_barrier_helper import candidates_barrier_lifted

    conn, cfg, ids = build_world(tmp_path, "refuse")
    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET initial_stop = 8.00 WHERE id = ?",
                     (ids["candidate_id"],))
    conn.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _apply(conn, cfg, ids)
    assert "frozen_value_drift" in str(exc.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


def test_the_cited_candidate_must_be_the_links_fire(tmp_path) -> None:
    """S2.7: the cited candidate MUST equal the link's fire, else REFUSE.

    Under the latch ladder the citation is not the operator's to choose. A
    citation naming a DIFFERENT contemporaneous `aplus` row is refused with
    the fire named, rather than silently corrected to it.

    The competitor is seeded on its OWN evaluation run: `candidates` carries a
    uniqueness constraint per (run, ticker) and the 0037 barrier turns a
    conflicting INSERT into an abort, so "another row on the same run" is not
    a representable world.  An EARLIER run is, and it is also the world that
    makes the case sharp -- the earlier row is contemporaneous, so only the
    fire-identity clause can refuse it.
    """
    from tests.trades._cohort_provenance_fixtures import (
        seed_candidate,
        seed_evaluation_run,
        seed_recommendation,
    )

    # The archive is widened to the EARLIER fire's anchor: a second `aplus`
    # row on the ticker RE-ANCHORS the fold, so a single-session archive would
    # make the probe refuse `aliveness_unverifiable` and this case would be
    # blocked for a reason that has nothing to do with the fire-identity
    # clause it is written for.  MEASURED: the refusal reason was exactly that
    # before the widening.
    conn, cfg, ids = build_world(tmp_path, "wrongfire", closes={
        date(2026, 8, 7): ARCHIVE_CLOSE,
        date(2026, 8, 10): ARCHIVE_CLOSE,
        date(2026, 8, 11): ARCHIVE_CLOSE,
    })
    earlier_run = seed_evaluation_run(
        conn, run_ts="2026-08-07T17:30:26", data_asof_date="2026-08-06",
        action_session_date="2026-08-07")
    other = seed_candidate(
        conn, evaluation_run_id=earlier_run, bucket="aplus")
    other_dr = seed_recommendation(
        conn, evaluation_run_id=earlier_run, data_asof_date="2026-08-06",
        action_session_date="2026-08-07")
    conn.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _apply(conn, cfg, ids, cited_candidate_id=other,
               cited_recommendation_id=other_dr)
    assert str(ids["candidate_id"]) in str(exc.value)
    assert "FORCED" in str(exc.value)


def test_the_preview_reports_the_same_tier_as_the_apply(tmp_path) -> None:
    """ONE authorization function, two entry points.

    A dry run that reported `last_word` for a correction the apply writes as
    `latch_ladder` would show the operator a different decision from the one
    he is about to make.
    """
    conn, cfg, ids = build_world(tmp_path, "preview")
    preview = preview_cohort_provenance_correction(
        conn, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason="dry", cfg=cfg)
    assert preview.admission_tier == "latch_ladder"
    assert preview.cited_latch_link_id == ids["link_id"]
    assert preview.cited_latch_broker_order_id == ids["broker_order_id"]
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0

    result = _apply(conn, cfg, ids)
    assert result.admission_tier == preview.admission_tier
    assert result.cited_latch_link_id == preview.cited_latch_link_id


def test_the_service_blob_survives_the_shipped_citation_trigger(
        tmp_path) -> None:
    """THE SERVICE'S OWN BLOB PASSES THE SHIPPED TRIGGER.

    Task 11's SQL half proved the trigger is SATISFIABLE from a hand-built
    payload.  This proves the SERVICE builds one it accepts -- the
    synthetic-fixture-vs-production-emitter gap, closed in the direction that
    matters: a service whose blob the trigger rejects has no correction path
    at all.
    """
    conn, cfg, ids = build_world(tmp_path, "trigger")
    _apply(conn, cfg, ids)
    row = _stored(conn, ids["trade_id"])
    assert row["admission_tier"] == "latch_ladder"
    # The trigger fired on INSERT; the row's presence IS the proof.
    assert isinstance(row["cited_latch_probe_json"], str)


def test_an_inverted_window_refuses_on_the_LATCH_path_too(tmp_path) -> None:
    """22A-R3-07: the inverted-window check is about the RECORD.

    A pipeline run that FINISHED before its own evaluation run STARTED bounds
    nothing, whoever is asking.  The check lived in the fill-specific `gate`,
    and the latch path passes `gate=None` -- so PRE-FIX this correction
    ADMITTED at `latch_ladder` and derived its label from an inverted window
    in silence.  POST-FIX it refuses, and the message names the inversion.

    The control is the SAME world through the LAST-WORD tier -- and it is
    reached by STRIPPING THE ENVELOPE, not by passing `cfg=None`.  Since
    22A-R7-01 a linked fill with no config is RECOGNISED and refuses
    `no_config` before the derivation ever runs, so a `cfg=None` control would
    pass for a reason unrelated to the inverted window.  Without the control
    at all, a fix that moved the check somewhere unreachable could pass by
    breaking both paths for different reasons.
    """
    conn, cfg, ids = build_world(tmp_path, "r307")
    run_ts = conn.execute(
        "SELECT run_ts FROM evaluation_runs WHERE id = ?",
        (ids["evaluation_run_id"],)).fetchone()[0]
    conn.execute(
        "UPDATE pipeline_runs SET finished_ts = '2026-08-10T17:00:00' "
        "WHERE evaluation_run_id = ?", (ids["evaluation_run_id"],))
    conn.commit()
    assert run_ts > "2026-08-10T17:00:00", (
        "the fixture must INVERT the window or the case pins nothing")

    with pytest.raises(CohortProvenanceCorrectionError) as latch:
        _apply(conn, cfg, ids)
    # The latch path reports it as `keys_not_derivable`, which is the resolver's
    # own name for "the shared derivation refused": `_cohort_keys_for_fire`
    # catches any refusal so cohort bookkeeping can never block an ENTRY, and
    # the CORRECTION path then refuses on the recognised-but-underivable
    # verdict.  The inner message is on the WARNING record; what matters here
    # is that the correction is REFUSED at all, which pre-fix it was not.
    assert "keys_not_derivable" in str(latch.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0

    control, _unused, control_ids = build_world(tmp_path, "r307ctl")
    control.execute(
        "UPDATE pipeline_runs SET finished_ts = '2026-08-10T17:00:00' "
        "WHERE evaluation_run_id = ?", (control_ids["evaluation_run_id"],))
    control.execute(
        "UPDATE fills SET schwab_source_value_json = NULL WHERE fill_id = ?",
        (control_ids["fill_id"],))
    control.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as last_word:
        _apply(control, None, control_ids)
    assert "inverted" in str(last_word.value)
