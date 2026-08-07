"""T3 -- the per-session STRUCTURAL verdict reader (item 3b, Task 4).

The pure T4 fixtures can all pass while the SQL feeds the fold the wrong data,
so these exercise the reader functions directly against a real schema.

Two rules every test here is written against, because each naive alternative is
unsafe in its own direction:

* **generous PASS / strict FAIL.** Any verifiable pass RESETS (keeping a mandate
  alive is the conservative outcome); only the LATEST RUN's verifiable failure
  INCREMENTS (withdrawal is what can destroy a trade).
* **the latest RUN, not the latest ROW.** The ordinary off-screen case is a
  later run that carries no row for the ticker at all.
"""
from __future__ import annotations

from datetime import date

import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.latches.reader import (
    load_session_structural_verdicts,
    structural_inputs_from_rows,
)

_TT = ("TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
       "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
       "TT7_within_52w_high_25pct", "TT8_rs_rank")
_VCP = ("adr", "ma_short_rising", "ma_stack_10_20_50", "orderliness",
        "prior_trend", "proximity_20ma", "pullback", "tightness",
        "vcp_volume_contraction")


@pytest.fixture
def cfg():
    from pathlib import Path
    return load(Path(__file__).resolve().parents[2] / "swing.config.toml")


def _rows(*, tt_fail=(), vcp_fail=(), tt_na=(), risk="pass", drop=()):
    """The full 18-criterion roster with named exceptions."""
    out = []
    for n in _TT:
        if n in drop:
            continue
        result = "fail" if n in tt_fail else ("na" if n in tt_na else "pass")
        out.append((n, "trend_template", result))
    for n in _VCP:
        if n in drop:
            continue
        out.append((n, "vcp", "fail" if n in vcp_fail else "pass"))
    if "risk_feasibility" not in drop:
        out.append(("risk_feasibility", "risk", risk))
    return out


def _run(conn, rid, action, run_ts):
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
        (rid, run_ts, action, action))


def _candidate(conn, rid, ticker, bucket, rows):
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, rs_method) "
        "VALUES (?, ?, ?, 15.0, 16.9, 13.4, 4.021, 'universe')",
        (rid, ticker, bucket))
    cid = int(cur.lastrowid)
    for name, layer, result in rows:
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, "
            "layer, result) VALUES (?, ?, ?, ?)", (cid, name, layer, result))
    return cid


@pytest.fixture
def db(tmp_path):
    return ensure_schema(tmp_path / "t.db")


def _verdicts(conn, cfg, ticker="VSTS", start="2026-07-27", end="2026-07-31"):
    return load_session_structural_verdicts(
        conn, cfg, tickers=[ticker],
        start=date.fromisoformat(start), end=date.fromisoformat(end),
    ).get(ticker, ())


# ---------------------------------------------------------------------------
# structural_inputs_from_rows -- the roster check (T2.4/T2.5 at the reader)
# ---------------------------------------------------------------------------
def test_zero_rows_is_a_sentinel_not_a_failure(cfg):
    """T2.4/T3 -- an `excluded` (held-position) or `error` row. The evaluator
    synthesises those with `criteria=()`.

    Counting it FAILED would let the framework withdraw a mandate BECAUSE the
    operator took the position it recommended. In practice the `fill` clear
    usually pre-empts it, but the rule must be right independently rather than
    correct-by-luck through another rule's precedence.
    """
    inputs, cause = structural_inputs_from_rows(())
    assert inputs is None and cause == "sentinel_row"


def test_a_missing_FAILING_vcp_row_is_unverifiable_not_a_pass(cfg):
    """T2.5(a). Discriminator: WITHOUT the roster check `vcp_fail_count == 0`
    and the gate falsely PASSES -- the framework asserting a mandate is sound
    from a criterion set it never saw."""
    rows = [r for r in _rows(vcp_fail=("tightness",))
            if r[0] != "tightness"]
    inputs, cause = structural_inputs_from_rows(rows)
    assert inputs is None and cause == "incomplete_roster"


