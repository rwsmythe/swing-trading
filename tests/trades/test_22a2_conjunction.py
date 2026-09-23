"""22-A2 Task 5 -- the four-part conjunction, the seventh-column blob builder
and the authorize-then-abort predicate roster (A2-42..A2-60).

Every discriminator runs on trade 25's REAL values (candidate 12284: OII,
pivot 53.97999954223633, initial_stop 41.41999816894531, action session
2026-08-10; run_ts 2026-08-07T17:30:02 / finished_ts 2026-08-07T17:39:07, naive
HST; fill session 2026-08-17) and the pinned line-57 bytes, varying ONE field
per case.  The variants live in a HEAD database seeded with the same row shape
(the conjunction reads only candidates, evaluation_runs, the run's one complete
pipeline_runs row and the epoch row); A2-42 runs on the full pre-barrier world
and inserts the builder's blob RAW through the citation trigger.
"""
from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from swing.data.db import ensure_schema
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import (
    LINE57_FIXTURE,
    SEVENTH_BLOB_FIXTURE,
    T25_ACTION_SESSION,
    T25_AUTHOR_INSTANT,
    T25_CANDIDATE_ID,
    T25_INITIAL_STOP,
    T25_PIPELINE_FINISHED,
    T25_PIPELINE_ID,
    T25_PIVOT,
    T25_RUN_ID,
    T25_RUN_TS,
    T25_TICKER,
    insert_payload,
    load_seventh_blob,
    truthful_tier2_payload,
)
from tests.data._migration_text import head_create_statement

LINE57_TEXT = LINE57_FIXTURE.read_bytes().decode("utf-8")
FILL_SESSION = date(2026, 8, 17)
READ_AT = "2026-09-23T12:00:00.000"
SHA_9F315CC6 = "9f315cc64a8f171049b510021e6418bc261c50b7"
ORIGIN_MAIN_348F126B = "348f126bb463519999ae7b183de98af448112557"


def _facts(*, quoted: str = LINE57_TEXT, author: str = T25_AUTHOR_INSTANT,
           committer: str | None = None, is_ancestor: bool = True) -> fve.ArtifactFacts:
    """The preflight's facts for 9f315cc6 as measured (P24/P36, the ledger)."""
    return fve.ArtifactFacts(
        selection=fve.EvidenceSelection(
            artifact_path="docs/rd-state.md", artifact_commit_sha=SHA_9F315CC6,
            quoted_text=quoted),
        author_instant=datetime.fromisoformat(author),
        committer_instant=datetime.fromisoformat(committer or author),
        is_ancestor=is_ancestor,
        resolved_remote_ref_sha=ORIGIN_MAIN_348F126B,
        descendant_count=684 if is_ancestor else None,
        remote_ref_updated_at=None,
        remote_ref_age_seconds=None,
    )


def _world(tmp_path: Path, *, ticker: str = T25_TICKER, pivot: float = T25_PIVOT,
           stop: float = T25_INITIAL_STOP,
           session: str = T25_ACTION_SESSION) -> sqlite3.Connection:
    """A HEAD database carrying trade 25's evaluation run, candidate and
    pipeline row, with ONE field varied."""
    conn = ensure_schema(tmp_path / "conj.db")
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, finviz_csv_path, tickers_evaluated, aplus_count, "
        "watch_count, skip_count, excluded_count, error_count) "
        "VALUES (?, ?, '2026-08-07', ?, NULL, 60, 1, 10, 46, 3, 0)",
        (T25_RUN_ID, T25_RUN_TS, session))
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
        "pattern_tag, notes, sector, industry) "
        "VALUES (?, ?, ?, 'aplus', 53.49, ?, ?, 4.1, 5, 8.0, 60.0, NULL, 20.1, "
        "'universe', 'vcp', NULL, 'Energy', 'Oil & Gas Equipment & Services')",
        (T25_CANDIDATE_ID, T25_RUN_ID, ticker, pivot, stop))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (?, '2026-08-07T17:30:00', ?, 'scheduled', "
        "'2026-08-07', ?, 'complete', 'lease-t25', ?)",
        (T25_PIPELINE_ID, T25_PIPELINE_FINISHED, session, T25_RUN_ID))
    conn.commit()
    return conn


def _evaluate(conn: sqlite3.Connection, facts: fve.ArtifactFacts, *,
              fill_session: date = FILL_SESSION) -> fve.ConjunctionVerdict:
    return fve.evaluate_conjunction(
        conn, facts, candidate_id=T25_CANDIDATE_ID, fill_session=fill_session,
        read_at=READ_AT, barrier_installed=True)


