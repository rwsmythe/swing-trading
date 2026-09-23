"""22-A2 Task 10 -- the four cohort readers exclude BY NAME (A2-91..A2-97c).

RD's F10 sub-ruling: a tier-2 row whose read-time verdict is not ``ADMIT`` does
NOT count, and it is NAMED in the read's output -- never silently uncounted.
CHARC G-T7FE-A+C item C: ``tier2_cohort_exclusions`` returns the named
``Tier2CohortRead(exclusions, observations)``; each reader COUNTS from
``exclusions`` only and RENDERS both.  CHARC G-T10-1: the four P35 readers are
the ONLY callers (one invocation per reader invocation; the breakdown threads
its read into every per-hypothesis tripwire status; the web callers pass
``WEB_REPLAY_BUDGET_SECONDS``, the CLI none).  RD G-T10-2: every surface that
SHOWS a cohort N from an excluding read renders the compact marker beside it
(count + the canonical surface; ``unverifiable`` never merged with
``excluded``), empty at zero exclusions.

The world is trade 25's real tier-2 row (written by the correction service
over a throwaway git world), with trade 25 closed and a second closed
``A+ baseline`` trade beside it, so the H1 cohort's N is TWO when the row is
admitted and ONE when it is excluded -- "drops by exactly one", never "drops
to zero".
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main
from swing.config import load
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import T25_TRADE_ID, build_pre_barrier_world
from tests.cli.test_cli_eval import _minimal_config
from tests.trades.test_22a2_correction_service import ticking_clock  # noqa: F401
from tests.trades.test_22a2_replay import _GitCounter, _tier2_world

H1_ID = 1
H1 = "A+ baseline"
H1_LABEL = "A+ baseline (aplus)"
H1_PEER = 26            # the second closed H1 trade: never tier-2
STORED_VERSION = fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
MOVED_VERSION = "2026-12-31.9"
STALE_REASON = "criterion 1: not_ancestor_of_origin_main"
OBSERVATION = (f"derivation_version_moved (stored {STORED_VERSION}, "
               f"current {MOVED_VERSION})")
STALE_LINE = (f"tier-2 not counted: trade {T25_TRADE_ID} tier2_evidence_stale "
              f"({STALE_REASON})")
UNVERIFIABLE_PREFIX = f"tier-2 not counted: trade {T25_TRADE_ID} tier2_unverifiable ("
OBSERVED_LINE = f"tier-2 counted with observation: trade {T25_TRADE_ID} ({OBSERVATION})"
STATES = ("admit", "rewritten", "grown", "moved", "unverifiable")


# --------------------------------------------------------------------------- worlds

def _seed_cohort(conn: sqlite3.Connection) -> None:
    """Close trade 25 (one exit fill) and add a second closed H1 trade."""
    conn.execute(
        "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, quantity, "
        "price, reason, reconciliation_status, fill_origin) VALUES "
        "(4801, ?, '2026-08-20T15:00:00', 'exit', 2.0, 55.0, NULL, "
        "'unreconciled', 'operator_typed')", (T25_TRADE_ID,))
    conn.execute(
        "UPDATE trades SET state = 'closed', current_size = 0, "
        "last_fill_at = '2026-08-20T15:00:00' WHERE id = ?", (T25_TRADE_ID,))
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "current_size, current_avg_cost, last_fill_at, hypothesis_label, "
        "candidate_id, entry_intent) VALUES (?, 'ZZZ', '2026-08-03', 10.0, 10, "
        "9.0, 9.0, 'closed', 'manual_off_pipeline', '2026-08-03T10:00:00', 0, "
        "10.0, '2026-08-05T15:00:00', ?, NULL, 'standard')", (H1_PEER, H1_LABEL))
    for fill_id, when, action, price in (
            (4802, "2026-08-03T10:00:00", "entry", 10.0),
            (4803, "2026-08-05T15:00:00", "exit", 10.5)):
        conn.execute(
            "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, "
            "quantity, price, reason, reconciliation_status, fill_origin) VALUES "
            "(?, ?, ?, ?, 10.0, ?, NULL, 'unreconciled', 'operator_typed')",
            (fill_id, H1_PEER, when, action, price))
    conn.commit()


def _world(tmp_path: Path, monkeypatch, state: str) -> sqlite3.Connection:
    """Trade 25's tier-2 row in one of the five read-time states."""
    w = _tier2_world(tmp_path)
    _seed_cohort(w.conn)
    monkeypatch.setattr(fve, "EVIDENCE_REPO_DIR", w.git.work)
    if state == "rewritten":
        w.git.rewrite_remote_dropping(w.sha)
    elif state == "grown":
        w.git.grow_remote(3, push_date="2026-09-21T12:00:00+00:00")
    elif state == "moved":
        monkeypatch.setattr(fve, "FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION", MOVED_VERSION)
    elif state == "unverifiable":
        _GitCounter(monkeypatch, timeout=True)
    else:
        assert state == "admit", state
    return w.conn


