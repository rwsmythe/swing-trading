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
call, resolving the remote ref ONCE per call (CHARC G-T9 item 2; no cache
across calls) under an optional TOTAL wall-clock budget (CHARC R4.2 ruling 1).

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


def _tier2_world(tmp_path: Path, *, pristine_copy: Path | None = None) -> _World:
    """A real tier-2 row, written by the correction service, over a git world.
    ``pristine_copy``: a byte copy of the same world taken BEFORE the correction
    (the A-R1 raw-insert discriminators plant their row there)."""
    world = GitWorld(tmp_path / "evidence-git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, _rd_state_bytes(LINE57), author_date=T25_AUTHOR_INSTANT)
    world.push()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "artifact_path": RD_STATE, "artifact_commit_sha": sha,
        "quoted_text": LINE57.decode("utf-8")}), encoding="utf-8")
    conn, cfg = _t25(tmp_path)
    if pristine_copy is not None:
        pristine_copy.parent.mkdir(parents=True, exist_ok=True)
        copy = sqlite3.connect(pristine_copy)
        try:
            conn.backup(copy)
        finally:
            copy.close()
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

def _ref_resolutions(counter: _GitCounter) -> tuple[int, int]:
    """(``rev-parse`` calls, reflog reads) among the counted git calls."""
    rev_parse = sum(1 for c in counter.calls if c[1:2] == ("rev-parse",))
    reflog = sum(1 for c in counter.calls if c[1:3] == ("log", "-g"))
    return rev_parse, reflog


def _three_rows(w: _World) -> list:
    """Trade 25's row and two duck-typed copies (the model refuses a trade id
    its snapshot does not carry), each citing the same commit."""
    return [w.row] + [
        SimpleNamespace(**{**dataclasses.asdict(w.row),
                           "provenance_correction_id": 90 + n, "trade_id": 90 + n})
        for n in (1, 2)]


def test_a2_89_one_replay_per_row_and_one_ref_resolution_per_invocation(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """CHARC G-T9 item 2 (the per-row memo DROPPED): (i) one ``replay_verdict``
    per tier-2 row per invocation; (ii) exactly ONE ref resolution (one
    ``rev-parse`` + one reflog read) per invocation regardless of row count --
    a per-row-resolve impl makes THREE of each here; (iii) a SECOND invocation
    re-resolves and re-runs git -- a module-level cache makes zero calls.  The
    per-row calls (``show``, ``cat-file``, ``merge-base``) stay per row: each
    row cites its own commit."""
    w = _tier2_world(tmp_path)
    try:
        w.git.rewrite_remote_dropping(w.sha)
        tip = w.git.remote_tip()     # before the counter: it runs git itself
        rows = _three_rows(w)
        monkeypatch.setattr(fve, "_tier2_rows", lambda conn: rows)
        replays: list[int] = []
        real = fve.replay_verdict

        def counting(conn, row, **kw):
            replays.append(row.provenance_correction_id)
            return real(conn, row, **kw)

        monkeypatch.setattr(fve, "replay_verdict", counting)
        counter = _GitCounter(monkeypatch)
        first = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work).exclusions
        assert set(first) == {T25_TRADE_ID, 91, 92}
        for v in first.values():
            assert (v.verdict, v.reason) == ("tier2_evidence_stale",
                                             "criterion 1: not_ancestor_of_origin_main")
            assert v.resolved_origin_main_sha == tip
        # (i)
        assert replays == [r.provenance_correction_id for r in rows]
        # (ii)
        assert _ref_resolutions(counter) == (1, 1)
        assert sum(1 for c in counter.calls if c[1:2] == ("show",)) == 3
        calls_first = len(counter.calls)
        # (iii) A SECOND invocation re-resolves: no cache across calls (a
        # cached verdict is a stored grade, F10-shape).
        second = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work).exclusions
        assert set(second) == {T25_TRADE_ID, 91, 92}
        assert len(replays) == 6
        assert _ref_resolutions(counter) == (2, 2)
        assert len(counter.calls) == 2 * calls_first
    finally:
        w.conn.close()


