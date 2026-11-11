"""D102 test 2j -- the shifting reader (plan section 0.3).

`swing/metrics/pattern_outcomes.py:_count_reached_1r_hit_stop` joins a trade
to the PE rows of ITS candidate's night (`t.candidate_id = c.id`). A
non-latched aplus entry that NAMES an earlier aplus night through the entry
form (T2.3) therefore attributes through THAT night's PE row -- the night the
operator acted on -- instead of the fill night's.

THE DISCRIMINATOR. The two nights carry PE rows of DIFFERENT pattern classes
(the earlier night `vcp`, the later `flat_base`), so the per-class count
itself tells which night the trade went through: the old POST ignored the
choice and attributed every trade through the later night (`flat_base`
hit-stop 1, `vcp` 0), the new one through the named night. The sibling keeps
the default and attributes through the later night.
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.metrics.pattern_outcomes import _count_reached_1r_hit_stop
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.web.conftest import full_phase7_entry_payload
# The web app world (the entry goes through the production POST).
from tests.web.conftest import seeded_db, test_cfg  # noqa: F401

TICKER = "APX"


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=15.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _night(conn, *, eval_id: int, pr_id: int, session: str, asof: str,
           pattern_class: str) -> int:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES "
        "(?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
        (eval_id, f"{asof}T18:00:00", asof, session))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, lease_token, state, "
        "evaluation_run_id) VALUES (?, ?, ?, 'manual', ?, ?, ?, 'complete', "
        "?)",
        (pr_id, f"{asof}T18:00:00", f"{asof}T18:30:00", asof, session,
         f"tok{pr_id}", eval_id))
    cid = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method) VALUES "
        "(?, ?, 'aplus', 15.0, 15.2, 13.0, 2.5, 3, 5.0, 40.0, 85, 12.0, "
        "'universe')", (eval_id, TICKER)).lastrowid
    conn.execute(
        "INSERT INTO pattern_evaluations (pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) VALUES (?, ?, ?, 'v1', 0.7, '{}', 0.7, '{}', '{}', "
        "'2026-05-01', '2026-05-20', '2026-05-20T18:00:00')",
        (pr_id, TICKER, pattern_class))
    conn.execute(
        "INSERT INTO pattern_exemplars (ticker, timeframe, start_date, "
        "end_date, proposed_pattern_class, label_source, final_decision, "
        "labeler_evidence_json, structural_evidence_json, created_by, "
        "created_at) VALUES (?, 'daily', '2026-05-01', '2026-05-20', ?, "
        "'claude_silver', 'confirmed', '{}', '{}', 'synthetic_generator', "
        "'2026-05-20T00:00:00Z')", (TICKER, pattern_class))
    return int(cid)


def _world(cfg) -> tuple[int, int]:
    conn = connect(cfg.paths.db_path)
    try:
        earlier = _night(conn, eval_id=301, pr_id=401, session="2026-05-19",
                         asof="2026-05-18", pattern_class="vcp")
        later = _night(conn, eval_id=302, pr_id=402, session="2026-05-20",
                       asof="2026-05-19", pattern_class="flat_base")
        conn.commit()
    finally:
        conn.close()
    return earlier, later


def _enter_and_stop_out(cfg, cfg_path, monkeypatch, *, choose) -> None:
    import html
    import re

    _patch_price_cache(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        form = client.get(f"/trades/entry/form?ticker={TICKER}").text
        anchor = html.unescape(re.search(
            r'name="decision_nights_anchor"\s+value="([^"]*)"', form).group(1))
        offered = [e["candidate_id"] for e in json.loads(anchor)]
        data = full_phase7_entry_payload(
            ticker=TICKER, entry_date="2026-05-20", entry_price="15.00",
            shares="3", initial_stop="13.00", rationale="aplus-setup",
            notes="", origin="watchlist",
            decision_nights_anchor=anchor,
            decision_candidate_id=str(choose(offered)))
        resp = client.post("/trades/entry", data=data,
                           headers={"HX-Request": "true"})
        assert resp.status_code in (200, 204), resp.text
    conn = connect(cfg.paths.db_path)
    try:
        # The fixture closes the trade at negative R (the reader's only
        # inputs are the state and the realized R).
        conn.execute(
            "UPDATE trades SET state = 'closed', "
            "realized_R_if_plan_followed = -1.0 WHERE ticker = ?", (TICKER,))
        conn.commit()
    finally:
        conn.close()


def _hit_stop(cfg, pattern_class: str) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        return _count_reached_1r_hit_stop(conn, pattern_class=pattern_class)[2]
    finally:
        conn.close()


def test_2j_a_named_earlier_night_attributes_through_its_own_pe_row(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    earlier, later = _world(cfg)
    _enter_and_stop_out(cfg, cfg_path, monkeypatch,
                        choose=lambda offered: earlier)
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT candidate_id FROM trades WHERE ticker = ?",
            (TICKER,)).fetchone()[0] == earlier
    finally:
        conn.close()
    assert (_hit_stop(cfg, "vcp"), _hit_stop(cfg, "flat_base")) == (1, 0)


def test_2j_sibling_the_default_night_attributes_through_the_later_row(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    earlier, later = _world(cfg)
    _enter_and_stop_out(cfg, cfg_path, monkeypatch,
                        choose=lambda offered: offered[0])
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT candidate_id FROM trades WHERE ticker = ?",
            (TICKER,)).fetchone()[0] == later
    finally:
        conn.close()
    assert (_hit_stop(cfg, "vcp"), _hit_stop(cfg, "flat_base")) == (0, 1)