def test_missing_PASSING_tt_rows_are_unverifiable_not_a_failure(cfg):
    """T2.5(b), and the fixture is built to CROSS `min_passes` (7 of 8) --
    a single arbitrary missing TT row does not necessarily cross it, and then
    the test would not discriminate.

    Discriminator: without the check `tt_pass_count` drops to 5, the gate
    falsely FAILS, and a false failure paired with the price conjunct can clear
    a LIVE mandate.
    """
    rows = _rows(drop=("TT1_above_150_200", "TT2_150_above_200",
                       "TT3_200_rising"))
    assert sum(1 for r in rows if r[1] == "trend_template") == 5
    inputs, cause = structural_inputs_from_rows(rows)
    assert inputs is None and cause == "incomplete_roster"


def test_an_unexpected_criterion_name_is_unverifiable(cfg):
    """T2.5(c). A renamed or added criterion changes what the gate MEANS."""
    rows = _rows() + [("vcp_brand_new_thing", "vcp", "pass")]
    inputs, cause = structural_inputs_from_rows(rows)
    assert inputs is None and cause == "incomplete_roster"


def test_a_malformed_result_degrades_and_does_not_raise(cfg):
    """T3.8. The schema CHECK forbids it, so this is reachable only through a
    corrupt DB -- but the reader must degrade, never 500 the panel."""
    rows = [(n, l, "PASS" if n == "adr" else r) for n, l, r in _rows()]
    inputs, cause = structural_inputs_from_rows(rows)
    assert inputs is None and cause == "malformed_result"


def test_the_risk_layer_is_excluded_from_the_reduction(cfg):
    """T3.6 / L4 at the reader. A risk FAILURE beside a perfect structure still
    reduces to a PASSING gate -- the operator's capital may not withdraw his
    own mandate."""
    from swing.evaluation.scoring import structural_gate_passes

    inputs, cause = structural_inputs_from_rows(_rows(risk="fail"))
    assert cause is None
    assert structural_gate_passes(inputs, cfg) is True


# ---------------------------------------------------------------------------
# load_session_structural_verdicts -- the asymmetric session rule
# ---------------------------------------------------------------------------
def test_an_empty_ticker_list_issues_no_sql(db, cfg):
    """T3.7. The empty `IN ()` gotcha, and the shipped reader convention
    (`load_entry_records` / `load_last_closes` both short-circuit).

    A sentinel connection proves NO SQL was issued rather than merely that the
    result was empty -- an implementation that ran the query and filtered
    afterwards would satisfy the equality but not the contract.
    """
    class _Explodes:
        def execute(self, *a, **k):        # pragma: no cover -- must not run
            raise AssertionError("issued SQL for an empty ticker list")

    assert load_session_structural_verdicts(
        _Explodes(), cfg, tickers=[],
        start=date(2026, 7, 27), end=date(2026, 7, 31)) == {}


def test_only_runs_inside_the_window_are_considered(db, cfg):
    """T3.1."""
    with db:
        _run(db, 1, "2026-07-24", "2026-07-23T17:30:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 2, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg)
    assert [v.action_session for v in got] == [date(2026, 7, 28)]


def test_a_session_with_NO_run_at_all_is_outside_the_domain(db, cfg):
    """T3.5. There is no evaluation run for 2026-08-05 on the live DB. The
    framework was not RUNNING -- a fact about the pipeline, not about this
    mandate -- so it is not counted and not rendered as unchecked."""
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-07-30", "2026-07-29T17:30:00")
        _candidate(db, 2, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg)
    # 2026-07-29 is a trading session and simply has no run.
    assert [v.action_session for v in got] == [
        date(2026, 7, 28), date(2026, 7, 30)]


def test_a_ticker_absent_from_a_run_is_UNVERIFIABLE_not_a_fabricated_verdict(
        db, cfg):
    """T3.4. RD's inverted default: the framework cannot check a mandate it
    cannot see, and it must not assert one it never checked."""
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "OTHER", "watch", _rows())
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [
        ("UNVERIFIABLE", "absent")]


