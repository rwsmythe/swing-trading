"""D84 T9 -- the criteria-derived RISK FLAG marker at the tag sites (RD (2),
CHARC P1 (c)).

The marker is `zero_share_line(risk=risk_inputs_from_criteria(...))`: ASCII,
no numbers, rendered for ANY bucket whose stored risk layer is FLAGGED, so a
risk-fail WATCH name is not silent. A passing layer and an EMPTY layer (no risk
row, E-d) render nothing. It lives in a SIBLING mapping, never in the
`_flag_tags` tuple, which is the sort key.

Three seeded watch names: FLG (risk FAIL), PAS (risk PASS), EMP (NO risk row).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Candidate, CriterionResult, WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app

_RISK = {"FLG": "fail", "PAS": "pass", "EMP": None}



@pytest.fixture
def no_network(monkeypatch):
    """No live price or chart fetch: the price cache answers from nothing and
    the JIT chart helper renders nothing."""
    import swing.web.routes.watchlist as wl_routes
    from swing.web.price_cache import PriceCache

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(wl_routes, "get_or_render_surface",
                        lambda **kwargs: None)


def _seed(db_path: Path) -> None:
    """A COMPLETED pipeline run whose evaluation run holds the three watch
    names, each with its persisted risk row (or none), plus an active
    watchlist row per name."""
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 3, 0, 3, 0, 0, 0, 'v1', 'h1')""",
                ("2026-10-22T17:30:00", "2026-10-22", "2026-10-23"),
            )
            eval_id = cur.lastrowid
            for ticker, risk in _RISK.items():
                cand = conn.execute(
                    """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                       close, pivot, initial_stop, rs_method)
                       VALUES (?, ?, 'watch', 98.46, 104.0, 29.81, 'universe')""",
                    (eval_id, ticker),
                )
                conn.execute(
                    "INSERT INTO candidate_criteria (candidate_id, "
                    "criterion_name, layer, result) VALUES "
                    "(?, 'adr', 'vcp', 'fail')", (cand.lastrowid,))
                if risk is not None:
                    conn.execute(
                        "INSERT INTO candidate_criteria (candidate_id, "
                        "criterion_name, layer, result, value, rule) VALUES "
                        "(?, 'risk_feasibility', 'risk', ?, ?, ?)",
                        (cand.lastrowid, risk,
                         "0 sh, $0.00 risk" if risk == "fail" else "1 sh",
                         ">= 1 share fits in 0.5% of equity ($37.50)"))
                upsert_watchlist_entry(conn, WatchlistEntry(
                    ticker=ticker, added_date="2026-10-20",
                    last_qualified_date="2026-10-22", status="watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date="2026-10-22", entry_target=104.0,
                    initial_stop_target=29.81, last_close=98.46,
                    last_pivot=104.0, last_stop=29.81, last_adr_pct=6.0,
                    missing_criteria=None, notes=None,
                ))
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-10-22T17:30:00', '2026-10-22T17:45:00',
                           'scheduled', '2026-10-22', '2026-10-23',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _row_html(page: str, ticker: str) -> str:
    m = re.search(rf'<tr id="watchlist-row-{ticker}".*?</tr>', page, re.S)
    assert m, f"no watchlist row for {ticker}"
    return m.group(0)


def _candidate(ticker: str, risk: str | None, bucket: str = "watch") -> Candidate:
    crit = [CriterionResult("TT1_above_150_200", "trend_template", "pass"),
            CriterionResult("adr", "vcp", "pass")]
    if risk is not None:
        crit.append(CriterionResult("risk_feasibility", "risk", risk))
    return Candidate(
        ticker=ticker, bucket=bucket, close=98.46, pivot=104.0,
        initial_stop=29.81, adr_pct=6.0, tight_streak=None, pullback_pct=None,
        prior_trend_pct=None, rs_rank=None, rs_return_12w_vs_spy=None,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tuple(crit),
    )


def test_risk_flags_maps_ONLY_a_flagged_layer():  # noqa: N802
    """R-E3(2)f (R1-03). The passing and the EMPTY-layer tickers are ABSENT
    from the mapping, not present with "". It kills a `not risk_layer_passes`
    spelling, which would flag the empty layer."""
    from swing.web.view_models.dashboard import _risk_flags

    out = _risk_flags({
        "FLG": _candidate("FLG", "fail"),
        "PAS": _candidate("PAS", "pass"),
        "EMP": _candidate("EMP", None),
    })
    assert dict(out) == {"FLG": "RISK FLAG"}


