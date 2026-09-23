"""22-A2 Task 9 -- the read-time replay (A2-81..A2-90; F10, F10-shape, P37).

A tier-2 row's stored tier is an ATTESTATION of what was verified at write
time; the VERDICT is computed at read time (RD's F10) by ONE function,
``replay_verdict``, that re-runs the write path's own evaluation -- the same
``read_artifact_facts`` and the same ``evaluate_conjunction`` -- against the
row's stored selection, and then compares the recomputed blob's
``VERDICT_BEARING_KEYS`` with the stored blob's (E-15).  It opens NO
transaction and writes nothing (P37).  A process failure is
``tier2_unverifiable``; git answering negatively, or any conjunction refusal,
is ``tier2_evidence_stale``; descendant growth and ref age are never compared
(doctrine #6).  ``tier2_cohort_exclusions`` replays every tier-2 row once per
call (a memo scoped to the call; no cache across calls) under an optional
TOTAL wall-clock budget (CHARC R4.2 ruling 1).

The world is trade 25's real row shape with a real tier-2 row written by the
correction service over a throwaway git world whose ``docs/rd-state.md`` line
57 is the pinned acceptance record.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from swing.data.repos.candidates_immutability_epoch import barrier_installed
from swing.data.models import (
    PROVENANCE_ADMISSION_TIER_LAST_WORD,
    PROVENANCE_ADMISSION_TIER_LATCH_TIER2,
)
from swing.data.repos.provenance_corrections import list_provenance_corrections
from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from tests._candidates_barrier_helper import candidates_barrier_lifted
from tests._tier2_world_22a2 import (
    LINE57_FIXTURE,
    T25_AUTHOR_INSTANT,
    T25_CANDIDATE_ID,
    T25_TRADE_ID,
)
from tests.trades._git_world import GitWorld, git
from tests.trades.test_22a2_correction_service import (  # noqa: F401 -- fixture
    RD_STATE,
    _apply,
    _rd_state_bytes,
    _t25,
    ticking_clock,
)

LINE57 = LINE57_FIXTURE.read_bytes()
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- helpers

@dataclasses.dataclass
class _World:
    conn: sqlite3.Connection
    git: GitWorld
    sha: str
    db_path: Path
    row: object


def _tier2_world(tmp_path: Path) -> _World:
    """A real tier-2 row, written by the correction service, over a git world."""
    world = GitWorld(tmp_path / "evidence-git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, _rd_state_bytes(LINE57), author_date=T25_AUTHOR_INSTANT)
    world.push()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "artifact_path": RD_STATE, "artifact_commit_sha": sha,
        "quoted_text": LINE57.decode("utf-8")}), encoding="utf-8")
    conn, cfg = _t25(tmp_path)
    result = _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=world.work)
    assert result.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
    (row,) = list_provenance_corrections(conn)
    return _World(conn=conn, git=world, sha=sha, db_path=tmp_path / "t25" / "swing.db",
                  row=row)


def _replay(w: _World, row=None, **kw) -> fve.ReplayVerdict:
    return fve.replay_verdict(w.conn, w.row if row is None else row, now=NOW,
                              repo_dir=w.git.work, **kw)


class _GitCounter:
    """Wraps ``subprocess.run`` as the module sees it: counts git calls and can
    delay each one (a SLOW git) or raise instead of running (a HUNG git)."""

    def __init__(self, monkeypatch, *, delay: float = 0.0, timeout: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._real = subprocess.run
        self._delay = delay
        self._timeout = timeout
        monkeypatch.setattr(fve.subprocess, "run", self)

    def __call__(self, args, *a, **kw):
        self.calls.append(tuple(args))
        if self._timeout:
            raise subprocess.TimeoutExpired(args, kw.get("timeout", 0))
        if self._delay:
            time.sleep(self._delay)
        return self._real(args, *a, **kw)


# --------------------------------------------------------------------------- A2-81

def test_a2_81_trade25_row_with_the_remote_unchanged_admits(
    tmp_path: Path, ticking_clock,
) -> None:
    w = _tier2_world(tmp_path)
    try:
        v = _replay(w)
        assert v.verdict == "ADMIT"
        assert v.reason is None
        assert v.evaluated_at == NOW.isoformat()
        assert v.resolved_origin_main_sha == w.git.remote_tip()
        assert v.barrier_installed_at_read is True
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-82

def test_a2_82_rewritten_remote_reads_stale_not_ancestor(
    tmp_path: Path, ticking_clock,
) -> None:
    """PRE (a stored-grade reader): the row counts.  POST: stale, named."""
    w = _tier2_world(tmp_path)
    try:
        w.git.rewrite_remote_dropping(w.sha)
        v = _replay(w)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "criterion 1: not_ancestor_of_origin_main"
        assert v.resolved_origin_main_sha == w.git.remote_tip()
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-83

def test_a2_83_grown_remote_still_admits_and_growth_is_not_compared(
    tmp_path: Path, ticking_clock,
) -> None:
    """A growth-as-staleness impl reads stale; the recomputed descendant count
    is larger than the stored one and is never compared (doctrine #6)."""
    w = _tier2_world(tmp_path)
    try:
        stored = json.loads(w.row.cited_frozen_value_evidence_json)
        w.git.grow_remote(3, push_date="2026-09-21T12:00:00+00:00")
        facts = fve.read_artifact_facts(
            fve.EvidenceSelection(stored["artifact_path"], stored["artifact_commit_sha"],
                                  stored["quoted_text"]),
            repo_dir=w.git.work, now_utc=NOW).facts
        assert facts is not None
        assert facts.descendant_count == stored["descendant_count"] + 3
        assert facts.remote_ref_updated_at.isoformat() != stored["remote_ref_updated_at"]
        v = _replay(w)
        assert v.verdict == "ADMIT", v
        assert v.resolved_origin_main_sha == w.git.remote_tip()
        assert v.resolved_origin_main_sha != stored["resolved_remote_ref_sha"]
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-84

def test_a2_84_git_timeout_and_a_missing_remote_ref_read_unverifiable(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    w = _tier2_world(tmp_path)
    try:
        with monkeypatch.context() as m:
            _GitCounter(m, timeout=True)
            v = _replay(w)
        assert v.verdict == "tier2_unverifiable"
        assert "timed out" in v.reason
        git(w.git.work, "update-ref", "-d", "refs/remotes/origin/main")
        v = _replay(w)
        assert v.verdict == "tier2_unverifiable"
        assert "refs/remotes/origin/main does not resolve" in v.reason
        assert v.resolved_origin_main_sha is None
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-85

def test_a2_85_a_changed_current_pivot_reads_stale_naming_pivot(
    tmp_path: Path, ticking_clock,
) -> None:
    """Criterion 3 at READ compares against the CURRENT candidate row (P37)."""
    w = _tier2_world(tmp_path)
    try:
        with candidates_barrier_lifted(w.conn):
            w.conn.execute("UPDATE candidates SET pivot = 53.93 WHERE id = ?",
                           (T25_CANDIDATE_ID,))
        w.conn.commit()
        assert barrier_installed(w.conn) is True     # re-armed
        v = _replay(w)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "criterion 3: pivot"
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-86

def test_a2_86_a_stored_verdict_bearing_value_differing_reads_key_mismatch(
    tmp_path: Path, ticking_clock,
) -> None:
    w = _tier2_world(tmp_path)
    try:
        blob = json.loads(w.row.cited_frozen_value_evidence_json)
        blob["interval"]["endpoints"]["fire_hi"]["raw"] = "2026-08-07T17:39:08"
        forged = dataclasses.replace(w.row, cited_frozen_value_evidence_json=json.dumps(blob))
        v = _replay(w, forged)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "interval.endpoints.fire_hi.raw_mismatch"
        # A RECORDED-only key differing is not compared (E-15).
        blob = json.loads(w.row.cited_frozen_value_evidence_json)
        blob["descendant_count"] += 7
        blob["committer_instant"] = "2030-01-01T00:00:00+00:00"
        recorded = dataclasses.replace(w.row,
                                       cited_frozen_value_evidence_json=json.dumps(blob))
        assert _replay(w, recorded).verdict == "ADMIT"
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-87

def test_a2_87_replay_opens_no_transaction_and_writes_nothing_on_a_ro_conn(
    tmp_path: Path, ticking_clock,
) -> None:
    w = _tier2_world(tmp_path)
    w.conn.close()
    ro = sqlite3.connect(f"file:{w.db_path.as_posix()}?mode=ro", uri=True)
    try:
        before = ro.total_changes
        v = fve.replay_verdict(ro, w.row, now=NOW, repo_dir=w.git.work)
        assert v.verdict == "ADMIT", v
        assert ro.total_changes == before
        assert ro.in_transaction is False
    finally:
        ro.close()


def test_replay_refuses_inside_a_caller_held_transaction_without_git(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """S12.1 #9 (no git inside a transaction) at the replay, CHARC's G-T7 Q1
    principle: a caller-held transaction reads unverifiable, and NO git
    subprocess starts.  Twin: the same call outside the transaction admits."""
    w = _tier2_world(tmp_path)
    try:
        counter = _GitCounter(monkeypatch)
        w.conn.execute("BEGIN")
        try:
            v = _replay(w)
        finally:
            w.conn.rollback()
        assert v.verdict == "tier2_unverifiable"
        assert v.reason == "caller_holds_transaction"
        assert counter.calls == []
        assert _replay(w).verdict == "ADMIT"
        assert counter.calls
    finally:
        w.conn.close()


@pytest.mark.parametrize("bad", ["not-a-date", "2026-W33-1", None])
def test_a_malformed_fill_session_reads_a_typed_stale_reason(
    tmp_path: Path, ticking_clock, bad,
) -> None:
    """The TEXT -> date boundary (CLAUDE.md gotcha): a typed stale reason,
    never a deep TypeError.  The model refuses these values at construction,
    so the row is a duck-typed copy."""
    w = _tier2_world(tmp_path)
    try:
        row = SimpleNamespace(**dataclasses.asdict(w.row))
        row.entry_fill_session_date = bad
        v = _replay(w, row)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "entry_fill_session_date_malformed"
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-88

def test_a2_88_barrier_absent_at_read_is_an_observation_only(
    tmp_path: Path, ticking_clock,
) -> None:
    w = _tier2_world(tmp_path)
    try:
        with candidates_barrier_lifted(w.conn):
            assert w.conn.in_transaction is False
            v = _replay(w)
        assert v.verdict == "ADMIT", v
        assert v.barrier_installed_at_read is False
        assert _replay(w).barrier_installed_at_read is True
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-89

def test_a2_89_one_replay_per_row_per_call_and_no_cache_across_calls(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    w = _tier2_world(tmp_path)
    try:
        w.git.rewrite_remote_dropping(w.sha)
        replays: list[int] = []
        real = fve.replay_verdict

        def counting(conn, row, **kw):
            replays.append(row.provenance_correction_id)
            return real(conn, row, **kw)

        monkeypatch.setattr(fve, "replay_verdict", counting)
        counter = _GitCounter(monkeypatch)
        first = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work)
        assert set(first) == {T25_TRADE_ID}
        assert first[T25_TRADE_ID].verdict == "tier2_evidence_stale"
        assert replays == [w.row.provenance_correction_id]
        calls_first = len(counter.calls)
        assert calls_first > 0
        # A SECOND call re-runs git: a cached verdict is a stored grade.
        second = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work)
        assert second[T25_TRADE_ID].verdict == "tier2_evidence_stale"
        assert len(replays) == 2
        assert len(counter.calls) == 2 * calls_first
        # The memo: the same row selected twice in ONE call replays once.
        monkeypatch.setattr(fve, "_tier2_rows", lambda conn: [w.row, w.row])
        fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work)
        assert len(replays) == 3
    finally:
        w.conn.close()


def test_an_admitted_row_is_not_an_exclusion(tmp_path: Path, ticking_clock) -> None:
    w = _tier2_world(tmp_path)
    try:
        assert fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work) == {}
    finally:
        w.conn.close()


