"""CLI: `swing journal correct-cohort-provenance` + `provenance-corrections`.

Pins the things a service-level test structurally CANNOT see:

  - the commands are REGISTERED on the flat `journal` group;
  - FREE-TYPING A COHORT KEY IS UNREPRESENTABLE -- the click parameter
    manifest is READ and asserted to be exactly six entries, which a grep for
    `"--label"` could never establish (a grep bounds the family from below and
    would miss `--hypothesis-label` or any other spelling);
  - `--reason` is NOT `required=True` at the parser. Click rejects a missing
    required option during PARSING, before the command body runs, so a
    `required=True` declaration would make the already-applied replay promise
    true for direct service calls and FALSE for the operator-facing surface.
    A service-level test passes under EITHER declaration.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config
from tests.trades._cohort_provenance_fixtures import (
    CADL_LABEL,
    build_cadl_case,
)

REASON = "the framework's own contemporaneous record"


def _setup(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir(parents=True)
    cfg = _minimal_config(project, home)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return runner, cfg, home / "swing-data" / "swing.db"


def _seed(db_path: Path, **kwargs) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        ids = build_cadl_case(conn, **kwargs)
        conn.commit()
    finally:
        conn.close()
    return ids


def _cmd(cfg, ids, *extra):
    return [
        "--config", str(cfg), "journal", "correct-cohort-provenance",
        str(ids["trade_id"]),
        "--cited-candidate", str(ids["candidate_id"]),
        "--cited-recommendation", str(ids["daily_recommendation_id"]),
        *extra,
    ]


# ------------------------------------------- free-typing is UNREPRESENTABLE


def test_a2_77_the_click_parameter_manifest_is_exactly_six_entries() -> None:
    """A manifest READ, not a name grep. `help` is deliberately NOT a member:
    verified on the installed click, the auto help option is appended by
    `get_params(ctx)` at parse time and never lives in `.params`.

    22-A2 (Task 8) added the SIXTH, `frozen_value_evidence`, declared LAST.
    It is a SELECTION -- a path to a file naming where the record is -- and
    carries no cohort value (F9). PRE: five entries -> the equality fails."""
    cmd = main.commands["journal"].commands["correct-cohort-provenance"]
    assert [p.name for p in cmd.params] == [
        "trade_id", "cited_candidate_id", "cited_recommendation_id",
        "reason", "dry_run", "frozen_value_evidence",
    ]
    assert "help" not in {p.name for p in cmd.params}
    for param in cmd.params:
        for opt in getattr(param, "opts", []):
            assert "label" not in opt
            assert "origin" not in opt
            assert "hypothesis" not in opt


def test_help_is_still_available_even_though_it_is_not_in_params(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, _ = _setup(tmp_path, monkeypatch)
    r = runner.invoke(
        main, ["--config", str(cfg), "journal",
               "correct-cohort-provenance", "--help"])
    assert r.exit_code == 0
    assert "--cited-candidate" in r.output


def test_the_service_signature_accepts_no_cohort_VALUE() -> None:
    """EIGHT parameters, and not one of them can carry a cohort key.

    `cfg` joined the manifest with 22-A (task 11): it is the CONFIG HANDLE the
    latch ladder needs to run its derivation at all, and it carries no value
    this surface writes -- without it the resolver returns `no_config` and
    every correction reports the `last_word` tier, which would be a true
    statement about a probe that never happened.

    `frozen_value_evidence` and `evidence_repo` joined with 22-A2 (Task 7):
    the tier-2 evidence is a SELECTION -- where the record is, never what it
    says (F9) -- and the repo that selection names. Neither carries a value
    this surface writes; the tier they can open is DETECTED from the ladder.

    The manifest is asserted as an EQUALITY rather than a set of absences on
    purpose: a value parameter added under any spelling fails here, which a
    grep for `--label` could never establish.
    """
    import inspect

    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )
    names = set(inspect.signature(correct_cohort_provenance).parameters)
    assert names == {
        "conn", "trade_id", "cited_candidate_id", "cited_recommendation_id",
        "reason", "cfg", "frozen_value_evidence", "evidence_repo",
    }
    # `applied_at` is DELIBERATELY absent: an audit time a caller can supply
    # is an audit time a caller can falsify, and this table exists to hold
    # claims that are true.
    assert "applied_at" not in names


def test_the_value_comes_from_the_RECORD_not_from_the_cohort(
    tmp_path: Path, monkeypatch,
) -> None:
    """A positive control: sibling cohort rows carry a DIFFERENT label, and
    the written label is still the one derived from the CITED record."""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    conn = sqlite3.connect(db)
    try:
        sibling = build_cadl_case(conn, ticker="VSTS", non_pass={})
        conn.execute(
            "UPDATE trades SET hypothesis_label = 'A+ baseline (aplus)', "
            "trade_origin = 'pipeline_aplus', candidate_id = ? WHERE id = ?",
            (sibling["candidate_id"], sibling["trade_id"]))
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON))
    assert r.exit_code == 0, r.output
    conn = sqlite3.connect(db)
    try:
        label = conn.execute(
            "SELECT hypothesis_label FROM trades WHERE id = ?",
            (ids["trade_id"],)).fetchone()[0]
    finally:
        conn.close()
    assert label == CADL_LABEL != "A+ baseline (aplus)"


# ---------------------------------------------------------- --reason parsing


def test_an_already_applied_replay_with_NO_reason_exits_zero(
    tmp_path: Path, monkeypatch,
) -> None:
    """The whole reason `--reason` is not `required=True`. A `required=True`
    declaration makes click print "Missing option '--reason'" and exit 2
    BEFORE the command body runs, so the operator replaying a correction never
    reaches the idempotent return."""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    first = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON))
    assert first.exit_code == 0, first.output
    replay = runner.invoke(main, _cmd(cfg, ids))
    assert replay.exit_code == 0, replay.output
    assert "ALREADY APPLIED" in replay.output
    assert "Missing option" not in replay.output


def test_a_FRESH_request_with_no_reason_is_a_clean_refusal(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _cmd(cfg, ids))
    assert r.exit_code != 0
    assert "--reason must be a non-empty string" in r.output
    assert "Traceback" not in r.output
    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0
    finally:
        conn.close()


# ------------------------------------------------------------ apply + dry-run


def test_dry_run_writes_nothing_and_prints_the_exact_label(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON, "--dry-run"))
    assert r.exit_code == 0, r.output
    assert "DRY RUN -- nothing written" in r.output
    assert CADL_LABEL in r.output
    assert "session F = 2026-08-12" in r.output
    assert "2026-08-11T03:30:26" in r.output  # normalized UTC bound
    assert "TT8_rs_rank" in r.output          # the `na` suffix note
    assert "records provenance ONCE" in r.output
    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0
        assert conn.execute(
            "SELECT hypothesis_label FROM trades WHERE id = ?",
            (ids["trade_id"],)).fetchone()[0] is None
    finally:
        conn.close()


def test_apply_writes_and_prints_the_follow_up_reader(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON))
    assert r.exit_code == 0, r.output
    assert "provenance correction 1 applied" in r.output
    assert CADL_LABEL in r.output
    assert (f"swing journal provenance-corrections {ids['trade_id']}"
            in r.output)
    assert "<" not in r.output.split("Read it back with:")[1]


def test_a_service_refusal_is_a_clean_ClickException(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db, bucket="watch")
    r = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON))
    assert r.exit_code != 0
    assert "Traceback" not in r.output
    assert "Nothing was written." in r.output


# ---------------------------------------------------------------- the reader


def test_the_reader_reports_the_citation_and_no_drift(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    assert runner.invoke(
        main, _cmd(cfg, ids, "--reason", REASON)).exit_code == 0
    r = runner.invoke(
        main, ["--config", str(cfg), "journal", "provenance-corrections",
               str(ids["trade_id"])])
    assert r.exit_code == 0, r.output
    assert f"cites candidates {ids['candidate_id']}" in r.output
    assert f"daily_recommendations {ids['daily_recommendation_id']}" in r.output
    assert "hypothesis 1 (A+ baseline)" in r.output
    assert "no citation drift." in r.output


def test_the_reader_prints_drift_when_the_cited_row_moves(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    assert runner.invoke(
        main, _cmd(cfg, ids, "--reason", REASON)).exit_code == 0
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE daily_recommendations SET action_text = 'rewritten' "
            "WHERE id = ?", (ids["daily_recommendation_id"],))
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(
        main, ["--config", str(cfg), "journal", "provenance-corrections"])
    assert r.exit_code == 0, r.output
    assert "CITATION DRIFT: daily_recommendations.action_text" in r.output


def test_the_reader_on_an_empty_table_says_so(
    tmp_path: Path, monkeypatch,
) -> None:
    runner, cfg, _ = _setup(tmp_path, monkeypatch)
    r = runner.invoke(
        main, ["--config", str(cfg), "journal", "provenance-corrections"])
    assert r.exit_code == 0, r.output
    assert "No provenance corrections recorded." in r.output


@pytest.mark.parametrize("argv_tail", [
    ["--reason", REASON, "--dry-run"],
    ["--reason", REASON],
])
def test_all_command_output_is_ascii(
    tmp_path: Path, monkeypatch, argv_tail,
) -> None:
    """Windows cp1252 crashes on a non-ASCII glyph in any click.echo path, and
    capsys/CliRunner bypass the OS encoder so they hide it."""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _cmd(cfg, ids, *argv_tail))
    assert r.exit_code == 0, r.output
    r.output.encode("ascii")
    reader = runner.invoke(
        main, ["--config", str(cfg), "journal", "provenance-corrections"])
    reader.output.encode("ascii")


# ------------------------------------------------- 22-A: the ADMISSION TIER


def test_both_surfaces_print_the_admission_tier(
    tmp_path: Path, monkeypatch,
) -> None:
    """The operator sees WHICH AUTHORITY admitted the correction.

    On a trade with no accepted latch order the tier is `last_word` and the
    line says what that means, so an operator reading the output never has to
    infer the authority from the absence of a citation.  Both surfaces print
    it from ONE helper, which is why the dry run and the apply cannot drift.
    """
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    dry = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON, "--dry-run"))
    assert dry.exit_code == 0, dry.output
    assert "admission tier                last_word" in dry.output
    assert "no accepted latch order" in dry.output
    # 22-A2: no tier-2 evidence surface on a tier that carries none.
    assert "criterion 1" not in dry.output
    assert "uncovered window" not in dry.output

    applied = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON))
    assert applied.exit_code == 0, applied.output
    assert "admission tier                last_word" in applied.output


def test_the_latch_tier_prints_its_full_citation() -> None:
    """The `latch_ladder` branch, over the PRODUCTION result dataclass.

    Building the whole probe world through the CLI would test the fixture; what
    this pins is that the printer emits the four ids and the probe's admission
    basis for a real `CohortProvenanceCorrectionResult` carrying them -- and
    that the output is ASCII, which is the failure `CliRunner` hides.
    """
    from swing.cli import _echo_admission_tier
    from swing.trades.cohort_provenance_correction import (
        CohortProvenanceCorrectionResult,
    )

    result = CohortProvenanceCorrectionResult(
        correction_id=1, trade_id=25, already_applied=False,
        cited_candidate_id=12284, cited_daily_recommendation_id=7,
        pre_values={}, applied_values={}, correction_reason="r",
        follow_up_command="swing journal provenance-corrections 25",
        admission_tier="latch_ladder",
        cited_latch_link_id=3,
        cited_latch_validity_intent_id=2,
        cited_latch_place_intent_id=1,
        cited_latch_broker_order_id="1007523377009",
        cited_latch_admission_basis="armed",
    )
    runner = CliRunner()
    with runner.isolation() as (out, _err, _):
        _echo_admission_tier(result)
        text = out.getvalue().decode("utf-8")
    text.encode("ascii")
    assert "admission tier                latch_ladder" in text
    assert "cited latch link              3 (broker order 1007523377009)" in text
    assert "cited latch intents           place 1, validity 2" in text
    assert "probe admission basis         armed" in text
    assert "no accepted latch order" not in text


# ===========================================================================
# 22A-R11-04 -- A DRIFT DETECTION IS A LEGIBLE REFUSAL, NOT A TRACEBACK
#
# The subject canonicalisation in `_resolve_latch_citation` sat OUTSIDE any
# conversion to `CohortProvenanceCorrectionError`, and the CLI maps only that
# exception -- so `EnvelopeIdentityDriftError`, the exact state the new
# repository exists to DETECT, reached the operator as an unhandled traceback.
# A broken refusal on the one condition the instrument was built for.
# ===========================================================================
_FORGED_DOC = '{"schwab_order_id": "1002937461"}'


def _plant_a_forged_reading(db_path: Path, fill_id: int) -> None:
    """The document with a reading that DISAGREES with today's authority.

    Written raw on purpose: the append-only barriers make this state
    unreachable through the writer, which is precisely why the repository
    treats it as a forgery rather than re-deriving it.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
            (_FORGED_DOC, fill_id))
        conn.execute(
            "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
            " envelope_state, broker_order_id, canonicalizer_version, "
            " recorded_ts) VALUES (?, ?, 'canonical', 'A DIFFERENT ORDER', "
            " 'v0', '2026-08-01T00:00:00Z')", (fill_id, _FORGED_DOC))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("extra", [("--dry-run",), ()])
