"""Arc 22-B RULING B item 2 (B-02, CHARC 2026-09-24): `trade review`'s close
handler re-evaluates TWO durability facts -- `review_committed` (bound
immediately after ``complete_trade_review`` returns) and `intent_committed`
(bound immediately after ``update_entry_intent``'s transaction exits), each
bound at its writer's own return, never cached earlier.

The bare ``finally: conn.close()`` predating this arc turned a committed
review, or a committed intent change, into exit 1 -- and on the AL-6 race
(``tests/trades/test_22b_terminal.py::...b22_240``) a close failure REPLACED
the ruled R3-1 refusal text instead of naming itself alongside it.

Discriminators, a ``close()`` that performs the REAL close and THEN raises
(the b22_251 probe, reused verbatim):
  (a) a review alone -> exit 0, WARN present on stderr naming the close
      failure, the review durable.
  (b) a review plus an intent change -> exit 0, both durable.
  (c) the AL-6 race -> exit nonzero, the R3-1 text PRESENT in R3-1's order
      (the committed review first, the refused intent second), the close
      failure NAMED after them and CHAINED; the review durable, the intent
      NOT written.
  (d) a pre-commit refusal (``complete_trade_review``'s own ``ValueError``)
      -> exit nonzero, the refusal text present, the close failure NAMED
      and CHAINED, nothing written.

The no-close-failure CONTROL is b22_240/241
(``tests/trades/test_22b_terminal.py``), left byte-unchanged by this file.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import click

from swing.cli import main
from swing.data.models import UNINTENDED_EXECUTION, attested_message
from tests._22b_fixtures import seed_amn_row5
from tests.trades.test_22b_terminal import (
    _REVIEW_WITH_STANDARD,
    _cli_closed_trade20,
    _row,
)

_REVIEW_PLAIN = [
    "trade", "review", "--trade-id", "20",
    "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
    "--mistake-tags", "none_observed", "--lesson-learned", "clean",
]


class _CloseRaises:
    """The b22_251 probe (``tests/cli/test_assign_intent_cli.py``), reused
    verbatim: forward everything to the real connection, perform the REAL
    close(), THEN raise -- so what is durable is genuinely so."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __enter__(self):
        object.__getattribute__(self, "_real").__enter__()
        return self

    def __exit__(self, *a):
        return object.__getattribute__(self, "_real").__exit__(*a)

    def close(self):
        object.__getattribute__(self, "_real").close()
        raise sqlite3.OperationalError("22-B PROBE: close failed")


def _patch_connect_to_raise_on_close(monkeypatch) -> None:
    import swing.data.db as db_mod
    real_connect = db_mod.connect

    def _wrapped(*a, **kw):
        return _CloseRaises(real_connect(*a, **kw))

    monkeypatch.setattr(db_mod, "connect", _wrapped)


