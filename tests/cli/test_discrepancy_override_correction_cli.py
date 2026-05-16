"""Phase 12 C.D T-D.4 — CLI: ``swing journal discrepancy override-correction``.

Per plan §E.4 acceptance criteria (spec §6.4 + OQ-8 + OQ-15 dispositions):

* §A — happy path with ``--force``: skips confirmation; override applied;
  new ``reconciliation_corrections`` row written with action
  ``operator_overridden``; prior row's ``superseded_by_correction_id``
  points to the new row.
* §B — confirmation prompt with stdin ``n\\n`` (decline): exit 0 with
  ``(aborted)`` message; NO new correction row written; prior row's
  ``superseded_by_correction_id`` remains NULL.
* §C — confirmation prompt with stdin ``y\\n`` (accept): override applied
  (same end state as §A).
* §D — already-superseded correction_id: exit 2 with friendly error
  naming the chain-head correction_id (OQ-15 disposition).
* §E — missing ``--truth-value`` → non-zero exit.
* §F — missing ``--reason`` → non-zero exit.
* §G — malformed JSON in ``--truth-value`` → exit 2.
* §H — ``ValidatorRejectedError`` from service → exit 1 + friendly message.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


# ---------------------------------------------------------------------------
# Workspace + seed helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_workspace(tmp_path: Path):
    """Create a project + home dir + run db-migrate to land schema v19."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _seed_cvgi_with_tier1_correction(db_path: Path) -> dict[str, Any]:
    """Plant CVGI fixture + a tier-1 correction so we have a row to override.

    Mirrors ``tests/trades/test_apply_tier3_override.py::_seed_cvgi_world``
    but committing through the CLI's DB path so the runner can read it.
    Returns dict with trade_id / fill_id / discrepancy_id / tier1_correction_id.
    """
    from swing.trades.reconciliation_auto_correct import apply_tier1_correction
    from swing.trades.reconciliation_classifier import ClassificationResult

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO trades (
                ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, state, trade_origin, pre_trade_locked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
                "manual_off_pipeline", "2026-04-27T16:00:00",
            ),
        )
        trade_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO fills (
                fill_id, trade_id, fill_datetime, action, quantity, price,
                reconciliation_status
            ) VALUES (9, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.23,
                "unreconciled",
            ),
        )
        from swing.data.repos.fills import _recompute_aggregates
        _recompute_aggregates(conn, trade_id)
        run_cur = conn.execute(
            """
            INSERT INTO reconciliation_runs (source, started_ts, state)
            VALUES (?, ?, ?)
            """,
            ("schwab_api", "2026-05-15T12:00:00", "running"),
        )
        run_id = int(run_cur.lastrowid)
        conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
                ticker, field_name, expected_value_json, actual_value_json,
                delta_text, material_to_review, resolution, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                41, run_id, "entry_price_mismatch", trade_id, 9,
                "CVGI", "price", '{"price": 5.23}', '{"price": 5.30}',
                "+$0.07", 1, "unresolved", "2026-05-15T12:00:00",
            ),
        )
        conn.commit()

        classification = ClassificationResult(
            tier=1, ambiguity_kind=None,
            correction_target={"price": 5.30},
            correction_reason="initial tier-1 apply",
            candidate_choices=None,
        )
        tier1 = apply_tier1_correction(
            conn, discrepancy_id=41, classification=classification,
            environment="production",
        )
        return {
            "trade_id": trade_id,
            "fill_id": 9,
            "run_id": run_id,
            "discrepancy_id": 41,
            "tier1_correction_id": tier1.correction_id,
        }
    finally:
        conn.close()


def _correction_row(db_path: Path, correction_id: int) -> tuple[Any, ...]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT correction_action, applied_by, "
            "pre_correction_value_json, applied_value_json, "
            "operator_truth_value_json, superseded_by_correction_id "
            "FROM reconciliation_corrections WHERE correction_id = ?",
            (correction_id,),
        ).fetchone()
    finally:
        conn.close()


def _count_corrections_for_discrepancy(db_path: Path, did: int) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()[0]
    finally:
        conn.close()


# ===========================================================================
# §A — Happy path with --force (skips prompt)
# ===========================================================================


def test_override_correction_force_happy_path(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]
    did = seed["discrepancy_id"]

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", '{"price": 5.25}',
        "--reason", "Verified broker statement; actual was $5.25",
        "--force",
    ])
    assert r.exit_code == 0, r.output
    assert "override applied" in r.output
    assert f"prior correction_id={tier1_id}" in r.output
    assert "new correction_id=" in r.output
    # No confirmation prompt fired with --force.
    assert "Override this correction" not in r.output

    # End-state: 2 correction rows for the discrepancy; chain pointer set.
    assert _count_corrections_for_discrepancy(db_path, did) == 2
    prior = _correction_row(db_path, tier1_id)
    assert prior is not None
    # superseded_by_correction_id points to the new row.
    assert prior[5] is not None
    new_id = prior[5]
    new = _correction_row(db_path, new_id)
    assert new is not None
    assert new[0] == "operator_overridden"
    assert new[1] == "operator"
    # applied_value_json + operator_truth_value_json are the override value.
    assert json.loads(new[3]) == {"price": 5.25}
    assert json.loads(new[4]) == {"price": 5.25}


