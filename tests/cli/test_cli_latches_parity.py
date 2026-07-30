"""`swing latches parity` -- the monthly execution-parity read (Task 9).

READ-ONLY: no Schwab call, no row written. The command is a RENDERER over the
pure classifier, so the number RD reads and the number the classifier tests
assert come from the same code.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.latches.constants import R_BUCKETS

NOW = datetime(2026, 7, 25, 12, 0)


@pytest.fixture
def seeded_db(tmp_path):
    """(cfg, cfg_path) on a fresh migrated DB.

    Local rather than imported: `tests/web/conftest.py` owns the web copy and
    this suite is not under `tests/web/`.
    """
    from swing.config import load
    from swing.data.db import ensure_schema
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, "
            "0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
        cid = int(cur.lastrowid)
    conn.close()
    return cid


def _run(cfg_path, *args):
    return CliRunner().invoke(
        main, ["--config", str(cfg_path), "latches", "parity", *args])


def test_the_report_prints_both_away_rates_LABELLED_on_adjacent_lines(seeded_db):
    """RD RULING 2. Stage-3 auto-place must not be able to take the decision
    quietly on the LARGER number, so a report printing only one rate, or
    printing them unlabelled, FAILS. Testimony is not telemetry: a self-report
    about one's own diligence is systematically biased toward the more
    comfortable explanation, and this is the number he least wants softenable.
    """
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "OBJECTIVE (primary)" in r.output
    assert "ATTESTED (upper bound)" in r.output
    lines = r.output.splitlines()
    obj = next(i for i, ln in enumerate(lines) if "OBJECTIVE (primary)" in ln)
    att = next(i for i, ln in enumerate(lines) if "ATTESTED (upper bound)" in ln)
    assert att == obj + 1


def test_both_rates_carry_the_telemetry_verdict_on_their_OWN_line(seeded_db):
    """The away rate CANNOT be obtained without its verdict. There is no
    function anywhere returning a bare float away rate, and the report keeps
    that property visible rather than merely structural."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    for line in r.output.splitlines():
        if "OBJECTIVE (primary)" in line or "ATTESTED (upper bound)" in line:
            assert "telemetry" in line.lower()


def test_a_broken_beacon_WITHHOLDS_both_rates_and_prints_the_counters(seeded_db):
    """The gate applies to the PAIR: an unreliable beacon corrupts the objective
    numerator directly and the bound derived from it consequently."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    import swing.cli_latches as mod
    from swing.latches.classification import TelemetryHealth
    real = mod.assess_telemetry_health
    try:
        mod.assess_telemetry_health = lambda **k: TelemetryHealth(
            verdict="broken", covered_sessions=1, uncovered_sessions=9)
        r = _run(cfg_path)
    finally:
        mod.assess_telemetry_health = real
    assert r.exit_code == 0, r.output
    assert r.output.count("WITHHELD") >= 2
    assert "covered=1" in r.output and "uncovered=9" in r.output


def test_pending_r_is_its_own_visible_line_and_is_not_in_any_denominator(
        seeded_db):
    """RD RULING 1. A latch that has not terminated is NOT AN OBSERVATION YET --
    there is no outcome, he can still act, and its value moves as the window
    runs. It is REPORTED so the reader sees the pipeline rather than a silently
    smaller corpus, and excluded from every denominator."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert "pending_r:" in r.output
    assert "REPORTED, NEVER SCORED" in r.output
    # FTRE is live and pre-telemetry, so nothing is classifiable yet: the rates
    # must be withheld rather than computed over a denominator that borrowed it.
    assert "1 fires" in r.output or "1 fires" in r.output.replace("  ", " ")


def test_the_three_decision_evidence_kinds_are_printed_and_SUM_to_decision_r(
        seeded_db):
    """The governing principle: the SUM may be reported, the DISTINCTION may not
    be erased."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    out = r.output
    for name in ("decision_r_logged", "decision_r_attested",
                 "decision_r_inferred", "decision_r:"):
        assert name in out

    def _value(label):
        line = next(ln for ln in out.splitlines() if ln.strip().startswith(label))
        return int(line.split(":")[1].strip().split()[0])

    assert (_value("decision_r_logged") + _value("decision_r_attested")
            + _value("decision_r_inferred")) == _value("decision_r:")


def test_every_bucket_in_the_roster_is_printed(seeded_db):
    """ITERATED from `R_BUCKETS`, never listed -- so a sixth bucket added to the
    resolver cannot be silently omitted from the report."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    for bucket in R_BUCKETS:
        assert f"{bucket}:" in r.output


def test_the_exclusion_counts_are_named_individually(seeded_db):
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    for name in ("pre_telemetry", "never_actionable", "telemetry_unhealthy"):
        assert name in r.output


def test_the_agreement_rate_and_the_per_field_delta_totals_are_printed(
        seeded_db):
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert "AGREEMENT" in r.output
    assert "PER-FIELD DELTA TOTALS" in r.output
    for field in ("order_type_differs", "duration_differs",
                  "limit_price_differs", "quantity_differs"):
        assert field in r.output