def _zero_world(tmp_path: Path) -> sqlite3.Connection:
    """No tier-2 row at all: trade 25 uncorrected (unlabelled), the peer in H1."""
    conn, _ids = build_pre_barrier_world(tmp_path, "zero")
    _seed_cohort(conn)
    return conn


def _expected(state: str) -> tuple[int, tuple, tuple]:
    """(H1 N, excluded, observed) -- excluded ``(id, verdict, reason)``."""
    if state == "rewritten":
        return 1, ((T25_TRADE_ID, "tier2_evidence_stale", STALE_REASON),), ()
    if state == "moved":
        return 2, (), ((T25_TRADE_ID, OBSERVATION),)
    return 2, (), ()


def _check(n: int, excluded: tuple, observed: tuple, state: str) -> None:
    if state == "unverifiable":
        assert n == 1
        ((tid, verdict, reason),) = excluded
        assert (tid, verdict) == (T25_TRADE_ID, "tier2_unverifiable")
        assert reason
        assert observed == ()
        return
    assert (n, excluded, observed) == _expected(state)


def _install(conn: sqlite3.Connection, tmp_path: Path, monkeypatch):
    """A real config whose DB is a byte copy of the world's DB."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    cfg.paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn.commit()
    dst = sqlite3.connect(cfg.paths.db_path)
    try:
        conn.backup(dst)
    finally:
        dst.close()
    return cfg, cfg_path


def _cli(cfg_path: Path, *args: str) -> str:
    result = CliRunner().invoke(main, ["--config", str(cfg_path), *args])
    assert result.exit_code == 0, (result.output, result.exception)
    return result.output


def _patch_prices(monkeypatch) -> None:
    """The dashboard's live-price read, held below trade 25's pivot."""
    from datetime import datetime

    from swing.web.price_cache import PriceCache, PriceSnapshot

    def get_many(self, tickers, *, deadline_seconds, executor):
        return {t: PriceSnapshot(ticker=t, price=53.5, asof=datetime.now(),
                                 is_stale=False, source="live") for t in tickers}

    monkeypatch.setattr(PriceCache, "get_many", get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _get(cfg, cfg_path, path: str) -> str:
    from swing.web.app import create_app

    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.get(path)
    assert r.status_code == 200, (path, r.status_code, r.text[:2000])
    return r.text


# --------------------------------------------------------------------------- the read

def test_the_read_is_a_named_frozen_type_admitted_observations_beside_exclusions(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """CHARC G-T7FE item C: a named frozen dataclass, never a bare tuple.
    ``exclusions`` is exactly the non-ADMIT set; ``observations`` is every
    ADMITTED row with a non-empty observation -- a moved version with keys
    equal lands in ``observations`` and NOT in ``exclusions``."""
    import dataclasses

    conn = _world(tmp_path, monkeypatch, "moved")
    try:
        read = fve.tier2_cohort_exclusions(conn, now=fve.datetime.now(fve.UTC))
        assert type(read) is fve.Tier2CohortRead
        assert dataclasses.is_dataclass(read)
        with pytest.raises(dataclasses.FrozenInstanceError):
            read.exclusions = {}  # type: ignore[misc]
        assert read.exclusions == {}
        assert set(read.observations) == {T25_TRADE_ID}
        v = read.observations[T25_TRADE_ID]
        assert (v.verdict, v.derivation_observation) == ("ADMIT", OBSERVATION)
    finally:
        conn.close()


def test_a_stale_row_under_a_moved_version_is_an_exclusion_not_an_observation(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    conn = _world(tmp_path, monkeypatch, "rewritten")
    try:
        monkeypatch.setattr(fve, "FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION", MOVED_VERSION)
        read = fve.tier2_cohort_exclusions(conn, now=fve.datetime.now(fve.UTC))
        assert set(read.exclusions) == {T25_TRADE_ID}
        assert read.observations == {}
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-91

@pytest.mark.parametrize("state", STATES)
def test_a2_91_tripwire_status_counts_from_exclusions_and_names_both(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    """PRE (a stored-tier reader): N reads 2 in every state.  REWRITTEN and
    UNVERIFIABLE drop N by exactly one and name the trade; GROWN leaves N
    unchanged; MOVED leaves N unchanged (an exclude-on-observation impl reads
    1) and carries the observation (an ignore-observations impl carries none)."""
    from swing.recommendations.hypothesis import compute_tripwire_status

    conn = _world(tmp_path, monkeypatch, state)
    try:
        tw = compute_tripwire_status(conn, hypothesis_id=H1_ID, starting_equity=1200.0)
        _check(tw.current_sample, tw.tier2_excluded, tw.tier2_observed, state)
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-92

@pytest.mark.parametrize("state", STATES)
def test_a2_92_journal_progress_counts_from_exclusions_and_names_both(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    from swing.journal.stats import compute_hypothesis_progress_breakdown

    conn = _world(tmp_path, monkeypatch, state)
    try:
        rows = {r.hypothesis_id: r for r in compute_hypothesis_progress_breakdown(
            conn, starting_equity=1200.0)}
        h1 = rows[H1_ID]
        _check(h1.current_sample, h1.tier2_excluded, h1.tier2_observed, state)
        for hid, r in rows.items():
            if hid != H1_ID:
                assert (r.tier2_excluded, r.tier2_observed) == ((), ())
    finally:
        conn.close()


@pytest.mark.parametrize("state", STATES)
def test_journal_review_renders_the_line_under_its_cohort_only(  # A2-92's surface
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    conn = _world(tmp_path, monkeypatch, state)
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    out = _cli(cfg_path, "journal", "review")
    section = out[out.index("## Hypothesis investigation progress"):]
    lines = section.splitlines()
    named = [i for i, line in enumerate(lines) if "tier-2" in line]
    h1_row = next(i for i, line in enumerate(lines) if line.startswith(f"- {H1} ("))
    if state in ("admit", "grown"):
        assert named == []
        assert f"{H1} (" in lines[h1_row] and ": 2 / " in lines[h1_row]
        return
    assert named == [h1_row + 1], section
    if state == "rewritten":
        assert lines[h1_row + 1].strip() == STALE_LINE
        assert ": 1 / " in lines[h1_row]
    elif state == "moved":
        assert lines[h1_row + 1].strip() == OBSERVED_LINE
        assert ": 2 / " in lines[h1_row]
    else:
        assert lines[h1_row + 1].strip().startswith(UNVERIFIABLE_PREFIX)
        assert ": 1 / " in lines[h1_row]


# --------------------------------------------------------------------------- A2-93

@pytest.mark.parametrize("state", STATES)
def test_a2_93_tier_surface_counts_from_exclusions_and_names_both(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    from swing.metrics.tier import compute_tier_comparison

    conn = _world(tmp_path, monkeypatch, state)
    try:
        result = compute_tier_comparison(conn)
        by_name = {c.cohort_name: c for c in result.cohorts}
        h1 = by_name[H1]
        _check(h1.n_closed, h1.tier2_excluded, h1.tier2_observed, state)
        for name, c in by_name.items():
            if name != H1:
                assert (c.tier2_excluded, c.tier2_observed) == ((), ())
    finally:
        conn.close()


def test_codex_r1_04_tier_observation_names_only_trades_the_filtered_n_counts(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """Codex R1-04: ``tier2_observed`` renders "tier-2 counted with observation"
    beside the cohort's N, so it must be computed from the trades the N ACTUALLY
    counts -- AFTER the optional unresolved-discrepancy filter, not before it.

    World: the MOVED state (trade 25 admitted, carrying the observation) plus
    an unresolved MATERIAL discrepancy on trade 25, read with
    ``exclude_unresolved_discrepancies=True``.  The filter removes trade 25 from
    the N (1, the peer only).  Pre-fix arithmetic: the observation was computed
    before the filter, so ``tier2_observed == ((25, OBSERVATION),)`` beside an
    N of 1 that does not include trade 25 -- a named line claiming a count that
    did not happen.  Post-fix: ``()``.  The filter-off twin keeps the line
    (N 2, observed ((25, OBSERVATION),)), so an impl that simply drops
    observations fails the twin."""
    from swing.metrics.tier import compute_tier_comparison

    conn = _world(tmp_path, monkeypatch, "moved")
    try:
        conn.execute(
            "INSERT INTO reconciliation_runs (run_id, source, source_artifact_path, "
            "source_artifact_sha256, period_start, period_end, started_ts, "
            "finished_ts, state) VALUES (9101, 'tos_csv', '/tmp/r1-04.csv', "
            "'r1-04', '2026-08-01', '2026-08-31', '2026-08-31T10:00:00.000', "
            "'2026-08-31T10:01:00.000', 'completed')")
        conn.execute(
            "INSERT INTO reconciliation_discrepancies (discrepancy_id, run_id, "
            "trade_id, discrepancy_type, field_name, expected_value_json, "
            "actual_value_json, material_to_review, resolution, resolution_reason, "
            "created_at) VALUES (9101, 9101, ?, 'stop_mismatch', 'current_stop', "
            "'\"x\"', '\"y\"', 1, 'unresolved', NULL, '2026-08-31T10:01:00.000')",
            (T25_TRADE_ID,))
        conn.commit()

        off = {c.cohort_name: c for c in compute_tier_comparison(conn).cohorts}[H1]
        assert (off.n_closed, off.tier2_observed) == (
            2, ((T25_TRADE_ID, OBSERVATION),))

        on = {c.cohort_name: c for c in compute_tier_comparison(
            conn, exclude_unresolved_discrepancies=True).cohorts}[H1]
        assert on.n_closed == 1
        assert on.tier2_observed == ()
        assert on.tier2_excluded == ()
    finally:
        conn.close()


@pytest.mark.parametrize("state", STATES)
def test_card_vm_counts_from_exclusions_and_names_both(  # A2-94's reader
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    from swing.web.view_models.metrics.hypothesis_progress_card import (
        build_hypothesis_progress_card_vm,
    )

    conn = _world(tmp_path, monkeypatch, state)
    try:
        vm = build_hypothesis_progress_card_vm(cfg=None, conn=conn)  # type: ignore[arg-type]
        by_name = {c.cohort_name: c for c in vm.cohorts}
        h1 = by_name[H1]
        _check(h1.n_closed, h1.tier2_excluded, h1.tier2_observed, state)
        for name, c in by_name.items():
            if name != H1:
                assert (c.tier2_excluded, c.tier2_observed) == ((), ())
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-94 / A2-95 (web)

_PAGE_STATES = ("rewritten", "moved", "unverifiable", "admit", "zero")


def _named_page(tmp_path: Path, monkeypatch, state: str, path: str) -> None:
    """One named page in one state.  ``zero`` is the zero-data state: neither
    line renders, the GET is 200, and NO subprocess starts."""
    conn = (_zero_world(tmp_path) if state == "zero"
            else _world(tmp_path, monkeypatch, state))
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    counter = _GitCounter(monkeypatch) if state == "zero" else None
    html = _get(cfg, cfg_path, path)
    if state == "rewritten":
        assert STALE_LINE in html
        assert "tier-2 counted with observation" not in html
    elif state == "moved":
        assert OBSERVED_LINE in html
        assert "tier-2 not counted" not in html
    elif state == "unverifiable":
        assert UNVERIFIABLE_PREFIX in html
    else:
        assert "tier-2" not in html
    if counter is not None:
        assert counter.calls == []


@pytest.mark.parametrize("state", _PAGE_STATES)
def test_a2_94_the_card_page_renders_the_line_and_zero_data_renders_none(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    _named_page(tmp_path, monkeypatch, state, "/metrics/hypothesis-progress")


@pytest.mark.parametrize("state", _PAGE_STATES)
def test_a2_95_the_tier_page_renders_the_line_and_zero_data_renders_none(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    _named_page(tmp_path, monkeypatch, state, "/metrics/tier-comparison")


# --------------------------------------------------------------------------- A2-96 + hypothesis status

@pytest.mark.parametrize("state", STATES)
def test_a2_96_hypothesis_list_prints_the_line_once_under_its_row(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    """CHARC G-T10-1 (3): the line renders ONCE PER ROW -- an exclusion is a
    fact about THAT cohort's N, and trade 25 is under H1 only."""
    conn = _world(tmp_path, monkeypatch, state)
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    lines = _cli(cfg_path, "hypothesis", "list").splitlines()
    h1_row = next(i for i, line in enumerate(lines) if line.startswith(f"{H1_ID} "))
    named = [i for i, line in enumerate(lines) if "tier-2" in line]
    n, _excl, _obs = _expected(state if state != "unverifiable" else "rewritten")
    assert f" {n}/" in lines[h1_row]
    if state in ("admit", "grown"):
        assert named == []
    elif state == "rewritten":
        assert named == [h1_row + 1]
        assert lines[h1_row + 1].strip() == STALE_LINE
    elif state == "moved":
        assert named == [h1_row + 1]
        assert lines[h1_row + 1].strip() == OBSERVED_LINE
    else:
        assert named == [h1_row + 1]
        assert lines[h1_row + 1].strip().startswith(UNVERIFIABLE_PREFIX)