def test_zero_tier2_rows_make_zero_git_calls(tmp_path: Path, monkeypatch) -> None:
    from tests._tier2_world_22a2 import build_pre_barrier_world

    conn, _ids = build_pre_barrier_world(tmp_path, "empty")
    try:
        counter = _GitCounter(monkeypatch)
        assert fve.tier2_cohort_exclusions(conn, now=NOW) == {}
        assert fve.tier2_cohort_exclusions(conn, now=NOW, budget_seconds=0.0) == {}
        assert counter.calls == []
    finally:
        conn.close()


def test_an_exhausted_budget_excludes_every_unverdicted_row_by_name(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """Budget 0: no row is reached, none replays, no git starts; each row reads
    ``tier2_unverifiable`` / ``web_budget_exhausted`` -- excluded, never admitted.
    The row would ADMIT unbudgeted (the counterfactual)."""
    w = _tier2_world(tmp_path)
    try:
        # A second tier-2 row (the model refuses a trade id its snapshot does
        # not carry, so it is a duck-typed copy; it is never replayed here).
        other = SimpleNamespace(**{**dataclasses.asdict(w.row),
                                   "provenance_correction_id": 99, "trade_id": 26})
        monkeypatch.setattr(fve, "_tier2_rows", lambda conn: [w.row, other])
        counter = _GitCounter(monkeypatch)
        out = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work,
                                          budget_seconds=0.0)
        assert set(out) == {T25_TRADE_ID, 26}
        for v in out.values():
            assert (v.verdict, v.reason) == ("tier2_unverifiable", "web_budget_exhausted")
        assert counter.calls == []
        assert fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work) == {}
    finally:
        w.conn.close()