def test_close_raising_after_a_review_alone_warns_and_stays_durable_b02_a(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """(a) A review alone: exit 0, WARN present on stderr naming the close
    failure, the review durable (read on a FRESH connection)."""
    runner, cfg, db = _cli_closed_trade20(tmp_path)
    _patch_connect_to_raise_on_close(monkeypatch)
    with caplog.at_level(logging.ERROR, logger="swing.cli"):
        res = runner.invoke(main, ["--config", str(cfg), *_REVIEW_PLAIN])
    assert res.exit_code == 0, (res.output, res.exception)
    assert res.exception is None
    row = _row(db)
    assert row[0] == "reviewed", row
    warn = [ln for ln in res.stderr.splitlines() if ln.startswith("WARN")]
    assert len(warn) == 1, res.stderr
    assert "DURABLE" in warn[0]
    assert "review" in warn[0]
    assert "CLOSING the database connection" in warn[0]
    assert "close failed" in warn[0]
    assert res.output.isascii()
    assert "close failed" in caplog.text and "IS DURABLE" in caplog.text


def test_close_raising_after_review_and_intent_reports_both_durable_b02_b(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """(b) A review plus an intent change: exit 0, both durable."""
    runner, cfg, db = _cli_closed_trade20(tmp_path)
    _patch_connect_to_raise_on_close(monkeypatch)
    with caplog.at_level(logging.ERROR, logger="swing.cli"):
        res = runner.invoke(main, ["--config", str(cfg), *_REVIEW_WITH_STANDARD])
    assert res.exit_code == 0, (res.output, res.exception)
    assert res.exception is None
    row = _row(db)
    assert row[0] == "reviewed" and row[-1] == "standard", row
    warn = [ln for ln in res.stderr.splitlines() if ln.startswith("WARN")]
    assert len(warn) == 1, res.stderr
    assert "DURABLE" in warn[0]
    assert "intent" in warn[0]
    assert "close failed" in warn[0]
    assert res.output.isascii()
    assert "close failed" in caplog.text and "IS DURABLE" in caplog.text


def test_close_raising_on_the_al6_race_names_and_chains_after_r3_1_b02_c(
        tmp_path: Path, monkeypatch) -> None:
    """(c) The AL-6 race (b22_240's planted-race technique), PLUS a close
    failure: exit nonzero, the R3-1 text PRESENT in R3-1's order (the
    committed review first, the refused intent second), the close failure
    NAMED after them and CHAINED; the review durable, the intent NOT
    written."""
    from swing.data.db import open_connection
    from swing.data.repos import trades as trades_repo
    from swing.trades.entry_intent_assignment import assign

    runner, cfg, db = _cli_closed_trade20(tmp_path)
    seed = open_connection(db)
    try:
        seed_amn_row5(seed)
        seed.commit()
    finally:
        seed.close()

    real_check = trades_repo.assert_entry_intent_change_allowed
    committed: list[int] = []

    def _stale_check(conn, *, trade_id, entry_intent):
        if not committed:
            other = open_connection(db)
            try:
                r = assign(other, None, trade_id=20, cite=["notes", "why_now"],
                           reason="Stale A+ latch order fired after the "
                                  "mandate died", applied_by="operator")
            finally:
                other.close()
            assert r.admitted, r.message
            committed.append(int(r.attestation_id))
            return None
        return real_check(conn, trade_id=trade_id, entry_intent=entry_intent)

    monkeypatch.setattr(trades_repo, "assert_entry_intent_change_allowed",
                        _stale_check)
    _patch_connect_to_raise_on_close(monkeypatch)
    res = runner.invoke(main, ["--config", str(cfg), *_REVIEW_WITH_STANDARD])
    assert committed, "the planted race did not run"
    assert res.exit_code != 0, res.output
    out = res.output
    recorded = out.find("Review recorded for trade #20")
    refused = out.find(f"Intent change REFUSED: {attested_message(committed[0])}")
    assert recorded != -1, out
    assert refused != -1, out
    assert recorded < refused, out  # the committed review FIRST, per R3-1
    assert "the connection close also failed" in out, out
    assert "close failed" in out, out
    assert type(res.exception) is SystemExit, repr(res.exception)
    click_exc = res.exception.__context__
    assert isinstance(click_exc, click.ClickException), repr(click_exc)
    assert (f"Intent change REFUSED: {attested_message(committed[0])}"
            in click_exc.message)
    assert "the connection close also failed" in click_exc.message
    assert type(click_exc.__cause__) is sqlite3.OperationalError, \
        repr(click_exc.__cause__)
    assert "close failed" in str(click_exc.__cause__)
    row = _row(db)
    assert row[0] == "reviewed" and row[-1] == UNINTENDED_EXECUTION


def test_close_raising_on_a_pre_commit_refusal_names_and_chains_b02_d(
        tmp_path: Path, monkeypatch) -> None:
    """(d) A pre-commit refusal (``complete_trade_review``'s own
    ``ValueError``): exit nonzero, the refusal text present, the close
    failure NAMED and CHAINED, nothing written."""
    import swing.trades.review as review_mod

    runner, cfg, db = _cli_closed_trade20(tmp_path)
    before = _row(db)

    def _boom(*a, **kw):
        raise ValueError("22-B PROBE: pre-commit review refusal")

    monkeypatch.setattr(review_mod, "complete_trade_review", _boom)
    _patch_connect_to_raise_on_close(monkeypatch)
    res = runner.invoke(main, ["--config", str(cfg), *_REVIEW_PLAIN])
    assert res.exit_code != 0, res.output
    assert "22-B PROBE: pre-commit review refusal" in res.output, res.output
    assert "the connection close also failed" in res.output, res.output
    assert "close failed" in res.output, res.output
    assert type(res.exception) is SystemExit, repr(res.exception)
    click_exc = res.exception.__context__
    assert isinstance(click_exc, click.ClickException), repr(click_exc)
    assert "22-B PROBE: pre-commit review refusal" in click_exc.message
    assert "the connection close also failed" in click_exc.message
    assert type(click_exc.__cause__) is sqlite3.OperationalError, \
        repr(click_exc.__cause__)
    assert "close failed" in str(click_exc.__cause__)
    assert _row(db) == before  # nothing written
