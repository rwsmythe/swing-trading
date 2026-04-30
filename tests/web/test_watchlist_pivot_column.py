"""CC pivot bug fix — discriminating regression across all three render sites.

Spec §3.9 — Q-G resolution; R1-Major-3 + R2-Major-1.

Each test uses entry_target=$42.00 vs candidates.pivot=$44.50 so the
pre-fix path (entry_target binding) and post-fix path (current_pivot
binding) produce visually distinct output. Lightning trigger fixture
asserts the trigger DOES fire under the entry_target binding even
after the column display switches to current_pivot — proving the
trigger binding survives the column-display change.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot

# `_seed_watchlist_and_candidate` and `_make_watchlist_entry` were lifted
# to `tests/web/conftest.py` as the `seed_watchlist_and_candidate` fixture
# (Phase 4 Task 11). Tests below consume the fixture by parameter.


def _patch_price_cache(monkeypatch, ticker: str, price: float | None) -> None:
    """Patch PriceCache.get_many so the dashboard / watchlist rendering does
    not hit yfinance during tests."""
    if price is None:
        snapshot_map: dict[str, PriceSnapshot] = {}
    else:
        snapshot_map = {
            ticker: PriceSnapshot(
                ticker=ticker,
                price=price,
                asof=datetime.now(),
                is_stale=False,
                source="live",
            )
        }
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snapshot_map[t] for t in tickers if t in snapshot_map
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_dashboard_top5_pivot_column_renders_current_pivot(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """R1-Major-3 site 1: dashboard top-5 watchlist row.

    Discriminating fixture: entry_target=$42.00 vs candidates.pivot=$44.50.
    Pre-fix render emits $42.00; post-fix emits $44.50.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot column for PYPL must render $44.50 (current_pivot), NOT $42.00.
    assert "$44.50" in body, "post-fix Pivot column must render candidates.pivot"
    assert "$42.00" not in body, (
        "pre-fix Pivot column rendered entry_target — fix did not apply to "
        "watchlist_top5_section.html.j2"
    )


def test_standalone_watchlist_pivot_column_renders_current_pivot(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """R1-Major-3 site 2: standalone /watchlist page."""
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body
    assert "$42.00" not in body


def test_watchlist_row_close_path_pivot_column_renders_current_pivot(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """R1-Major-3 site 3: GET /watchlist/{ticker}/row close-path.

    Without the WatchlistRowVM.current_pivot extension, this would revert
    to $42.00 (entry_target) post-close, recreating the bug exactly when
    the operator most needs the current value.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/watchlist/PYPL/row",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body, (
        "WatchlistRowVM.current_pivot did not propagate to the row-collapse "
        "render path"
    )
    assert "$42.00" not in body


def test_pivot_column_falls_back_to_entry_target_when_no_candidate(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """When candidates_by_ticker has no row for the ticker (rotated out
    of finviz; not an open trade), the Pivot column falls back to
    entry_target — the fix should not REGRESS this path."""
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="NEM", entry_target=42.00,
        candidate_pivot=None, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "NEM", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # Falls back to entry_target.
    assert "$42.00" in body


def test_pivot_column_dash_when_both_absent(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """R1-Minor-3 dash sentinel: when candidate_pivot is absent AND
    entry_target is None, the cell renders '—' (NOT $0.00)."""
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="NEM", entry_target=None,
        candidate_pivot=None, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "NEM", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot cell for NEM renders '—', NOT '$0.00'.
    assert "$0.00" not in body, (
        "R1-Minor-3 dash sentinel: missing pivot must render '—', not '$0.00'"
    )


def test_lightning_trigger_unchanged_uses_entry_target(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Q4 + spec §3.8 — lightning trigger stays bound to entry_target.

    Discriminating fixture chosen so the trigger fires under entry_target
    binding but would NOT fire under current_pivot binding:
      - entry_target = $42.00; current_pivot = $100.00; price = $41.60.
      - 41.60 ≥ 0.99 × 42 = 41.58 → lightning fires (entry_target binding).
      - 41.60 ≥ 0.99 × 100 = 99   → would NOT fire (current_pivot binding).
    Asserting the lightning glyph IS present proves the trigger binding
    survives the column-display change.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="PYPL", entry_target=42.00,
        candidate_pivot=100.00, last_close=41.60,
    )
    _patch_price_cache(monkeypatch, "PYPL", 41.60)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "⚡" in body, (
        "Lightning trigger must remain bound to entry_target after CC pivot "
        "fix — fired at $41.60 ≥ 0.99 × $42.00"
    )
    # Sanity: the column itself shows current_pivot ($100.00).
    assert "$100.00" in body