def test_the_marker_is_SORT_NEUTRAL():  # noqa: N802
    """R-E3(2)c. `_flag_tags` is the sort key; the marker never enters it, so
    a risk-fail candidate and the same candidate with risk `pass` carry the
    same tags and sort identically -- while the marker DOES exist, beside the
    tuple, in the sibling mapping."""
    from swing.web.view_models.dashboard import (
        _flag_tags,
        _risk_flags,
        _sort_watchlist,
    )

    flagged = {"AAA": _candidate("AAA", "fail", "aplus"),
               "BBB": _candidate("BBB", "pass", "watch")}
    passing = {"AAA": _candidate("AAA", "pass", "aplus"),
               "BBB": _candidate("BBB", "pass", "watch")}
    assert _flag_tags(flagged) == _flag_tags(passing)
    assert dict(_risk_flags(flagged)) == {"AAA": "RISK FLAG"}
    assert dict(_risk_flags(passing)) == {}
    rows = [
        WatchlistEntry(
            ticker=t, added_date="2026-10-20", last_qualified_date="2026-10-22",
            status="watch", qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-10-22", entry_target=104.0,
            initial_stop_target=29.81, last_close=98.46, last_pivot=104.0,
            last_stop=29.81, last_adr_pct=6.0, missing_criteria=None,
            notes=None)
        for t in ("BBB", "AAA")]
    assert ([w.ticker for w in _sort_watchlist(rows, _flag_tags(flagged))]
            == [w.ticker for w in _sort_watchlist(rows, _flag_tags(passing))])


def test_the_watchlist_tag_row_renders_the_marker_for_a_risk_fail_WATCH_name(  # noqa: N802
        seeded_db, no_network):
    """R-E3(2)b -- RD (iv): a risk-fail WATCH name is not silent. The passing
    sibling and the NO-risk-row sibling (E-d, R1-03) render no marker."""
    cfg, cfg_path = seeded_db
    _seed(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        page = client.get("/watchlist").text
    flg = _row_html(page, "FLG")
    assert 'class="tag tag-risk-flag"' in flg and "RISK FLAG" in flg
    for t in ("PAS", "EMP"):
        row = _row_html(page, t)
        assert "RISK FLAG" not in row and "tag-risk-flag" not in row, t


def test_the_dashboard_top5_and_the_row_route_render_the_marker(seeded_db, no_network):
    """R-E3(2)d. The dashboard top-5 and the single-row route both render the
    marker for the risk-fail name; the NO-risk-row name renders none on
    either (E-d, R1-03)."""
    cfg, cfg_path = seeded_db
    _seed(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        dash = client.get("/").text
        row_flg = client.get("/watchlist/FLG/row").text
        row_emp = client.get("/watchlist/EMP/row").text
    assert "RISK FLAG" in _row_html(dash, "FLG")
    assert "RISK FLAG" not in _row_html(dash, "EMP")
    assert "RISK FLAG" in row_flg and "tag-risk-flag" in row_flg
    assert "RISK FLAG" not in row_emp


def test_the_watchlist_expansion_renders_the_risk_row_and_the_marker(seeded_db, no_network):
    """R-E3(2)e -- CHARC P1: the expansion renders the RISK layer as its own
    grid, so the persisted value and rule are visible where the marker is
    (the evaluation record, not the flag). A name with NO risk row renders no
    marker and no risk-grid item (E-d, R1-03)."""
    import html as _html

    cfg, cfg_path = seeded_db
    _seed(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        flg = _html.unescape(client.get("/watchlist/FLG/expand").text)
        emp = client.get("/watchlist/EMP/expand").text
    assert 'class="risk-grid"' in flg
    assert "risk_feasibility: fail" in flg
    assert "0 sh, $0.00 risk" in flg
    assert ">= 1 share fits in 0.5% of equity ($37.50)" in flg
    assert "RISK FLAG" in flg
    assert "RISK FLAG" not in emp
    grid = re.search(r'<ul class="risk-grid">(.*?)</ul>', emp, re.S)
    assert grid is None or "<li" not in grid.group(1)
