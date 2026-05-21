"""Phase 13 T3.SB3 T-B.3.3 — review_form_page + ReviewVM auto-fill extension.

Per plan §G.8 T-B.3.3 acceptance (7+ tests):
  (a) Form renders with priors populated as DEFAULT input values.
  (b) MFE/MAE auto-populated.
  (c) Hidden ``auto_populated_field_keys_json`` field present + server-
      stamped at handler entry (operator cannot tamper).
  (d) Session-anchor ``last_completed_session(now())`` aligned.
  (e) ``ReviewVM`` extends ``BaseLayoutVM`` (banner fields).
  (f) Form renders gracefully at zero priors (no priors row exists).
  (g) ``ReviewVM`` populates ``unresolved_material_discrepancies_count`` +
      ``banner_resolve_link`` + ``recent_multi_leg_auto_correction_count``
      per forward-binding lesson #12 + Phase 10 §A.18 helper.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

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
    """Test-only stub mirroring ``OhlcvCache.get_or_fetch`` shape contract."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames
        self.calls: list[tuple[str, int]] = []

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        self.calls.append((ticker.upper(), int(window_days)))
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


def _seed_reviewed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    reviewed_at: str,
    mistake_tags: list[str] | None = None,
    process_grade: str | None = None,
    lesson_learned: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "current_size, reviewed_at, mistake_tags, process_grade, lesson_learned) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticker, "2026-01-01", 10.0, 100, 9.0, 9.0, "reviewed",
            "manual_off_pipeline", "2026-01-01T09:30:00", 100.0,
            reviewed_at,
            json.dumps(mistake_tags) if mistake_tags is not None else None,
            process_grade,
            lesson_learned,
        ),
    )
    return cursor.lastrowid


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str = "2026-04-20",
    entry_price: float = 10.0,
) -> int:
    """Insert a CLOSED trade (eligible for per-trade review)."""
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


@pytest.fixture
def app_factory(tmp_path: Path):
    def _factory(stub_cache: Any | None = None):
        db_path = tmp_path / "review_auto_fill.db"
        ensure_schema(db_path).close()
        conn = connect(db_path)
        try:
            yield_state: dict[str, Any] = {"conn": conn, "db_path": db_path}
            return yield_state
        finally:
            pass

    return _factory


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "review_auto_fill.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    yield conn
    conn.close()


# --- (a) Form renders with priors populated as DEFAULT input values ---


def test_build_review_vm_populates_priors_from_prior_reviews(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    from swing.web.view_models.trades import build_review_vm

    # Two prior reviewed trades for the same ticker (priors source).
    _seed_reviewed_trade(
        fresh_db, ticker="ABC", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["CHASED"], process_grade="B",
        lesson_learned="Wait for proper base.",
    )
    _seed_reviewed_trade(
        fresh_db, ticker="ABC", reviewed_at="2026-05-10T10:00:00",
        mistake_tags=["FOMO"], process_grade="A",
        lesson_learned="Be patient at the breakout.",
    )
    # The trade under review (different id; same ticker).
    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()

    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))

    cache = _StubOhlcvCache({})
    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    assert vm.priors is not None
    assert set(vm.priors.mistake_tag_candidates) == {"CHASED", "FOMO"}
    assert vm.priors.process_grade_baseline == pytest.approx(3.5)
    assert vm.priors.lesson_learned_candidates == (
        "Be patient at the breakout.", "Wait for proper base.",
    )


# --- (b) MFE/MAE auto-populated from OhlcvCache (no Phase 8 coverage) ---


def test_build_review_vm_populates_mfe_mae_from_ohlcv_cache(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    from swing.web.view_models.trades import build_review_vm

    trade_id = _seed_closed_trade(
        fresh_db, ticker="XYZ", entry_date="2026-04-20", entry_price=10.0,
    )
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))

    # High since entry = 15.0; Low = 7.0 → mfe = 0.50; mae = -0.30.
    cache = _StubOhlcvCache({
        "XYZ": _ohlcv_frame([
            ("2026-04-20", 10.0, 12.0, 9.0, 11.0, 1000),
            ("2026-04-22", 11.0, 15.0, 7.0, 13.0, 2000),
            ("2026-04-25", 13.0, 14.0, 10.0, 11.0, 1500),
        ]),
    })
    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    assert vm.mfe_pct == pytest.approx(0.50)
    assert vm.mae_pct == pytest.approx(-0.30)


# --- (c) Hidden auto_populated_field_keys_json field present + server-
#         stamped at handler entry (operator cannot tamper) ---


def test_build_review_vm_server_stamps_auto_populated_field_keys_json(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    from swing.web.view_models.trades import build_review_vm

    # Seed prior priors so multiple keys auto-populate.
    _seed_reviewed_trade(
        fresh_db, ticker="ABC", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["CHASED"], process_grade="B",
        lesson_learned="Lesson NEW",
    )
    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})

    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    # JSON-encoded array of auto-populated field keys.
    assert vm.auto_populated_field_keys_json is not None
    decoded = json.loads(vm.auto_populated_field_keys_json)
    assert isinstance(decoded, list)
    assert set(decoded) >= {
        "mistake_tags", "process_grade_baseline", "lesson_learned",
    }


