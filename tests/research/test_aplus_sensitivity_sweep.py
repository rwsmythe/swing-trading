"""T-T4.SB.1 §B.1 Sub-task 1B — sensitivity-sweep machinery tests.

Inline fixture planters seed an in-memory ``evaluation_runs`` /
``candidates`` / ``candidate_criteria`` schema matching
``swing/data/migrations/0001_phase1_initial.sql``. Per Expansion #4 + the
synthetic-fixture-vs-production-emitter shape drift gotcha, every column
referenced in the SQL skeleton is verified against the migration file.
"""
from __future__ import annotations

import sqlite3

from research.harness.aplus_sensitivity.sweep import (
    SweepResult,
    run_sensitivity_sweep,
)
from research.harness.aplus_sensitivity.variables import (
    SweepVariable,
    enumerate_variables,
)
from swing.config import Config

# ---------------------------------------------------------------------------
# Inline fixture helpers (kept here -- not in conftest -- because they are
# small + only used in this module; mirror the style of
# tests/integration/test_*.py helpers).
# ---------------------------------------------------------------------------

_SCHEMA_DDL = (
    """
    CREATE TABLE evaluation_runs (
      id INTEGER PRIMARY KEY,
      run_ts TEXT NOT NULL,
      data_asof_date TEXT NOT NULL,
      action_session_date TEXT NOT NULL,
      finviz_csv_path TEXT,
      tickers_evaluated INTEGER NOT NULL,
      aplus_count INTEGER NOT NULL,
      watch_count INTEGER NOT NULL,
      skip_count INTEGER NOT NULL,
      excluded_count INTEGER NOT NULL,
      error_count INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE candidates (
      id INTEGER PRIMARY KEY,
      evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
      ticker TEXT NOT NULL,
      bucket TEXT NOT NULL CHECK (bucket IN ('aplus','watch','skip','error','excluded')),
      close REAL,
      pivot REAL,
      initial_stop REAL,
      adr_pct REAL,
      tight_streak INTEGER,
      pullback_pct REAL,
      prior_trend_pct REAL,
      rs_rank INTEGER,
      rs_return_12w_vs_spy REAL,
      rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable')),
      pattern_tag TEXT,
      notes TEXT,
      UNIQUE(evaluation_run_id, ticker)
    );
    """,
    """
    CREATE TABLE candidate_criteria (
      candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
      criterion_name TEXT NOT NULL,
      layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
      result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
      value TEXT,
      rule TEXT,
      PRIMARY KEY (candidate_id, criterion_name)
    );
    """,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    for ddl in _SCHEMA_DDL:
        conn.execute(ddl)


def _insert_eval_run(conn: sqlite3.Connection, run_id: int) -> int:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (?, '2026-05-22T00:00:00Z', '2026-05-21', '2026-05-22',"
        " 0, 0, 0, 0, 0, 0)",
        (run_id,),
    )
    return run_id


def _insert_candidate_with_criteria(
    conn: sqlite3.Connection,
    *,
    eval_run_id: int,
    ticker: str,
    bucket: str,
    tt_pass: int = 7,
    tt_fail_names: tuple[str, ...] = (),
    vcp_fail_count: int = 0,
    risk_pass: bool = True,
) -> int:
    """Plant one ``candidates`` row + paired ``candidate_criteria`` rows.

    Trend-template layer emits 8 rows total (TT1..TT8); ``tt_pass`` named pass,
    ``tt_fail_names`` named fails (must be among TT1..TT8). Remaining slots fill
    in as ``pass`` until 8 rows. VCP layer emits 8 rows: ``vcp_fail_count`` fails,
    remaining pass. Risk layer emits 1 row (pass / fail).
    """
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)"
        " VALUES (?, ?, ?, 'universe')",
        (eval_run_id, ticker, bucket),
    )
    candidate_id = cur.lastrowid
    # TT layer -- 8 criteria.
    tt_names = ["TT1", "TT2", "TT3", "TT4", "TT5", "TT6", "TT7", "TT8_rs_rank"]
    fail_set = set(tt_fail_names)
    pass_count = 0
    for name in tt_names:
        if name in fail_set:
            result = "fail"
        elif pass_count < tt_pass:
            result = "pass"
            pass_count += 1
        else:
            result = "fail"
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer,"
            " result, value, rule) VALUES (?, ?, 'trend_template', ?, NULL, NULL)",
            (candidate_id, name, result),
        )
    # VCP layer -- 8 criteria.
    vcp_names = [
        "vcp_prior_trend",
        "vcp_adr",
        "vcp_pullback",
        "vcp_proximity",
        "vcp_tightness_days",
        "vcp_tightness_range",
        "vcp_orderliness_bar",
        "vcp_orderliness_cv",
    ]
    for i, name in enumerate(vcp_names):
        result = "fail" if i < vcp_fail_count else "pass"
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer,"
            " result, value, rule) VALUES (?, ?, 'vcp', ?, NULL, NULL)",
            (candidate_id, name, result),
        )
    # Risk layer -- 1 criterion.
    risk_result = "pass" if risk_pass else "fail"
    conn.execute(
        "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer,"
        " result, value, rule) VALUES (?, ?, 'risk', ?, NULL, NULL)",
        (candidate_id, "risk_max_pct", risk_result),
    )
    return candidate_id


