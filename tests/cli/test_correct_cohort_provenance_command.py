"""CLI: `swing journal correct-cohort-provenance` + `provenance-corrections`.

Pins the things a service-level test structurally CANNOT see:

  - the commands are REGISTERED on the flat `journal` group;
  - FREE-TYPING A COHORT KEY IS UNREPRESENTABLE -- the click parameter
    manifest is READ and asserted to be exactly five entries, which a grep for
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


def test_the_click_parameter_manifest_is_exactly_five_entries() -> None:
    """A manifest READ, not a name grep. `help` is deliberately NOT a member:
    verified on the installed click, the auto help option is appended by
    `get_params(ctx)` at parse time and never lives in `.params`."""
    cmd = main.commands["journal"].commands["correct-cohort-provenance"]
    assert [p.name for p in cmd.params] == [
        "trade_id", "cited_candidate_id", "cited_recommendation_id",
        "reason", "dry_run",
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
    import inspect

    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )
    names = set(inspect.signature(correct_cohort_provenance).parameters)
    assert names == {
        "conn", "trade_id", "cited_candidate_id", "cited_recommendation_id",
        "reason", "applied_at",
    }


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