def test_the_since_cutoff_filters_on_recorded_ts_and_NOT_on_the_mandate_session(
        seeded_db):
    """THE R9 MAJOR 2 DISCRIMINATOR. A validity row RECORDED in month N about a
    month-N-1 render belongs to month N. Filtering on `action_session_date`
    would misbucket it -- and would drop a post-month-end CORRECTION out of the
    current read entirely. Both are silent misbucketings of a measurement read
    once a month."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        # A JULY mandate, ANSWERED in August. A session-axis filter drops it.
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id) VALUES "
            "(?, 121, 'FTRE', '2026-07-20', 'k1', '2026-07-27', "
            "'2026-08-04T09:00:00', 'latch_panel', 'cancel', '1001')", (cid,))
    conn.close()
    from_august = _run(cfg_path, "--since", "2026-08-01")
    assert "order 1001" in from_august.output
    from_september = _run(cfg_path, "--since", "2026-09-01")
    assert "order 1001" not in from_september.output


def test_the_origin_field_is_named_inferred_origin_and_prints_its_basis(
        seeded_db):
    """A report printing a bare `origin` FAILS. A params match is a HEURISTIC --
    two identical orders are indistinguishable by params -- so presenting
    inference as identity would be an overclaim, and the basis is printed beside
    the value so the reader can see which kind of claim it is."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id) VALUES "
            "(?, 121, 'FTRE', '2026-07-20', 'k2', '2026-07-27', "
            "'2026-07-27T09:00:00', 'latch_panel', 'cancel', '1002')", (cid,))
    conn.close()
    r = _run(cfg_path)
    assert "inferred_origin=" in r.output
    assert "INFERRED" in r.output or "EXACT" in r.output
    # The bare word must not appear as the FIELD name.
    assert " origin=" not in r.output


def test_the_report_writes_nothing_and_makes_no_schwab_call(seeded_db):
    """READ-ONLY, asserted rather than asserted-in-a-docstring."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    conn = connect(cfg.paths.db_path)
    before = (
        conn.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM latch_order_intents").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM latch_view_events").fetchone()[0],
    )
    conn.close()
    assert _run(cfg_path).exit_code == 0
    conn = connect(cfg.paths.db_path)
    after = (
        conn.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM latch_order_intents").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM latch_view_events").fetchone()[0],
    )
    conn.close()
    assert before == after


@pytest.mark.skipif(sys.platform != "win32", reason="the cp1252 gotcha is Windows")
def test_the_output_survives_a_real_powershell_stdout(seeded_db, tmp_path):
    """THE cp1252 GOTCHA, and `capsys` CANNOT SEE IT: pytest's capture bypasses
    the OS encoder, so every byte test above passes against code that crashes in
    production the first time a non-ASCII glyph reaches PowerShell's stdout.
    Only a real subprocess through the real console encoder discriminates."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"{sys.executable} -m swing.cli --config '{cfg_path}' latches parity"],
        capture_output=True, text=True, cwd=str(cfg_path.parent.parent),
        env=None, timeout=180)
    assert "UnicodeEncodeError" not in (proc.stderr or "")


# --- Codex exec R1 adjudications ------------------------------------------
def test_a_ledger_row_with_no_derivable_latch_is_LABELLED_not_dropped(seeded_db):
    """CODEX EXEC R1 MAJOR 2. Classification is a property of a LATCH, so the
    corpus is latch-driven -- which means an intent whose latch the derivation
    does not produce would VANISH from a report that claims to read the ledger
    window. It should be impossible (candidate_id is NOT NULL ON DELETE
    RESTRICT, candidates is append-only, and every intent was written against an
    already-derived latch), and THAT is why an unlabelled drop would be
    dangerous: nobody would ever look. So the count is rendered."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        # An A+ fire dated BEYOND the derivation horizon, so it produces NO
        # latch at `now` while still satisfying the identity-coherence trigger
        # (which requires `bucket = 'aplus'` and a matching run / ticker /
        # detection date). Planted via raw SQL: the route could not create it,
        # and that is the point -- the guard exists for the shape nobody
        # predicted, so its test must reach one the writers cannot produce.
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(777, '2099-01-04T17:30:05', '2099-01-04', '2099-01-05', 1, 1, 0, "
            "0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(777, 'AMN', 'aplus', 12.0, 13.0, 11.0, 'universe')")
        orphan = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id) VALUES "
            "(?, 777, 'AMN', '2099-01-05', 'orphan', '2099-01-05', "
            "'2026-07-27T09:00:00', 'latch_panel', 'cancel', '9001')",
            (orphan,))
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "LEDGER ROWS WITH NO DERIVABLE LATCH" in r.output
    assert "in NO bucket and NO denominator" in r.output


def test_the_health_window_and_the_classified_corpus_are_the_SAME_latches(
        seeded_db):
    """CODEX EXEC R1 MAJOR 1, adjudicated. The finding assumed the telemetry
    health window is built over a WIDER set than the one being classified, so a
    stale terminal latch could withhold a verdict about a live one. Both are
    built from the SAME list, and this pins it rather than leaving the claim to
    a code reading -- if they ever diverge, health would start describing a
    corpus nobody is scoring."""
    import swing.cli_latches as mod
    cfg, cfg_path = seeded_db
    _seed(cfg)
    seen = {}
    real = mod.assess_telemetry_health

    def _capture(*, sessions, latches, **kw):
        seen["health"] = [x.identity.candidate_id for x in latches]
        return real(sessions=sessions, latches=latches, **kw)

    real_classify = mod.classify_latch
    classified: list[int] = []

    def _capture_classify(**kw):
        classified.append(kw["latch"].identity.candidate_id)
        return real_classify(**kw)

    mod.assess_telemetry_health = _capture
    mod.classify_latch = _capture_classify
    try:
        assert _run(cfg_path).exit_code == 0
    finally:
        mod.assess_telemetry_health = real
        mod.classify_latch = real_classify
    assert seen["health"] == classified
