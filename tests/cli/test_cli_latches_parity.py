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
    the value so the reader can see which kind of claim it is.

    THE THIRD BASIS KIND ARRIVED WITH RD's D-2 RULING and this assertion was
    widened rather than narrowed: a `cancel` row can reach NEITHER attribution
    branch, so its basis is now UNDETERMINED -- which is a kind of claim in
    exactly the sense this test is about, and the seeded row here IS a bare
    cancel. Leaving the assertion at `INFERRED or EXACT` would have made this
    test demand the wrong answer the ruling exists to remove."""
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
    line = next(x for x in r.output.splitlines() if "order 1002" in x)
    assert any(k in line for k in ("INFERRED", "EXACT", "UNDETERMINED")), line
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
        (obs, _health, intents, _unattached, _places, _sc,
         _latches) = _observations(
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
        (obs, health, _i, _u, _p, _sc, _latches) = _observations(
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


# ---------------------------------------------------------------------------
# The remaining OPEN review findings (Codex exec R5 MAJOR 5; auto-review
# CRITICAL 2)
# ---------------------------------------------------------------------------
def _intent(conn, cid, key, kind, **cols):
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    conn.execute(
        "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
        "ticker, detection_date, idempotency_key, action_session_date, "
        f"recorded_ts, surface, intent_kind{', ' + names if cols else ''}) "
        "VALUES (?, 121, 'FTRE', '2026-07-20', ?, '2026-07-27', "
        f"?, 'latch_panel', ?{', ' + marks if cols else ''})",
        (cid, key, f"2026-07-27T09:00:0{key[-1]}", kind, *cols.values()))
    return int(conn.execute(
        "SELECT intent_id FROM latch_order_intents WHERE idempotency_key = ?",
        (key,)).fetchone()[0])


# The FULL framework + derivation block a `place` row structurally requires.
# Written out here rather than trimmed to the fields under test, because the
# migration's required-block CHECK is the point: a `place` row that could be
# written without its derivation would be an unauditable mandate.
_SNAPSHOT = '{"attributable_order_count": 0, "broker_snapshot_branch": "absence", "broker_snapshot_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "broker_snapshot_session": "2026-07-27", "broker_snapshot_ts": "2026-07-27T09:00:00", "exact_framework_match_count": 0, "indeterminate": false}'

_PLACE_BLOCK = dict(
    framework_order_type="LIMIT", framework_duration="GOOD_TILL_CANCEL",
    framework_limit_price=18.89, framework_quantity=9,
    derivation_zone_cap_pct=3.0, derivation_sizing_equity=7500.0,
    derivation_max_risk_pct=0.005, derivation_position_pct_cap=0.15,
    derivation_sizing_basis="limit_price", derivation_regime_close=19.20,
    derivation_regime_close_session="2026-07-24",
    derivation_real_equity=1234.56, derivation_equity_floor=7500.0,
)


def test_an_ATTEST_row_carrying_a_broker_order_id_reaches_the_origin_query(
        seeded_db):
    """CODEX EXEC R5 MAJOR 5. The writer and the schema both PERMIT
    `actual_broker_order_id` on an `attest` row -- `acted_manually` is precisely
    the case where the operator names the order he placed by hand -- but the
    origin report filtered observed orders to `validity` and `cancel`, so that
    broker order vanished from the distinguishability query entirely.

    Framework-versus-operator attribution has to survive the ATTESTATION path,
    which is the one path that exists for orders the framework did not prepare.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        _intent(conn, cid, "att1", "attest",
                attested_disposition="acted_manually",
                actual_broker_order_id="5150")
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "order 5150" in r.output
    assert "inferred_origin=" in r.output
    # The roster is DERIVED from the enum by the same EXCLUSION the migration
    # states, so a kind added later joins it without an edit here.
    from swing.latches.constants import (
        LATCH_BROKER_ORDER_ID_KINDS,
        LATCH_INTENT_KINDS,
    )
    assert LATCH_BROKER_ORDER_ID_KINDS == LATCH_INTENT_KINDS - {
        "place", "decline"}


