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


def test_the_CLI_health_window_ENUMERATES_the_silent_sessions(
        seeded_db, monkeypatch):
    """CODEX EXEC R2 MAJOR 4, at the CLI. The report's window was built from
    `{view dates} | {latch anchors}` -- only sessions that ALREADY have a row --
    so `assess_telemetry_health` could never SEE a dark session and a mostly
    dark month with one beacon hit would verdict `ok`, letting `away_unseen`
    into the away rate rather than withholding it.

    THE CLOCK IS FROZEN TO A SATURDAY, and that is the second half of the test.
    The walk steps with `session_offset`, which REFUSES a non-session, so a
    window bounded by a raw `now.date()` CRASHES the command outright every
    weekend and market holiday -- and a monthly report is exactly the thing run
    at a weekend. Bounding by the derivation's `horizon_session` is a session by
    construction, and it is the same bound the panel passes.
    """
    import swing.cli_latches as mod
    from swing.evaluation.dates import is_trading_session
    from swing.latches.classification import telemetry_window_sessions
    cfg, cfg_path = seeded_db
    _seed(cfg)
    saturday = datetime(2026, 8, 8, 12, 0)
    assert not is_trading_session(saturday.date())

    class _Clock:
        @staticmethod
        def now():
            return saturday

    monkeypatch.setattr(mod, "datetime", _Clock)
    seen = {}
    real = mod.assess_telemetry_health

    def _capture(*, sessions, latches, **kw):
        seen["sessions"] = list(sessions)
        seen["latches"] = list(latches)
        return real(sessions=sessions, latches=latches, **kw)

    monkeypatch.setattr(mod, "assess_telemetry_health", _capture)
    result = _run(cfg_path)
    assert result.exit_code == 0, result.output

    sessions = seen["sessions"]
    # A contiguous NYSE WALK, not the anchors it would collapse to pre-fix.
    assert sessions == telemetry_window_sessions(seen["latches"], max(sessions))
    assert len(sessions) > len({x.anchor for x in seen["latches"]})
    assert all(is_trading_session(s) for s in sessions)


def _seed_place(cfg, cid, *, key, recorded_ts, intent_id=None):
    """A `place` row carrying the framework side the schema requires of one."""
    conn = connect(cfg.paths.db_path)
    with conn:
        cur = conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, framework_order_type, "
            "framework_duration, framework_limit_price, framework_quantity, "
            "derivation_zone_cap_pct, derivation_sizing_equity, "
            "derivation_max_risk_pct, derivation_position_pct_cap, "
            "derivation_sizing_basis, derivation_regime_close, "
            "derivation_regime_close_session, derivation_real_equity, "
            "derivation_equity_floor) "
            "VALUES (?, 121, 'FTRE', '2026-07-20', ?, '2026-07-27', ?, "
            "'latch_panel', 'place', 'LIMIT', 'GOOD_TILL_CANCEL', 18.89, 9, "
            "3.0, 7500.0, 1.25, 25.0, 'limit_price', 19.20, '2026-07-24', 1300.0, "
            "7500.0)",
            (cid, key, recorded_ts))
        out = int(cur.lastrowid)
    conn.close()
    return out


def test_a_windowed_read_classifies_from_the_latchs_WHOLE_intent_history(
        seeded_db):
    """CODEX EXEC R3 MAJOR 1. `--since` selects which LEDGER ROWS the report
    covers; it must NOT truncate the evidence the CLASSIFIER reasons from.

    The arc's own worked case is a JULY mandate answered in AUGUST -- so a
    August-onward read sees the validity row but, under a truncated intent set,
    NOT its parent `place`. `governing_intent(..., 'place')` then returns None,
    rung 1 never fires, and a latch the operator demonstrably ACCEPTED is
    reclassified as a lapse or an away: the instrument losing evidence it holds
    and scoring the loss against its subject.

    Classification is a property of a LATCH (the round-1 ruling), and a latch's
    disposition is not a function of the calendar window someone asked about.
    """
    from swing.cli_latches import _observations
    from swing.config_overrides import apply_overrides
    cfg, _ = seeded_db
    cid = _seed(cfg)
    _seed_place(cfg, cid, key="p-july", recorded_ts="2026-07-27T09:00:00")
    conn = connect(cfg.paths.db_path)
    try:
        obs, _health, intents, _unattached, _places = _observations(
            conn, apply_overrides(cfg), since_ts="2026-08-01T00:00:00",
            now=NOW)
    finally:
        conn.close()
    # The WINDOW is still honoured: the July row is not a row of this month.
    assert intents == []
    # ...but the DISPOSITION still knows the operator placed the order.
    assert [o.disposition.disposition for o in obs] == ["accepted"]


