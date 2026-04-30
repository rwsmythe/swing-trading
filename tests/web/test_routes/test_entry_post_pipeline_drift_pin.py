"""Behavior-pin test: cross-fragment drift in entry_post when a pipeline_run
completes between record_entry and build_dashboard.

Phase 2 R1 Minor 2 advisory; Phase 4 cleanup-remainder Task 12. NOT a fix —
this test pins the CURRENT behavior so a future fix dispatch makes the
test FAIL deliberately and updates the assertion.

Mechanism: `record_entry` (Connection A) commits the trade row. After
A commits, `build_dashboard` (Connection B) opens a NEW connection to
read state for the OOB rebuild chunks (status_strip, open_positions,
watchlist_top5, hyp_recs). If a NEW completed pipeline_run lands
between A.commit and B.open, the dashboard reads against the newer
run's state — even though record_entry's trade row binds to the older
run's chart-pattern classification.

Pin: the rebuilt OOB hyp-recs section reflects the LATER pipeline's
candidate set (the drift). A future fix that pins the rebuild to the
SAME PipelineRunBinding the form-render captured would change the
rebuilt section's content; this test fails deliberately and the fix
dispatch updates the assertion.
"""
from __future__ import annotations

import re
import threading

from fastapi.testclient import TestClient


def _seed_pipeline_run(cfg, *, eval_id: int, finished_ts: str) -> int:
    """Seed a complete pipeline_run row pointing at eval_id."""
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES (?, ?, 'manual', '2026-04-28', '2026-04-29',
                           'complete', ?, ?, 'ok')""",
                (
                    finished_ts.replace(":", "-")[:19],
                    finished_ts,
                    f"tok-{finished_ts}",
                    eval_id,
                ),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def _seed_eval_with_candidate(cfg, *, ticker: str, run_ts: str) -> int:
    """Seed a fresh evaluation_runs row + one A+ candidate."""
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, '2026-04-28', '2026-04-29', NULL, 1, 1,
                           0, 0, 0, 0, 'v1', 'h1')""",
                (run_ts,),
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (eval_id, ticker),
            )
        return eval_id
    finally:
        conn.close()


def _patch_pricecache(monkeypatch):
    from datetime import datetime

    from swing.web.price_cache import PriceCache, PriceSnapshot
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