def test_a_drifted_subject_reading_refuses_legibly(
        tmp_path, monkeypatch, extra) -> None:
    """PRE-FIX both arms raised `EnvelopeIdentityDriftError` out of the command.

    BOTH arms are run because the dry-run and the apply reach the subject
    canonicalisation through the SAME `_authorize`, and a fix applied at one
    entry point would leave the other exactly as it was.
    """
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    _plant_a_forged_reading(db, ids["fill_id"])

    r = runner.invoke(main, _cmd(cfg, ids, "--reason", REASON, *extra))
    assert r.exit_code != 0
    assert r.exception is None or isinstance(r.exception, SystemExit), (
        f"an unhandled {type(r.exception).__name__} reached the operator")
    assert "disagrees with what the canonicaliser" in r.output, r.output
    assert "Nothing was written." in r.output, r.output

    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0
    finally:
        conn.close()


# ===========================================================================
# 22-A2 (Task 8) -- `--frozen-value-evidence`: the tier-2 SELECTION at the CLI
#
# Trade 25's REAL row shape (`tests/_tier2_world_22a2.py`) with a
# `pre_barrier_reconstructed` link, and the evidence a selection into a
# throwaway git world whose `docs/rd-state.md` line 57 is the pinned
# acceptance record. The CLI has no repo option: with none, the service reads
# `frozen_value_evidence.EVIDENCE_REPO_DIR` at call time, so the world is
# installed there. The config the command resolves is the world's own (its
# price archive + trend template); the `--config` file only lets the group load.
# ===========================================================================
_T25_REASON = "22-A2 Task 8: trade 25's tier-2 correction"
_TIER2_NOTE = ("already applied; evidence not re-evaluated here -- the read-time "
               "verdict is on journal provenance-corrections")