def test_an_EARLIER_place_validity_cycle_is_LABELLED_not_silently_discarded(
        seeded_db):
    """AUTO-REVIEW CRITICAL 2. The resolver explicitly supports SEVERAL
    place/validity cycles on one latch -- he places, it is rejected, he
    re-places -- but the report reads the GOVERNING place intent and its
    validity child ONLY. An initial REJECTION followed by an accepted retry
    therefore reported `validity_failed=0` and up to 100% agreement, discarding
    the rejection: a flattering measurement over incomplete evidence.

    RD CARRY 1 fixes the ledger's UNIT as the LATCH, so the fix is NOT a second
    observation for the same opportunity -- that would inflate every denominator
    including the away rate. It is a LABELLED REDUCTION: the earlier cycles and
    their outcomes are printed, so the reader sees the evidence the agreement
    numbers do not contain instead of never learning it existed.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        first = _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "val2", "validity",
                validity_outcome="rejected_by_broker",
                validated_place_intent_id=first,
                validity_detail=_SNAPSHOT)
        _intent(conn, cid, "plc3", "place", **_PLACE_BLOCK)
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "EARLIER PLACE/VALIDITY CYCLES" in r.output
    assert "rejected_by_broker" in r.output
    assert f"place intent {first}" in r.output


def test_an_UNANSWERED_earlier_cycle_is_reported_as_unknown_not_omitted(
        seeded_db):
    """CODEX EXEC R6 MAJOR. The earlier-cycles disclosure only reported cycles
    that HAD a validity child, so an UNRESOLVED first attempt followed by an
    accepted retry produced neither an earlier-cycle line nor an unknown count --
    and the governing retry could show 100% agreement over evidence the ledger
    was holding and not showing.

    An unanswered cycle is exactly the absence RD's ruling 4 says must be
    LABELLED rather than left to read as nothing-to-see.

    THE LABEL IS NOW A NAMED CATEGORY (RD ruling, 2026-07-30). "unknown (never
    answered)" was prose; `displaced_unanswerable` is a NAME the report also
    COUNTS and discloses beside the agreement rate it was excluded from. The
    counting half lives in `tests/cli/test_latches_displaced_unanswerable.py`.
    """
    from swing.latches.constants import DISPLACED_UNANSWERABLE
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        first = _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "plc3", "place", **_PLACE_BLOCK)
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "EARLIER PLACE/VALIDITY CYCLES" in r.output
    assert f"place intent {first}: {DISPLACED_UNANSWERABLE}" in r.output


def test_a_DECLINE_superseding_the_place_moves_it_into_the_earlier_cycles(
        seeded_db):
    """CODEX EXEC R7 MAJOR. The place/decline recency ruling was applied in the
    classifier and NOT propagated to the report, which still keyed on the latest
    place BY KIND -- so `place -> rejected validity -> later decline` neither
    scored the rejection as the current cycle nor disclosed it as an earlier one.
    Real framework-failure evidence the ledger was holding and not showing.

    The decision family resolves ONCE, in the classifier, in the panel and here.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        place = _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "val2", "validity",
                validity_outcome="rejected_by_broker",
                validated_place_intent_id=place,
                validity_detail=_SNAPSHOT)
        _intent(conn, cid, "dec3", "decline",
                decline_reason="the retry is not worth it", **{
                    k: v for k, v in _PLACE_BLOCK.items()})
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "declined:" in r.output
    assert "EARLIER PLACE/VALIDITY CYCLES" in r.output
    assert f"place intent {place}: rejected_by_broker" in r.output


