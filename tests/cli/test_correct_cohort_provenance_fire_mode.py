"""D104 test 1q -- `swing journal correct-cohort-provenance --cite-fire-candidate`.

The CLI half of the watch-fire relabel (plan T1.7): exactly one mode per
call, the fire mode reaching `preview_watch_fire_label` /
`correct_watch_fire_label`, a service refusal surfacing as a
`ClickException` (exit 1, no traceback), the kind-2 row rendered with
`(none: watch-fire relabel)` where a recommendation would be, and every
line ASCII (cp1252 crashes on anything else; `CliRunner` would not show it).

Seeded from trade 29's LIVE shape (`build_sg_case`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.cli import main
from tests.cli.test_correct_cohort_provenance_command import _setup
from tests.trades._cohort_provenance_fixtures import (
    SG_BASELINE_LABEL,
    SG_FIRE_CANDIDATE_ID,
    SG_FIRE_LABEL,
    SG_OLDER_CANDIDATE_ID,
    SG_TRADE_ID,
    build_cadl_case,
    build_sg_case,
)

REASON = "D104: the SG fire was eval 193"
NONE_REC = "(none: watch-fire relabel)"


def _seed_sg(db_path: Path, **case) -> None:
    conn = sqlite3.connect(db_path)
    try:
        build_sg_case(conn, **case)
        conn.commit()
    finally:
        conn.close()


def _keys(db_path: Path) -> tuple:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT hypothesis_label, candidate_id FROM trades WHERE id = ?",
            (SG_TRADE_ID,)).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path) -> list:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT correction_kind, admission_tier, cited_candidate_id "
            "FROM provenance_corrections").fetchall()
    finally:
        conn.close()


def _fire(cfg, *extra, candidate=SG_FIRE_CANDIDATE_ID):
    return ["--config", str(cfg), "journal", "correct-cohort-provenance",
            str(SG_TRADE_ID), "--cite-fire-candidate", str(candidate), *extra]


def _assert_ascii(text: str) -> None:
    text.encode("ascii")
    text.encode("cp1252")


def test_1q_dry_run_prints_the_exact_label_and_writes_nothing(
        tmp_path, monkeypatch) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(cfg, "--reason", REASON, "--dry-run"))
    assert r.exit_code == 0, r.output
    assert "DRY RUN -- nothing written" in r.output
    assert repr(SG_FIRE_LABEL) in r.output
    assert repr(SG_BASELINE_LABEL) in r.output
    assert NONE_REC in r.output
    assert "watch_fire_relabel" in r.output
    assert "last_fire" in r.output
    # The kind-2 tier is NOT printed as a latch row (cli.py's tier branch).
    assert "cited latch link" not in r.output
    _assert_ascii(r.output)
    assert _rows(db) == []
    assert _keys(db) == (SG_BASELINE_LABEL, 15980)


def test_1q_apply_writes_and_the_reader_renders_kind2(
        tmp_path, monkeypatch) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(cfg, "--reason", REASON))
    assert r.exit_code == 0, r.output
    assert "applied to trade 29" in r.output
    assert NONE_REC in r.output
    assert "cited latch link" not in r.output
    _assert_ascii(r.output)
    assert _rows(db) == [("watch_fire_relabel", "last_fire", 15901)]
    assert _keys(db) == (SG_FIRE_LABEL, 15901)

    again = runner.invoke(main, _fire(cfg))
    assert again.exit_code == 0, again.output
    assert "ALREADY APPLIED" in again.output
    assert NONE_REC in again.output
    _assert_ascii(again.output)

    read = runner.invoke(main, ["--config", str(cfg), "journal",
                                "provenance-corrections", str(SG_TRADE_ID)])
    assert read.exit_code == 0, read.output
    assert "correction_kind watch_fire_relabel" in read.output
    assert NONE_REC in read.output
    assert "daily_recommendations None" not in read.output
    assert "CITATION" not in read.output
    _assert_ascii(read.output)


@pytest.mark.parametrize("extra", [
    (),                                             # no mode at all
    ("--cited-candidate", "1"),                     # half of kind 1
    ("--cited-recommendation", "1"),                # the other half
])
def test_1q_no_complete_mode_is_a_usage_error(
        tmp_path, monkeypatch, extra) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, ["--config", str(cfg), "journal",
                             "correct-cohort-provenance", str(SG_TRADE_ID),
                             "--reason", REASON, *extra])
    assert r.exit_code == 2, r.output
    assert "--cite-fire-candidate" in r.output
    assert _rows(db) == []


@pytest.mark.parametrize("extra", [
    ("--cited-candidate", "15901"),
    ("--cited-recommendation", "1"),
    ("--cited-candidate", "15901", "--cited-recommendation", "1"),
])
def test_1q_both_modes_is_a_usage_error(tmp_path, monkeypatch, extra) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(cfg, "--reason", REASON, *extra))
    assert r.exit_code == 2, r.output
    assert _rows(db) == []
    assert _keys(db) == (SG_BASELINE_LABEL, 15980)


def test_1q_frozen_value_evidence_with_the_fire_mode_is_a_usage_error(
        tmp_path, monkeypatch) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(
        cfg, "--reason", REASON, "--frozen-value-evidence",
        str(tmp_path / "evidence.json")))
    assert r.exit_code == 2, r.output
    assert "--frozen-value-evidence" in r.output
    assert _rows(db) == []


@pytest.mark.parametrize("extra", [("--dry-run",), ()])
def test_1q_a_service_refusal_is_a_click_exception(
        tmp_path, monkeypatch, extra) -> None:
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(cfg, "--reason", REASON, *extra,
                                  candidate=SG_OLDER_CANDIDATE_ID))
    assert r.exit_code == 1, r.output
    assert "Error:" in r.output
    assert "Traceback" not in r.output
    assert "the derived last fire is 15901" in r.output
    assert r.exception is None or isinstance(r.exception, SystemExit)
    _assert_ascii(r.output)
    assert _rows(db) == []
    assert _keys(db) == (SG_BASELINE_LABEL, 15980)


def test_1q_the_kind1_mode_is_unchanged(tmp_path, monkeypatch) -> None:
    """The existing two-id mode still runs and still prints its
    recommendation citation (keeper)."""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    conn = sqlite3.connect(db)
    ids = build_cadl_case(conn)
    conn.commit()
    conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "correct-cohort-provenance",
        str(ids["trade_id"]), "--cited-candidate", str(ids["candidate_id"]),
        "--cited-recommendation", str(ids["daily_recommendation_id"]),
        "--reason", REASON])
    assert r.exit_code == 0, r.output
    assert f"daily_recommendations {ids['daily_recommendation_id']}" in (
        r.output)
    assert NONE_REC not in r.output


def test_1q_the_watch_fire_service_accepts_no_cohort_value() -> None:
    """The kind-2 service signature, asserted as an EQUALITY (the kind-1
    test's own form): one cited id, a reason and the config handle -- no
    parameter can carry a label, an origin or an anchor value."""
    import inspect

    from swing.trades.cohort_provenance_correction import (
        correct_watch_fire_label,
        preview_watch_fire_label,
    )
    expected = {"conn", "trade_id", "fire_candidate_id", "reason", "cfg"}
    assert set(inspect.signature(correct_watch_fire_label).parameters) == (
        expected)
    assert set(inspect.signature(preview_watch_fire_label).parameters) == (
        expected)


@pytest.mark.parametrize("extra", [("--dry-run",), ()])
@pytest.mark.parametrize("candidate", [2 ** 63, -(2 ** 63) - 1])
def test_r1_4_an_out_of_range_fire_id_is_a_typed_refusal(
        tmp_path, monkeypatch, extra, candidate) -> None:
    """Codex R1-4 (sg-label exec round 1): an id outside SQLite's signed
    64-bit INTEGER range is refused BEFORE it is bound (an unbound
    OverflowError would escape as a traceback)."""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, _fire(cfg, "--reason", REASON, *extra,
                                  candidate=candidate))
    assert r.exit_code == 1, r.output
    assert "Error:" in r.output
    assert "Traceback" not in r.output
    assert "64-bit" in r.output
    assert r.exception is None or isinstance(r.exception, SystemExit)
    _assert_ascii(r.output)
    assert _rows(db) == []
    assert _keys(db) == (SG_BASELINE_LABEL, 15980)


@pytest.mark.parametrize("trade_id", [2 ** 63, 2 ** 64])
def test_r2_3_an_out_of_range_trade_id_is_a_typed_refusal(
        tmp_path, monkeypatch, trade_id) -> None:
    """Codex exec R2-3: the positional trade id is bound before any range
    check, so an id outside SQLite's signed 64-bit range escaped as an
    OverflowError traceback. The R1-4 fix covered only the fire id. (A
    negative positional parses as a click option, a usage error already.)"""
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    _seed_sg(db)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "correct-cohort-provenance",
        str(trade_id), "--cite-fire-candidate", str(SG_FIRE_CANDIDATE_ID),
        "--reason", REASON])
    assert r.exit_code == 1, r.output
    assert "Error:" in r.output
    assert "Traceback" not in r.output
    assert "64-bit" in r.output
    assert r.exception is None or isinstance(r.exception, SystemExit)
    _assert_ascii(r.output)
    assert _rows(db) == []
