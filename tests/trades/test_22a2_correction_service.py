"""22-A2 Task 7 -- the correction service's tier-2 wiring (A2-67..A2-76).

The world is trade 25's REAL row shape (``tests/_tier2_world_22a2.py``) with a
``pre_barrier_reconstructed`` link, and the evidence is a SELECTION into a
throwaway git world (``tests/trades/_git_world.py``) whose ``docs/rd-state.md``
line 57 is the pinned acceptance record, authored at 9f315cc6's measured
instant and published to ``refs/remotes/origin/main``.  Nothing here is
built to satisfy the premise: the conjunction runs on the real candidate row.

What these tests pin is the WIRING, not the conjunction (Task 5) or the seam
(Task 6): the preflight runs BEFORE any transaction (S12.1 #9), SELECT-first
still precedes every payload refusal (E-6), ONE ``applied_at`` stamp is the
column, the blob's ``evaluated_at`` and the interval's ``read_at`` (E-7), the
tier is DETECTED (never chosen), supplied evidence is never silently ignored
(R0.10 encoding 3, E-18), and the dry run authorizes exactly as the apply
does while leaving the DB byte-identical.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from swing.data.models import (
    PROVENANCE_ADMISSION_TIER_LAST_WORD,
    PROVENANCE_ADMISSION_TIER_LATCH_TIER2,
)
from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import (
    LINE57_FIXTURE,
    T25_AUTHOR_INSTANT,
    T25_CANDIDATE_ID,
    T25_FILL_ID,
    T25_REC_ID,
    T25_TRADE_ID,
    build_last_word_world,
    build_pre_barrier_world,
    t25_cfg,
)
from tests.trades._git_world import GitWorld

REPO_ROOT = Path(__file__).resolve().parents[2]
SWING_ROOT = REPO_ROOT / "swing"
LINE57 = LINE57_FIXTURE.read_bytes()
RD_STATE = "docs/rd-state.md"
REASON = "22-A2 Task 7: trade 25's tier-2 correction"
TIER2_NOTE = ("already applied; evidence not re-evaluated here -- the read-time "
              "verdict is on journal provenance-corrections")
NOT_CONSULTED = "the supplied --frozen-value-evidence was not consulted"
NO_LATCH = ("no accepted latch order: tier-2 evidence is admissible only as rung "
            "9's escape on a pre-barrier linked mandate")


# --------------------------------------------------------------------------- helpers

def _stamp(instant: datetime) -> str:
    """The production audit-stamp grammar: naive UTC, millisecond precision."""
    naive = instant.astimezone(UTC).replace(tzinfo=None)
    return naive.strftime("%Y-%m-%dT%H:%M:%S.") + f"{naive.microsecond // 1000:03d}"


@pytest.fixture
def ticking_clock(monkeypatch):
    """Every read of the audit clock returns a DISTINCT stamp one second apart,
    AFTER the world's barrier was armed (now) -- so two reads can never agree
    by coincidence (A2-68's discriminator)."""
    base = datetime.now(UTC) + timedelta(minutes=5)
    calls: list[str] = []

    def _clock() -> str:
        value = _stamp(base + timedelta(seconds=len(calls)))
        calls.append(value)
        return value

    monkeypatch.setattr(cpc, "_APPLIED_AT_CLOCK", _clock)
    return calls


def _rd_state_bytes(line57: bytes) -> bytes:
    lines = [f"line {i}".encode("ascii") for i in range(1, 57)]
    return b"\n".join([*lines, line57, b"line 58", b""])


def _evidence(tmp_path: Path, *, line57: bytes = LINE57,
              name: str = "evidence") -> tuple[Path, Path]:
    """``(repo_dir, evidence_file)``: the record published, the selection written."""
    world = GitWorld(tmp_path / f"{name}-git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, _rd_state_bytes(line57), author_date=T25_AUTHOR_INSTANT)
    world.push()
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({
        "artifact_path": RD_STATE, "artifact_commit_sha": sha,
        "quoted_text": line57.decode("utf-8")}), encoding="utf-8")
    return world.work, path


def _pivot_absent_line() -> bytes:
    """Line 57 with the pivot numeral replaced: ticker and session still present,
    so the conjunction's criterion 3 names ``pivot`` (its order is ticker ->
    action_session -> pivot -> invalidation)."""
    changed = LINE57.replace(b"53.98", b"53.93")
    assert changed != LINE57 and b"53.98" not in changed
    return changed


def _t25(tmp_path: Path, name: str = "t25", **kw):
    conn, _ids = build_pre_barrier_world(tmp_path, name, **kw)
    return conn, t25_cfg(tmp_path / name)


def _apply(conn, cfg, **kw) -> cpc.CohortProvenanceCorrectionResult:
    return cpc.correct_cohort_provenance(
        conn, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
        cited_recommendation_id=T25_REC_ID, reason=REASON, cfg=cfg, **kw)


def _preview(conn, cfg, **kw) -> cpc.CohortProvenanceCorrectionPreview:
    return cpc.preview_cohort_provenance_correction(
        conn, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
        cited_recommendation_id=T25_REC_ID, reason=REASON, cfg=cfg, **kw)


def _row(conn) -> dict:
    cur = conn.execute("SELECT * FROM provenance_corrections")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    assert len(rows) == 1, rows
    return dict(zip(cols, rows[0], strict=True))


def _count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM provenance_corrections").fetchone()[0]


def _trade_keys(conn) -> tuple:
    return conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin FROM trades WHERE id = ?",
        (T25_TRADE_ID,)).fetchone()