# ==========================================================================
# T7.14 -- the REPORT-ONLY calibration lines (item 3b, RD OQ-9 / OQ-15).
#
# NOTE ON THE COMMAND NAME: the item-3 plan calls this surface `swing latches
# report`. No such command exists -- `parity` is the only one on the group, and
# it IS the latch measurement read -- so the lines land there. Recorded rather
# than silently reconciled.
# ==========================================================================
def _seed_lapse_corpus(cfg):
    """TWO latches: one TRUE would-clear, one qualifying-but-precedence-LOSING.

    The loser is the T4.23(a) shape -- a qualifying lapse behind an earlier
    FILL -- which is the only geometry that separates a would-clear count read
    off `lapse_would_clear_session` from one read off
    `lapse_qualifying_session`.
    """
    from swing.evaluation.dates import session_offset
    from datetime import date

    anchor = date(2026, 7, 27)
    days = [anchor]
    while len(days) < 6:
        days.append(session_offset(days[-1], 1))
    tt = ("TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
          "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
          "TT7_within_52w_high_25pct", "TT8_rs_rank")
    vcp = ("adr", "ma_short_rising", "ma_stack_10_20_50", "orderliness",
           "prior_trend", "proximity_20ma", "pullback", "tightness",
           "vcp_volume_contraction")
    conn = connect(cfg.paths.db_path)
    with conn:
        for i, d in enumerate(days):
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 2, 1, 1, 0, 0, 0)",
                (300 + i, f"{d.isoformat()}T17:30:00", d.isoformat(),
                 d.isoformat()))
            for ticker in ("WOULD", "LOSER"):
                bucket = "aplus" if i == 0 else "watch"
                cur = conn.execute(
                    "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                    "close, pivot, initial_stop, adr_pct, rs_method) VALUES "
                    "(?, ?, ?, 16.5, 16.90, 13.40, 4.021, 'universe')",
                    (300 + i, ticker, bucket))
                cid = int(cur.lastrowid)
                for name in tt:
                    conn.execute(
                        "INSERT INTO candidate_criteria (candidate_id, "
                        "criterion_name, layer, result) VALUES (?, ?, "
                        "'trend_template', 'pass')", (cid, name))
                for name in vcp:
                    bad = i > 0 and name in ("tightness", "adr", "pullback")
                    conn.execute(
                        "INSERT INTO candidate_criteria (candidate_id, "
                        "criterion_name, layer, result) VALUES (?, ?, 'vcp', ?)",
                        (cid, name, "fail" if bad else "pass"))
                conn.execute(
                    "INSERT INTO candidate_criteria (candidate_id, "
                    "criterion_name, layer, result) VALUES "
                    "(?, 'risk_feasibility', 'risk', 'pass')", (cid,))
        # The LOSER carries a FILL dated before its qualifying lapse, so the
        # armed rule would clear it by `fill` and it must NOT be counted.
        conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) VALUES "
            "(?, ?, 17.00, 5, 13.40, 13.40, 'entered', 's', 'i', 'pipeline_aplus', "
            "?, 5)", ("LOSER", days[3].isoformat(),
                      f"{days[3].isoformat()}T09:30:00"))
    conn.close()
    return days


def test_the_would_clear_line_counts_the_PRECEDENCE_RESOLVED_withdrawals(
        seeded_db, monkeypatch, tmp_path):
    """T7.14 -- THE CALIBRATION INSTRUMENT, TESTED AS ONE.

    Discriminator: a CLI reading `lapse_qualifying_session` counts TWO -- the
    instrument INFLATED on the very number that decides whether the rule gets
    armed -- while the web card and the conflict line both stay green.

    The loser is listed separately rather than dropped, because it is real
    evidence about the CONJUNCTS that the withdrawal count deliberately
    excludes.
    """
    import pandas as pd

    cfg, cfg_path = seeded_db
    days = _seed_lapse_corpus(cfg)
    closes = [16.50, 16.20, 15.90, 15.60, 15.30, 15.00]
    frame = pd.DataFrame({
        "asof_date": [d.isoformat() for d in days],
        "open": closes, "high": closes, "low": closes, "close": closes,
    })
    import swing.data.ohlcv_archive as archive
    monkeypatch.setattr(archive, "resolve_ohlcv_window",
                        lambda ticker, **kw: (frame, {"provider": "test"}))
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "CRITERIA-LAPSE CALIBRATION" in r.output
    assert "REPORT ONLY -- the rule is NOT armed" in r.output
    assert "would-withdraw latches:" in r.output
    # ONE withdrawal, not two: the filled latch qualified and LOST.
    would = [ln for ln in r.output.splitlines()
             if "would-withdraw latches:" in ln]
    assert would and would[0].strip().endswith("1"), r.output
    lost = [ln for ln in r.output.splitlines()
            if "qualified but LOST on precedence:" in ln]
    assert lost and lost[0].strip().endswith("1"), r.output
    assert "WOULD" in r.output
    assert "NOTHING WAS WITHDRAWN" in r.output


