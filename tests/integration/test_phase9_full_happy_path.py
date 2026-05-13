"""Phase 9 combined E2E happy path (Sub-bundle E Task T-E.0).

Plan §H acceptance: a SINGLE test that runs the operator's natural workflow
across all four prior Phase 9 sub-bundles' surfaces in one connection:

  §1 (Sub-bundle A) — edit risk policy via ``swing config policy set``
      ⇒ ``supersede_active_policy`` chains policy_id 1 → 2.
  §2 (Sub-bundle B) — reconcile a TOS CSV via ``swing journal reconcile-tos``
      ⇒ emits close_price + stop + position_qty + cash_movement discrepancies.
  §3 (Sub-bundle B) — resolve one material discrepancy via CLI
      ⇒ row's resolution + resolved_at populated; parent run counter --.
  §4 (Sub-bundle C) — record an account equity snapshot via CLI.
  §5 (Sub-bundle C) — update hypothesis status via CLI
      ⇒ routes through ``update_hypothesis_status_with_audit``.
  §6 (Sub-bundle D) — issue a sector tamper attempt via web POST /trades/entry
      ⇒ ``_emit_sector_tamper_audit`` persists a system_audit reconciliation_run
      + sector_tamper discrepancy (material=0); entry transaction rolled back.
  §7 — verify ``list_unresolved_material_for_active_trades`` returns exactly the
      MATERIAL=1 active-trade rows from §2 minus the one resolved in §3 (and
      that the §6 sector_tamper row does NOT appear since material=0).
"""
from __future__ import annotations

from datetime import datetime as _dt
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main
from swing.config import load as load_config
from swing.data.db import connect
from swing.data.repos import reconciliation as recon_repo
from swing.data.repos.hypothesis_status_history import (
    list_history_for_hypothesis,
)
from swing.evaluation.dates import action_session_for_run
from swing.trades.reconciliation import MATERIAL_BY_TYPE
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.cli.test_cli_eval import _minimal_config
from tests.integration.test_phase9_end_to_end import (
    _E2E_TOS_CSV,
    _seed_journal_cash,
    _seed_managing_trade,
    _seed_partial_exited_trade,
)
from tests.web.conftest import full_phase7_entry_payload