# ===========================================================================
# §B — Confirmation prompt with "n" → aborted
# ===========================================================================


def test_override_correction_prompt_decline_aborts(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]
    did = seed["discrepancy_id"]
    before = _count_corrections_for_discrepancy(db_path, did)

    r = runner.invoke(
        main,
        [
            "--config", str(cfg),
            "journal", "discrepancy", "override-correction", str(tier1_id),
            "--truth-value", '{"price": 5.25}',
            "--reason", "test rationale",
        ],
        input="n\n",
    )
    assert r.exit_code == 0, r.output
    assert "(aborted)" in r.output
    # Prompt rendered the current correction summary + proposed override.
    assert "Override this correction" in r.output

    # No new correction row written.
    after = _count_corrections_for_discrepancy(db_path, did)
    assert after == before
    # Prior row's chain pointer stayed NULL.
    prior = _correction_row(db_path, tier1_id)
    assert prior[5] is None


# ===========================================================================
# §C — Confirmation prompt with "y" → override applied
# ===========================================================================


def test_override_correction_prompt_accept_applies(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]
    did = seed["discrepancy_id"]

    r = runner.invoke(
        main,
        [
            "--config", str(cfg),
            "journal", "discrepancy", "override-correction", str(tier1_id),
            "--truth-value", '{"price": 5.25}',
            "--reason", "accept-confirm test",
        ],
        input="y\n",
    )
    assert r.exit_code == 0, r.output
    assert "override applied" in r.output
    # Verify mutation persisted.
    assert _count_corrections_for_discrepancy(db_path, did) == 2
    prior = _correction_row(db_path, tier1_id)
    assert prior[5] is not None


# ===========================================================================
# §D — Already-superseded correction_id → exit 2 + chain-head guidance
# ===========================================================================


def test_override_correction_already_superseded_names_chain_head(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]

    # First override (succeeds) — tier1_id becomes superseded.
    r1 = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", '{"price": 5.25}',
        "--reason", "first override",
        "--force",
    ])
    assert r1.exit_code == 0, r1.output
    # Determine new chain-head correction_id from DB state.
    prior = _correction_row(db_path, tier1_id)
    new_head = prior[5]
    assert new_head is not None

    # Second override against the SAME (now-superseded) id → exit 2.
    r2 = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", '{"price": 5.20}',
        "--reason", "second override against stale row",
        "--force",
    ])
    assert r2.exit_code == 2, r2.output
    assert f"correction {tier1_id}" in r2.output
    assert "already superseded by" in r2.output
    assert f"correction {new_head}" in r2.output
    # Routing-hint: override the chain head.
    assert "override the chain head" in r2.output


# ===========================================================================
# §E — Missing --truth-value → non-zero exit
# ===========================================================================


def test_override_correction_missing_truth_value_errors(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--reason", "missing truth-value",
        "--force",
    ])
    assert r.exit_code != 0
    assert "--truth-value" in r.output


# ===========================================================================
# §F — Missing --reason → non-zero exit
# ===========================================================================


def test_override_correction_missing_reason_errors(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", '{"price": 5.25}',
        "--force",
    ])
    assert r.exit_code != 0
    assert "--reason" in r.output


# ===========================================================================
# §G — Malformed JSON in --truth-value → exit 2
# ===========================================================================


def test_override_correction_malformed_json_errors(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]
    did = seed["discrepancy_id"]
    before = _count_corrections_for_discrepancy(db_path, did)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", "{not valid json",
        "--reason", "should fail",
        "--force",
    ])
    assert r.exit_code == 2, r.output
    assert "--truth-value" in r.output
    # No mutation happened.
    assert _count_corrections_for_discrepancy(db_path, did) == before


# ===========================================================================
# §H — Validator rejects the operator_truth_value → exit 1 + friendly msg
# ===========================================================================


def test_override_correction_validator_rejection_exits_1(
    cli_workspace,
) -> None:
    """The validator chain rejects non-finite (NaN/inf) REAL field values per
    ``swing/trades/reconciliation_validators.py``. Submit ``"price": NaN``
    (encoded as ``"price": 1e500`` → inf when parsed) → service raises
    ValidatorRejectedError BEFORE any mutation."""
    runner, cfg, db_path = cli_workspace
    seed = _seed_cvgi_with_tier1_correction(db_path)
    tier1_id = seed["tier1_correction_id"]
    did = seed["discrepancy_id"]
    before = _count_corrections_for_discrepancy(db_path, did)

    # JSON has no native NaN; use a numeric value that parses to float
    # then becomes non-finite via overflow. json.loads("1e500") → inf.
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "override-correction", str(tier1_id),
        "--truth-value", '{"price": 1e500}',
        "--reason", "non-finite payload should be rejected",
        "--force",
    ])
    assert r.exit_code == 1, r.output
    assert "validator rejected" in r.output.lower()
    # No mutation happened — prior row's chain pointer still NULL.
    prior = _correction_row(db_path, tier1_id)
    assert prior[5] is None
    assert _count_corrections_for_discrepancy(db_path, did) == before
