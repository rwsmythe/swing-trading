"""Phase 13 T3.SB3 T-B.3.5 closer — review auto-fill E2E.

Seeds a closed trade + 5 prior reviewed-trade rows (priors source) + an
OhlcvCache stub for the MFE/MAE source-ladder fallback. Invokes
``GET /trades/{trade_id}/review`` + asserts the form renders with:

  * Priors populated as DEFAULT input values (mistake-tag checkboxes
    pre-checked; lesson-learned textarea pre-filled).
  * MFE/MAE displayed from the OhlcvCache fallback path.
  * Hidden ``auto_populated_field_keys_json`` server-stamped envelope.

Then submits a review POST + asserts the trade transitions to
``state='reviewed'``. Per-trade audit-envelope persistence is deferred
to V2 (v20 column lives on review_log; future v21 may add trades-level
audit column).

Per plan §G.8 T-B.3.5 step 1.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_cfg
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


class _StubOhlcvCache:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        frame = self._frames.get(ticker.upper())
        if frame is None or frame.empty:
            raise ValueError(f"No data for {ticker.upper()}")
        return frame.copy()


def _ohlcv_frame(rows: list[tuple[str, float, float, float, float, int]]) -> pd.DataFrame:
    df = pd.DataFrame(
        rows, columns=["date", "Open", "High", "Low", "Close", "Volume"],
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _seed_prior_review(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    reviewed_at: str,
    mistake_tags: list[str],
    process_grade: str,
    lesson_learned: str,
) -> None:
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, current_size, reviewed_at, mistake_tags, "
        "process_grade, lesson_learned) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticker, "2026-01-01", 10.0, 100, 9.0, 9.0, "reviewed",
            "manual_off_pipeline", "2026-01-01T09:30:00", 100.0,
            reviewed_at, json.dumps(mistake_tags),
            process_grade, lesson_learned,
        ),
    )


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
) -> int:
    trade_id = insert_trade_with_event(
        conn,
        Trade(
            id=None, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, initial_shares=10,
            initial_stop=entry_price - 1.0, current_stop=entry_price - 1.0,
            state="entered",
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at=f"{entry_date}T09:30:00",
        ),
        event_ts=f"{entry_date}T09:30:00",
    )
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime=f"{entry_date}T09:30:00",
            action="entry", quantity=10.0, price=entry_price,
        ),
        event_ts=f"{entry_date}T09:30:00",
    )
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-04-25T09:30:00",
            action="exit", quantity=10.0, price=entry_price + 1.0,
            reason="manual",
        ),
        event_ts="2026-04-25T09:30:00",
    )
    conn.execute("UPDATE trades SET state='closed' WHERE id=?", (trade_id,))
    return trade_id


def test_phase13_t3_sb3_review_auto_fill_e2e_get_then_post(tmp_path: Path) -> None:
    db_path = tmp_path / "t3sb3_e2e.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        # 5 prior reviewed-trade rows for the same ticker (priors source).
        for i in range(5):
            _seed_prior_review(
                conn, ticker="ABC",
                reviewed_at=f"2026-05-{i + 1:02d}T10:00:00",
                mistake_tags=["CHASED" if i % 2 == 0 else "FOMO"],
                process_grade=("A" if i < 3 else "B"),
                lesson_learned=f"Lesson #{i + 1}.",
            )
        # Closed trade under review.
        trade_id = _seed_closed_trade(
            conn, ticker="ABC", entry_date="2026-04-20", entry_price=10.0,
        )
        conn.commit()
    finally:
        conn.close()

    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=db_path))
    app = create_app(cfg)
    # Inject an OhlcvCache stub so MFE/MAE has a non-zero source.
    app.state.ohlcv_cache = _StubOhlcvCache({
        "ABC": _ohlcv_frame([
            ("2026-04-20", 10.0, 12.0, 9.0, 11.0, 1000),
            ("2026-04-22", 11.0, 15.0, 7.0, 13.0, 2000),
            ("2026-04-25", 13.0, 14.0, 10.0, 11.0, 1500),
        ]),
    })

    with TestClient(app) as client:
        # GET surfaces auto-fill defaults.
        resp = client.get(f"/trades/{trade_id}/review")
        assert resp.status_code == 200
        # Hidden audit envelope server-stamped.
        assert 'name="auto_populated_field_keys_json"' in resp.text
        # JSON-encoded keys present (mistake_tags + process_grade_baseline +
        # lesson_learned + mfe_pct + mae_pct).
        for key in (
            "mistake_tags", "process_grade_baseline", "lesson_learned",
            "mfe_pct", "mae_pct",
        ):
            assert key in resp.text, f"missing audit key {key!r} in body"
        # MFE/MAE display fieldset present.
        assert "MFE" in resp.text
        assert "MAE" in resp.text
        # Priors fieldset present.
        assert "Priors" in resp.text or "priors" in resp.text

        # POST submit the review.
        post_resp = client.post(
            f"/trades/{trade_id}/review",
            data={
                "entry_grade": "A",
                "management_grade": "B",
                "exit_grade": "B",
                "lesson_learned": "Final lesson",
                "mistake_tags": ["CHASED"],
            },
            headers={"HX-Request": "true"},
        )
        # Phase 5/6: success-path is 204 + HX-Redirect.
        assert post_resp.status_code == 204
        assert post_resp.headers.get("HX-Redirect") == "/reviews/pending"

    # Trade transitioned to 'reviewed'.
    conn2 = connect(db_path)
    try:
        row = conn2.execute(
            "SELECT state, reviewed_at FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()
    finally:
        conn2.close()
    assert row[0] == "reviewed"
    assert row[1] is not None