# --------------------------------------------------------------------------- A2-67

def test_a2_67_trade25_world_applies_as_latch_ladder_tier2(
    tmp_path: Path, ticking_clock,
) -> None:
    """PRE: the service has no evidence input -> the ladder refuses
    ``pre_barrier_unproven``.  POST: the tier is DETECTED as tier-2 and all six
    citation columns are written."""
    repo, evidence = _evidence(tmp_path)
    conn, cfg = _t25(tmp_path)
    try:
        result = _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert result.already_applied is False
        assert result.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        row = _row(conn)
        assert row["admission_tier"] == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        for col in ("cited_latch_link_id", "cited_latch_validity_intent_id",
                    "cited_latch_place_intent_id", "cited_latch_broker_order_id",
                    "cited_latch_probe_json", "cited_frozen_value_evidence_json"):
            assert row[col] is not None, col
        blob = json.loads(row["cited_frozen_value_evidence_json"])
        assert blob["evidence_version"] == fve.FROZEN_VALUE_EVIDENCE_VERSION
        assert blob["quoted_text"] == LINE57.decode("utf-8")
        assert blob["interval"]["record_position"] == "before_barrier"
        assert _trade_keys(conn) == ("A+ baseline (aplus)", T25_CANDIDATE_ID,
                                     "pipeline_aplus")
        # The operator surface carries the four clauses and the prose.
        assert [c.split(" ")[:2] for c, _ in result.tier2_clauses] == [
            ["criterion", str(n)] for n in (1, 2, 3, 4)]
        assert [v for _, v in result.tier2_clauses] == ["PASS"] * 4
        assert blob["artifact_commit_sha"] in result.tier2_clauses[0][0]
        assert "pivot 53.98, invalidation 41.42" in result.tier2_clauses[2][0]
        assert result.tier2_interval_prose == blob["uncovered_window_prose"]
        assert result.tier2_note is None
    finally:
        conn.close()


def test_without_evidence_the_pre_barrier_ladder_still_refuses(
    tmp_path: Path, ticking_clock,
) -> None:
    """A2-67's counterfactual (no roster id of its own): the escape is opt-in --
    no evidence -> 22-A's refusal, nothing written."""
    conn, cfg = _t25(tmp_path)
    try:
        with pytest.raises(cpc.CohortProvenanceCorrectionError,
                           match="pre_barrier_unproven") as exc:
            _apply(conn, cfg)
        assert NOT_CONSULTED not in str(exc.value)
        assert _count(conn) == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-68

def test_a2_68_one_stamp_is_the_column_the_evaluated_at_and_the_read_at(
    tmp_path: Path, ticking_clock,
) -> None:
    """PRE: the column is stamped at INSERT and the blob before it -- two clock
    reads, and this clock never returns the same value twice.  POST: equal."""
    repo, evidence = _evidence(tmp_path)
    conn, cfg = _t25(tmp_path)
    try:
        _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        row = _row(conn)
        blob = json.loads(row["cited_frozen_value_evidence_json"])
        assert row["applied_at"] == blob["evaluated_at"]
        assert row["applied_at"] == blob["interval"]["endpoints"]["read_at"]["raw"]
        assert row["applied_at"] in ticking_clock
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-69