@pytest.mark.parametrize("state", ("rewritten", "unverifiable", "admit", "moved"))
def test_hypothesis_status_renders_the_named_lines_and_no_marker(
    tmp_path: Path, ticking_clock, monkeypatch, state: str,
) -> None:
    """CHARC G-T10-1 (4) + RD G-T10-F4: ``hypothesis status`` is a per-cohort
    DETAIL surface (the fifth named surface), so it renders the FULL named
    line below the shown N and NO compact marker -- a "see hypothesis list"
    pointer on the surface that already holds the line is a wrong pointer.
    An impl that keeps both FAILS; zero exclusions -> neither."""
    conn = _world(tmp_path, monkeypatch, state)
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    out = _cli(cfg_path, "hypothesis", "status", str(H1_ID))
    lines = out.splitlines()
    (i,) = [k for k, line in enumerate(lines) if "Current sample:" in line]
    sample = lines[i]
    assert "see hypothesis list" not in out
    assert "(1 excluded" not in out
    assert "(1 unverifiable:" not in out
    if state == "rewritten":
        assert sample.split(":", 1)[1].strip() == "1"
        assert lines[i + 1].strip() == STALE_LINE
    elif state == "unverifiable":
        assert sample.split(":", 1)[1].strip() == "1"
        assert lines[i + 1].strip().startswith(UNVERIFIABLE_PREFIX)
    elif state == "moved":
        assert sample.split(":", 1)[1].strip() == "2"
        assert OBSERVED_LINE in out
    else:
        assert sample.split(":", 1)[1].strip() == "2"
        assert "tier-2" not in out