def test_phase9_full_happy_path_across_all_sub_bundles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator's natural workflow exercising all four Phase 9 sub-bundles in
    one test/connection (plan §H Task T-E.0).

    Discriminating arithmetic for §7:
      - §2 emits FIVE active-trade discrepancies (all MAT=1):
          close_price_mismatch (DEF)
          stop_mismatch (ABC) + stop_mismatch (DEF)
          position_qty_mismatch (ABC) + position_qty_mismatch (DEF)
        plus cash_movement_mismatch (NULL trade_id, MAT=0) ⇒ filtered out.
      - ``list_unresolved_material_for_active_trades`` ⇒ 5 attention rows
        pre-resolve, all touching {ABC, DEF}.
      - §3 resolves ONE of the 5 ⇒ 4 remain.
      - §6 emits sector_tamper (MAT=0) ⇒ MUST NOT appear in §7.
      ⇒ final assertion: count == active_count_pre - 1.
    The expected_pre count is computed at §2 from the actual emit so the
    arithmetic remains discriminating even if Bundle B reflows what counts
    as a discrepancy emission — what matters for §3 is "exactly one fewer
    than pre" + "sector_tamper not in".
    """
    # CLAUDE.md gotcha: tests that exercise ``write_user_overrides`` (the
    # ``swing config policy set`` path consults ``_user_home()``) MUST
    # monkeypatch BOTH USERPROFILE and HOME or writes leak to the operator's
    # real ~/swing-data/user-config.toml.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "project"
    project.mkdir()
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()

    # Bootstrap DB at v17 (lands the risk_policy seed at policy_id=1 +
    # ratifies cfg-derived seed values on the v16→v17 transition).
    r_init = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r_init.exit_code == 0, r_init.output
    db_path = home / "swing-data" / "swing.db"

    # =========================================================================
    # §1: edit risk policy via CLI ⇒ supersede_active_policy chains 1 → 2 (or
    # higher if ratification fired during migration).
    # =========================================================================
    conn = connect(db_path)
    try:
        prior = conn.execute(
            "SELECT policy_id, max_account_risk_per_trade_pct, effective_to "
            "FROM risk_policy "
            "WHERE effective_to IS NULL"
        ).fetchone()
        assert prior is not None, "active risk_policy row must exist post-migrate"
        prior_policy_id, prior_max_risk_pct, prior_effective_to = prior
        assert prior_effective_to is None
    finally:
        conn.close()

    new_max_risk = "0.0075"  # differs from cfg-seeded 0.005 to avoid no-op-skip.
    r_policy = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "policy", "set",
        "--field", "max_account_risk_per_trade_pct",
        "--value", new_max_risk,
        "--notes", "Bundle E full-happy-path §1",
    ])
    assert r_policy.exit_code == 0, r_policy.output

    conn = connect(db_path)
    try:
        new_active = conn.execute(
            "SELECT policy_id, max_account_risk_per_trade_pct, "
            "effective_from, effective_to "
            "FROM risk_policy WHERE effective_to IS NULL"
        ).fetchone()
        assert new_active is not None
        new_policy_id, new_max_risk_val, new_eff_from, new_eff_to = new_active
        assert new_policy_id > prior_policy_id, (
            f"supersede must chain forward: prior={prior_policy_id} "
            f"new={new_policy_id}"
        )
        assert abs(new_max_risk_val - float(new_max_risk)) < 1e-9
        assert new_eff_to is None
        # Predecessor row closed: its effective_to == new row's effective_from.
        predecessor = conn.execute(
            "SELECT effective_to FROM risk_policy WHERE policy_id = ?",
            (prior_policy_id,),
        ).fetchone()
        assert predecessor[0] == new_eff_from, (
            f"predecessor effective_to ({predecessor[0]}) must align with new "
            f"effective_from ({new_eff_from})"
        )
    finally:
        conn.close()

    # =========================================================================
    # §2: seed two trades + a journal cash row, then reconcile via CLI.
    # CSV emits all four Bundle B discrepancy types (mirrors the existing
    # ``test_phase9_end_to_end_four_discrepancy_types`` shape).
    # =========================================================================
    conn = connect(db_path)
    try:
        tid_abc = _seed_managing_trade(
            conn, ticker="ABC", entry_date="2026-05-10",
            entry_price=10.00, shares=10, initial_stop=9.00,
        )
        tid_def, _exit_fid = _seed_partial_exited_trade(
            conn, ticker="DEF", entry_date="2026-05-08",
            entry_price=20.00, shares=10, initial_stop=18.00,
            exit_date="2026-05-12", exit_price=11.00, exit_shares=5,
        )
        _seed_journal_cash(conn, ref="REF-001", kind="deposit", amount=400.00)
    finally:
        conn.close()

    csv = tmp_path / "tos.csv"
    csv.write_text(_E2E_TOS_CSV, encoding="utf-8")
    r_recon = runner.invoke(main, [
        "--config", str(cfg_path),
        "journal", "reconcile-tos",
        "--csv-path", str(csv),
        "--period-end", "2026-05-12",
    ])
    assert r_recon.exit_code == 0, r_recon.output

    conn = connect(db_path)
    try:
        runs = recon_repo.list_recent_runs(conn, limit=5)
        assert len(runs) == 1
        run_id = runs[0].run_id
        ds = recon_repo.list_discrepancies_for_run(conn, run_id)
        types = sorted({d.discrepancy_type for d in ds})
        # All four canonical types must surface.
        assert "close_price_mismatch" in types, types
        assert "stop_mismatch" in types, types
        assert "position_qty_mismatch" in types, types
        assert "cash_movement_mismatch" in types, types
        # MATERIAL_BY_TYPE applied authoritatively at INSERT time.
        for d in ds:
            assert d.material_to_review == MATERIAL_BY_TYPE[d.discrepancy_type]

        # Pre-resolve active-trade attention snapshot: 5 rows
        # (close_price + stop×2 + position_qty×2, all material=1, all on
        # {ABC, DEF}).
        active_pre = recon_repo.list_unresolved_material_for_active_trades(conn)
        assert {d.trade_id for d in active_pre} == {tid_abc, tid_def}
        active_count_pre = len(active_pre)
        assert active_count_pre == 5, (
            f"expected 5 material+active discrepancies pre-resolve "
            f"(close_price + stop×2 + position_qty×2); got {active_count_pre}: "
            f"{[(d.discrepancy_id, d.discrepancy_type, d.trade_id) for d in active_pre]}"
        )
        # Every pre-resolve row is material=1 (cash_movement is filtered out).
        for d in active_pre:
            assert d.material_to_review == 1
            assert d.trade_id is not None

        # Pick the first material+active discrepancy to resolve (any of the 3).
        target_to_resolve = active_pre[0]
        target_did = target_to_resolve.discrepancy_id
        # Codex R1 Minor #1: capture parent run's unresolved-counter
        # pre-resolve so §3's resolution-side assertion can verify the
        # decrement (counter -- contract per ``run_tos_reconciliation``
        # at swing/trades/reconciliation.py:497-502).
        parent_run_unresolved_pre = conn.execute(
            "SELECT unresolved_discrepancies_count FROM reconciliation_runs "
            "WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        assert parent_run_unresolved_pre is not None and parent_run_unresolved_pre > 0
    finally:
        conn.close()

    # =========================================================================
    # §3: resolve one material discrepancy via CLI.
    # =========================================================================
    r_resolve = runner.invoke(main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "resolve", str(target_did),
        "--resolution", "journal_corrected",
        "--reason", "Bundle E full-happy-path §3 resolve probe",
    ])
    assert r_resolve.exit_code == 0, r_resolve.output

    conn = connect(db_path)
    try:
        d_after = recon_repo.get_discrepancy(conn, target_did)
        assert d_after.resolution == "journal_corrected"
        assert d_after.resolved_at is not None
        assert d_after.resolved_by == "operator"
        # Codex R1 Minor #1: parent run's unresolved counter -- (docstring
        # §3 line "parent run counter --"). Pre-fix the test did not
        # assert this; with the no-op rollback at swing/trades/
        # reconciliation.py:497-502 disabled the counter would stay at
        # parent_run_unresolved_pre and this assertion would fail.
        parent_run_unresolved_post = conn.execute(
            "SELECT unresolved_discrepancies_count FROM reconciliation_runs "
            "WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        assert parent_run_unresolved_post == parent_run_unresolved_pre - 1, (
            f"parent run unresolved counter must decrement by 1 on resolve "
            f"(pre={parent_run_unresolved_pre}, "
            f"post={parent_run_unresolved_post})"
        )
    finally:
        conn.close()

    # =========================================================================
    # §4: record an account snapshot via CLI (today's session).
    # =========================================================================
    snapshot_date = "2026-05-12"
    r_snap = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--date", snapshot_date,
        "--notes", "Bundle E full-happy-path §4",
    ])
    assert r_snap.exit_code == 0, r_snap.output
    assert "back-recorded" not in r_snap.output  # today is not >7 days past

    conn = connect(db_path)
    try:
        snap_row = conn.execute(
            "SELECT snapshot_date, equity_dollars, source "
            "FROM account_equity_snapshots WHERE snapshot_date = ?",
            (snapshot_date,),
        ).fetchone()
        assert snap_row == (snapshot_date, 1300.0, "manual")
    finally:
        conn.close()

    # =========================================================================
    # §5: update hypothesis status via CLI (active → paused).
    # =========================================================================
    list_r = runner.invoke(main, ["--config", str(cfg_path), "hypothesis", "list"])
    assert list_r.exit_code == 0, list_r.output
    line = next(
        ln for ln in list_r.output.splitlines() if "A+ baseline" in ln
    )
    hid_str = next(tok for tok in line.split() if tok.isdigit())
    hid = int(hid_str)

    r_hyp = runner.invoke(main, [
        "--config", str(cfg_path),
        "hypothesis", "update", hid_str,
        "--status", "paused",
        "--reason", "Bundle E full-happy-path §5",
    ])
    assert r_hyp.exit_code == 0, r_hyp.output
    assert "paused" in r_hyp.output

    conn = connect(db_path)
    try:
        history = list_history_for_hypothesis(conn, hid)
        assert len(history) == 2, (
            f"expected seed (closed) + new (open) history rows; got {len(history)}"
        )
        seed_row, new_row = history
        assert seed_row.status == "active"
        assert seed_row.effective_to is not None
        assert new_row.status == "paused"
        assert new_row.effective_to is None
        assert new_row.change_reason == "Bundle E full-happy-path §5"
        reg = conn.execute(
            "SELECT status, status_change_reason FROM hypothesis_registry "
            "WHERE id = ?", (hid,),
        ).fetchone()
        assert reg == ("paused", "Bundle E full-happy-path §5")
    finally:
        conn.close()

    # =========================================================================
    # §6: sector tamper attempt via web POST /trades/entry
    # (mirrors tests/integration/test_phase9_end_to_end.py:502 Bundle D E2E).
    # =========================================================================
    session_iso = action_session_for_run(_dt.now()).isoformat()
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO watchlist (ticker, added_date, "
                "last_qualified_date, status, qualification_count, "
                "not_qualified_streak, last_data_asof_date, "
                "entry_target, last_close) VALUES "
                "('TAMP', '2026-04-01', ?, 'watch', 1, 0, ?, 11.0, 10.0)",
                (session_iso, session_iso),
            )
            cur = conn.execute(
                "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
                "action_session_date, finviz_csv_path, "
                "tickers_evaluated, aplus_count, watch_count, "
                "skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0)",
                (f"{session_iso}T08:00:00", session_iso, session_iso),
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO pipeline_runs (started_ts, finished_ts, "
                "trigger, data_asof_date, action_session_date, state, "
                "lease_token, evaluation_run_id) "
                "VALUES (?, ?, 'manual', ?, ?, 'complete', "
                "'tok-e0', ?)",
                (
                    f"{session_iso}T08:00:00",
                    f"{session_iso}T09:00:00",
                    session_iso,
                    session_iso,
                    eval_id,
                ),
            )
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, "
                "bucket, close, pivot, initial_stop, adr_pct, "
                "tight_streak, pullback_pct, prior_trend_pct, "
                "rs_rank, rs_return_12w_vs_spy, rs_method, "
                "pattern_tag, notes, sector, industry) "
                "VALUES (?, 'TAMP', 'watch', 10.0, 10.0, 9.5, 2.0, "
                "5, NULL, NULL, NULL, NULL, 'fallback_spy', NULL, "
                "NULL, 'Healthcare', 'Biotechnology')",
                (eval_id,),
            )
    finally:
        conn.close()

    # PriceCache shims so the entry-form code path sees a live price.
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=10.5, asof=_dt.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cfg = load_config(cfg_path)
    app = create_app(cfg, cfg_path)
    payload = full_phase7_entry_payload(
        ticker="TAMP",
        entry_date="2026-04-26",
        entry_price="10.0",
        shares="1",
        initial_stop="9.0",
        rationale="aplus-setup",
        notes="",
    )
    payload["sector"] = "Technology"  # tampered (cached candidate is Healthcare)
    payload["industry"] = "Biotechnology"
    payload["sector_industry_evaluation_run_id"] = str(eval_id)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/trades/entry", data=payload,
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 400, (
        f"Expected 400 (sector tamper rejection), got {resp.status_code}. "
        f"Body[:400]: {resp.text[:400]!r}"
    )

    conn = connect(db_path)
    try:
        # Entry transaction rolled back ⇒ no TAMP trade.
        tamp_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
        assert tamp_count == 0
        # Audit run + sector_tamper discrepancy committed in separate tx.
        audit_run = conn.execute(
            "SELECT run_id, source, state FROM reconciliation_runs "
            "WHERE source = 'system_audit' "
            "ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        assert audit_run is not None, "system_audit run must persist"
        assert audit_run[2] == "completed"
        tamper_disc = conn.execute(
            "SELECT discrepancy_id, ticker, field_name, "
            "material_to_review, resolution "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
        assert len(tamper_disc) == 1, tamper_disc
        tamp_did, tamp_ticker, tamp_field, tamp_material, tamp_resolution = (
            tamper_disc[0]
        )
        assert tamp_ticker == "TAMP"
        assert tamp_field == "sector"
        # sector_tamper is V1 advisory (material=0); MUST NOT surface in §7.
        assert tamp_material == 0
        assert tamp_resolution == "unresolved"
    finally:
        conn.close()

    # =========================================================================
    # §7: final attention surface.
    # Pre-resolve active-trade material count = 5 (verified at §2).
    # §3 resolved 1 ⇒ 4 remain.
    # §6 sector_tamper (material=0) MUST NOT appear.
    # =========================================================================
    conn = connect(db_path)
    try:
        attn = recon_repo.list_unresolved_material_for_active_trades(conn)
        # Discriminating arithmetic: active_count_pre - 1 (resolved in §3).
        assert len(attn) == active_count_pre - 1, (
            f"expected {active_count_pre - 1} attention rows "
            f"(pre={active_count_pre} minus 1 resolved in §3); got {len(attn)}: "
            f"{[(d.discrepancy_id, d.discrepancy_type, d.trade_id) for d in attn]}"
        )
        # The §6 sector_tamper row is material=0 ⇒ must not appear.
        assert all(d.discrepancy_type != "sector_tamper" for d in attn), (
            "sector_tamper (material=0) leaked into the active-trade attention "
            "surface"
        )
        # The §3-resolved id must not appear.
        assert all(d.discrepancy_id != target_did for d in attn), (
            f"§3-resolved discrepancy_id={target_did} still surfacing in "
            f"attention list"
        )
        # All surviving rows are still material=1 + have a trade_id.
        for d in attn:
            assert d.material_to_review == 1
            assert d.trade_id in {tid_abc, tid_def}
    finally:
        conn.close()