@pytest.mark.parametrize("entry", ["apply", "preview"])
def test_a2_69_the_preflight_runs_before_any_transaction(
    tmp_path: Path, ticking_clock, monkeypatch, entry: str,
) -> None:
    """Every git call observes ``conn.in_transaction is False`` (S12.1 #9)."""
    repo, evidence = _evidence(tmp_path)
    conn, cfg = _t25(tmp_path)
    real = fve._run_git
    observed: list[bool] = []

    def _watched(repo_dir, *args):
        observed.append(conn.in_transaction)
        return real(repo_dir, *args)

    monkeypatch.setattr(fve, "_run_git", _watched)
    try:
        call = _apply if entry == "apply" else _preview
        out = call(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert out.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        assert observed, "the preflight never ran git"
        assert observed == [False] * len(observed)
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-70

@pytest.mark.parametrize("bad", ["malformed", "missing"])
def test_a2_70_already_applied_returns_the_existing_id_with_a_note(
    tmp_path: Path, ticking_clock, bad: str,
) -> None:
    """SELECT-first precedes every payload REFUSAL: a malformed or absent
    evidence file on an already-applied trade is parsed (never consulted) and
    the existing id returns, with the note naming the read-time surface.  The
    CLI leg of A2-70 landed with the CLI option (Task 8):
    ``tests/cli/test_correct_cohort_provenance_command.py::
    test_an_already_applied_replay_with_a_bad_evidence_file_exits_zero``."""
    repo, evidence = _evidence(tmp_path)
    conn, cfg = _t25(tmp_path)
    try:
        first = _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        if bad == "malformed":
            bad_path = tmp_path / "malformed.json"
            bad_path.write_bytes(b"{not json")
        else:
            bad_path = tmp_path / "does-not-exist.json"
            assert not bad_path.exists()
        again = _apply(conn, cfg, frozen_value_evidence=bad_path, evidence_repo=repo)
        assert again.already_applied is True
        assert again.correction_id == first.correction_id
        assert again.tier2_note == TIER2_NOTE
        pre = _preview(conn, cfg, frozen_value_evidence=bad_path, evidence_repo=repo)
        assert pre.already_applied_correction_id == first.correction_id
        assert pre.tier2_note == TIER2_NOTE
        # The counterfactual: no evidence supplied -> no note.
        plain = _apply(conn, cfg)
        assert plain.already_applied is True and plain.tier2_note is None
        assert _preview(conn, cfg).tier2_note is None
        assert _count(conn) == 1
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-71

@pytest.mark.parametrize("entry", ["apply", "preview"])
def test_a2_71_evidence_on_a_last_word_trade_refuses(
    tmp_path: Path, ticking_clock, entry: str,
) -> None:
    """PRE: the evidence is silently ignored and a ``last_word`` row is
    written.  POST: refused, naming why; nothing written."""
    repo, evidence = _evidence(tmp_path)
    conn = build_last_word_world(tmp_path)
    try:
        call = _apply if entry == "apply" else _preview
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            call(conn, None, frozen_value_evidence=evidence, evidence_repo=repo)
        assert NO_LATCH in str(exc.value)
        assert _count(conn) == 0
        # The counterfactual: the same world WITHOUT evidence corrects last_word.
        out = call(conn, None)
        assert out.admission_tier == PROVENANCE_ADMISSION_TIER_LAST_WORD
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-72

def test_a2_72_a_ladder_refusal_with_evidence_says_it_was_not_consulted(
    tmp_path: Path, ticking_clock,
) -> None:
    """A LINKED fill with no config is RECOGNISED and refused (``no_config``)
    before rung 9 -- the evidence was never reached, and the message says so."""
    repo, evidence = _evidence(tmp_path)
    conn, _cfg = _t25(tmp_path)
    try:
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            _apply(conn, None, frozen_value_evidence=evidence, evidence_repo=repo)
        message = str(exc.value)
        assert "no_config" in message
        assert f"({NOT_CONSULTED}: no_config)" in message
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as plain:
            _apply(conn, None)
        assert "no_config" in str(plain.value)
        assert NOT_CONSULTED not in str(plain.value)
        assert _count(conn) == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-73

def test_a2_73_evidence_failing_criterion_3_refuses_naming_the_field(
    tmp_path: Path, ticking_clock,
) -> None:
    repo, evidence = _evidence(tmp_path, line57=_pivot_absent_line())
    conn, cfg = _t25(tmp_path)
    try:
        before = _trade_keys(conn)
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        message = str(exc.value)
        assert "tier2_evidence_refused" in message
        assert "criterion 3: pivot" in message
        assert NOT_CONSULTED not in message
        assert _count(conn) == 0
        assert _trade_keys(conn) == before
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-74

def _dump(conn) -> list[str]:
    return list(conn.iterdump())


def test_a2_74_dry_run_authorizes_as_apply_and_leaves_the_db_identical(
    tmp_path: Path, ticking_clock,
) -> None:
    repo, evidence = _evidence(tmp_path)
    repo_bad, evidence_bad = _evidence(tmp_path, line57=_pivot_absent_line(), name="bad")
    conn, cfg = _t25(tmp_path)
    try:
        # The refusal is the same refusal.
        before = _dump(conn)
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as dry_refusal:
            _preview(conn, cfg, frozen_value_evidence=evidence_bad, evidence_repo=repo_bad)
        assert _dump(conn) == before
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as apply_refusal:
            _apply(conn, cfg, frozen_value_evidence=evidence_bad, evidence_repo=repo_bad)
        assert str(dry_refusal.value) == str(apply_refusal.value)

        # The admission is the same admission.
        before = _dump(conn)
        preview = _preview(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert _dump(conn) == before
        assert preview.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        result = _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert result.admission_tier == preview.admission_tier
        assert result.tier2_clauses == preview.tier2_clauses
        assert result.tier2_interval_prose == preview.tier2_interval_prose
        for field in ("cited_latch_link_id", "cited_latch_validity_intent_id",
                      "cited_latch_place_intent_id", "cited_latch_broker_order_id",
                      "cited_latch_admission_basis"):
            assert getattr(result, field) == getattr(preview, field), field
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-75

# The ONE caller walk (CHARC R4.2 ruling 2, gotcha #31): every Name/Attribute
# REFERENCE to a guarded entry point anywhere under ``swing/``, keyed by its
# enclosing function.  Task 9 added ``replay_verdict`` (the read-time verdict,
# one function for every consumer) and ``tier2_cohort_exclusions``, whose
# callers are EXACTLY the four P35 cohort readers (CHARC G-T9 item 1 +
# G-T10-1 (1), Task 10): the breakdown threads its ONE read into every
# per-hypothesis ``compute_tripwire_status``, which calls only when handed
# none -- so no fifth caller exists, and a CLI command or web route that
# shows a cohort N reaches the verdict THROUGH one of the four.
_EXPECTED_CALLERS: dict[str, set[str]] = {
    "run_preflight": {
        "swing.trades.cohort_provenance_correction:correct_cohort_provenance",
        "swing.trades.cohort_provenance_correction:preview_cohort_provenance_correction",
    },
    "evaluate_conjunction": {
        "swing.trades.latched_origin:_rung9_tier2_escape",
        "swing.trades.frozen_value_evidence:replay_verdict",
    },
    "replay_verdict": {
        "swing.trades.frozen_value_evidence:tier2_cohort_exclusions",
        "swing.trades.cohort_provenance_correction:read_provenance_corrections",
    },
    "tier2_cohort_exclusions": {
        "swing.recommendations.hypothesis:compute_tripwire_status",
        "swing.journal.stats:compute_hypothesis_progress_breakdown",
        "swing.metrics.tier:compute_tier_comparison",
        "swing.web.view_models.metrics.hypothesis_progress_card:"
        "build_hypothesis_progress_card_vm",
    },
}


def _references(names: set[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {n: set() for n in names}
    for path in sorted(SWING_ROOT.rglob("*.py")):
        module = ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)
        tree = ast.parse(path.read_bytes().decode("utf-8"))

        def _walk(node: ast.AST, scope: list[str], _module: str = module) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    _walk(child, [*scope, child.name])
                    continue
                ref = (child.id if isinstance(child, ast.Name)
                       else child.attr if isinstance(child, ast.Attribute) else None)
                if ref in found:
                    found[ref].add(f"{_module}:{'.'.join(scope) or '<module>'}")
                _walk(child, scope)

        _walk(tree, [])
    return found


def test_a2_75_guarded_entry_points_have_exactly_their_named_callers() -> None:
    found = _references(set(_EXPECTED_CALLERS))
    for name, expected in _EXPECTED_CALLERS.items():
        assert found[name] == expected, (name, sorted(found[name] ^ expected))


# --------------------------------------------------------------------------- A2-76

def test_a2_76_the_envelope_reading_is_written_by_apply_and_unwound_by_dry_run(
    tmp_path: Path, ticking_clock,
) -> None:
    repo, evidence = _evidence(tmp_path)
    conn, cfg = _t25(tmp_path, with_envelope_reading=False)

    def readings() -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM fill_envelope_identity WHERE fill_id = ?",
            (T25_FILL_ID,)).fetchone()[0]

    try:
        assert readings() == 0
        preview = _preview(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert preview.admission_tier == PROVENANCE_ADMISSION_TIER_LATCH_TIER2
        assert readings() == 0
        _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert readings() == 1
    finally:
        conn.close()