_CLAUSE_LINE = r"^  criterion (\d) .+: PASS$"


def _t25_world(tmp_path: Path, monkeypatch, *, line57: bytes | None = None):
    """``(runner, argv_head, db_path, evidence_file)`` over trade 25's world."""
    import json

    from swing.trades import frozen_value_evidence as fve
    from tests._tier2_world_22a2 import (
        LINE57_FIXTURE,
        T25_AUTHOR_INSTANT,
        T25_CANDIDATE_ID,
        T25_REC_ID,
        T25_TRADE_ID,
        build_pre_barrier_world,
        t25_cfg,
    )
    from tests.trades._git_world import GitWorld

    line = LINE57_FIXTURE.read_bytes() if line57 is None else line57
    world = GitWorld(tmp_path / "evidence-git")
    world.commit("README.md", b"base\n")
    body = b"\n".join([*(f"line {i}".encode("ascii") for i in range(1, 57)),
                       line, b"line 58", b""])
    sha = world.commit("docs/rd-state.md", body, author_date=T25_AUTHOR_INSTANT)
    world.push()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "artifact_path": "docs/rd-state.md", "artifact_commit_sha": sha,
        "quoted_text": line.decode("utf-8")}), encoding="utf-8")
    monkeypatch.setattr(fve, "EVIDENCE_REPO_DIR", world.work)

    conn, _ids = build_pre_barrier_world(tmp_path, "t25")
    conn.close()
    cfg = t25_cfg(tmp_path / "t25")
    monkeypatch.setattr("swing.config_overrides.apply_overrides", lambda _c: cfg)

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_file = _minimal_config(project, home)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    argv = ["--config", str(cfg_file), "journal", "correct-cohort-provenance",
            str(T25_TRADE_ID), "--cited-candidate", str(T25_CANDIDATE_ID),
            "--cited-recommendation", str(T25_REC_ID)]
    return CliRunner(), argv, cfg.paths.db_path, evidence