def test_an_excluded_held_position_row_is_UNVERIFIABLE_not_FAILED(db, cfg):
    """T4.4 at the reader. The moment the operator takes a position his ticker
    becomes `bucket='excluded'` with ZERO criteria rows.

    Discriminator: an implementation whose predicate is `bucket != 'aplus'`
    calls this a structural FAILURE and advances the streak -- withdrawing the
    mandate because he acted on it.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "VSTS", "excluded", [])
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [
        ("UNVERIFIABLE", "sentinel_row")]


def test_an_earlier_PASS_beats_a_later_sentinel_within_the_session(db, cfg):
    """T3.2 -- the GENEROUS half, scoped to WITHIN a session (OQ-18's ratified
    half): a non-check cannot erase a check.

    Discriminator: a 'latest row wins' implementation returns UNVERIFIABLE, the
    streak fails to reset, and the latch moves toward withdrawal on the strength
    of a run that never looked at it.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T09:00:00")
        _candidate(db, 1, "VSTS", "aplus", _rows())
        _run(db, 2, "2026-07-28", "2026-07-27T18:00:00")
        _candidate(db, 2, "VSTS", "excluded", [])
    got = _verdicts(db, cfg)
    assert [v.classification for v in got] == ["PASSED"]


def test_an_earlier_FAIL_followed_by_a_sentinel_is_UNVERIFIABLE_not_FAILED(
        db, cfg):
    """T3.3 -- the STRICT half. Together with T3.2 this pins the asymmetry;
    either alone is satisfied by one of the two naive rules.

    Discriminator: a 'latest VERIFIABLE row wins' implementation returns FAILED
    and advances the streak on evidence the most recent run contradicts.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T09:00:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-07-28", "2026-07-27T18:00:00")
        _candidate(db, 2, "VSTS", "excluded", [])
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [
        ("UNVERIFIABLE", "sentinel_row")]


def test_the_strict_half_keys_on_the_latest_RUN_not_the_latest_ROW(db, cfg):
    """T3.12 -- THE ORDINARY OFF-SCREEN CASE, not an edge case.

    A 09:00 run records a verifiable FAILURE; the 18:00 run carries NO row for
    the ticker at all (it went off-screen). The latest ROW belonging to the
    ticker is still the 09:00 failure.

    Discriminator: a row-keyed implementation returns FAILED and, repeated over
    N sessions, clears a mandate on evidence no current run supports.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T09:00:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-07-28", "2026-07-27T18:00:00")
        _candidate(db, 2, "OTHER", "watch", _rows())
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [
        ("UNVERIFIABLE", "absent")]


def test_the_run_order_is_run_ts_then_evaluation_run_id(db, cfg):
    """T3.14. Two runs for one session sharing an identical `run_ts`: the LOWER
    id carries a verifiable FAILING row, the HIGHER carries none.

    Discriminator: an implementation ordering by `(run_ts, candidate_id)` cannot
    break the tie at all -- the later run has NO candidate_id for this ticker --
    and falls back to the failing row.
    """
    with db:
        _run(db, 5, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 5, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 6, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 6, "OTHER", "watch", _rows())
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [
        ("UNVERIFIABLE", "absent")]


