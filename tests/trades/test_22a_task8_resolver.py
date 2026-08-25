"""22-A Task 8 -- ``resolve_latched_provenance``, and the reason roster closes.

Cases 18 and 5c, plus the two closure checks the plan attaches to the
thirty-three-member decline roster (S5.1): every member is exercised by a
named case, AND a STATIC walk of the module's own return sites asserts every
reason string it constructs is a member.  The second is the load-bearing half
-- a hand-enumerated roster is the same instrument as the count it replaced and
fails the same way.

FROZEN CLOCK: every session is an explicit date.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from swing.data.db import ensure_schema
from swing.trades import latched_origin
from swing.trades.latched_origin import (
    DECLINE_REASONS,
    resolve_latched_provenance,
)
from tests._latch_probe_world_22a import (
    BASE_CLOSES,
    BROKER_ORDER_ID,
    FILL_SESSION,
    TICKER,
    accept_and_link,
    probe_cfg,
    seed_fire,
    write_closes,
)

ACCEPT_SESSION = date(2026, 7, 24)


def _req(**over) -> SimpleNamespace:
    """The fields the resolver reads off an ``EntryRequest``, and only those.

    A ``SimpleNamespace`` rather than a real ``EntryRequest`` because the
    resolver's contract IS this field set: building the full request would
    hide which fields it actually depends on, and task 9 wires the real one.
    """
    fields = {
        "ticker": TICKER,
        "entry_date": FILL_SESSION.isoformat(),
        "entry_price": 18.50,
        "shares": 2,
        "fill_origin": "schwab_auto",
        "hypothesis_label": None,
        "schwab_source_value_json": json.dumps(
            {"schwab_order_id": BROKER_ORDER_ID,
             "schwab_instrument_symbol": TICKER}),
    }
    fields.update(over)
    return SimpleNamespace(**fields)


def build_world(tmp_path: Path, name: str):
    """A fire, its archive, AND the two things the SHARED derivation needs.

    THE PROBE WORLD IS NOT ENOUGH, and the difference is the point of the
    extraction.  ``derive_cohort_keys_for_fire`` opens at rung 16 -- the
    evaluation run's PERSISTENCE BOUND -- so the fire's run must own a COMPLETE
    ``pipeline_runs`` row, and rung 17 reads the hypothesis registry AS OF that
    window, so the seeded status intervals must be CONTEMPORANEOUS rather than
    carrying the migration's own apply-time stamp (which is TODAY, a backdated
    assertion the surface refuses by design).

    Measured rather than assumed: without the pipeline row the resolver
    returns ``keys_not_derivable`` -- *"evaluation run 121 has no single
    COMPLETE pipeline_runs row with a finished_ts"* -- which is the correct
    fail-closed degrade and would have made every admit assertion here pass for
    the wrong reason if it had been the expected outcome.
    """
    from tests.trades._cohort_provenance_fixtures import (
        rebase_status_history_recorded_at,
        seed_pipeline_run,
    )

    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root)
    conn = ensure_schema(root / "swing.db")
    candidate_id = seed_fire(conn)
    run = conn.execute(
        "SELECT data_asof_date, action_session_date FROM evaluation_runs "
        "WHERE id = 121").fetchone()
    seed_pipeline_run(
        conn, evaluation_run_id=121, data_asof_date=run[0],
        action_session_date=run[1],
        started_ts=f"{run[0]}T17:30:26",
        finished_ts=f"{run[0]}T17:44:45")
    rebase_status_history_recorded_at(conn)
    conn.commit()
    write_closes(cfg, BASE_CLOSES)
    return conn, cfg, candidate_id


# ===========================================================================
# CASE 18 -- the two preliminary declines carry their OWN reason
# ===========================================================================
def test_no_config_and_no_order_id_decline_with_their_own_reasons_case_18(
        tmp_path) -> None:
    """CASE 18 -- lens clause 21.

    ``cfg=None`` and an envelope WITHOUT the key are different ignorances.  A
    shared reason would tell an operator only that the ladder did not run, and
    the two have different remedies (pass the config; re-fetch the order).

    NEITHER is ``recognised_but_underivable``: no link was recognised, so the
    ordinary candidate/origin chain must still run.  That flag is what
    SUPPRESSES it, and setting it here would write honest-unset keys for a
    trade the framework knows nothing unusual about.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case18")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)

        no_cfg = resolve_latched_provenance(conn, None, _req())
        assert no_cfg.decline_reason == "no_config"
        assert no_cfg.recognised_but_underivable is False

        no_key = resolve_latched_provenance(
            conn, cfg, _req(schwab_source_value_json=json.dumps(
                {"schwab_instrument_symbol": TICKER})))
        assert no_key.decline_reason == "no_order_id"
        assert no_key.recognised_but_underivable is False

        absent = resolve_latched_provenance(
            conn, cfg, _req(schwab_source_value_json=None))
        assert absent.decline_reason == "no_envelope"
        assert absent.recognised_but_underivable is False

        unmatched = resolve_latched_provenance(
            conn, cfg, _req(schwab_source_value_json=json.dumps(
                {"schwab_order_id": "not-a-real-order",
                 "schwab_instrument_symbol": TICKER})))
        assert unmatched.decline_reason == "no_accepted_latch_order"
        assert unmatched.recognised_but_underivable is False
    finally:
        conn.close()