def _refusal(v: fve.ConjunctionVerdict) -> tuple[int | None, str | None, str | None]:
    assert v.admitted is False and v.evidence is None
    return v.criterion, v.reason, v.field


def _at(blob: dict, dotted: str) -> object:
    value: object = blob
    for part in dotted.split("."):
        assert isinstance(value, dict)
        value = value[part]
    return value


# --------------------------------------------------------------------------- A2-42

def test_a2_42_trade25_admits_and_builder_equals_the_hand_built_literal(
    tmp_path: Path,
) -> None:
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        verdict = fve.evaluate_conjunction(
            conn, _facts(), candidate_id=T25_CANDIDATE_ID, fill_session=FILL_SESSION,
            read_at=payload["applied_at"], barrier_installed=True)
        assert verdict.admitted, verdict
        blob = verdict.evidence
        assert blob is not None
        literal = load_seventh_blob(conn, applied_at=payload["applied_at"])
        # The closed roster: the plan's section 2, as the hand-built literal carries it.
        assert set(blob) == set(literal)
        assert len(blob) == 28
        # The ISO session match comes from the RESOLUTION token "T5 RESOLVED
        # 2026-08-10" (RD's note), equal to the action session by coincidence.
        assert (blob["quoted_ticker_text"], blob["quoted_action_session_text"],
                blob["quoted_pivot_text"], blob["quoted_invalidation_text"]) == (
            "OII", "2026-08-10", "53.98", "41.42")
        # Two independent representations agree on every verdict-bearing key
        # (RD's F2.I-NEG consequence (iii): record_position is one of them).
        assert "interval.record_position" in fve.VERDICT_BEARING_KEYS
        assert blob["interval"]["record_position"] == "before_barrier"
        assert len(blob["interval"]["segments"]) == 4
        for key in sorted(fve.VERDICT_BEARING_KEYS):
            assert _at(blob, key) == _at(literal, key), key
        # And the constants the literal carries are the module's.
        for key in ("evidence_version", "ruling_citation", "verification_method",
                    "anchor_strength", "time_anchor_residual", "compare_dp"):
            assert blob[key] == literal[key], key
        # It inserts RAW through the HEAD citation trigger.
        payload["cited_frozen_value_evidence_json"] = json.dumps(blob)
        insert_payload(conn, payload)
        assert conn.execute(
            "SELECT admission_tier FROM provenance_corrections").fetchone() == (
            "latch_ladder_tier2",)
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-43

def test_a2_43_interval_durations_and_prose_on_trade25_live_values() -> None:
    literal = json.loads(SEVENTH_BLOB_FIXTURE.read_text(encoding="utf-8"))
    interval = fve.build_interval(
        fire_lo_raw=T25_RUN_TS, fire_hi_raw=T25_PIPELINE_FINISHED,
        author_instant=datetime.fromisoformat(T25_AUTHOR_INSTANT),
        barrier_armed_raw="2026-09-02T10:03:33Z", read_at=READ_AT,
        barrier_installed=True)
    seconds = {s["kind"]: s["seconds"] for s in interval["segments"]}
    assert seconds["fire"] == 545
    assert seconds["writer_absence_only"] == 205_346
    assert seconds["match_only"] == 1_977_720
    # Pre-fix arithmetic: a POINT fire at run START would give 205,891 s.
    assert seconds["writer_absence_only"] + seconds["fire"] == 205_891
    prose = fve.render_uncovered_window_prose(interval)
    assert "2.38 days" in prose and "22.89 days" in prose
    # The whole interval and prose equal the hand-built literal.
    assert interval == literal["interval"]
    assert prose == literal["uncovered_window_prose"]


# ------------------------------------------------------------ F2.I-NEG (RD, 2026-09-23)
# The trade-25 world with ONLY the barrier time moved.  Trade 25's record is
# 2026-08-10T12:41:33Z; the discriminators put the barrier 1 s before, at, and
# 1 s after it.

T25_RECORD_UTC = "2026-08-10T12:41:33Z"
BARRIER_RECORD_PLUS_1 = "2026-08-10T12:41:32Z"   # record = barrier + 1 s
BARRIER_RECORD_MINUS_1 = "2026-08-10T12:41:34Z"  # record = barrier - 1 s
BARRIER_AT_RECORD = T25_RECORD_UTC               # record == barrier