def _plant_minimal_eval_run_fixture(conn: sqlite3.Connection) -> None:
    """Plant 1 eval_run with 5 candidates: 1 aplus, 2 watch, 2 skip.

    Layout per the bucket_for semantics used by ``_bucket_for_substituted``:
      - aplus: TT 7-pass + 1 TT8 fail (allowed_miss); 0 vcp fails; risk pass
      - watch x2: TT 8-pass; 1 or 2 vcp fails; risk pass
      - skip x2: 1 with risk fail; 1 with TT < min_passes
    """
    _create_schema(conn)
    run_id = _insert_eval_run(conn, 1)
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="APLUS1", bucket="aplus",
        tt_pass=7, tt_fail_names=("TT8_rs_rank",), vcp_fail_count=0, risk_pass=True,
    )
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="WATCH1", bucket="watch",
        tt_pass=8, vcp_fail_count=1, risk_pass=True,
    )
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="WATCH2", bucket="watch",
        tt_pass=8, vcp_fail_count=2, risk_pass=True,
    )
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="SKIP1", bucket="skip",
        tt_pass=8, vcp_fail_count=0, risk_pass=False,
    )
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="SKIP2", bucket="skip",
        tt_pass=4, tt_fail_names=("TT1", "TT2", "TT3", "TT4"),
        vcp_fail_count=0, risk_pass=True,
    )
    conn.commit()