# --------------------------------------------------------------------------- RD G-T10-2 markers (web)

_MARKER_PAGES = (
    ("/", "hypothesis list"),
    ("/hyp-recs/refresh", "hypothesis list"),
    ("/metrics/deviation-outcome", "tier comparison"),
)


@pytest.mark.parametrize(("path", "surface"), _MARKER_PAGES)
@pytest.mark.parametrize("state", ("rewritten", "unverifiable", "admit"))
def test_rd_g_t10_2_a_shown_cohort_n_carries_the_marker(
    tmp_path: Path, ticking_clock, monkeypatch, state: str, path: str, surface: str,
) -> None:
    """One excluded -> the marker with count 1 and the canonical surface; zero
    -> ABSENT (an always-render impl FAILS); one unverifiable -> says
    ``unverifiable`` (a merged-categories impl FAILS).  Full names are NOT
    duplicated here."""
    _patch_prices(monkeypatch)
    conn = _world(tmp_path, monkeypatch, state)
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    html = _get(cfg, cfg_path, path)
    if state == "rewritten":
        assert f"(1 excluded: see {surface})" in html
        assert "unverifiable: see" not in html
    elif state == "unverifiable":
        assert f"(1 unverifiable: see {surface})" in html
        assert "excluded: see" not in html
    else:
        assert f": see {surface})" not in html
    assert "tier-2 not counted" not in html