def _t25_interval(barrier_z: str) -> dict:
    return fve.build_interval(
        fire_lo_raw=T25_RUN_TS, fire_hi_raw=T25_PIPELINE_FINISHED,
        author_instant=datetime.fromisoformat(T25_AUTHOR_INSTANT),
        barrier_armed_raw=barrier_z, read_at=READ_AT, barrier_installed=True)


def _kinds(interval: dict) -> list[str]:
    return [s["kind"] for s in interval["segments"]]


def test_f2i_neg_record_after_barrier_emits_no_match_only() -> None:
    interval = _t25_interval(BARRIER_RECORD_PLUS_1)
    # Pre-fix arithmetic: the literal impl emits match_only = -1 s; a clamp
    # impl emits match_only = 0 s; either fails the exact kind list.
    assert _kinds(interval) == ["fire", "writer_absence_only", "covered"]
    assert interval["record_position"] == "inside_coverage"
    assert all(s["seconds"] > 0 for s in interval["segments"])
    # writer_absence_only END = min(record_at, barrier_armed_at): the barrier.
    wao = interval["segments"][1]
    assert (wao["from"], wao["to"], wao["seconds"]) == (
        "2026-08-08T03:39:07Z", BARRIER_RECORD_PLUS_1, 205_345)
    assert interval["segments"][2]["from"] == BARRIER_RECORD_PLUS_1
    prose = fve.render_uncovered_window_prose(interval)
    assert "inside coverage" in prose
    assert prose == (
        "writer_absence_only 2.38 days (2026-08-08T03:39:07Z to 2026-08-10T12:41:32Z); "
        "covered from 2026-08-10T12:41:32Z; "
        "record authored inside coverage at 2026-08-10T12:41:33Z")


def test_f2i_neg_record_before_barrier_keeps_a_one_second_match_only() -> None:
    interval = _t25_interval(BARRIER_RECORD_MINUS_1)
    assert _kinds(interval) == ["fire", "writer_absence_only", "match_only", "covered"]
    assert interval["segments"][2]["seconds"] == 1
    assert interval["segments"][1]["seconds"] == 205_346
    assert interval["record_position"] == "before_barrier"
    assert all(s["seconds"] > 0 for s in interval["segments"])


def test_f2i_neg_record_at_barrier_emits_no_empty_match_only() -> None:
    interval = _t25_interval(BARRIER_AT_RECORD)
    # Pre-fix arithmetic: a clamp/literal impl emits match_only = 0 s.
    assert "match_only" not in _kinds(interval)
    assert _kinds(interval) == ["fire", "writer_absence_only", "covered"]
    assert interval["record_position"] == "inside_coverage"
    assert all(s["seconds"] > 0 for s in interval["segments"])


_REAL_READ_CONTEXT = fve._read_context


def _moved_barrier_world(tmp_path: Path, monkeypatch, barrier_z: str):
    """The conjunction world with ONLY the epoch's applied_at moved (the test
    world's epoch is stamped at migration time and is immutable)."""
    conn = _world(tmp_path)

    def moved(c, candidate_id):
        return {**_REAL_READ_CONTEXT(c, candidate_id), "barrier_armed_at": barrier_z}
    monkeypatch.setattr(fve, "_read_context", moved)
    return conn, fve._read_context(conn, T25_CANDIDATE_ID)


def test_f2i_neg_each_barrier_position_admits_through_the_conjunction(
    tmp_path: Path, monkeypatch,
) -> None:
    """The three discriminators end to end: the built blob passes every
    trigger-predicate mirror (the presence IFF and the belt included)."""
    for barrier_z, n_segments, position in (
            (BARRIER_RECORD_PLUS_1, 3, "inside_coverage"),
            (BARRIER_RECORD_MINUS_1, 4, "before_barrier"),
            (BARRIER_AT_RECORD, 3, "inside_coverage")):
        conn, _ctx = _moved_barrier_world(tmp_path / barrier_z[-3:-1], monkeypatch,
                                          barrier_z)
        verdict = _evaluate(conn, _facts())
        assert verdict.admitted, (barrier_z, verdict)
        assert verdict.evidence is not None
        interval = verdict.evidence["interval"]
        assert interval == _t25_interval(barrier_z)
        assert (len(interval["segments"]), interval["record_position"]) == (
            n_segments, position)
        assert verdict.evidence["uncovered_window_prose"] == (
            fve.render_uncovered_window_prose(interval))
        conn.close()


