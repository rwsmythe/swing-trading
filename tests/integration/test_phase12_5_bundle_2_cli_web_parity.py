"""Phase 12.5 #2 T-2.11 — CLI/web parity tests.

Per plan §A T-2.11 acceptance + spec §13.3 R2 LOCK + F2 + F18: the
operator-typed CLI path (``swing journal discrepancy resolve-ambiguity``)
and the web POST path (``/reconcile/discrepancy/{id}/resolve``) MUST
produce semantically-equivalent ``reconciliation_corrections`` audit
rows (semantic-shape projection equality; operator-typed reason
normalized as a sentinel because the test supplies different strings
per path).

The ONE deliberate, distinguishing difference is
``reconciliation_discrepancies.resolved_by``:
  - CLI path -> ``'operator'`` (pre-existing default)
  - Web path -> ``'operator_web'`` (F2 LOCK)

Tests:
  - test_cli_web_audit_row_semantic_shape_parity
  - test_cli_web_resolved_by_distinguishability
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main as cli_main
from swing.config import Config, load
from swing.data.db import ensure_schema
from swing.web.app import create_app

_SEMANTIC_PROJECTION_COLUMNS = (
    "correction_action",
    "correction_choice",
    "affected_table",
    "field_name",
    "pre_correction_value_json",
    "source_canonical_value_json",
    "applied_value_json",
    "operator_truth_value_json",
    "applied_by",
    "correction_reason",
    "notes",
    "risk_policy_id_at_correction",
)

_REASON_SENTINEL = "<REASON-NORMALIZED>"


def _make_cfg(tmp_path: Path) -> tuple[Config, Path]:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed_one_pending_ambiguity(
    db_path: Path, *, ticker: str,
) -> tuple[int, int, int]:
    """Plant trade+entry-fill+reconciliation_run+one pending ambiguity. Returns
    (trade_id, fill_id, discrepancy_id).

    Both discrepancies seeded in this test will share the SAME
    ``ambiguity_kind``, ``expected_value_json``, ``actual_value_json``,
    ``field_name``, and ``discrepancy_type`` -- the only difference is the
    surface used to resolve them.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            """
            INSERT INTO trades (
                ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, state, trade_origin, pre_trade_locked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker, "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
                "manual_off_pipeline", "2026-04-27T16:00:00",
            ),
        )
        trade_id = int(cur.lastrowid)
        fcur = conn.execute(
            """
            INSERT INTO fills (trade_id, fill_datetime, action, quantity, price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 10.0),
        )
        fill_id = int(fcur.lastrowid)
        rcur = conn.execute(
            """
            INSERT INTO reconciliation_runs (source, started_ts, state)
            VALUES (?, ?, ?)
            """,
            ("schwab_api", "2026-05-18T12:00:00", "running"),
        )
        run_id = int(rcur.lastrowid)
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, ticker,
                field_name, expected_value_json, actual_value_json, delta_text,
                material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, "entry_price_mismatch", trade_id, fill_id, ticker,
                "price", '{"price": 10.0}', '{"price": 10.10}', "+$0.10",
                1, "pending_ambiguity_resolution",
                "multi_partial_vs_consolidated",
                None, None, None,
                "2026-05-18T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return trade_id, fill_id, discrepancy_id
    finally:
        conn.close()