def test_the_window_still_EXCLUDES_the_out_of_window_row_from_the_ledger_read(
        seeded_db):
    """The pair to the above, and the reason the fix is two reads rather than
    one widened read. If classifying from full history also widened the reported
    LEDGER WINDOW, `--since` would stop meaning anything and a month's report
    would silently restate every prior month."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id) VALUES "
            "(?, 121, 'FTRE', '2026-07-20', 'k-july', '2026-07-27', "
            "'2026-07-27T09:00:00', 'latch_panel', 'cancel', '1001')", (cid,))
    conn.close()
    assert "order 1001" not in _run(cfg_path, "--since", "2026-09-01").output


def test_a_non_canonical_since_is_REFUSED_not_silently_mis_windowed(seeded_db):
    """CODEX EXEC R3 MAJOR 2. `recorded_ts` is TEXT and the window is a
    LEXICOGRAPHIC `>=`, so an unpadded `2026-8-1` does not merely look untidy:
    the string `2026-8-1T00:00:00` sorts ABOVE every `2026-0X` and `2026-1X`
    stamp, so the cutoff silently excludes almost the whole year and the monthly
    measurement is computed over the wrong window with no visible sign.

    A measurement window that can be corrupted by a plausible typo must fail
    CLOSED. The message names the expected form so the recovery is obvious.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    _seed_place(cfg, cid, key="p1", recorded_ts="2026-07-27T09:00:00")
    bad = _run(cfg_path, "--since", "2026-8-1")
    assert bad.exit_code != 0
    assert "YYYY-MM-DD" in bad.output
    # ...and the canonical spelling of the SAME date is accepted.
    assert _run(cfg_path, "--since", "2026-08-01").exit_code == 0


def test_a_since_that_is_not_a_date_at_all_is_REFUSED(seeded_db):
    """The unconstrained-input half: `--since` is free text from a shell."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    for bad_value in ("last month", "2026-13-01", "20260801", ""):
        r = _run(cfg_path, "--since", bad_value)
        assert r.exit_code != 0, bad_value
        assert "YYYY-MM-DD" in r.output, bad_value


def test_an_unattributed_R_bucket_prints_UNAVAILABLE_not_a_confident_zero(
        seeded_db):
    """CODEX EXEC R4 MAJOR 3. A SUM OVER NOTHING IS NOT A ZERO. No V1 emitter
    attributes an R to an observation, so every bucket summed to 0.0 and the
    report printed an authoritative `+0.00R` -- a confident measurement over no
    evidence at all, which is exactly the fabricated all-clear this arc exists
    to refuse. Where nothing was attributed the report must SAY so."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "R UNAVAILABLE" in r.output
    assert "+0.00R" not in r.output


def test_an_ATTRIBUTED_R_still_prints_the_number_and_its_basis(seeded_db):
    """The pair. Without it, 'print UNAVAILABLE' is satisfied by a report that
    has stopped printing R at all -- and the R total is the figure the whole
    bucket partition exists to carry once 21-C attributes one."""
    from swing.latches.classification import (
        ParityObservation,
        compute_execution_parity,
    )
    cfg, _ = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        from swing.cli_latches import _observations
        from swing.config_overrides import apply_overrides
        obs, health, _i, _u, _p = _observations(
            conn, apply_overrides(cfg), since_ts="", now=NOW)
    finally:
        conn.close()
    assert obs, "the fixture must produce at least one observation"
    scored = [
        ParityObservation(
            disposition=o.disposition, framework=o.framework, actual=o.actual,
            r_multiple=1.5)
        for o in obs
    ]
    report = compute_execution_parity(scored, health=health)
    assert any(v > 0 for v in report.bucket_r_attributed.values())
    assert any(abs(v) > 0 for v in report.bucket_r.values())
    assert cid  # the seeded latch is the one carrying it


# ---------------------------------------------------------------------------
# RD RULING 4 (2026-07-30) -- THE ZERO-DATA STATE MUST BE DISTINGUISHABLE FROM
# THE GOOD STATE, ACROSS EVERY RATE AND EVERY CLASSIFICATION THIS LEDGER REPORTS
#
# Imposed as a CLASS rather than defect by defect, because the class is
# structural: every failure mode of a RECORDING instrument is SILENCE, and on
# this instrument silence reads as "he did fine". Absent data yields no lapse
# recorded, no mismatch flagged and no disagreement counted -- so an unlabelled
# zero is not a neutral default, it is a favourable verdict delivered by
# omission. It is RD's labelled-reduction rule generalised from ALARMS to RATES.
#
# Each test below asserts BOTH halves: the unmeasured label is PRESENT and the
# good-state reading is ABSENT. Asserting only the label would pass against a
# report that printed both.
# ---------------------------------------------------------------------------
def _lines_after(output: str, header: str, count: int) -> str:
    lines = output.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith(header))
    return "\n".join(lines[i:i + count])