def _corrections(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT provenance_correction_id, admission_tier, "
            "cited_frozen_value_evidence_json FROM provenance_corrections"
        ).fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize("extra", [("--dry-run",), ()])
def test_a2_78_both_surfaces_print_the_four_clauses_and_the_prose(
    tmp_path: Path, monkeypatch, extra,
) -> None:
    """The tier, the four clauses ONE PER LINE in criterion order, and the
    interval prose -- ASCII, so the cp1252 encode that `CliRunner` hides
    succeeds. PRE: `--frozen-value-evidence` does not exist -> exit 2."""
    import json
    import re

    runner, argv, db, evidence = _t25_world(tmp_path, monkeypatch)
    r = runner.invoke(main, [*argv, "--reason", _T25_REASON,
                             "--frozen-value-evidence", str(evidence), *extra])
    assert r.exit_code == 0, r.output
    r.output.encode("cp1252")
    r.output.encode("ascii")
    assert "admission tier                latch_ladder_tier2" in r.output
    lines = r.output.splitlines()
    clauses = [ln for ln in lines if re.match(_CLAUSE_LINE, ln)]
    assert [re.match(_CLAUSE_LINE, ln).group(1) for ln in clauses] == [
        "1", "2", "3", "4"]
    assert "refs/remotes/origin/main" in clauses[0]
    assert "pivot 53.98, invalidation 41.42" in clauses[2]
    prose_lines = [ln for ln in lines if ln.startswith("  uncovered window")]
    assert len(prose_lines) == 1
    assert "writer_absence_only 2.38 days" in prose_lines[0]
    rows = _corrections(db)
    if extra:
        assert rows == []
    else:
        assert len(rows) == 1 and rows[0][1] == "latch_ladder_tier2"
        blob = json.loads(rows[0][2])
        assert prose_lines[0].endswith(blob["uncovered_window_prose"])
        assert blob["artifact_commit_sha"] in clauses[0]


