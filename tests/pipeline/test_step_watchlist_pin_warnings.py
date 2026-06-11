"""Arc 7 Task 4 — _step_watchlist pin plumbing + suppressed-removal warning.

A pinned watchlist row whose stable criteria fail for a 3rd consecutive run
would normally age off (archive). The pin vetoes the age-off: the live row
survives with the streak honestly advanced to 3, and _step_watchlist emits a
``pin_suppressed_removal`` run-warning (#27 silent-skip-without-audit) instead
of archiving.

REUSES the conftest_temporal _FakeLease + a file-backed HEAD DB.
"""
from __future__ import annotations

from types import SimpleNamespace

from swing.data.models import Candidate, CriterionResult, WatchlistEntry
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.watchlist import (
    get_watchlist_entry,
    upsert_watchlist_entry,
)
from swing.pipeline.runner import _step_watchlist
from swing.watchlist.service import STABLE_CRITERION_NAMES

from tests.pipeline.conftest_temporal import _FakeLease, tmp_db_v22  # noqa: F401

DATA_ASOF = "2026-06-10"


def _failing_candidate(ticker: str) -> Candidate:
    """A candidate whose 7 STABLE criteria all FAIL (bucket 'skip', close set).

    compute_watchlist_changes computes new_streak = prior(2) + 1 = 3 >=
    AGING_STREAK_THRESHOLD, so a non-pinned ticker would archive; the pin
    diverts it to suppressed_removes + streak_increment.
    """
    criteria = tuple(
        CriterionResult(
            criterion_name=name, layer="trend_template", result="fail",
            value=None, rule=None,
        )
        for name in STABLE_CRITERION_NAMES
    )
    return Candidate(
        ticker=ticker, bucket="skip", close=12.34, pivot=13.0,
        initial_stop=11.0, adr_pct=2.0, tight_streak=0, pullback_pct=5.0,
        prior_trend_pct=10.0, rs_rank=20, rs_return_12w_vs_spy=-1.0,
        rs_method="universe", pattern_tag=None, notes=None, criteria=criteria,
    )


def _seed(conn, *, ticker: str) -> int:
    """Seed a pinned watchlist row at streak=2 + a running pipeline_runs row +
    an evaluation_run with a FAILING candidate for the ticker. Return eval_run_id."""
    # Pinned watchlist row via the INSERT path (upsert's DO-UPDATE excludes pin
    # cols, but on a fresh INSERT for a NEW ticker pinned=1 writes through).
    with conn:
        upsert_watchlist_entry(conn, WatchlistEntry(
            ticker=ticker, added_date="2026-06-01",
            last_qualified_date="2026-06-01", status="watch",
            qualification_count=1, not_qualified_streak=2,
            last_data_asof_date="2026-06-09", entry_target=13.0,
            initial_stop_target=11.0, last_close=12.0, last_pivot=13.0,
            last_stop=11.0, last_adr_pct=2.0, missing_criteria=None, notes=None,
            pinned=True, pin_note="operator tracking", pinned_at="2026-06-01T00:00:00Z",
        ))
    # pipeline_runs running row (id must equal lease.run_id for set_*; here
    # _step_watchlist does NOT touch pipeline_runs, but keep a valid row).
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, '2026-06-10T18:00:00', 'manual', ?, '2026-06-10', 'tok', 'running')",
        (DATA_ASOF,),
    )
    from swing.data.models import EvaluationRun
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-06-10T18:00:00", data_asof_date=DATA_ASOF,
        action_session_date="2026-06-10", finviz_csv_path=None,
        tickers_evaluated=1, aplus_count=0, watch_count=0, skip_count=1,
        excluded_count=0, error_count=0))
    insert_candidates(conn, eval_run_id, [_failing_candidate(ticker)])
    conn.commit()
    return eval_run_id


def test_step_watchlist_pin_suppresses_removal_and_warns(tmp_db_v22):
    conn, db_path = tmp_db_v22
    eval_run_id = _seed(conn, ticker="KEEP")

    cfg = SimpleNamespace(paths=SimpleNamespace(db_path=db_path))
    lease = _FakeLease(db_path, run_id=1, data_asof=DATA_ASOF)
    run_warnings: list[dict] = []

    _step_watchlist(
        cfg=cfg, eval_run_id=eval_run_id, data_asof_date=DATA_ASOF,
        lease=lease, run_warnings=run_warnings,
    )

    sup = [w for w in run_warnings if w.get("kind") == "pin_suppressed_removal"]
    assert len(sup) == 1
    assert sup[0]["ticker"] == "KEEP"
    assert sup[0]["streak"] == 3
    assert sup[0]["step"] == "watchlist"

    # NOT archived — the live row survives, streak honestly advanced to 3.
    e = get_watchlist_entry(conn, "KEEP")
    assert e is not None
    assert e.not_qualified_streak == 3
    assert e.pinned is True

    archived = conn.execute(
        "SELECT COUNT(*) FROM watchlist_archive WHERE ticker = 'KEEP'"
    ).fetchone()[0]
    assert archived == 0


def test_step_watchlist_no_warnings_list_does_not_crash(tmp_db_v22):
    """run_warnings=None (the default) must not raise even with a suppressed removal."""
    conn, db_path = tmp_db_v22
    eval_run_id = _seed(conn, ticker="KEEP")

    cfg = SimpleNamespace(paths=SimpleNamespace(db_path=db_path))
    lease = _FakeLease(db_path, run_id=1, data_asof=DATA_ASOF)

    _step_watchlist(
        cfg=cfg, eval_run_id=eval_run_id, data_asof_date=DATA_ASOF, lease=lease,
    )
    e = get_watchlist_entry(conn, "KEEP")
    assert e is not None and e.not_qualified_streak == 3