def _fetch_semantic_projection(
    db_path: Path, discrepancy_id: int,
) -> dict[str, object]:
    """Project the latest correction row for ``discrepancy_id`` onto the
    semantic-shape columns per spec §13.3 R2 LOCK; normalize the operator-
    typed ``correction_reason`` field to a sentinel so the two paths'
    differently-worded reasons don't trip the equality assertion.
    """
    placeholders = ", ".join(_SEMANTIC_PROJECTION_COLUMNS)
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            f"SELECT {placeholders} FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? "
            "ORDER BY correction_id DESC LIMIT 1",
            (discrepancy_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, (
        f"expected a reconciliation_corrections row for "
        f"discrepancy_id={discrepancy_id}"
    )
    projection = dict(zip(_SEMANTIC_PROJECTION_COLUMNS, row, strict=True))
    # Normalize operator-typed reason so the two paths' different reason
    # strings don't break the equality assertion. The test asserts the
    # remaining columns match semantically (everything else flows from the
    # discrepancy + choice).
    projection["correction_reason"] = _REASON_SENTINEL
    return projection


def _fetch_resolved_by(db_path: Path, discrepancy_id: int) -> str | None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT resolved_by FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else row[0]


def test_cli_web_audit_row_semantic_shape_parity(tmp_path: Path) -> None:
    """Resolve two structurally-identical discrepancies via the CLI + web
    paths; assert their reconciliation_corrections rows match on the
    semantic-shape projection (with ``correction_reason`` normalized)."""
    cfg, cfg_path = _make_cfg(tmp_path)
    db_path = cfg.paths.db_path
    _, _, disc_cli = _seed_one_pending_ambiguity(db_path, ticker="CLI")
    _, _, disc_web = _seed_one_pending_ambiguity(db_path, ticker="WEB")

    # CLI path: invoke via swing journal discrepancy resolve-ambiguity.
    runner = CliRunner()
    r_cli = runner.invoke(cli_main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "resolve-ambiguity", str(disc_cli),
        "--choice", "keep_journal_as_is",
        "--reason", "cli-acked",
    ])
    assert r_cli.exit_code == 0, r_cli.output

    # Web path: TestClient POST.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_web = client.post(
            f"/reconcile/discrepancy/{disc_web}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "web-acked-via-form",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r_web.status_code == 204, r_web.text[:300]

    proj_cli = _fetch_semantic_projection(db_path, disc_cli)
    proj_web = _fetch_semantic_projection(db_path, disc_web)

    # F18 LOCK: semantic-shape projection equality.
    assert proj_cli == proj_web, (
        f"semantic projection mismatch:\n  CLI: {proj_cli}\n  WEB: {proj_web}"
    )

    # Belt-and-suspenders: both rows should record applied_by='operator'
    # (a manual operator resolved them in either case).
    assert proj_cli["applied_by"] == "operator"
    assert proj_web["applied_by"] == "operator"
    assert proj_cli["correction_action"] == "operator_resolved_ambiguity"
    assert proj_web["correction_action"] == "operator_resolved_ambiguity"


def test_cli_web_resolved_by_distinguishability(tmp_path: Path) -> None:
    """F2 LOCK distinguishability: CLI -> ``'operator'``; web -> ``'operator_web'``."""
    cfg, cfg_path = _make_cfg(tmp_path)
    db_path = cfg.paths.db_path
    _, _, disc_cli = _seed_one_pending_ambiguity(db_path, ticker="CLI")
    _, _, disc_web = _seed_one_pending_ambiguity(db_path, ticker="WEB")

    runner = CliRunner()
    r_cli = runner.invoke(cli_main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "resolve-ambiguity", str(disc_cli),
        "--choice", "keep_journal_as_is",
        "--reason", "cli-acked",
    ])
    assert r_cli.exit_code == 0, r_cli.output

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_web = client.post(
            f"/reconcile/discrepancy/{disc_web}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "web-acked",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r_web.status_code == 204, r_web.text[:300]

    cli_resolved_by = _fetch_resolved_by(db_path, disc_cli)
    web_resolved_by = _fetch_resolved_by(db_path, disc_web)
    assert cli_resolved_by == "operator", cli_resolved_by
    assert web_resolved_by == "operator_web", web_resolved_by
    assert cli_resolved_by != web_resolved_by, (
        "F2 LOCK violated: surfaces must be distinguishable via resolved_by"
    )


# Force module-level import of pytest so the file is at minimum a valid
# pytest test module even if collection happens with --co for inventory.
_ = pytest