def test_a_direct_replay_resolves_the_ref_itself(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """The write path and a direct call are unchanged: with no resolution
    passed, ``replay_verdict`` resolves the ref itself (one of each)."""
    w = _tier2_world(tmp_path)
    try:
        counter = _GitCounter(monkeypatch)
        assert _replay(w).verdict == "ADMIT"
        assert _ref_resolutions(counter) == (1, 1)
    finally:
        w.conn.close()


def test_a_resolution_for_another_repo_is_refused_not_used(
    tmp_path: Path, ticking_clock,
) -> None:
    """A resolution read in one repo never stands in for another's ref."""
    w = _tier2_world(tmp_path)
    try:
        other = fve.resolve_remote_ref(tmp_path)
        v = _replay(w, resolution=other)
        assert v.verdict == "tier2_unverifiable"
        assert "resolution" in v.reason
        own = fve.resolve_remote_ref(w.git.work)
        assert own.resolved_sha == w.git.remote_tip()
        assert _replay(w, resolution=own).verdict == "ADMIT"
    finally:
        w.conn.close()


def test_the_drift_reader_resolves_the_ref_once_per_invocation(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """``read_provenance_corrections`` is the second invocation site (CHARC
    G-T9): three tier-2 reports, ONE ``rev-parse`` + ONE reflog read; a second
    read re-resolves."""
    w = _tier2_world(tmp_path)
    try:
        monkeypatch.setattr(fve, "EVIDENCE_REPO_DIR", w.git.work)
        real_inner = cpc._read_provenance_corrections_inner

        def tripled(conn, **kw):
            (report,) = real_inner(conn, **kw)
            return [dataclasses.replace(report, correction=row) for row in _three_rows(w)]

        monkeypatch.setattr(cpc, "_read_provenance_corrections_inner", tripled)
        counter = _GitCounter(monkeypatch)
        reports = cpc.read_provenance_corrections(w.conn, now=NOW)
        assert [r.replay.verdict for r in reports] == ["ADMIT"] * 3
        assert _ref_resolutions(counter) == (1, 1)
        cpc.read_provenance_corrections(w.conn, now=NOW)
        assert _ref_resolutions(counter) == (2, 2)
    finally:
        w.conn.close()


def test_the_invocation_resolves_no_ref_under_a_caller_held_transaction(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """S12.1 #9 at the invocation: the per-invocation resolution never runs git
    inside a caller-held transaction; each row reads unverifiable, zero git."""
    w = _tier2_world(tmp_path)
    try:
        counter = _GitCounter(monkeypatch)
        w.conn.execute("BEGIN")
        try:
            out = fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work).exclusions
            (report,) = cpc.read_provenance_corrections(w.conn, now=NOW)
        finally:
            w.conn.rollback()
        assert (out[T25_TRADE_ID].verdict, out[T25_TRADE_ID].reason) == (
            "tier2_unverifiable", "caller_holds_transaction")
        assert (report.replay.verdict, report.replay.reason) == (
            "tier2_unverifiable", "caller_holds_transaction")
        assert counter.calls == []
    finally:
        w.conn.close()


def test_an_admitted_row_is_not_an_exclusion(tmp_path: Path, ticking_clock) -> None:
    w = _tier2_world(tmp_path)
    try:
        assert fve.tier2_cohort_exclusions(w.conn, now=NOW, repo_dir=w.git.work) == (
            fve.Tier2CohortRead(exclusions={}, observations={}))
    finally:
        w.conn.close()


def test_zero_tier2_rows_make_zero_git_calls(tmp_path: Path, monkeypatch) -> None:
    from tests._tier2_world_22a2 import build_pre_barrier_world

    conn, _ids = build_pre_barrier_world(tmp_path, "empty")
    try:
        counter = _GitCounter(monkeypatch)
        empty = fve.Tier2CohortRead(exclusions={}, observations={})
        assert fve.tier2_cohort_exclusions(conn, now=NOW) == empty
        assert fve.tier2_cohort_exclusions(conn, now=NOW, budget_seconds=0.0) == empty
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
                                          budget_seconds=0.0).exclusions
        assert set(out) == {T25_TRADE_ID, 26}
        for v in out.values():
            assert (v.verdict, v.reason) == ("tier2_unverifiable", "web_budget_exhausted")
        assert counter.calls == []
        assert fve.tier2_cohort_exclusions(
            w.conn, now=NOW, repo_dir=w.git.work).exclusions == {}
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
                                          budget_seconds=0.5).exclusions
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


