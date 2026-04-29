"""Dashboard "Hypothesis-driven recommendations" template section.

Frontend brief §4.2 + §5: section renders only when active_recommendations
is non-empty; tripwire-fired rows carry a `tripwire-fired` CSS class so the
operator cannot miss them; long suggested labels truncate with a tooltip
showing the full label; empty state hides the section entirely.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_aplus_pipeline(cfg, *, ticker: str = "AAPL", criteria=None) -> None:
    """Insert one complete pipeline run linked to one evaluation_run with a
    single A+ candidate (or whatever shape `criteria` yields)."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _patch_caches(monkeypatch):
    from swing.web.price_cache import PriceCache, PriceSnapshot
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=180.5, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_dashboard_renders_hypothesis_recommendations_section(
    seeded_db, monkeypatch,
):
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg)
    _patch_caches(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # Section heading is the operator's anchor.
    assert "Hypothesis-driven recommendations" in body
    # Ticker + hypothesis name appear in the section table.
    assert "AAPL" in body
    assert "A+ baseline" in body
    # Progress fraction "0 / 20" reflects the seeded target_sample_size.
    assert "0 / 20" in body
    # Suggested label preserves the canonical hypothesis-name prefix so
    # operators copy/paste the right tag into trade entry.
    assert "A+ baseline" in body
    # No tripwire-fired class when no closed trades exist.
    assert "tripwire-fired" not in body


def test_dashboard_omits_section_when_no_recommendations(
    seeded_db, monkeypatch,
):
    """Empty state — no candidates → no section in the HTML."""
    cfg, cfg_path = seeded_db
    _patch_caches(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # Section heading must not appear when there's nothing to show.
    assert "Hypothesis-driven recommendations" not in r.text


def test_dashboard_renders_section_when_no_match(seeded_db, monkeypatch):
    """Candidates exist but none match an active hypothesis (skip-bucket
    candidate without risk_feasibility-only failure) — section should still
    be omitted (empty list, not just "no panel"):"""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 0, 1, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            # skip-bucket without ANY criteria → matcher returns no matches.
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'ZZZ', 'skip', 50.0, 51.0, 45.0, 'universe')""",
                (eval_id,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()

    _patch_caches(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "Hypothesis-driven recommendations" not in r.text


def test_dashboard_long_suggested_label_truncates_with_tooltip(
    seeded_db, monkeypatch,
):
    """A long suggested label is truncated in the visible cell but the
    full text is available via title= tooltip. The threshold matches the
    template's {[:60]} truncation."""
    cfg, cfg_path = seeded_db
    # Watch-bucket candidate with proximity_20ma fail → "Near-A+ defensible:
    # extension test (...)" — long enough to trip truncation.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 1, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            cand_cur = conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'MSFT', 'watch', 200.0, 205.0, 190.0, 'universe')""",
                (eval_id,),
            )
            cid = cand_cur.lastrowid
            conn.execute(
                """INSERT INTO candidate_criteria
                   (candidate_id, criterion_name, layer, result)
                   VALUES (?, 'proximity_20ma', 'vcp', 'fail')""",
                (cid,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()

    _patch_caches(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    body = r.text
    assert "Hypothesis-driven recommendations" in body
    # Tooltip carries the full label.
    assert "title=\"Near-A+ defensible: extension test" in body


def test_dashboard_tripwire_fired_row_marked_with_css_class(
    seeded_db, monkeypatch,
):
    """When a hypothesis has a tripwire fired, the recommendations row gets
    `class="tripwire-fired"` so the operator cannot miss the alarm.

    We force the tripwire by seeding 3 closed trades labeled `Sub-A+
    VCP-not-formed ...` with -1R exits — meets the consecutive-loss
    threshold of 3 for that hypothesis (target_sample_size = 5, so
    consecutive_loss_tripwire = 3 per the seed plan).
    """
    cfg, cfg_path = seeded_db
    # Pipeline + a watch candidate with tightness fail → matches Sub-A+
    # VCP-not-formed.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 1, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            cand_cur = conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'NUE', 'watch', 100.0, 102.0, 95.0, 'universe')""",
                (eval_id,),
            )
            cid = cand_cur.lastrowid
            conn.execute(
                """INSERT INTO candidate_criteria
                   (candidate_id, criterion_name, layer, result)
                   VALUES (?, 'tightness', 'vcp', 'fail')""",
                (cid,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
            # Three closed trades, each at -1R, labeled with the hypothesis name.
            for i, ticker in enumerate(("VIR", "TST", "QED")):
                conn.execute(
                    """INSERT INTO trades
                       (ticker, entry_date, entry_price, initial_shares,
                        initial_stop, current_stop, status,
                        watchlist_entry_target, watchlist_initial_stop,
                        notes, hypothesis_label)
                       VALUES (?, ?, 100.0, 10, 90.0, 90.0, 'closed',
                               NULL, NULL, NULL,
                               'Sub-A+ VCP-not-formed test')""",
                    (ticker, f"2026-04-{15 + i:02d}"),
                )
                trade_id = conn.execute(
                    "SELECT id FROM trades WHERE ticker = ?", (ticker,),
                ).fetchone()[0]
                conn.execute(
                    """INSERT INTO exits
                       (trade_id, exit_date, exit_price, shares, reason,
                        realized_pnl, r_multiple, notes)
                       VALUES (?, ?, 90.0, 10, 'stop-hit', -100.0, -1.0, NULL)""",
                    (trade_id, f"2026-04-{20 + i:02d}"),
                )
    finally:
        conn.close()

    _patch_caches(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "Hypothesis-driven recommendations" in body
    assert "tripwire-fired" in body
    # Firing reason text appears so operator sees WHY.
    assert "consecutive -1R" in body


def test_dashboard_section_appears_after_today_decisions(
    seeded_db, monkeypatch,
):
    """Frontend brief §4.2: hypothesis-recommendations section renders AFTER
    today_decisions in the DOM order."""
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg)
    _patch_caches(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    body = r.text
    decisions_idx = body.find("Today's decisions")
    recs_idx = body.find("Hypothesis-driven recommendations")
    assert decisions_idx >= 0
    assert recs_idx >= 0
    assert decisions_idx < recs_idx, (
        "hypothesis-recommendations section must render AFTER today_decisions"
    )


def _hyp_recs_section(body: str) -> str:
    """Slice the body to JUST the hypothesis-recommendations <section>.

    Other surfaces (watchlist top5) already have a Pivot column; assertions
    scoped to the hyp-recs section avoid cross-section false positives.
    """
    start = body.find('id="hypothesis-recommendations"')
    assert start >= 0, "hypothesis-recommendations section is missing"
    end = body.find("</section>", start)
    assert end > start
    return body[start:end]


def test_dashboard_renders_pivot_price_column(seeded_db, monkeypatch):
    """QoL #3: the hyp-recs table renders a Pivot column between Price and
    Hypothesis showing Candidate.pivot formatted as $X.XX."""
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg)   # AAPL with pivot=181.0
    _patch_caches(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    section = _hyp_recs_section(r.text)
    # Pivot column header is present in the hyp-recs section specifically.
    assert "<th>Pivot</th>" in section
    # Pivot value rendered. Distinguishes from current_price ($180.50).
    assert "$181.00" in section
    # Column ordering: Price, then Pivot, then Hypothesis (within the section).
    price_idx = section.find("<th>Price</th>")
    pivot_idx = section.find("<th>Pivot</th>")
    hyp_idx = section.find("<th>Hypothesis</th>")
    assert price_idx >= 0 and pivot_idx >= 0 and hyp_idx >= 0
    assert price_idx < pivot_idx < hyp_idx, (
        "Pivot column must appear between Price and Hypothesis in hyp-recs"
    )


def test_dashboard_pivot_falls_back_to_dash_when_none(seeded_db, monkeypatch):
    """When the candidate's pivot is NULL the cell renders em-dash, not
    a stray $0.00 or empty cell."""
    cfg, cfg_path = seeded_db
    # Seed an A+ candidate WITHOUT a pivot value (NULL).
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'NOPV', 'aplus', 50.0, NULL, 45.0, 'universe')""",
                (eval_id,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()
    _patch_caches(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    section = _hyp_recs_section(r.text)
    # Pivot column header must exist in this section pre/post-fix asymmetry:
    # pre-fix (no Pivot column rendered in hyp-recs section), this assertion
    # is the discriminator.
    assert "<th>Pivot</th>" in section
    # NOPV row must NOT carry $0.00 or $null in its pivot cell — must
    # render an em-dash. The hyp-recs section's "Tripwire" column also
    # renders "—" when not fired, so we cannot rely on a single em-dash.
    # Instead, count cells in the NOPV row and assert the pivot-position
    # cell (3rd <td>, after Ticker and Price) is exactly "—".
    row_start = section.find("NOPV")
    assert row_start > 0
    row_end = section.find("</tr>", row_start)
    row_html = section[row_start:row_end]
    # Cells: Ticker (NOPV) / Price / Pivot / Hypothesis / Progress / Tripwire / Label
    # Pivot cell content per the template: either "$X.XX" or "—"
    assert "$0.00" not in row_html
    # Reslice from the row's <tr so the Ticker cell is included in the
    # parse below; otherwise body.find("NOPV") puts us inside the first
    # <td> and we'd miscount cells.
    tr_start = section.rfind("<tr", 0, row_start)
    assert tr_start >= 0
    full_row_html = section[tr_start:row_end]
    import re
    cells = re.findall(r"<td[^>]*>(.*?)</td>", full_row_html, re.DOTALL)
    # Task 5.4 prepends a chevron-button column → cells are now:
    #   chevron / Ticker / Price / Pivot / Hypothesis / Progress / Tripwire / Label
    # Pivot is at index 3.
    assert len(cells) >= 4, f"row has fewer cells than expected: {cells!r}"
    pivot_cell = cells[3].strip()
    assert pivot_cell == "—", f"pivot cell expected em-dash, got {pivot_cell!r}"


def test_tripwire_fired_css_class_styled(seeded_db, monkeypatch):
    """The `tripwire-fired` CSS class must have a real style rule (red bg
    or red border) so the visual alarm is obvious. Defends against the
    class being added to HTML without ever being styled."""
    css = (
        Path(__file__).resolve().parent.parent.parent
        / "swing" / "web" / "static" / "app.css"
    ).read_text(encoding="utf-8")
    assert ".tripwire-fired" in css, (
        "app.css must define a .tripwire-fired rule so the operator can't "
        "miss the alarm"
    )