def test_the_budget_is_checked_between_git_calls_not_only_between_rows(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """A slow git (each call 1.0 s) under a 0.5 s budget: the FIRST call starts
    inside the budget and is let finish (never killed mid-flight); the second is
    never started.  PRE (a between-rows-only check): all of the row's git calls
    run and the row is verdicted on them."""
    w = _tier2_world(tmp_path)
    try:
        counter = _GitCounter(monkeypatch, delay=1.0)
        started = time.monotonic()
        out = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work,
                                          budget_seconds=0.5)
        elapsed = time.monotonic() - started
        assert (out[T25_TRADE_ID].verdict, out[T25_TRADE_ID].reason) == (
            "tier2_unverifiable", "web_budget_exhausted")
        assert len(counter.calls) == 1
        assert elapsed < 0.5 + fve.GIT_TIMEOUT_SECONDS
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A2-90

def test_a2_90_the_drift_reader_renders_the_read_time_verdict_for_tier2_only(
    tmp_path: Path, monkeypatch,
) -> None:
    from swing.cli import main
    from tests.cli.test_correct_cohort_provenance_command import (
        _cmd,
        _seed,
        _setup,
        _t25_world,
    )

    # A last_word row renders as today: no verdict line, no git.
    runner, cfg, db = _setup(tmp_path / "lw", monkeypatch)
    ids = _seed(db)
    assert runner.invoke(main, _cmd(cfg, ids, "--reason", "record")).exit_code == 0
    with monkeypatch.context() as m:
        counter = _GitCounter(m)
        r = runner.invoke(main, ["--config", str(cfg), "journal", "provenance-corrections"])
        assert r.exit_code == 0, r.output
        assert counter.calls == []
    assert "read-time verdict" not in r.output
    assert "no citation drift." in r.output
    plain = sqlite3.connect(db)
    try:
        (lw,) = cpc.read_provenance_corrections(plain)
    finally:
        plain.close()
    assert lw.correction.admission_tier == PROVENANCE_ADMISSION_TIER_LAST_WORD
    assert lw.replay is None

    # A tier-2 row renders its verdict line, ASCII.
    runner, argv, db, evidence = _t25_world(tmp_path / "t2", monkeypatch)
    r = runner.invoke(main, [*argv, "--reason", "tier-2", "--frozen-value-evidence",
                             str(evidence)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, [argv[0], argv[1], "journal", "provenance-corrections"])
    assert r.exit_code == 0, r.output
    r.output.encode("ascii")
    lines = [ln for ln in r.output.splitlines() if "read-time verdict" in ln]
    assert len(lines) == 1, r.output
    tip = git(fve.EVIDENCE_REPO_DIR, "rev-parse", "refs/remotes/origin/main")
    assert lines[0].startswith("  read-time verdict: ADMIT evaluated_at ")
    assert f"origin/main {tip.decode('ascii').strip()}" in lines[0]
    assert lines[0].endswith("barrier installed at read True")