# ------------------------------------------------------ G-T7F-AMEND (CHARC; RD's dissent)
# A moved DERIVATION version is CONTEXT DRIFT, never divergence: the verdict
# follows the RECOMPUTATION under current code; the moved version is an
# OBSERVATION beside it, and it is on the reason line of every key mismatch.

OLD_DERIVATION = "2026-09-01.1"


def _stored_under(w: _World, version: str, **forge):
    """The row as if written under an OLDER derivation version (and, optionally,
    one verdict-bearing value forged)."""
    blob = json.loads(w.row.cited_frozen_value_evidence_json)
    blob["derivation_version"] = version
    for dotted, value in forge.items():
        node = blob
        *head, last = dotted.split(".")
        for part in head:
            node = node[part]
        node[last] = value
    return dataclasses.replace(w.row, cited_frozen_value_evidence_json=json.dumps(blob))


def _moved(stored: str) -> str:
    return (f"derivation_version_moved (stored {stored}, "
            f"current {fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION})")


def test_g_t7f_amend_derivation_bumped_keys_equal_admits_with_the_observation(
    tmp_path: Path, ticking_clock,
) -> None:
    """PRE (a version-only-stale impl): ``tier2_evidence_stale`` because the
    version moved.  POST: ADMIT -- the fresh recomputation under current code
    agrees on every verdict-bearing key -- with the observation beside it."""
    w = _tier2_world(tmp_path)
    try:
        stored = json.loads(w.row.cited_frozen_value_evidence_json)
        assert stored["derivation_version"] == fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
        assert OLD_DERIVATION != fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
        v = _replay(w, _stored_under(w, OLD_DERIVATION))
        assert (v.verdict, v.reason) == ("ADMIT", None), v
        assert v.derivation_observation == _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


def test_g_t7f_amend_derivation_bumped_one_key_differs_names_both(
    tmp_path: Path, ticking_clock,
) -> None:
    """PRE (a keys-only impl): the reason names the key and omits the version.
    POST: stale, naming BOTH the mismatched key AND the moved version."""
    w = _tier2_world(tmp_path)
    try:
        row = _stored_under(w, OLD_DERIVATION, **{
            "interval.endpoints.fire_hi.raw": "2026-08-07T17:39:08"})
        v = _replay(w, row)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == ("interval.endpoints.fire_hi.raw_mismatch; "
                            + _moved(OLD_DERIVATION))
        assert v.derivation_observation == _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


def test_g_t7f_amend_a_moved_version_is_on_every_stale_reason_line(
    tmp_path: Path, ticking_clock,
) -> None:
    """The encoding of "the moved version is always on the reason line": a
    CRITERION refusal under a moved derivation version names it too (a code
    change can never read as an evidence change).  The observation rides
    beside an unverifiable verdict without entering its reason."""
    w = _tier2_world(tmp_path)
    try:
        row = _stored_under(w, OLD_DERIVATION)
        w.git.rewrite_remote_dropping(w.sha)
        v = _replay(w, row)
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == ("criterion 1: not_ancestor_of_origin_main; "
                            + _moved(OLD_DERIVATION))
        git(w.git.work, "update-ref", "-d", "refs/remotes/origin/main")
        v = _replay(w, row)
        assert v.verdict == "tier2_unverifiable"
        assert "derivation_version_moved" not in v.reason
        assert v.derivation_observation == _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


def test_g_t7f_amend_derivation_unchanged_carries_no_observation(
    tmp_path: Path, ticking_clock,
) -> None:
    """The counterfactual: an unmoved version is ADMIT with NO observation, and
    a key mismatch under it names the key alone (A2-86's reason, unchanged)."""
    w = _tier2_world(tmp_path)
    try:
        v = _replay(w)
        assert (v.verdict, v.reason, v.derivation_observation) == ("ADMIT", None, None)
        current = fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
        v = _replay(w, _stored_under(w, current, **{
            "interval.endpoints.fire_hi.raw": "2026-08-07T17:39:08"}))
        assert v.reason == "interval.endpoints.fire_hi.raw_mismatch"
        assert v.derivation_observation is None
    finally:
        w.conn.close()