def test_build_review_vm_auto_populated_field_keys_json_excludes_empty_fields(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Fields without an auto-fill source must NOT appear in the audit
    array. Operator-typed fields stay attributable."""
    from swing.web.view_models.trades import build_review_vm

    # No priors seeded for the trade's ticker.
    trade_id = _seed_closed_trade(fresh_db, ticker="EMPTY")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})  # no data

    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    assert vm.auto_populated_field_keys_json is not None
    decoded = json.loads(vm.auto_populated_field_keys_json)
    # Zero-priors + zero-cache-data → empty audit array.
    assert decoded == []


# --- (d) Session-anchor last_completed_session(now()) aligned ---


def test_build_review_vm_populates_session_date_from_last_completed_session(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    from swing.evaluation.dates import last_completed_session
    from swing.web.view_models.trades import build_review_vm
    from datetime import datetime as _dt

    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})

    expected_session = last_completed_session(_dt.now()).isoformat()
    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    # session_date is now populated (was "" default before T-B.3.3).
    assert vm.session_date == expected_session


# --- (e) ReviewVM carries BaseLayoutVM banner fields (already in place;
#         this test pins the existence so any drift is caught) ---


def test_review_vm_carries_base_layout_banner_fields(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    from swing.web.view_models.trades import build_review_vm

    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})

    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    # 5-VM base layout fields:
    assert hasattr(vm, "session_date")
    assert hasattr(vm, "stale_banner")
    assert hasattr(vm, "price_source_degraded")
    assert hasattr(vm, "ohlcv_source_degraded")


# --- (f) Form renders gracefully at zero priors ---


def test_build_review_vm_renders_gracefully_at_zero_priors(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A trade for a ticker with no prior reviews still builds a valid VM
    with empty priors + no raise (§A.16 graceful at n=0)."""
    from swing.trades.review import ReviewPriors
    from swing.web.view_models.trades import build_review_vm

    trade_id = _seed_closed_trade(fresh_db, ticker="VIRGIN")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})

    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    assert vm.priors == ReviewPriors(
        mistake_tag_candidates=(),
        process_grade_baseline=None,
        lesson_learned_candidates=(),
    )
    assert vm.mfe_pct == 0.0
    assert vm.mae_pct == 0.0


# --- (g) banner counters populated per forward-binding lesson #12 ---


def test_build_review_vm_populates_phase_10_banner_counters(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """ReviewVM extends BaseLayoutVM banner mixin via 3 banner counters.
    Forward-binding lesson #12 + Phase 10 §A.18 helper require explicit
    population at handler entry; zero-state default is 0 / None."""
    from swing.web.view_models.trades import build_review_vm

    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))
    cache = _StubOhlcvCache({})

    vm = build_review_vm(trade_id=trade_id, cfg=cfg, ohlcv_cache=cache)
    assert vm is not None
    # Pre-existing counters — populated to integer zero with no banner state.
    assert vm.unresolved_material_discrepancies_count == 0
    assert vm.recent_multi_leg_auto_correction_count == 0
    assert vm.banner_resolve_link is None


# --- (h) ReviewVM is backwards-compatible with the no-cache call site ---


def test_build_review_vm_ohlcv_cache_param_defaults_to_none(
    fresh_db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Existing callsites that don't pass ohlcv_cache must continue to
    work — MFE/MAE simply render as 0.0 + don't appear in the audit
    array."""
    from swing.web.view_models.trades import build_review_vm

    trade_id = _seed_closed_trade(fresh_db, ticker="ABC")
    fresh_db.commit()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=tmp_path / "review_auto_fill.db"))

    # No ohlcv_cache kwarg — backwards-compat.
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    assert vm is not None
    assert vm.mfe_pct == 0.0
    assert vm.mae_pct == 0.0


# --- (i) Round-trip: GET /trades/{id}/review surfaces auto-populated keys ---


def test_get_trade_review_surfaces_auto_populated_field_keys_json(
    tmp_path: Path,
) -> None:
    """End-to-end GET surfaces the hidden audit field in the response
    body. Confirms server-stamping flows through the route handler +
    template, not just the VM construction."""
    db_path = tmp_path / "phase13_t3sb3.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        _seed_reviewed_trade(
            conn, ticker="ABC", reviewed_at="2026-05-01T10:00:00",
            mistake_tags=["CHASED"], process_grade="B",
            lesson_learned="Wait for breakout.",
        )
        trade_id = _seed_closed_trade(conn, ticker="ABC")
        conn.commit()
    finally:
        conn.close()
    cfg = load_cfg(Path("swing.config.toml"))
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=db_path))
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(f"/trades/{trade_id}/review")
    assert resp.status_code == 200
    # Hidden form input must be present.
    assert 'name="auto_populated_field_keys_json"' in resp.text
    # JSON-encoded keys round-trip into the page body.
    assert "mistake_tags" in resp.text
    assert "process_grade_baseline" in resp.text
    assert "lesson_learned" in resp.text