def test_entry_post_oob_rebuild_reflects_pipeline_run_inserted_mid_request(
    seeded_db, monkeypatch,
):
    """Construct the mid-POST scenario via threading.Event: record_entry
    commits → test thread inserts P2 with a NEW candidate set → real
    build_dashboard then reads against P2 state → response's OOB hyp-recs
    section reflects P2's candidate (the drift).

    CURRENT pinned behavior: the OOB hyp-recs section contains the P2
    ticker (not P1's). The trade row itself was committed before P2
    landed, so it persists with whatever pipeline_run was latest at
    record_entry time (P1). A future fix that pins the rebuild to a
    PipelineRunBinding captured at request entry would have the OOB
    section contain P1's candidate instead — flipping the assertion.

    SKIP fallback explicitly forbidden: if threading coordination
    fails, the test must FAIL (not skip) so the regression is visible.
    """
    from swing.web.app import create_app

    cfg, cfg_path = seeded_db

    # P1: existing complete pipeline_run + eval E1 + candidate "P1ALPHA".
    e1 = _seed_eval_with_candidate(
        cfg, ticker="P1ALPHA", run_ts="2026-04-29T08:00:00",
    )
    _seed_pipeline_run(cfg, eval_id=e1, finished_ts="2026-04-29T08:30:00")

    # P2 will be seeded mid-request. Pre-stage the eval+candidate now
    # so the only thing the test thread needs to do mid-POST is insert
    # the pipeline_run row that flips `latest_completed_pipeline_run`.
    e2 = _seed_eval_with_candidate(
        cfg, ticker="P2BETA", run_ts="2026-04-29T09:00:00",
    )

    # Watchlist row for the ticker being traded (so the entry-form POST
    # is valid). TRADER is NOT in either eval's candidates — its presence
    # in OOB sections doesn't drive the discriminator.
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(
                conn,
                WatchlistEntry(
                    ticker="TRADER", added_date="2026-04-29",
                    last_qualified_date="2026-04-29", status="watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date="2026-04-28",
                    entry_target=180.0, initial_stop_target=170.0,
                    last_close=180.95, last_pivot=None, last_stop=None,
                    last_adr_pct=2.0, missing_criteria=None, notes=None,
                ),
            )
    finally:
        conn.close()

    _patch_pricecache(monkeypatch)

    # threading.Event coordination: wrap build_dashboard so the test
    # thread can insert P2 BEFORE real build_dashboard reads the DB.
    record_entry_committed = threading.Event()
    p2_inserted = threading.Event()

    import swing.web.routes.trades as trades_route_mod
    real_build_dashboard = trades_route_mod.build_dashboard

    def patched_build_dashboard(*args, **kwargs):
        # By the time entry_post calls build_dashboard, record_entry has
        # already committed. Signal the test thread; wait for it to
        # insert P2; then call real build_dashboard which sees P2.
        record_entry_committed.set()
        if not p2_inserted.wait(timeout=5.0):
            raise AssertionError(
                "test thread did not signal p2_inserted within 5s; "
                "threading.Event coordination broken — SKIP fallback "
                "forbidden per Task 12 contract."
            )
        return real_build_dashboard(*args, **kwargs)

    monkeypatch.setattr(
        trades_route_mod, "build_dashboard", patched_build_dashboard,
    )

    app = create_app(cfg, cfg_path)

    response_holder: dict = {}

    def post_thread():
        with TestClient(app) as client:
            r = client.post(
                "/trades/entry",
                headers={"HX-Request": "true"},
                data={
                    "ticker": "TRADER",
                    "entry_date": "2026-04-29",
                    "entry_price": "180.95",
                    "shares": "5",
                    "initial_stop": "170.00",
                    "rationale": "aplus-setup",
                    "origin": "hyp-recs",
                },
            )
        response_holder["resp"] = r

    t = threading.Thread(target=post_thread)
    t.start()

    if not record_entry_committed.wait(timeout=10.0):
        p2_inserted.set()  # release the wrapper so the thread doesn't hang
        t.join(timeout=2.0)
        raise AssertionError(
            "patched build_dashboard never signaled record_entry_committed "
            "within 10s; entry_post did not run as expected."
        )

    # record_entry has committed. Insert P2 now so the next read of
    # `latest_completed_pipeline_run` in build_dashboard returns P2.
    _seed_pipeline_run(cfg, eval_id=e2, finished_ts="2026-04-29T09:30:00")
    p2_inserted.set()

    t.join(timeout=10.0)
    assert not t.is_alive(), "post_thread did not complete within 10s"
    r = response_holder.get("resp")
    assert r is not None and r.status_code == 200, (
        f"entry_post failed: {r.status_code if r else 'no response'} "
        f"body={(r.text[:500] if r else '')!r}"
    )

    # Extract the OOB hyp-recs section.
    pattern = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<body>.*?)</section>'
        r'|<section[^>]*hx-swap-oob="true"[^>]*id="hypothesis-recommendations"[^>]*>'
        r'(?P<body2>.*?)</section>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(r.text)
    assert m is not None, (
        f"OOB hyp-recs section not found. Body[:500]={r.text[:500]!r}"
    )
    section_body = m.group("body") or m.group("body2") or ""

    # Pin the CURRENT drift behavior: rebuilt OOB section reflects
    # P2's candidates (because build_dashboard runs against post-P2
    # state, not against a request-entry-time PipelineRunBinding
    # snapshot). P2BETA is in P2's candidate set; P1ALPHA is in P1's.
    # If the fix were applied, P1ALPHA would be in the section instead.
    assert ">P2BETA<" in section_body, (
        "Drift behavior-pin: the rebuilt OOB hyp-recs section MUST "
        "contain P2BETA (the candidate from P2, the pipeline_run that "
        "completed between record_entry's commit and build_dashboard's "
        f"DB read). Got body[:1000]={section_body[:1000]!r}"
    )
    assert ">P1ALPHA<" not in section_body, (
        "Drift behavior-pin: P1ALPHA (P1's candidate) MUST NOT appear "
        "in the rebuilt OOB section — current behavior is that "
        "build_dashboard binds to the LATEST completed pipeline_run "
        "(P2), not the one captured at request entry. A future fix "
        "would flip this assertion."
    )