def test_f2i_neg_service_mirrors_refuse_what_sql_cannot_see(
    tmp_path: Path, monkeypatch,
) -> None:
    """The presence IFF (match_only iff record_at.utc < barrier_armed_at.utc)
    and seconds > 0 live in the interval_segment_order service mirror (SQL
    never reads a utc value, R8-03); the length belt is its own mirror."""
    conn, ctx = _moved_barrier_world(tmp_path, monkeypatch, BARRIER_RECORD_PLUS_1)
    admitted = _evaluate(conn, _facts())
    assert admitted.evidence is not None
    good = admitted.evidence

    def first_fail(blob: dict) -> str | None:
        return fve._first_failing_mirror(blob, ctx, read_at=READ_AT,
                                         fill_session=FILL_SESSION)
    assert first_fail(good) is None

    # (1) a match_only forged into an inside-coverage record, belt satisfied:
    # SQL-consistent (length 4, before_barrier), the IFF refuses it.
    forged = copy.deepcopy(good)
    segs = forged["interval"]["segments"]
    segs.insert(2, {"kind": "match_only", "from": T25_RECORD_UTC,
                    "to": BARRIER_RECORD_PLUS_1, "seconds": 1})
    forged["interval"]["record_position"] = "before_barrier"
    assert first_fail(forged) == "interval_segment_order"

    # (2) a zero-second segment is never admissible.
    zero = copy.deepcopy(good)
    zero["interval"]["segments"][1]["seconds"] = 0
    assert first_fail(zero) == "interval_segment_order"

    # (3) CHARC's belt: record_position disagreeing with the segment count.
    belt = copy.deepcopy(good)
    belt["interval"]["record_position"] = "before_barrier"
    assert first_fail(belt) == "record_position_consistent"

    # (4) interval_closed admits exactly one more typed key.
    bad_pos = copy.deepcopy(good)
    bad_pos["interval"]["record_position"] = "after_barrier"
    assert first_fail(bad_pos) == "interval_closed"
    missing = copy.deepcopy(good)
    del missing["interval"]["record_position"]
    assert first_fail(missing) == "interval_closed"
    conn.close()


# --------------------------------------------------------------------------- A2-44