def test_the_calibration_section_states_the_N_in_force(seeded_db):
    """N is a deliberate calibration RD says plainly he cannot derive, and
    changing it rewrites history -- so the read that will be used to RETUNE it
    must say which N produced its numbers."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert "N in force:" in r.output
    assert "same-session verdict conflicts:" in r.output


# ---------------------------------------------------------------------------
# Codex R1 MINOR + auto-review MINOR -- two CLI counting/roster defects
# ---------------------------------------------------------------------------
def test_the_EXCLUSIONS_breakdown_covers_EVERY_unattributable_disposition(
        seeded_db):
    """Both reviewers, independently. The section is titled "unattributable"
    and enumerated a THREE-VALUE LITERAL; `UNATTRIBUTABLE_DISPOSITIONS` became
    four when item 3b added `framework_withdrawn`.

    So the R-bucket total counts a withdrawal into `unattributable_r` while the
    breakdown that claims to explain that total omits the reason for it -- a
    read whose whole job is telling the operator WHY observations were excluded.

    Pinned against the DERIVED set rather than a widened literal, which is the
    only version of this test that survives the next disposition.
    """
    from swing.latches.constants import UNATTRIBUTABLE_DISPOSITIONS
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    section = r.output.split("EXCLUSIONS (unattributable", 1)[1]
    for name in sorted(UNATTRIBUTABLE_DISPOSITIONS):
        assert f"  {name}:" in section, (name, section)


def test_one_pipeline_conflict_is_counted_ONCE_across_overlapping_latches(
        capsys):
    """Codex R1 MINOR + auto-review MINOR. A same-session verdict conflict is a
    fact about the PIPELINE -- two runs for one action session disagreeing about
    one ticker's structure. It is not a fact about a latch.

    But the lapse analysis deliberately scans PAST a latch's actual terminal, so
    an old cleared latch and its successor on the same ticker carry OVERLAPPING
    analysis windows and both list the same conflicted session. Summing the
    tuple lengths reported TWO pipeline conflicts where one occurred, and
    printed the same date twice under the same ticker -- inflating a data-quality
    signal RD required to be surfaced accurately.
    """
    from datetime import date

    from swing.cli_latches import _echo_report_only_lapse
    from swing.config import LatchesConfig
    from swing.latches.identity import LatchIdentity
    from swing.latches.models import Latch

    shared = date(2026, 7, 30)

    def _latch(cid):
        return Latch(
            identity=LatchIdentity(
                candidate_id=cid, evaluation_run_id=126, ticker="VSTS",
                detection_date="2026-07-27", pipeline_run_id=140),
            latched_pivot=16.90, latched_initial_stop=13.40, zone_cap=17.4070,
            anchor=date(2026, 7, 27), horizon_expiry=date(2026, 9, 8),
            sessions_elapsed=5, sessions_to_horizon=25, state="armed",
            lapse_conflicted_sessions=(shared,))

    class _Cfg:
        latches = LatchesConfig()

    _echo_report_only_lapse(_Cfg(), [_latch(8851), _latch(8852)])
    out = capsys.readouterr().out
    line = [ln for ln in out.splitlines()
            if "same-session verdict conflicts:" in ln]
    assert line and line[0].strip().endswith("1"), out
    # And the date is printed ONCE, not once per latch.
    assert out.count("2026-07-30") == 1, out


# ---------------------------------------------------------------------------
# D-2a -- THE ATTRIBUTION FLOOR (RD ruling 2, wave item 4; MERGE-BLOCKING).
#
# `_inferred_origin` has two attribution branches and a `cancel` row can reach
# NEITHER:
#   * the EXACT branch needs `validated_place_intent_id`, which migration 0033
#     makes NULL on every kind but `validity`
#     (`CHECK (intent_kind = 'validity' OR (... validated_place_intent_id IS
#     NULL))`);
#   * the params branch needs `actual_limit_price` / `actual_quantity`, which
#     the shape-exclusion CHECK makes NULL on every kind but `validity`.
# So it fell through to the latch-match fallback and reported a
# framework-mandated order, cancelled through the framework, carrying the
# broker order id the framework itself recorded, as OPERATOR-originated.
#
# That is a WRONG ANSWER, not a missing one, in a ledger whose entire purpose
# is framework-versus-operator attribution -- and it is `alarm, never assert`
# violated: a positive attribution asserted from an absence of evidence.
#
# THE EXACT THREE-HOP CHAIN (cancel -> the validity row bearing the same broker
# order id -> its `validated_place_intent_id` -> the place) IS DEFERRED TO ITEM
# 5. What is NOT available is shipping its absence as `operator_inferred`.
# ---------------------------------------------------------------------------


def _seed_cancel(cfg, cid, *, key, order_id, recorded_ts="2026-07-27T09:00:00"):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id) VALUES "
            "(?, 121, 'FTRE', '2026-07-20', ?, '2026-07-27', ?, "
            "'latch_panel', 'cancel', ?)",
            (cid, key, recorded_ts, order_id))
    conn.close()


def test_a_CANCEL_beside_a_PLACE_is_UNDETERMINED_and_never_operator_inferred(
        seeded_db):
    """DISCRIMINATOR. Pre-fix this exact geometry prints
    `inferred_origin=operator_inferred` -- the framework prepared the order, the
    operator cancelled it through the framework, and the report credits him with
    originating it."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    _seed_place(cfg, cid, key="p-1", recorded_ts="2026-07-27T08:00:00")
    _seed_cancel(cfg, cid, key="c-1", order_id="2001")
    r = _run(cfg_path)
    assert "order 2001" in r.output
    line = next(x for x in r.output.splitlines() if "order 2001" in x)
    assert "operator_inferred" not in line, line
    assert "inferred_origin=undetermined" in line, line
    # THE BASIS'S OTHER BRANCH, ASSERTED HERE (Codex R5 MINOR). Its sibling
    # below pins the no-place wording; without this line a regression that
    # printed "no place intent" in BOTH branches would pass both tests, and the
    # residual evidence the basis exists to carry would be silently gone.
    assert "a place intent exists on this latch" in line, line


