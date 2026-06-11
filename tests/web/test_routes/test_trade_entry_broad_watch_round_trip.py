"""Task 5 — entry-form server-stamps Broad-watch baseline label for watch
candidates (include_baseline=True opt-in at the prefill call site).

Two tests:
  (a) GET /trades/entry/form?ticker=WCH stamps the broad-watch label in
      the hidden hypothesis_label input.
  (b) POST soft-warn round-trip: the stamped label survives the soft-warn
      confirm fragment and is persisted after force=true resubmit.

Seed: `_seed_watch_pipeline` inserts bucket='watch' candidate with no
criteria rows → label = "Broad-watch baseline (watch)" (no failing
criteria; label_matches_hypothesis prefix-contract satisfied).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app
from tests.web.conftest import full_phase7_entry_payload

BROAD_PREFIX = "Broad-watch baseline"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_watch_pipeline(db_path: Path, ticker: str) -> None:
    """Insert a completed pipeline_run with one watch-bucket candidate.

    No criteria rows seeded → criteria=() → label = "Broad-watch baseline (watch)".
    """
    conn = connect(db_path)
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
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'watch', 180.0, 181.0, 170.0, 'universe')""",
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


def _seed_n_open_trades(db_path: Path, n: int) -> None:
    """Seed n open trades to trip the default soft_warn_open=4 gate.

    Uses unique tickers to avoid the one-open-per-ticker constraint.
    The conftest autouse fixture auto-adds entry fills so trades are in
    valid 'entered' state.
    """
    tickers = ["MSFT", "NVDA", "AMD", "TSLA", "META", "AMZN", "GOOGL", "NFLX"]
    conn = connect(db_path)
    try:
        with conn:
            for t in tickers[:n]:
                insert_trade_with_event(
                    conn,
                    Trade(
                        id=None, ticker=t, entry_date="2026-04-10",
                        entry_price=100.0, initial_shares=1,
                        initial_stop=90.0, current_stop=90.0,
                        state="entered",
                        watchlist_entry_target=None,
                        watchlist_initial_stop=None,
                        notes=None,
                    ),
                    event_ts="2026-04-10T09:30:00",
                )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cloned helpers from test_trade_entry_hypothesis_thread.py
# ---------------------------------------------------------------------------


def _read_persisted_hypothesis_label(db_path: Path, ticker: str) -> str | None:
    """Read the most-recent trade row for ticker; return its hypothesis_label."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT hypothesis_label FROM trades WHERE ticker = ? "
            "ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def _parse_hidden_inputs(html: str) -> dict[str, str]:
    """Extract every <input type="hidden" name="..." value="..."> tag."""
    return dict(re.findall(
        r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
        html,
    ))


def _rendered_hypothesis_label(client: TestClient, ticker: str) -> str:
    html = client.get(f"/trades/entry/form?ticker={ticker}").text
    m = re.search(r'name="hypothesis_label"\s+value="([^"]*)"', html)
    assert m, f"entry form must render a hidden hypothesis_label input; got: {html[:500]!r}"
    return m.group(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_entry_form_server_stamps_broad_watch_label(seeded_db):
    """GET /trades/entry/form?ticker=WCH stamps the broad-watch label when
    the candidate is bucket='watch' with no narrow hypothesis match."""
    cfg, cfg_path = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        label = _rendered_hypothesis_label(client, "WCH")
    assert label.startswith(BROAD_PREFIX), (
        f"expected broad-watch label starting with {BROAD_PREFIX!r}; got {label!r}"
    )


def test_broad_watch_label_persists_through_soft_warn_force_resubmit(seeded_db):
    """POST soft-warn round-trip: the broad-watch stamp survives the soft-warn
    confirm fragment and is persisted after force=true resubmit.

    Flow mirrors test_post_entry_soft_warn_round_trip_via_fragment_faithful_resubmit
    from test_trade_entry_hypothesis_thread.py, substituting the watch seed and
    broad-watch expectation.

    Soft-warn tripped by seeding 4 open trades (default soft_warn_open=4).
    """
    cfg, cfg_path = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    _seed_n_open_trades(cfg.paths.db_path, n=4)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # GET the form to retrieve the server-stamped label.
        stamped = _rendered_hypothesis_label(client, "WCH")
        assert stamped.startswith(BROAD_PREFIX), (
            f"server-stamped label must start with {BROAD_PREFIX!r}; got {stamped!r}"
        )

        # First POST — should trigger soft-warn (4 open trades at soft_warn_open=4).
        payload = full_phase7_entry_payload(
            ticker="WCH",
            entry_date="2026-04-15",
            entry_price="180.0",
            shares="1",
            initial_stop="170.0",
            rationale="aplus-setup",
            hypothesis_label=stamped,
            sector="",
            industry="",
            origin="watchlist",
        )
        r_first = client.post("/trades/entry", data=payload,
                               headers={"HX-Request": "true"})
        assert r_first.status_code == 200, r_first.text

        # Confirm the fragment carries the broad-watch label as a hidden input.
        assert stamped in r_first.text, (
            f"soft-warn fragment must carry the broad-watch label; "
            f"stamped={stamped!r}\nfragment={r_first.text[:600]!r}"
        )
        fragment = _parse_hidden_inputs(r_first.text)
        assert fragment.get("hypothesis_label", "").startswith(BROAD_PREFIX), (
            f"fragment hidden inputs must carry hypothesis_label starting with "
            f"{BROAD_PREFIX!r}; got {fragment!r}"
        )

        # Force resubmit.
        fragment["force"] = "true"
        r_second = client.post("/trades/entry", data=fragment,
                                headers={"HX-Request": "true"})
        assert r_second.status_code in (200, 204), r_second.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "WCH")
    assert persisted is not None and persisted.startswith(BROAD_PREFIX), (
        f"persisted hypothesis_label must start with {BROAD_PREFIX!r}; got {persisted!r}"
    )