def test_a2_79_a_tier2_refusal_names_the_reason_and_the_field(
    tmp_path: Path, monkeypatch,
) -> None:
    """The pivot numeral is absent from the quoted line, so criterion 3 names
    `pivot`. Exit 1 (a clean ClickException), no traceback, nothing written.
    PRE: the option does not exist -> exit 2 `No such option`."""
    from tests._tier2_world_22a2 import LINE57_FIXTURE

    line = LINE57_FIXTURE.read_bytes().replace(b"53.98", b"53.93")
    runner, argv, db, evidence = _t25_world(tmp_path, monkeypatch, line57=line)
    for extra in (("--dry-run",), ()):
        r = runner.invoke(main, [*argv, "--reason", _T25_REASON,
                                 "--frozen-value-evidence", str(evidence), *extra])
        assert r.exit_code == 1, r.output
        assert "tier2_evidence_refused" in r.output
        assert "criterion 3: pivot" in r.output
        assert "Traceback" not in r.output
        r.output.encode("ascii")
    assert _corrections(db) == []


def test_a2_80_help_documents_the_three_key_file_and_no_typed_values(
    tmp_path: Path, monkeypatch,
) -> None:
    """The option's help names each key of the selection file -- read off the
    service's own constant, so a key added there fails here -- and says the
    values are never typed. PRE: no such option in the help."""
    from swing.trades.frozen_value_evidence import EVIDENCE_FILE_KEYS

    runner, cfg, _ = _setup(tmp_path, monkeypatch)
    r = runner.invoke(
        main, ["--config", str(cfg), "journal",
               "correct-cohort-provenance", "--help"])
    assert r.exit_code == 0, r.output
    text = " ".join(r.output.split())
    assert "--frozen-value-evidence" in text
    for key in EVIDENCE_FILE_KEYS:
        assert key in text, key
    assert "never typed" in text
    r.output.encode("ascii")


@pytest.mark.parametrize("bad", ["malformed", "missing"])
def test_an_already_applied_replay_with_a_bad_evidence_file_exits_zero(
    tmp_path: Path, monkeypatch, bad: str,
) -> None:
    """The CLI leg of roster case 70 (its service legs live in
    `tests/trades/test_22a2_correction_service.py`): SELECT-first precedes every
    payload REFUSAL, and the caller-side obligation (#31) is that CLICK never
    parses or existence-checks the file. PRE (`click.Path(exists=True)`): the
    missing path exits 2 before the command body runs."""
    runner, argv, db, evidence = _t25_world(tmp_path, monkeypatch)
    first = runner.invoke(main, [*argv, "--reason", _T25_REASON,
                                 "--frozen-value-evidence", str(evidence)])
    assert first.exit_code == 0, first.output
    if bad == "malformed":
        bad_path = tmp_path / "malformed.json"
        bad_path.write_bytes(b"{not json")
    else:
        bad_path = tmp_path / "does-not-exist.json"
        assert not bad_path.exists()
    for extra in ((), ("--dry-run",)):
        r = runner.invoke(main, [*argv, "--frozen-value-evidence", str(bad_path),
                                 *extra])
        assert r.exit_code == 0, r.output
        assert _TIER2_NOTE in " ".join(r.output.split())
        r.output.encode("ascii")
    assert "ALREADY APPLIED" in runner.invoke(
        main, [*argv, "--frozen-value-evidence", str(bad_path)]).output
    # The counterfactual: no evidence supplied -> no note.
    plain = runner.invoke(main, argv)
    assert plain.exit_code == 0, plain.output
    assert "evidence not re-evaluated" not in plain.output
    assert len(_corrections(db)) == 1