def test_an_earlier_PASS_and_a_later_verified_FAIL_resolve_PASSED(db, cfg):
    """T3.10 -- THE OVERLAP. The session satisfies BOTH predicates ('any pass'
    and 'the latest run verifiably failed').

    OQ-15 RULED: a session holding conflicting VERIFIED verdicts is AMBIGUOUS,
    and ambiguity must never advance a withdrawal -- the conservative direction
    is keep-alive.

    Discriminator: reading the rule table top-to-bottom without noticing the
    overlap classifies it FAILED and advances the streak.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T09:00:00")
        _candidate(db, 1, "VSTS", "aplus", _rows())
        _run(db, 2, "2026-07-28", "2026-07-27T18:00:00")
        _candidate(db, 2, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg)
    assert [v.classification for v in got] == ["PASSED"]


def test_a_same_session_verified_conflict_is_SURFACED_not_silently_resolved(
        db, cfg):
    """T3.15 -- OQ-15's ADDITION, and the half a generous resolution alone
    would swallow.

    RD's requirement is that the ambiguity be REPORTED: two runs for one session
    disagreeing on the STRUCTURAL verdict is a fact about the PIPELINE, not a
    tie to be quietly broken. This asserts the READER's flag and NOTHING about
    the card -- the card is Task 7's job, and asserting it here would stop Task
    4 being a standalone green commit.

    Discriminator: an implementation that resolves generously and says nothing
    passes every other assertion in this file.
    """
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T09:00:00")
        _candidate(db, 1, "VSTS", "aplus", _rows())
        _run(db, 2, "2026-07-28", "2026-07-27T18:00:00")
        _candidate(db, 2, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 3, "2026-07-29", "2026-07-28T17:30:00")
        _candidate(db, 3, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg)
    assert [v.classification for v in got] == ["PASSED", "FAILED"]
    assert [v.conflicted for v in got] == [True, False]


def test_the_verdicts_carry_the_ACTION_SESSION_date(db, cfg):
    """T3.9. The streak's domain is action sessions; a verdict stamped with a
    `data_asof_date` would silently shift the whole sequence by a session."""
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        db.execute("UPDATE evaluation_runs SET data_asof_date='2026-07-27' "
                   "WHERE id=1")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg)
    assert got[0].action_session == date(2026, 7, 28)
    assert got[0].classification == "FAILED"


def test_a_verified_failure_at_the_only_run_is_FAILED(db, cfg):
    """The positive control. Without it every UNVERIFIABLE assertion above
    would pass under an implementation that NEVER returns FAILED."""
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness", "adr")))
    got = _verdicts(db, cfg)
    assert [(v.classification, v.cause) for v in got] == [("FAILED", None)]


def test_two_tickers_slice_the_same_run_sequence_independently(db, cfg):
    """Per-TICKER, not per-latch: two latches on one ticker slice the SAME
    sequence by their own windows, so the reader can never disagree with itself
    between two latches on one ticker."""
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _candidate(db, 1, "FTRE", "aplus", _rows())
    got = load_session_structural_verdicts(
        db, cfg, tickers=["VSTS", "FTRE"],
        start=date(2026, 7, 27), end=date(2026, 7, 31))
    assert got["VSTS"][0].classification == "FAILED"
    assert got["FTRE"][0].classification == "PASSED"


def test_the_fire_row_carries_its_own_adr_pct(db, cfg):
    """The `_FIRE_SQL` half of Task 4. A per-ROW value, so no gotcha-#30
    exposure -- and the one input the materiality floor scales by.

    Discriminator: an implementation that adds the FIELD but forgets the SELECT
    passes every hand-built FireRow fixture while production marks every latch
    directionally unverifiable and the feature never fires at all.
    """
    from swing.latches.reader import load_fire_rows

    with db:
        _run(db, 1, "2026-07-27", "2026-07-24T17:30:00")
        _candidate(db, 1, "VSTS", "aplus", _rows())
    fires = load_fire_rows(db)
    assert len(fires) == 1
    assert fires[0].adr_pct == pytest.approx(4.021)


def test_a_TEXT_adr_pct_does_not_drop_the_whole_fire(db, cfg):
    """The reader's degrade-don't-drop contract, applied to the new column.
    SQLite holds TEXT in a REAL column, and an eager float() here would raise
    and lose a real A+ fire -- the mandate would vanish from the panel."""
    from swing.latches.reader import load_fire_rows

    with db:
        _run(db, 1, "2026-07-27", "2026-07-24T17:30:00")
        _candidate(db, 1, "VSTS", "aplus", _rows())
        db.execute("UPDATE candidates SET adr_pct = 'bad'")
    fires = load_fire_rows(db)
    assert len(fires) == 1                 # the fire SURVIVES
    assert fires[0].adr_pct == "bad"       # raw, for the resolver to refuse


def test_the_verdict_value_type_refuses_an_incoherent_cause():
    """The construction barrier. A cause explains an UNVERIFIABLE and nothing
    else -- a verified verdict carrying one would let the detail line state a
    reason for a session the framework actually checked."""
    from swing.latches.models import SessionStructuralVerdict

    with pytest.raises(ValueError):
        SessionStructuralVerdict(
            action_session=date(2026, 7, 28), classification="PASSED",
            cause="absent")
    with pytest.raises(ValueError):
        SessionStructuralVerdict(
            action_session=date(2026, 7, 28), classification="UNVERIFIABLE")
    with pytest.raises(ValueError):
        SessionStructuralVerdict(
            action_session=date(2026, 7, 28), classification="MAYBE")


# ---------------------------------------------------------------------------
# T5.6 -- THE PRODUCTION PATH (Task 5c)
# ---------------------------------------------------------------------------
def _seed_lapse_geometry(conn):
    """A latch that qualifies: an A+ fire, then five structurally FAILING
    evaluated sessions whose archive closes decay past the materiality floor."""
    from datetime import timedelta

    from swing.evaluation.dates import session_offset

    anchor = date(2026, 7, 27)
    days = [anchor]
    while len(days) < 6:
        days.append(session_offset(days[-1], 1))
    _run(conn, 100, days[0].isoformat(), "2026-07-24T17:30:00")
    _candidate(conn, 100, "VSTS", "aplus", _rows())
    for i, d in enumerate(days[1:], start=1):
        _run(conn, 100 + i, d.isoformat(), f"{days[i - 1].isoformat()}T17:30:00")
        _candidate(conn, 100 + i, "VSTS", "watch",
                   _rows(vcp_fail=("tightness", "adr", "pullback")))
    return days, timedelta


def _bars_frame(days, closes):
    import pandas as pd
    return pd.DataFrame({
        "asof_date": [d.isoformat() for d in days],
        "open": closes, "high": closes, "low": closes, "close": closes,
    })


def test_the_arm_flag_reaches_the_pure_resolver_from_PRODUCTION_config(
        db, cfg, tmp_path, monkeypatch):
    """T5.6 -- and the discriminator is the whole reason this test is DB-backed.

    `criteria_lapse_armed` is a DEFAULTED parameter, so an implementation that
    threads it through `derive_latches` but FORGETS to pass
    `cfg.latches.criteria_lapse_armed` from `build_latch_derivation` passes
    every direct-resolver fixture while PRODUCTION CAN NEVER ARM -- the feature
    permanently dead, and no unit test over the pure layer would notice. Same
    for `adr_pct`: an implementation that adds the FIELD but forgets
    `c.adr_pct` in `_FIRE_SQL` marks every latch directionally unverifiable in
    production while every hand-built `FireRow` fixture stays green.

    And the UNARMED half asserts EVERY roster field is populated identically to
    the armed run -- a builder that conditionally drops the conflict sessions,
    the causes or the block reason while unarmed would otherwise pass both the
    pure-layer equivalence test and a would-clear-only version of this one.
    """
    import dataclasses

    from swing.latches.models import LATCH_LAPSE_DIAGNOSTIC_FIELDS
    from swing.latches.reader import build_latch_derivation

    days, _ = _seed_lapse_geometry(db)
    db.commit()
    # The seeded fire is the VSTS geometry: pivot 16.90, stop 13.40, adr_pct
    # 4.021 -> floor max(1.0 x 4.021% x 16.90, 2% x 16.90) = $0.68. These closes
    # stay BELOW the pivot (so lifetime 2a holds), ABOVE the stop (so the latch
    # does not invalidate and pass this test for the wrong reason), end at their
    # own low, and widen $1.20 over the five-failure window.
    closes = [16.50, 16.20, 15.90, 15.60, 15.30, 15.00]
    frame = _bars_frame(days, closes)

    import swing.data.ohlcv_archive as archive
    monkeypatch.setattr(
        archive, "resolve_ohlcv_window",
        lambda ticker, **kw: (frame, {"provider": "test"}))

    base = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, prices_cache_dir=tmp_path))
    now = __import__("datetime").datetime(2026, 8, 5, 18, 0, 0)

    unarmed_cfg = dataclasses.replace(
        base, latches=dataclasses.replace(
            base.latches, criteria_lapse_armed=False))
    armed_cfg = dataclasses.replace(
        base, latches=dataclasses.replace(
            base.latches, criteria_lapse_armed=True))

    unarmed = build_latch_derivation(db, unarmed_cfg, now=now).latches[0]
    armed = build_latch_derivation(db, armed_cfg, now=now).latches[0]

    # PRODUCTION CAN ARM -- the flag reaches the pure resolver.
    assert armed.clear_reason == "criteria_lapsed"
    # ...and the shipped default does NOT withdraw, while still MEASURING.
    assert unarmed.clear_reason is None
    assert unarmed.lapse_would_clear_session == armed.clear_session
    # `adr_pct` reached the resolver through the real SELECT, or the floor
    # would be None and nothing could ever qualify.
    assert unarmed.directional_evaluable is True
    assert unarmed.lapse_qualifying_session is not None
    for name in LATCH_LAPSE_DIAGNOSTIC_FIELDS:
        assert getattr(unarmed, name) == getattr(armed, name), name


def test_the_shipped_tracked_config_leaves_the_rule_DISARMED(cfg):
    """The OQ-9 ruling, asserted against the config production actually loads.

    This is the fact the whole arc rests on: the instrument runs, and it
    withdraws nothing until someone deliberately arms it.
    """
    assert cfg.latches.criteria_lapse_armed is False


def test_the_run_dimension_is_CHUNKED_so_a_long_history_cannot_overflow(db, cfg):
    """Codex R1. `run_ids` is UNBOUNDED historical data -- one entry per
    evaluation run since the earliest retained A+ fire or archive bar, and the
    fire loader deliberately never truncates ("ALL A+ fires are loaded"). A bare
    `IN` over it eventually raises `sqlite3.OperationalError: too many SQL
    variables`, and because the panel's outer handler degrades on ANY exception,
    that takes out EVERY latch at once rather than one row. The criteria query in
    the same function was already chunked; this one was not.

    THE LIMIT IS LOWERED RATHER THAN THE FIXTURE ENLARGED, and that is what makes
    the test DISCRIMINATE. This box's SQLite allows 32766 host parameters, so a
    1200-run fixture passes with or without the fix and would have pinned
    nothing. `setlimit` puts the ceiling BELOW the fixture and ABOVE the 500-row
    chunk, so the assertion is exactly "the query is chunked": pre-fix it raises,
    post-fix it does not.
    """
    import sqlite3
    from datetime import timedelta
    start = date(2026, 1, 5)
    with db:
        for i in range(1200):
            db.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
                (i + 1, f"2026-01-05T{i % 24:02d}:{i % 60:02d}:00", "2026-01-02",
                 (start + timedelta(days=i % 5)).isoformat()))
    db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 600)
    try:
        got = load_session_structural_verdicts(
            db, cfg, tickers=["TST"], start=start,
            end=start + timedelta(days=10))
    finally:
        db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 32766)
    assert set(got) == {"TST"}


# ---------------------------------------------------------------------------
# Codex R2 MINOR -- an empty roster is only a SENTINEL when the bucket says so
# ---------------------------------------------------------------------------
def test_an_empty_roster_on_a_SCORED_bucket_is_incomplete_not_a_sentinel(db, cfg):
    """Codex R2. `structural_inputs_from_rows` returned `sentinel_row` for EVERY
    empty roster, and the candidate query did not load `bucket` -- so a `watch`
    or `aplus` candidate carrying no criteria rows (representable: the PK is
    `(candidate_id, criterion_name)` and NOTHING requires the roster to exist)
    was reported as an evaluator sentinel.

    The verdict is UNVERIFIABLE either way, so no mandate moves. But the CAUSE
    is now OPERATOR-VISIBLE on the card -- the `_unverifiable_label` fix earlier
    in this review put it there -- so a wrong cause is a wrong sentence on the
    panel: "the operator holds this / the evaluator errored" instead of "we have
    an incomplete criterion set".

    The two real sentinels keep their label; the evaluator synthesises
    `excluded` and `error` with `criteria=()` and those are genuine.
    """
    from swing.latches.reader import structural_inputs_from_rows

    for bucket in ("excluded", "error"):
        inputs, cause = structural_inputs_from_rows((), bucket=bucket)
        assert inputs is None and cause == "sentinel_row", bucket
    for bucket in ("aplus", "watch", "skip"):
        inputs, cause = structural_inputs_from_rows((), bucket=bucket)
        assert inputs is None and cause == "incomplete_roster", bucket

    # AND THE PRODUCTION LOADER MUST ACTUALLY PASS IT. Without this the helper
    # can be perfectly correct while the reader never supplies a bucket -- the
    # default-arg-diverges-from-production class.
    with db:
        _run(db, 1, "2026-07-28", "2026-07-27T17:30:00")
        _candidate(db, 1, "VSTS", "watch", [])
    got = _verdicts(db, cfg, start="2026-07-28", end="2026-07-28")
    assert [v.classification for v in got] == ["UNVERIFIABLE"]
    assert [v.cause for v in got] == ["incomplete_roster"]


def test_the_run_and_ticker_placeholders_TOGETHER_stay_under_the_limit(db, cfg):
    """Codex R2 MINOR -- the chunking fix was only half a fix.

    Each 500-run chunk executed with `500 + len(values)` parameters, and the
    ticker set comes from the same unbounded all-history fire corpus the run set
    does. A chunk that is bounded on one dimension only is not bounded.

    The budget is now taken from the CONNECTION's own limit, so the pair always
    fits. Pinned with a limit BELOW `500 + len(tickers)` -- which the previous
    fix would have exceeded on the very first chunk.
    """
    import sqlite3
    from datetime import timedelta
    start = date(2026, 1, 5)
    tickers = [f"T{i:04d}" for i in range(400)]
    with db:
        for i in range(400):
            db.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
                (i + 1, f"2026-01-05T{i % 24:02d}:{i % 60:02d}:00",
                 "2026-01-02", (start + timedelta(days=i % 5)).isoformat()))
    db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 600)
    try:
        got = load_session_structural_verdicts(
            db, cfg, tickers=tickers, start=start,
            end=start + timedelta(days=10))
    finally:
        db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 32766)
    assert set(got) == set(tickers)


def test_the_CRITERIA_chunk_is_bounded_by_the_same_limit_as_the_others(db, cfg):
    """Codex R3 MINOR, and it is an inconsistency the R1/R2 fix INTRODUCED: the
    run/ticker query learned to size itself from the connection's own variable
    limit while the criteria query beside it kept a hard-coded 500.

    So a connection whose limit is BELOW 500 -- an old SQLite build, or any
    caller that has lowered it -- passes the first query and then raises
    `too many SQL variables` on the second, which fails the whole verdict load
    and takes the read-only panel with it.

    Pinned with a limit of 400 against 450 candidates: above the ticker/run
    query's own needs, below the 450 placeholders the criteria query wanted.
    """
    import sqlite3
    from datetime import timedelta
    start = date(2026, 1, 5)
    tickers = [f"T{i:04d}" for i in range(450)]
    with db:
        _run(db, 1, start.isoformat(), "2026-01-05T17:30:00")
        for ticker in tickers:
            _candidate(db, 1, ticker, "watch", _rows())
    db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 400)
    try:
        got = load_session_structural_verdicts(
            db, cfg, tickers=tickers, start=start,
            end=start + timedelta(days=3))
    finally:
        db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 32766)
    assert set(got) == set(tickers)
    # The rosters were COMPLETE, so every verdict is a real PASSED -- proving
    # the criteria rows actually arrived rather than the query silently
    # returning nothing.
    assert {v.classification for vs in got.values() for v in vs} == {"PASSED"}


# ---------------------------------------------------------------------------
# Codex R6 -- two ways a verdict could be manufactured from unusable metadata
# ---------------------------------------------------------------------------
def test_a_NON_TRADING_evaluated_session_is_not_a_session_at_all(db, cfg):
    """Codex R6 MAJOR. This guard already exists TWICE in this file -- for entry
    dates (`reader.py:143`) and for bars (`reader.py:617`), whose comment states
    the reason outright: "letting one invalidate a mandate would clear it on a
    day the market never traded". The verdict path was the sibling that never
    got it.

    It matters because the two halves disagree about what a session IS. A
    Saturday-dated run would be counted as a failure by the streak, while
    `_enumerate_sessions` -- which walks TRADING sessions only -- would demand no
    Saturday bar for it. So the coverage requirement is satisfied without the
    evidence, and an armed withdrawal gets stamped with a `clear_session` on a
    day the market was closed.
    """
    with db:
        _run(db, 1, "2026-07-31", "2026-07-30T17:30:00")     # Friday, real
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-08-01", "2026-07-31T17:30:00")     # SATURDAY
        _candidate(db, 2, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
    got = _verdicts(db, cfg, start="2026-07-31", end="2026-08-01")
    assert [v.action_session.isoformat() for v in got] == ["2026-07-31"]
    assert [v.classification for v in got] == ["FAILED"]


def test_an_UNORDERABLE_run_ts_cannot_produce_a_FAILED_verdict(db, cfg):
    """Codex R6 MAJOR. `run_ts` is unconstrained TEXT and the SQL orders it
    LEXICALLY, so a malformed stamp sorts after every valid ISO one and is taken
    as "the latest run".

    The STRICT half exists precisely because incrementing the streak moves a
    latch toward withdrawal, and it keys on WHICH RUN WAS LATEST. If that
    ordering cannot be established from the data, the honest answer is
    UNVERIFIABLE -- asserting FAILED would withdraw a mandate on an ordering the
    data does not support.

    Here the failing run is stamped `zzz` (sorting last) while the genuinely
    later run does not carry the ticker at all. Pre-fix: FAILED. The generous
    PASS is deliberately untouched -- that direction preserves mandates.
    """
    with db:
        _run(db, 1, "2026-07-31", "zzz")                     # malformed
        _candidate(db, 1, "VSTS", "watch", _rows(vcp_fail=("tightness",)))
        _run(db, 2, "2026-07-31", "2026-07-30T18:00:00")     # ticker ABSENT
    got = _verdicts(db, cfg, start="2026-07-31", end="2026-07-31")
    assert [v.classification for v in got] == ["UNVERIFIABLE"]
    # AND IT NAMES THE REAL CAUSE (Codex R7). Defaulting to `absent` would make
    # the card say OFF SCREEN about a ticker that WAS on screen and WAS
    # evaluated -- re-opening, through this guard's default, the exact falsehood
    # the OFF-SCREEN fix closed one round earlier.
    assert [v.cause for v in got] == ["unorderable_run_ts"]


def test_a_generous_PASS_survives_an_unorderable_run_ts(db, cfg):
    """The bound. The unorderable guard must disable only the STRICT half; a
    verified PASS anywhere in the session still resets the streak, because that
    is the mandate-preserving direction and OQ-15 says ambiguity must never
    advance a withdrawal."""
    with db:
        _run(db, 1, "2026-07-31", "zzz")
        _candidate(db, 1, "VSTS", "watch", _rows())          # a full PASS
        _run(db, 2, "2026-07-31", "2026-07-30T18:00:00")
    got = _verdicts(db, cfg, start="2026-07-31", end="2026-07-31")
    assert [v.classification for v in got] == ["PASSED"]
