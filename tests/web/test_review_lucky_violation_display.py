"""Phase 10 Sub-bundle B T-B.7 (electives amendment §2) tests.

Surfaces ``lucky_violation_R_display`` + ``mistake_cost_R_display`` on the
Phase 6 review form symmetrically. Per amendment §2 acceptance:
- both fields render "—" when ``realized_R_if_plan_followed IS NULL``
  OR when the computed value is 0.0;
- otherwise both render with 2-decimal-place precision;
- existing review form continues to render (Phase 6 regression check).
"""
from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app
from swing.web.view_models.trades import build_review_vm


@pytest.fixture
def cfg_factory(tmp_path: Path):
    """Return a callable that seeds a fresh DB + returns (cfg, cfg_path)."""
    base_cfg = load_config(Path("swing.config.toml"))

    def _factory(suffix: str = "") -> tuple:
        db_path = tmp_path / f"phase10_tb7{suffix}.db"
        ensure_schema(db_path).close()
        cfg = dc_replace(
            base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
        )
        return cfg, Path("swing.config.toml")
    return _factory


def _seed_closed_trade(
    cfg, *,
    trade_id: int,
    ticker: str,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    exit_price: float = 11.0,
    realized_R_if_plan_followed: float | None = None,  # noqa: N803
) -> int:
    """Seed a closed (state='closed') trade with entry + exit fills.

    Note: ``realized_R_if_plan_followed`` is a Phase 6 review-form field
    persisted on the trade row at review-submit time — not at trade
    creation. The seeder applies it via direct UPDATE to mirror the
    post-review state.
    """
    conn = connect(cfg.paths.db_path)
    with conn:
        tid = insert_trade_with_event(
            conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-01",
                entry_price=entry_price, initial_shares=initial_shares,
                initial_stop=initial_stop, current_stop=initial_stop,
                state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-01T09:30:00",
            ),
            event_ts="2026-04-01T09:30:00",
        )
        insert_fill_with_event(
            conn, Fill(
                fill_id=None, trade_id=tid,
                fill_datetime="2026-04-01T09:30:00",
                action="entry", quantity=initial_shares, price=entry_price,
            ),
            event_ts="2026-04-01T09:30:00",
        )
        insert_fill_with_event(
            conn, Fill(
                fill_id=None, trade_id=tid,
                fill_datetime="2026-04-08T15:30:00",
                action="exit", quantity=initial_shares, price=exit_price,
                reason="manual",
            ),
            event_ts="2026-04-08T15:30:00",
        )
        conn.execute(
            "UPDATE trades SET state='closed', "
            "realized_R_if_plan_followed=? WHERE id=?",
            (realized_R_if_plan_followed, tid),
        )
    conn.close()
    return tid


# ---------------------------------------------------------------------------
# VM-layer tests (per electives amendment §2 acceptance)
# ---------------------------------------------------------------------------

def test_vm_mistake_cost_positive_when_plan_followed_better_than_actual(
    cfg_factory,
) -> None:
    """Trade with plan=+2.0R, actual=+0.5R ⇒ mistake_cost_R=+1.5;
    lucky_violation_R=0 (rendered as None)."""
    cfg, _ = cfg_factory("_a")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="SE",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.50,  # +0.5R
        realized_R_if_plan_followed=2.0,
    )
    vm = build_review_vm(trade_id=tid, cfg=cfg)
    assert vm is not None
    assert vm.actual_realized_R_effective == pytest.approx(0.5, abs=0.001)
    assert vm.mistake_cost_R_display == pytest.approx(1.5, abs=0.001)
    assert vm.lucky_violation_R_display is None


def test_vm_lucky_violation_positive_when_actual_better_than_plan(
    cfg_factory,
) -> None:
    """Trade with plan=+1.5R, actual=+3.0R ⇒ mistake_cost_R=0 (None);
    lucky_violation_R=+1.5."""
    cfg, _ = cfg_factory("_b")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="LL",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=13.00,  # +3.0R
        realized_R_if_plan_followed=1.5,
    )
    vm = build_review_vm(trade_id=tid, cfg=cfg)
    assert vm is not None
    assert vm.actual_realized_R_effective == pytest.approx(3.0, abs=0.001)
    assert vm.mistake_cost_R_display is None
    assert vm.lucky_violation_R_display == pytest.approx(1.5, abs=0.001)


def test_vm_both_zero_when_plan_followed_exactly(cfg_factory) -> None:
    """Trade with plan=+2.0R, actual=+2.0R ⇒ both fields render None
    (the "—" placeholder per amendment §2 suppression rule)."""
    cfg, _ = cfg_factory("_c")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="EXAC",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=12.00,  # +2.0R exact
        realized_R_if_plan_followed=2.0,
    )
    vm = build_review_vm(trade_id=tid, cfg=cfg)
    assert vm is not None
    assert vm.mistake_cost_R_display is None
    assert vm.lucky_violation_R_display is None


def test_vm_both_none_when_plan_unspecified(cfg_factory) -> None:
    """When ``realized_R_if_plan_followed IS NULL``, both fields render
    None — no counterfactual recorded."""
    cfg, _ = cfg_factory("_d")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="UNK",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        realized_R_if_plan_followed=None,
    )
    vm = build_review_vm(trade_id=tid, cfg=cfg)
    assert vm is not None
    assert vm.mistake_cost_R_display is None
    assert vm.lucky_violation_R_display is None


# ---------------------------------------------------------------------------
# Template-layer tests (Phase 6 regression + T-B.7 symmetric render)
# ---------------------------------------------------------------------------

def test_review_form_renders_mistake_cost_value_inline(cfg_factory) -> None:
    """Mistake-cost trade renders the numeric value in the dd cell."""
    cfg, cfg_path = cfg_factory("_e")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="SE",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.50, realized_R_if_plan_followed=2.0,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    body = r.text
    # Mistake-cost row carries the value 1.50 (2.0 - 0.5).
    assert 'data-field="mistake_cost_R"' in body
    assert "1.50" in body
    # Lucky-violation row exists + renders "—".
    assert 'data-field="lucky_violation_R"' in body
    assert "—" in body


def test_review_form_renders_lucky_violation_value_inline(cfg_factory) -> None:
    """Lucky-violation trade renders the numeric value in the dd cell."""
    cfg, cfg_path = cfg_factory("_f")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="LL",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=13.00, realized_R_if_plan_followed=1.5,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    body = r.text
    assert 'data-field="lucky_violation_R"' in body
    assert "1.50" in body
    assert 'data-field="mistake_cost_R"' in body
    assert "—" in body


def test_review_form_renders_both_em_dash_when_plan_followed_exactly(
    cfg_factory,
) -> None:
    """Per amendment §2: both fields render '—' when plan_followed_exact."""
    cfg, cfg_path = cfg_factory("_g")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="EXAC",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=12.00, realized_R_if_plan_followed=2.0,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    body = r.text
    # Both dd cells render the em-dash placeholder.
    assert body.count("—") >= 2


def test_review_form_phase6_regression_existing_form_renders(
    cfg_factory,
) -> None:
    """Phase 6 regression check: the existing review form fields still
    render — operator entry fields + submit button unchanged by T-B.7."""
    cfg, cfg_path = cfg_factory("_h")
    tid = _seed_closed_trade(
        cfg, trade_id=1, ticker="REG",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0, realized_R_if_plan_followed=1.0,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    body = r.text
    # Phase 6 existing form fields:
    assert 'name="realized_R_if_plan_followed"' in body
    assert 'name="mistake_cost_confidence"' in body
    assert 'name="lesson_learned"' in body
    assert "Submit review" in body