def test_an_empty_agreement_DENOMINATOR_renders_NOT_YET_MEASURABLE(seeded_db):
    """The agreement rate is the arc's headline deliverable, and until a
    validity row exists its denominator is EMPTY. `n/a (0/0)` is a rendering of
    a number; NOT YET MEASURABLE is a statement about the measurement, and only
    the second one keeps a reader from filing 'no disagreements recorded' as
    'the framework and the operator agree'."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    block = _lines_after(r.output, "AGREEMENT", 4)
    assert "NOT YET MEASURABLE" in block
    assert "%" not in block, (
        "a percentage over an empty denominator is a measurement claim")
    assert "n/a" not in block


def test_a_POPULATED_agreement_denominator_still_prints_the_RATE(seeded_db):
    """The pair. Without it, 'print NOT YET MEASURABLE' is satisfied by a report
    that has stopped printing the agreement rate at all -- which would delete
    the deliverable rather than label its absence."""
    from swing.latches.classification import ExecutionParityReport

    report = ExecutionParityReport(
        bucket_counts={}, bucket_r={}, bucket_r_attributed={},
        disposition_counts={}, away=None, decision_r_logged=0,
        decision_r_attested=0, decision_r_inferred=0,
        agreement_numerator=3, agreement_denominator=4, validity_unknown=0,
        validity_failed=0, actual_side_unknown=0, delta_totals={},
        total_observations=4)
    from swing.cli_latches import _agreement_line
    line = _agreement_line(report)
    assert "75.0%" in line and "(3/4)" in line
    assert "NOT YET MEASURABLE" not in line


def test_a_report_over_ZERO_observations_says_so_before_any_histogram(
        seeded_db):
    """A histogram of zeros and a delta table of zeros both read as findings --
    'nothing wrong was found' -- when what happened is that nothing was
    examined."""
    cfg, cfg_path = seeded_db
    r = _run(cfg_path)          # NOT seeded: no latch, no observation at all
    assert r.exit_code == 0, r.output
    assert "NO OBSERVATIONS" in r.output
    assert "UNMEASURED, not clean" in r.output


def test_the_discipline_signal_with_no_terminal_observations_says_NO_OBSERVATIONS(
        seeded_db):
    """RD, verbatim: a discipline signal with no terminal observations renders
    'no observations', never 'clean'. The three evidence-kind sub-counts summing
    to zero is exactly the shape that reads as a clean record."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    block = _lines_after(r.output, "DECISION EVIDENCE KINDS", 8)
    assert "NO TERMINAL OBSERVATIONS" in block
    assert "NOT YET MEASURABLE, not clean" in block


def test_the_delta_totals_over_an_empty_denominator_are_LABELLED_unmeasured(
        seeded_db):
    """Five zeros under PER-FIELD DELTA TOTALS is the single most inviting
    misreading in the whole report: it looks like five checks that passed."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    block = _lines_after(r.output, "PER-FIELD DELTA TOTALS", 9)
    assert "NOT YET MEASURABLE" in block
    assert "no observation reached the delta" in block
    assert "these zeros are absences and NOT results" in block


def test_an_away_rate_with_no_classifiable_fire_is_NOT_YET_MEASURABLE_not_zero(
        seeded_db):
    """`0.0%` away over an empty corpus is the flattering reading of an
    instrument that has not measured anything yet -- and this is the number that
    would justify stage-3 auto-place. The verdict is `ok` here, so the label
    must distinguish 'the beacon is broken' from 'there is nothing to score'."""
    cfg, cfg_path = seeded_db
    # NOT seeded, deliberately: a latch on the books makes the telemetry window
    # non-empty and the verdict INDETERMINATE, which is the OTHER unmeasured
    # state. This case is the empty corpus under a HEALTHY beacon.
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    block = _lines_after(r.output, "AWAY RATE", 6)
    assert "telemetry OK" in block
    assert "NOT YET MEASURABLE" in block
    assert "0.0%" not in block
    assert "WITHHELD" not in block, (
        "nothing is being withheld here -- the corpus is empty, and conflating "
        "the two hides a broken beacon behind a quiet start-up state")


def test_a_BROKEN_beacon_still_says_WITHHELD_and_names_the_verdict(seeded_db):
    """The discriminating pair for the line above: an unreliable beacon and an
    empty corpus are DIFFERENT unmeasured states and the report may not print
    one for the other."""
    from swing.latches.classification import (
        AwayRateResult,
        TelemetryHealth,
        compute_away_rate,
    )
    broken = TelemetryHealth(verdict="broken", covered_sessions=0,
                             uncovered_sessions=9, uninstrumented_sessions=0)
    result = compute_away_rate(bucket_counts={"away_r": 2, "decision_r": 1},
                               health=broken)
    assert isinstance(result, AwayRateResult)
    assert result.unmeasured_kind == "withheld"
    assert result.objective_rate is None
    empty = compute_away_rate(
        bucket_counts={}, health=TelemetryHealth(verdict="ok"))
    assert empty.unmeasured_kind == "not_yet_measurable"
    scored = compute_away_rate(bucket_counts={"away_r": 1, "decision_r": 1},
                               health=TelemetryHealth(verdict="ok"))
    assert scored.unmeasured_kind is None and scored.objective_rate == 0.5
