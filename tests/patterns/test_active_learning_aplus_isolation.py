from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.patterns.active_learning import prioritize_candidates
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def _pe_geom(conn, run_id, ticker, geom):
    # _pe variant pinning geometric_score so _classify_priority fires
    # (criterion 1 borderline_geometric: abs(geom-0.5) < BORDERLINE band).
    return conn.execute(
        "INSERT INTO pattern_evaluations (pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, geometric_score_json, "
        "composite_score, structural_evidence_json, feature_distribution_log_json, "
        "window_start_date, window_end_date, created_at) VALUES "
        "(?,?, 'vcp', 'v1', ?, '{}', 0.7, '{}', '{}', '2026-05-01','2026-05-20',"
        "'2026-05-20T18:00:00')", (run_id, ticker, geom)).lastrowid


def test_queue_excludes_watch_origin(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    # geometric_score=0.5 -> classifiable (borderline_geometric), so the queue
    # is NON-empty post-isolation (Codex R1 MINOR #2: avoid the vacuous pass).
    _cand(conn, 1, "AAA", "aplus"); _pe_geom(conn, 1, "AAA", 0.5)
    for i in range(30):  # watch flood, also classifiable (geom 0.5)
        _cand(conn, 1, f"W{i}", "watch"); _pe_geom(conn, 1, f"W{i}", 0.5)
        _pde(conn, 1, f"W{i}", "watch")
    conn.commit()
    out = prioritize_candidates(conn, top_k=50)
    tickers = {c.ticker for c in out}
    # Post-isolation: queue == {AAA} (the watch flood is filtered at the SQL
    # source). Pre-isolation: up to 31 rows including the watch flood. The
    # `"AAA" in tickers` assert makes this NON-vacuous (the queue is non-empty).
    assert "AAA" in tickers
    assert tickers == {"AAA"}