# --------------------------------------------------------------------------- A2-97

@pytest.mark.parametrize("reader", ("tripwire", "breakdown", "tier", "card"))
def test_a2_97_unverifiable_excludes_and_names_never_admitted_on_the_stored_grade(
    tmp_path: Path, ticking_clock, monkeypatch, reader: str,
) -> None:
    """The stored tier is ``latch_ladder_tier2`` (an attestation); a replay
    that could not reach a verdict EXCLUDES and names, in every reader."""
    from swing.journal.stats import compute_hypothesis_progress_breakdown
    from swing.metrics.tier import compute_tier_comparison
    from swing.recommendations.hypothesis import compute_tripwire_status
    from swing.web.view_models.metrics.hypothesis_progress_card import (
        build_hypothesis_progress_card_vm,
    )

    conn = _world(tmp_path, monkeypatch, "unverifiable")
    try:
        (tier,) = [r[0] for r in conn.execute(
            "SELECT admission_tier FROM provenance_corrections")]
        assert tier == "latch_ladder_tier2"
        if reader == "tripwire":
            got = compute_tripwire_status(conn, hypothesis_id=H1_ID, starting_equity=1.0)
            n = got.current_sample
        elif reader == "breakdown":
            got = next(r for r in compute_hypothesis_progress_breakdown(
                conn, starting_equity=1.0) if r.hypothesis_id == H1_ID)
            n = got.current_sample
        elif reader == "tier":
            got = next(c for c in compute_tier_comparison(conn).cohorts
                       if c.cohort_name == H1)
            n = got.n_closed
        else:
            got = next(c for c in build_hypothesis_progress_card_vm(
                cfg=None, conn=conn).cohorts if c.cohort_name == H1)  # type: ignore[arg-type]
            n = got.n_closed
        _check(n, got.tier2_excluded, got.tier2_observed, "unverifiable")
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-97b / A2-97c