# ===========================================================================
# CASE 5c -- the fill session is the CORRECTED date
# ===========================================================================
def test_the_fill_session_is_req_entry_date_and_nothing_else_case_5c(
        tmp_path) -> None:
    """CASE 5c -- lens clause 8.  THE CORRECTED-DATE DISCRIMINATOR.

    The resolver probes as of ``req.entry_date``.  Two submissions differing
    ONLY in that field must reach different verdicts, or the field is not
    being read: here the mandate is alive at 2026-07-27 and its horizon has
    expired by 2026-09-15.

    An implementation reading ``trades.entry_date`` -- the value being
    CORRECTED on the correction path -- or the wall clock probes a different
    world and can admit a mandate that was dead when the fill happened.  The
    two dates are the whole assertion; every other field is identical.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case5c")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        near = resolve_latched_provenance(conn, cfg, _req())
        assert near.admitted is True, near.decline_reason
        assert near.horizon_session == FILL_SESSION

        far = resolve_latched_provenance(
            conn, cfg, _req(entry_date="2026-09-15"))
        assert far.admitted is False
        assert far.horizon_session == date(2026, 9, 15)
        assert far.decline_reason == "mandate_not_alive"
        assert far.clear_reason == "horizon"
    finally:
        conn.close()


def test_a_malformed_entry_date_is_recognised_and_refused(tmp_path) -> None:
    """A RECOGNISED request that cannot be probed does NOT fall through.

    NO CASE ID.  An order id WAS supplied, so treating an unparseable date as
    "no link here" would run the ordinary chain and write TODAY's candidate for
    a fill the framework knows came from a specific mandate -- silent-wrong
    rather than honest-NULL.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "baddate")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        verdict = resolve_latched_provenance(
            conn, cfg, _req(entry_date="not-a-date"))
        assert verdict.admitted is False
        assert verdict.recognised_but_underivable is True
        assert verdict.decline_reason == "fill_session_not_a_session"
    finally:
        conn.close()


def test_an_admitted_resolution_carries_all_three_cohort_keys(tmp_path) -> None:
    """THE THREE KEYS MOVE TOGETHER OR NOT AT ALL (S2.6).

    NO CASE ID -- cases 1-3 and 5-6 are task 9's, at the persisted-row grain.
    This is the resolver-level property they rest on, and it is the one that
    fails if the shared derivation is wired in but its output is dropped.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "keys")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        verdict = resolve_latched_provenance(conn, cfg, _req())
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.candidate_id == candidate_id
        assert verdict.trade_origin == latched_origin.aplus_trade_origin()
        assert verdict.hypothesis_label
        assert verdict.hypothesis_label.startswith("A+ baseline")
    finally:
        conn.close()


def test_a_refused_resolution_carries_NO_cohort_keys(tmp_path) -> None:
    """AND THE CONVERSE, which is what SUPPRESSION means.

    NO CASE ID.  A recognised-but-refused verdict leaves all three keys NULL:
    the caller writes ``manual_off_pipeline`` + NULL + NULL rather than falling
    back to the ordinary chain, which would write TODAY's candidate.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "nokeys")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        verdict = resolve_latched_provenance(
            conn, cfg, _req(entry_date="2026-09-15"))
        assert verdict.recognised_but_underivable is True
        assert (verdict.candidate_id, verdict.hypothesis_label,
                verdict.trade_origin) == (None, None, None)
    finally:
        conn.close()


# ===========================================================================
# THE DECLINE-REASON ROSTER CLOSES, IN BOTH DIRECTIONS
# ===========================================================================
_MODULE = Path(latched_origin.__file__)


