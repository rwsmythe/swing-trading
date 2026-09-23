"""22-A2 Task 11 -- the trade-25 acceptance case end to end (A2-98..A2-104).

Brief section 4, reproduced from the record.  The DB world is trade 25's REAL
row shape (``tests/_tier2_world_22a2.py``: candidate 12284, run 136, rec 169,
pipeline 150, fill 48, a ``pre_barrier_reconstructed`` link minted the
production way -- rows on v36, then migrated), and the evidence is a SELECTION
into a throwaway git world whose ``docs/rd-state.md`` line 57 is the pinned
line-57 bytes, authored at 9f315cc6's measured instant and published to
``refs/remotes/origin/main``.  Everything runs through the PRODUCTION service
(``correct_cohort_provenance``); nothing here is built to satisfy the premise.

One world constraint, stated rather than hidden: the test world's epoch row is
stamped by 0037 at MIGRATION time and is immutable (the citation trigger binds
``barrier_armed_at.raw`` to it), so the live barrier ``2026-09-02T10:03:33Z``
cannot be carried end to end.  A2-98 therefore asserts the world-independent
segment (``writer_absence_only`` 2.38 d) on the service-written row, and the
22.89 d ``match_only`` by re-deriving the interval from THAT ROW's recorded
endpoints with the live barrier substituted.  The live copy's dry run (Task
11's second half, not a test) carries the live barrier itself.

A2-101..A2-103 RE-ASSERT existing green tests (A2-60, A2-09, A2-23 + A2-25)
on the final head; they call the originals rather than copy them, so the
assertion cannot fork.  A2-101 re-points A2-60 at the MIGRATED schema's stored
trigger (``sqlite_master``) instead of the migration file's text.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PROVENANCE_ADMISSION_TIER_LATCH_TIER2
from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from swing.trades.latched_origin import LATCH_PROBE_TIER2_EVIDENCE_VERSION
from tests._tier2_world_22a2 import (
    LINE57_FIXTURE,
    SEVENTH_BLOB_FIXTURE,
    T25_AUTHOR_INSTANT,
    T25_CANDIDATE_ID,
    T25_FILL_ID,
    T25_ORDER_ID,
    T25_PIPELINE_ID,
    T25_REC_ID,
    T25_RUN_ID,
    T25_TRADE_ID,
    build_pre_barrier_world,
    t25_cfg,
)
from tests.trades._git_world import GitWorld, git
from tests.trades.test_22a2_cohort_readers import H1_ID, H1_LABEL, _world
from tests.trades.test_22a2_correction_service import (  # noqa: F401 -- fixture
    RD_STATE,
    _pivot_absent_line,
    _rd_state_bytes,
    ticking_clock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LINE57 = LINE57_FIXTURE.read_bytes()
LINE57_SHA256 = "abfd428aaa55e409fa1261f3c1813da8c1a2941621499ff581d81b37e96c5407"
SHA_9F315CC6 = "9f315cc6"
LIVE_BARRIER = "2026-09-02T10:03:33Z"
REASON = "22-A2 Task 11: the trade-25 acceptance case"


# --------------------------------------------------------------------------- helpers

def _publish(tmp_path: Path, *, line57: bytes = LINE57,
             author: str = T25_AUTHOR_INSTANT, name: str = "evidence",
             drop_from_remote: bool = False) -> tuple[GitWorld, str, Path]:
    """``(world, sha, evidence_file)``: line 57 committed as line 57 of
    ``docs/rd-state.md`` at ``author``, pushed and fetched.  With
    ``drop_from_remote`` the published history is REWRITTEN so the commit is no
    longer an ancestor of ``refs/remotes/origin/main`` (still readable locally)."""
    world = GitWorld(tmp_path / f"{name}-git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, _rd_state_bytes(line57), author_date=author)
    world.push()
    if drop_from_remote:
        world.rewrite_remote_dropping(sha)
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({
        "artifact_path": RD_STATE, "artifact_commit_sha": sha,
        "quoted_text": line57.decode("utf-8")}), encoding="utf-8")
    return world, sha, path


def _t25(tmp_path: Path, name: str = "t25"):
    conn, ids = build_pre_barrier_world(tmp_path, name)
    return conn, t25_cfg(tmp_path / name), ids


def _apply(conn, cfg, **kw) -> cpc.CohortProvenanceCorrectionResult:
    return cpc.correct_cohort_provenance(
        conn, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
        cited_recommendation_id=T25_REC_ID, reason=REASON, cfg=cfg, **kw)


def _row(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT * FROM provenance_corrections")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    assert len(rows) == 1, rows
    return dict(zip(cols, rows[0], strict=True))


def _trade_keys(conn: sqlite3.Connection) -> tuple:
    return conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin FROM trades WHERE id = ?",
        (T25_TRADE_ID,)).fetchone()


def _dump(conn: sqlite3.Connection) -> list[str]:
    return list(conn.iterdump())


def _seconds(interval: dict) -> dict[str, int]:
    return {s["kind"]: s["seconds"] for s in interval["segments"]}


# --------------------------------------------------------------------------- A2-98

def test_a2_98_trade25_admits_on_tier2_from_line57_end_to_end(
    tmp_path: Path, ticking_clock,
) -> None:
    """Brief 4.1.  PRE (no evidence, the unarmed twin): 22-A's ladder refuses
    ``pre_barrier_unproven`` and nothing is written.  POST (line 57 at an
    ancestor commit authored 2026-08-10T02:41:33-10:00): ADMIT on tier 2 --
    keys H1 / 12284 / ``pipeline_aplus``; the row carries the tier, the
    citation JSON, the interval and the attestation."""
    world, sha, evidence = _publish(tmp_path)
    conn, cfg, ids = _t25(tmp_path)
    try:
        # The unarmed twin: the escape is opt-in.
        before = _dump(conn)
        with pytest.raises(cpc.CohortProvenanceCorrectionError,
                           match="pre_barrier_unproven"):
            _apply(conn, cfg)
        assert _dump(conn) == before
        assert _trade_keys(conn) == (None, None, "manual_off_pipeline")

        # The record commit IS an ancestor of the published remote ref.
        git(world.work, "merge-base", "--is-ancestor", sha, fve.REMOTE_REF)

        result = _apply(conn, cfg, frozen_value_evidence=evidence,
                        evidence_repo=world.work)
        assert result.already_applied is False
        assert result.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2

        # Keys: H1 / 12284 / the ruled origin.
        assert _trade_keys(conn) == (H1_LABEL, T25_CANDIDATE_ID, "pipeline_aplus")
        row = _row(conn)
        assert (row["trade_id"], row["entry_fill_id"], row["cited_candidate_id"],
                row["cited_daily_recommendation_id"], row["cited_evaluation_run_id"],
                row["cited_pipeline_run_id"], row["cited_hypothesis_id"]) == (
            T25_TRADE_ID, T25_FILL_ID, T25_CANDIDATE_ID, T25_REC_ID, T25_RUN_ID,
            T25_PIPELINE_ID, H1_ID)
        assert row["cited_hypothesis_name_at_correction"] == "A+ baseline"

        # The row tier and the citation JSON.
        assert row["admission_tier"] == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        assert (row["cited_latch_link_id"], row["cited_latch_validity_intent_id"],
                row["cited_latch_place_intent_id"], row["cited_latch_broker_order_id"]) == (
            ids["link_id"], ids["validity_id"], ids["place_id"], T25_ORDER_ID)
        probe = json.loads(row["cited_latch_probe_json"])
        assert probe["evidence_version"] == LATCH_PROBE_TIER2_EVIDENCE_VERSION
        assert probe["fire_candidate_id"] == T25_CANDIDATE_ID
        assert probe["freeze_tier"] == "pre_barrier_reconstructed"
        assert probe["admission_basis"] == "armed"
        assert probe["authorization"]["rung9_stored_freeze_tier"]["verdict"] == (
            "escaped_by_tier2")
        blob = json.loads(row["cited_frozen_value_evidence_json"])
        literal = json.loads(SEVENTH_BLOB_FIXTURE.read_text(encoding="utf-8"))
        # Stored with sort_keys (the service's json.dumps); the roster is closed.
        assert sorted(blob) == sorted(fve.FROZEN_VALUE_BLOB_KEYS)
        assert (blob["artifact_path"], blob["artifact_commit_sha"], blob["quoted_text"]) == (
            RD_STATE, sha, LINE57.decode("utf-8"))
        assert (blob["author_instant"], blob["author_date_et"],
                blob["fill_session_date"]) == (T25_AUTHOR_INSTANT, "2026-08-10",
                                               "2026-08-17")
        assert (blob["quoted_ticker_text"], blob["quoted_action_session_text"],
                blob["quoted_pivot_text"], blob["quoted_invalidation_text"]) == (
            "OII", "2026-08-10", "53.98", "41.42")
        assert (blob["evidence_version"], blob["derivation_version"]) == (
            fve.FROZEN_VALUE_EVIDENCE_VERSION, fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION)
        assert blob["derivation_version"] == literal["derivation_version"] == "2026-09-23.5"

        # The interval: fire 545 s, writer_absence_only 2.38 d (world-independent).
        interval = blob["interval"]
        assert interval["record_position"] == "before_barrier"
        assert [s["kind"] for s in interval["segments"]] == [
            "fire", "writer_absence_only", "match_only", "covered"]
        assert interval["segments"][:2] == literal["interval"]["segments"][:2]
        assert _seconds(interval)["writer_absence_only"] == 205_346
        assert "writer_absence_only 2.38 days" in blob["uncovered_window_prose"]
        epoch = conn.execute("SELECT applied_at FROM candidates_immutability_epoch "
                             "WHERE epoch_id = 1").fetchone()[0]
        assert interval["endpoints"]["barrier_armed_at"]["raw"] == epoch
        # 22.89 d: the ROW's recorded endpoints with the LIVE barrier substituted.
        ep = interval["endpoints"]
        live = fve.build_interval(
            fire_lo_raw=ep["fire_lo"]["raw"], fire_hi_raw=ep["fire_hi"]["raw"],
            author_instant=datetime.fromisoformat(ep["record_at"]["raw"]),
            barrier_armed_raw=LIVE_BARRIER, read_at=ep["read_at"]["raw"],
            barrier_installed=True)
        assert live["segments"][:3] == literal["interval"]["segments"][:3]
        assert _seconds(live)["match_only"] == 1_977_720
        live_prose = fve.render_uncovered_window_prose(live)
        assert "writer_absence_only 2.38 days" in live_prose
        assert "match_only 22.89 days" in live_prose

        # The attestation.
        assert blob["evaluated_at"] == row["applied_at"] == ep["read_at"]["raw"]
        assert blob["verification_method"] == fve.VERIFICATION_METHOD == (
            literal["verification_method"])
        assert blob["resolved_remote_ref_sha"] == world.remote_tip()
        assert blob["anchor_strength"] == literal["anchor_strength"]
        assert blob["time_anchor_residual"] == literal["time_anchor_residual"]
        assert blob["ruling_citation"] == literal["ruling_citation"]

        # The operator surface: four clauses PASS, and the interval prose.
        assert [v for _, v in result.tier2_clauses] == ["PASS"] * 4
        assert result.tier2_interval_prose == blob["uncovered_window_prose"]
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-99

def _mutated_evidence(tmp_path: Path, leg: str) -> tuple[GitWorld, Path]:
    if leg == "criterion1_not_ancestor":            # A2-44
        world, _sha, path = _publish(tmp_path, drop_from_remote=True)
    elif leg == "criterion2_et_date_is_fill_session":  # A2-45
        world, _sha, path = _publish(tmp_path, author="2026-08-17T09:00:00-04:00")
    elif leg == "criterion3_five_cent_pivot":        # A2-49
        world, _sha, path = _publish(tmp_path, line57=_pivot_absent_line())
    elif leg == "criterion4_record_at_fire_hi_minus_1s":  # A2-57
        world, _sha, path = _publish(tmp_path, author="2026-08-07T17:39:06-10:00")
    else:
        raise AssertionError(leg)
    return world, path


_A2_99_REFUSALS = {
    "criterion1_not_ancestor": "criterion 1: not_ancestor_of_origin_main",
    "criterion2_et_date_is_fill_session": "criterion 2: recorded_on_fill_session",
    "criterion3_five_cent_pivot": "criterion 3: pivot",
    "criterion4_record_at_fire_hi_minus_1s": "criterion 4: window_indeterminate",
}


@pytest.mark.parametrize("leg", [*_A2_99_REFUSALS, "trigger_interval_uncomputed"])
def test_a2_99_each_clause_refuses_its_one_mutation_end_to_end(
    tmp_path: Path, ticking_clock, monkeypatch, leg: str,
) -> None:
    """Brief 4.2: ONE mutated value per clause on the trade-25 world, through
    ``correct_cohort_provenance``, refuses for ITS reason with nothing written
    (the unmutated control is A2-98).  The fifth leg is AUTHORIZE-THEN-ABORT
    at the TRIGGER: the service's conjunction is made to hand over a blob with
    the interval left uncomputed (its own mirror skipped), and the citation
    trigger -- not the service -- refuses it; the same path with the interval
    intact inserts (the leg's control)."""
    conn, cfg, _ids = _t25(tmp_path)
    try:
        before = _dump(conn)
        if leg in _A2_99_REFUSALS:
            world, evidence = _mutated_evidence(tmp_path, leg)
            with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
                _apply(conn, cfg, frozen_value_evidence=evidence,
                       evidence_repo=world.work)
            message = str(exc.value)
            assert "tier2_evidence_refused" in message, message
            assert _A2_99_REFUSALS[leg] in message, message
        else:
            world, _sha, evidence = _publish(tmp_path)
            real = fve.evaluate_conjunction

            def uncomputed(*a, **kw):
                verdict = real(*a, **kw)
                assert verdict.admitted and verdict.evidence is not None, verdict
                blob = dict(verdict.evidence)
                del blob["interval"]
                return fve.ConjunctionVerdict(admitted=True, criterion=None,
                                              reason=None, field=None, evidence=blob)
            monkeypatch.setattr(fve, "evaluate_conjunction", uncomputed)
            with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
                _apply(conn, cfg, frozen_value_evidence=evidence,
                       evidence_repo=world.work)
        assert conn.in_transaction is False
        assert _dump(conn) == before
        assert _trade_keys(conn) == (None, None, "manual_off_pipeline")
    finally:
        conn.close()
    if leg == "trigger_interval_uncomputed":
        # The control: the SAME wrapped path with the interval intact admits.
        def intact(*a, **kw):
            return real(*a, **kw)
        monkeypatch.setattr(fve, "evaluate_conjunction", intact)
        conn, cfg, _ids = _t25(tmp_path, "t25-control")
        try:
            result = _apply(conn, cfg, frozen_value_evidence=evidence,
                            evidence_repo=world.work)
            assert result.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        finally:
            conn.close()


# --------------------------------------------------------------------------- A2-100

def test_a2_100_replay_rewritten_drops_h1_by_one_named_grown_admits_unchanged(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """Brief 4.3, on the H1-count harness (trade 25 + one closed H1 peer).
    ADMIT: N = 2.  REWRITTEN (the cited commit dropped from origin/main): N = 1,
    trade 25 excluded BY NAME as stale.  GROWN (descendants added): the
    verdict is ADMIT and N is unchanged at 2."""
    from swing.recommendations.hypothesis import compute_tripwire_status

    counts: dict[str, tuple] = {}
    for state in ("admit", "rewritten", "grown"):
        (tmp_path / state).mkdir()
        with monkeypatch.context() as m:
            conn = _world(tmp_path / state, m, state)
            try:
                tw = compute_tripwire_status(conn, hypothesis_id=H1_ID,
                                             starting_equity=1200.0)
                read = fve.tier2_cohort_exclusions(conn, now=fve.datetime.now(fve.UTC))
                counts[state] = (tw.current_sample, tw.tier2_excluded,
                                 set(read.exclusions))
            finally:
                conn.close()
    assert counts["admit"] == (2, (), set())
    n, excluded, ids = counts["rewritten"]
    assert n == counts["admit"][0] - 1 == 1
    assert excluded == ((T25_TRADE_ID, fve.VERDICT_STALE,
                         "criterion 1: not_ancestor_of_origin_main"),)
    assert ids == {T25_TRADE_ID}
    assert counts["grown"] == counts["admit"]


# --------------------------------------------------------------------------- A2-101

def test_a2_101_the_predicate_closure_holds_against_the_migrated_head_schema(
    tmp_path: Path, monkeypatch,
) -> None:
    """Brief 4.4 = A2-60 re-asserted: the trigger text is read from the
    MIGRATED database's ``sqlite_master`` (what ships), not the migration
    file, and A2-60's both-directions check runs over it."""
    from tests.trades import test_22a2_conjunction as conj

    conn = ensure_schema(tmp_path / "head.db")
    try:
        stored = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            ("trg_provenance_corrections_citation_graph",)).fetchone()[0]
    finally:
        conn.close()
    _path, file_text = conj.head_create_statement(
        "trg_provenance_corrections_citation_graph")
    assert conj._MARKER.findall(stored) == conj._MARKER.findall(file_text)
    monkeypatch.setattr(conj, "head_create_statement",
                        lambda name: (tmp_path / "head.db", stored))
    conj.test_a2_60_every_trigger_predicate_has_a_reached_service_check()


# --------------------------------------------------------------------------- A2-102

def test_a2_102_the_22a_six_case_gate_is_byte_unchanged_on_the_final_head() -> None:
    """Brief 4.5 = A2-09, green on the final head."""
    from tests.trades.test_22a2_case_closure import (
        test_a2_09_six_case_functions_are_byte_unchanged as a2_09,
    )
    a2_09()


# --------------------------------------------------------------------------- A2-103

def test_a2_103_the_tier_enum_drift_tests_hold(tmp_path: Path) -> None:
    """Brief 4.6 = A2-23 + A2-25 (the #11 comparators)."""
    from tests.data.test_migration_0039_provenance_corrections_tier2 import (
        test_a2_23_sql_admission_tier_check_equals_the_python_enum as a2_23,
    )
    from tests.data.test_migration_0039_provenance_corrections_tier2 import (
        test_a2_25_trigger_literals_equal_their_python_mirrors as a2_25,
    )
    a2_23(tmp_path)
    a2_25()


# --------------------------------------------------------------------------- A2-104

def _real_repo_has(obj: str) -> bool:
    try:
        proc = subprocess.run(["git", "cat-file", "-e", obj], cwd=str(REPO_ROOT),
                              capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def test_a2_104_the_fixture_is_the_record_in_the_real_repo() -> None:
    """``git show 9f315cc6:docs/rd-state.md`` line 57 (BYTES, split on
    ``b"\\n"``, index 56) hashes to the pinned sha256, and the committed
    fixture is those exact bytes.  Skipped ONLY when the object is absent."""
    if not _real_repo_has(SHA_9F315CC6):
        pytest.skip("9f315cc6 is not in this clone (git cat-file -e failed)")
    proc = subprocess.run(["git", "show", f"{SHA_9F315CC6}:{RD_STATE}"],
                          cwd=str(REPO_ROOT), capture_output=True, timeout=30,
                          check=True)
    line57 = proc.stdout.split(b"\n")[56]
    assert b"\r" not in line57
    assert len(line57) == 1015
    assert len(line57.decode("utf-8")) == 1005
    assert hashlib.sha256(line57).hexdigest() == LINE57_SHA256
    assert line57 == LINE57