def test_a2_44_not_ancestor_refuses_criterion_1(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    assert _refusal(_evaluate(conn, _facts(is_ancestor=False))) == (
        1, "not_ancestor_of_origin_main", None)
    assert _evaluate(conn, _facts()).admitted


# --------------------------------------------------------------------------- A2-45

def test_a2_45_et_date_equal_to_fill_session_refuses(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    facts = _facts(author="2026-08-17T09:00:00-04:00")
    assert _refusal(_evaluate(conn, facts)) == (2, "recorded_on_fill_session", None)
    # Pre-fix arithmetic: a `<=` comparison admits this date.
    assert date(2026, 8, 17) <= FILL_SESSION


# --------------------------------------------------------------------------- A2-46

def test_a2_46_et_date_not_the_local_offset_date(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    author = datetime.fromisoformat("2026-08-16T20:00:00-10:00")
    # Pre-fix arithmetic: the commit's OWN offset date is 08-16 < 08-17 (admits).
    assert author.date() == date(2026, 8, 16)
    facts = _facts(author="2026-08-16T20:00:00-10:00")
    assert _refusal(_evaluate(conn, facts)) == (2, "recorded_on_fill_session", None)


# --------------------------------------------------------------------------- A2-47

def test_a2_47_et_day_before_fill_passes_criterion_2(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    verdict = _evaluate(conn, _facts(author="2026-08-16T23:59:59-04:00"))
    assert verdict.admitted, verdict
    assert verdict.evidence is not None
    assert verdict.evidence["author_date_et"] == "2026-08-16"


# --------------------------------------------------------------------------- A2-48

def test_a2_48_committer_date_is_never_verdict_bearing(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    facts = _facts(committer="2026-08-17T12:00:00-04:00")
    verdict = _evaluate(conn, facts)
    assert verdict.admitted, verdict
    assert verdict.evidence is not None
    assert verdict.evidence["committer_instant"] == "2026-08-17T12:00:00-04:00"
    # Pre-fix arithmetic: the committer's ET date IS the fill session.
    assert facts.committer_instant.astimezone(fve.ET_ZONE).date() == FILL_SESSION


# --------------------------------------------------------------------------- A2-49

def test_a2_49_five_cent_pivot_refuses_naming_pivot(tmp_path: Path) -> None:
    conn = _world(tmp_path, pivot=53.93)
    assert _refusal(_evaluate(conn, _facts())) == (3, "pivot", "pivot")


# --------------------------------------------------------------------------- A2-50

_EIGHTH = "OII action session 2026-08-10: pivot 22.12 / initial_stop 41.42"


def test_a2_50_eighth_dollar_pivot_admits_under_python_half_even(tmp_path: Path) -> None:
    conn = _world(tmp_path, pivot=22.125)
    assert fve.render_price(22.125) == "22.12"
    verdict = _evaluate(conn, _facts(quoted=_EIGHTH))
    assert verdict.admitted, verdict
    assert verdict.evidence is not None
    assert verdict.evidence["quoted_pivot_text"] == "22.12"
    # Pre-fix arithmetic: SQLite rounds half AWAY from zero -> 22.13, a refusal.
    sqlite_rendered = sqlite3.connect(":memory:").execute(
        "SELECT printf('%.2f', round(22.125, 2))").fetchone()[0]
    assert sqlite_rendered == "22.13"


# --------------------------------------------------------------------------- A2-51

def test_a2_51_control_both_engines_render_22_12(tmp_path: Path) -> None:
    conn = _world(tmp_path, pivot=22.1249)
    assert fve.render_price(22.1249) == "22.12"
    assert sqlite3.connect(":memory:").execute(
        "SELECT printf('%.2f', round(22.1249, 2))").fetchone()[0] == "22.12"
    assert _evaluate(conn, _facts(quoted=_EIGHTH)).admitted


# --------------------------------------------------------------------------- A2-52

def test_a2_52_ticker_is_token_bounded(tmp_path: Path) -> None:
    conn = _world(tmp_path, ticker="OI")
    # Pre-fix arithmetic: a substring check finds "OI" inside "OII".
    assert "OI" in LINE57_TEXT
    assert _refusal(_evaluate(conn, _facts())) == (3, "ticker", "ticker")


# --------------------------------------------------------------------------- A2-53

def test_a2_53_absent_ticker_refuses_naming_ticker(tmp_path: Path) -> None:
    conn = _world(tmp_path, ticker="VSTS")
    assert "VSTS" not in LINE57_TEXT
    assert _refusal(_evaluate(conn, _facts())) == (3, "ticker", "ticker")


# --------------------------------------------------------------------------- A2-54

def test_a2_54_wrong_action_session_refuses_naming_action_session(tmp_path: Path) -> None:
    conn = _world(tmp_path, session="2026-08-11")
    assert _refusal(_evaluate(conn, _facts())) == (3, "action_session", "action_session")


# --------------------------------------------------------------------------- A2-55

def test_a2_55_year_rule_refuses_mm_dd_for_a_prior_year_author(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    no_iso = LINE57_TEXT.replace("2026-08-10 ", "", 1)
    assert "2026-08-10" not in no_iso and "08-10" in no_iso
    facts = _facts(quoted=no_iso, author="2025-08-09T10:00:00-10:00")
    assert _refusal(_evaluate(conn, facts)) == (3, "action_session", "action_session")
    # Pre-fix arithmetic: without the year rule the MM-DD token matches and
    # criterion 4 speaks instead (the record predates the fire).
    assert fve.find_token(no_iso, "08-10", kind="session") == "08-10"


# --------------------------------------------------------------------------- A2-56

def test_a2_56_iso_token_carries_its_own_year(tmp_path: Path) -> None:
    conn = _world(tmp_path)
    facts = _facts(author="2025-08-09T10:00:00-10:00")
    assert _refusal(_evaluate(conn, facts)) == (4, "window_negative", None)


# --------------------------------------------------------------------------- A2-57

def test_a2_57_record_must_be_strictly_after_fire_hi(tmp_path: Path) -> None:
    """RD's G-U1 ruling: the fire bracket [fire_lo, fire_hi] is CLOSED on both
    ends -- finished_ts is second-truncated (lease.py ``timespec="seconds"``),
    so a record EQUAL to either bound is order-indeterminate."""
    conn = _world(tmp_path)
    # Pre-fix arithmetic: the `>=` impl ADMITS at_hi with a 0 s writer_absence_only.
    assert _refusal(_evaluate(conn, _facts(author="2026-08-07T17:39:07-10:00"))) == (
        4, "window_indeterminate", None)
    # The boundary twin: one second past fire_hi admits, writer_absence_only 1 s.
    past_hi = _evaluate(conn, _facts(author="2026-08-07T17:39:08-10:00"))
    assert past_hi.admitted, past_hi
    assert past_hi.evidence is not None
    segs = past_hi.evidence["interval"]["segments"]
    assert [s["kind"] for s in segs][:2] == ["fire", "writer_absence_only"]
    assert segs[1]["seconds"] == 1
    assert _refusal(_evaluate(conn, _facts(author="2026-08-07T17:39:06-10:00"))) == (
        4, "window_indeterminate", None)
    assert _refusal(_evaluate(conn, _facts(author="2026-08-07T17:30:02-10:00"))) == (
        4, "window_indeterminate", None)
    assert _refusal(_evaluate(conn, _facts(author="2026-08-07T17:30:01-10:00"))) == (
        4, "window_negative", None)


# --------------------------------------------------------------------------- A2-58

def test_a2_58_refusal_order_first_failing_field_speaks(tmp_path: Path) -> None:
    both = _world(tmp_path / "a", ticker="VSTS", pivot=53.93)
    assert _refusal(_evaluate(both, _facts()))[2] == "ticker"
    pivot_and_stop = _world(tmp_path / "b", pivot=53.93, stop=41.40)
    assert _refusal(_evaluate(pivot_and_stop, _facts()))[2] == "pivot"
    stop_only = _world(tmp_path / "c", stop=41.40)
    assert _refusal(_evaluate(stop_only, _facts()))[2] == "invalidation"


# --------------------------------------------------------------------------- A2-59

def test_a2_59_declared_limits_are_pinned(tmp_path: Path) -> None:
    # AL2-3: swapped numerals admit (containment binds no label).
    conn = _world(tmp_path / "swap")
    swapped = "OII 2026-08-10 pivot 41.42 / stop 53.98"
    assert _evaluate(conn, _facts(quoted=swapped)).admitted
    # AL2-2: containment proves MENTION -- line 57 mentions AMN in passing.
    amn = _world(tmp_path / "amn", ticker="AMN")
    verdict = _evaluate(amn, _facts())
    assert verdict.admitted, verdict
    assert verdict.evidence is not None
    assert verdict.evidence["quoted_ticker_text"] == "AMN"


# --------------------------------------------------------------------------- A2-60

_MARKER = re.compile(r"--\s*TIER2-PREDICATE\s+([a-z0-9_]+)")


def _module_reach(module: object, root: str) -> set[str]:
    """Every module-level name reachable from ``root`` by NAME REFERENCE
    (calls and bare references -- a mirror tuple counts), walked transitively
    through the module's own functions and module-level assignments."""
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    defs[t.id] = node
    seen: set[str] = set()
    stack = [root]
    while stack:
        name = stack.pop()
        if name in seen or name not in defs:
            continue
        seen.add(name)
        for sub in ast.walk(defs[name]):
            if isinstance(sub, ast.Name) and sub.id in defs:
                stack.append(sub.id)
    return seen


def test_a2_60_every_trigger_predicate_has_a_reached_service_check() -> None:
    _path, trigger = head_create_statement("trg_provenance_corrections_citation_graph")
    sql_ids = _MARKER.findall(trigger)
    # 28 + CHARC's G-NEG belt `record_position_consistent`.
    assert len(sql_ids) == len(set(sql_ids)) == 29
    assert "record_position_consistent" in sql_ids
    py_ids = [pid for pid, _ in fve.TIER2_TRIGGER_PREDICATES]
    assert len(py_ids) == len(set(py_ids))
    assert set(sql_ids) - set(py_ids) == set(), "trigger predicate with no service check"
    assert set(py_ids) - set(sql_ids) == set(), "service check with no trigger predicate"

    roots = {
        "swing.trades.frozen_value_evidence": "evaluate_conjunction",
        "swing.trades.latched_origin": "authorize_accepted_order",
    }
    reach = {mod: _module_reach(importlib.import_module(mod), root)
             for mod, root in roots.items()}
    latched_src = inspect.getsource(importlib.import_module("swing.trades.latched_origin"))
    for pid, target in fve.TIER2_TRIGGER_PREDICATES:
        module_name, _, attr = target.partition(":")
        module = importlib.import_module(module_name)
        assert callable(getattr(module, attr)), (pid, target)
        if module_name in reach:
            assert attr in reach[module_name], (pid, target, "not reached")
        else:
            # A check owned by another module is reached from rung 9's home.
            assert re.search(rf"\b{attr}\(", latched_src), (pid, target)