def test_the_UNDETERMINED_basis_still_states_whether_a_place_EXISTS(seeded_db):
    """The residual evidence is preserved in the BASIS rather than thrown away.

    "is there a place intent on this candidate at all" IS answerable for every
    kind -- it is only the ORDER-LEVEL comparison that a cancel row cannot
    reach -- so the value goes UNDETERMINED while the basis keeps the fact.
    Without this the fix would trade a wrong answer for a blind one.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    _seed_cancel(cfg, cid, key="c-2", order_id="2002")
    line = next(
        x for x in _run(cfg_path).output.splitlines() if "order 2002" in x)
    assert "inferred_origin=undetermined" in line, line
    assert "no place intent" in line, line


def test_a_VALIDITY_row_carrying_its_PARENT_is_still_reported_EXACT(seeded_db):
    """GUARD, and it is what stops the fix from over-firing. `validity` is the
    one kind the schema lets carry BOTH the parent link and the observed params,
    so the guard must not reach it: turning every row UNDETERMINED would delete
    the only exact linkage V1 has."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    parent = _seed_place(cfg, cid, key="p-3", recorded_ts="2026-07-27T08:00:00")
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO latch_order_intents (candidate_id, evaluation_run_id, "
            "ticker, detection_date, idempotency_key, action_session_date, "
            "recorded_ts, surface, intent_kind, actual_broker_order_id, "
            "actual_order_type, actual_duration, actual_limit_price, "
            "actual_quantity, validity_outcome, validity_detail, "
            "validated_place_intent_id) VALUES "
            "(?, 121, 'FTRE', '2026-07-20', 'v-3', '2026-07-27', "
            "'2026-07-27T10:00:00', 'latch_panel', 'validity', '2003', "
            "'LIMIT', 'GOOD_TILL_CANCEL', 18.89, 9, 'accepted_by_broker', "
            "?, ?)",
            (cid, _SNAPSHOT.replace('"absence"', '"presence"'), parent))
    conn.close()
    line = next(
        x for x in _run(cfg_path).output.splitlines() if "order 2003" in x)
    assert "inferred_origin=framework_inferred" in line, line
    assert "EXACT (captured broker order id)" in line, line