def _plant_eval_runs_with_known_distribution(
    conn: sqlite3.Connection, *, aplus: int, watch: int, skip: int,
) -> None:
    """Plant 1 eval_run with N aplus + M watch + K skip candidates."""
    _create_schema(conn)
    run_id = _insert_eval_run(conn, 1)
    for i in range(aplus):
        _insert_candidate_with_criteria(
            conn, eval_run_id=run_id, ticker=f"A{i}", bucket="aplus",
            tt_pass=7, tt_fail_names=("TT8_rs_rank",),
            vcp_fail_count=0, risk_pass=True,
        )
    for i in range(watch):
        _insert_candidate_with_criteria(
            conn, eval_run_id=run_id, ticker=f"W{i}", bucket="watch",
            tt_pass=8, vcp_fail_count=1, risk_pass=True,
        )
    for i in range(skip):
        _insert_candidate_with_criteria(
            conn, eval_run_id=run_id, ticker=f"S{i}", bucket="skip",
            tt_pass=8, vcp_fail_count=0, risk_pass=False,
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sweep_recomputes_buckets_per_variable(tmp_path):
    db_path = tmp_path / "sweep.db"
    conn = sqlite3.connect(str(db_path))
    _plant_minimal_eval_run_fixture(conn)
    var = SweepVariable(
        name="trend_template.min_passes",
        kind="gate",
        current_value=7,
        sweep_points=(5, 6, 7, 8, 9),
    )
    result = run_sensitivity_sweep(
        conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    assert isinstance(result, SweepResult)
    entries = [e for e in result.entries if e.variable_name == "trend_template.min_passes"]
    assert len(entries) == 5
    # The current-value entry MUST reproduce a 5-candidate distribution.
    current = next(e for e in entries if e.sweep_point == 7)
    assert current.aplus_count + current.watch_count + current.skip_count == 5


def test_sweep_at_current_value_matches_persisted_distribution(tmp_path):
    """The sweep point matching current_value MUST reproduce the persisted
    bucket counts exactly (no substitution applied at current_value)."""
    conn = sqlite3.connect(":memory:")
    _plant_eval_runs_with_known_distribution(conn, aplus=2, watch=3, skip=4)
    var = SweepVariable(
        name="vcp.watch_max_fails",
        kind="gate",
        current_value=2,
        sweep_points=(0, 1, 2, 3, 4),
    )
    result = run_sensitivity_sweep(
        conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    current_entry = next(
        e for e in result.entries
        if e.variable_name == "vcp.watch_max_fails" and e.sweep_point == 2
    )
    assert current_entry.aplus_count == 2
    assert current_entry.watch_count == 3
    assert current_entry.skip_count == 4
    assert current_entry.delta_aplus == 0
    assert current_entry.delta_watch == 0


def test_threshold_variables_have_zero_deltas_in_sweep_result():
    """Invariant: threshold-variable sweep entries have delta_aplus ==
    delta_watch == 0 (parity-preserving V1 behavior). Gate variables
    may have non-zero deltas."""
    conn = sqlite3.connect(":memory:")
    _plant_eval_runs_with_known_distribution(conn, aplus=1, watch=2, skip=4)
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    result = run_sensitivity_sweep(
        conn, variables=variables, cfg=cfg, eval_runs_window=10,
    )
    for entry in result.entries:
        var = next(v for v in variables if v.name == entry.variable_name)
        if var.kind.startswith("threshold_"):
            assert entry.delta_aplus == 0, f"{entry.variable_name}@{entry.sweep_point}"
            assert entry.delta_watch == 0, f"{entry.variable_name}@{entry.sweep_point}"


def test_sweep_empty_db_returns_empty_result(tmp_path):
    """Edge case: empty eval_runs table -> empty result, no exception."""
    conn = sqlite3.connect(":memory:")
    _create_schema(conn)
    result = run_sensitivity_sweep(
        conn, variables=(), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    assert result.total_candidates == 0
    assert result.entries == ()


def test_run_harness_emits_csv_and_markdown_to_output_dir(tmp_path):
    """End-to-end smoke test for run.py harness orchestrator."""
    from research.harness.aplus_sensitivity.run import run_harness

    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    _plant_eval_runs_with_known_distribution(conn, aplus=1, watch=2, skip=2)
    conn.close()
    out_dir = tmp_path / "out"
    md_path, csv_path = run_harness(
        db_path=db_path, eval_runs=10, output_dir=out_dir,
    )
    assert md_path.exists()
    assert csv_path.exists()
    # Markdown is non-empty + ASCII-safe (cp1252-encodable).
    md_path.read_text(encoding="utf-8").encode("cp1252")


def test_sweep_gate_variable_redistributes_buckets_at_non_current_points():
    """Discriminating test: a sweep point distinct from current_value produces
    a different bucket distribution for gate variables.

    Plant a divergent fixture where 1 of the watch candidates has 3 vcp fails
    (would be reclassified as aplus at watch_max_fails=3 because vcp_fails<=3,
    or stays skip at watch_max_fails=0).
    """
    conn = sqlite3.connect(":memory:")
    _create_schema(conn)
    run_id = _insert_eval_run(conn, 1)
    # 2 aplus, 2 watch (with vcp_fail_count=2), 1 skip
    for i in range(2):
        _insert_candidate_with_criteria(
            conn, eval_run_id=run_id, ticker=f"A{i}", bucket="aplus",
            tt_pass=7, tt_fail_names=("TT8_rs_rank",), vcp_fail_count=0, risk_pass=True,
        )
    for i in range(2):
        _insert_candidate_with_criteria(
            conn, eval_run_id=run_id, ticker=f"W{i}", bucket="watch",
            tt_pass=7, tt_fail_names=("TT8_rs_rank",), vcp_fail_count=2, risk_pass=True,
        )
    _insert_candidate_with_criteria(
        conn, eval_run_id=run_id, ticker="S0", bucket="skip",
        tt_pass=8, vcp_fail_count=0, risk_pass=False,
    )
    conn.commit()

    var = SweepVariable(
        name="vcp.watch_max_fails",
        kind="gate",
        current_value=2,
        sweep_points=(0, 1, 2, 3, 4),
    )
    result = run_sensitivity_sweep(
        conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    # At watch_max_fails=0 -- 2 watch candidates (vcp_fails=2) drop to skip.
    at_0 = next(e for e in result.entries if e.sweep_point == 0)
    assert at_0.watch_count == 0
    assert at_0.skip_count == 3
    # At watch_max_fails=2 (current) -- 2 watch present.
    at_2 = next(e for e in result.entries if e.sweep_point == 2)
    assert at_2.watch_count == 2
    # Delta vs current at sweep_point=0: watch lost 2.
    assert at_0.delta_watch == -2
