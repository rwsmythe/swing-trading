"""Arc 22-B Task 7 -- N4 (CHARC, R0.D): `unintended_execution` is TERMINAL for
every generic writer.

Three layers, each named to the writer it catches: (1) `update_entry_intent`
(and the pure read `assert_entry_intent_change_allowed` it shares with the two
review surfaces, which call it BEFORE the review commits, R2-02); (2) the
corrector's reservation; (3) the SQL twin `trg_trades_entry_intent_attested_
terminal` (b22_34, tested alone). Here: layers 1 and 2 by execution, and layer
1 ALONE with the trigger dropped (b22_127), so neither layer masks the other.

Every attested trade is made by the REAL writer (`assign`), on trade 20's
live row shape (`tests/_22b_fixtures.attest_trade20`).
"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect, ensure_schema
from swing.data.models import (
    UNINTENDED_EXECUTION,
    AttestedIntentError,
    attested_message,
)
from swing.data.repos.trades import (
    assert_entry_intent_change_allowed,
    update_entry_intent,
)
from tests._22b_fixtures import attest_trade20
from tests.cli.test_cli_eval import _minimal_config

N4_TRIGGER = "trg_trades_entry_intent_attested_terminal"
REVIEW_COLUMNS = ("state", "reviewed_at", "entry_grade", "management_grade",
                  "exit_grade", "process_grade", "lesson_learned",
                  "mistake_tags", "entry_intent")


def _attested_db(tmp_path: Path) -> tuple[Path, int]:
    db = tmp_path / "t.db"
    ensure_schema(db).close()
    return db, attest_trade20(db)


def _cli(tmp_path: Path) -> tuple[CliRunner, Path, Path, int]:
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    res = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert res.exit_code == 0, res.output
    db = Path(tomllib.loads(cfg.read_text())["paths"]["db_path"])
    return runner, cfg, db, attest_trade20(db)


def _row(db: Path, trade_id: int = 20) -> tuple:
    c = sqlite3.connect(db)
    try:
        return c.execute(f"SELECT {', '.join(REVIEW_COLUMNS)} FROM trades "
                         "WHERE id = ?", (trade_id,)).fetchone()
    finally:
        c.close()


def test_the_message_is_n4s_words_and_names_the_row() -> None:
    msg = attested_message(7)
    assert msg == ("entry_intent is attested (entry_intent_attestations row 7); "
                   "no reversal surface exists -- a reversal is a NEW evidence "
                   "class with its own record")
    assert "assign-intent" not in msg  # R0.D: assign-intent is NOT the recovery
    assert msg.isascii()
    assert issubclass(AttestedIntentError, ValueError)


def test_cli_review_entry_intent_standard_refuses_b22_123(tmp_path: Path) -> None:
    """The refusal lands BEFORE complete_trade_review (R2-02): the review
    fields and `state` are byte-unchanged, read on a fresh connection."""
    runner, cfg, db, att_id = _cli(tmp_path)
    before = _row(db)
    assert before[0] == "closed" and before[-1] == UNINTENDED_EXECUTION
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", "20",
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--entry-intent", "standard"])
    assert res.exit_code != 0
    assert attested_message(att_id) in res.output, res.output
    assert _row(db) == before


def test_cli_review_without_entry_intent_still_completes(tmp_path: Path) -> None:
    """The control: the terminality check does not block a review that does
    not touch the intent."""
    runner, cfg, db, _ = _cli(tmp_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", "20",
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean"])
    assert res.exit_code == 0, res.output
    row = _row(db)
    assert row[0] == "reviewed" and row[-1] == UNINTENDED_EXECUTION


@pytest.mark.parametrize("flags", [["--force"], ["--trade-id", "20"]])
def test_backfill_force_skips_attested_row_b22_124(tmp_path: Path,
                                                   flags: list[str]) -> None:
    """--force / --trade-id SKIP an attested row with the message; they never
    PROMPT over it (no input is supplied, so a prompt would abort)."""
    runner, cfg, db, att_id = _cli(tmp_path)
    res = runner.invoke(main, ["--config", str(cfg), "trade", "backfill-intent",
                               *flags], input="")
    assert res.exit_code == 0, res.output
    assert attested_message(att_id) in res.output, res.output
    assert "intent [standard" not in res.output  # never prompted
    assert _row(db)[-1] == UNINTENDED_EXECUTION


def test_corrector_on_entry_intent_raises_reserved_b22_125(tmp_path: Path) -> None:
    from swing.trades.reconciliation_auto_correct import (
        ReservedJournalFieldError,
        _update_journal_field,
    )

    db, _ = _attested_db(tmp_path)
    conn = connect(db)
    try:
        for value in ("standard", None):
            with pytest.raises(ReservedJournalFieldError):
                _update_journal_field(conn, "trades", 20, "entry_intent", value)
    finally:
        conn.close()
    assert _row(db)[-1] == UNINTENDED_EXECUTION


def test_update_entry_intent_same_value_passes_b22_126(tmp_path: Path) -> None:
    """A same-value write is a no-op (idempotent), through layer 1 and the
    trigger alike; every DIFFERENT value, NULL included, is refused typed."""
    db, att_id = _attested_db(tmp_path)
    conn = connect(db)
    try:
        with conn:
            update_entry_intent(conn, trade_id=20, entry_intent=UNINTENDED_EXECUTION)
        assert_entry_intent_change_allowed(
            conn, trade_id=20, entry_intent=UNINTENDED_EXECUTION)
        for value in ("standard", "hypothesis_test_by_design", None):
            with pytest.raises(AttestedIntentError) as exc, conn:
                update_entry_intent(conn, trade_id=20, entry_intent=value)
            assert str(exc.value) == attested_message(att_id)
    finally:
        conn.close()
    assert _row(db)[-1] == UNINTENDED_EXECUTION


def test_layer1_race_with_assign_refuses_typed_b22_226(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex R1 Major 2: `assign` commits BETWEEN layer 1's reads and the
    UPDATE. The reads saw NULL, so the N4 trigger is what aborts the UPDATE;
    the generic writer must still raise the TYPED ``AttestedIntentError`` (a
    ``ValueError`` every surface converts), never a raw
    ``sqlite3.IntegrityError``. The race is made deterministic by committing
    the real ``assign`` on a SECOND connection from inside layer 1's pre-check
    (which then returns, as a read taken before that commit would have).
    Pre-fix: ``sqlite3.IntegrityError`` from the trigger's RAISE."""
    from swing.data.db import open_connection
    from swing.data.repos import trades as trades_repo
    from swing.trades.entry_intent_assignment import assign
    from tests._22b_fixtures import seed_amn_row5, seed_trade20

    db = tmp_path / "t.db"
    ensure_schema(db).close()
    seed = open_connection(db)
    try:
        seed_amn_row5(seed)
        seed_trade20(seed, state="closed")
        seed.commit()
    finally:
        seed.close()

    real_check = trades_repo.assert_entry_intent_change_allowed
    committed: list[int] = []

    def _stale_check(conn, *, trade_id, entry_intent):
        if not committed:
            other = open_connection(db)
            try:
                res = assign(other, None, trade_id=20, cite=["notes", "why_now"],
                             reason="Stale A+ latch order fired after the "
                                    "mandate died", applied_by="operator")
            finally:
                other.close()
            assert res.admitted, res.message
            committed.append(int(res.attestation_id))
            return None
        return real_check(conn, trade_id=trade_id, entry_intent=entry_intent)

    monkeypatch.setattr(trades_repo, "assert_entry_intent_change_allowed",
                        _stale_check)
    conn = connect(db)
    try:
        with pytest.raises(AttestedIntentError) as exc, conn:
            update_entry_intent(conn, trade_id=20, entry_intent="standard")
    finally:
        conn.close()
    assert str(exc.value) == attested_message(committed[0])
    assert _row(db)[-1] == UNINTENDED_EXECUTION


def test_layer1_alone_refuses_with_trigger_absent_b22_127(tmp_path: Path) -> None:
    """The trigger DROPPED in the test DB (a pre-trigger shape): the service
    layer alone still refuses. Pre-fix arithmetic: with no layer 1 the same
    call writes 'standard' (the control below proves the trigger is gone)."""
    db, att_id = _attested_db(tmp_path)
    raw = sqlite3.connect(db)
    raw.execute(f"DROP TRIGGER {N4_TRIGGER}")
    raw.commit()
    raw.close()
    conn = connect(db)
    try:
        with pytest.raises(AttestedIntentError, match="row "), conn:
            update_entry_intent(conn, trade_id=20, entry_intent="standard")
    finally:
        conn.close()
    assert _row(db)[-1] == UNINTENDED_EXECUTION
    # The control: with the trigger gone, a RAW write is not refused.
    raw = sqlite3.connect(db)
    try:
        raw.execute("UPDATE trades SET entry_intent = 'standard' WHERE id = 20")
        assert raw.execute("SELECT entry_intent FROM trades WHERE id = 20"
                           ).fetchone() == ("standard",)
    finally:
        raw.close()
    assert attested_message(att_id).endswith("its own record")