def test_a2_97b_the_web_card_on_a_slow_git_excludes_within_the_budget(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """Each git call sleeps 2.5 s.  The card's ONE invocation runs under the
    web budget: the first call starts inside it and is let finish, nothing
    after it starts, and the row reads EXCLUDED ``web_budget_exhausted``.
    PRE (no budget): the GET is held for every call (>= 6 x 2.5 s)."""
    conn = _world(tmp_path, monkeypatch, "admit")
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    from swing.web.app import create_app

    with TestClient(create_app(cfg, cfg_path)) as client:
        counter = _GitCounter(monkeypatch, delay=2.5)
        started = time.monotonic()
        r = client.get("/metrics/hypothesis-progress")
        elapsed = time.monotonic() - started
    assert r.status_code == 200
    assert (f"tier-2 not counted: trade {T25_TRADE_ID} tier2_unverifiable "
            f"({fve.REASON_WEB_BUDGET_EXHAUSTED})") in r.text
    assert len(counter.calls) == 1
    assert elapsed < fve.WEB_REPLAY_BUDGET_SECONDS + 2.5 + 3.0


def test_a2_97c_the_cli_reader_on_the_same_slow_git_waits_and_admits(
    tmp_path: Path, ticking_clock, monkeypatch,
) -> None:
    """``swing hypothesis status`` passes ``budget_seconds=None``: every git
    call runs (the total past the web budget) and the row ADMITS.  PRE (a
    budget leaked into the CLI): the row reads ``web_budget_exhausted``."""
    conn = _world(tmp_path, monkeypatch, "admit")
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    counter = _GitCounter(monkeypatch, delay=0.45)
    started = time.monotonic()
    out = _cli(cfg_path, "hypothesis", "status", str(H1_ID))
    elapsed = time.monotonic() - started
    assert elapsed > fve.WEB_REPLAY_BUDGET_SECONDS, (elapsed, len(counter.calls))
    assert fve.REASON_WEB_BUDGET_EXHAUSTED not in out
    assert "tier-2" not in out
    (sample,) = [line for line in out.splitlines() if "Current sample:" in line]
    assert sample.split(":", 1)[1].strip() == "2"


# --------------------------------------------------------------------------- CHARC G-T10-1 (1)(2): invocations

def _count_invocations(monkeypatch) -> list[float | None]:
    budgets: list[float | None] = []
    real = fve.tier2_cohort_exclusions

    def counting(conn, **kw):
        budgets.append(kw.get("budget_seconds"))
        return real(conn, **kw)

    monkeypatch.setattr(fve, "tier2_cohort_exclusions", counting)
    return budgets


_WEB_ROUTES = (
    ("/", 1),
    ("/hyp-recs/refresh", 1),
    ("/metrics", 3),
    ("/metrics/hypothesis-progress", 1),
    ("/metrics/tier-comparison", 1),
    ("/metrics/deviation-outcome", 1),
    ("/trades/entry/form?ticker=OII", 1),
)


@pytest.mark.parametrize(("path", "expected"), _WEB_ROUTES)
@pytest.mark.parametrize("rows", ("zero", "one"))
def test_charc_g_t10_1_web_invocations_per_route_each_under_the_web_budget(
    tmp_path: Path, ticking_clock, monkeypatch, rows: str, path: str, expected: int,
) -> None:
    """A page composing N readers spends at most N budgets.  ``/metrics``
    composes THREE (the card, the tier card and the deviation card -- the
    last reaches ``compute_tier_comparison`` through
    ``compute_deviation_outcome``).  Every web invocation passes
    ``WEB_REPLAY_BUDGET_SECONDS``."""
    _patch_prices(monkeypatch)
    conn = (_zero_world(tmp_path) if rows == "zero"
            else _world(tmp_path, monkeypatch, "admit"))
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
    finally:
        conn.close()
    budgets = _count_invocations(monkeypatch)
    _get(cfg, cfg_path, path)
    assert budgets == [fve.WEB_REPLAY_BUDGET_SECONDS] * expected


_CLI_COMMANDS = (
    (("journal", "review"), 1),
    (("hypothesis", "list"), 5),
    (("hypothesis", "status", str(H1_ID)), 1),
)


@pytest.mark.parametrize(("argv", "expected"), _CLI_COMMANDS)
@pytest.mark.parametrize("rows", ("zero", "one"))
def test_charc_g_t10_1_cli_invocations_carry_no_budget(
    tmp_path: Path, ticking_clock, monkeypatch, rows: str, argv: tuple, expected: int,
) -> None:
    """``journal review`` is ONE replay pass (PRE: 1 + H, the breakdown's own
    read plus one per hypothesis); ``hypothesis list`` is H invocations (five
    registry rows), accepted; none carries a budget."""
    conn = (_zero_world(tmp_path) if rows == "zero"
            else _world(tmp_path, monkeypatch, "admit"))
    try:
        cfg, cfg_path = _install(conn, tmp_path, monkeypatch)
        (registry_rows,) = conn.execute("SELECT COUNT(*) FROM hypothesis_registry").fetchone()
    finally:
        conn.close()
    assert registry_rows == 5
    budgets = _count_invocations(monkeypatch)
    _cli(cfg_path, *argv)
    assert budgets == [None] * expected


def test_the_trade_entry_prefill_threads_its_budget(tmp_path: Path, monkeypatch) -> None:
    """The prefill consumes the read and renders no count; the CLI prefill
    passes none, a web caller passes its budget through."""
    from swing.recommendations.hypothesis_prefill import (
        lookup_active_recommendation_label,
    )

    conn = _zero_world(tmp_path)
    try:
        budgets = _count_invocations(monkeypatch)
        lookup_active_recommendation_label(conn, ticker="OII", starting_equity=1200.0)
        lookup_active_recommendation_label(
            conn, ticker="OII", starting_equity=1200.0,
            budget_seconds=fve.WEB_REPLAY_BUDGET_SECONDS)
        assert budgets == [None, fve.WEB_REPLAY_BUDGET_SECONDS]
    finally:
        conn.close()