def test_g_t7f_amend_no_evidence_version_moved_reason_exists_anywhere() -> None:
    """G-T7F renamed G-T7 Q2's reason and the AMEND made it an observation: a
    moved GRAMMAR version cannot reach replay (the trigger refuses the write)."""
    swing_root = Path(fve.__file__).resolve().parents[1]
    hits = [str(path) for path in swing_root.rglob("*.py")
            if "evidence_version_moved" in path.read_bytes().decode("utf-8")]
    assert hits == []
    assert "derivation_observation" in {f.name for f in dataclasses.fields(fve.ReplayVerdict)}
    assert dataclasses.fields(fve.ReplayVerdict)[-1].name == "derivation_observation"


def test_g_t7f_amend_the_drift_reader_renders_the_observation_on_its_own_line(
    tmp_path: Path, monkeypatch,
) -> None:
    """The observation is rendered on ITS OWN line (A2-90 pins the verdict
    line's ending); absent when the version has not moved."""
    from swing.cli import main
    from tests.cli.test_correct_cohort_provenance_command import _t25_world

    runner, argv, _db, evidence = _t25_world(tmp_path / "t2", monkeypatch)
    r = runner.invoke(main, [*argv, "--reason", "tier-2", "--frozen-value-evidence",
                             str(evidence)])
    assert r.exit_code == 0, r.output
    read = [argv[0], argv[1], "journal", "provenance-corrections"]
    r = runner.invoke(main, read)
    assert r.exit_code == 0, r.output
    assert "derivation_version_moved" not in r.output
    written = fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
    monkeypatch.setattr(fve, "FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION", "2099-01-01.1")
    r = runner.invoke(main, read)
    assert r.exit_code == 0, r.output
    r.output.encode("ascii")
    lines = r.output.splitlines()
    (verdict,) = [ln for ln in lines if "read-time verdict" in ln]
    assert verdict.startswith("  read-time verdict: ADMIT evaluated_at ")
    assert verdict.endswith("barrier installed at read True")
    assert "derivation_version_moved" not in verdict
    observed = [ln for ln in lines if "derivation_version_moved" in ln]
    assert observed == [
        f"  observation: derivation_version_moved (stored {written}, current 2099-01-01.1)"]
    assert lines.index(observed[0]) == lines.index(verdict) + 1


# ---------------------------------------------------------- G-T7FE-B (RD, ruling (a))
# When the derivation version has moved, EVERY ``tier2_evidence_stale`` reason
# carries it -- criterion refusals, ``author_instant_changed`` and
# ``<key>_mismatch`` alike; ``tier2_unverifiable`` carries it in the
# observation FIELD only; an unmoved version is on no reason.  Pins on
# behaviour encoded at abcbd632, each proven by a one-line mutation.

FORGED_AUTHOR_INSTANT = "2026-08-10T09:00:00-04:00"


def test_g_t7fe_b_a_criterion_3_refusal_under_a_moved_version_names_both(
    tmp_path: Path, ticking_clock,
) -> None:
    """The five-cent pivot.  A ``_mismatch``-only suffix impl FAILS."""
    w = _tier2_world(tmp_path)
    try:
        with candidates_barrier_lifted(w.conn):
            w.conn.execute("UPDATE candidates SET pivot = 53.93 WHERE id = ?",
                           (T25_CANDIDATE_ID,))
        w.conn.commit()
        v = _replay(w, _stored_under(w, OLD_DERIVATION))
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "criterion 3: pivot; " + _moved(OLD_DERIVATION)
        assert v.derivation_observation == _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


def test_g_t7fe_b_author_instant_changed_under_a_moved_version_names_both(
    tmp_path: Path, ticking_clock,
) -> None:
    """A ``_mismatch``-only suffix impl FAILS."""
    w = _tier2_world(tmp_path)
    try:
        v = _replay(w, _stored_under(w, OLD_DERIVATION,
                                     author_instant=FORGED_AUTHOR_INSTANT))
        assert v.verdict == "tier2_evidence_stale"
        assert v.reason == "author_instant_changed; " + _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