def _constructed_reason_strings() -> set[str]:
    """Every reason string the module CONSTRUCTS, by a STATIC ast walk.

    Not a grep and not a run trace.  A grep would need the right pattern and a
    trace only sees the branches a fixture happened to take -- which is exactly
    how eleven cases stayed invisible through two reviews and a self-sweep.
    The walk collects the string literal passed as the ``reason`` argument to
    ``_refuse`` / ``_probe_refusal``, the ``decline_reason=`` keyword on a
    ``LatchedProvenance`` construction, and any bare string returned by
    ``assert_fill_consistent_with_order``.
    """
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"), filename=str(_MODULE))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in {"_refuse", "_probe_refusal"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(
                        first.value, str):
                    found.add(first.value)
            for kw in node.keywords:
                if kw.arg == "decline_reason" and isinstance(
                        kw.value, ast.Constant) and isinstance(
                        kw.value.value, str):
                    found.add(kw.value.value)
        if isinstance(node, ast.Return):
            # A BARE STRING **OR** A TUPLE'S FIRST ELEMENT.  The rungs that
            # also return their scanned input -- rung 8 and the decision
            # ordering guard -- return `(reason, ids)`, and a walk that read
            # only bare returns reported FOUR roster members as unemittable
            # while the code emits all four.  Found by running the check, which
            # is the whole argument for a static walk over a maintained list:
            # the list would have agreed with the walk and both been wrong.
            # ONLY THE FIRST ELEMENT.  `_fill_wins` returns
            # `(alive, admission_basis)` -- 'armed' and
            # 'subject_fill_wins_same_session_tie' are ADMISSION BASES, not
            # decline reasons, and a walk over every element reported both as
            # stray members.  The reason always sits in position zero, which is
            # a convention this assertion now pins.
            for value in (
                [node.value] if not isinstance(node.value, ast.Tuple)
                else node.value.elts[:1]
            ):
                if isinstance(value, ast.Constant) and isinstance(
                        value.value, str):
                    found.add(value.value)
    return found


def test_every_reason_the_module_constructs_is_a_roster_member() -> None:
    """THE LIST IS NOT THE FIX; THE CLOSURE CHECK IS.

    A reason the code can emit but the roster does not name would pass every
    ``__post_init__`` validation the frozenset performs -- because the
    validation reads the roster -- while no case could ever be written for it.
    """
    stray = sorted(_constructed_reason_strings() - DECLINE_REASONS)
    assert not stray, (
        f"latched_origin constructs decline reasons the 33-member roster does "
        f"not name: {stray}")


def test_the_roster_has_no_member_no_rung_can_emit() -> None:
    """AND THE OTHER DIRECTION, which is the half a one-directional check
    misses.

    A member nothing can emit is a roster entry whose case would have to be
    written against DEAD CODE -- the exact defect SELF-SWEEP SS-06 found when
    ``quantity_mismatch`` survived the rung that used to produce it.

    THE EXCLUSION SET IS EMPTY AND THAT IS AN ASSERTION, not an omission:
    every one of the thirty-three is emittable from THIS module as of task 8.
    A later task adding a reason nothing emits fails here rather than shipping
    a roster member whose case would be written against dead code.
    """
    owed_by_a_later_task: frozenset[str] = frozenset()
    emitted = _constructed_reason_strings() & DECLINE_REASONS
    unemitted = sorted(DECLINE_REASONS - emitted - owed_by_a_later_task)
    assert not unemitted, (
        f"{len(unemitted)} roster members nothing in latched_origin can emit: "
        f"{unemitted}. Either a rung is missing or the roster carries a dead "
        f"member whose case would be written against dead code.")


def test_the_roster_size_is_stated_and_counted_by_reading_it() -> None:
    """THIRTY-THREE, counted from the members and not from a grep.

    The plan records why the method has to be stated: a ``^[a-z_]+$`` regex
    over an earlier version of this block returned one FEWER than the read,
    because one member contained a DIGIT -- a regex under-counting a roster in
    the very act of fixing an under-count.
    """
    assert len(DECLINE_REASONS) == 33
    source = _MODULE.read_text(encoding="utf-8")
    block = source.split("DECLINE_REASONS: frozenset[str] = frozenset({", 1)[1]
    block = block.split("})", 1)[0]
    literals = re.findall(r'"([a-z0-9_]+)"', block)
    assert sorted(literals) == sorted(DECLINE_REASONS)
    assert len(literals) == len(set(literals)), "a duplicated member"


@pytest.mark.parametrize("reason", sorted(DECLINE_REASONS))
def test_every_roster_member_is_accepted_by_the_verdict_validator(
        reason: str) -> None:
    """And the validator's frozenset IS the roster, not a second copy."""
    verdict = latched_origin.LatchedProvenance(
        admitted=False, recognised_but_underivable=True, decline_reason=reason)
    assert verdict.decline_reason == reason