def test_g_t7fe_b_an_unmoved_version_is_on_no_stale_reason(
    tmp_path: Path, ticking_clock,
) -> None:
    """Every stale class under the CURRENT version: no ``derivation_version``
    token on any reason.  An always-append impl FAILS."""
    w = _tier2_world(tmp_path)
    try:
        current = fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
        reasons = [
            _replay(w, _stored_under(w, current,
                                     author_instant=FORGED_AUTHOR_INSTANT)).reason,
            _replay(w, _stored_under(w, current, **{
                "interval.endpoints.fire_hi.raw": "2026-08-07T17:39:08"})).reason,
        ]
        with candidates_barrier_lifted(w.conn):
            w.conn.execute("UPDATE candidates SET pivot = 53.93 WHERE id = ?",
                           (T25_CANDIDATE_ID,))
        w.conn.commit()
        v = _replay(w)
        reasons.append(v.reason)
        assert v.derivation_observation is None
        assert reasons == ["author_instant_changed",
                           "interval.endpoints.fire_hi.raw_mismatch",
                           "criterion 3: pivot"]
        assert not any("derivation_version" in r for r in reasons)
    finally:
        w.conn.close()


def test_g_t7fe_b_unverifiable_under_a_moved_version_carries_it_in_the_field_only(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """A hung git: no verdict was reached, so the version is context, never a
    cause.  An append-on-unverifiable impl FAILS."""
    w = _tier2_world(tmp_path)
    try:
        _GitCounter(monkeypatch, timeout=True)
        v = _replay(w, _stored_under(w, OLD_DERIVATION))
        assert v.verdict == "tier2_unverifiable"
        assert v.reason == "git rev-parse timed out after 10.0s"
        assert "derivation_version" not in v.reason
        assert v.derivation_observation == _moved(OLD_DERIVATION)
    finally:
        w.conn.close()


# --------------------------------------------------------------------------- A-R1 item 1
# RD's ruling A-R1 item 1 (R1-01): the segments and the uncovered-window prose
# are DERIVED -- a pure function of the verdict-bearing endpoints plus the
# barrier state -- so a stored value has one legitimate source, its
# recomputation.  The replay compares every segment's kind, from, to and
# seconds EXCEPT the terminal segment's kind (the one value that follows the
# barrier at READ), and checks the stored prose against its rendering of the
# STORED interval.  Every discriminator is a RAW-INSERTED row (the 18-B.1
# technique: the forgery the service can never write, planted past it) in the
# real shape, one mutated value each, on the trade-25 world.

def _raw_forged(tmp_path: Path, mutate) -> tuple[_World, sqlite3.Connection, object]:
    """``(world, conn, row)``: trade 25's truthful service-written row, its blob
    mutated by ``mutate``, RAW-INSERTED into a byte copy of the same world
    taken before the correction (same barrier, same ids) -- past the service,
    through the citation trigger, which must admit it."""
    from swing.data.db import open_connection
    from tests._tier2_world_22a2 import insert_payload
    from tests.trades.test_22a2_correction_service import _row

    pristine = tmp_path / "t25-raw" / "swing.db"
    w = _tier2_world(tmp_path, pristine_copy=pristine)
    payload = _row(w.conn)
    blob = json.loads(payload["cited_frozen_value_evidence_json"])
    mutate(blob)
    payload["cited_frozen_value_evidence_json"] = json.dumps(blob)
    conn = open_connection(pristine)
    with conn:
        insert_payload(conn, payload)
    (row,) = list_provenance_corrections(conn)
    return w, conn, row


def _raw_replay(tmp_path: Path, mutate) -> fve.ReplayVerdict:
    w, conn, row = _raw_forged(tmp_path, mutate)
    try:
        return fve.replay_verdict(conn, row, now=NOW, repo_dir=w.git.work)
    finally:
        conn.close()
        w.conn.close()


def _terminal_flip(kind: str) -> str:
    return {fve.SEGMENT_COVERED: fve.SEGMENT_UNCOVERED_BARRIER_ABSENT,
            fve.SEGMENT_UNCOVERED_BARRIER_ABSENT: fve.SEGMENT_COVERED}[kind]


def test_a_r1_i_a_negated_segment_duration_reads_segments_mismatch(
    tmp_path: Path, ticking_clock,
) -> None:
    def mutate(blob):
        seg = blob["interval"]["segments"][1]
        assert seg["kind"] == "writer_absence_only" and seg["seconds"] > 0
        seg["seconds"] = -seg["seconds"]
    v = _raw_replay(tmp_path, mutate)
    assert v.verdict == "tier2_evidence_stale"
    assert v.reason == "interval.segments_mismatch"


def test_a_r1_ii_swapped_segment_bounds_read_segments_mismatch(
    tmp_path: Path, ticking_clock,
) -> None:
    def mutate(blob):
        seg = blob["interval"]["segments"][1]
        assert seg["from"] != seg["to"]
        seg["from"], seg["to"] = seg["to"], seg["from"]
    v = _raw_replay(tmp_path, mutate)
    assert v.verdict == "tier2_evidence_stale"
    assert v.reason == "interval.segments_mismatch"


def test_a_r1_iii_only_the_terminal_kind_flipped_admits(
    tmp_path: Path, ticking_clock,
) -> None:
    """The boundary twin: the terminal kind follows the barrier at READ (E-15's
    ``covered`` segment kind), so a row written under the other barrier state
    ADMITS.  The prose is the rendering the writer would have produced for
    that interval (the prose rule is (iv)'s, pinned separately below).  An
    implementation that compares the terminal kind FAILS."""
    def mutate(blob):
        seg = blob["interval"]["segments"][-1]
        assert seg["kind"] == fve.SEGMENT_COVERED
        seg["kind"] = _terminal_flip(seg["kind"])
        blob["uncovered_window_prose"] = fve.render_uncovered_window_prose(
            blob["interval"])
    v = _raw_replay(tmp_path, mutate)
    assert v.verdict == "ADMIT", v
    assert v.reason is None


def test_a_r1_iii_the_terminal_kind_flipped_under_the_old_prose_reads_prose_mismatch(
    tmp_path: Path, ticking_clock,
) -> None:
    """The kind is exempt; the prose's CONSISTENCY with the stored interval is
    not -- the stored prose must be the rendering of the stored interval."""
    def mutate(blob):
        seg = blob["interval"]["segments"][-1]
        seg["kind"] = _terminal_flip(seg["kind"])
    v = _raw_replay(tmp_path, mutate)
    assert v.verdict == "tier2_evidence_stale"
    assert v.reason == "uncovered_window_prose_mismatch"


def test_a_r1_iv_one_changed_prose_character_reads_prose_mismatch(
    tmp_path: Path, ticking_clock,
) -> None:
    def mutate(blob):
        prose = blob["uncovered_window_prose"]
        i = prose.index("days")
        blob["uncovered_window_prose"] = prose[:i] + "D" + prose[i + 1:]
    v = _raw_replay(tmp_path, mutate)
    assert v.verdict == "tier2_evidence_stale"
    assert v.reason == "uncovered_window_prose_mismatch"


def test_a_r1_v_the_unmodified_raw_inserted_row_admits(
    tmp_path: Path, ticking_clock,
) -> None:
    v = _raw_replay(tmp_path, lambda blob: None)
    assert v.verdict == "ADMIT", v
    assert v.reason is None


def test_a_r1_a_forged_endpoint_still_speaks_before_a_forged_segment(
    tmp_path: Path, ticking_clock,
) -> None:
    """The existing sorted-key order: the endpoint keys sort first.  The forged
    endpoint is a ``utc`` rendering (SQL binds the raws and never reads a utc,
    R8-03), so the row passes the write barrier and the replay names it."""
    def mutate(blob):
        endpoint = blob["interval"]["endpoints"]["fire_hi"]
        assert endpoint["utc"] == "2026-08-08T03:39:07Z"
        endpoint["utc"] = "2026-08-08T03:39:08Z"
        blob["interval"]["segments"][1]["seconds"] += 1
        blob["uncovered_window_prose"] += "x"
    v = _raw_replay(tmp_path, mutate)
    assert v.reason == "interval.endpoints.fire_hi.utc_mismatch"
